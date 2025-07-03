"""Tests for check_updates tool."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from aromcp.standards_server.tools.check_updates import check_updates_impl


class TestCheckUpdates:
    """Test the check_updates functionality."""
    
    def test_basic_functionality(self):
        """Test basic check_updates functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up project structure
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            # Create standards directory
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create a sample markdown file
            sample_md = standards_dir / "error-handling.md"
            sample_md.write_text("# Error Handling\n\nSample standard content.")
            
            # Test with no existing manifest
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert "needsUpdate" in result["data"]
            assert "upToDate" in result["data"]
            assert len(result["data"]["needsUpdate"]) == 1
            assert result["data"]["needsUpdate"][0]["reason"] == "new"
            assert result["data"]["needsUpdate"][0]["standardId"] == "error-handling"
    
    def test_empty_standards_directory(self):
        """Test with empty standards directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            assert result["data"]["needsUpdate"] == []
            assert result["data"]["upToDate"] == 0
    
    def test_invalid_standards_path(self):
        """Test with invalid standards path."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            result = check_updates_impl("nonexistent", temp_dir)
            
            assert "data" in result
            assert result["data"]["needsUpdate"] == []
            assert result["data"]["upToDate"] == 0