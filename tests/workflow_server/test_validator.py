"""
Test suite for Validation Error Recovery - Acceptance Criteria 8.3

This file tests the following acceptance criteria:
- AC 8.3: Validation Error Recovery - recovery and reporting for validation failures
- AC 1.1: Schema Compliance - step validation against step registry requirements
- Workflow validation with clear error messages and context tracking

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

import pytest

from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestWorkflowValidator:
    """Test the WorkflowValidator functionality."""

    def test_valid_operations(self):
        """Test validation of state update operations in embedded state_update fields."""
        # This test now validates that embedded state_update fields work properly
        # and that invalid operations are caught
        workflow = {
            "name": "test:operations",
            "description": "Test operations",
            "version": "1.0.0",
            "default_state": {
                "state": {"value": 0}
            },
            "steps": [
                {"id": "valid1", "type": "shell_command", "command": "echo test", "state_update": {"path": "state.value", "value": "1"}},
                {"id": "valid2", "type": "shell_command", "command": "echo test", "state_update": {"path": "state.value", "value": "1", "operation": "increment"}},
                {"id": "invalid", "type": "shell_command", "command": "echo test", "state_update": {"path": "state.value", "value": "1", "operation": "invalid_op"}},
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        
        # Should fail due to invalid operation
        assert result is False
        # Check that it fails due to invalid operation
        assert any("invalid_op" in str(error) for error in validator.errors)
        # Verify validation error recovery structure
        assert len(validator.errors) > 0, "Should have validation errors"
        # Verify error structure format
        for error in validator.errors:
            assert isinstance(error, str) and len(error) > 0, "Errors should be non-empty strings"

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
        # Verify validation error recovery provides clear context
        assert len(validator.errors) >= 2, "Should have multiple specific validation errors"
        # Verify error message structure provides field-level details
        error_messages = [str(e) for e in validator.errors]
        assert any("type" in msg for msg in error_messages), "Should include field context"

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
                    "body": [{"type": "state_update"}],  # Invalid step type
                },
            ],
        }

        validator = WorkflowValidator()
        # Disable schema validation for this test since it tests invalid step types
        validator.schema = None
        result = validator.validate(workflow)
        assert result is False
        assert any("invalid type: invalid_step_type" in error for error in validator.errors)
        assert any("else_steps must be an array" in error for error in validator.errors)
        # shell_command with state_update is not a valid step type
        assert any("invalid type: state_update" in error for error in validator.errors)

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
        # prompt_template is now optional, so no error for missing_prompt task
        assert any("must be an object" in error for error in validator.errors)
        # Should have warnings about missing description and missing prompt_template/steps
        assert len(validator.warnings) > 0  
        assert any("should have either prompt_template or steps" in warning for warning in validator.warnings)

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
                {"id": "hello_msg", "type": "user_message", "message": "Hello"},
                # Valid: message_type field
                {"id": "warning_msg", "type": "user_message", "message": "Warning", "message_type": "warning"},
                # Invalid: bad message type
                {"id": "bad_msg", "type": "user_message", "message": "Bad", "message_type": "invalid_type"},
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        errors = validator.errors
        # Should have at least one error about the invalid message type
        assert any("invalid message type: invalid_type" in error for error in errors)

    def test_special_step_types(self):
        """Test validation of special step types."""
        workflow = {
            "name": "test:special-steps",
            "description": "Test special steps",
            "version": "1.0.0",
            "default_state": {
                "flag": False
            },
            "steps": [
                {"id": "break_step", "type": "break"},  # Valid in loops
                {"id": "continue_step", "type": "continue"},  # Valid in loops
                {
                    "id": "batch_update",
                    "type": "batch_state_update",
                    "updates": [{"path": "raw.a", "value": 1}, {"path": "raw.b", "value": 2}],
                },
                {"id": "agent_cmd", "type": "agent_shell_command", "command": "ls -la", "reason": "List files"},
                {"id": "internal_call", "type": "internal_mcp_call", "tool": "internal_tool", "parameters": {}},
                {"id": "cond_msg", "type": "conditional_message", "condition": "{{ state.flag }}", "message": "Flag is set"},
            ],
        }

        validator = WorkflowValidator()
        # Disable schema validation for this test since it tests step types not in the schema
        validator.schema = None
        result = validator.validate(workflow)
        # These step types are not in the VALID_STEP_TYPES list
        assert result is False
        assert any("invalid type: batch_state_update" in error for error in validator.errors)
        assert any("invalid type: agent_shell_command" in error for error in validator.errors)
        assert any("invalid type: internal_mcp_call" in error for error in validator.errors)
        assert any("invalid type: conditional_message" in error for error in validator.errors)

    def test_circular_dependency_detection_direct(self):
        """Test detection of direct circular dependencies in computed fields."""
        workflow = {
            "name": "test:circular",
            "description": "Test circular dependencies",
            "version": "1.0.0",
            "default_state": {
                "value": 10
            },
            "state_schema": {
                "computed": {
                    "field_a": {
                        "from": "computed.field_b",
                        "transform": "input * 2"
                    },
                    "field_b": {
                        "from": "computed.field_a",
                        "transform": "input + 1"
                    }
                }
            },
            "steps": []
        }
        
        validator = WorkflowValidator()
        validator.schema = None  # Disable JSON schema validation for test
        assert not validator.validate(workflow)
        errors = [error for error in validator.errors if "Circular dependency" in error]
        assert len(errors) >= 1  # Should detect circular dependency

    def test_circular_dependency_detection_indirect(self):
        """Test detection of indirect circular dependencies in computed fields."""
        workflow = {
            "name": "test:circular-indirect",
            "description": "Test indirect circular dependencies",
            "version": "1.0.0",
            "default_state": {
                "value": 10
            },
            "state_schema": {
                "computed": {
                    "field_a": {
                        "from": "computed.field_b",
                        "transform": "input * 2"
                    },
                    "field_b": {
                        "from": "computed.field_c",
                        "transform": "input + 1"
                    },
                    "field_c": {
                        "from": "computed.field_a",
                        "transform": "input / 2"
                    }
                }
            },
            "steps": []
        }
        
        validator = WorkflowValidator()
        validator.schema = None  # Disable JSON schema validation for test
        assert not validator.validate(workflow)
        errors = [error for error in validator.errors if "Circular dependency" in error]
        assert len(errors) >= 1  # Should detect circular dependency


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
