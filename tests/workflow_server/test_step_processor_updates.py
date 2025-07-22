"""Tests for updated step processor functionality.

Tests new step types (agent_prompt, agent_response) and embedded state updates.
"""

import pytest
from unittest.mock import Mock, MagicMock

from aromcp.workflow_server.workflow.step_processors import StepProcessor
from aromcp.workflow_server.workflow.models import WorkflowInstance, WorkflowStep, WorkflowDefinition
from aromcp.workflow_server.workflow.queue import WorkflowQueue
from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator


class TestStepProcessorUpdates:
    """Test updated step processor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock(spec=StateManager)
        self.expression_evaluator = Mock(spec=ExpressionEvaluator)
        self.processor = StepProcessor(self.state_manager, self.expression_evaluator)
        
        # Mock workflow instance
        self.workflow_def = Mock(spec=WorkflowDefinition)
        self.instance = WorkflowInstance(
            id="test-workflow-id",
            workflow_name="test-workflow",
            definition=self.workflow_def,
            inputs={"test_input": "test_value"}
        )
        
        self.queue = Mock(spec=WorkflowQueue)
        
        # Default state structure
        self.default_state = {
            "inputs": {"test_input": "test_value"},
            "state": {"counter": 0, "message": ""},
            "computed": {"total": 10}
        }

    def test_agent_prompt_step_processing(self):
        """Test agent_prompt step processing."""
        step = WorkflowStep(
            id="agent_prompt_1",
            type="agent_prompt",
            definition={
                "prompt": "Analyze the code for issues",
                "context": {"file_path": "test.py"},
                "expected_response": {"type": "object", "required": ["issues"]},
                "timeout": 300,
                "max_retries": 3
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        # Should return agent prompt instruction
        assert result["id"] == "agent_prompt_1"
        assert result["type"] == "agent_prompt"
        assert result["definition"]["prompt"] == "Analyze the code for issues"
        assert result["definition"]["context"]["file_path"] == "test.py"
        assert result["definition"]["timeout"] == 300
        assert result["definition"]["max_retries"] == 3

    def test_agent_response_step_processing(self):
        """Test agent_response step processing."""
        step = WorkflowStep(
            id="agent_response_1",
            type="agent_response",
            definition={
                "response_schema": {"type": "object", "required": ["status"]},
                "state_updates": [
                    {"path": "state.result", "value": "response.status", "operation": "set"}
                ]
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        # Should return placeholder for agent response processing
        assert result["executed"] is False
        assert result["requires_agent_response"] is True

    def test_shell_command_with_embedded_state_updates(self):
        """Test shell command with embedded state updates."""
        step = WorkflowStep(
            id="shell_cmd_1",
            type="shell_command",
            definition={
                "command": "echo 'test output'",
                "state_update": {
                    "path": "state.last_output",
                    "value": "stdout",
                    "operation": "set"
                },
                "state_updates": [
                    {"path": "state.command_count", "value": 1, "operation": "increment"},
                    {"path": "state.outputs", "value": "stdout", "operation": "append"}
                ]
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        # Mock shell command result
        shell_result = {
            "status": "success",
            "output": {
                "stdout": "test output",
                "stderr": "",
                "returncode": 0
            }
        }
        self.processor.shell_command_processor.process.return_value = shell_result
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        # Should process embedded state updates
        assert result["executed"] is True
        assert result["result"]["shell_command with state_updates_applied"] == 3  # shell_command with state_update + 2 shell_command with state_updates
        
        # Verify state updates were called
        self.state_manager.update.assert_called_once()
        updates = self.state_manager.update.call_args[0][1]
        
        # Should have 3 updates: single state_update + 2 from state_updates array
        assert len(updates) == 3
        
        # Check individual updates
        update_paths = [u["path"] for u in updates]
        assert "state.last_output" in update_paths
        assert "state.command_count" in update_paths
        assert "state.outputs" in update_paths

    def test_embedded_state_update_value_resolution(self):
        """Test that embedded state updates resolve shell command output values."""
        step = WorkflowStep(
            id="shell_cmd_2",
            type="shell_command",
            definition={
                "command": "echo 'hello world'",
                "state_updates": [
                    {"path": "state.stdout_content", "value": "stdout", "operation": "set"},
                    {"path": "state.exit_code", "value": "returncode", "operation": "set"},
                    {"path": "state.full_result", "value": "full_output", "operation": "set"}
                ]
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        # Mock shell command result
        shell_result = {
            "status": "success",
            "output": {
                "stdout": "hello world\n",
                "stderr": "",
                "returncode": 0,
                "command": "echo 'hello world'"
            }
        }
        self.processor.shell_command_processor.process.return_value = shell_result
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        # Verify state updates with resolved values
        updates = self.state_manager.update.call_args[0][1]
        
        # Find each update and verify values were resolved
        stdout_update = next(u for u in updates if u["path"] == "state.stdout_content")
        assert stdout_update["value"] == "hello world\n"
        
        exit_code_update = next(u for u in updates if u["path"] == "state.exit_code")
        assert exit_code_update["value"] == 0
        
        full_result_update = next(u for u in updates if u["path"] == "state.full_result")
        assert full_result_update["value"] == shell_result["output"]

    def test_deprecated_step_types_removed(self):
        """Test that deprecated step types are no longer processed."""
        deprecated_steps = ["state_update", "batch_state_update"]
        
        for step_type in deprecated_steps:
            step = WorkflowStep(
                id=f"{step_type}_test",
                type=step_type,
                definition={"path": "state.test", "value": "test"}
            )
            
            self.state_manager.read.return_value = self.default_state
            
            result = self.processor.process_server_step(self.instance, step, self.queue, {})
            
            # Should return error for unsupported step type
            assert "error" in result
            if isinstance(result["error"], dict):
                assert f"Unsupported server step type: {step_type}" in result["error"]["message"]
            else:
                assert f"Unsupported server step type: {step_type}" in result["error"]

    def test_flatten_state_utility(self):
        """Test the _flatten_state utility method."""
        nested_state = {
            "inputs": {"file_path": "test.py", "mode": "analyze"},
            "state": {"counter": 5, "nested": {"value": "test"}},
            "computed": {"total": 15}
        }
        
        flattened = self.processor._flatten_state(nested_state)
        
        expected_keys = [
            "inputs.file_path", "inputs.mode",
            "state.counter", "state.nested.value",
            "computed.total"
        ]
        
        for key in expected_keys:
            assert key in flattened
        
        assert flattened["inputs.file_path"] == "test.py"
        assert flattened["state.counter"] == 5
        assert flattened["state.nested.value"] == "test"
        assert flattened["computed.total"] == 15


class TestUpdateOperations:
    """Test all update operations: set, increment, decrement, append, multiply."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock(spec=StateManager)
        self.expression_evaluator = Mock(spec=ExpressionEvaluator)
        self.processor = StepProcessor(self.state_manager, self.expression_evaluator)
        
        self.instance = WorkflowInstance(
            id="test-workflow-id",
            workflow_name="test-workflow",
            definition=Mock(spec=WorkflowDefinition),
            inputs={}
        )
        
        self.queue = Mock(spec=WorkflowQueue)
        self.default_state = {"inputs": {}, "state": {}, "computed": {}}

    def test_set_operation(self):
        """Test set operation in state updates."""
        step = WorkflowStep(
            id="test_set",
            type="shell_command",
            definition={
                "command": "echo 'test'",
                "state_update": {
                    "path": "state.value",
                    "value": "new_value",
                    "operation": "set"
                }
            }
        )
        
        self._run_step_with_mock_shell_result(step)
        
        updates = self.state_manager.update.call_args[0][1]
        assert len(updates) == 1
        assert updates[0]["operation"] == "set"
        assert updates[0]["value"] == "new_value"

    def test_increment_operation(self):
        """Test increment operation in state updates."""
        step = WorkflowStep(
            id="test_increment",
            type="shell_command",
            definition={
                "command": "echo 'test'",
                "state_update": {
                    "path": "state.counter",
                    "value": 5,
                    "operation": "increment"
                }
            }
        )
        
        self._run_step_with_mock_shell_result(step)
        
        updates = self.state_manager.update.call_args[0][1]
        assert updates[0]["operation"] == "increment"
        assert updates[0]["value"] == 5

    def test_decrement_operation(self):
        """Test decrement operation in state updates."""
        step = WorkflowStep(
            id="test_decrement",
            type="shell_command",
            definition={
                "command": "echo 'test'",
                "state_update": {
                    "path": "state.counter",
                    "value": 2,
                    "operation": "decrement"
                }
            }
        )
        
        self._run_step_with_mock_shell_result(step)
        
        updates = self.state_manager.update.call_args[0][1]
        assert updates[0]["operation"] == "decrement"
        assert updates[0]["value"] == 2

    def test_append_operation(self):
        """Test append operation in state updates."""
        step = WorkflowStep(
            id="test_append",
            type="shell_command",
            definition={
                "command": "echo 'test'",
                "state_update": {
                    "path": "state.items",
                    "value": "new_item",
                    "operation": "append"
                }
            }
        )
        
        self._run_step_with_mock_shell_result(step)
        
        updates = self.state_manager.update.call_args[0][1]
        assert updates[0]["operation"] == "append"
        assert updates[0]["value"] == "new_item"

    def test_multiply_operation(self):
        """Test multiply operation in state updates."""
        step = WorkflowStep(
            id="test_multiply",
            type="shell_command",
            definition={
                "command": "echo 'test'",
                "state_update": {
                    "path": "state.value",
                    "value": 3,
                    "operation": "multiply"
                }
            }
        )
        
        self._run_step_with_mock_shell_result(step)
        
        updates = self.state_manager.update.call_args[0][1]
        assert updates[0]["operation"] == "multiply"
        assert updates[0]["value"] == 3

    def test_multiple_operations_in_state_updates(self):
        """Test multiple different operations in state_updates array."""
        step = WorkflowStep(
            id="test_multiple_ops",
            type="shell_command",
            definition={
                "command": "echo 'test'",
                "state_updates": [
                    {"path": "state.counter", "value": 1, "operation": "increment"},
                    {"path": "state.items", "value": "item1", "operation": "append"},
                    {"path": "state.multiplier", "value": 2, "operation": "multiply"},
                    {"path": "state.status", "value": "completed", "operation": "set"},
                    {"path": "state.attempts", "value": 1, "operation": "decrement"}
                ]
            }
        )
        
        self._run_step_with_mock_shell_result(step)
        
        updates = self.state_manager.update.call_args[0][1]
        assert len(updates) == 5
        
        operations = [u["operation"] for u in updates]
        assert "increment" in operations
        assert "append" in operations
        assert "multiply" in operations
        assert "set" in operations
        assert "decrement" in operations

    def _run_step_with_mock_shell_result(self, step):
        """Helper to run a step with mocked shell command result."""
        self.state_manager.read.return_value = self.default_state
        
        shell_result = {
            "status": "success",
            "output": {"stdout": "test", "stderr": "", "returncode": 0}
        }
        self.processor.shell_command_processor.process.return_value = shell_result
        
        self.processor.process_server_step(self.instance, step, self.queue, {})


class TestErrorHandlingStrategies:
    """Test error handling strategies per step."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = Mock(spec=StateManager)
        self.expression_evaluator = Mock(spec=ExpressionEvaluator)
        self.processor = StepProcessor(self.state_manager, self.expression_evaluator)
        
        self.instance = WorkflowInstance(
            id="test-workflow-id",
            workflow_name="test-workflow",
            definition=Mock(spec=WorkflowDefinition),
            inputs={}
        )
        
        self.queue = Mock(spec=WorkflowQueue)
        self.default_state = {"inputs": {}, "state": {}, "computed": {}}

    def test_shell_command_fail_strategy(self):
        """Test fail error handling strategy for shell commands."""
        step = WorkflowStep(
            id="test_fail",
            type="shell_command",
            definition={
                "command": "false",  # Command that fails
                "error_handling": {"strategy": "fail"}
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        # Mock failed shell command
        shell_result = {
            "status": "failed",
            "error": "Command failed with exit code 1: "
        }
        self.processor.shell_command_processor.process.return_value = shell_result
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        # Check that result contains the shell result
        assert result["executed"] is True
        # Error is in the shell result
        assert result["result"]["status"] == "failed"
        assert "error" in result["result"]

    def test_shell_command_continue_strategy(self):
        """Test continue error handling strategy for shell commands."""
        step = WorkflowStep(
            id="test_continue",
            type="shell_command",
            definition={
                "command": "false",
                "error_handling": {"strategy": "continue"}
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        # Mock shell command with continue strategy
        shell_result = {
            "status": "success",
            "output": {
                "stdout": "",
                "stderr": "",
                "returncode": 1,
                "warning": "Command failed with exit code 1 but continuing due to error_handling strategy"
            }
        }
        self.processor.shell_command_processor.process.return_value = shell_result
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        assert result["executed"] is True
        assert result["result"]["status"] == "success"
        assert "warning" in result["result"]["output"]

    def test_shell_command_fallback_strategy(self):
        """Test fallback error handling strategy for shell commands."""
        step = WorkflowStep(
            id="test_fallback",
            type="shell_command",
            definition={
                "command": "false",
                "error_handling": {
                    "strategy": "fallback",
                    "fallback_value": "default_output"
                }
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        # Mock shell command with fallback strategy
        shell_result = {
            "status": "success",
            "output": {
                "stdout": "default_output",
                "stderr": "",
                "returncode": 0
            }
        }
        self.processor.shell_command_processor.process.return_value = shell_result
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        assert result["executed"] is True
        assert result["result"]["status"] == "success"
        assert result["result"]["output"]["stdout"] == "default_output"

    def test_agent_prompt_with_timeout(self):
        """Test agent prompt with timeout configuration."""
        step = WorkflowStep(
            id="test_timeout",
            type="agent_prompt",
            definition={
                "prompt": "Complex analysis task",
                "timeout": 600,  # 10 minutes
                "max_retries": 2
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        result = self.processor.process_server_step(self.instance, step, self.queue, {})
        
        assert result["definition"]["timeout"] == 600
        assert result["definition"]["max_retries"] == 2

    def test_conditional_with_expression_error(self):
        """Test conditional step with expression evaluation error."""
        step = WorkflowStep(
            id="test_conditional_error",
            type="conditional",
            definition={
                "condition": "{{ invalid.expression }}",
                "then_steps": [{"id": "then1", "type": "user_message", "message": "Success"}]
            }
        )
        
        self.state_manager.read.return_value = self.default_state
        
        # Mock expression evaluation error
        self.expression_evaluator.evaluate.side_effect = Exception("Invalid expression")
        
        result = self.processor.process_conditional(
            self.instance, step, step.definition, self.queue, self.default_state
        )
        
        assert "error" in result
        if isinstance(result["error"], dict):
            assert "Error evaluating condition" in result["error"]["message"]
        else:
            assert "Error evaluating condition" in result["error"]