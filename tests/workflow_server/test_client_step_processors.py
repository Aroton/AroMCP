"""Tests for client-side step processors (user_input, user_message, mcp_call, parallel_foreach)."""

import pytest
from unittest.mock import Mock, MagicMock

from aromcp.workflow_server.workflow.steps.user_message import UserMessageProcessor, UserInputProcessor as UserInputProcessorStatic
from aromcp.workflow_server.workflow.steps.mcp_call import MCPCallProcessor
from aromcp.workflow_server.workflow.parallel import ParallelForEachProcessor, ParallelForEachStep
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.models import WorkflowStep


class TestUserMessageProcessor:
    """Test UserMessageProcessor functionality."""

    def test_basic_user_message_processing(self):
        """Test basic user message processing."""
        step_definition = {
            "message": "Please review the analysis results",
            "message_type": "info",
            "format": "text"
        }
        
        result = UserMessageProcessor.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_message"
        assert result["agent_action"]["message"] == "Please review the analysis results"
        assert result["agent_action"]["message_type"] == "info"
        assert result["agent_action"]["format"] == "text"

    def test_user_message_with_title(self):
        """Test user message with title."""
        step_definition = {
            "message": "Analysis complete",
            "title": "Results Summary",
            "type": "success"  # Using 'type' field as per implementation
        }
        
        result = UserMessageProcessor.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "success"
        assert result["agent_action"]["title"] == "Results Summary"
        assert result["agent_action"]["message_type"] == "success"

    def test_user_message_missing_message(self):
        """Test user message with missing message field."""
        step_definition = {
            "type": "error"
            # Missing required 'message' field
        }
        
        result = UserMessageProcessor.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "failed"
        assert "Missing 'message'" in result["error"]

    def test_user_message_defaults(self):
        """Test user message with default values."""
        step_definition = {
            "message": "Simple message"
            # No message_type or format specified
        }
        
        result = UserMessageProcessor.process(step_definition, "workflow_123", None)
        
        assert result["agent_action"]["message_type"] == "info"  # Default type
        assert result["agent_action"]["format"] == "text"  # Default format


class TestUserInputProcessorStatic:
    """Test UserInputProcessor (static version) functionality."""

    def test_basic_user_input_processing(self):
        """Test basic user input processing."""
        step_definition = {
            "prompt": "Enter your name:",
            "input_type": "text",
            "required": True
        }
        
        result = UserInputProcessorStatic.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["prompt"] == "Enter your name:"
        assert result["agent_action"]["input_type"] == "text"
        assert result["agent_action"]["required"] is True

    def test_user_input_with_choices(self):
        """Test user input with choices."""
        step_definition = {
            "prompt": "Select an option:",
            "input_type": "choice",
            "choices": ["option1", "option2", "option3"],
            "default": "option1"
        }
        
        result = UserInputProcessorStatic.process(step_definition, "workflow_123", None)
        
        assert result["agent_action"]["choices"] == ["option1", "option2", "option3"]
        assert result["agent_action"]["default"] == "option1"

    def test_user_input_with_state_update(self):
        """Test user input with state update configuration."""
        step_definition = {
            "prompt": "Enter value:",
            "state_update": {
                "path": "state.user_input",
                "operation": "set"
            }
        }
        
        result = UserInputProcessorStatic.process(step_definition, "workflow_123", None)
        
        assert "state_update" in result["agent_action"]
        assert result["agent_action"]["state_update"]["path"] == "state.user_input"

    def test_user_input_missing_prompt(self):
        """Test user input with missing prompt field."""
        step_definition = {
            "input_type": "text"
            # Missing required 'prompt' field
        }
        
        result = UserInputProcessorStatic.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "failed"
        assert "Missing 'prompt'" in result["error"]

    def test_user_input_defaults(self):
        """Test user input with default values."""
        step_definition = {
            "prompt": "Enter something:"
            # No input_type or required specified
        }
        
        result = UserInputProcessorStatic.process(step_definition, "workflow_123", None)
        
        assert result["agent_action"]["input_type"] == "text"  # Default type
        assert result["agent_action"]["required"] is True  # Default required


class TestMCPCallProcessor:
    """Test MCPCallProcessor functionality."""

    def test_basic_mcp_call_processing(self):
        """Test basic MCP call processing."""
        step_definition = {
            "tool": "read_files",
            "parameters": {
                "file_paths": ["src/main.py"],
                "project_root": "/project"
            }
        }
        
        result = MCPCallProcessor.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "mcp_call"
        assert result["agent_action"]["tool"] == "read_files"
        assert result["agent_action"]["parameters"]["file_paths"] == ["src/main.py"]

    def test_mcp_call_with_state_update(self):
        """Test MCP call with state update configuration."""
        step_definition = {
            "tool": "lint_project",
            "parameters": {"project_root": "/project"},
            "state_update": {
                "path": "state.lint_results",
                "value": "response.result",
                "operation": "set"
            }
        }
        
        result = MCPCallProcessor.process(step_definition, "workflow_123", None)
        
        assert "state_update" in result["agent_action"]
        assert result["agent_action"]["state_update"]["path"] == "state.lint_results"

    def test_mcp_call_no_parameters(self):
        """Test MCP call without parameters."""
        step_definition = {
            "tool": "workflow_status"
            # No parameters provided - should use empty dict
        }
        
        result = MCPCallProcessor.process(step_definition, "workflow_123", None)
        
        assert result["agent_action"]["parameters"] == {}

    def test_mcp_call_missing_tool(self):
        """Test MCP call with missing tool field."""
        step_definition = {
            "parameters": {"key": "value"}
            # Missing required 'tool' field
        }
        
        result = MCPCallProcessor.process(step_definition, "workflow_123", None)
        
        assert result["status"] == "failed"
        assert "Missing 'tool'" in result["error"]


class TestParallelForEachProcessor:
    """Test ParallelForEachProcessor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.expression_evaluator = Mock()
        self.processor = ParallelForEachProcessor(self.expression_evaluator)

    def test_basic_parallel_foreach_processing(self):
        """Test basic parallel foreach processing."""
        step_def = ParallelForEachStep(
            items="state.file_list",
            sub_agent_task="analyze_file",
            max_parallel=3
        )
        
        # Mock expression evaluator to return file list
        self.expression_evaluator.evaluate.return_value = ["file1.py", "file2.py", "file3.py"]
        
        state = {"state.file_list": ["file1.py", "file2.py", "file3.py"]}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_1", "workflow_123")
        
        assert "step" in result
        assert result["step"]["type"] == "parallel_tasks"
        assert result["step"]["definition"]["max_parallel"] == 3
        assert result["step"]["definition"]["sub_agent_task"] == "analyze_file"
        assert len(result["step"]["definition"]["tasks"]) == 3

    def test_parallel_foreach_task_context(self):
        """Test parallel foreach task context creation."""
        step_def = ParallelForEachStep(
            items="inputs.targets",
            sub_agent_task="process_target"
        )
        
        self.expression_evaluator.evaluate.return_value = ["target_a", "target_b"]
        
        state = {"inputs.targets": ["target_a", "target_b"]}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_2", "workflow_456")
        
        tasks = result["step"]["definition"]["tasks"]
        
        # Check first task context
        assert tasks[0]["context"]["item"] == "target_a"
        assert tasks[0]["context"]["index"] == 0
        assert tasks[0]["context"]["total"] == 2
        
        # Check second task context
        assert tasks[1]["context"]["item"] == "target_b"
        assert tasks[1]["context"]["index"] == 1
        assert tasks[1]["context"]["total"] == 2

    def test_parallel_foreach_with_prompt_override(self):
        """Test parallel foreach with sub-agent prompt override."""
        step_def = ParallelForEachStep(
            items="data.items",
            sub_agent_task="custom_task",
            sub_agent_prompt_override="Analyze this item carefully"
        )
        
        self.expression_evaluator.evaluate.return_value = ["item1"]
        
        state = {"data.items": ["item1"]}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_3", "workflow_789")
        
        tasks = result["step"]["definition"]["tasks"]
        assert tasks[0]["sub_agent_prompt"] == "Analyze this item carefully"

    def test_parallel_foreach_invalid_items_expression(self):
        """Test parallel foreach with invalid items expression."""
        step_def = ParallelForEachStep(
            items="invalid.expression",
            sub_agent_task="test_task"
        )
        
        # Mock expression evaluator to raise exception
        self.expression_evaluator.evaluate.side_effect = Exception("Invalid expression")
        
        state = {}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_4", "workflow_error")
        
        assert "error" in result
        assert "Failed to evaluate items expression" in result["error"]

    def test_parallel_foreach_non_list_items(self):
        """Test parallel foreach when items expression returns non-list."""
        step_def = ParallelForEachStep(
            items="state.single_value",
            sub_agent_task="process"
        )
        
        # Mock expression evaluator to return non-list
        self.expression_evaluator.evaluate.return_value = "not_a_list"
        
        state = {"state.single_value": "not_a_list"}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_5", "workflow_type_error")
        
        assert "error" in result
        assert "Items expression must return array" in result["error"]

    def test_parallel_foreach_empty_items(self):
        """Test parallel foreach with empty items list."""
        step_def = ParallelForEachStep(
            items="state.empty_list",
            sub_agent_task="process_empty"
        )
        
        self.expression_evaluator.evaluate.return_value = []
        
        state = {"state.empty_list": []}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_6", "workflow_empty")
        
        assert "step" in result
        assert len(result["step"]["definition"]["tasks"]) == 0

    def test_parallel_execution_tracking(self):
        """Test parallel execution state tracking."""
        step_def = ParallelForEachStep(
            items="data.items",
            sub_agent_task="track_test"
        )
        
        self.expression_evaluator.evaluate.return_value = ["item1", "item2"]
        
        state = {"data.items": ["item1", "item2"]}
        
        result = self.processor.process_parallel_foreach(step_def, state, "step_7", "workflow_track")
        
        execution_id = result["step"]["definition"]["execution_id"]
        
        # Verify execution is tracked
        execution = self.processor.get_execution(execution_id)
        assert execution is not None
        assert execution.workflow_id == "workflow_track"
        assert execution.parent_step_id == "step_7"
        assert len(execution.tasks) == 2

    def test_task_status_updates(self):
        """Test updating task status in parallel execution."""
        step_def = ParallelForEachStep(
            items="test.data",
            sub_agent_task="status_test"
        )
        
        self.expression_evaluator.evaluate.return_value = ["task1"]
        
        result = self.processor.process_parallel_foreach(step_def, {}, "step_8", "workflow_status")
        
        execution_id = result["step"]["definition"]["execution_id"]
        task_id = result["step"]["definition"]["tasks"][0]["task_id"]
        
        # Update task to running
        success = self.processor.update_task_status(execution_id, task_id, "running")
        assert success is True
        
        execution = self.processor.get_execution(execution_id)
        assert execution.tasks[0].status == "running"
        assert execution.status == "running"
        
        # Update task to completed
        success = self.processor.update_task_status(execution_id, task_id, "completed", result={"success": True})
        assert success is True
        
        execution = self.processor.get_execution(execution_id)
        assert execution.tasks[0].status == "completed"
        assert execution.is_complete is True

    def test_get_next_available_tasks(self):
        """Test getting next available tasks with parallel limits."""
        step_def = ParallelForEachStep(
            items="test.items",
            sub_agent_task="limit_test",
            max_parallel=2
        )
        
        self.expression_evaluator.evaluate.return_value = ["task1", "task2", "task3", "task4"]
        
        result = self.processor.process_parallel_foreach(step_def, {}, "step_9", "workflow_limit")
        
        execution_id = result["step"]["definition"]["execution_id"]
        
        # Get next available tasks (should respect max_parallel=2)
        available_tasks = self.processor.get_next_available_tasks(execution_id)
        assert len(available_tasks) == 2
        
        # Mark two tasks as running
        for task in available_tasks:
            self.processor.update_task_status(execution_id, task.task_id, "running")
        
        # Should have no more available tasks
        available_tasks = self.processor.get_next_available_tasks(execution_id)
        assert len(available_tasks) == 0
        
        # Complete one task
        task_id = result["step"]["definition"]["tasks"][0]["task_id"]
        self.processor.update_task_status(execution_id, task_id, "completed")
        
        # Should have one more available task
        available_tasks = self.processor.get_next_available_tasks(execution_id)
        assert len(available_tasks) == 1

    def test_execution_cleanup(self):
        """Test cleaning up completed executions."""
        step_def = ParallelForEachStep(
            items="cleanup.test",
            sub_agent_task="cleanup_task"
        )
        
        self.expression_evaluator.evaluate.return_value = ["single_task"]
        
        result = self.processor.process_parallel_foreach(step_def, {}, "step_10", "workflow_cleanup")
        
        execution_id = result["step"]["definition"]["execution_id"]
        task_id = result["step"]["definition"]["tasks"][0]["task_id"]
        
        # Complete the task
        self.processor.update_task_status(execution_id, task_id, "completed")
        
        # Verify execution exists and is complete
        execution = self.processor.get_execution(execution_id)
        assert execution.is_complete is True
        
        # Clean up execution
        cleaned = self.processor.cleanup_execution(execution_id)
        assert cleaned is True
        
        # Verify execution is removed
        execution = self.processor.get_execution(execution_id)
        assert execution is None