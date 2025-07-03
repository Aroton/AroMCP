"""Tests for update_rule tool."""

import json
import os
import tempfile
from pathlib import Path

import pytest

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
    
    def test_add_eslint_rules_only(self):
        """Test adding only ESLint rules."""
        eslint_rules = {
            "rules": {
                "no-console": "error",
                "prefer-const": "warn",
                "no-unused-vars": "error"
            }
        }
        
        result = update_rule_impl("test-standard", False, None, eslint_rules, self.temp_dir)
        
        assert "data" in result
        assert result["data"]["hintsUpdated"] == 0
        assert result["data"]["eslintUpdated"] is True
        assert result["data"]["clearedExisting"] is False
        
        # Verify ESLint rules were saved
        eslint_file = Path(self.temp_dir) / ".aromcp" / "eslint" / "test-standard.json"
        assert eslint_file.exists()
        
        with open(eslint_file) as f:
            saved_rules = json.load(f)
        assert saved_rules["rules"]["no-console"] == "error"
    
    def test_add_both_hints_and_eslint(self):
        """Test adding both AI hints and ESLint rules."""
        ai_hints = [{
            "rule": "Test rule",
            "context": "Test context",
            "correctExample": "correct",
            "incorrectExample": "incorrect",
            "hasEslintRule": False
        }]
        
        eslint_rules = {
            "rules": {
                "test-rule": "error"
            }
        }
        
        result = update_rule_impl("test-standard", False, ai_hints, eslint_rules, self.temp_dir)
        
        assert "data" in result
        assert result["data"]["hintsUpdated"] == 1
        assert result["data"]["eslintUpdated"] is True
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
    
    def test_invalid_eslint_rules_type(self):
        """Test adding ESLint rules with invalid type."""
        result = update_rule_impl("test-standard", False, None, "not-an-object", self.temp_dir)
        
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "eslintRules must be an object" in result["error"]["message"]
    
    def test_eslint_rules_without_rules_key(self):
        """Test ESLint rules without explicit 'rules' key."""
        eslint_rules = {
            "no-console": "error",
            "prefer-const": "warn"
        }
        
        result = update_rule_impl("test-standard", False, None, eslint_rules, self.temp_dir)
        
        assert "data" in result
        assert result["data"]["eslintUpdated"] is True
        
        # Verify rules key was added
        eslint_file = Path(self.temp_dir) / ".aromcp" / "eslint" / "test-standard.json"
        with open(eslint_file) as f:
            saved_rules = json.load(f)
        assert "rules" in saved_rules
        assert saved_rules["rules"]["no-console"] == "error"
    
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