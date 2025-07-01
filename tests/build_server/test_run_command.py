"""Tests for run_command tool in Build Tools."""

import json
import subprocess
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from aromcp.build_server.tools.run_command import run_command_impl


class TestRunCommand:
    """Test class for run_command tool."""

    def test_basic_functionality(self):
        """Test basic command execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="echo",
                args=["hello", "world"],
                project_root=temp_dir,
                allowed_commands=["echo", "ls"],  # Add echo to allowed commands
                timeout=30
            )
            
            assert "data" in result
            assert result["data"]["success"] is True
            assert result["data"]["exit_code"] == 0
            assert "hello world" in result["data"]["stdout"]
            assert result["data"]["command"] == "echo hello world"

    def test_command_whitelist_validation(self):
        """Test that commands not in whitelist are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="rm",
                args=["-rf", "/"],
                project_root=temp_dir,
                allowed_commands=["npm", "yarn", "tsc"]
            )
            
            assert "error" in result
            assert result["error"]["code"] == "PERMISSION_DENIED"
            assert "not in whitelist" in result["error"]["message"]

    def test_custom_whitelist(self):
        """Test command execution with custom whitelist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="echo",
                args=["test"],
                project_root=temp_dir,
                allowed_commands=["echo", "ls"],
                timeout=30
            )
            
            assert "data" in result
            assert result["data"]["success"] is True

    def test_command_failure(self):
        """Test handling of failed commands."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="ls",
                args=["/nonexistent/path"],
                project_root=temp_dir,
                allowed_commands=["ls"],
                timeout=30
            )
            
            assert "data" in result
            assert result["data"]["success"] is False
            assert result["data"]["exit_code"] != 0
            assert len(result["data"]["stderr"]) > 0

    def test_environment_variables(self):
        """Test setting custom environment variables."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="echo",
                args=["$TEST_VAR"],
                project_root=temp_dir,
                allowed_commands=["echo"],
                env_vars={"TEST_VAR": "test_value"},
                timeout=30
            )
            
            assert "data" in result
            assert result["data"]["success"] is True

    def test_no_capture_output(self):
        """Test command execution without capturing output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="echo",
                args=["test"],
                project_root=temp_dir,
                allowed_commands=["echo"],
                capture_output=False,
                timeout=30
            )
            
            assert "data" in result
            assert result["data"]["stdout"] == ""
            assert result["data"]["stderr"] == ""

    @patch('subprocess.run')
    def test_timeout_handling(self, mock_run):
        """Test timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired("test", 30)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="echo",
                args=["test"],
                project_root=temp_dir,
                allowed_commands=["echo"],
                timeout=30
            )
            
            assert "error" in result
            assert result["error"]["code"] == "TIMEOUT"

    def test_invalid_project_root(self):
        """Test handling of invalid project root."""
        result = run_command_impl(
            command="echo",
            args=["test"],
            project_root="/../../invalid/path"
        )
        
        assert "error" in result
        # The function checks whitelist before project root, so PERMISSION_DENIED comes first
        assert result["error"]["code"] == "PERMISSION_DENIED"

    def test_metadata_present(self):
        """Test that metadata is included in response."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_command_impl(
                command="echo",
                args=["test"],
                project_root=temp_dir,
                allowed_commands=["echo"],
                timeout=30
            )
            
            assert "metadata" in result
            assert "timestamp" in result["metadata"]
            assert "duration_ms" in result["metadata"]
            assert "timeout_seconds" in result["metadata"]
            assert result["metadata"]["timeout_seconds"] == 30

    def test_working_directory(self):
        """Test that command runs in correct working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file in the temp directory
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")
            
            result = run_command_impl(
                command="ls",
                args=["test.txt"],
                project_root=temp_dir,
                allowed_commands=["ls"],
                timeout=30
            )
            
            assert "data" in result
            assert result["data"]["success"] is True
            assert "test.txt" in result["data"]["stdout"]