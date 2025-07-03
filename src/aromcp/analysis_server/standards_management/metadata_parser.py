"""YAML frontmatter parser for coding standards metadata."""

import re
import yaml
from typing import Any, Dict, Tuple, Optional
from pathlib import Path


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.
    
    Args:
        content: Full markdown content with potential frontmatter
        
    Returns:
        Tuple of (metadata_dict, content_without_frontmatter)
    """
    # Pattern to match YAML frontmatter
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n'
    
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if not match:
        return {}, content
    
    yaml_content = match.group(1)
    remaining_content = content[match.end():]
    
    try:
        metadata = yaml.safe_load(yaml_content) or {}
        return metadata, remaining_content
    except yaml.YAMLError as e:
        # Return error information in metadata
        return {
            "_parse_error": f"Invalid YAML frontmatter: {str(e)}"
        }, content


def validate_standard_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize standard metadata.
    
    Args:
        metadata: Parsed metadata dictionary
        
    Returns:
        Dictionary with validation result and normalized metadata
    """
    errors = []
    warnings = []
    
    # Check for parse errors
    if "_parse_error" in metadata:
        return {
            "valid": False,
            "errors": [metadata["_parse_error"]],
            "warnings": [],
            "metadata": {}
        }
    
    # Required fields (updated for new template)
    required_fields = ["id", "name", "category"]
    for field in required_fields:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")
    
    # Validate field types and values
    if "id" in metadata:
        if not isinstance(metadata["id"], str):
            errors.append("Field 'id' must be a string")
        elif not re.match(r'^[a-z0-9-_]+$', metadata["id"]):
            errors.append("Field 'id' must contain only lowercase letters, numbers, hyphens, and underscores")
    
    if "name" in metadata:
        if not isinstance(metadata["name"], str):
            errors.append("Field 'name' must be a string")
    
    if "version" in metadata:
        if not isinstance(metadata["version"], str):
            warnings.append("Field 'version' should be a string")
    
    # Validate applies_to patterns (required field)
    if "applies_to" not in metadata:
        errors.append("Missing required field: applies_to")
    elif not isinstance(metadata["applies_to"], list):
        errors.append("Field 'applies_to' must be a list")
    else:
        for i, pattern in enumerate(metadata["applies_to"]):
            if not isinstance(pattern, str):
                errors.append(f"Pattern {i} in 'applies_to' must be a string")
    
    # Validate tags
    if "tags" in metadata:
        if not isinstance(metadata["tags"], list):
            errors.append("Field 'tags' must be a list")
        else:
            for i, tag in enumerate(metadata["tags"]):
                if not isinstance(tag, str):
                    errors.append(f"Tag {i} must be a string")
    
    # Validate category
    if "category" in metadata:
        valid_categories = ["api", "database", "frontend", "architecture", "security", "pipeline", "general"]
        if metadata["category"] not in valid_categories:
            warnings.append(f"Field 'category' should be one of: {', '.join(valid_categories)}")
    
    # Validate severity
    if "severity" in metadata:
        valid_severities = ["error", "warning", "info"]
        if metadata["severity"] not in valid_severities:
            errors.append(f"Field 'severity' must be one of: {', '.join(valid_severities)}")
    
    # Validate enabled
    if "enabled" in metadata:
        if not isinstance(metadata["enabled"], bool):
            warnings.append("Field 'enabled' should be a boolean")
    
    # Validate priority (required field with specific values)
    if "priority" not in metadata:
        errors.append("Missing required field: priority")
    else:
        valid_priorities = ["required", "important", "recommended"]
        if metadata["priority"] not in valid_priorities:
            errors.append(f"Field 'priority' must be one of: {', '.join(valid_priorities)}")
    
    # Validate dependencies
    if "dependencies" in metadata:
        if not isinstance(metadata["dependencies"], list):
            errors.append("Field 'dependencies' must be a list")
        else:
            for i, dep in enumerate(metadata["dependencies"]):
                if not isinstance(dep, str):
                    errors.append(f"Dependency {i} must be a string")
    
    # Set defaults for missing optional fields
    normalized_metadata = metadata.copy()
    if "enabled" not in normalized_metadata:
        normalized_metadata["enabled"] = True
    if "tags" not in normalized_metadata:
        normalized_metadata["tags"] = []
    # Note: severity, priority, applies_to, category are now required fields with no defaults
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "metadata": normalized_metadata
    }


def extract_rule_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract rule-specific metadata for ESLint rule generation.
    
    Args:
        metadata: Validated standard metadata
        
    Returns:
        Dictionary with rule generation hints and configuration
    """
    rule_metadata = {}
    
    # Extract rules section if present
    if "rules" in metadata and isinstance(metadata["rules"], dict):
        rule_metadata.update(metadata["rules"])
    
    # Map standard fields to rule metadata
    if "severity" in metadata:
        rule_metadata["default_severity"] = metadata["severity"]
    
    if "id" in metadata:
        rule_metadata["rule_prefix"] = metadata["id"]
    
    # Set defaults for rule generation
    if "naming_convention" not in rule_metadata:
        rule_metadata["naming_convention"] = "camelCase"
    
    if "auto_fix" not in rule_metadata:
        rule_metadata["auto_fix"] = False
    
    if "suggestion" not in rule_metadata:
        rule_metadata["suggestion"] = True
    
    return rule_metadata


def parse_standard_file(file_path: Path) -> Dict[str, Any]:
    """Parse a complete standard file with metadata and content.
    
    Args:
        file_path: Path to the standard markdown file
        
    Returns:
        Dictionary with parsed standard information
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            "error": {
                "code": "READ_ERROR",
                "message": f"Failed to read file {file_path}: {str(e)}"
            }
        }
    
    # Parse frontmatter
    metadata, content_body = parse_frontmatter(content)
    
    # Validate metadata
    validation = validate_standard_metadata(metadata)
    
    if not validation["valid"]:
        return {
            "error": {
                "code": "INVALID_METADATA",
                "message": f"Invalid metadata in {file_path}: {'; '.join(validation['errors'])}"
            }
        }
    
    # Extract rule metadata
    rule_metadata = extract_rule_metadata(validation["metadata"])
    
    return {
        "data": {
            "file_path": str(file_path),
            "metadata": validation["metadata"],
            "rule_metadata": rule_metadata,
            "content": content_body,
            "warnings": validation["warnings"]
        }
    }


def parse_content_structure(content: str) -> Dict[str, Any]:
    """Parse the structured content of a new template standard.
    
    Args:
        content: Markdown content without frontmatter
        
    Returns:
        Dictionary with parsed content sections
    """
    sections = {
        "title": "",
        "why_and_when": "",
        "core_rules": [],
        "pattern": {
            "structure": "",
            "implementation": ""
        },
        "examples": {
            "correct": [],
            "wrong": []
        },
        "common_mistakes": [],
        "automation": "",
        "related": []
    }
    
    # Extract title (first heading)
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    if title_match:
        sections["title"] = title_match.group(1).strip()
    
    # Extract Why & When section
    why_when_match = re.search(r'## Why & When\s*\n<!--.*?-->\s*\n(.+?)(?=\n## |$)', content, re.DOTALL)
    if why_when_match:
        sections["why_and_when"] = why_when_match.group(1).strip()
    
    # Extract Core Rules
    rules_match = re.search(r'## Core Rules\s*\n<!--.*?-->\s*\n(.+?)(?=\n## |$)', content, re.DOTALL)
    if rules_match:
        rules_text = rules_match.group(1)
        # Extract numbered rules
        rule_matches = re.findall(r'^(\d+)\. \*\*(.+?)\*\* (.+?) - (.+?)$', rules_text, re.MULTILINE)
        for rule_match in rule_matches:
            sections["core_rules"].append({
                "number": int(rule_match[0]),
                "type": rule_match[1],  # NEVER, ALWAYS, USE
                "rule": rule_match[2],
                "reason": rule_match[3]
            })
    
    # Extract Pattern sections
    structure_match = re.search(r'### Structure\s*\n```[^\n]*\n(.+?)\n```', content, re.DOTALL)
    if structure_match:
        sections["pattern"]["structure"] = structure_match.group(1).strip()
    
    implementation_match = re.search(r'### Implementation\s*\n```[^\n]*\n(.+?)\n```', content, re.DOTALL)
    if implementation_match:
        sections["pattern"]["implementation"] = implementation_match.group(1).strip()
    
    # Extract Examples
    correct_matches = re.finditer(r'### ✅ Correct\s*\n```[^\n]*\n(.+?)\n```', content, re.DOTALL)
    for match in correct_matches:
        sections["examples"]["correct"].append(match.group(1).strip())
    
    wrong_matches = re.finditer(r'### ❌ Wrong\s*\n```[^\n]*\n(.+?)\n```', content, re.DOTALL)
    for match in wrong_matches:
        sections["examples"]["wrong"].append(match.group(1).strip())
    
    # Extract Common Mistakes
    mistakes_match = re.search(r'## Common Mistakes\s*\n(.+?)(?=\n## |$)', content, re.DOTALL)
    if mistakes_match:
        mistakes_text = mistakes_match.group(1)
        mistake_matches = re.findall(r'^\d+\. \*\*(.+?)\*\*: (.+?) → (.+?)$', mistakes_text, re.MULTILINE)
        for mistake_match in mistake_matches:
            sections["common_mistakes"].append({
                "mistake": mistake_match[0],
                "reason": mistake_match[1],
                "solution": mistake_match[2]
            })
    
    # Extract Automation section
    automation_match = re.search(r'## Automation\s*\n<!--.*?-->\s*\n```yaml\s*\n(.+?)\n```', content, re.DOTALL)
    if automation_match:
        sections["automation"] = automation_match.group(1).strip()
    
    # Extract Related dependencies
    related_match = re.search(r'## Related\s*\n```yaml\s*\n(.+?)\n```', content, re.DOTALL)
    if related_match:
        related_text = related_match.group(1)
        # Parse YAML-like dependencies
        dep_matches = re.findall(r'- id: (.+?)\s*\n\s*reason: "(.+?)"', related_text)
        for dep_match in dep_matches:
            sections["related"].append({
                "id": dep_match[0].strip(),
                "reason": dep_match[1].strip()
            })
    
    return sections


def get_standard_summary(metadata: Dict[str, Any]) -> str:
    """Generate a human-readable summary of a standard.
    
    Args:
        metadata: Standard metadata dictionary
        
    Returns:
        Formatted summary string
    """
    summary_parts = []
    
    if "name" in metadata:
        summary_parts.append(f"Name: {metadata['name']}")
    
    # Version is not part of new template
    
    if "category" in metadata:
        summary_parts.append(f"Category: {metadata['category']}")
    
    if "tags" in metadata and metadata["tags"]:
        summary_parts.append(f"Tags: {', '.join(metadata['tags'])}")
    
    if "applies_to" in metadata and metadata["applies_to"]:
        summary_parts.append(f"Applies to: {', '.join(metadata['applies_to'])}")
    
    if "priority" in metadata:
        summary_parts.append(f"Priority: {metadata['priority']}")
    
    if "severity" in metadata:
        summary_parts.append(f"Severity: {metadata['severity']}")
    
    return " | ".join(summary_parts)