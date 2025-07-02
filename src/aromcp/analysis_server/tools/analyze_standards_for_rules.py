"""
Analyze standards and return a generation recipe.

This tool performs single-pass analysis of standards and project,
returning a simple recipe for AI to generate rules.
"""

import os
import json
import re
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from ...utils.json_parameter_middleware import json_convert
from ...filesystem_server._security import get_project_root, validate_file_path


def analyze_standards_for_rules_impl(
    standards_dir: str = ".aromcp/standards",
    project_root: str | None = None
) -> dict[str, Any]:
    """Analyze standards and return a generation recipe.
    
    Performs single-pass analysis of standards and project,
    returning a simple recipe for AI to generate rules.
    
    Args:
        standards_dir: Directory containing markdown standards files
        project_root: Project root directory (auto-resolved if None)
        
    Returns:
        Dict with standards, minimal project context, and generation hints
    """
    if project_root is None:
        project_root = get_project_root()
        
    try:
        # Validate input directory
        standards_path = os.path.join(project_root, standards_dir)
        validation_result = validate_file_path(standards_path, project_root)
        if not validation_result["valid"]:
            return {"error": {"code": "PERMISSION_DENIED", "message": validation_result["error"]}}
            
        if not os.path.exists(standards_path):
            return {"error": {"code": "NOT_FOUND", "message": f"Standards directory not found: {standards_dir}"}}
            
        # Load all standards
        standards = []
        for filename in os.listdir(standards_path):
            if not filename.endswith('.md'):
                continue
                
            file_path = os.path.join(standards_path, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                standard_metadata = _extract_standard_metadata(content, filename, file_path)
                if standard_metadata:
                    standards.append(standard_metadata)
                    
            except Exception:
                continue
                
        # Analyze project context
        project_context = _analyze_project_context(project_root)
        
        # Generate hints for AI
        generation_hints = _generate_hints(standards, project_context)
        
        return {
            "data": {
                "standards": standards,
                "project_context": project_context,
                "generation_hints": generation_hints,
                "analysis_timestamp": _get_timestamp()
            }
        }
        
    except Exception as e:
        return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to analyze standards: {str(e)}"}}


def _extract_standard_metadata(content: str, filename: str, file_path: str) -> dict[str, Any] | None:
    """Extract metadata from a standard markdown file."""
    try:
        import yaml
        
        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        frontmatter = {}
        
        if frontmatter_match:
            try:
                frontmatter = yaml.safe_load(frontmatter_match.group(1)) or {}
            except yaml.YAMLError:
                frontmatter = {}
                
        # Enhanced content analysis for new template format
        has_critical_rules = bool(re.search(r'## 🚨 CRITICAL RULES', content))
        has_core_requirements = bool(re.search(r'## Core Requirements', content))
        has_patterns = bool(re.search(r'## Pattern Detection', content))
        has_auto_fix = bool(re.search(r'## Auto-Fix Configuration', content))
        has_examples = bool(re.search(r'(✅ CORRECT|❌ INCORRECT|## Examples|## Good Examples|## Bad Examples)', content))
        has_refactoring = bool(re.search(r'### 📝 REFACTORING EXAMPLE', content))
        has_common_mistakes = bool(re.search(r'## Common Mistakes & Anti-Patterns', content))
        has_decision_guide = bool(re.search(r'## Decision Guide', content))
        has_naming_conventions = bool(re.search(r'## Naming Conventions', content))
        has_testing_patterns = bool(re.search(r'## Testing Patterns', content))
        has_security_considerations = bool(re.search(r'## Security Considerations', content))
        has_performance_considerations = bool(re.search(r'## Performance Considerations', content))
        
        # Determine complexity and enforcement type
        complexity_indicators = sum([
            has_critical_rules, has_core_requirements, has_common_mistakes,
            has_decision_guide, has_security_considerations, has_performance_considerations
        ])
        
        # Try legacy enforcement type extraction first for backward compatibility
        legacy_enforcement = _extract_enforcement_type_from_content(content)
        if legacy_enforcement != "unknown":
            enforcement_type = legacy_enforcement
        else:
            # Use new structure-based determination
            enforcement_type = _determine_enforcement_type(
                has_patterns, has_auto_fix, has_critical_rules, has_core_requirements
            )
        
        return {
            "id": frontmatter.get('id', filename.replace('.md', '')),
            "name": frontmatter.get('name', filename.replace('.md', '').replace('-', ' ').title()),
            "category": frontmatter.get('category', 'general'),
            "tags": frontmatter.get('tags', []),
            "applies_to": frontmatter.get('applies_to', ['**/*.js', '**/*.ts']),
            "severity": frontmatter.get('severity', 'error'),
            "priority": frontmatter.get('priority', 'recommended'),
            "dependencies": frontmatter.get('dependencies', []),
            "updated": frontmatter.get('updated', ''),
            "description": frontmatter.get('description', ''),
            
            # Enforcement and automation
            "enforcement_type": enforcement_type,
            "has_patterns": has_patterns,
            "has_auto_fix": has_auto_fix,
            
            # Content richness indicators
            "has_examples": has_examples,
            "has_refactoring": has_refactoring,
            "has_critical_rules": has_critical_rules,
            "has_core_requirements": has_core_requirements,
            "has_common_mistakes": has_common_mistakes,
            "has_decision_guide": has_decision_guide,
            "has_naming_conventions": has_naming_conventions,
            "has_testing_patterns": has_testing_patterns,
            "has_security_considerations": has_security_considerations,
            "has_performance_considerations": has_performance_considerations,
            
            # Metadata
            "complexity_score": complexity_indicators / 6.0,  # Normalized 0-1
            "template_version": "v2" if any([has_critical_rules, has_core_requirements, has_common_mistakes]) else "v1",
            "file_path": file_path,
            "filename": filename
        }
        
    except Exception:
        return None


def _determine_enforcement_type(
    has_patterns: bool,
    has_auto_fix: bool, 
    has_critical_rules: bool,
    has_core_requirements: bool
) -> str:
    """Determine enforcement type based on content structure."""
    
    has_automation = has_patterns or has_auto_fix
    has_human_judgment = has_critical_rules or has_core_requirements
    
    if has_automation and has_human_judgment:
        return "hybrid"
    elif has_automation:
        return "eslint_rule"
    elif has_human_judgment:
        return "ai_context"
    else:
        return "unknown"


def _extract_enforcement_type_from_content(content: str) -> str:
    """Extract enforcement type from checkboxes in content (legacy support)."""
    enforcement_pattern = r'## Enforcement Type\s*\n(.*?)(?=\n## |\n# |\Z)'
    enforcement_match = re.search(enforcement_pattern, content, re.DOTALL)
    
    if enforcement_match:
        enforcement_content = enforcement_match.group(1)
        
        if '- [x] ESLint Rule' in enforcement_content:
            if '- [x] Hybrid' in enforcement_content:
                return 'hybrid'
            return 'eslint_rule'
        elif '- [x] AI Context' in enforcement_content:
            return 'ai_context'
        elif '- [x] Hybrid' in enforcement_content:
            return 'hybrid'
            
    return 'unknown'


def _analyze_project_context(project_root: str) -> dict[str, Any]:
    """Analyze project structure to provide minimal context."""
    context = {
        "root_path": project_root,
        "framework": "unknown",
        "package_manager": "unknown",
        "typescript": False,
        "common_patterns": [],
        "directory_structure": {}
    }
    
    try:
        # Detect framework and package manager
        package_json_path = os.path.join(project_root, "package.json")
        if os.path.exists(package_json_path):
            with open(package_json_path, 'r', encoding='utf-8') as f:
                package_data = json.load(f)
                
            # Detect framework
            dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
            
            if 'next' in dependencies:
                context["framework"] = "nextjs"
            elif 'react' in dependencies:
                context["framework"] = "react"
            elif 'express' in dependencies:
                context["framework"] = "express"
            elif 'vue' in dependencies:
                context["framework"] = "vue"
            elif 'angular' in dependencies:
                context["framework"] = "angular"
                
            # Detect TypeScript
            context["typescript"] = 'typescript' in dependencies or '@types/node' in dependencies
            
        # Detect package manager
        if os.path.exists(os.path.join(project_root, "pnpm-lock.yaml")):
            context["package_manager"] = "pnpm"
        elif os.path.exists(os.path.join(project_root, "yarn.lock")):
            context["package_manager"] = "yarn"
        elif os.path.exists(os.path.join(project_root, "package-lock.json")):
            context["package_manager"] = "npm"
        elif os.path.exists(package_json_path):  # Default to npm if package.json exists
            context["package_manager"] = "npm"
            
        # Analyze directory structure (top level only)
        common_dirs = ["src", "lib", "components", "pages", "app", "api", "utils", "hooks", "types"]
        for dirname in common_dirs:
            dir_path = os.path.join(project_root, dirname)
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                context["directory_structure"][dirname] = _get_directory_summary(dir_path)
                
        # Detect common patterns
        if context["framework"] == "nextjs":
            context["common_patterns"] = ["app-router", "pages-router", "api-routes", "components"]
        elif context["framework"] == "react":
            context["common_patterns"] = ["components", "hooks", "context"]
        elif context["framework"] == "express":
            context["common_patterns"] = ["middleware", "routes", "controllers"]
            
    except Exception:
        pass
        
    return context


def _get_directory_summary(dir_path: str) -> dict[str, Any]:
    """Get summary of directory contents."""
    summary = {
        "exists": True,
        "file_count": 0,
        "has_index": False,
        "common_extensions": set()
    }
    
    try:
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path):
                summary["file_count"] += 1
                
                if item in ["index.js", "index.ts", "index.tsx", "index.jsx"]:
                    summary["has_index"] = True
                    
                ext = os.path.splitext(item)[1]
                if ext:
                    summary["common_extensions"].add(ext)
                    
        # Convert set to list for JSON serialization
        summary["common_extensions"] = list(summary["common_extensions"])
        
    except Exception:
        summary["exists"] = False
        
    return summary


def _generate_hints(standards: list[dict[str, Any]], project_context: dict[str, Any]) -> dict[str, Any]:
    """Generate hints for AI rule generation."""
    eslint_capable = []
    ai_context_only = []
    hybrid_standards = []
    high_complexity = []
    template_v2_standards = []
    
    for standard in standards:
        enforcement_type = standard.get("enforcement_type", "unknown")
        complexity = standard.get("complexity_score", 0.0)
        template_version = standard.get("template_version", "v1")
        
        # Track V2 template standards
        if template_version == "v2":
            template_v2_standards.append(standard["id"])
            
        # Track high complexity standards
        if complexity > 0.5:
            high_complexity.append(standard["id"])
        
        # Categorize by enforcement type
        if enforcement_type == "eslint_rule":
            # V1 templates might have explicit ESLint designation without patterns
            if standard.get("has_patterns") or standard.get("has_auto_fix") or template_version == "v1":
                eslint_capable.append(standard["id"])
            else:
                ai_context_only.append(standard["id"])
        elif enforcement_type == "ai_context":
            ai_context_only.append(standard["id"])
        elif enforcement_type == "hybrid":
            hybrid_standards.append(standard["id"])
        elif standard.get("has_patterns") and standard.get("has_examples"):
            # Infer ESLint capability from structure
            eslint_capable.append(standard["id"])
        elif standard.get("has_critical_rules") or standard.get("has_core_requirements"):
            # Standards with critical rules likely need AI context
            ai_context_only.append(standard["id"])
        else:
            ai_context_only.append(standard["id"])
            
    return {
        "eslint_capable": eslint_capable,
        "ai_context_only": ai_context_only,
        "hybrid_standards": hybrid_standards,
        "high_complexity_standards": high_complexity,
        "template_v2_standards": template_v2_standards,
        "framework_specific_hints": _get_framework_hints(project_context["framework"]),
        "typescript_enabled": project_context["typescript"],
        "generation_strategy": {
            "prefer_hybrid_for_complex": True,
            "auto_fix_threshold": 0.3,
            "ai_context_threshold": 0.6
        }
    }


def _get_framework_hints(framework: str) -> dict[str, Any]:
    """Get framework-specific generation hints."""
    hints = {
        "nextjs": {
            "router_patterns": ["app/", "pages/"],
            "api_patterns": ["api/", "route.ts"],
            "component_patterns": ["components/", ".tsx", ".jsx"]
        },
        "react": {
            "component_patterns": ["components/", ".tsx", ".jsx"],
            "hook_patterns": ["hooks/", "use*.ts", "use*.js"]
        },
        "express": {
            "route_patterns": ["routes/", "*.route.js", "*.route.ts"],
            "middleware_patterns": ["middleware/", "*.middleware.js"]
        }
    }
    
    return hints.get(framework, {})


def _get_timestamp() -> str:
    """Get current timestamp in ISO format."""
    from datetime import datetime
    return datetime.now().isoformat()


def register_analyze_standards_for_rules(mcp: FastMCP):
    """Register the analyze_standards_for_rules tool with FastMCP."""
    
    @mcp.tool
    @json_convert
    def analyze_standards_for_rules(
        standards_dir: str = ".aromcp/standards",
        project_root: str | None = None
    ) -> dict[str, Any]:
        """Analyze standards and return a generation recipe.
        
        Performs single-pass analysis of standards and project,
        returning a simple recipe for AI to generate rules.
        
        Args:
            standards_dir: Directory containing markdown standards files
            project_root: Project root directory (auto-resolved if None)
            
        Returns:
            Dict with standards, minimal project context, and generation hints
        """
        return analyze_standards_for_rules_impl(standards_dir, project_root)