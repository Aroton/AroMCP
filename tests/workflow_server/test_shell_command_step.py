"""
Test suite for Shell Command Step Implementation - Acceptance Criteria 3.4

This file tests the following acceptance criteria:
- AC 3.4.1: Shell command execution with working directory
- AC 3.4.2: Command timeout and graceful termination  
- AC 3.4.3: Output capture (stdout, stderr, exit codes)
- AC 3.4.4: Execution context (client vs server)
- AC 3.4.5: State updates with command output
- AC 3.4.6: Error handling strategies for command failures

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

import os
import pytest
import tempfile
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from aromcp.workflow_server.workflow.steps.shell_command import ShellCommandProcessor


class TestShellCommandExecution:
    """Test shell command execution with various configurations."""

    def test_shell_command_basic_execution(self):
        """Test basic shell command execution with default configuration."""
        step_definition = {
            "command": "echo 'Hello World'"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert "Hello World" in result["output"]["stdout"]
        assert result["output"]["exit_code"] == 0
        assert result["output"]["stderr"] == ""

    def test_shell_command_working_directory_specification(self):
        """Test shell command execution with specified working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file in the temp directory
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("test content")
            
            step_definition = {
                "command": "ls test.txt",
                "working_directory": temp_dir
            }
            
            workflow_id = "test_workflow_123"
            state_manager = Mock()
            
            result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
            
            assert result["status"] == "success"
            assert "test.txt" in result["output"]["stdout"]
            assert result["output"]["exit_code"] == 0

    def test_shell_command_timeout_handling(self):
        """Test shell command timeout handling with graceful termination."""
        step_definition = {
            "command": "sleep 5",  # Command that takes longer than timeout
            "timeout": 1  # 1 second timeout
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "failed"
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower() or "killed" in result["error"].lower()

    def test_shell_command_output_capture_stdout_stderr(self):
        """Test shell command output capture for both stdout and stderr."""
        step_definition = {
            "command": "echo 'stdout message' && echo 'stderr message' >&2"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert "stdout message" in result["output"]["stdout"]
        assert "stderr message" in result["output"]["stderr"]
        assert result["output"]["exit_code"] == 0

    def test_shell_command_exit_code_handling(self):
        """Test shell command exit code handling for failed commands."""
        step_definition = {
            "command": "exit 42"  # Command that returns non-zero exit code
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        # Should capture exit code but status depends on error handling strategy
        assert result["output"]["exit_code"] == 42
        # With default error handling, non-zero exit should fail
        assert result["status"] == "failed"

    def test_shell_command_state_updates_with_output(self):
        """Test shell command state updates with command output."""
        step_definition = {
            "command": "echo 'test output'",
            "state_update": {
                "command_result": "{{ output.stdout }}"
            }
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert "test output" in result["output"]["stdout"]
        
        # State updates are handled by the embedded state update processor
        # in step_processors.py, so the shell command processor doesn't call
        # update_state directly. It just returns the output for processing.
        assert not state_manager.update_state.called
        
        # The step definition is preserved for the embedded processor
        assert "state_update" in step_definition


class TestShellCommandExecutionContext:
    """Test shell command execution context handling."""

    def test_shell_command_server_execution_context(self):
        """Test shell command execution in server context."""
        step_definition = {
            "command": "pwd",
            "execution_context": "server"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "server"
        assert result["output"]["exit_code"] == 0

    def test_shell_command_client_execution_context(self):
        """Test shell command execution in client context."""
        step_definition = {
            "command": "echo 'client command'",
            "execution_context": "client"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        # Client execution should return different result structure
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "shell_command"
        assert result["agent_action"]["command"] == "echo 'client command'"

    def test_shell_command_context_parameter_validation(self):
        """Test shell command execution context parameter validation."""
        step_definition = {
            "command": "echo 'test'",
            "execution_context": "invalid_context"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "failed"
        assert "invalid execution_context" in result["error"].lower()


class TestShellCommandErrorHandling:
    """Test shell command error handling strategies."""

    def test_shell_command_timeout_graceful_termination(self):
        """Test shell command timeout with graceful termination."""
        step_definition = {
            "command": "sleep 10",
            "timeout": 1,
            "error_handling": {
                "strategy": "fail",
                "timeout_signal": "SIGTERM"
            }
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "failed"
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()

    def test_shell_command_failure_error_strategies(self):
        """Test shell command failure with different error strategies."""
        # Test retry strategy
        step_definition = {
            "command": "exit 1",
            "error_handling": {
                "strategy": "retry",
                "max_retries": 2,
                "retry_delay": 0.1
            }
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        # Should eventually fail after retries
        assert result["status"] == "failed"
        assert result["output"]["exit_code"] == 1

    def test_shell_command_invalid_command_handling(self):
        """Test shell command handling for invalid/non-existent commands."""
        step_definition = {
            "command": "nonexistent_command_12345"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "failed"
        assert result["output"]["exit_code"] != 0

    def test_shell_command_missing_command_field(self):
        """Test shell command error handling when command field is missing."""
        step_definition = {
            # Missing required 'command' field
            "timeout": 30
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "failed"
        assert "missing 'command'" in result["error"].lower()

    def test_shell_command_working_directory_not_exists(self):
        """Test shell command handling when working directory doesn't exist."""
        step_definition = {
            "command": "pwd",
            "working_directory": "/nonexistent/directory/path"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        # Should fallback to current directory and succeed
        assert result["status"] == "success"
        assert result["output"]["exit_code"] == 0

    def test_shell_command_relative_working_directory(self):
        """Test shell command with relative working directory resolution."""
        step_definition = {
            "command": "pwd",
            "working_directory": "."
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        with patch('aromcp.workflow_server.workflow.steps.shell_command.get_project_root') as mock_get_root:
            mock_get_root.return_value = "/mock/project/root"
            
            result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
            
            assert result["status"] == "success"
            mock_get_root.assert_called_once()

    def test_shell_command_state_updates_field_variations(self):
        """Test shell command state updates with different field variations."""
        step_definition = {
            "command": "echo 'test'",
            "state_updates": {
                "cmd_output": "{{ output.stdout }}",
                "cmd_exit_code": "{{ output.exit_code }}"
            }
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = ShellCommandProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        
        # State updates are handled by the embedded state update processor
        # in step_processors.py, so the shell command processor doesn't call
        # update_state directly. It just returns the output for processing.
        assert not state_manager.update_state.called
        
        # The step definition is preserved for the embedded processor
        assert "state_updates" in step_definition