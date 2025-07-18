"""Tests for the WorkflowValidator class."""

import pytest

from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestWorkflowValidator:
    """Test the WorkflowValidator functionality."""

    def test_valid_operations(self):
        """Test validation of state update operations."""
        workflow = {
            "name": "test:operations",
            "description": "Test operations",
            "version": "1.0.0",
            "steps": [
                {"type": "state_update", "path": "raw.value", "value": 1, "operation": "set"},
                {"type": "state_update", "path": "raw.value", "value": 1, "operation": "increment"},
                {"type": "state_update", "path": "raw.value", "value": 1, "operation": "invalid_op"},
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("invalid operation: invalid_op" in error for error in validator.errors)

    def test_input_validation(self):
        """Test validation of input parameters."""
        workflow = {
            "name": "test:inputs",
            "description": "Test inputs",
            "version": "1.0.0",
            "inputs": {
                "valid_string": {"type": "string"},
                "valid_number": {"type": "number", "required": False},
                "invalid_type": {"type": "invalid"},
                "bad_required": {"type": "string", "required": "yes"},  # Should be boolean
            },
            "steps": [],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("invalid type: invalid" in error for error in validator.errors)
        assert any("required field must be boolean" in error for error in validator.errors)

    def test_nested_step_validation(self):
        """Test validation of nested steps in conditionals and loops."""
        workflow = {
            "name": "test:nested",
            "description": "Test nested steps",
            "version": "1.0.0",
            "steps": [
                {
                    "type": "conditional",
                    "condition": "true",
                    "then_steps": [{"type": "invalid_step_type"}, {"type": "user_message", "message": "valid"}],
                    "else_steps": "not_an_array",  # Should be array
                },
                {
                    "type": "while_loop",
                    "condition": "true",
                    "body": [{"type": "state_update"}],  # Missing required fields
                },
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("invalid type: invalid_step_type" in error for error in validator.errors)
        assert any("else_steps must be an array" in error for error in validator.errors)
        assert any("missing 'path' field" in error for error in validator.errors)

    def test_computed_field_validation(self):
        """Test validation of computed state fields."""
        workflow = {
            "name": "test:computed",
            "description": "Test computed fields",
            "version": "1.0.0",
            "state_schema": {
                "computed": {
                    "valid_field": {"from": "raw.value", "transform": "input * 2"},
                    "missing_from": {"transform": "input"},
                    "missing_transform": {"from": "raw.value"},
                    "invalid_error_handler": {"from": "raw.value", "transform": "input", "on_error": "invalid_handler"},
                    "not_an_object": "simple_string",
                }
            },
            "steps": [],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("missing 'from' property" in error for error in validator.errors)
        assert any("missing 'transform' property" in error for error in validator.errors)
        assert any("invalid on_error value" in error for error in validator.errors)
        assert any("must be an object" in error for error in validator.errors)

    def test_sub_agent_task_validation(self):
        """Test validation of sub-agent tasks."""
        workflow = {
            "name": "test:sub-agent",
            "description": "Test sub-agent tasks",
            "version": "1.0.0",
            "steps": [{"type": "parallel_foreach", "items": "{{ items }}", "sub_agent_task": "process_item"}],
            "sub_agent_tasks": {
                "process_item": {"prompt_template": "Process {{ item }}"},
                "missing_prompt": {"description": "This task has no prompt"},
                "not_an_object": "invalid",
            },
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("missing prompt_template" in error for error in validator.errors)
        assert any("must be an object" in error for error in validator.errors)
        assert len(validator.warnings) > 0  # Should warn about missing description

    def test_config_validation(self):
        """Test validation of workflow configuration."""
        workflow = {
            "name": "test:config",
            "description": "Test config",
            "version": "1.0.0",
            "config": {
                "timeout_seconds": -10,  # Should be positive
                "max_retries": 3.5,  # Should be integer
            },
            "steps": [],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("timeout_seconds must be a positive number" in error for error in validator.errors)
        assert any("max_retries must be a non-negative integer" in error for error in validator.errors)

    def test_get_validation_error_message(self):
        """Test formatted error message generation."""
        workflow = {
            "name": "test",  # Missing namespace
            "description": "Test",
            "version": "not.semantic",  # Bad version
            "steps": [{"type": "invalid_step"}],  # Add an error, not just warnings
        }

        validator = WorkflowValidator()
        validator.validate(workflow)

        error_msg = validator.get_validation_error()
        assert "Workflow validation failed:" in error_msg
        assert "Warnings:" in error_msg
        assert "namespace:name" in error_msg
        assert "semantic versioning" in error_msg

    def test_user_message_type_overloading(self):
        """Test that user_message steps handle type field correctly."""
        workflow = {
            "name": "test:message-types",
            "description": "Test message types",
            "version": "1.0.0",
            "steps": [
                # Valid: no message type
                {"type": "user_message", "message": "Hello"},
                # Valid: message_type field
                {"type": "user_message", "message": "Warning", "message_type": "warning"},
                # Invalid: bad message type
                {"type": "user_message", "message": "Bad", "message_type": "invalid_type"},
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        errors = validator.errors
        assert len(errors) == 1
        assert "invalid message type: invalid_type" in errors[0]

    def test_special_step_types(self):
        """Test validation of special step types."""
        workflow = {
            "name": "test:special-steps",
            "description": "Test special steps",
            "version": "1.0.0",
            "steps": [
                {"type": "break"},  # Valid in loops
                {"type": "continue"},  # Valid in loops
                {
                    "type": "batch_state_update",
                    "updates": [{"path": "raw.a", "value": 1}, {"path": "raw.b", "value": 2}],
                },
                {"type": "agent_shell_command", "command": "ls -la", "reason": "List files"},
                {"type": "internal_mcp_call", "tool": "internal_tool", "parameters": {}},
                {"type": "conditional_message", "condition": "{{ flag }}", "message": "Flag is set"},
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is True
        assert len(validator.errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
