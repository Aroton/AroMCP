"""Tests for scoped variable reference validation in workflows."""

from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestScopedValidation:
    """Test validation of scoped variable references."""

    def test_this_scope_validation_valid_state(self):
        """Test validation of this.variable references against state variables."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0, "data": {"value": "test"}}},
            "steps": [
                {"id": "step1", "type": "mcp_call", "tool": "test_tool", "parameters": {"value": "{{ this.counter }}"}},
                {
                    "id": "step2",
                    "type": "mcp_call",
                    "tool": "test_tool2",
                    "parameters": {"nested": "{{ this.data.value }}"},
                },
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_this_scope_validation_valid_computed(self):
        """Test validation of this.variable references against computed fields."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"input_value": 5}},
            "state_schema": {"computed": {"doubled": {"from": "state.input_value", "transform": "input * 2"}}},
            "steps": [
                {
                    "id": "step_1",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {"result": "{{ this.doubled }}"},
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_this_scope_validation_invalid_field(self):
        """Test validation fails for undefined this.variable references."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0}},
            "steps": [
                {
                    "id": "step_2",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {"value": "{{ this.nonexistent }}"},
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid
        assert any("this.nonexistent" in error for error in validator.errors)

    def test_global_scope_validation_always_valid(self):
        """Test that global.variable references are always valid."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "step_3",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {"value": "{{ global.any_variable }}"},
                },
                {
                    "id": "step_4",
                    "type": "mcp_call",
                    "tool": "test_tool2",
                    "parameters": {"nested": "{{ global.deeply.nested.value }}"},
                },
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_loop_scope_validation_in_foreach_context(self):
        """Test loop.item and loop.index validation in foreach contexts."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"items": [1, 2, 3]}},
            "steps": [
                {
                    "id": "step_5",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "body": [
                        {
                            "id": "step_6",
                            "type": "mcp_call",
                            "tool": "process_item",
                            "parameters": {"current_item": "{{ loop.item }}", "current_index": "{{ loop.index }}"},
                        }
                    ],
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_loop_scope_validation_in_while_context(self):
        """Test loop.iteration validation in while_loop contexts."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0}},
            "steps": [
                {
                    "id": "step_7",
                    "type": "while_loop",
                    "condition": "{{ loop.iteration }} < 5",
                    "body": [
                        {
                            "id": "step_8",
                            "type": "mcp_call",
                            "tool": "process_iteration",
                            "parameters": {"iteration": "{{ loop.iteration }}"},
                        }
                    ],
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_loop_scope_validation_outside_loop_context(self):
        """Test loop variables fail validation outside loop contexts."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "steps": [
                {"id": "step_9", "type": "mcp_call", "tool": "test_tool", "parameters": {"value": "{{ loop.item }}"}}
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid
        assert any("loop.item" in error and "only valid inside" in error for error in validator.errors)

    def test_loop_item_wrong_context(self):
        """Test loop.item fails in while_loop context."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0}},
            "steps": [
                {
                    "id": "step_10",
                    "type": "while_loop",
                    "condition": "{{ state.counter }} < 5",
                    "body": [
                        {
                            "id": "step_11",
                            "type": "mcp_call",
                            "tool": "test_tool",
                            "parameters": {"item": "{{ loop.item }}"},  # Invalid in while_loop
                        }
                    ],
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid
        assert any("loop.item" in error and "foreach" in error for error in validator.errors)

    def test_loop_iteration_wrong_context(self):
        """Test loop.iteration fails in foreach context."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"items": [1, 2, 3]}},
            "steps": [
                {
                    "id": "step_12",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "body": [
                        {
                            "id": "step_13",
                            "type": "mcp_call",
                            "tool": "test_tool",
                            "parameters": {"iteration": "{{ loop.iteration }}"},  # Invalid in foreach
                        }
                    ],
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid
        assert any("loop.iteration" in error and "while_loop" in error for error in validator.errors)

    def test_inputs_scope_validation_valid(self):
        """Test inputs.parameter validation against defined inputs."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "inputs": {
                "file_path": {"type": "string", "description": "Path to file"},
                "max_count": {"type": "number", "description": "Maximum count"},
            },
            "steps": [
                {
                    "id": "step_14",
                    "type": "mcp_call",
                    "tool": "process_file",
                    "parameters": {"path": "{{ inputs.file_path }}", "count": "{{ inputs.max_count }}"},
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_inputs_scope_validation_invalid(self):
        """Test inputs.parameter validation fails for undefined inputs."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "inputs": {"file_path": {"type": "string", "description": "Path to file"}},
            "steps": [
                {
                    "id": "step_15",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {"value": "{{ inputs.undefined_param }}"},
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid
        assert any("inputs.undefined_param" in error for error in validator.errors)

    def test_invalid_scope_name(self):
        """Test validation fails for invalid scope names."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "step_16",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {"value": "{{ invalid_scope.variable }}"},
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid
        assert any("invalid_scope" in error and "Invalid scope" in error for error in validator.errors)

    def test_nested_loop_scoped_variables(self):
        """Test scoped variables in nested loop contexts."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"outer_items": [[1, 2], [3, 4]]}},
            "steps": [
                {
                    "id": "step_17",
                    "type": "foreach",
                    "items": "{{ state.outer_items }}",
                    "body": [
                        {
                            "id": "step_18",
                            "type": "foreach",
                            "items": "{{ loop.item }}",
                            "body": [
                                {
                                    "id": "step_19",
                                    "type": "mcp_call",
                                    "tool": "process_nested",
                                    "parameters": {"inner_item": "{{ loop.item }}", "inner_index": "{{ loop.index }}"},
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_scoped_variables_error_messages(self):
        """Test quality of error messages for scoped variable validation."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0}},
            "steps": [
                {
                    "id": "step_20",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {
                        "wrong_scope": "{{ invalid.variable }}",
                        "wrong_context": "{{ loop.item }}",
                        "nonexistent": "{{ this.missing }}",
                    },
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid

        error_text = " ".join(validator.errors)

        # Check for specific error guidance
        assert "Invalid scope 'invalid'" in error_text
        assert "only valid inside foreach loops" in error_text
        assert "this.missing" in error_text

    def test_backward_compatibility_with_legacy_syntax(self):
        """Test that legacy state.variable syntax still works alongside new scoped syntax."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0, "data": {"value": "test"}}},
            "state_schema": {"computed": {"doubled": {"from": "state.counter", "transform": "input * 2"}}},
            "inputs": {"file_path": {"type": "string", "description": "Path to file"}},
            "steps": [
                {
                    "id": "step_21",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {
                        "legacy_state": "{{ state.counter }}",
                        "legacy_computed": "{{ computed.doubled }}",
                        "legacy_inputs": "{{ inputs.file_path }}",
                        "new_this": "{{ this.counter }}",
                        "new_inputs": "{{ inputs.file_path }}",
                        "new_global": "{{ global.dynamic_var }}",
                    },
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_subagent_scoped_validation(self):
        """Test scoped variable validation in sub-agent contexts."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"items": [1, 2, 3]}},
            "sub_agent_tasks": {
                "process_item": {
                    "description": "Process an item",
                    "default_state": {"state": {"item_data": None}},
                    "inputs": {"item": {"type": "object", "description": "Item to process"}},
                    "state_schema": {
                        "computed": {"processed": {"from": "inputs.item", "transform": "input.processed = true; input"}}
                    },
                    "steps": [
                        {
                            "id": "step_22",
                            "type": "mcp_call",
                            "tool": "sub_process",
                            "parameters": {
                                "input": "{{ inputs.item }}",
                                "state": "{{ this.item_data }}",
                                "computed": "{{ this.processed }}",
                                "global": "{{ global.sub_var }}",
                            },
                        }
                    ],
                }
            },
            "steps": [
                {
                    "id": "step_23",
                    "type": "parallel_foreach",
                    "items": "{{ state.items }}",
                    "sub_agent_task": "process_item",
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert is_valid, f"Validation errors: {validator.errors}"

    def test_suggestions_for_scoped_variables(self):
        """Test that validation provides helpful suggestions for scoped variables."""
        validator = WorkflowValidator()

        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"counter": 0, "user_data": {"name": "test"}}},
            "state_schema": {
                "computed": {
                    "user_info": {
                        "from": "state.user_data",
                        "transform": "input.display_name = input.name.toUpperCase(); input",
                    }
                }
            },
            "steps": [
                {
                    "id": "step_24",
                    "type": "mcp_call",
                    "tool": "test_tool",
                    "parameters": {"typo": "{{ this.countr }}"},  # Typo in counter
                }
            ],
        }

        is_valid = validator.validate(workflow)
        assert not is_valid

        error_text = " ".join(validator.errors)
        # Should suggest correct alternatives
        assert "this.counter" in error_text or "state.counter" in error_text

    def test_context_aware_validation_while_vs_foreach(self):
        """Test that loop variable context is properly distinguished between while_loop and foreach."""
        validator = WorkflowValidator()

        # Test valid while_loop with iteration
        workflow_while = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "step_25",
                    "type": "while_loop",
                    "condition": "{{ loop.iteration }} < 3",
                    "body": [
                        {
                            "id": "step_26",
                            "type": "mcp_call",
                            "tool": "test_tool",
                            "parameters": {"count": "{{ loop.iteration }}"},
                        }
                    ],
                }
            ],
        }

        is_valid = validator.validate(workflow_while)
        assert is_valid, f"While loop validation errors: {validator.errors}"

        # Test valid foreach with item/index
        workflow_foreach = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {"state": {"items": [1, 2, 3]}},
            "steps": [
                {
                    "id": "step_27",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "body": [
                        {
                            "id": "step_28",
                            "type": "mcp_call",
                            "tool": "test_tool",
                            "parameters": {"item": "{{ loop.item }}", "index": "{{ loop.index }}"},
                        }
                    ],
                }
            ],
        }

        validator_foreach = WorkflowValidator()
        is_valid = validator_foreach.validate(workflow_foreach)
        assert is_valid, f"Foreach validation errors: {validator_foreach.errors}"
