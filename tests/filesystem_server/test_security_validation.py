"""Tests for security validation across all filesystem tools."""

import tempfile
from pathlib import Path

from aromcp.filesystem_server._security import validate_file_path, validate_file_path_legacy
from aromcp.filesystem_server.tools import (
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

                # extract_method_signatures tool has been removed

    def test_write_files_path_validation(self):
        """Test path validation in write operations."""
        with tempfile.TemporaryDirectory():
            malicious_files = {
                "../../../tmp/malicious.txt": "bad content",
                "/tmp/absolute_bad.txt": "also bad",  # noqa: S108 # Test file path for security validation
            }

            # Test write_files (should raise exception for security violations)
            try:
                write_files_impl(malicious_files)
                raise AssertionError("Should have raised security violation")
            except ValueError as e:
                assert "Failed to write files" in str(e)

    def test_claude_directory_access(self):
        """Test that ~/.claude directory access is allowed for Claude configuration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get ~/.claude directory for test paths
            claude_dir = Path.home() / ".claude"

            # Test paths within ~/.claude
            claude_paths = [
                str(claude_dir / "commands" / "standards:create.md"),
                str(claude_dir / "templates" / "code-standards-template.md"),
                str(claude_dir / "some-config.json"),
                "~/.claude/commands/test.md",  # Test tilde expansion
            ]

            for path in claude_paths:
                # Test validate_file_path function
                result = validate_file_path(path, temp_dir)
                assert result["valid"], f"Should allow access to {path}: {result.get('error')}"

                # Test validate_file_path_legacy function
                try:
                    abs_path = validate_file_path_legacy(path, Path(temp_dir))
                    assert abs_path.is_absolute(), f"Should return absolute path for {path}"
                    # Should be within ~/.claude
                    assert str(abs_path).startswith(str(claude_dir)), f"Path should be within ~/.claude: {abs_path}"
                except ValueError as e:
                    raise AssertionError(f"Should allow access to {path}: {e}") from e

    def test_claude_directory_security_boundary(self):
        """Test that security is maintained - only ~/.claude is accessible, not other home dirs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test paths that should still be blocked
            blocked_paths = [
                "~/.ssh/id_rsa",  # SSH keys should be blocked
                "~/Documents/private.txt",  # Other home directories should be blocked
                str(Path.home() / ".ssh" / "config"),  # Absolute path to sensitive area
                str(Path.home() / "sensitive.txt"),  # Root of home directory
            ]

            for path in blocked_paths:
                # Test validate_file_path function
                result = validate_file_path(path, temp_dir)
                assert not result["valid"], f"Should block access to {path}"
                assert "outside project root" in result["error"], f"Should show proper error for {path}"

                # Test validate_file_path_legacy function
                try:
                    validate_file_path_legacy(path, Path(temp_dir))
                    raise AssertionError(f"Should block access to {path}")
                except ValueError as e:
                    assert "outside project root" in str(e), f"Should show proper error for {path}"

    def test_claude_subdirectory_traversal_protection(self):
        """Test that directory traversal is still blocked even within ~/.claude context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            claude_dir = Path.home() / ".claude"

            # These should be blocked even though they start with ~/.claude
            traversal_paths = [
                str(claude_dir / ".." / ".ssh" / "id_rsa"),  # Traverse out of .claude
                str(claude_dir / "commands" / ".." / ".." / ".ssh" / "config"),  # Multiple traversals
            ]

            for path in traversal_paths:
                # The resolved path should not be within ~/.claude anymore
                resolved = Path(path).resolve()
                claude_resolved = claude_dir.resolve()

                try:
                    resolved.relative_to(claude_resolved)
                    is_within_claude = True
                except ValueError:
                    is_within_claude = False

                if not is_within_claude:
                    # Should be blocked by our validation
                    result = validate_file_path(path, temp_dir)
                    assert not result["valid"], f"Should block traversal path {path}"

                    try:
                        validate_file_path_legacy(path, Path(temp_dir))
                        raise AssertionError(f"Should block traversal path {path}")
                    except ValueError:
                        pass  # Expected

    def test_read_files_claude_access_integration(self):
        """Test that read_files tool can access ~/.claude files."""
        # Create a temporary file in ~/.claude for testing
        claude_dir = Path.home() / ".claude"
        claude_dir.mkdir(exist_ok=True)

        test_file = claude_dir / "test-aromcp-access.txt"
        test_content = "Test content for AroMCP access validation"

        try:
            # Create test file
            test_file.write_text(test_content)

            # Test reading via read_files_impl
            result = read_files_impl([str(test_file)])
            assert isinstance(result, dict), "Should return dict with file contents"
            assert "items" in result, "Should have items key"
            assert len(result["items"]) == 1, "Should return one file result"
            assert result["items"][0]["content"] == test_content, "Should return correct file content"

        finally:
            # Clean up test file
            if test_file.exists():
                test_file.unlink()
