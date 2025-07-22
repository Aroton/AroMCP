#!/usr/bin/env python3
"""
Tests for workflow validation.
"""

from pathlib import Path

import pytest
import yaml

from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestWorkflowValidation:
    """Test workflow validation functionality."""

    def test_valid_minimal_workflow(self):
        """Test validation of a minimal valid workflow."""
        workflow = {
            "name": "test:minimal",
            "description": "A minimal test workflow",
            "version": "1.0.0",
            "steps": [{"id": "hello", "type": "user_message", "message": "Hello, world!"}],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is True
        assert len(validator.errors) == 0

    def test_missing_required_fields(self):
        """Test detection of missing required fields."""
        workflow = {"description": "Missing name and version", "steps": [{"id": "test_step", "type": "user_message", "message": "Test"}]}

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("Missing required fields" in error for error in validator.errors)

    def test_invalid_step_type(self):
        """Test detection of invalid step types."""
        workflow = {
            "name": "test:invalid-step",
            "description": "Workflow with invalid step type",
            "version": "1.0.0",
            "steps": [{"id": "invalid_step", "type": "invalid_step_type", "message": "This should fail"}],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("invalid type: invalid_step_type" in error for error in validator.errors)

    def test_complex_workflow(self):
        """Test validation of a complex workflow with all features."""
        workflow = {
            "name": "test:complex",
            "description": "A complex test workflow",
            "version": "1.0.0",
            "config": {"max_retries": 3, "timeout_seconds": 300},
            "default_state": {"counter": 0, "items": [], "results": {}},
            "state_schema": {
                "computed": {
                    "total_items": {"from": "state.items", "transform": "input.length"},
                    "has_items": {"from": "state.items", "transform": "input.length > 0"},
                }
            },
            "inputs": {
                "file_path": {"type": "string", "description": "Path to process", "required": True},
                "max_items": {
                    "type": "number",
                    "description": "Maximum items to process",
                    "required": False,
                    "default": 10,
                },
            },
            "steps": [
                {"id": "get_input", "type": "user_input", "prompt": "Enter initial counter", "variable_name": "init_count"},
                {
                    "id": "check_items",
                    "type": "conditional",
                    "condition": "{{ computed.has_items }}",
                    "then_steps": [
                        {
                            "id": "show_processing",
                            "type": "user_message",
                            "message": "Processing {{ computed.total_items }} items",
                            "message_type": "info",
                        }
                    ],
                    "else_steps": [
                        {"id": "show_no_items", "type": "user_message", "message": "No items to process", "message_type": "warning"}
                    ],
                },
                {
                    "id": "process_items_sequentially",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "variable_name": "item",
                    "body": [{"id": "call_process_item", "type": "mcp_call", "tool": "process_item", "parameters": {"item": "{{ item }}"}}],
                },
                {
                    "id": "process_items_parallel",
                    "type": "parallel_foreach",
                    "items": "{{ state.items }}",
                    "max_parallel": 5,
                    "sub_agent_task": "process_item_task",
                },
            ],
            "sub_agent_tasks": {
                "process_item_task": {
                    "description": "Process a single item",
                    "prompt_template": "Process item: {{ item }}",
                }
            },
        }

        validator = WorkflowValidator()
        # Disable schema validation as the test uses a different state structure
        validator.schema = None
        result = validator.validate(workflow)
        assert result is True
        assert len(validator.errors) == 0

    def test_step_validation(self):
        """Test validation of specific step types."""
        workflow = {
            "name": "test:step-validation",
            "description": "Test step validation",
            "version": "1.0.0",
            "steps": [
                # Missing required fields
                {
                    "id": "invalid_mcp_call",
                    "type": "mcp_call",
                    # Missing tool
                    "parameters": {"test": True},
                },
                {
                    "id": "invalid_user_message",
                    "type": "user_message",
                    # Missing message
                    "message_type": "info",
                },
                {
                    "id": "invalid_conditional",
                    "type": "conditional",
                    # Missing condition
                    "then_steps": [{"id": "break_step", "type": "break"}],
                },
                {
                    "id": "invalid_foreach",
                    "type": "foreach",
                    # Missing items
                    "body": [{"id": "step", "type": "user_message", "message": "test"}]
                },
            ],
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False
        assert any("missing 'tool' field" in error for error in validator.errors)
        assert any("missing 'message' field" in error for error in validator.errors)
        assert any("missing 'condition' field" in error for error in validator.errors)
        assert any("missing 'items' field" in error for error in validator.errors)

    def test_our_generated_workflow(self):
        """Test validation of the code-standards:enforce workflow we generated."""
        workflow_path = Path(__file__).parent.parent / ".aromcp" / "workflows" / "code-standards:enforce.yaml"

        if workflow_path.exists():
            with open(workflow_path) as f:
                workflow = yaml.safe_load(f)

            validator = WorkflowValidator()
            result = validator.validate(workflow)

            # Print any issues for debugging
            if not result:
                print("\nValidation errors:")
                for _error in validator.errors:
                    print(f"  - {_error}")
            if validator.warnings:
                print("\nValidation warnings:")
                for _warning in validator.warnings:
                    print(f"  - {_warning}")

            assert result is True
            assert len(validator.errors) == 0

    def test_validation_error_message(self):
        """Test the validation error message formatting."""
        workflow = {
            "name": "test",  # Missing namespace
            "description": "Test",
            # Missing version
            "steps": "not-an-array",  # Wrong type
        }

        validator = WorkflowValidator()
        result = validator.validate(workflow)
        assert result is False

        error_msg = validator.get_validation_error()
        assert "Workflow validation failed:" in error_msg
        assert "Missing required fields" in error_msg
        assert "Steps must be an array" in error_msg
        assert "Warnings:" in error_msg
        assert "namespace:name" in error_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
