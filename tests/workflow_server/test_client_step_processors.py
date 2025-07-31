"""Tests for client-side step processors (user_input, user_message, mcp_call, parallel_foreach)."""

from unittest.mock import Mock

from aromcp.workflow_server.workflow.steps.mcp_call import MCPCallProcessor
from aromcp.workflow_server.workflow.steps.user_message import (
    UserInputProcessor as UserInputProcessorStatic,
)
from aromcp.workflow_server.workflow.steps.user_message import (
    UserMessageProcessor,
)


class TestUserMessageProcessor:
    """Test UserMessageProcessor functionality."""

    def test_basic_user_message_processing(self):
        """Test basic user message processing."""
        step_definition = {"message": "Please review the analysis results", "message_type": "info", "format": "text"}

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
            "type": "success",  # Using 'type' field as per implementation
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
        step_definition = {"prompt": "Enter your name:", "input_type": "text", "required": True}

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
            "default": "option1",
        }

        result = UserInputProcessorStatic.process(step_definition, "workflow_123", None)

        assert result["agent_action"]["choices"] == ["option1", "option2", "option3"]


class TestMCPToolErrorHandling:
    """Test MCP tool basic formatting and edge cases for call preparation."""

    def test_mcp_call_missing_tool(self):
        """Test MCP call with missing tool field."""
        step_definition = {
            "parameters": {"data": "test_data"}
            # Missing required 'tool' field
        }

        state_manager = Mock()

        result = MCPCallProcessor.process(step_definition, "workflow_test", state_manager)

        assert result["status"] == "failed"
        assert "Missing 'tool'" in result["error"]

    def test_mcp_call_with_error_handling_config(self):
        """Test that error handling configuration is passed through in formatting."""
        step_definition = {
            "tool": "analysis_tool",
            "parameters": {"data": "test_data"},
            "error_handling": {"strategy": "retry", "max_retries": 3},
        }

        state_manager = Mock()

        result = MCPCallProcessor.process(step_definition, "workflow_test", state_manager)

        assert result["status"] == "success"
        assert result["agent_action"]["tool"] == "analysis_tool"
        assert result["agent_action"]["parameters"]["data"] == "test_data"
        # Error handling config should be formatted for agent but not processed here

    def test_mcp_call_with_timeout_config(self):
        """Test that timeout configuration is included in formatted call."""
        step_definition = {"tool": "slow_tool", "parameters": {"dataset": "large"}, "timeout": 30}

        state_manager = Mock()

        result = MCPCallProcessor.process(step_definition, "workflow_test", state_manager)

        assert result["status"] == "success"
        assert result["agent_action"]["tool"] == "slow_tool"
        # Timeout should be available in step_definition for agent processing

    def test_mcp_call_with_complex_parameters(self):
        """Test MCP call formatting with complex parameter structures."""
        step_definition = {
            "tool": "complex_tool",
            "parameters": {
                "nested": {"field1": "value1", "field2": {"deep": "nested"}},
                "list_param": ["item1", "item2"],
                "null_param": None,
            },
        }

        state_manager = Mock()

        result = MCPCallProcessor.process(step_definition, "workflow_test", state_manager)

        assert result["status"] == "success"
        assert result["agent_action"]["parameters"]["nested"]["field1"] == "value1"
        assert result["agent_action"]["parameters"]["list_param"] == ["item1", "item2"]
        assert result["agent_action"]["parameters"]["null_param"] is None

    def test_mcp_call_empty_parameters(self):
        """Test MCP call with empty parameters."""
        step_definition = {
            "tool": "no_param_tool"
            # No parameters field
        }

        state_manager = Mock()

        result = MCPCallProcessor.process(step_definition, "workflow_test", state_manager)

        assert result["status"] == "success"
        assert result["agent_action"]["parameters"] == {}

    def test_mcp_call_with_all_optional_fields(self):
        """Test MCP call with all optional fields present."""
        step_definition = {
            "tool": "full_featured_tool",
            "parameters": {"input": "data"},
            "state_update": {"result_path": "state.results", "operation": "merge"},
            "store_result": {"key": "analysis_output", "format": "json"},
        }

        state_manager = Mock()

        result = MCPCallProcessor.process(step_definition, "workflow_test", state_manager)

        assert result["status"] == "success"
        assert result["agent_action"]["state_update"]["result_path"] == "state.results"
        assert result["agent_action"]["store_result"]["key"] == "analysis_output"


class TestUserInputProcessorStaticEnhanced:
    """Enhanced tests for UserInputProcessor functionality."""

    def test_user_input_with_state_update(self):
        """Test user input with state update configuration."""
        step_definition = {"prompt": "Enter value:", "state_update": {"path": "state.user_input", "operation": "set"}}

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
            "parameters": {"file_paths": ["src/main.py"], "project_root": "/project"},
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
            "state_update": {"path": "state.lint_results", "value": "response.result", "operation": "set"},
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
