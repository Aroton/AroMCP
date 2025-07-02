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
    
    # Required fields
    required_fields = ["id", "name"]
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
    
    # Validate patterns
    if "patterns" in metadata:
        if not isinstance(metadata["patterns"], list):
            errors.append("Field 'patterns' must be a list")
        else:
            for i, pattern in enumerate(metadata["patterns"]):
                if not isinstance(pattern, str):
                    errors.append(f"Pattern {i} must be a string")
    
    # Validate tags
    if "tags" in metadata:
        if not isinstance(metadata["tags"], list):
            errors.append("Field 'tags' must be a list")
        else:
            for i, tag in enumerate(metadata["tags"]):
                if not isinstance(tag, str):
                    errors.append(f"Tag {i} must be a string")
    
    # Validate severity
    if "severity" in metadata:
        valid_severities = ["error", "warn", "info"]
        if metadata["severity"] not in valid_severities:
            errors.append(f"Field 'severity' must be one of: {', '.join(valid_severities)}")
    
    # Validate enabled
    if "enabled" in metadata:
        if not isinstance(metadata["enabled"], bool):
            warnings.append("Field 'enabled' should be a boolean")
    
    # Validate priority
    if "priority" in metadata:
        if not isinstance(metadata["priority"], (int, float)):
            warnings.append("Field 'priority' should be a number")
    
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
    if "priority" not in normalized_metadata:
        normalized_metadata["priority"] = 1
    if "severity" not in normalized_metadata:
        normalized_metadata["severity"] = "error"
    if "patterns" not in normalized_metadata:
        normalized_metadata["patterns"] = []
    if "tags" not in normalized_metadata:
        normalized_metadata["tags"] = []
    if "dependencies" not in normalized_metadata:
        normalized_metadata["dependencies"] = []
    
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
    
    if "version" in metadata:
        summary_parts.append(f"Version: {metadata['version']}")
    
    if "tags" in metadata and metadata["tags"]:
        summary_parts.append(f"Tags: {', '.join(metadata['tags'])}")
    
    if "patterns" in metadata and metadata["patterns"]:
        summary_parts.append(f"Applies to: {', '.join(metadata['patterns'])}")
    
    if "severity" in metadata:
        summary_parts.append(f"Severity: {metadata['severity']}")
    
    return " | ".join(summary_parts)