"""Get ESLint rules relevant to a specific file (formerly coding standards)."""

from typing import Any
from pathlib import Path

from .._security import validate_file_path, get_project_root
from ..standards_management.pattern_matcher import get_file_categories
from ..eslint_metadata.rules_registry import ESLintRulesRegistry
from ..eslint_metadata.pattern_matcher import categorize_rules_by_file_type, get_file_type_from_patterns


def get_relevant_standards_impl(
    file_path: str,
    project_root: str,
    include_general: bool = True
) -> dict[str, Any]:
    """Get ESLint rules relevant to a specific file.
    
    This function has been migrated from reading original .aromcp/standards/*.md files
    to reading generated .aromcp/generated-rules/rules/*.js files. This creates proper
    separation between generation-time (standards) and runtime (ESLint rules) concerns.
    
    Args:
        file_path: File path to analyze for relevant ESLint rules
        project_root: Root directory of the project
        include_general: Whether to include rules without specific patterns (deprecated)
        
    Returns:
        Dict with matched ESLint rules and metadata
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
        
        # Initialize ESLint rules registry
        registry = ESLintRulesRegistry(project_root)
        
        # Load generated ESLint rules
        registry_result = registry.load_generated_rules()
        if "error" in registry_result:
            # Provide helpful error message if no generated rules exist
            error = registry_result["error"]
            if error.get("code") == "NOT_FOUND":
                return {
                    "error": {
                        "code": "ESLINT_RULES_NOT_FOUND",
                        "message": "Generated ESLint rules not found. Please run the ESLint rule generation command first.",
                        "suggestion": "Use the ESLint rule generation command (see documentation/commands/generate-eslint-rules.md) to create rules from your coding standards.",
                        "details": {
                            "expected_directory": str(Path(project_root) / ".aromcp" / "generated-rules" / "rules"),
                            "migration_note": "get_relevant_standards now reads ESLint rules instead of original standards files"
                        }
                    }
                }
            return registry_result
        
        registry_data = registry_result["data"]
        
        # Find applicable ESLint rules for the file
        applicable_rules = registry.find_applicable_rules(file_path, registry_data)
        
        # Extract categories from file path (same logic as before)
        categories = get_file_categories(file_path)
        
        # Add categories from rule patterns
        rule_patterns = []
        for rule in applicable_rules:
            rule_patterns.extend(rule.get("patterns", []))
        pattern_categories = get_file_type_from_patterns(rule_patterns)
        categories.extend(pattern_categories)
        categories = list(set(categories))  # Remove duplicates
        
        # Categorize rules by type (critical, recommended, optional)
        categorized_rules = categorize_rules_by_file_type(applicable_rules, file_path)
        
        # Format the applicable rules (maintain similar structure to original)
        formatted_rules = []
        for rule in applicable_rules:
            formatted_rules.append({
                "rule_id": rule.get("rule_id", "unknown"),
                "rule_file": rule.get("rule_file", ""),
                "name": rule.get("name", "Unnamed Rule"),
                "patterns": rule.get("patterns", []),
                "pattern_matched": rule.get("pattern_matched"),
                "specificity": rule.get("match_specificity", rule.get("specificity", 0.0)),
                "severity": rule.get("severity", "warn"),
                "tags": rule.get("tags", []),
                "eslint_rule_name": rule.get("eslint_rule_name", "")
            })
        
        # Calculate file statistics
        try:
            # Use the validated path from the security validation
            validated_path = validation_result["abs_path"]
            file_stat = validated_path.stat()
            file_size = file_stat.st_size
            file_exists = True
        except (OSError, FileNotFoundError):
            file_size = 0
            file_exists = False
        
        # Calculate summary statistics
        specificities = [rule.get("specificity", 0.0) for rule in formatted_rules]
        highest_specificity = max(specificities) if specificities else 0.0
        
        return {
            "data": {
                "file_path": file_path,
                "file_exists": file_exists,
                "file_size": file_size,
                "applicable_rules": formatted_rules,
                "categories": categories,
                "total_rules": len(formatted_rules),
                "has_specific_rules": any(s > 0.2 for s in specificities),
                "highest_specificity": highest_specificity,
                "rules_by_category": {
                    "critical": len(categorized_rules["critical"]),
                    "recommended": len(categorized_rules["recommended"]), 
                    "optional": len(categorized_rules["optional"])
                },
                "eslint_config_section": _determine_eslint_config_section(categories),
                "summary": {
                    "specific_rules": len([s for s in specificities if s > 0.2]),
                    "general_rules": len([s for s in specificities if s <= 0.2]),
                    "unique_tags": list(set(
                        tag for rule in formatted_rules 
                        for tag in rule.get("tags", [])
                    )),
                    "severity_distribution": _get_severity_distribution(formatted_rules)
                },
                # Include registry information for debugging
                "registry_info": {
                    "total_rules_available": registry_data.get("summary", {}).get("valid_rules", 0),
                    "rules_directory": registry_data.get("rules_directory"),
                    "last_updated": registry_data.get("last_updated")
                }
            }
        }
        
    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to get relevant ESLint rules: {str(e)}"
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