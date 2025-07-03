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
            
            # Create a sample markdown file with valid YAML header
            sample_md = standards_dir / "error-handling.md"
            sample_md.write_text("""---
id: error-handling
name: Error Handling
category: general
tags: [error, handling]
applies_to: ["**/*.ts", "**/*.tsx"]
severity: error
priority: required
---

# Error Handling

Sample standard content.""")
            
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

    def test_yaml_header_filtering(self):
        """Test that files without valid YAML headers are filtered out."""
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["MCP_FILE_ROOT"] = temp_dir
            
            standards_dir = Path(temp_dir) / "standards"
            standards_dir.mkdir()
            
            # Create a file with valid YAML header
            valid_md = standards_dir / "valid-standard.md"
            valid_md.write_text("""---
id: valid-standard
name: Valid Standard
category: general
---

# Valid Standard
This has a valid YAML header with id field.""")
            
            # Create a file without YAML header
            invalid_md = standards_dir / "invalid-standard.md"
            invalid_md.write_text("# Invalid Standard\n\nThis has no YAML header.")
            
            # Create a file with YAML header but no id field
            no_id_md = standards_dir / "no-id-standard.md"
            no_id_md.write_text("""---
name: No ID Standard
category: general
---

# No ID Standard
This has YAML header but no id field.""")
            
            result = check_updates_impl("standards", temp_dir)
            
            assert "data" in result
            # Only the valid file should be processed
            assert len(result["data"]["needsUpdate"]) == 1
            assert result["data"]["needsUpdate"][0]["standardId"] == "valid-standard"