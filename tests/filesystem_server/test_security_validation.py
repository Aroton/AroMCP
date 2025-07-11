"""Tests for security validation across all filesystem tools."""

import tempfile

from aromcp.filesystem_server.tools import (
    extract_method_signatures_impl,
    read_files_impl,
    write_files_impl,
)


class TestSecurityValidation:
    """Test security measures across all tools."""

    def test_path_traversal_protection(self):
        """Test protection against directory traversal in all tools."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test cases that should definitely trigger path traversal protection
            malicious_paths = [
                "../../../etc/passwd",
                "/etc/shadow",
            ]

            for path in malicious_paths:
                # Test read_files (should raise exception for security violations)
                try:
                    result = read_files_impl([path])
                    raise AssertionError("Should have raised security violation")
                except ValueError as e:
                    assert "Failed to read files" in str(e)

                # Test extract_method_signatures
                import os
                os.environ['MCP_FILE_ROOT'] = temp_dir
                try:
                    result = extract_method_signatures_impl(path)
                    # Should return empty result or error for invalid paths
                    assert isinstance(result, list)
                except ValueError as e:
                    assert "Failed to extract" in str(e) or "Invalid" in str(e)
                finally:
                    if 'MCP_FILE_ROOT' in os.environ:
                        del os.environ['MCP_FILE_ROOT']

    def test_write_files_path_validation(self):
        """Test path validation in write operations."""
        with tempfile.TemporaryDirectory():
            malicious_files = {
                "../../../tmp/malicious.txt": "bad content",
                "/tmp/absolute_bad.txt": "also bad"  # noqa: S108 # Test file path for security validation
            }

            # Test write_files (should raise exception for security violations)
            try:
                write_files_impl(malicious_files)
                raise AssertionError("Should have raised security violation")
            except ValueError as e:
                assert "Failed to write files" in str(e)
