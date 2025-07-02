"""
Extract template data from standardized coding standards files.

This tool parses standardized markdown templates and extracts structured data
that AI can use to generate ESLint rules.
"""

import os
import re
import json
import yaml
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from ...utils.json_parameter_middleware import json_convert
from ...filesystem_server._security import get_project_root, validate_file_path


def extract_templates_from_standards_impl(
    standards_dir: str = ".aromcp/standards",
    output_dir: str = ".aromcp/templates",
    project_root: str | None = None
) -> dict[str, Any]:
    """Extract template data from standardized coding standards files.
    
    Args:
        standards_dir: Directory containing markdown standards files
        output_dir: Directory to write extracted template data
        project_root: Project root directory (auto-resolved if None)
        
    Returns:
        Dict with extracted template data paths and metadata
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
            
        # Create output directory
        output_path = os.path.join(project_root, output_dir)
        data_path = os.path.join(output_path, "data")
        os.makedirs(data_path, exist_ok=True)
        
        extracted_templates = []
        total_files = 0
        
        # Process each markdown file in standards directory
        for filename in os.listdir(standards_path):
            if not filename.endswith('.md'):
                continue
                
            total_files += 1
            file_path = os.path.join(standards_path, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                template_data = _extract_template_data_from_content(content, filename)
                
                if template_data:
                    # Write extracted data to JSON file
                    standard_id = template_data.get('id', filename.replace('.md', ''))
                    output_filename = f"{standard_id}_template_data.json"
                    output_file_path = os.path.join(data_path, output_filename)
                    
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        json.dump(template_data, f, indent=2, default=str)
                        
                    extracted_templates.append({
                        "standard_id": standard_id,
                        "source_file": filename,
                        "template_data_path": os.path.join(output_dir, "data", output_filename),
                        "has_good_examples": bool(template_data.get('correct_examples')),  # Updated for V2
                        "has_bad_examples": bool(template_data.get('incorrect_examples')),  # Updated for V2
                        "has_pattern_detection": bool(template_data.get('pattern_detection')),
                        "enforcement_type": template_data.get('enforcement_type', 'unknown')
                    })
                    
            except Exception as e:
                # Continue processing other files on individual file errors
                continue
                
        return {
            "data": {
                "templates_extracted": len(extracted_templates),
                "total_files_processed": total_files,
                "output_directory": output_dir,
                "templates": extracted_templates
            }
        }
        
    except Exception as e:
        return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to extract templates: {str(e)}"}}


def _extract_template_data_from_content(content: str, filename: str) -> dict[str, Any] | None:
    """Extract structured template data from markdown content."""
    try:
        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        frontmatter = {}
        
        if frontmatter_match:
            try:
                frontmatter = yaml.safe_load(frontmatter_match.group(1)) or {}
            except yaml.YAMLError:
                frontmatter = {}
                
        # Extract code examples (both V1 and V2 patterns)
        correct_examples = _extract_code_examples(content, "✅ CORRECT")
        if not correct_examples:
            correct_examples = _extract_code_examples(content, "Good Examples")
            
        incorrect_examples = _extract_code_examples(content, "❌ INCORRECT")
        if not incorrect_examples:
            incorrect_examples = _extract_code_examples(content, "Bad Examples")
        complete_examples = _extract_code_examples(content, "Complete Example")
        refactoring_examples = _extract_refactoring_examples(content)
        
        # Extract pattern detection section
        pattern_detection = _extract_yaml_section(content, "Pattern Detection")
        
        # Extract auto-fix configuration (try both V1 and V2 patterns)
        auto_fix = _extract_yaml_section(content, "Auto-Fix Configuration")
        if not auto_fix:
            auto_fix = _extract_yaml_section(content, "Auto-Fix")
        
        # Extract critical rules
        critical_rules = _extract_critical_rules(content)
        
        # Extract core requirements
        core_requirements = _extract_core_requirements(content)
        
        # Extract naming conventions
        naming_conventions = _extract_naming_conventions(content)
        
        # Extract common mistakes
        common_mistakes = _extract_common_mistakes(content)
        
        # Extract decision guide
        decision_guide = _extract_decision_guide(content)
        
        # Extract security and performance considerations
        security_considerations = _extract_section_content(content, "Security Considerations")
        performance_considerations = _extract_section_content(content, "Performance Considerations")
        
        # Extract migration guide
        migration_guide = _extract_section_content(content, "Migration Guide")
        
        # Extract testing patterns
        testing_patterns = _extract_code_examples(content, "Testing Patterns")
        
        # Determine enforcement type - try explicit first, then structure-based
        enforcement_type = _extract_enforcement_type(content)
        if enforcement_type == 'unknown':
            enforcement_type = _determine_enforcement_type_from_structure(
                pattern_detection, auto_fix, critical_rules, core_requirements
            )
        
        template_data = {
            "id": frontmatter.get('id', filename.replace('.md', '')),
            "name": frontmatter.get('name', ''),
            "category": frontmatter.get('category', 'general'),
            "tags": frontmatter.get('tags', []),
            "applies_to": frontmatter.get('applies_to', []),
            "severity": frontmatter.get('severity', 'error'),
            "priority": frontmatter.get('priority', 'recommended'),
            "dependencies": frontmatter.get('dependencies', []),
            "updated": frontmatter.get('updated', ''),
            "description": frontmatter.get('description', '') or _extract_section_content(content, "Overview"),
            
            # Examples (enhanced structure)
            "correct_examples": correct_examples,
            "incorrect_examples": incorrect_examples,
            "complete_examples": complete_examples,
            "refactoring_examples": refactoring_examples,
            "testing_patterns": testing_patterns,
            
            # Structural elements
            "critical_rules": critical_rules,
            "core_requirements": core_requirements,
            "naming_conventions": naming_conventions,
            "common_mistakes": common_mistakes,
            "decision_guide": decision_guide,
            
            # Configuration and automation
            "pattern_detection": pattern_detection,
            "auto_fix": auto_fix,
            "enforcement_type": enforcement_type,
            
            # Additional guidance
            "security_considerations": security_considerations,
            "performance_considerations": performance_considerations,
            "migration_guide": migration_guide,
            
            # Metadata
            "source_file": filename,
            "template_version": "v2",
            "has_critical_rules": bool(critical_rules),
            "has_examples": bool(correct_examples or incorrect_examples),
            "has_automation": bool(pattern_detection or auto_fix),
            "complexity_score": _calculate_complexity_score(content)
        }
        
        return template_data
        
    except Exception:
        return None


def _extract_code_examples(content: str, section_name: str) -> list[dict[str, str]]:
    """Extract code examples from a specific section."""
    examples = []
    
    # First try to find as a top-level section (V1 format)
    section_pattern = rf'## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if not section_match:
        # Try to find as subsections under "Examples" section (V2 format)
        if section_name in ["✅ CORRECT", "❌ INCORRECT"]:
            # Look for subsections under ## Examples
            examples_pattern = r'## Examples\s*\n(.*?)(?=\n## |\n# |\Z)'
            examples_match = re.search(examples_pattern, content, re.DOTALL)
            
            if examples_match:
                examples_content = examples_match.group(1)
                
                # Find the specific subsection (### ✅ CORRECT: or ### ❌ INCORRECT:)
                subsection_pattern = rf'### {re.escape(section_name)}[:\s]+(.*?)(?=\n### |\n## |\n# |\Z)'
                subsection_match = re.search(subsection_pattern, examples_content, re.DOTALL)
                
                if subsection_match:
                    section_content = subsection_match.group(1)
                else:
                    return examples
            else:
                return examples
        else:
            return examples
    else:
        section_content = section_match.group(1)
    
    # Extract code blocks with language hints
    code_pattern = r'```(\w+)?\n(.*?)\n```'
    code_matches = re.findall(code_pattern, section_content, re.DOTALL)
    
    for lang, code in code_matches:
        # Extract comments for context
        comment_lines = [line.strip() for line in code.split('\n') if line.strip().startswith('//')]
        context = '\n'.join(comment_lines)
        
        examples.append({
            "language": lang or "javascript",
            "code": code.strip(),
            "context": context
        })
        
    return examples


def _extract_yaml_section(content: str, section_name: str) -> dict[str, Any]:
    """Extract YAML content from a specific section."""
    section_pattern = rf'## {re.escape(section_name)}\s*\n```yaml\n(.*?)\n```'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        try:
            return yaml.safe_load(section_match.group(1)) or {}
        except yaml.YAMLError:
            pass
            
    return {}


def _extract_enforcement_type(content: str) -> str:
    """Extract enforcement type from checkboxes."""
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


def _extract_section_content(content: str, section_name: str) -> str:
    """Extract plain text content from a specific section."""
    section_pattern = rf'## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        return section_match.group(1).strip()
        
    return ""


def _extract_refactoring_examples(content: str) -> list[dict[str, str]]:
    """Extract before/after refactoring examples."""
    examples = []
    
    # Find refactoring example section
    section_pattern = r'### 📝 REFACTORING EXAMPLE\s*\n(.*?)(?=\n### |\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        section_content = section_match.group(1)
        
        # Extract before and after code blocks
        before_pattern = r'\*\*Before:\*\*\s*\n```(\w+)?\n(.*?)\n```'
        after_pattern = r'\*\*After:\*\*\s*\n```(\w+)?\n(.*?)\n```'
        
        before_match = re.search(before_pattern, section_content, re.DOTALL)
        after_match = re.search(after_pattern, section_content, re.DOTALL)
        
        if before_match and after_match:
            examples.append({
                "type": "refactoring",
                "before": {
                    "language": before_match.group(1) or "typescript",
                    "code": before_match.group(2).strip()
                },
                "after": {
                    "language": after_match.group(1) or "typescript", 
                    "code": after_match.group(2).strip()
                }
            })
            
    return examples


def _extract_critical_rules(content: str) -> list[str]:
    """Extract critical rules from the CRITICAL RULES section."""
    rules = []
    
    section_pattern = r'## 🚨 CRITICAL RULES\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        section_content = section_match.group(1)
        
        # Extract numbered list items with flexible pattern
        rule_pattern = r'^\d+\.\s+\*\*(.*?)\*\*\s*(.*)$'
        for line in section_content.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            match = re.match(rule_pattern, line)
            if match:
                rule_type = match.group(1).strip()
                description = match.group(2).strip()
                # Remove leading dash if present
                if description.startswith('- '):
                    description = description[2:]
                elif description.startswith('-'):
                    description = description[1:].strip()
                    
                rules.append({
                    "type": rule_type,
                    "description": description
                })
                
    return rules


def _extract_core_requirements(content: str) -> list[str]:
    """Extract core requirements from the Core Requirements section."""
    requirements = []
    
    section_pattern = r'## Core Requirements\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        section_content = section_match.group(1)
        
        # Extract bullet points
        req_pattern = r'^\s*-\s+\*\*(.*?)\*\*:\s*(.*?)$'
        for line in section_content.split('\n'):
            match = re.match(req_pattern, line.strip())
            if match:
                requirements.append({
                    "requirement": match.group(1).strip(),
                    "description": match.group(2).strip()
                })
                
    return requirements


def _extract_naming_conventions(content: str) -> dict[str, Any]:
    """Extract naming conventions table."""
    conventions = {}
    
    section_pattern = r'## Naming Conventions\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        section_content = section_match.group(1)
        
        # Extract table rows
        table_pattern = r'\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|'
        lines = section_content.split('\n')
        
        for line in lines:
            match = re.match(table_pattern, line.strip())
            if match and not match.group(1).startswith('Item'):  # Skip header
                item = match.group(1).strip()
                pattern = match.group(2).strip()
                example = match.group(3).strip()
                
                if item and pattern and example:
                    conventions[item.lower()] = {
                        "pattern": pattern,
                        "example": example
                    }
                    
    return conventions


def _extract_common_mistakes(content: str) -> list[dict[str, Any]]:
    """Extract common mistakes and anti-patterns."""
    mistakes = []
    
    section_pattern = r'## Common Mistakes & Anti-Patterns\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        section_content = section_match.group(1)
        
        # Extract subsections for each mistake
        mistake_pattern = r'### \d+\.\s+(.*?)\n\*\*Why it\'s problematic:\*\*\s+(.*?)(?=\n### |\Z)'
        for match in re.finditer(mistake_pattern, section_content, re.DOTALL):
            mistake_name = match.group(1).strip()
            explanation = match.group(2).strip()
            
            # Extract don't/do examples
            mistake_section = match.group(0)
            dont_pattern = r'❌ \*\*Don\'t do this:\*\*\s*\n```(\w+)?\n(.*?)\n```'
            do_pattern = r'✅ \*\*Do this instead:\*\*\s*\n```(\w+)?\n(.*?)\n```'
            
            dont_match = re.search(dont_pattern, mistake_section, re.DOTALL)
            do_match = re.search(do_pattern, mistake_section, re.DOTALL)
            
            mistake_entry = {
                "name": mistake_name,
                "explanation": explanation
            }
            
            if dont_match:
                mistake_entry["bad_example"] = {
                    "language": dont_match.group(1) or "typescript",
                    "code": dont_match.group(2).strip()
                }
                
            if do_match:
                mistake_entry["good_example"] = {
                    "language": do_match.group(1) or "typescript",
                    "code": do_match.group(2).strip()
                }
                
            mistakes.append(mistake_entry)
            
    return mistakes


def _extract_decision_guide(content: str) -> list[dict[str, str]]:
    """Extract decision guide table."""
    guide = []
    
    section_pattern = r'## Decision Guide\s*\n(.*?)(?=\n## |\n# |\Z)'
    section_match = re.search(section_pattern, content, re.DOTALL)
    
    if section_match:
        section_content = section_match.group(1)
        
        # Extract table rows
        table_pattern = r'\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|'
        lines = section_content.split('\n')
        
        for line in lines:
            match = re.match(table_pattern, line.strip())
            if match and not match.group(1).startswith('Scenario'):  # Skip header
                scenario = match.group(1).strip()
                approach = match.group(2).strip()
                reason = match.group(3).strip()
                
                if scenario and approach and reason:
                    guide.append({
                        "scenario": scenario,
                        "approach": approach,
                        "reason": reason
                    })
                    
    return guide


def _determine_enforcement_type_from_structure(
    pattern_detection: dict[str, Any],
    auto_fix: dict[str, Any], 
    critical_rules: list[str],
    core_requirements: list[str]
) -> str:
    """Determine enforcement type based on content structure."""
    
    has_automation = bool(pattern_detection or auto_fix)
    has_critical_rules = bool(critical_rules)
    has_requirements = bool(core_requirements)
    
    if has_automation and (has_critical_rules or has_requirements):
        return "hybrid"
    elif has_automation:
        return "eslint_rule"
    elif has_critical_rules or has_requirements:
        return "ai_context"
    else:
        return "unknown"


def _calculate_complexity_score(content: str) -> float:
    """Calculate complexity score based on content analysis."""
    score = 0.0
    
    # Base scoring factors
    if '🚨 CRITICAL RULES' in content:
        score += 0.3
    if 'Core Requirements' in content:
        score += 0.2
    if 'Common Mistakes' in content:
        score += 0.2
    if 'Decision Guide' in content:
        score += 0.1
    if 'Security Considerations' in content:
        score += 0.1
    if 'Performance Considerations' in content:
        score += 0.1
    
    # Count code examples
    example_count = len(re.findall(r'```\w*\n', content))
    score += min(example_count * 0.05, 0.3)
    
    # Normalize to 0-1 range
    return min(score, 1.0)


def register_extract_templates_from_standards(mcp: FastMCP):
    """Register the extract_templates_from_standards tool with FastMCP."""
    
    @mcp.tool
    @json_convert
    def extract_templates_from_standards(
        standards_dir: str = ".aromcp/standards",
        output_dir: str = ".aromcp/templates", 
        project_root: str | None = None
    ) -> dict[str, Any]:
        """Extract template data from standardized coding standards files.
        
        This tool parses standardized markdown templates and extracts
        structured data that AI can use to generate ESLint rules.
        
        Args:
            standards_dir: Directory containing markdown standards files
            output_dir: Directory to write extracted template data
            project_root: Project root directory (auto-resolved if None)
            
        Returns:
            Dict with extracted template data paths and metadata
        """
        return extract_templates_from_standards_impl(standards_dir, output_dir, project_root)