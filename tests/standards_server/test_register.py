"""Tests for register tool."""

import os
import tempfile
from pathlib import Path

import pytest

from aromcp.standards_server.tools.register import register_impl


class TestRegister:
    """Test the register functionality."""
    
    def test_basic_registration(self):
        """Test basic standard registration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            # Create source file
            source_file = Path(temp_dir) / "standards" / "error-handling.md"
            source_file.parent.mkdir()
            source_file.write_text("# Error Handling Standard")
            
            metadata = {
                "id": "error-handling",
                "name": "Error Handling",
                "category": "api",
                "tags": ["error", "exceptions"],
                "appliesTo": ["*.py", "*.js"],
                "severity": "error",
                "priority": "required"
            }
            
            result = register_impl("standards/error-handling.md", metadata, temp_dir)
            
            assert "data" in result
            assert result["data"]["standardId"] == "error-handling"
            assert result["data"]["isNew"] is True
            
            # Verify files were created
            aromcp_dir = Path(temp_dir) / ".aromcp"
            assert aromcp_dir.exists()
            
            metadata_file = aromcp_dir / "hints" / "error-handling" / "metadata.json"
            assert metadata_file.exists()
            
            manifest_file = aromcp_dir / "manifest.json"
            assert manifest_file.exists()
    
    def test_duplicate_registration(self):
        """Test registering the same standard twice."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            source_file = Path(temp_dir) / "standards" / "test.md"
            source_file.parent.mkdir()
            source_file.write_text("# Test Standard")
            
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "warning",
                "priority": "recommended"
            }
            
            # First registration
            result1 = register_impl("standards/test.md", metadata, temp_dir)
            assert result1["data"]["isNew"] is True
            
            # Second registration
            result2 = register_impl("standards/test.md", metadata, temp_dir)
            assert result2["data"]["isNew"] is False
    
    def test_missing_required_fields(self):
        """Test registration with missing required fields."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            incomplete_metadata = {
                "id": "incomplete",
                "name": "Incomplete Standard"
                # Missing required fields
            }
            
            result = register_impl("standards/incomplete.md", incomplete_metadata, temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "Missing required metadata field" in result["error"]["message"]
    
    def test_invalid_severity(self):
        """Test registration with invalid severity value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "invalid-severity",  # Invalid value
                "priority": "recommended"
            }
            
            result = register_impl("standards/test.md", metadata, temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "Invalid severity" in result["error"]["message"]
    
    def test_invalid_priority(self):
        """Test registration with invalid priority value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "invalid-priority"  # Invalid value
            }
            
            result = register_impl("standards/test.md", metadata, temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "Invalid priority" in result["error"]["message"]
    
    def test_invalid_tags_type(self):
        """Test registration with invalid tags type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": "not-an-array",  # Should be array
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            result = register_impl("standards/test.md", metadata, temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "tags must be an array" in result["error"]["message"]
    
    def test_invalid_applies_to_type(self):
        """Test registration with invalid appliesTo type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": "not-an-array",  # Should be array
                "severity": "error",
                "priority": "required"
            }
            
            result = register_impl("standards/test.md", metadata, temp_dir)
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "appliesTo must be an array" in result["error"]["message"]
    
    def test_index_rebuild_after_registration(self):
        """Test that index is rebuilt after registration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            metadata = {
                "id": "test-standard",
                "name": "Test Standard",
                "category": "testing",
                "tags": ["test"],
                "appliesTo": ["*.py"],
                "severity": "error",
                "priority": "required"
            }
            
            result = register_impl("standards/test.md", metadata, temp_dir)
            assert "data" in result
            
            # Check that index was created
            index_file = Path(temp_dir) / ".aromcp" / "hints" / "index.json"
            assert index_file.exists()
            
            # Load and verify index content
            import json
            with open(index_file) as f:
                index = json.load(f)
            
            assert "standards" in index
            assert "test-standard" in index["standards"]
            assert index["standards"]["test-standard"]["category"] == "testing"