"""Tests for ESLint rule parser."""

import tempfile
import shutil
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.aromcp.analysis_server.eslint_metadata.rule_parser import (
    parse_eslint_rule_file,
    extract_patterns_from_rule,
    extract_metadata_from_comments,
    get_rule_specificity,
    validate_rule_metadata,
    create_sample_eslint_rule
)


class TestESLintRuleParser:
    """Test class for ESLint rule parser functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_rule_file(self, filename: str, content: str):
        """Helper to create a rule file."""
        rule_path = Path(self.temp_dir) / filename
        rule_path.write_text(content, encoding='utf-8')
        return str(rule_path)

    def test_parse_valid_eslint_rule(self):
        """Test parsing a valid ESLint rule file."""
        rule_content = """/*
 * @aromcp-rule-id: api-async-handlers
 * @aromcp-patterns: ["**/routes/**/*.ts", "**/api/**/*.ts"]
 * @aromcp-severity: error
 * @aromcp-tags: ["api", "routes", "async"]
 * @aromcp-description: Require async handlers for API routes
 */

module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Require async handlers for API routes'
        }
    },
    create(context) {
        return {};
    }
};"""
        
        rule_file = self.create_rule_file("api-async-handlers.js", rule_content)
        result = parse_eslint_rule_file(rule_file)
        
        assert "error" not in result
        assert result["rule_id"] == "api-async-handlers"
        assert result["eslint_rule_name"] == "@aromcp/api-async-handlers"
        assert result["severity"] == "error"
        assert result["patterns"] == ["**/routes/**/*.ts", "**/api/**/*.ts"]
        assert result["tags"] == ["api", "routes", "async"]
        assert result["name"] == "Require async handlers for API routes"

    def test_extract_metadata_from_comments(self):
        """Test metadata extraction from rule comments."""
        rule_content = """/*
 * @aromcp-rule-id: test-rule
 * @aromcp-patterns: ["**/*.ts", "**/*.tsx"]
 * @aromcp-severity: warn
 * @aromcp-tags: ["typescript", "testing"]
 * @aromcp-description: Test rule description
 */"""
        
        metadata = extract_metadata_from_comments(rule_content)
        
        assert metadata["rule_id"] == "test-rule"
        assert metadata["patterns"] == ["**/*.ts", "**/*.tsx"]
        assert metadata["severity"] == "warn"
        assert metadata["tags"] == ["typescript", "testing"]
        assert metadata["description"] == "Test rule description"

    def test_extract_patterns_from_rule(self):
        """Test pattern extraction from rule content."""
        rule_content = """/*
 * @aromcp-patterns: ["**/api/**/*.ts", "**/routes/**/*.js"]
 */
module.exports = {};"""
        
        patterns = extract_patterns_from_rule(rule_content)
        assert patterns == ["**/api/**/*.ts", "**/routes/**/*.js"]

    def test_get_rule_specificity(self):
        """Test rule specificity calculation."""
        test_cases = [
            (["**/*.ts"], 0.3),  # General file extension
            (["**/api/**/*.ts"], 0.7),  # Specific directory + extension
            (["src/components/Button.tsx"], 1.0),  # Exact file
            ([], 0.1)  # No patterns
        ]
        
        for patterns, expected_min in test_cases:
            specificity = get_rule_specificity(patterns)
            assert specificity >= expected_min, f"Patterns {patterns} should have specificity >= {expected_min}"

    def test_validate_rule_metadata_valid(self):
        """Test validation of valid rule metadata."""
        rule_data = {
            "metadata": {
                "rule_id": "test-rule",
                "patterns": ["**/*.ts"],
                "severity": "error",
                "tags": ["typescript"]
            },
            "patterns": ["**/*.ts"],
            "severity": "error",
            "tags": ["typescript"]
        }
        
        validation = validate_rule_metadata(rule_data)
        assert validation["valid"]
        assert len(validation["errors"]) == 0

    def test_validate_rule_metadata_missing_required(self):
        """Test validation with missing required fields."""
        rule_data = {
            "metadata": {
                "severity": "warn"
                # Missing rule_id and patterns
            },
            "severity": "warn"
        }
        
        validation = validate_rule_metadata(rule_data)
        assert not validation["valid"]
        assert len(validation["errors"]) == 2  # Missing rule_id and patterns

    def test_validate_rule_metadata_warnings(self):
        """Test validation that generates warnings."""
        rule_data = {
            "metadata": {
                "rule_id": "test-rule",
                "patterns": [],  # Empty patterns - warning
                "severity": "invalid",  # Invalid severity - warning
                "tags": "not-array"  # Invalid tags format - warning
            },
            "patterns": [],
            "severity": "invalid",
            "tags": "not-array"
        }
        
        validation = validate_rule_metadata(rule_data)
        assert validation["valid"]  # No errors, just warnings
        assert len(validation["warnings"]) >= 2

    def test_create_sample_eslint_rule(self):
        """Test creation of sample ESLint rule."""
        rule_content = create_sample_eslint_rule(
            rule_id="test-sample",
            patterns=["**/*.ts"],
            description="Sample test rule",
            severity="error",
            tags=["test", "sample"]
        )
        
        # Parse the created content to verify it's valid
        metadata = extract_metadata_from_comments(rule_content)
        
        assert metadata["rule_id"] == "test-sample"
        assert metadata["patterns"] == ["**/*.ts"]
        assert metadata["severity"] == "error"
        assert metadata["tags"] == ["test", "sample"]
        assert metadata["description"] == "Sample test rule"
        
        # Should be valid JavaScript module
        assert "module.exports" in rule_content
        assert "meta:" in rule_content
        assert "create(" in rule_content

    def test_parse_nonexistent_file(self):
        """Test parsing a file that doesn't exist."""
        nonexistent_file = str(Path(self.temp_dir) / "nonexistent.js")
        result = parse_eslint_rule_file(nonexistent_file)
        
        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_parse_malformed_rule_file(self):
        """Test parsing a malformed rule file."""
        malformed_content = "This is not a valid JavaScript file!!!"
        rule_file = self.create_rule_file("malformed.js", malformed_content)
        
        # Should still parse (we only extract comments, not validate JS)
        result = parse_eslint_rule_file(rule_file)
        assert "error" not in result  # No parse error for comment extraction
        # But metadata should be empty/default
        assert result["patterns"] == []

    def test_comma_separated_tags_parsing(self):
        """Test parsing comma-separated tags (fallback format)."""
        rule_content = """/*
 * @aromcp-rule-id: test-comma
 * @aromcp-patterns: **/*.ts, **/*.tsx
 * @aromcp-tags: typescript, react, components
 */"""
        
        metadata = extract_metadata_from_comments(rule_content)
        
        assert metadata["rule_id"] == "test-comma"
        # Should parse comma-separated values
        assert "typescript" in metadata["tags"]
        assert "react" in metadata["tags"]
        assert "components" in metadata["tags"]

    def test_multiple_comment_blocks(self):
        """Test handling multiple comment blocks in a rule file."""
        rule_content = """/*
 * Regular comment block
 */

/*
 * @aromcp-rule-id: multi-comment
 * @aromcp-patterns: ["**/*.ts"]
 * @aromcp-severity: warn
 */

/*
 * Another regular comment
 */

module.exports = {};"""
        
        metadata = extract_metadata_from_comments(rule_content)
        
        assert metadata["rule_id"] == "multi-comment"
        assert metadata["patterns"] == ["**/*.ts"]
        assert metadata["severity"] == "warn"