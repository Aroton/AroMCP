"""Tests for add_rule tool."""

import json
import os
import tempfile
from pathlib import Path

from aromcp.standards_server.tools.add_rule import add_rule_impl, list_rules_impl
from aromcp.standards_server.tools.register import register_impl


class TestAddRule:
    """Test the add_rule functionality."""

    def setup_method(self):
        """Set up test environment with a registered standard."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

        # Register a test standard first
        source_file = Path(self.temp_dir) / "standards" / "test.md"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# Test Standard")

        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.js"],
            "severity": "error",
            "priority": "required",
        }

        result = register_impl("standards/test.md", metadata, self.temp_dir)
        assert "data" in result

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_add_basic_rule(self):
        """Test adding a basic ESLint rule to a standard."""
        rule_content = """module.exports = {
    meta: {
        type: 'problem',
        docs: {
            description: 'Test rule description',
            category: 'Best Practices',
            recommended: true
        },
        messages: {
            testMessage: 'This is a test message'
        },
        fixable: 'code'
    },
    create(context) {
        return {
            'Identifier': function(node) {
                context.report({
                    node: node,
                    messageId: 'testMessage'
                });
            }
        };
    }
};"""

        result = add_rule_impl("test-standard", "test-rule", rule_content, self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard"
        assert result["data"]["ruleName"] == "test-rule"
        assert result["data"]["ruleSize"] == len(rule_content)

        # Verify rule file was created
        rule_file = Path(result["data"]["ruleFile"])
        assert rule_file.exists()
        assert rule_file.name == "test-standard-test-rule.js"

        # Verify rule content
        assert rule_file.read_text() == rule_content

    def test_add_multiple_rules(self):
        """Test adding multiple rules to a standard."""
        rule1_content = "module.exports = { /* rule 1 */ };"
        rule2_content = "module.exports = { /* rule 2 */ };"

        # Add first rule
        result1 = add_rule_impl("test-standard", "rule-1", rule1_content, self.temp_dir)
        assert "data" in result1
        assert result1["data"]["ruleName"] == "rule-1"

        # Add second rule
        result2 = add_rule_impl("test-standard", "rule-2", rule2_content, self.temp_dir)
        assert "data" in result2
        assert result2["data"]["ruleName"] == "rule-2"

        # Verify both files exist
        rules_dir = Path(self.temp_dir) / ".aromcp" / "eslint" / "rules"
        assert (rules_dir / "test-standard-rule-1.js").exists()
        assert (rules_dir / "test-standard-rule-2.js").exists()

    def test_add_rule_nonexistent_standard(self):
        """Test adding a rule to a nonexistent standard."""
        rule_content = "module.exports = {};"

        result = add_rule_impl("nonexistent-standard", "test-rule", rule_content, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert "Standard nonexistent-standard not found" in result["error"]["message"]

    def test_add_rule_invalid_name(self):
        """Test adding a rule with invalid name."""
        rule_content = "module.exports = {};"

        # Test with special characters
        result = add_rule_impl("test-standard", "invalid@name", rule_content, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Rule name must be alphanumeric" in result["error"]["message"]

    def test_add_rule_empty_name(self):
        """Test adding a rule with empty name."""
        rule_content = "module.exports = {};"

        result = add_rule_impl("test-standard", "", rule_content, self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Rule name must be alphanumeric" in result["error"]["message"]

    def test_add_rule_empty_content(self):
        """Test adding a rule with empty content."""
        result = add_rule_impl("test-standard", "test-rule", "", self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Rule content cannot be empty" in result["error"]["message"]

    def test_add_rule_whitespace_only_content(self):
        """Test adding a rule with whitespace-only content."""
        result = add_rule_impl("test-standard", "test-rule", "   \n  \t  ", self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Rule content cannot be empty" in result["error"]["message"]

    def test_add_rule_valid_names(self):
        """Test adding rules with valid names including hyphens and underscores."""
        rule_content = "module.exports = {};"

        # Test hyphenated name
        result1 = add_rule_impl("test-standard", "hyphen-rule", rule_content, self.temp_dir)
        assert "data" in result1

        # Test underscore name
        result2 = add_rule_impl("test-standard", "underscore_rule", rule_content, self.temp_dir)
        assert "data" in result2

        # Test mixed alphanumeric
        result3 = add_rule_impl("test-standard", "rule123", rule_content, self.temp_dir)
        assert "data" in result3

    def test_add_rule_directory_creation(self):
        """Test that ESLint rules directory is created if it doesn't exist."""
        # Remove the eslint directory
        eslint_dir = Path(self.temp_dir) / ".aromcp" / "eslint"
        if eslint_dir.exists():
            import shutil

            shutil.rmtree(eslint_dir)

        rule_content = "module.exports = {};"
        result = add_rule_impl("test-standard", "test-rule", rule_content, self.temp_dir)

        assert "data" in result
        assert (eslint_dir / "rules").exists()

    def test_add_rule_index_rebuild(self):
        """Test that index is rebuilt after adding a rule."""
        rule_content = "module.exports = {};"

        # Check index before
        index_file = Path(self.temp_dir) / ".aromcp" / "hints" / "index.json"
        if index_file.exists():
            with open(index_file) as f:
                json.load(f)
        else:
            pass

        result = add_rule_impl("test-standard", "index-test", rule_content, self.temp_dir)
        assert "data" in result

        # Check index after
        assert index_file.exists()
        with open(index_file) as f:
            index_after = json.load(f)

        # Index should have been updated
        assert "standards" in index_after


class TestListRules:
    """Test the list_rules functionality."""

    def setup_method(self):
        """Set up test environment with a registered standard and some rules."""
        self.temp_dir = tempfile.mkdtemp()
        os.environ["MCP_FILE_ROOT"] = self.temp_dir

        # Register a test standard first
        source_file = Path(self.temp_dir) / "standards" / "test.md"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# Test Standard")

        metadata = {
            "id": "test-standard",
            "name": "Test Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.js"],
            "severity": "error",
            "priority": "required",
        }

        result = register_impl("standards/test.md", metadata, self.temp_dir)
        assert "data" in result

        # Add a couple of rules
        add_rule_impl("test-standard", "rule-1", "module.exports = { /* rule 1 */ };", self.temp_dir)
        add_rule_impl("test-standard", "rule-2", "module.exports = { /* rule 2 */ };", self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_list_rules_basic(self):
        """Test listing rules for a standard."""
        result = list_rules_impl("test-standard", self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard"
        assert len(result["data"]["rules"]) == 2

        # Check rule details
        rules = {rule["ruleName"]: rule for rule in result["data"]["rules"]}
        assert "rule-1" in rules
        assert "rule-2" in rules

        # Check file paths
        assert "test-standard-rule-1.js" in rules["rule-1"]["ruleFile"]
        assert "test-standard-rule-2.js" in rules["rule-2"]["ruleFile"]

        # Check sizes
        assert rules["rule-1"]["ruleSize"] > 0
        assert rules["rule-2"]["ruleSize"] > 0

    def test_list_rules_empty(self):
        """Test listing rules for a standard with no rules."""
        # Register another standard without rules
        metadata = {
            "id": "empty-standard",
            "name": "Empty Standard",
            "category": "testing",
            "tags": ["test"],
            "appliesTo": ["*.js"],
            "severity": "error",
            "priority": "required",
        }

        register_impl("standards/empty.md", metadata, self.temp_dir)

        result = list_rules_impl("empty-standard", self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "empty-standard"
        assert len(result["data"]["rules"]) == 0

    def test_list_rules_nonexistent_standard(self):
        """Test listing rules for a nonexistent standard."""
        result = list_rules_impl("nonexistent-standard", self.temp_dir)

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert "Standard nonexistent-standard not found" in result["error"]["message"]

    def test_list_rules_no_eslint_directory(self):
        """Test listing rules when ESLint directory doesn't exist."""
        # Remove the eslint directory
        eslint_dir = Path(self.temp_dir) / ".aromcp" / "eslint"
        if eslint_dir.exists():
            import shutil

            shutil.rmtree(eslint_dir)

        result = list_rules_impl("test-standard", self.temp_dir)

        assert "data" in result
        assert result["data"]["standardId"] == "test-standard"
        assert len(result["data"]["rules"]) == 0
