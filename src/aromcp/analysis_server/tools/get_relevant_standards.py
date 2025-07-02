"""Get relevant standards for a specific file.

Updated for V2: Now reads from manifest.json to find applicable rules,
then loads from both generated ESLint rules and AI context sections.
"""

import os
import json
import fnmatch
from typing import Any
from pathlib import Path

from ...filesystem_server._security import get_project_root, validate_file_path


def get_relevant_standards_impl(
    file_path: str,
    project_root: str,
    include_general: bool = True
) -> dict[str, Any]:
    """Get relevant standards for a specific file.
    
    Updated for V2: Reads from manifest.json to find applicable rules,
    then loads from generated ESLint rules and AI context sections.
    
    Args:
        file_path: File path to analyze for relevant standards
        project_root: Root directory of the project
        include_general: Whether to include general/default standards
        
    Returns:
        Dict with matched standards from generated rules and AI context
    """
    try:
        # Validate the file path
        validation_result = validate_file_path(file_path, project_root)
        if not validation_result["valid"]:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Invalid file path: {validation_result['error']}"
                }
            }
        
        # Load manifest.json to find applicable rules
        manifest = _load_manifest(project_root)
        if not manifest:
            return {
                "error": {
                    "code": "RULES_NOT_GENERATED",
                    "message": "Generated rules manifest not found. Please run ESLint rule generation first.",
                    "suggestion": "Use extract_templates_from_standards and analyze_standards_for_rules to generate rules from your coding standards.",
                    "details": {
                        "expected_file": str(Path(project_root) / ".aromcp" / "generated-rules" / "manifest.json")
                    }
                }
            }
        
        # Find applicable rules based on file patterns
        applicable_rules = []
        ai_context_sections = []
        
        for rule_id, rule_metadata in manifest.get("rules", {}).items():
            # Check if rule patterns match the file
            patterns = rule_metadata.get("patterns", [])
            if _file_matches_patterns(file_path, patterns) or (include_general and not patterns):
                
                rule_entry = {
                    "id": rule_id,
                    "name": rule_metadata.get("name", rule_id.replace("-", " ").title()),
                    "type": rule_metadata.get("type", "unknown"),
                    "severity": rule_metadata.get("severity", "error"),
                    "patterns": patterns,
                    "last_updated": rule_metadata.get("updated"),
                    "source_standard": rule_metadata.get("source_standard"),
                    "pattern_matched": _get_matched_pattern(file_path, patterns)
                }
                
                if rule_metadata.get("type") == "eslint_rule":
                    # Load ESLint rule content
                    rule_content = _load_eslint_rule(project_root, rule_id)
                    if rule_content:
                        rule_entry["eslint_rule"] = rule_content
                    applicable_rules.append(rule_entry)
                    
                elif rule_metadata.get("type") == "ai_context":
                    # Load AI context section
                    context_content = _load_ai_context_section(project_root, rule_id)
                    if context_content:
                        rule_entry["ai_context"] = context_content
                    ai_context_sections.append(rule_entry)
                    
                elif rule_metadata.get("type") == "hybrid":
                    # Load both ESLint rule and AI context
                    rule_content = _load_eslint_rule(project_root, rule_id)
                    context_content = _load_ai_context_section(project_root, rule_id)
                    if rule_content:
                        rule_entry["eslint_rule"] = rule_content
                    if context_content:
                        rule_entry["ai_context"] = context_content
                    applicable_rules.append(rule_entry)
        
        # Determine file categories
        categories = _determine_file_categories(file_path)
        
        # Calculate file statistics
        try:
            file_path_obj = Path(project_root) / file_path
            if file_path_obj.exists():
                file_stat = file_path_obj.stat()
                file_size = file_stat.st_size
                file_exists = True
            else:
                file_size = 0
                file_exists = False
        except (OSError, FileNotFoundError):
            file_size = 0
            file_exists = False
        
        # Calculate specificity for applicable rules
        for rule in applicable_rules + ai_context_sections:
            rule["specificity"] = _calculate_pattern_specificity(rule.get("patterns", []), file_path)
        
        return {
            "data": {
                "file_path": file_path,
                "file_exists": file_exists,
                "file_size": file_size,
                "applicable_eslint_rules": applicable_rules,
                "ai_context_sections": ai_context_sections,
                "categories": categories,
                "total_applicable": len(applicable_rules) + len(ai_context_sections),
                "eslint_rules_count": len(applicable_rules),
                "ai_context_count": len(ai_context_sections),
                "eslint_config_section": _determine_eslint_config_section(categories),
                "manifest_info": {
                    "version": manifest.get("version"),
                    "last_updated": manifest.get("last_updated"),
                    "total_rules_in_manifest": len(manifest.get("rules", {})),
                    "statistics": manifest.get("statistics", {})
                },
                "summary": {
                    "highest_specificity": max([r.get("specificity", 0.0) for r in applicable_rules + ai_context_sections] or [0.0]),
                    "severity_distribution": _get_severity_distribution(applicable_rules + ai_context_sections),
                    "has_specific_rules": any(r.get("specificity", 0.0) > 0.5 for r in applicable_rules + ai_context_sections),
                    "rule_types": {
                        "eslint_only": len([r for r in applicable_rules if r.get("type") == "eslint_rule"]),
                        "ai_context_only": len(ai_context_sections),
                        "hybrid": len([r for r in applicable_rules if r.get("type") == "hybrid"])
                    }
                }
            }
        }
        
    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to get relevant standards: {str(e)}"
            }
        }


def _determine_eslint_config_section(categories: list[str]) -> str:
    """Determine appropriate ESLint config section based on file categories."""
    if "api" in categories or "routes" in categories:
        return "api-routes"
    elif "components" in categories or "react" in categories:
        return "components"
    elif "tests" in categories:
        return "testing"
    elif "typescript" in categories:
        return "typescript"
    elif "javascript" in categories:
        return "javascript"
    else:
        return "general"


def _get_severity_distribution(rules: list[dict[str, Any]]) -> dict[str, int]:
    """Get distribution of rule severities."""
    distribution = {}
    for rule in rules:
        severity = rule.get("severity", "warn")
        distribution[severity] = distribution.get(severity, 0) + 1
    return distribution


def _load_manifest(project_root: str) -> dict[str, Any] | None:
    """Load manifest.json from generated rules directory."""
    try:
        manifest_path = os.path.join(project_root, ".aromcp", "generated-rules", "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError, OSError):
        pass
    return None


def _file_matches_patterns(file_path: str, patterns: list[str]) -> bool:
    """Check if file path matches any of the given glob patterns."""
    if not patterns:
        return False
        
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False


def _get_matched_pattern(file_path: str, patterns: list[str]) -> str | None:
    """Get the first pattern that matches the file path."""
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return pattern
    return None


def _load_eslint_rule(project_root: str, rule_id: str) -> str | None:
    """Load ESLint rule content from generated rules directory."""
    try:
        rule_path = os.path.join(project_root, ".aromcp", "generated-rules", "rules", f"{rule_id}.js")
        if os.path.exists(rule_path):
            with open(rule_path, 'r', encoding='utf-8') as f:
                return f.read()
    except (IOError, OSError):
        pass
    return None


def _load_ai_context_section(project_root: str, section_id: str) -> str | None:
    """Load AI context section from ai-context.md file."""
    try:
        context_path = os.path.join(project_root, ".aromcp", "generated-rules", "ai-context.md")
        if os.path.exists(context_path):
            with open(context_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Extract specific section using markers
            start_marker = f"<!-- aromcp:section:start:{section_id} -->"
            end_marker = f"<!-- aromcp:section:end:{section_id} -->"
            
            start_idx = content.find(start_marker)
            if start_idx != -1:
                end_idx = content.find(end_marker, start_idx)
                if end_idx != -1:
                    section_content = content[start_idx + len(start_marker):end_idx].strip()
                    # Remove the header line if present
                    lines = section_content.split('\n')
                    if lines and lines[0].startswith('## '):
                        lines = lines[1:]
                    return '\n'.join(lines).strip()
    except (IOError, OSError):
        pass
    return None


def _determine_file_categories(file_path: str) -> list[str]:
    """Determine file categories based on path and extension."""
    categories = []
    
    # Extension-based categories
    if file_path.endswith(('.ts', '.tsx')):
        categories.append('typescript')
    elif file_path.endswith(('.js', '.jsx')):
        categories.append('javascript')
    elif file_path.endswith('.md'):
        categories.append('documentation')
    elif file_path.endswith(('.json', '.yaml', '.yml')):
        categories.append('configuration')
        
    # Path-based categories
    path_lower = file_path.lower()
    if '/components/' in path_lower or file_path.endswith(('.tsx', '.jsx')):
        categories.append('components')
    if '/api/' in path_lower or '/routes/' in path_lower:
        categories.append('api')
    if '/test' in path_lower or file_path.endswith('.test.') or file_path.endswith('.spec.'):
        categories.append('tests')
    if '/pages/' in path_lower:
        categories.append('pages')
    if '/hooks/' in path_lower or 'use' in os.path.basename(file_path).lower():
        categories.append('hooks')
        
    return list(set(categories))


def _calculate_pattern_specificity(patterns: list[str], file_path: str) -> float:
    """Calculate pattern specificity score (0.0 to 1.0)."""
    if not patterns:
        return 0.0
        
    # Find best matching pattern
    best_score = 0.0
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            # Score based on pattern specificity
            score = 0.1  # Base score for matching
            
            # Add points for specificity
            if '/' in pattern:
                score += 0.3  # Path specificity
            if pattern.count('*') == 1:
                score += 0.2  # Single wildcard
            elif pattern.count('*') == 0:
                score += 0.4  # No wildcards (exact match)
            if pattern.startswith('**/'):
                score += 0.1  # Deep path matching
            if pattern.endswith(('tsx', 'ts', 'jsx', 'js')):
                score += 0.1  # Extension specificity
                
            best_score = max(best_score, min(score, 1.0))
            
    return best_score