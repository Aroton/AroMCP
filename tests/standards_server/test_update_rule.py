"""Tests for update_rule tool."""

import json
import os
import tempfile
from pathlib import Path

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
            "priority": "required"
        }

        # Register the standard first
        register_impl("standards/test.md", self.metadata, self.temp_dir)

    def teardown_method(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_add_ai_hints_only(self):
        """Test adding only AI hints."""
        ai_hints = [
            {
                "rule": "Always use proper error handling",
                "context": "This ensures better debugging",
                "correctExample": "try: ...",
                "incorrectExample": "just do it",
                "hasEslintRule": False
            },
            {
                "rule": "Use meaningful variable names",
                "context": "Improves code readability",
                "correctExample": "user_count = 5",
                "incorrectExample": "x = 5",
                "hasEslintRule": True
            }
        ]

        result = update_rule_impl("test-standard", False, ai_hints, None, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 2
        assert result["data"]["eslintUpdated"] is False
        assert result["data"]["clearedExisting"] is False

        # Verify hints were saved
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "test-standard"
        hint_files = list(hints_dir.glob("hint-*.json"))
        assert len(hint_files) == 2

        # Verify hint content
        with open(hints_dir / "hint-001.json") as f:
            hint1 = json.load(f)
        assert hint1["rule"] == "Always use proper error handling"
        assert "tokens" in hint1  # Token count should be added

    def test_add_eslint_files_only(self):
        """Test adding only ESLint files."""
        eslint_files = {
            "rules/test-standard.js": '''module.exports = {
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
};''',
            "config.json": '{"rules": {"test-rule": "error"}}'
        }

        result = update_rule_impl("test-standard", False, None, eslint_files, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 0
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["eslintFilesWritten"] == 2
        assert result["data"]["clearedExisting"] is False

        # Verify ESLint files were saved
        rule_file = Path(self.temp_dir) / ".aromcp" / "eslint" / "rules" / "test-standard.js"
        config_file = Path(self.temp_dir) / ".aromcp" / "eslint" / "config.json"

        assert rule_file.exists()
        assert config_file.exists()

        with open(rule_file) as f:
            rule_content = f.read()
        assert "module.exports" in rule_content
        assert "Test rule" in rule_content

    def test_add_both_hints_and_eslint(self):
        """Test adding both AI hints and ESLint files."""
        ai_hints = [{
            "rule": "Test rule",
            "context": "Test context",
            "correctExample": "correct",
            "incorrectExample": "incorrect",
            "hasEslintRule": False
        }]

        eslint_files = {
            "rules/test-rule.js": "module.exports = { meta: {}, create: function() {} };"
        }

        result = update_rule_impl("test-standard", False, ai_hints, eslint_files, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 1
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["eslintFilesWritten"] == 1
        assert result["data"]["clearedExisting"] is False

    def test_clear_existing_hints(self):
        """Test clearing existing hints before adding new ones."""
        # First add some hints
        initial_hints = [{
            "rule": "Initial rule",
            "context": "Initial context",
            "correctExample": "initial correct",
            "incorrectExample": "initial incorrect",
            "hasEslintRule": False
        }]

        update_rule_impl("test-standard", False, initial_hints, None, self.temp_dir)

        # Verify initial hints exist
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "test-standard"
        assert len(list(hints_dir.glob("hint-*.json"))) == 1

        # Now clear and add new hints
        new_hints = [
            {
                "rule": "New rule 1",
                "context": "New context 1",
                "correctExample": "new correct 1",
                "incorrectExample": "new incorrect 1",
                "hasEslintRule": False
            },
            {
                "rule": "New rule 2",
                "context": "New context 2",
                "correctExample": "new correct 2",
                "incorrectExample": "new incorrect 2",
                "hasEslintRule": False
            }
        ]

        result = update_rule_impl("test-standard", True, new_hints, None, self.temp_dir)

        assert "data" in result
        assert result["data"]["hintsUpdated"] == 2
        assert result["data"]["clearedExisting"] is True
        assert result["data"]["clearedCount"] == 1

        # Verify only new hints exist
        hint_files = list(hints_dir.glob("hint-*.json"))
        assert len(hint_files) == 2

        with open(hints_dir / "hint-001.json") as f:
            hint = json.load(f)
        assert hint["rule"] == "New rule 1"

    def test_nonexistent_standard(self):
        """Test updating rules for a non-existent standard."""
        ai_hints = [{
            "rule": "Test rule",
            "context": "Test context",
            "correctExample": "correct",
            "incorrectExample": "incorrect"
        }]

        result = update_rule_impl("nonexistent-standard", False, ai_hints, None, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert "not found" in result["error"]["message"]

    def test_empty_standard_id(self):
        """Test updating with empty standard ID."""
        result = update_rule_impl("", False, [], None, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "standardId must be a non-empty string" in result["error"]["message"]

    def test_missing_hint_fields(self):
        """Test adding hints with missing required fields."""
        incomplete_hints = [{
            "rule": "Test rule",
            "context": "Test context"
            # Missing correctExample and incorrectExample
        }]

        result = update_rule_impl("test-standard", False, incomplete_hints, None, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "missing required field" in result["error"]["message"]

    def test_invalid_eslint_files_type(self):
        """Test adding ESLint files with invalid type."""
        # Pass a valid JSON string that parses to a non-dict
        result = update_rule_impl("test-standard", False, None, '"not-an-object"', self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "eslintFiles must be an object" in result["error"]["message"]

    def test_eslint_files_invalid_filename(self):
        """Test ESLint files with invalid filename."""
        eslint_files = {
            "../../../etc/passwd": "malicious content"
        }

        result = update_rule_impl("test-standard", False, None, eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid filename" in result["error"]["message"]

    def test_eslint_files_non_string_content(self):
        """Test ESLint files with non-string content."""
        eslint_files = {
            "rules/test.js": {"not": "a string"}  # type: ignore
        }

        result = update_rule_impl("test-standard", False, None, eslint_files, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "must be a string" in result["error"]["message"]

    def test_default_has_eslint_rule(self):
        """Test that hasEslintRule defaults to False."""
        ai_hints = [{
            "rule": "Test rule",
            "context": "Test context",
            "correctExample": "correct",
            "incorrectExample": "incorrect"
            # hasEslintRule not specified
        }]

        result = update_rule_impl("test-standard", False, ai_hints, None, self.temp_dir)

        assert "data" in result

        # Verify hasEslintRule was set to False
        hints_dir = Path(self.temp_dir) / ".aromcp" / "hints" / "test-standard"
        with open(hints_dir / "hint-001.json") as f:
            hint = json.load(f)
        assert hint["hasEslintRule"] is False

    def test_index_rebuild_after_update(self):
        """Test that index is rebuilt after updating rules."""
        ai_hints = [{
            "rule": "Test rule",
            "context": "Test context",
            "correctExample": "correct",
            "incorrectExample": "incorrect",
            "hasEslintRule": False
        }]

        result = update_rule_impl("test-standard", False, ai_hints, None, self.temp_dir)
        assert "data" in result

        # Verify index reflects the changes
        index_file = Path(self.temp_dir) / ".aromcp" / "hints" / "index.json"
        with open(index_file) as f:
            index = json.load(f)

        assert "test-standard" in index["standards"]
        assert index["standards"]["test-standard"]["hintCount"] == 1

    def test_eslint_config_files_generated(self):
        """Test that ESLint configuration files are generated when rules are added."""
        eslint_files = {
            "rules/test-rule.js": "module.exports = { meta: {}, create: function() {} };",
            "rules/another-rule.js": "module.exports = { meta: {}, create: function() {} };"
        }

        result = update_rule_impl("test-standard", False, None, eslint_files, self.temp_dir)
        assert "data" in result

        # Verify config files were created
        eslint_dir = Path(self.temp_dir) / ".aromcp" / "eslint"

        # Check plugin index file
        plugin_file = eslint_dir / "custom-rules.js"
        assert plugin_file.exists()

        with open(plugin_file) as f:
            plugin_content = f.read()
        assert "test-rule" in plugin_content
        assert "another-rule" in plugin_content
        assert "require('./rules/test-rule')" in plugin_content

        # Check standards config file (JS)
        config_file = eslint_dir / "standards-config.js"
        assert config_file.exists()

        with open(config_file) as f:
            config_content = f.read()
        assert "custom-rules/test-rule" in config_content
        assert "custom-rules/another-rule" in config_content

        # Check standards config file (JSON)
        config_json_file = eslint_dir / "standards-config.json"
        assert config_json_file.exists()

        with open(config_json_file) as f:
            config_data = json.load(f)

        assert "custom-rules/test-rule" in config_data["rules"]
        assert "custom-rules/another-rule" in config_data["rules"]
        assert config_data["plugins"] == ["./custom-rules"]
