"""Test variable reference validation in workflows."""

import pytest

from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestVariableReferenceValidation:
    """Test validation of variable references in workflows."""
    
    def setup_method(self):
        """Set up test method."""
        # Disable schema validation for these tests
        # as we're testing the reference validation logic
        self.original_has_jsonschema = WorkflowValidator.__dict__.get('HAS_JSONSCHEMA')
    
    def create_validator(self):
        """Create a validator with schema disabled for testing."""
        validator = WorkflowValidator()
        validator.schema = None  # Disable JSON schema validation
        return validator

    def test_valid_state_references(self):
        """Test validation of valid state variable references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "counter": 0,
                "config": {
                    "enabled": True,
                    "value": 42
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Counter is {{ state.counter }}"
                },
                {
                    "id": "step2",
                    "type": "user_message",
                    "message": "Config enabled: {{ state.config.enabled }}, value: {{ state.config.value }}"
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_valid_computed_references(self):
        """Test validation of computed field references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "value": 10
            },
            "state_schema": {
                "computed": {
                    "doubled": {
                        "from": "state.value",
                        "transform": "input * 2"
                    },
                    "quadrupled": {
                        "from": "computed.doubled",
                        "transform": "input * 2"
                    }
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Doubled: {{ computed.doubled }}, Quadrupled: {{ computed.quadrupled }}"
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_valid_input_references(self):
        """Test validation of input parameter references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "inputs": {
                "file_path": {
                    "type": "string",
                    "description": "File to process"
                },
                "max_retries": {
                    "type": "number",
                    "default": 3
                }
            },
            "default_state": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Processing {{ inputs.file_path }} with {{ inputs.max_retries }} retries"
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_undefined_state_reference(self):
        """Test detection of undefined state references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "counter": 0
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Value is {{ state.undefined_value }}"
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        assert any("Undefined variable reference: 'state.undefined_value'" in error for error in validator.errors)

    def test_undefined_computed_reference(self):
        """Test detection of undefined computed field references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {},
            "state_schema": {
                "computed": {
                    "valid_field": {
                        "from": "state.value",
                        "transform": "input * 2"
                    }
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Value is {{ computed.undefined_field }}"
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        assert any("Undefined variable reference: 'computed.undefined_field'" in error for error in validator.errors)

    def test_undefined_input_reference(self):
        """Test detection of undefined input parameter references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "inputs": {
                "file_path": {
                    "type": "string",
                    "description": "File to process"
                }
            },
            "default_state": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Processing {{ inputs.undefined_param }}"
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        assert any("Undefined variable reference: 'inputs.undefined_param'" in error for error in validator.errors)

    def test_loop_context_variables(self):
        """Test validation of loop-specific variables."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "items": ["a", "b", "c"]
            },
            "steps": [
                {
                    "id": "loop1",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "body": [
                        {
                            "id": "show_item",
                            "type": "user_message",
                            "message": "Item {{ state.loop_index }}: {{ state.loop_item }}"
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_while_loop_context(self):
        """Test validation of while loop context variables."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "counter": 0
            },
            "steps": [
                {
                    "id": "loop1",
                    "type": "while_loop",
                    "condition": "{{ state.counter < 5 }}",
                    "body": [
                        {
                            "id": "show_iteration",
                            "type": "user_message",
                            "message": "Iteration {{ loop.iteration }}"
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_sub_agent_task_references(self):
        """Test validation of references in sub-agent tasks."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {},
            "steps": [
                {
                    "id": "parallel1",
                    "type": "parallel_foreach",
                    "items": "{{ state.files }}",
                    "sub_agent_task": "process_file"
                }
            ],
            "sub_agent_tasks": {
                "process_file": {
                    "description": "Process a file",
                    "inputs": {
                        "file_path": {
                            "type": "string",
                            "required": True
                        }
                    },
                    "default_state": {
                        "status": "pending"
                    },
                    "state_schema": {
                        "computed": {
                            "is_ready": {
                                "from": "state.status",
                                "transform": "input === 'ready'"
                            }
                        }
                    },
                    "steps": [
                        {
                            "id": "check",
                            "type": "user_message",
                            "message": "Processing {{ inputs.file_path }}, ready: {{ computed.is_ready }}"
                        }
                    ]
                }
            }
        }
        
        validator = self.create_validator()
        result = validator.validate(workflow)
        # Note: state.files is not defined, so this should fail
        assert not result
        assert any("state.files" in error for error in validator.errors)

    def test_computed_field_from_references(self):
        """Test validation of references in computed field 'from' properties."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "value": 10
            },
            "state_schema": {
                "computed": {
                    "invalid": {
                        "from": "state.undefined_field",
                        "transform": "input * 2"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        assert any("Undefined variable reference: 'state.undefined_field'" in error for error in validator.errors)

    def test_multiple_from_references(self):
        """Test validation of multiple 'from' references in computed fields."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "a": 1,
                "b": 2
            },
            "state_schema": {
                "computed": {
                    "sum": {
                        "from": ["state.a", "state.b"],
                        "transform": "input[0] + input[1]"
                    },
                    "invalid": {
                        "from": ["state.a", "state.undefined"],
                        "transform": "input[0] + input[1]"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        assert any("Undefined variable reference: 'state.undefined'" in error for error in validator.errors)

    def test_nested_state_path_validation(self):
        """Test validation of nested state paths when parent is object type."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "tool_output": None,
                "specific_config": {
                    "host": "localhost",
                    "port": 8080
                }
            },
            "state_schema": {
                "state": {
                    "tool_output": "object",  # Dynamic object - any properties allowed
                    "specific_config": "object"  # Has specific structure
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    # These should be valid - tool_output is object type
                    "message": "Tool: {{ state.tool_output.success }}, {{ state.tool_output.data.anything }}"
                },
                {
                    "id": "step2", 
                    "type": "user_message",
                    # These should be valid - we defined these in default_state
                    "message": "Config: {{ state.specific_config.host }}:{{ state.specific_config.port }}"
                },
                {
                    "id": "step3",
                    "type": "user_message",
                    # This should be valid - parent exists as object
                    "message": "Extra: {{ state.specific_config.timeout }}"
                },
                {
                    "id": "step4",
                    "type": "user_message",
                    # This should fail - no undefined_field at root
                    "message": "Invalid: {{ state.undefined_field }}"
                }
            ]
        }
        
        validator = self.create_validator()
        result = validator.validate(workflow)
        # Should fail due to undefined_field
        assert not result
        
        # Check for the actual undefined reference error
        undefined_errors = [error for error in validator.errors if "Undefined variable reference:" in error]
        assert len(undefined_errors) == 1  # Should only have one undefined reference error
        assert "state.undefined_field" in undefined_errors[0]
        
        # Make sure nested object properties are NOT reported as undefined
        # (they might appear in suggestions, but not as the undefined reference itself)
        for error in undefined_errors:
            # Extract just the reference being reported as undefined
            if "Undefined variable reference: '" in error:
                ref_start = error.find("Undefined variable reference: '") + len("Undefined variable reference: '")
                ref_end = error.find("'", ref_start)
                undefined_ref = error[ref_start:ref_end]
                # These should NOT be the undefined reference
                assert undefined_ref != "state.tool_output.success"
                assert undefined_ref != "state.tool_output.data.anything"
                assert undefined_ref != "state.specific_config.host"
                assert undefined_ref != "state.specific_config.port"
                assert undefined_ref != "state.specific_config.timeout"

    def test_raw_state_references(self):
        """Test validation rejects deprecated raw state references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "data": {
                    "value": 42
                }
            },
            "state_schema": {
                "computed": {
                    "processed": {
                        "from": "raw.data.value",  # Deprecated: should use state.data.value
                        "transform": "input * 2"
                    }
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Raw value: {{ raw.data.value }}"  # Deprecated: should use state.data.value
                }
            ]
        }
        
        validator = self.create_validator()
        # Should fail because raw namespace is deprecated
        assert not validator.validate(workflow)
        # Should have deprecation errors
        deprecated_errors = [error for error in validator.errors if "deprecated" in error]
        assert len(deprecated_errors) >= 1

    def test_suggestions_for_typos(self):
        """Test that validator provides suggestions for typos."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "counter": 0,
                "configuration": {
                    "enabled": True
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Value is {{ state.countr }}"  # Typo: countr instead of counter
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        errors = validator.get_validation_error()
        assert "state.countr" in errors
        assert "Did you mean" in errors
        assert "state.counter" in errors

    def test_direct_input_references_in_templates(self):
        """Test validation of direct input references like {{ file_path }}."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "inputs": {
                "file_path": {
                    "type": "string",
                    "description": "File to process"
                },
                "max_attempts": {
                    "type": "number",
                    "default": 5
                }
            },
            "default_state": {},
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Processing {{ file_path }} with {{ max_attempts }} attempts"
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_sub_agent_state_isolation(self):
        """Test that sub-agents have isolated state and cannot access parent state."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow with sub-agent",
            "version": "1.0.0",
            "default_state": {
                "parent_state": "parent_value",
                "items": ["item1", "item2"]
            },
            "state_schema": {
                "computed": {
                    "parent_computed": {
                        "from": "state.parent_state",
                        "transform": "input.toUpperCase()"
                    }
                }
            },
            "steps": [
                {
                    "id": "call_sub",
                    "type": "parallel_foreach",
                    "items": "{{ state.items }}",
                    "sub_agent_task": "isolated_task"
                }
            ],
            "sub_agent_tasks": {
                "isolated_task": {
                    "description": "Task with isolated state",
                    "inputs": {
                        "task_input": {
                            "type": "string",
                            "required": True
                        }
                    },
                    "default_state": {
                        "state": {
                            "task_state": "task_value",
                            "lint_output": None
                        }
                    },
                    "state_schema": {
                        "state": {
                            "task_state": "string",
                            "lint_output": "object"
                        },
                        "computed": {
                            "has_lint_output": {
                                "from": "state.lint_output",
                                "transform": "input !== null"
                            }
                        }
                    },
                    "steps": [
                        {
                            "id": "valid_ref",
                            "type": "user_message",
                            "message": "Task state: {{ state.task_state }}, input: {{ inputs.task_input }}"
                        },
                        {
                            "id": "valid_nested_ref",
                            "type": "user_message",
                            "message": "Lint data: {{ state.lint_output.data }}, success: {{ state.lint_output.success }}"
                        },
                        {
                            "id": "invalid_parent_ref",
                            "type": "user_message",
                            "message": "Parent state: {{ state.parent_state }}"
                        },
                        {
                            "id": "invalid_parent_computed",
                            "type": "user_message", 
                            "message": "Parent computed: {{ computed.parent_computed }}"
                        }
                    ]
                }
            }
        }
        
        validator = self.create_validator()
        result = validator.validate(workflow)
        # Should fail because sub-agent tries to access parent state
        assert not result
        # Check for specific errors
        errors_str = ' '.join(validator.errors)
        assert "state.parent_state" in errors_str
        assert "computed.parent_computed" in errors_str
        # But should not have errors for valid sub-agent references
        # Check that these are not reported as undefined (they might appear in suggestions)
        assert not any("'state.task_state'" in error for error in validator.errors)
        assert not any("'inputs.task_input'" in error for error in validator.errors)
        # Nested object references should be valid
        assert not any("'state.lint_output.data'" in error for error in validator.errors)
        assert not any("'state.lint_output.success'" in error for error in validator.errors)
    
    def test_nested_object_references(self):
        """Test validation of nested object references."""
        workflow = {
            "name": "test:workflow",
            "description": "Test workflow",
            "version": "1.0.0",
            "default_state": {
                "tool_output": None
            },
            "state_schema": {
                "state": {
                    "tool_output": "object"
                }
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Tool success: {{ state.tool_output.success }}, data: {{ state.tool_output.data }}"
                },
                {
                    "id": "step2",
                    "type": "conditional",
                    "condition": "{{ state.tool_output.data.errors.length > 0 }}",
                    "then_steps": [
                        {
                            "id": "show_errors",
                            "type": "user_message",
                            "message": "Found {{ state.tool_output.data.errors.length }} errors"
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0