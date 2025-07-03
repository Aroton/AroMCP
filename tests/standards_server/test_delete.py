"""Tests for delete tool."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from aromcp.standards_server.tools.delete import delete_impl
from aromcp.standards_server.tools.register import register_impl
from aromcp.standards_server.tools.update_rule import update_rule_impl


class TestDelete:
    """Test the delete functionality."""
    
    def test_basic_deletion(self):
        """Test basic standard deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
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
            
            register_result = register_impl("standards/test.md", metadata, temp_dir)
            assert "data" in register_result
            
            # Add some hints and ESLint rules
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
            
            update_result = update_rule_impl(
                "test-standard", False, ai_hints, eslint_rules, temp_dir
            )
            assert "data" in update_result
            
            # Now delete the standard
            delete_result = delete_impl("test-standard", temp_dir)
            
            assert "data" in delete_result
            assert "deleted" in delete_result["data"]
            assert delete_result["data"]["deleted"]["aiHints"] == 1
            assert delete_result["data"]["deleted"]["eslintRules"] is True
            
            # Verify files were removed
            aromcp_dir = Path(temp_dir) / ".aromcp"
            standard_dir = aromcp_dir / "hints" / "test-standard"
            eslint_file = aromcp_dir / "eslint" / "test-standard.json"
            
            assert not standard_dir.exists()
            assert not eslint_file.exists()
            
            # Verify manifest was updated
            manifest_file = aromcp_dir / "manifest.json"
            with open(manifest_file) as f:
                manifest = json.load(f)
            
            assert "test-standard" not in manifest.get("standards", {})
    
    def test_delete_nonexistent_standard(self):
        """Test deleting a standard that doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            result = delete_impl("nonexistent-standard", temp_dir)
            
            assert "data" in result
            assert result["data"]["deleted"]["aiHints"] == 0
            assert result["data"]["deleted"]["eslintRules"] is False
    
    def test_delete_empty_standard_id(self):
        """Test deleting with empty standard ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            result = delete_impl("", temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "standardId must be a non-empty string" in result["error"]["message"]
    
    def test_delete_none_standard_id(self):
        """Test deleting with None standard ID."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            result = delete_impl(None, temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
    
    def test_delete_with_hints_only(self):
        """Test deleting a standard with only hints (no ESLint rules)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            # Register standard
            metadata = {
                "id": "hints-only",
                "name": "Hints Only Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            register_impl("standards/hints-only.md", metadata, temp_dir)
            
            # Add only hints (no ESLint rules)
            ai_hints = [
                {
                    "rule": "First rule",
                    "context": "First context",
                    "correctExample": "correct1",
                    "incorrectExample": "incorrect1",
                    "hasEslintRule": False
                },
                {
                    "rule": "Second rule",
                    "context": "Second context",
                    "correctExample": "correct2",
                    "incorrectExample": "incorrect2",
                    "hasEslintRule": False
                }
            ]
            
            update_rule_impl("hints-only", False, ai_hints, None, temp_dir)
            
            # Delete the standard
            result = delete_impl("hints-only", temp_dir)
            
            assert "data" in result
            assert result["data"]["deleted"]["aiHints"] == 2
            assert result["data"]["deleted"]["eslintRules"] is False
    
    def test_delete_with_eslint_only(self):
        """Test deleting a standard with only ESLint rules (no hints)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            # Register standard
            metadata = {
                "id": "eslint-only",
                "name": "ESLint Only Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            register_impl("standards/eslint-only.md", metadata, temp_dir)
            
            # Add only ESLint rules (no hints)
            eslint_rules = {
                "rules": {
                    "test-rule": "error",
                    "another-rule": "warn"
                }
            }
            
            update_rule_impl("eslint-only", False, None, eslint_rules, temp_dir)
            
            # Delete the standard
            result = delete_impl("eslint-only", temp_dir)
            
            assert "data" in result
            assert result["data"]["deleted"]["aiHints"] == 0
            assert result["data"]["deleted"]["eslintRules"] is True
    
    def test_index_rebuild_after_deletion(self):
        """Test that index is rebuilt after deletion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            # Register two standards
            metadata1 = {
                "id": "standard-1",
                "name": "Standard 1",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            metadata2 = {
                "id": "standard-2",
                "name": "Standard 2",
                "category": "api",
                "tags": ["api"],
                "appliesTo": ["*.js"],
                "severity": "warning",
                "priority": "important"
            }
            
            register_impl("standards/standard-1.md", metadata1, temp_dir)
            register_impl("standards/standard-2.md", metadata2, temp_dir)
            
            # Verify both are in index
            index_file = Path(temp_dir) / ".aromcp" / "hints" / "index.json"
            with open(index_file) as f:
                index = json.load(f)
            
            assert "standard-1" in index["standards"]
            assert "standard-2" in index["standards"]
            
            # Delete one standard
            delete_impl("standard-1", temp_dir)
            
            # Verify index was updated
            with open(index_file) as f:
                updated_index = json.load(f)
            
            assert "standard-1" not in updated_index["standards"]
            assert "standard-2" in updated_index["standards"]