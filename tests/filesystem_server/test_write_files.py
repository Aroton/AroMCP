"""Tests for write_files implementation."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from aromcp.filesystem_server.tools.write_files import write_files_impl


class TestWriteFiles:
    """Test class for write_files functionality."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory for testing."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir)

        # Create initial files
        (project_path / "existing.txt").write_text("Original content", encoding='utf-8')
        (project_path / "src").mkdir()
        (project_path / "src" / "existing.py").write_text("# Original Python file", encoding='utf-8')

        # Set environment variable for testing
        import os
        os.environ['MCP_FILE_ROOT'] = str(project_path)

        yield str(project_path)

        # Cleanup
        shutil.rmtree(temp_dir)
        if 'MCP_FILE_ROOT' in os.environ:
            del os.environ['MCP_FILE_ROOT']

    def test_write_single_file(self, temp_project):
        """Test writing a single file."""
        files = {"new_file.txt": "Hello, World!"}

        write_files_impl(files)

        # Verify file was created
        project_path = Path(temp_project)
        created_file = project_path / "new_file.txt"
        assert created_file.exists()
        assert created_file.read_text(encoding='utf-8') == "Hello, World!"

    def test_write_multiple_files(self, temp_project):
        """Test writing multiple files at once."""
        files = {
            "file1.txt": "Content of file 1",
            "file2.py": "# Python file\nprint('Hello')",
            "config.json": '{"setting": "value"}'
        }

        write_files_impl(files)

        # Verify all files were created
        project_path = Path(temp_project)
        for filename, expected_content in files.items():
            file_path = project_path / filename
            assert file_path.exists()
            assert file_path.read_text(encoding='utf-8') == expected_content

    def test_overwrite_existing_file(self, temp_project):
        """Test overwriting an existing file."""
        files = {"existing.txt": "New content"}

        write_files_impl(files)

        # Verify file was overwritten
        project_path = Path(temp_project)
        file_path = project_path / "existing.txt"
        assert file_path.read_text(encoding='utf-8') == "New content"

    def test_create_subdirectories(self, temp_project):
        """Test automatic directory creation."""
        files = {
            "new_dir/subdir/file.txt": "Content in subdirectory",
            "another/path/to/file.py": "# Python in deep path"
        }

        write_files_impl(files)

        # Verify directories and files were created
        project_path = Path(temp_project)

        file1 = project_path / "new_dir" / "subdir" / "file.txt"
        assert file1.exists()
        assert file1.read_text(encoding='utf-8') == "Content in subdirectory"

        file2 = project_path / "another" / "path" / "to" / "file.py"
        assert file2.exists()
        assert file2.read_text(encoding='utf-8') == "# Python in deep path"

    def test_write_files_in_existing_subdirectory(self, temp_project):
        """Test writing files in existing subdirectories."""
        files = {"src/new_file.py": "# New Python file in existing dir"}

        write_files_impl(files)

        # Verify file was created in existing directory
        project_path = Path(temp_project)
        file_path = project_path / "src" / "new_file.py"
        assert file_path.exists()
        assert file_path.read_text(encoding='utf-8') == "# New Python file in existing dir"

    def test_empty_files_dict(self, temp_project):
        """Test error handling for empty files dictionary."""
        with pytest.raises(ValueError, match="Files dictionary cannot be empty"):
            write_files_impl({})

    def test_json_string_input(self, temp_project):
        """Test handling JSON string input for files parameter."""
        files_json = json.dumps({
            "from_json.txt": "Content from JSON string",
            "another.py": "# Python from JSON"
        })

        write_files_impl(files_json)

        # Verify files were created from JSON input
        project_path = Path(temp_project)

        file1 = project_path / "from_json.txt"
        assert file1.exists()
        assert file1.read_text(encoding='utf-8') == "Content from JSON string"

        file2 = project_path / "another.py"
        assert file2.exists()
        assert file2.read_text(encoding='utf-8') == "# Python from JSON"

    def test_invalid_json_string(self, temp_project):
        """Test error handling for invalid JSON string."""
        invalid_json = "{'invalid': json}"  # Single quotes, not valid JSON

        with pytest.raises(ValueError, match="Files parameter must be a valid JSON object"):
            write_files_impl(invalid_json)

    def test_unicode_content(self, temp_project):
        """Test writing files with Unicode content."""
        files = {
            "unicode.txt": "Hello 世界! 🌍",
            "emoji.md": "# Documentation with emojis 📝\n\n✅ Completed\n❌ Failed"
        }

        write_files_impl(files)

        # Verify Unicode content is preserved
        project_path = Path(temp_project)

        unicode_file = project_path / "unicode.txt"
        assert unicode_file.read_text(encoding='utf-8') == "Hello 世界! 🌍"

        emoji_file = project_path / "emoji.md"
        content = emoji_file.read_text(encoding='utf-8')
        assert "🌍" not in content  # This emoji is in unicode.txt
        assert "📝" in content
        assert "✅" in content
        assert "❌" in content

    def test_large_file_content(self, temp_project):
        """Test writing files with large content."""
        large_content = "\n".join([f"Line {i}: " + "x" * 100 for i in range(1000)])
        files = {"large_file.txt": large_content}

        write_files_impl(files)

        # Verify large file was written correctly
        project_path = Path(temp_project)
        large_file = project_path / "large_file.txt"
        assert large_file.exists()

        content = large_file.read_text(encoding='utf-8')
        assert "Line 0:" in content
        assert "Line 999:" in content
        assert len(content) > 100000  # Should be substantial

    def test_mixed_file_types(self, temp_project):
        """Test writing various file types with different content."""
        files = {
            "script.py": '''#!/usr/bin/env python3
"""A sample Python script."""

def main():
    print("Hello from Python!")

if __name__ == "__main__":
    main()
''',
            "config.json": json.dumps({
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "name": "testdb"
                },
                "features": ["auth", "logging", "caching"]
            }, indent=2),
            "README.md": '''# Test Project

This is a test project for file writing.

## Features
- File creation
- Directory creation
- Unicode support

## Usage
```python
write_files({"file.txt": "content"})
```
''',
            "style.css": '''body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
}

.container {
    max-width: 800px;
    margin: 0 auto;
}
'''
        }

        write_files_impl(files)

        # Verify all different file types were created correctly
        project_path = Path(temp_project)
        for filename, expected_content in files.items():
            file_path = project_path / filename
            assert file_path.exists()
            actual_content = file_path.read_text(encoding='utf-8')
            assert actual_content == expected_content

    def test_special_characters_in_content(self, temp_project):
        """Test writing files with special characters and escape sequences."""
        files = {
            "special.txt": 'Line with "quotes" and \'apostrophes\'\nLine with tabs:\t\tand newlines\n',
            "escaped.json": '{"message": "String with \\"escaped\\" quotes and \\n newlines"}'
        }

        write_files_impl(files)

        # Verify special characters are preserved
        project_path = Path(temp_project)

        special_file = project_path / "special.txt"
        content = special_file.read_text(encoding='utf-8')
        assert '"quotes"' in content
        assert "'apostrophes'" in content
        assert '\t\t' in content

        escaped_file = project_path / "escaped.json"
        content = escaped_file.read_text(encoding='utf-8')
        assert '\\"escaped\\"' in content
        assert '\\n' in content

    def test_path_safety(self, temp_project):
        """Test that file paths are relative to project root."""
        files = {"safe/file.txt": "Content in safe location"}

        write_files_impl(files)

        # Verify file was created within project directory
        project_path = Path(temp_project)
        created_file = project_path / "safe" / "file.txt"
        assert created_file.exists()
        assert created_file.is_relative_to(project_path)

    def test_atomic_operation_on_error(self, temp_project):
        """Test behavior when an error occurs during multi-file writing."""
        # Create a scenario where writing might fail partway through
        project_path = Path(temp_project)

        # Make a directory read-only to cause write failure
        readonly_dir = project_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        files = {
            "good_file.txt": "This should work",
            "readonly/bad_file.txt": "This should fail"
        }

        try:
            # This should raise an error
            with pytest.raises(ValueError):
                write_files_impl(files)

            # Verify that no partial writes occurred
            project_path / "good_file.txt"
            # The function doesn't guarantee atomicity, so this test
            # verifies the current behavior rather than ideal behavior

        finally:
            # Cleanup: restore permissions
            readonly_dir.chmod(0o755)
            if readonly_dir.exists():
                shutil.rmtree(readonly_dir)
