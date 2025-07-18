"""Tests for update_rule tool."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from aromcp.standards_server.tools.register import register_impl
from aromcp.standards_server.tools.update_rule import update_rule_impl


class TestUpdateRule:
    """Test the update_rule functionality."""

    def setup_method(self):
        """Set up a registered standard for testing."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

        self.metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.py"],
            "severity": "error",
            "priority": "required",
        }

        # Register the standard first
        register_impl("standards/test.md", self.metadata, self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_add_eslint_files(self):
        """Test adding ESLint files."""
        eslint_files = {
            "rules/test-standard.js": """module.exports = {
  meta: {
    type: "problem",
    docs: {
      description: "Test rule",
      category: "Possible Errors"
    }
  },
  create: function(context) {
    return {
      'CallExpression': function(node) {
        context.report({
          node: node,
          message: 'Test message'
        });
      }
    };
  }
};"""
        }

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "data" in result
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["eslintFilesWritten"] == 1
        assert result["data"]["standard_id"] == "test-standard"

        # Verify ESLint files were saved
        rule_file = Path(self.temp_dir) / ".aromcp" / "eslint" / "rules" / "test-standard.js"
        config_file = Path(self.temp_dir) / ".aromcp" / "eslint" / "standards-config.json"

        assert rule_file.exists()
        assert config_file.exists()

        with open(rule_file) as f:
            rule_content = f.read()
        assert "module.exports" in rule_content
        assert "Test rule" in rule_content

    def test_add_multiple_eslint_files(self):
        """Test adding multiple ESLint files."""
        eslint_files = {
            "rules/test-rule1.js": "module.exports = { meta: {}, create: function() {} };",
            "rules/test-rule2.js": "module.exports = { meta: {}, create: function() {} };",
        }

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "data" in result
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["eslintFilesWritten"] == 2

        # Verify both files were saved
        rule_file1 = Path(self.temp_dir) / ".aromcp" / "eslint" / "rules" / "test-rule1.js"
        rule_file2 = Path(self.temp_dir) / ".aromcp" / "eslint" / "rules" / "test-rule2.js"

        assert rule_file1.exists()
        assert rule_file2.exists()

    def test_missing_eslint_files(self):
        """Test calling update_rule without eslint_files."""
        result = update_rule_impl("test-standard", None, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "eslint_files is required" in result["error"]["message"]

    def test_nonexistent_standard(self):
        """Test updating rules for a non-existent standard."""
        eslint_files = {"rules/test.js": "module.exports = { meta: {}, create: function() {} };"}

        result = update_rule_impl("nonexistent-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert "not found" in result["error"]["message"]

    def test_empty_standard_id(self):
        """Test updating with empty standard ID."""
        result = update_rule_impl("", {}, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "standardId must be a non-empty string" in result["error"]["message"]

    def test_invalid_eslint_files_type(self):
        """Test adding ESLint files with invalid type."""
        # Pass a valid JSON string that parses to a non-dict
        result = update_rule_impl("test-standard", '"not-an-object"', self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "eslintFiles must be an object" in result["error"]["message"]

    def test_eslint_files_invalid_filename(self):
        """Test ESLint files with invalid filename."""
        eslint_files = {"../../../etc/passwd": "malicious content"}

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid filename" in result["error"]["message"]

    def test_eslint_files_non_string_content(self):
        """Test ESLint files with non-string content."""
        eslint_files: dict[str, Any] = {"rules/test.js": {"not": "a string"}}  # type: ignore

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "must be a string" in result["error"]["message"]

    def test_eslint_files_not_in_rules_directory(self):
        """Test ESLint files not in rules/ directory."""
        eslint_files = {"test.js": "module.exports = { meta: {}, create: function() {} };"}

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "must be in 'rules/' directory" in result["error"]["message"]

    def test_eslint_files_config_in_filename(self):
        """Test ESLint files with 'config' in filename."""
        eslint_files = {"rules/test-config.js": "module.exports = { meta: {}, create: function() {} };"}

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "cannot contain 'config' in filename" in result["error"]["message"]

    def test_eslint_files_index_filename(self):
        """Test ESLint files named 'index'."""
        eslint_files = {"rules/index.js": "module.exports = { meta: {}, create: function() {} };"}

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "cannot be named 'index'" in result["error"]["message"]

    def test_eslint_files_invalid_content(self):
        """Test ESLint files with invalid content."""
        eslint_files = {"rules/test.js": "not a valid ESLint rule"}

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "must contain a valid module.exports ESLint rule" in result["error"]["message"]

    def test_eslint_files_with_config_object(self):
        """Test ESLint files containing configuration objects."""
        eslint_files = {
            "rules/test.js": """module.exports = {
                meta: {},
                create: function() {},
                rules: {
                    'some-rule': 'error'
                }
            };"""
        }

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "must contain a valid module.exports ESLint rule" in result["error"]["message"]

    def test_index_rebuild_after_update(self):
        """Test that index is rebuilt after updating rules."""
        eslint_files = {"rules/test.js": "module.exports = { meta: {}, create: function() {} };"}

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)
        assert "data" in result

        # Verify index exists (it should be created by build_index)
        index_file = Path(self.temp_dir) / ".aromcp" / "hints" / "index.json"
        assert index_file.exists()

    def test_eslint_config_files_generated(self):
        """Test that ESLint configuration files are generated when rules are added."""
        eslint_files = {
            "rules/test-rule.js": "module.exports = { meta: {}, create: function() {} };",
            "rules/another-rule.js": "module.exports = { meta: {}, create: function() {} };",
        }

        result = update_rule_impl("test-standard", eslint_files, self.temp_dir)
        assert "data" in result

        # Verify config files were created
        eslint_dir = Path(self.temp_dir) / ".aromcp" / "eslint"

        # Check plugin index file (updated name)
        plugin_file = eslint_dir / "eslint-plugin-aromcp.js"
        assert plugin_file.exists()

        with open(plugin_file) as f:
            plugin_content = f.read()
        assert "test-rule" in plugin_content
        assert "another-rule" in plugin_content
        assert "require('./rules/test-rule')" in plugin_content

        # Check that package.json was created for the plugin
        package_file = eslint_dir / "package.json"
        assert package_file.exists()
        with open(package_file) as f:
            package_data = json.load(f)
        assert package_data["name"] == "eslint-plugin-aromcp"

        # Check standards config file (JS)
        config_file = eslint_dir / "standards-config.js"
        assert config_file.exists()

        with open(config_file) as f:
            config_content = f.read()
        # Check for new aromcp/ rule format
        assert "aromcp/test-rule" in config_content
        assert "aromcp/another-rule" in config_content
        # Check that ignore patterns are included
        assert "ignores:" in config_content
        assert "'.aromcp/**'" in config_content
        assert "'node_modules/**'" in config_content

        # Check standards config file (JSON)
        config_json_file = eslint_dir / "standards-config.json"
        assert config_json_file.exists()

        with open(config_json_file) as f:
            config_data = json.load(f)

        # Check for new aromcp/ rule format in JSON (new configs format)
        assert "configs" in config_data
        assert len(config_data["configs"]) >= 1

        # Find the config that contains our rules
        rules_found = []
        for config in config_data["configs"]:
            if "rules" in config:
                rules_found.extend(config["rules"].keys())

        assert "aromcp/test-rule" in rules_found
        assert "aromcp/another-rule" in rules_found

    def test_json_string_input(self):
        """Test that JSON string input is properly parsed."""
        eslint_files_json = json.dumps({"rules/test.js": "module.exports = { meta: {}, create: function() {} };"})

        result = update_rule_impl("test-standard", eslint_files_json, self.temp_dir)

        assert "data" in result
        assert result["data"]["eslintFilesWritten"] == 1
        assert result["data"]["eslintUpdated"] is True
