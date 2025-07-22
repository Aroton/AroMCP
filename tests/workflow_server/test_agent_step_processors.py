"""Tests for agent step processors (agent_prompt and agent_response)."""

import pytest
from unittest.mock import Mock

from aromcp.workflow_server.workflow.steps.agent_prompt import AgentPromptProcessor
from aromcp.workflow_server.workflow.steps.agent_response import AgentResponseProcessor
from aromcp.workflow_server.workflow.models import WorkflowStep


class TestAgentPromptProcessor:
    """Test AgentPromptProcessor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = AgentPromptProcessor()

    def test_basic_agent_prompt_processing(self):
        """Test basic agent prompt processing."""
        step = WorkflowStep(
            id="agent_prompt_1",
            type="agent_prompt",
            definition={
                "prompt": "Analyze the provided code for potential issues",
                "context": {"file_path": "src/main.py", "language": "python"},
                "timeout": 300,
                "max_retries": 3
            }
        )
        
        state = {"inputs.file_path": "src/main.py", "state.analysis_mode": "full"}
        
        result = self.processor.process_agent_prompt(step, state)
        
        assert result["id"] == "agent_prompt_1"
        assert result["type"] == "agent_prompt"
        assert result["definition"]["prompt"] == "Analyze the provided code for potential issues"
        assert result["definition"]["context"]["file_path"] == "src/main.py"
        assert result["definition"]["timeout"] == 300
        assert result["definition"]["max_retries"] == 3

    def test_agent_prompt_with_expected_response(self):
        """Test agent prompt with expected response schema."""
        step = WorkflowStep(
            id="agent_prompt_2",
            type="agent_prompt",
            definition={
                "prompt": "Count the number of functions in the file",
                "expected_response": {
                    "type": "object",
                    "required": ["function_count", "function_names"]
                }
            }
        )
        
        state = {}
        
        result = self.processor.process_agent_prompt(step, state)
        
        assert "expected_response" in result["definition"]
        assert result["definition"]["expected_response"]["type"] == "object"
        assert "function_count" in result["definition"]["expected_response"]["required"]

    def test_agent_prompt_missing_prompt(self):
        """Test agent prompt with missing prompt field."""
        step = WorkflowStep(
            id="agent_prompt_3",
            type="agent_prompt",
            definition={
                "context": {"file_path": "test.py"}
                # Missing required 'prompt' field
            }
        )
        
        state = {}
        
        result = self.processor.process_agent_prompt(step, state)
        
        assert "error" in result
        assert "missing required 'prompt' field" in result["error"]

    def test_agent_prompt_defaults(self):
        """Test agent prompt with default values."""
        step = WorkflowStep(
            id="agent_prompt_4",
            type="agent_prompt",
            definition={
                "prompt": "Simple analysis task"
                # No timeout or max_retries specified
            }
        )
        
        state = {}
        
        result = self.processor.process_agent_prompt(step, state)
        
        assert result["definition"]["timeout"] == 300  # Default 5 minutes
        assert result["definition"]["max_retries"] == 3  # Default retries

    def test_validate_agent_response_valid_object(self):
        """Test validation of valid object response."""
        step = WorkflowStep(
            id="agent_prompt_5",
            type="agent_prompt",
            definition={
                "prompt": "Test",
                "expected_response": {
                    "type": "object",
                    "required": ["status", "count"]
                }
            }
        )
        
        agent_response = {
            "status": "completed",
            "count": 5,
            "details": "analysis finished"
        }
        
        result = self.processor.validate_agent_response(step, agent_response)
        
        assert result["valid"] is True
        assert result["response"] == agent_response

    def test_validate_agent_response_missing_required_field(self):
        """Test validation with missing required field."""
        step = WorkflowStep(
            id="agent_prompt_6",
            type="agent_prompt",
            definition={
                "prompt": "Test",
                "expected_response": {
                    "type": "object",
                    "required": ["status", "count"]
                }
            }
        )
        
        agent_response = {
            "status": "completed"
            # Missing required 'count' field
        }
        
        result = self.processor.validate_agent_response(step, agent_response)
        
        assert result["valid"] is False
        assert "Required field 'count' missing" in result["error"]

    def test_validate_agent_response_wrong_type(self):
        """Test validation with wrong response type."""
        step = WorkflowStep(
            id="agent_prompt_7",
            type="agent_prompt",
            definition={
                "prompt": "Test",
                "expected_response": {
                    "type": "array"
                }
            }
        )
        
        agent_response = "not an array"
        
        result = self.processor.validate_agent_response(step, agent_response)
        
        assert result["valid"] is False
        assert "Expected array response, got str" in result["error"]

    def test_validate_agent_response_no_schema(self):
        """Test validation with no expected response schema."""
        step = WorkflowStep(
            id="agent_prompt_8",
            type="agent_prompt",
            definition={
                "prompt": "Test"
                # No expected_response
            }
        )
        
        agent_response = "any response"
        
        result = self.processor.validate_agent_response(step, agent_response)
        
        assert result["valid"] is True
        assert result["response"] == "any response"


class TestAgentResponseProcessor:
    """Test AgentResponseProcessor functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.processor = AgentResponseProcessor()

    def test_basic_agent_response_processing(self):
        """Test basic agent response processing."""
        step = WorkflowStep(
            id="agent_response_1",
            type="agent_response",
            definition={
                "response_schema": {
                    "type": "object",
                    "required": ["status"]
                },
                "state_updates": [
                    {
                        "path": "state.analysis_result",
                        "value": "response.status",
                        "operation": "set"
                    }
                ]
            }
        )
        
        agent_response = {"status": "completed", "issues": 3}
        state = {"inputs.file": "test.py", "state.counter": 0}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert result["executed"] is True
        assert result["id"] == "agent_response_1"
        assert result["type"] == "agent_response"
        assert result["result"]["status"] == "success"
        assert result["result"]["response_validated"] is True
        assert len(result["state_updates"]) == 1

    def test_agent_response_validation_failure(self):
        """Test agent response with validation failure."""
        step = WorkflowStep(
            id="agent_response_2",
            type="agent_response",
            definition={
                "response_schema": {
                    "type": "object",
                    "required": ["status", "count"]
                },
                "error_handling": {"strategy": "fail"}
            }
        )
        
        agent_response = {"status": "completed"}  # Missing 'count'
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert "error" in result
        assert result["error"]["code"] == "VALIDATION_FAILED"
        assert "Required field 'count' missing" in result["error"]["message"]

    def test_agent_response_continue_on_error(self):
        """Test agent response with continue error handling strategy."""
        step = WorkflowStep(
            id="agent_response_3",
            type="agent_response",
            definition={
                "response_schema": {
                    "type": "object",
                    "required": ["status"]
                },
                "error_handling": {"strategy": "continue"}
            }
        )
        
        agent_response = "invalid response"  # Wrong type
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert result["executed"] is True
        assert result["strategy"] == "continued_on_error"
        assert "validation_error" in result

    def test_agent_response_fallback_strategy(self):
        """Test agent response with fallback error handling strategy."""
        step = WorkflowStep(
            id="agent_response_4",
            type="agent_response",
            definition={
                "response_schema": {
                    "type": "object",
                    "required": ["result"]
                },
                "error_handling": {
                    "strategy": "fallback",
                    "fallback_value": {"result": "default"}
                }
            }
        )
        
        agent_response = "invalid"  # Wrong type
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert result["executed"] is True
        assert result["result"]["status"] == "success"

    def test_agent_response_retry_strategy(self):
        """Test agent response with retry error handling strategy."""
        step = WorkflowStep(
            id="agent_response_5",
            type="agent_response",
            definition={
                "response_schema": {
                    "type": "object",
                    "required": ["data"]
                },
                "error_handling": {
                    "strategy": "retry",
                    "max_retries": 2
                }
            }
        )
        
        agent_response = []  # Wrong type
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert result["executed"] is False
        assert result["strategy"] == "retry_requested"
        assert result["max_retries"] == 2
        assert "validation_error" in result

    def test_state_updates_from_response(self):
        """Test extracting values from response for state updates."""
        step = WorkflowStep(
            id="agent_response_6",
            type="agent_response",
            definition={
                "state_updates": [
                    {
                        "path": "state.result_status",
                        "value": "response.status",
                        "operation": "set"
                    },
                    {
                        "path": "state.issue_count",
                        "value": "response.data.issues",
                        "operation": "set"
                    },
                    {
                        "path": "state.analysis_complete",
                        "value": True,
                        "operation": "set"
                    }
                ]
            }
        )
        
        agent_response = {
            "status": "success",
            "data": {"issues": 3, "warnings": 1},
            "timestamp": "2023-01-01T00:00:00Z"
        }
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert len(result["state_updates"]) == 3
        
        # Check extracted values
        updates = {u["path"]: u["value"] for u in result["state_updates"]}
        assert updates["state.result_status"] == "success"
        assert updates["state.issue_count"] == 3
        assert updates["state.analysis_complete"] is True

    def test_store_full_response(self):
        """Test storing full response in state."""
        step = WorkflowStep(
            id="agent_response_7",
            type="agent_response",
            definition={
                "store_response": "state.full_agent_response"
            }
        )
        
        agent_response = {"data": "test", "metadata": {"version": "1.0"}}
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert len(result["state_updates"]) == 1
        update = result["state_updates"][0]
        assert update["path"] == "state.full_agent_response"
        assert update["value"] == agent_response
        assert update["operation"] == "set"

    def test_state_update_extraction_error(self):
        """Test error handling when state update extraction fails."""
        step = WorkflowStep(
            id="agent_response_8",
            type="agent_response",
            definition={
                "state_updates": [
                    {
                        "path": "state.value",
                        "value": "response.nonexistent.field",
                        "operation": "set"
                    }
                ],
                "error_handling": {"strategy": "fail"}
            }
        )
        
        agent_response = {"status": "success"}
        state = {}
        
        result = self.processor.process_agent_response(step, agent_response, state)
        
        assert "error" in result
        assert result["error"]["code"] == "STATE_UPDATE_FAILED"

    def test_nested_value_extraction(self):
        """Test the _get_nested_value utility method."""
        data = {
            "level1": {
                "level2": {
                    "target": "found"
                }
            },
            "array": [1, 2, 3]
        }
        
        # Test successful extraction
        result = self.processor._get_nested_value(data, "level1.level2.target")
        assert result == "found"
        
        # Test accessing top-level
        result = self.processor._get_nested_value(data, "array")
        assert result == [1, 2, 3]
        
        # Test non-existent path
        with pytest.raises(KeyError):
            self.processor._get_nested_value(data, "level1.nonexistent")
        
        # Test accessing key on non-dict
        with pytest.raises(KeyError):
            self.processor._get_nested_value(data, "array.length")

    def test_response_validation_against_schema(self):
        """Test response validation against different schema types."""
        # String response
        result = self.processor._validate_against_schema("test", {"type": "string"})
        assert result["valid"] is True
        
        # Number response
        result = self.processor._validate_against_schema(42, {"type": "number"})
        assert result["valid"] is True
        
        # Boolean response
        result = self.processor._validate_against_schema(True, {"type": "boolean"})
        assert result["valid"] is True
        
        # Array response
        result = self.processor._validate_against_schema([1, 2, 3], {"type": "array"})
        assert result["valid"] is True
        
        # Invalid type
        result = self.processor._validate_against_schema("not a number", {"type": "number"})
        assert result["valid"] is False
        assert "Expected number, got str" in result["error"]