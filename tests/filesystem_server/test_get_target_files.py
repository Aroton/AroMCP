"""Tests for get_target_files implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import get_target_files_impl


class TestGetTargetFiles:
    """Test get_target_files implementation."""

    def test_pattern_mode_basic(self):
        """Test basic pattern matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = ["test.py", "src/main.py", "docs/readme.md"]
            for file_path in test_files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("test content")

            result = get_target_files_impl(
                status="pattern",
                patterns=["*.py"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 2  # Both test.py and src/main.py match
            file_paths = {f["path"] for f in result["data"]["files"]}
            assert "test.py" in file_paths
            assert "src/main.py" in file_paths

    def test_pattern_mode_recursive(self):
        """Test recursive pattern matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            files = ["src/main.py", "src/utils/helper.py", "tests/test_main.py"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("# Python file")

            result = get_target_files_impl(
                status="pattern",
                patterns=["**/*.py"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 3
            file_paths = {f["path"] for f in result["data"]["files"]}
            assert file_paths == {"src/main.py", "src/utils/helper.py", "tests/test_main.py"}

    def test_invalid_project_root(self):
        """Test error handling for invalid project root."""
        result = get_target_files_impl(
            status="pattern",
            patterns=["*.py"],
            project_root="/nonexistent/path"
        )

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_pattern_mode_without_patterns(self):
        """Test error when patterns are missing in pattern mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_target_files_impl(
                status="pattern",
                patterns=None,
                project_root=temp_dir
            )

            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
    
    def test_git_status_not_in_git_repo(self):
        """Test error when trying to use git status outside git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_target_files_impl(
                status="working",
                project_root=temp_dir
            )
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "Not in a git repository" in result["error"]["message"]
    
    def test_invalid_status_mode(self):
        """Test error for invalid status mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_target_files_impl(
                status="invalid_mode",
                project_root=temp_dir
            )
            
            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"
            assert "Invalid status" in result["error"]["message"]
    
    def test_multiple_patterns(self):
        """Test multiple glob patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create diverse file structure
            files = [
                "src/main.py", "src/utils.js", "tests/test.py", 
                "docs/readme.md", "config.json", "style.css"
            ]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")
            
            result = get_target_files_impl(
                status="pattern",
                patterns=["**/*.py", "**/*.js", "*.json"],
                project_root=temp_dir
            )
            
            assert "data" in result
            file_paths = {f["path"] for f in result["data"]["files"]}
            expected = {"src/main.py", "src/utils.js", "tests/test.py", "config.json"}
            assert file_paths == expected
    
    def test_absolute_patterns(self):
        """Test absolute patterns within project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            files = ["src/main.py", "tests/test.py", "docs/readme.md"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")
            
            result = get_target_files_impl(
                status="pattern",
                patterns=["/src/*.py"],  # Absolute pattern
                project_root=temp_dir
            )
            
            assert "data" in result
            file_paths = {f["path"] for f in result["data"]["files"]}
            assert file_paths == {"src/main.py"}