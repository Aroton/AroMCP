"""Tests for read_files_batch implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import read_files_batch_impl


class TestReadFilesBatch:
    """Test read_files_batch implementation."""

    def test_read_multiple_files(self):
        """Test reading multiple files successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "file1.txt": "Content of file 1",
                "file2.py": "# Python content\nprint('hello')",
                "dir/file3.md": "# Markdown\n\nSome content"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            result = read_files_batch_impl(
                file_paths=list(files.keys()),
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 3

            for file_path, expected_content in files.items():
                assert file_path in result["data"]["files"]
                assert result["data"]["files"][file_path]["content"] == expected_content
                assert result["data"]["files"][file_path]["lines"] == len(expected_content.splitlines())

    def test_file_not_found(self):
        """Test handling of non-existent files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = read_files_batch_impl(
                file_paths=["nonexistent.txt"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 0
            assert "errors" in result["data"]
            assert len(result["data"]["errors"]) == 1
            assert result["data"]["errors"][0]["file"] == "nonexistent.txt"

    def test_path_traversal_protection(self):
        """Test protection against directory traversal attacks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = read_files_batch_impl(
                file_paths=["../../../etc/passwd"],
                project_root=temp_dir
            )

            assert "data" in result
            assert "errors" in result["data"]
            assert any("outside project root" in error["error"] for error in result["data"]["errors"])

    def test_encoding_auto_detection(self):
        """Test automatic encoding detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create files with different encodings
            utf8_file = Path(temp_dir) / "utf8.txt"
            utf8_file.write_text("Hello 世界", encoding="utf-8")

            ascii_file = Path(temp_dir) / "ascii.txt"
            ascii_file.write_text("Hello World", encoding="ascii")

            result = read_files_batch_impl(
                file_paths=["utf8.txt", "ascii.txt"],
                project_root=temp_dir,
                encoding="auto"
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 2
            assert result["data"]["files"]["utf8.txt"]["content"] == "Hello 世界"
            assert result["data"]["files"]["ascii.txt"]["content"] == "Hello World"

    def test_explicit_encoding(self):
        """Test explicit encoding specification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("Hello World", encoding="utf-8")

            result = read_files_batch_impl(
                file_paths=["test.txt"],
                project_root=temp_dir,
                encoding="utf-8"
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 1
            assert result["data"]["files"]["test.txt"]["encoding"] == "utf-8"

    def test_large_file_handling(self):
        """Test handling of large files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file larger than 1MB
            large_file = Path(temp_dir) / "large.txt"
            large_content = "x" * (1024 * 1024 + 1)  # Just over 1MB
            large_file.write_text(large_content)

            result = read_files_batch_impl(
                file_paths=["large.txt"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 0
            assert "errors" in result["data"]
            assert any("too large" in error["error"] for error in result["data"]["errors"])

    def test_directory_instead_of_file(self):
        """Test error when path points to directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a directory
            dir_path = Path(temp_dir) / "subdir"
            dir_path.mkdir()

            result = read_files_batch_impl(
                file_paths=["subdir"],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 0
            assert "errors" in result["data"]
            assert any("not a file" in error["error"] for error in result["data"]["errors"])

    def test_empty_file_list(self):
        """Test behavior with empty file list."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = read_files_batch_impl(
                file_paths=[],
                project_root=temp_dir
            )

            assert "data" in result
            assert len(result["data"]["files"]) == 0
            assert result["data"]["summary"]["total_files"] == 0

    def test_pattern_expansion_basic(self):
        """Test basic glob pattern expansion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "test1.py": "# Python file 1",
                "test2.py": "# Python file 2",
                "test.js": "// JavaScript file",
                "README.md": "# Readme",
                "dir/nested.py": "# Nested Python file"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Test *.py pattern
            result = read_files_batch_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            python_files = result["data"]["files"]
            assert len(python_files) == 2  # test1.py and test2.py
            assert "test1.py" in python_files
            assert "test2.py" in python_files
            assert "test.js" not in python_files

    def test_pattern_expansion_recursive(self):
        """Test recursive glob pattern expansion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "src/main.py": "# Main Python file",
                "src/utils/helper.py": "# Helper functions",
                "src/tests/test_main.py": "# Test file",
                "docs/README.md": "# Documentation"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content)

            # Test **/*.py pattern
            result = read_files_batch_impl(
                file_paths=["**/*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            python_files = result["data"]["files"]
            assert len(python_files) == 3
            assert "src/main.py" in python_files
            assert "src/utils/helper.py" in python_files
            assert "src/tests/test_main.py" in python_files

    def test_pattern_expansion_multiple_patterns(self):
        """Test multiple patterns in one call."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "app.py": "# Python app",
                "config.json": '{"test": true}',
                "styles.css": "body { margin: 0; }",
                "script.js": "console.log('hello');",
                "README.md": "# Documentation"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            # Test multiple patterns
            result = read_files_batch_impl(
                file_paths=["*.py", "*.json", "*.js"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            matched_files = result["data"]["files"]
            assert len(matched_files) == 3
            assert "app.py" in matched_files
            assert "config.json" in matched_files
            assert "script.js" in matched_files
            assert "styles.css" not in matched_files
            assert "README.md" not in matched_files

    def test_pattern_expansion_disabled(self):
        """Test behavior when pattern expansion is disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "test1.py": "# Python file 1",
                "test2.py": "# Python file 2"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            # Test with patterns but expansion disabled
            result = read_files_batch_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=False
            )

            assert "data" in result
            # Should treat "*.py" as literal filename (which doesn't exist)
            assert len(result["data"]["files"]) == 0
            assert "errors" in result["data"]
            assert len(result["data"]["errors"]) == 1

    def test_pattern_no_matches(self):
        """Test pattern that matches no files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create one file
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")

            # Test pattern that won't match
            result = read_files_batch_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            # Should treat "*.py" as literal filename since no matches found
            assert len(result["data"]["files"]) == 0
            assert "errors" in result["data"]
            assert len(result["data"]["errors"]) == 1

    def test_mixed_patterns_and_static_paths(self):
        """Test mixing glob patterns with static file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "main.py": "# Main file",
                "utils.py": "# Utils",
                "config.json": '{"key": "value"}',
                "README.md": "# Documentation"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            # Test mixing patterns and static paths
            result = read_files_batch_impl(
                file_paths=["*.py", "config.json", "README.md"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            matched_files = result["data"]["files"]
            assert len(matched_files) == 4
            assert "main.py" in matched_files
            assert "utils.py" in matched_files
            assert "config.json" in matched_files
            assert "README.md" in matched_files

    def test_pattern_summary_statistics(self):
        """Test that summary includes pattern expansion statistics."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            files = {
                "test1.py": "# File 1",
                "test2.py": "# File 2"
            }

            for file_path, content in files.items():
                full_path = Path(temp_dir) / file_path
                full_path.write_text(content)

            result = read_files_batch_impl(
                file_paths=["*.py"],
                project_root=temp_dir,
                expand_patterns=True
            )

            assert "data" in result
            summary = result["data"]["summary"]
            assert summary["input_patterns"] == 1  # One input pattern
            assert summary["total_files"] == 2     # Expanded to 2 files
            assert summary["patterns_expanded"] is True
            assert "duration_ms" in summary
