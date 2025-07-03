"""Tests for security validation across all filesystem tools."""

import tempfile

from aromcp.filesystem_server.tools import (
    extract_method_signatures_impl,
    read_files_batch_impl,
    write_files_batch_impl,
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
                # Test read_files_batch
                result = read_files_batch_impl([path], temp_dir)
                assert "data" in result
                assert "errors" in result["data"]
                assert any("outside project root" in error["error"] for error in result["data"]["errors"])

                # Test extract_method_signatures
                result = extract_method_signatures_impl(path, temp_dir)
                assert "data" in result
                assert "errors" in result["data"]
                assert any("outside project root" in error["error"] for error in result["data"]["errors"])

    def test_write_files_path_validation(self):
        """Test path validation in write operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            malicious_files = {
                "../../../tmp/malicious.txt": "bad content",
                "/tmp/absolute_bad.txt": "also bad"
            }

            result = write_files_batch_impl(malicious_files, temp_dir)

            # Should fail due to path validation
            assert "error" in result
            assert "outside project root" in result["error"]["message"]
