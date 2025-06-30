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