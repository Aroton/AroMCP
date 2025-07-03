"""Tests for string parameter handling in standards server APIs."""

import json
import os
import tempfile

from aromcp.standards_server.tools.register import register_impl
from aromcp.standards_server.tools.update_rule import update_rule_impl


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
            "priority": "required"
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
            "priority": "required"
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

    def test_update_rule_with_string_ai_hints(self):
        """Test update_rule API with JSON string ai_hints."""
        # First register a standard
        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required"
        }

        register_impl("standards/test.md", metadata, self.temp_dir)

        # Now test with string ai_hints
        ai_hints_list = [
            {
                "rule": "Test rule",
                "context": "Test context",
                "correctExample": "correct",
                "incorrectExample": "incorrect",
                "hasEslintRule": False
            }
        ]

        ai_hints_str = json.dumps(ai_hints_list)

        result = update_rule_impl("test-standard", False, ai_hints_str, None, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 1
        assert result["data"]["eslintUpdated"] is False

    def test_update_rule_with_string_eslint_files(self):
        """Test update_rule API with JSON string eslint_files."""
        # First register a standard
        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required"
        }

        register_impl("standards/test.md", metadata, self.temp_dir)

        # Now test with string eslint_files
        eslint_files_dict = {
            "rules/test-rule.js": "module.exports = { meta: {}, create: function() {} };"
        }

        eslint_files_str = json.dumps(eslint_files_dict)

        result = update_rule_impl("test-standard", False, None, eslint_files_str, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 0
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["eslintFilesWritten"] == 1

    def test_update_rule_with_both_string_parameters(self):
        """Test update_rule API with both ai_hints and eslint_files as strings."""
        # First register a standard
        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required"
        }

        register_impl("standards/test.md", metadata, self.temp_dir)

        # Test with both parameters as strings
        ai_hints_list = [
            {
                "rule": "Test rule",
                "context": "Test context",
                "correctExample": "correct",
                "incorrectExample": "incorrect",
                "hasEslintRule": False
            }
        ]

        eslint_files_dict = {
            "rules/test-rule.js": "module.exports = { meta: {}, create: function() {} };"
        }

        ai_hints_str = json.dumps(ai_hints_list)
        eslint_files_str = json.dumps(eslint_files_dict)

        result = update_rule_impl("test-standard", False, ai_hints_str, eslint_files_str, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 1
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["eslintFilesWritten"] == 1

    def test_update_rule_with_invalid_json_ai_hints(self):
        """Test update_rule API with invalid JSON string for ai_hints."""
        # First register a standard
        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required"
        }

        register_impl("standards/test.md", metadata, self.temp_dir)

        # Test with invalid JSON
        invalid_json = '[{"rule": "incomplete"'  # Missing closing bracket

        result = update_rule_impl("test-standard", False, invalid_json, None, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid JSON in ai_hints" in result["error"]["message"]

    def test_update_rule_with_invalid_json_eslint_files(self):
        """Test update_rule API with invalid JSON string for eslint_files."""
        # First register a standard
        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required"
        }

        register_impl("standards/test.md", metadata, self.temp_dir)

        # Test with invalid JSON
        invalid_json = '{"rules/test.js": '  # Missing closing braces

        result = update_rule_impl("test-standard", False, None, invalid_json, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid JSON in eslint_files" in result["error"]["message"]
