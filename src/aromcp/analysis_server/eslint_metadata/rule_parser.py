"""Parser for ESLint rule metadata from generated rule files."""

import json
import re
from pathlib import Path
from typing import Any


def parse_eslint_rule_file(file_path: str) -> dict[str, Any]:
    """Parse an ESLint rule file to extract metadata and patterns.
    
    Args:
        file_path: Path to the ESLint rule file (.js)
        
    Returns:
        Dictionary containing rule metadata and content
    """
    try:
        rule_path = Path(file_path)
        if not rule_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"ESLint rule file not found: {file_path}"
                }
            }

        content = rule_path.read_text(encoding='utf-8')
        metadata = extract_metadata_from_comments(content)

        # Extract rule name from the file
        rule_name = rule_path.stem
        eslint_rule_name = f"@aromcp/{rule_name}"

        return {
            "rule_id": metadata.get("rule_id", rule_name),
            "rule_file": str(rule_path),
            "name": metadata.get("description", f"Rule: {rule_name}"),
            "patterns": metadata.get("patterns", []),
            "severity": metadata.get("severity", "warn"),
            "tags": metadata.get("tags", []),
            "eslint_rule_name": eslint_rule_name,
            "content": content,
            "metadata": metadata
        }

    except Exception as e:
        return {
            "error": {
                "code": "PARSE_ERROR",
                "message": f"Failed to parse ESLint rule file: {str(e)}"
            }
        }


def extract_patterns_from_rule(rule_content: str) -> list[str]:
    """Extract file patterns from ESLint rule content.
    
    Args:
        rule_content: Content of the ESLint rule file
        
    Returns:
        List of file patterns this rule applies to
    """
    metadata = extract_metadata_from_comments(rule_content)
    return metadata.get("patterns", [])


def extract_metadata_from_comments(rule_content: str) -> dict[str, Any]:
    """Extract AroMCP metadata from ESLint rule comments.
    
    Expected format:
    /*
     * @aromcp-rule-id: api-async-handlers
     * @aromcp-patterns: ["**/routes/**/*.ts", "**/api/**/*.ts"]
     * @aromcp-severity: error
     * @aromcp-tags: [api, routes, async]
     * @aromcp-description: Require async handlers for API routes
     */
    
    Args:
        rule_content: Content of the ESLint rule file
        
    Returns:
        Dictionary with extracted metadata
    """
    metadata = {}

    # Find the metadata comment block - handle both /** and /* styles
    # Updated patterns to match line comments instead of block comments
    comment_patterns = [
        r'//\n((?://.*\n)*)',     # Multiple line comments starting with //
        r'//(.*)',                 # Single line comment
    ]

    matches = []
    for pattern in comment_patterns:
        matches = re.findall(pattern, rule_content, re.DOTALL)
        if matches:
            break

    for comment_block in matches:
        # Extract @aromcp- prefixed metadata with proper multiline handling
        # Split by lines and rebuild values that might span multiple lines
        lines = comment_block.split('\n')
        current_key = None
        current_value = ""

        for line in lines:
            line = line.strip()
            # Check if this line starts a new @aromcp directive (updated for line comments)
            aromcp_match = re.match(r'//\s*@aromcp-([\w-]+):\s*(.+)', line)

            if aromcp_match:
                # Process previous key-value pair if exists
                if current_key:
                    _process_metadata_value(metadata, current_key, current_value.strip())

                # Start new key-value pair
                current_key = aromcp_match.group(1).replace('-', '_')
                current_value = aromcp_match.group(2)
            elif current_key and line.startswith('//'):
                # Continuation of previous value
                continuation = line[2:].strip()  # Remove the '//' prefix
                if continuation:
                    current_value += " " + continuation

        # Process the last key-value pair
        if current_key:
            _process_metadata_value(metadata, current_key, current_value.strip())

    return metadata


def _process_metadata_value(metadata: dict[str, Any], key: str, value: str) -> None:
    """Process a metadata key-value pair and store it appropriately."""
    if key == "patterns" or key == "tags":
        # Parse JSON arrays
        try:
            if value.startswith('[') and value.endswith(']'):
                parsed_value = json.loads(value)
            else:
                # Handle comma-separated values
                parsed_value = [item.strip().strip('"\'') for item in value.split(',')]
            metadata[key] = parsed_value
        except json.JSONDecodeError:
            # Fallback to simple comma-separated parsing
            metadata[key] = [item.strip().strip('"\'') for item in value.split(',')]
    else:
        # Store as string
        metadata[key] = value.strip('"\'')

    # Function doesn't return anything, it modifies metadata in place


def get_rule_specificity(patterns: list[str]) -> float:
    """Calculate specificity score for ESLint rule patterns.
    
    Uses the same logic as the standards pattern matcher for consistency.
    
    Args:
        patterns: List of glob patterns
        
    Returns:
        Specificity score between 0.0 and 1.0
    """
    if not patterns:
        return 0.1  # Default specificity for rules without patterns

    # Import the existing pattern specificity calculation
    from ..standards_management.pattern_matcher import calculate_pattern_specificity

    # Calculate specificity for each pattern and return the highest
    specificities = [calculate_pattern_specificity(pattern) for pattern in patterns]
    return max(specificities) if specificities else 0.1


def validate_rule_metadata(rule_data: dict[str, Any]) -> dict[str, Any]:
    """Validate that ESLint rule contains required AroMCP metadata.
    
    Args:
        rule_data: Parsed rule data from parse_eslint_rule_file
        
    Returns:
        Validation result with errors if any
    """
    errors = []
    warnings = []

    # Check for required metadata
    required_fields = ["rule_id", "patterns"]
    for field in required_fields:
        if field not in rule_data.get("metadata", {}):
            errors.append(f"Missing required @aromcp-{field} metadata")

    # Check patterns format
    patterns = rule_data.get("patterns", [])
    if not isinstance(patterns, list):
        errors.append("@aromcp-patterns must be a JSON array")
    elif len(patterns) == 0:
        warnings.append("Rule has no file patterns - will only match if explicitly called")

    # Check severity
    severity = rule_data.get("severity", "warn")
    valid_severities = ["error", "warn", "info", "off"]
    if severity not in valid_severities:
        warnings.append(f"Invalid severity '{severity}', expected one of: {valid_severities}")

    # Check tags format
    tags = rule_data.get("tags", [])
    if tags and not isinstance(tags, list):
        warnings.append("@aromcp-tags should be a JSON array")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


def create_sample_eslint_rule(
    rule_id: str,
    patterns: list[str],
    description: str,
    severity: str = "warn",
    tags: list[str] = None
) -> str:
    """Create a sample ESLint rule file content with AroMCP metadata.
    
    This is primarily for testing and documentation purposes.
    
    Args:
        rule_id: Unique identifier for the rule
        patterns: File patterns the rule applies to
        description: Human-readable description
        severity: Rule severity level
        tags: Optional tags for categorization
        
    Returns:
        ESLint rule file content as string
    """
    if tags is None:
        tags = []

    patterns_json = json.dumps(patterns)
    tags_json = json.dumps(tags)

    return f'''//
// @aromcp-rule-id: {rule_id}
// @aromcp-patterns: {patterns_json}
// @aromcp-severity: {severity}
// @aromcp-tags: {tags_json}
// @aromcp-description: {description}
//

module.exports = {{
    meta: {{
        type: 'problem',
        docs: {{
            description: '{description}',
            category: 'Best Practices',
            recommended: {str(severity == 'error').lower()}
        }},
        fixable: null,
        schema: []
    }},

    create(context) {{
        return {{
            // ESLint rule implementation would go here
            // This is generated by the ESLint rule generation command
        }};
    }}
}};
'''
