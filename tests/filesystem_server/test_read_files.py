"""Tests for read_files implementation."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from aromcp.filesystem_server.tools.read_files import read_files_impl


class TestReadFiles:
    """Test class for read_files functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory with test files."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir)

        # Create test files with different encodings and sizes
        (project_path / "small.txt").write_text("Hello World", encoding="utf-8")
        (project_path / "medium.py").write_text(
            '''def hello():
    """A simple greeting function."""
    print("Hello, World!")
    return "greeting"

def goodbye():
    """A simple farewell function."""
    print("Goodbye!")
    return "farewell"
''',
            encoding="utf-8",
        )

        # Create a larger file for pagination testing
        large_content = "\n".join([f"# Line {i}: " + "x" * 100 for i in range(100)])
        (project_path / "large.py").write_text(large_content, encoding="utf-8")

        # Create JSON config file
        config = {"name": "test", "version": "1.0.0", "features": ["read", "write"]}
        (project_path / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

        # Create subdirectory with file
        (project_path / "src").mkdir()
        (project_path / "src" / "utils.py").write_text("# Utility functions\npass", encoding="utf-8")

        # Set environment variable for testing
        import os

        os.environ["MCP_FILE_ROOT"] = str(project_path)

        yield str(project_path)

        # Cleanup
        shutil.rmtree(temp_dir)
        if "MCP_FILE_ROOT" in os.environ:
            del os.environ["MCP_FILE_ROOT"]

    def test_read_single_file(self, temp_project):
        """Test reading a single file."""
        result = read_files_impl("small.txt")

        assert "items" in result
        assert len(result["items"]) == 1

        file_data = result["items"][0]
        assert file_data["file"] == "small.txt"
        assert file_data["content"] == "Hello World"
        assert file_data["encoding"] in ["utf-8", "ascii"]  # chardet may detect ASCII for simple text
        assert file_data["size"] == 11

    def test_read_multiple_files(self, temp_project):
        """Test reading multiple files."""
        files = ["small.txt", "config.json"]
        result = read_files_impl(files)

        assert "items" in result
        assert len(result["items"]) == 2

        # Files should be sorted by filename
        assert result["items"][0]["file"] == "config.json"
        assert result["items"][1]["file"] == "small.txt"

        # Check metadata
        assert result["total_files"] == 2
        assert result["files_requested"] == 2

    def test_read_files_with_subdirectory(self, temp_project):
        """Test reading files from subdirectories."""
        result = read_files_impl("src/utils.py")

        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["file"] == "src/utils.py"
        assert result["items"][0]["content"] == "# Utility functions\npass"

    def test_pagination_small_files(self, temp_project):
        """Test that small file sets skip pagination."""
        files = ["small.txt", "config.json"]
        result = read_files_impl(files, page=1, max_tokens=1000)

        # Small sets should not have pagination metadata
        assert "items" in result
        assert "page" not in result or result.get("page") == 1
        assert len(result["items"]) == 2

    def test_pagination_large_files(self, temp_project):
        """Test pagination with large files."""
        files = ["large.py", "medium.py", "small.txt", "config.json"]
        result = read_files_impl(files, page=1, max_tokens=5000)

        assert "items" in result
        # Should have pagination for larger datasets
        if len(result["items"]) < 4:
            assert "page" in result
            assert "has_more" in result

    def test_single_file_as_string(self, temp_project):
        """Test passing a single file as string instead of list."""
        result = read_files_impl("small.txt")

        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["file"] == "small.txt"

    def test_file_not_found(self, temp_project):
        """Test error handling for non-existent files."""
        with pytest.raises(ValueError, match="File not found"):
            read_files_impl("nonexistent.txt")

    def test_path_is_directory(self, temp_project):
        """Test error handling when path is a directory."""
        with pytest.raises(ValueError, match="Path is not a file"):
            read_files_impl("src")

    def test_empty_file_list(self, temp_project):
        """Test behavior with empty file list."""
        result = read_files_impl([])

        assert "items" in result
        assert len(result["items"]) == 0

    def test_encoding_detection(self, temp_project):
        """Test that encoding is properly detected and reported."""
        result = read_files_impl("medium.py")

        assert "items" in result
        file_data = result["items"][0]
        assert file_data["encoding"] in ["utf-8", "ascii"]  # chardet may detect ASCII for simple text
        assert "def hello():" in file_data["content"]

    def test_deterministic_ordering(self, temp_project):
        """Test that file ordering is deterministic."""
        files = ["medium.py", "small.txt", "config.json"]
        result1 = read_files_impl(files)
        result2 = read_files_impl(files)

        # Results should be identical
        assert result1["items"] == result2["items"]

        # Should be sorted by filename
        filenames = [item["file"] for item in result1["items"]]
        assert filenames == sorted(filenames)

    def test_pagination_page_parameter(self, temp_project):
        """Test pagination with different page numbers."""
        files = ["large.py", "medium.py", "small.txt", "config.json"] * 3  # 12 files

        # Test first page
        result_page1 = read_files_impl(files, page=1, max_tokens=3000)

        # Test second page if pagination occurred
        if result_page1.get("has_more"):
            result_page2 = read_files_impl(files, page=2, max_tokens=3000)
            assert result_page2["page"] == 2

            # Items should be different between pages
            page1_files = {item["file"] for item in result_page1["items"]}
            page2_files = {item["file"] for item in result_page2["items"]}
            assert page1_files != page2_files

    def test_large_file_content_handling(self, temp_project):
        """Test handling of files with substantial content."""
        result = read_files_impl("large.py")

        assert "items" in result
        file_data = result["items"][0]
        assert file_data["file"] == "large.py"
        assert "Line 0:" in file_data["content"]
        assert "Line 99:" in file_data["content"]
        assert file_data["size"] > 10000  # Should be a substantial file

    def test_metadata_consistency(self, temp_project):
        """Test that metadata is consistent and accurate."""
        files = ["small.txt", "medium.py", "config.json"]
        result = read_files_impl(files)

        assert result["total_files"] == len(result["items"])
        assert result["files_requested"] == len(files)

        # All items should have required fields
        for item in result["items"]:
            assert "file" in item
            assert "content" in item
            assert "encoding" in item
            assert "size" in item
            assert isinstance(item["size"], int)
            assert item["size"] >= 0
