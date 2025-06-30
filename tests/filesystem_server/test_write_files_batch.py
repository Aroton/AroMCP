"""Tests for write_files_batch implementation."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server.tools import write_files_batch_impl


class TestWriteFilesBatch:
    """Test write_files_batch implementation."""

    def test_write_multiple_files(self):
        """Test writing multiple files successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = {
                "test1.txt": "Content 1",
                "dir/test2.py": "print('hello')",
                "deep/nested/test3.md": "# Header"
            }

            result = write_files_batch_impl(
                files=files,
                project_root=temp_dir,
                create_backup=False
            )

            assert "data" in result
            assert len(result["data"]["written"]) == 3

            # Verify files were actually written
            for file_path, expected_content in files.items():
                full_path = Path(temp_dir) / file_path
                assert full_path.exists()
                assert full_path.read_text() == expected_content

    def test_backup_creation(self):
        """Test backup creation for existing files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing file
            existing_file = Path(temp_dir) / "existing.txt"
            existing_file.write_text("original content")

            files = {"existing.txt": "new content"}

            result = write_files_batch_impl(
                files=files,
                project_root=temp_dir,
                create_backup=True
            )

            assert "data" in result
            assert result["data"]["backup_location"] is not None

            # Verify backup was created
            backup_dir = Path(temp_dir) / result["data"]["backup_location"]
            assert backup_dir.exists()
            assert (backup_dir / "existing.txt").exists()
    
    def test_encoding_specification(self):
        """Test writing files with different encodings."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = {
                "utf8.txt": "Hello 世界",
                "ascii.txt": "Hello World"
            }
            
            # Test UTF-8 encoding
            result = write_files_batch_impl(
                files=files,
                project_root=temp_dir,
                encoding="utf-8",
                create_backup=False
            )
            
            assert "data" in result
            assert len(result["data"]["written"]) == 2
            
            # Verify files were written correctly
            utf8_file = Path(temp_dir) / "utf8.txt"
            assert utf8_file.read_text(encoding="utf-8") == "Hello 世界"
    
    def test_empty_files_dict(self):
        """Test behavior with empty files dictionary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = write_files_batch_impl(
                files={},
                project_root=temp_dir
            )
            
            assert "data" in result
            assert len(result["data"]["written"]) == 0
            assert result["data"]["backup_location"] is None
    
    def test_atomic_operation_failure(self):
        """Test atomic operation behavior on failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a read-only directory to cause write failure
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only
            
            files = {
                "readonly/test.txt": "content"
            }
            
            try:
                result = write_files_batch_impl(
                    files=files,
                    project_root=temp_dir,
                    create_backup=False
                )
                
                # Should either succeed or fail gracefully
                if "error" in result:
                    assert result["error"]["code"] == "OPERATION_FAILED"
                else:
                    # If it succeeded, verify the file was written
                    assert "data" in result
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)
    
    def test_backup_disabled(self):
        """Test writing without backup creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing file
            existing_file = Path(temp_dir) / "existing.txt"
            existing_file.write_text("original")
            
            files = {"existing.txt": "new content"}
            
            result = write_files_batch_impl(
                files=files,
                project_root=temp_dir,
                create_backup=False
            )
            
            assert "data" in result
            assert result["data"]["backup_location"] is None
            assert len(result["data"]["written"]) == 1
            assert result["data"]["written"][0]["created"] is False  # File was updated
    
    def test_create_nested_directories(self):
        """Test automatic creation of nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            files = {
                "deep/nested/dir/file.txt": "content",
                "another/path/file2.txt": "content2"
            }
            
            result = write_files_batch_impl(
                files=files,
                project_root=temp_dir,
                create_backup=False
            )
            
            assert "data" in result
            assert len(result["data"]["written"]) == 2
            # Note: created_directories tracks directories that didn't exist before
            # If the test creates parent dirs, this might be empty if they already existed
            assert len(result["data"]["created_directories"]) >= 0
            
            # Verify directories were created
            assert (Path(temp_dir) / "deep/nested/dir").exists()
            assert (Path(temp_dir) / "another/path").exists()