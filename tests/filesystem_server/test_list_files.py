"""Tests for list_files implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import list_files_impl


class TestListFiles:
    """Test list_files implementation."""

    def test_basic_pattern_matching(self):
        """Test basic pattern matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            test_files = ["test.py", "src/main.py", "docs/readme.md"]
            for file_path in test_files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("test content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["*.py"])

            assert isinstance(result, list)
            assert len(result) == 2  # Both test.py and src/main.py match
            assert "test.py" in result
            assert "src/main.py" in result

    def test_recursive_pattern_matching(self):
        """Test recursive pattern matching."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested structure
            files = ["src/main.py", "src/utils/helper.py", "tests/test_main.py"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("# Python file")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["**/*.py"])

            assert isinstance(result, list)
            assert len(result) == 3
            assert set(result) == {"src/main.py", "src/utils/helper.py", "tests/test_main.py"}

    def test_multiple_patterns(self):
        """Test multiple glob patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create diverse file structure
            files = ["src/main.py", "src/utils.js", "tests/test.py", "docs/readme.md", "config.json", "style.css"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["**/*.py", "**/*.js", "*.json"])

            assert isinstance(result, list)
            expected = {"src/main.py", "src/utils.js", "tests/test.py", "config.json"}
            assert set(result) == expected

    def test_single_string_pattern(self):
        """Test single pattern as string instead of list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = ["test.py", "other.js"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns="*.py")

            assert isinstance(result, list)
            assert result == ["test.py"]

    def test_no_matches(self):
        """Test when no files match the pattern."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files that won't match
            files = ["readme.md", "config.json"]
            for file_path in files:
                full_path = Path(temp_dir) / file_path
                full_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            result = list_files_impl(patterns=["*.py"])

            assert isinstance(result, list)
            assert len(result) == 0

    def test_duplicate_removal(self):
        """Test that duplicate paths are removed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file that would match multiple patterns
            file_path = Path(temp_dir) / "test.py"
            file_path.write_text("content")

            # Set project root for the test
            import os

            os.environ["MCP_FILE_ROOT"] = temp_dir

            # Use patterns that would both match the same file
            result = list_files_impl(patterns=["*.py", "test.*"])

            assert isinstance(result, list)
            assert len(result) == 1
            assert result == ["test.py"]
