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
                patterns=["*.py"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["items"]) == 2  # Both test.py and src/main.py match
            file_paths = {f["path"] for f in result["data"]["items"]}
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
                patterns=["**/*.py"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["items"]) == 3
            file_paths = {f["path"] for f in result["data"]["items"]}
            assert file_paths == {"src/main.py", "src/utils/helper.py", "tests/test_main.py"}

    def test_invalid_project_root(self):
        """Test error handling for invalid project root."""
        result = get_target_files_impl(
            patterns=["*.py"],
            project_root="/nonexistent/path"
        )

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"

    def test_empty_patterns(self):
        """Test error when patterns are empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = get_target_files_impl(
                patterns=[],
                project_root=temp_dir
            )

            assert "error" in result
            assert result["error"]["code"] == "INVALID_INPUT"


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
                patterns=["**/*.py", "**/*.js", "*.json"],
                project_root=temp_dir
            )

            assert "data" in result
            file_paths = {f["path"] for f in result["data"]["items"]}
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
                patterns=["/src/*.py"],  # Absolute pattern
                project_root=temp_dir
            )

            assert "data" in result
            file_paths = {f["path"] for f in result["data"]["items"]}
            assert file_paths == {"src/main.py"}

    def test_pagination_response_structure(self):
        """Test that pagination response structure is correct."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create some test files
            files = ["file1.py", "file2.py", "file3.py"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            result = get_target_files_impl(
                patterns=["*.py"],
                project_root=temp_dir
            )

            assert "data" in result
            assert "items" in result["data"]
            assert "pagination" in result["data"]

            # Check pagination structure
            pagination = result["data"]["pagination"]
            assert "page" in pagination
            assert "total_pages" in pagination
            assert "total_items" in pagination
            assert "page_size" in pagination
            assert "has_next" in pagination
            assert "has_previous" in pagination
            assert "estimated_tokens" in pagination
            assert "max_tokens" in pagination

    def test_pagination_parameters(self):
        """Test pagination with different page and max_tokens parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create many small files
            files = [f"file{i}.py" for i in range(10)]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Test with small max_tokens to force pagination
            result = get_target_files_impl(
                patterns=["*.py"],
                project_root=temp_dir,
                page=1,
                max_tokens=100  # Small limit to force pagination
            )

            assert "data" in result
            assert len(result["data"]["items"]) <= 10

            # Test page 2 if there are multiple pages
            if result["data"]["pagination"]["has_next"]:
                result_page2 = get_target_files_impl(
                    patterns=["*.py"],
                    project_root=temp_dir,
                    page=2,
                    max_tokens=100
                )

                assert "data" in result_page2
                assert result_page2["data"]["pagination"]["page"] == 2
