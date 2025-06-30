"""Tests for diff operations tools."""

import shutil
import tempfile
from pathlib import Path

import pytest

from aromcp.filesystem_server.tools.apply_file_diffs import apply_file_diffs_impl
from aromcp.filesystem_server.tools.preview_file_changes import (
    preview_file_changes_impl,
)
from aromcp.filesystem_server.tools.validate_diffs import validate_diffs_impl


class TestDiffOperations:
    """Test class for diff operations tools."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory with test files."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir)

        # Create test files
        (project_path / "test.py").write_text("""def hello():
    print("Hello")
    return "world"

def goodbye():
    print("Goodbye")
""")

        (project_path / "config.json").write_text("""{
    "name": "test",
    "version": "1.0.0"
}""")

        # Create subdirectory
        (project_path / "src").mkdir()
        (project_path / "src" / "main.py").write_text("""import sys

def main():
    print("Main function")
    sys.exit(0)
""")

        yield str(project_path)

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_validate_diffs_valid_diff(self, temp_project):
        """Test validation of valid diffs."""
        valid_diff = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("Extra line")
     return "world"
"""
        }

        result = validate_diffs_impl([valid_diff], temp_project)

        assert "data" in result
        assert result["data"]["overall_valid"] is True
        assert result["data"]["total_diffs"] == 1
        assert result["data"]["valid_diffs"] == 1
        assert len(result["data"]["individual_results"]) == 1
        assert result["data"]["individual_results"][0]["valid"] is True

    def test_validate_diffs_invalid_diff(self, temp_project):
        """Test validation of invalid diffs."""
        invalid_diff = {
            "file_path": "nonexistent.py",
            "diff_content": """--- nonexistent.py
+++ nonexistent.py
@@ -1,3 +1,4 @@
-def hello():
-    print("Hello")
 def goodbye():
     print("Goodbye")
"""
        }

        result = validate_diffs_impl([invalid_diff], temp_project)

        assert "data" in result
        assert result["data"]["overall_valid"] is False
        assert result["data"]["total_diffs"] == 1
        assert result["data"]["valid_diffs"] == 0
        assert result["data"]["invalid_diffs"] == 1

    def test_validate_diffs_security_check(self, temp_project):
        """Test security validation - path traversal attempt."""
        malicious_diff = {
            "file_path": "../../../etc/passwd",
            "diff_content": """--- ../../../etc/passwd
+++ ../../../etc/passwd
@@ -1,1 +1,2 @@
 root:x:0:0:root:/root:/bin/bash
+hacker:x:0:0:hacker:/root:/bin/bash
"""
        }

        result = validate_diffs_impl([malicious_diff], temp_project)

        assert "data" in result
        assert result["data"]["overall_valid"] is False
        assert result["data"]["invalid_diffs"] == 1
        assert "outside project root" in result["data"]["individual_results"][0]["errors"][0]

    def test_preview_file_changes_basic(self, temp_project):
        """Test basic preview functionality."""
        diff = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("New line")
     return "world"
"""
        }

        result = preview_file_changes_impl([diff], temp_project)

        assert "data" in result
        assert result["data"]["total_files"] == 1
        assert result["data"]["total_changes"] == 1
        assert len(result["data"]["files"]) == 1

        file_info = result["data"]["files"][0]
        assert file_info["path"] == "test.py"
        assert file_info["additions"] == 1
        assert file_info["deletions"] == 0
        assert file_info["net_change"] == 1
        assert file_info["file_exists"] is True

    def test_preview_file_changes_multiple_files(self, temp_project):
        """Test preview with multiple files."""
        diffs = [
            {
                "file_path": "test.py",
                "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("Added line")
     return "world"
"""
            },
            {
                "file_path": "config.json",
                "diff_content": """--- config.json
+++ config.json
@@ -1,4 +1,5 @@
 {
     "name": "test",
-    "version": "1.0.0"
+    "version": "1.0.1",
+    "description": "Test project"
 }"""
            }
        ]

        result = preview_file_changes_impl(diffs, temp_project)

        assert "data" in result
        assert result["data"]["total_files"] == 2
        assert result["data"]["total_changes"] == 4  # 1 addition + 1 deletion + 2 additions
        assert result["data"]["validation"]["all_valid"] is True

    def test_apply_file_diffs_simple(self, temp_project):
        """Test applying a simple diff."""
        diff = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@@ -2,3 +2,4 @@
     print("Hello")
     return "world"
 
+# Added comment
 def goodbye():
     print("Goodbye")
"""
        }

        result = apply_file_diffs_impl([diff], temp_project)

        assert "data" in result
        assert result["data"]["total_applied"] == 1
        assert "test.py" in result["data"]["applied_files"]

        # Verify the file was actually modified
        modified_content = (Path(temp_project) / "test.py").read_text()
        assert "# Added comment" in modified_content

    def test_apply_file_diffs_new_file(self, temp_project):
        """Test applying a diff that creates a new file."""
        diff = {
            "file_path": "new_file.py",
            "diff_content": """--- /dev/null
+++ new_file.py
@@ -0,0 +1,3 @@
+def new_function():
+    print("New file")
+    return True
"""
        }

        result = apply_file_diffs_impl([diff], temp_project)

        assert "data" in result
        assert result["data"]["total_applied"] == 1

        # Verify the new file was created
        new_file_path = Path(temp_project) / "new_file.py"
        assert new_file_path.exists()
        content = new_file_path.read_text()
        assert "def new_function():" in content

    def test_apply_file_diffs_with_backup(self, temp_project):
        """Test applying diffs with backup creation."""
        original_content = (Path(temp_project) / "test.py").read_text()

        diff = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,3 @@
 def hello():
-    print("Hello")
+    print("Hello World")
     return "world"
"""
        }

        result = apply_file_diffs_impl([diff], temp_project, create_backup=True)

        assert "data" in result
        assert result["data"]["backup_created"] is True

        # Verify the file was modified
        modified_content = (Path(temp_project) / "test.py").read_text()
        assert "Hello World" in modified_content
        assert "Hello World" not in original_content

    def test_apply_file_diffs_rollback_on_error(self, temp_project):
        """Test rollback functionality when a diff fails."""
        diffs = [
            {
                "file_path": "test.py",
                "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("First change")
     return "world"
"""
            },
            {
                "file_path": "../../../etc/passwd",  # This should fail validation
                "diff_content": """--- ../../../etc/passwd
+++ ../../../etc/passwd
@@ -1,1 +1,2 @@
 root:x:0:0:root:/root:/bin/bash
+hacker:x:0:0:hacker:/root:/bin/bash
"""
            }
        ]

        original_content = (Path(temp_project) / "test.py").read_text()

        result = apply_file_diffs_impl(diffs, temp_project, create_backup=True)

        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_FAILED"

        # Verify the file was not modified (rollback not needed since validation failed first)
        current_content = (Path(temp_project) / "test.py").read_text()
        assert current_content == original_content

    def test_apply_file_diffs_validation_failure(self, temp_project):
        """Test that validation failure prevents application."""
        invalid_diff = {
            "file_path": "../../../etc/passwd",
            "diff_content": """--- ../../../etc/passwd
+++ ../../../etc/passwd
@@ -1,1 +1,2 @@
 root:x:0:0:root:/root:/bin/bash
+hacker:x:0:0:hacker:/root:/bin/bash
"""
        }

        result = apply_file_diffs_impl([invalid_diff], temp_project)

        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_FAILED"

    def test_apply_file_diffs_directory_creation(self, temp_project):
        """Test that directories are created automatically."""
        diff = {
            "file_path": "nested/deep/new_file.py",
            "diff_content": """--- /dev/null
+++ nested/deep/new_file.py
@@ -0,0 +1,2 @@
+def nested_function():
+    return "nested"
"""
        }

        result = apply_file_diffs_impl([diff], temp_project)

        assert "data" in result
        assert result["data"]["total_applied"] == 1

        # Verify directories and file were created
        new_file_path = Path(temp_project) / "nested" / "deep" / "new_file.py"
        assert new_file_path.exists()
        assert new_file_path.parent.exists()

    def test_validation_with_missing_fields(self, temp_project):
        """Test validation with missing required fields."""
        invalid_diffs = [
            {"file_path": "test.py"},  # Missing diff_content
            {"diff_content": "some diff"},  # Missing file_path
            {}  # Missing both
        ]

        result = validate_diffs_impl(invalid_diffs, temp_project)

        assert "data" in result
        assert result["data"]["overall_valid"] is False
        assert result["data"]["invalid_diffs"] == 3

    def test_preview_with_no_preview_content(self, temp_project):
        """Test preview without full preview content."""
        diff = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("New line")
     return "world"
"""
        }

        result = preview_file_changes_impl([diff], temp_project, include_full_preview=False)

        assert "data" in result
        file_info = result["data"]["files"][0]
        assert file_info["preview"] == ""  # No preview when include_full_preview=False

    def test_complex_diff_operations(self, temp_project):
        """Test complex diff with multiple hunks."""
        diff = {
            "file_path": "src/main.py",
            "diff_content": """--- src/main.py
+++ src/main.py
@@ -1,2 +1,3 @@
 import sys
+import os
 
@@ -3,4 +4,5 @@
 def main():
     print("Main function")
+    print("Added functionality")
     sys.exit(0)
"""
        }

        # First validate
        validation_result = validate_diffs_impl([diff], temp_project)
        assert validation_result["data"]["overall_valid"] is True

        # Then preview
        preview_result = preview_file_changes_impl([diff], temp_project)
        assert preview_result["data"]["total_changes"] == 2  # 2 additions

        # Finally apply
        apply_result = apply_file_diffs_impl([diff], temp_project)
        assert "data" in apply_result

        # Verify changes
        modified_content = (Path(temp_project) / "src" / "main.py").read_text()
        assert "import os" in modified_content
        assert "Added functionality" in modified_content

    def test_strict_unified_diff_format_validation(self, temp_project):
        """Test strict validation of unified diff format requirements."""

        # Test missing file headers
        diff_no_headers = {
            "file_path": "test.py",
            "diff_content": """@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("Added line")
     return "world"
"""
        }

        result = validate_diffs_impl([diff_no_headers], temp_project)
        assert result["data"]["overall_valid"] is False
        assert any("file headers" in error for error in result["data"]["individual_results"][0]["errors"])

        # Test invalid hunk header format (single @ instead of double @@)
        diff_invalid_hunk = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@ -1,3 +1,4 @
 def hello():
     print("Hello")
+    print("Added line")
     return "world"
"""
        }

        result = validate_diffs_impl([diff_invalid_hunk], temp_project)
        assert result["data"]["overall_valid"] is False
        assert any("No hunk headers found" in error for error in result["data"]["individual_results"][0]["errors"])

        # Test proper unified diff format (should pass)
        diff_valid = {
            "file_path": "test.py",
            "diff_content": """--- test.py
+++ test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("Added line")
     return "world"
"""
        }

        result = validate_diffs_impl([diff_valid], temp_project)
        assert result["data"]["overall_valid"] is True

        # Verify metadata is populated correctly
        individual_result = result["data"]["individual_results"][0]
        assert individual_result["metadata"]["hunk_count"] == 1
        assert individual_result["metadata"]["additions"] == 1
        assert individual_result["metadata"]["deletions"] == 0
        assert individual_result["metadata"]["context_lines"] == 3
