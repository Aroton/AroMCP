"""Tests for the workflow step registry.

Tests step type validation, deprecated step type handling, and schema compliance.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.aromcp.workflow_server.workflow.step_registry import StepRegistry, STEP_TYPES


class TestStepRegistry:
    """Test the StepRegistry class and its validation functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = StepRegistry()

    def test_all_required_step_types_exist(self):
        """Test that all required step types from schema are included."""
        required_step_types = [
            "user_message",
            "mcp_call", 
            "user_input",
            "agent_prompt",
            "agent_response",
            "parallel_foreach",
            "shell_command",
            "conditional",
            "while_loop",
            "foreach",
            "break",
            "continue"
        ]
        
        for step_type in required_step_types:
            config = self.registry.get(step_type)
            assert config is not None, f"Required step type '{step_type}' not found in registry"

    def test_deprecated_step_types_removed(self):
        """Test that deprecated step types are removed from registry."""
        deprecated_step_types = ["state_update", "batch_state_update"]
        
        for step_type in deprecated_step_types:
            config = self.registry.get(step_type)
            assert config is None, f"Deprecated step type '{step_type}' should not be in registry"

    def test_deprecated_step_type_detection(self):
        """Test that deprecated step types are correctly identified."""
        assert self.registry.is_deprecated_step_type("state_update")
        assert self.registry.is_deprecated_step_type("batch_state_update")
        assert not self.registry.is_deprecated_step_type("user_message")
        assert not self.registry.is_deprecated_step_type("mcp_call")

    def test_deprecated_step_type_suggestions(self):
        """Test that deprecated step types provide helpful replacement suggestions."""
        suggestion = self.registry.suggest_replacement_for_deprecated("state_update")
        assert "state_update" in suggestion
        assert "field" in suggestion
        
        suggestion = self.registry.suggest_replacement_for_deprecated("batch_state_update")
        assert "state_updates" in suggestion
        assert "agent_response" in suggestion
        
        # Non-deprecated type should return None
        suggestion = self.registry.suggest_replacement_for_deprecated("user_message")
        assert suggestion is None

    def test_validate_deprecated_step_types(self):
        """Test that validation fails for deprecated step types with helpful messages."""
        # Test state_update step
        step = {"id": "test", "type": "state_update", "path": "state.count", "value": "1"}
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "deprecated and removed" in error_message
        assert "state_update" in error_message
        
        # Test batch_state_update step
        step = {"id": "test", "type": "batch_state_update", "updates": []}
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "deprecated and removed" in error_message
        assert "agent_response" in error_message

    def test_execution_context_validation(self):
        """Test that execution_context is only allowed on shell_command steps."""
        # Valid: shell_command with execution_context
        step = {
            "id": "test_shell",
            "type": "shell_command",
            "command": "echo test",
            "execution_context": "client"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert is_valid, f"Should be valid: {error_message}"
        
        # Invalid: execution_context on non-shell_command step
        step = {
            "id": "test_user",
            "type": "user_message",
            "message": "Hello",
            "execution_context": "client"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "execution_context" in error_message
        assert "only allowed on 'shell_command'" in error_message

    def test_execution_context_values(self):
        """Test that execution_context accepts only valid values."""
        # Valid values
        for context in ["client", "server"]:
            step = {
                "id": "test_shell",
                "type": "shell_command", 
                "command": "echo test",
                "execution_context": context
            }
            is_valid, error_message = self.registry.validate_step(step)
            assert is_valid, f"Should accept '{context}': {error_message}"
        
        # Invalid value
        step = {
            "id": "test_shell",
            "type": "shell_command",
            "command": "echo test", 
            "execution_context": "invalid"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "Invalid execution_context" in error_message
        assert "client" in error_message and "server" in error_message

    def test_required_fields_validation(self):
        """Test that required fields are properly validated."""
        # Missing required field
        step = {"id": "test", "type": "user_message"}  # Missing 'message'
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "missing required field" in error_message
        assert "message" in error_message
        
        # All required fields present
        step = {"id": "test", "type": "user_message", "message": "Hello"}
        is_valid, error_message = self.registry.validate_step(step)
        assert is_valid

    def test_optional_fields_validation(self):
        """Test that optional fields are properly handled."""
        # Test mcp_call with optional fields
        step = {
            "id": "test_mcp",
            "type": "mcp_call",
            "tool": "test_tool",
            "parameters": {"key": "value"},
            "state_update": {"path": "state.result", "value": "{{ result }}"},
            "timeout": 30,
            "error_handling": {"strategy": "retry"}
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert is_valid, f"Should accept optional fields: {error_message}"

    def test_unknown_fields_validation(self):
        """Test that unknown fields are rejected."""
        step = {
            "id": "test",
            "type": "user_message",
            "message": "Hello",
            "unknown_field": "should_fail"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "unknown field" in error_message
        assert "unknown_field" in error_message

    def test_step_categorization(self):
        """Test step categorization methods."""
        # Client steps
        assert self.registry.is_client_step("user_message")
        assert self.registry.is_client_step("mcp_call")
        assert self.registry.is_client_step("agent_prompt")
        assert self.registry.is_client_step("agent_response")
        
        # Server steps
        assert self.registry.is_server_step("shell_command")
        assert self.registry.is_server_step("conditional")
        assert self.registry.is_server_step("while_loop")
        
        # Control flow steps
        assert self.registry.is_control_flow("conditional")
        assert self.registry.is_control_flow("while_loop") 
        assert self.registry.is_control_flow("foreach")
        assert not self.registry.is_control_flow("user_message")
        
        # Batchable steps
        assert self.registry.is_batchable("user_message")
        assert not self.registry.is_batchable("mcp_call")

    def test_step_configuration_completeness(self):
        """Test that all step configurations have required properties."""
        for step_type, config in STEP_TYPES.items():
            # Check required config properties
            assert "execution" in config
            assert "queuing" in config
            assert "description" in config
            assert "supports_state_update" in config
            assert "required_fields" in config
            assert "optional_fields" in config
            
            # Check value types
            assert config["execution"] in ["client", "server"]
            assert config["queuing"] in ["batch", "blocking", "immediate", "expand"]
            assert isinstance(config["description"], str)
            assert isinstance(config["supports_state_update"], bool)
            assert isinstance(config["required_fields"], list)
            assert isinstance(config["optional_fields"], list)

    def test_schema_compliance_field_mappings(self):
        """Test that step configurations match schema field requirements."""
        # Test parallel_foreach has timeout_seconds option
        parallel_config = self.registry.get("parallel_foreach")
        assert "timeout_seconds" in parallel_config["optional_fields"]
        
        # Test foreach has variable_name option
        foreach_config = self.registry.get("foreach")
        assert "variable_name" in foreach_config["optional_fields"]
        
        # Test shell_command supports execution_context
        shell_config = self.registry.get("shell_command")
        assert "execution_context" in shell_config["optional_fields"]

    def test_step_type_listing(self):
        """Test methods that list step types."""
        all_types = self.registry.get_all_valid_step_types()
        assert len(all_types) == 12  # All 12 required step types
        assert "user_message" in all_types
        assert "state_update" not in all_types  # Deprecated
        
        deprecated_types = self.registry.get_deprecated_step_types()
        assert len(deprecated_types) == 2
        assert "state_update" in deprecated_types
        assert "batch_state_update" in deprecated_types

    def test_complex_step_validation(self):
        """Test validation of complex step configurations."""
        # Test agent_response with multiple optional fields
        step = {
            "id": "process_response",
            "type": "agent_response",
            "response_schema": {"type": "object", "required": ["status"]},
            "state_updates": [
                {"path": "state.status", "value": "{{ response.status }}"},
                {"path": "state.processed", "value": True}
            ],
            "store_response": "state.last_response",
            "validation": {"min_length": 5},
            "error_handling": {"strategy": "retry", "max_retries": 3}
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert is_valid, f"Complex agent_response should be valid: {error_message}"
        
        # Test while_loop step
        step = {
            "id": "retry_loop",
            "type": "while_loop",
            "condition": "state.attempt_count < 3",
            "body": [
                {"id": "attempt", "type": "user_message", "message": "Attempting..."}
            ],
            "max_iterations": 5
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert is_valid, f"Complex while_loop should be valid: {error_message}"

    def test_step_missing_type(self):
        """Test validation when step is missing type field."""
        step = {"id": "test", "message": "Hello"}  # Missing type
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "missing 'type' field" in error_message

    def test_unknown_step_type(self):
        """Test validation for unknown step types."""
        step = {"id": "test", "type": "unknown_step_type"}
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "Unknown step type" in error_message
        assert "unknown_step_type" in error_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])