"""Tests for string parameter handling in standards server APIs."""

import json
import os
import tempfile

from aromcp.standards_server.tools.add_rule import add_rule_impl
from aromcp.standards_server.tools.register import register_impl


class TestStringParameters:
    """Test that APIs accept both string and object parameters."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_register_with_string_metadata(self):
        """Test register API with JSON string metadata."""
        metadata_dict = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required",
        }

        # Convert to JSON string
        metadata_str = json.dumps(metadata_dict)

        result = register_impl("standards/test.md", metadata_str, self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard"
        assert result["data"]["isNew"] is True

    def test_register_with_dict_metadata(self):
        """Test register API with dict metadata (existing behavior)."""
        metadata_dict = {
            "id": "test-standard-2",
            "name": "Test Standard 2",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required",
        }

        result = register_impl("standards/test2.md", metadata_dict, self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard-2"
        assert result["data"]["isNew"] is True

    def test_register_with_invalid_json_string(self):
        """Test register API with invalid JSON string."""
        invalid_json = '{"id": "incomplete", "name": "Incomplete"'  # Missing closing brace

        result = register_impl("standards/invalid.md", invalid_json, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid JSON in metadata" in result["error"]["message"]

    def test_add_rule_with_string_parameters(self):
        """Test add_rule API with string parameters."""
        # First register a standard
        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required",
        }

        register_impl("standards/test.md", metadata, self.temp_dir)

        # Test with string parameters
        rule_content = "module.exports = { meta: {}, create: function() {} };"

        result = add_rule_impl("test-standard", "test-rule", rule_content, self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard"
        assert result["data"]["ruleName"] == "test-rule"
