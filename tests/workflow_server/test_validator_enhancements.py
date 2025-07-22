"""Test the enhanced WorkflowValidator functionality for acceptance criteria."""

import pytest

from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestValidatorEnhancements:
    """Test enhanced validator functionality meeting acceptance criteria."""

    def create_validator(self):
        """Create a validator with schema disabled for testing."""
        validator = WorkflowValidator()
        validator.schema = None  # Disable JSON schema validation
        return validator

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
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        errors = [error for error in validator.errors if "Circular dependency" in error]
        assert len(errors) == 2  # Both fields should be flagged
        assert any("field_a" in error for error in errors)
        assert any("field_b" in error for error in errors)

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
                        "transform": "input - 1"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        errors = [error for error in validator.errors if "Circular dependency" in error]
        assert len(errors) >= 1  # At least one circular dependency should be detected

    def test_no_circular_dependency_valid_chain(self):
        """Test that valid dependency chains don't trigger circular dependency errors."""
        workflow = {
            "name": "test:valid-chain",
            "description": "Test valid dependency chain",
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
                    },
                    "octupled": {
                        "from": "computed.quadrupled",
                        "transform": "input * 2"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_error_handling_strategy_validation(self):
        """Test validation of error handling strategies in computed fields."""
        workflow = {
            "name": "test:error-handling",
            "description": "Test error handling validation",
            "version": "1.0.0",
            "default_state": {
                "value": 10
            },
            "state_schema": {
                "computed": {
                    "valid_use_fallback": {
                        "from": "state.value",
                        "transform": "input * 2",
                        "on_error": "use_fallback",
                        "fallback": 0
                    },
                    "invalid_use_fallback": {
                        "from": "state.value",
                        "transform": "input * 2",
                        "on_error": "use_fallback"
                        # Missing fallback value
                    },
                    "valid_propagate": {
                        "from": "state.value",
                        "transform": "input * 2",
                        "on_error": "propagate"
                    },
                    "valid_ignore": {
                        "from": "state.value",
                        "transform": "input * 2",
                        "on_error": "ignore"
                    },
                    "invalid_strategy": {
                        "from": "state.value",
                        "transform": "input * 2",
                        "on_error": "invalid_strategy"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Should have error for missing fallback value
        assert any("no 'fallback' value is defined" in error for error in validator.errors)
        
        # Should have error for invalid strategy
        assert any("invalid on_error value" in error for error in validator.errors)

    def test_javascript_expression_validation(self):
        """Test validation of JavaScript expressions in transform fields."""
        workflow = {
            "name": "test:js-validation",
            "description": "Test JavaScript validation",
            "version": "1.0.0",
            "default_state": {
                "value": 10
            },
            "state_schema": {
                "computed": {
                    "safe_transform": {
                        "from": "state.value",
                        "transform": "input * 2 + Math.abs(input)"
                    },
                    "dangerous_eval": {
                        "from": "state.value",
                        "transform": "eval('input * 2')"
                    },
                    "dangerous_function": {
                        "from": "state.value", 
                        "transform": "new Function('return input * 2')()"
                    },
                    "dangerous_require": {
                        "from": "state.value",
                        "transform": "require('fs').readFileSync('/etc/passwd')"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        # Should still validate (warnings don't make validation fail)
        result = validator.validate(workflow)
        
        # Should have warnings for dangerous patterns
        warning_messages = ' '.join(validator.warnings)
        assert "unsafe JavaScript pattern" in warning_messages
        assert "eval" in warning_messages or "Function" in warning_messages or "require" in warning_messages

    def test_break_continue_loop_context_validation(self):
        """Test that break/continue are validated to only occur in loop contexts."""
        workflow = {
            "name": "test:break-continue",
            "description": "Test break/continue validation",
            "version": "1.0.0",
            "default_state": {
                "items": ["a", "b", "c"],
                "counter": 0
            },
            "steps": [
                {
                    "id": "invalid_break",
                    "type": "break"  # Invalid: not in a loop
                },
                {
                    "id": "invalid_continue", 
                    "type": "continue"  # Invalid: not in a loop
                },
                {
                    "id": "valid_foreach",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "body": [
                        {
                            "id": "valid_break_in_foreach",
                            "type": "break"  # Valid: in foreach loop
                        },
                        {
                            "id": "valid_continue_in_foreach",
                            "type": "continue"  # Valid: in foreach loop
                        }
                    ]
                },
                {
                    "id": "valid_while",
                    "type": "while_loop",
                    "condition": "{{ state.counter < 5 }}",
                    "body": [
                        {
                            "id": "valid_break_in_while",
                            "type": "break"  # Valid: in while loop
                        },
                        {
                            "id": "valid_continue_in_while",
                            "type": "continue"  # Valid: in while loop
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Should have errors for invalid break/continue outside loops
        break_continue_errors = [error for error in validator.errors if "'break'" in error or "'continue'" in error]
        assert len(break_continue_errors) == 2
        
        # Check error messages contain path information and suggestions
        for error in break_continue_errors:
            assert "At steps[" in error  # Should have exact path
            assert "can only be used inside loop contexts" in error
            assert "Valid loop types:" in error
            assert "foreach" in error and "while_loop" in error

    def test_context_variable_validation(self):
        """Test context-specific variable validation (item, loop.index, etc.)."""
        workflow = {
            "name": "test:context-vars",
            "description": "Test context variable validation",
            "version": "1.0.0",
            "default_state": {
                "items": ["a", "b", "c"],
                "counter": 0
            },
            "steps": [
                {
                    "id": "invalid_item_outside_foreach",
                    "type": "user_message",
                    "message": "Item: {{ item }}"  # Invalid: item outside foreach
                },
                {
                    "id": "invalid_loop_index_outside_loop",
                    "type": "user_message", 
                    "message": "Index: {{ loop.index }}"  # Invalid: loop.index outside loop
                },
                {
                    "id": "invalid_attempt_number_outside_loop",
                    "type": "user_message",
                    "message": "Attempts: {{ state.attempt_number }}"  # Invalid: attempt_number outside loop
                },
                {
                    "id": "valid_foreach",
                    "type": "foreach",
                    "items": "{{ state.items }}",
                    "body": [
                        {
                            "id": "valid_item_in_foreach",
                            "type": "user_message",
                            "message": "Item: {{ item }}"  # Valid: item in foreach
                        },
                        {
                            "id": "valid_loop_index_in_foreach",
                            "type": "user_message",
                            "message": "Index: {{ loop.index }}"  # Valid: loop.index in foreach
                        }
                    ]
                },
                {
                    "id": "valid_while",
                    "type": "while_loop",
                    "condition": "{{ state.counter < 5 }}",
                    "body": [
                        {
                            "id": "valid_loop_iteration_in_while",
                            "type": "user_message",
                            "message": "Iteration: {{ loop.iteration }}"  # Valid: loop.iteration in while
                        },
                        {
                            "id": "valid_attempt_number_in_while",
                            "type": "user_message",
                            "message": "Attempts: {{ state.attempt_number }}"  # Valid: attempt_number in while
                        },
                        {
                            "id": "invalid_item_in_while",
                            "type": "user_message",
                            "message": "Item: {{ item }}"  # Invalid: item not valid in while (only foreach)
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Check for context-specific errors with exact paths
        context_errors = [error for error in validator.errors if "At steps[" in error and ("only valid inside" in error)]
        assert len(context_errors) >= 3
        
        # Check specific error messages
        item_errors = [error for error in context_errors if "'item'" in error]
        assert len(item_errors) == 2  # One outside foreach, one in while loop
        assert any("only valid inside foreach loops" in error for error in item_errors)
        
        loop_index_errors = [error for error in context_errors if "'loop.index'" in error]
        assert len(loop_index_errors) == 1  # One outside loop
        assert any("only valid inside loop contexts" in error for error in loop_index_errors)

    def test_enhanced_error_messages_with_suggestions(self):
        """Test enhanced error messages with exact paths and suggestions."""
        workflow = {
            "name": "test:enhanced-errors",
            "description": "Test enhanced error messages",
            "version": "1.0.0",
            "default_state": {
                "counter": 0,
                "configuration": {
                    "enabled": True
                }
            },
            "inputs": {
                "file_path": {
                    "type": "string"
                }
            },
            "state_schema": {
                "computed": {
                    "doubled": {
                        "from": "state.counter",
                        "transform": "input * 2"
                    }
                }
            },
            "steps": [
                {
                    "id": "typo_in_state",
                    "type": "user_message",
                    "message": "Value: {{ state.countr }}"  # Typo: countr vs counter
                },
                {
                    "id": "typo_in_input",
                    "type": "user_message",
                    "message": "File: {{ inputs.file_pth }}"  # Typo: file_pth vs file_path
                },
                {
                    "id": "typo_in_computed",
                    "type": "user_message",
                    "message": "Double: {{ computed.doubl }}"  # Typo: doubl vs doubled
                },
                {
                    "id": "deprecated_raw",
                    "type": "user_message",
                    "message": "Raw value: {{ raw.counter }}"  # Deprecated: raw namespace
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Check for suggestion-enhanced error messages
        suggestion_errors = [error for error in validator.errors if "Did you mean:" in error]
        assert len(suggestion_errors) >= 3
        
        # Check for deprecated namespace guidance
        deprecated_errors = [error for error in validator.errors if "deprecated" in error]
        assert len(deprecated_errors) == 1
        assert "Use 'state' instead" in deprecated_errors[0]

    def test_attempt_number_validation_in_while_loops(self):
        """Test that attempt_number is properly validated for while loops."""
        workflow = {
            "name": "test:attempt-number",
            "description": "Test attempt_number validation",
            "version": "1.0.0",
            "default_state": {
                "counter": 0
            },
            "steps": [
                {
                    "id": "while_with_attempt_number",
                    "type": "while_loop",
                    "condition": "{{ state.counter < 5 && state.attempt_number < 3 }}",
                    "body": [
                        {
                            "id": "show_attempt",
                            "type": "user_message",
                            "message": "Attempt {{ state.attempt_number }} of counter {{ state.counter }}"
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        # attempt_number should be valid in while loop context
        assert validator.validate(workflow)
        assert len(validator.errors) == 0

    def test_sub_agent_computed_field_validation(self):
        """Test that sub-agents have isolated computed field validation."""
        workflow = {
            "name": "test:sub-agent-computed",
            "description": "Test sub-agent computed validation",
            "version": "1.0.0",
            "default_state": {
                "items": ["item1", "item2"]
            },
            "state_schema": {
                "computed": {
                    "parent_computed": {
                        "from": "state.items",
                        "transform": "input.length"
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
                    "description": "Task with computed fields",
                    "inputs": {
                        "task_input": {
                            "type": "string",
                            "required": True
                        }
                    },
                    "default_state": {
                        "state": {
                            "task_value": 10
                        }
                    },
                    "state_schema": {
                        "computed": {
                            "sub_computed": {
                                "from": "state.task_value",
                                "transform": "input * 2"
                            },
                            "circular_a": {
                                "from": "computed.circular_b",
                                "transform": "input + 1"
                            },
                            "circular_b": {
                                "from": "computed.circular_a",
                                "transform": "input - 1"
                            },
                            "invalid_parent_reference": {
                                "from": "computed.parent_computed",  # Invalid: references parent computed field
                                "transform": "input"
                            }
                        }
                    },
                    "steps": [
                        {
                            "id": "use_computed",
                            "type": "user_message",
                            "message": "Sub computed: {{ computed.sub_computed }}"
                        }
                    ]
                }
            }
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Should have circular dependency errors in sub-agent
        circular_errors = [error for error in validator.errors if "Circular dependency" in error]
        assert len(circular_errors) >= 1
        
        # Should have error for invalid parent reference
        parent_ref_errors = [error for error in validator.errors if "parent_computed" in error]
        assert len(parent_ref_errors) >= 1

    def test_multiple_array_dependencies_validation(self):
        """Test validation of computed fields with multiple array dependencies."""
        workflow = {
            "name": "test:array-deps",
            "description": "Test array dependencies validation",
            "version": "1.0.0",
            "default_state": {
                "a": 1,
                "b": 2,
                "c": 3
            },
            "state_schema": {
                "computed": {
                    "sum_valid": {
                        "from": ["state.a", "state.b", "state.c"],
                        "transform": "input[0] + input[1] + input[2]"
                    },
                    "sum_invalid": {
                        "from": ["state.a", "state.undefined", "state.c"],
                        "transform": "input[0] + input[1] + input[2]"
                    },
                    "circular_array": {
                        "from": ["computed.sum_valid", "computed.circular_array"],
                        "transform": "input[0] + input[1]"
                    }
                }
            },
            "steps": []
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Should have error for undefined reference in array
        undefined_errors = [error for error in validator.errors if "state.undefined" in error]
        assert len(undefined_errors) == 1
        
        # Should have circular dependency error (may detect multiple instances)
        circular_errors = [error for error in validator.errors if "Circular dependency" in error]
        assert len(circular_errors) >= 1

    def test_exact_path_reporting(self):
        """Test that error messages include exact paths for context-specific validation."""
        workflow = {
            "name": "test:exact-paths",
            "description": "Test exact path reporting",
            "version": "1.0.0",
            "default_state": {
                "flag": False,
                "items": ["a", "b", "c"]
            },
            "steps": [
                {
                    "id": "step0",
                    "type": "break"  # Invalid: break outside loop
                },
                {
                    "id": "step1",
                    "type": "conditional",
                    "condition": "{{ state.flag }}",
                    "then_steps": [
                        {
                            "id": "nested_step",
                            "type": "user_message",
                            "message": "Invalid item: {{ item }}"  # Invalid: item outside foreach
                        }
                    ],
                    "else_steps": [
                        {
                            "id": "else_step",
                            "type": "foreach",
                            "items": "{{ state.items }}",
                            "body": [
                                {
                                    "id": "deep_nested",
                                    "type": "user_message",
                                    "message": "Valid item: {{ item }}"  # Valid: item inside foreach
                                },
                                {
                                    "id": "invalid_in_foreach",
                                    "type": "user_message",
                                    "message": "Invalid loop var: {{ loop.iteration }}"  # Invalid: iteration in foreach (should be index)
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        
        validator = self.create_validator()
        assert not validator.validate(workflow)
        
        # Check for exact path reporting in context-specific errors
        path_errors = [error for error in validator.errors if "At steps[" in error]
        assert len(path_errors) >= 2  # Should have multiple path-specific errors
        
        # Should have error for break at root level
        root_break_errors = [error for error in path_errors if "At steps[0]:" in error and "break" in error]
        assert len(root_break_errors) >= 1
        
        # Should have error with nested path for item usage
        then_step_errors = [error for error in path_errors if ".then_steps[0]" in error and "item" in error]
        assert len(then_step_errors) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])