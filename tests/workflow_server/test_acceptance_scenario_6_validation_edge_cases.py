"""Tests for Acceptance Scenario 6: Validation Edge Cases.

This test suite covers comprehensive validation edge cases to ensure the workflow
system is robust against malformed inputs, circular dependencies, memory issues,
and provides helpful error messages with suggestions.

Tests edge cases that could occur in production and verifies the system gracefully
handles invalid workflows while providing actionable guidance to users.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import gc
import psutil

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aromcp.workflow_server.workflow.validator import WorkflowValidator
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.state.manager import StateManager


class TestAcceptanceScenario6ValidationEdgeCases:
    """Test validation edge cases to complete acceptance criteria coverage."""
    
    def setup_method(self):
        """Set up test environment."""
        self.validator = WorkflowValidator()
        self.loader = WorkflowLoader(strict_schema=False)  # Allow malformed workflows for testing
        self.executor = QueueBasedWorkflowExecutor()
        
    def create_validator_without_schema(self):
        """Create validator with JSON schema disabled for custom validation tests."""
        validator = WorkflowValidator()
        validator.schema = None  # Disable JSON schema to test custom validation
        return validator

    def test_missing_required_fields(self):
        """Test workflows with missing required fields."""
        test_cases = [
            # Missing name
            {
                "workflow": {
                    "description": "Test workflow",
                    "version": "1.0.0",
                    "steps": []
                },
                "expected_errors": ["name"]
            },
            # Missing description
            {
                "workflow": {
                    "name": "test:workflow",
                    "version": "1.0.0", 
                    "steps": []
                },
                "expected_errors": ["description"]
            },
            # Missing version
            {
                "workflow": {
                    "name": "test:workflow",
                    "description": "Test workflow",
                    "steps": []
                },
                "expected_errors": ["version"]
            },
            # Missing steps
            {
                "workflow": {
                    "name": "test:workflow",
                    "description": "Test workflow",
                    "version": "1.0.0"
                },
                "expected_errors": ["steps"]
            },
            # Multiple missing fields
            {
                "workflow": {
                    "description": "Test workflow"
                },
                "expected_errors": ["name", "version", "steps"]
            },
            # Empty workflow
            {
                "workflow": {},
                "expected_errors": ["name", "description", "version", "steps"]
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            validator = self.create_validator_without_schema()
            is_valid = validator.validate(test_case["workflow"])
            
            assert not is_valid, f"Test case {i}: Workflow with missing fields should be invalid"
            
            # Check that all expected missing fields are reported
            error_text = ' '.join(validator.errors)
            for expected_field in test_case["expected_errors"]:
                assert expected_field in error_text, f"Test case {i}: Missing field '{expected_field}' not reported in errors: {validator.errors}"

    def test_invalid_variable_references(self):
        """Test invalid variable references with helpful suggestions."""
        test_cases = [
            # Typo in state variable (root level) - this should be caught
            {
                "workflow": {
                    "name": "test:typo",
                    "description": "Test typos",
                    "version": "1.0.0",
                    "default_state": {"counter": 0, "configuration": {"enabled": True}},
                    "steps": [
                        {
                            "id": "step1",
                            "type": "user_message",
                            "message": "Value is {{ state.countr }}"  # Typo: countr vs counter
                        }
                    ]
                },
                "expected_undefined": "state.countr",
                "expected_suggestion": "state.counter"
            },
            # Typo in computed field - should be caught since computed fields are exact
            {
                "workflow": {
                    "name": "test:computed_typo",
                    "description": "Test computed typos",
                    "version": "1.0.0",
                    "default_state": {"value": 10},
                    "state_schema": {
                        "computed": {
                            "doubled_value": {"from": "state.value", "transform": "input * 2"}
                        }
                    },
                    "steps": [
                        {
                            "id": "step1", 
                            "type": "user_message",
                            "message": "Result: {{ computed.double_value }}"  # Typo: double_value vs doubled_value
                        }
                    ]
                },
                "expected_undefined": "computed.double_value",
                "expected_suggestion": "computed.doubled_value"
            },
            # Missing input parameter - should be caught
            {
                "workflow": {
                    "name": "test:missing_input",
                    "description": "Test missing input",
                    "version": "1.0.0",
                    "inputs": {
                        "file_path": {"type": "string"},
                        "max_attempts": {"type": "number"}
                    },
                    "default_state": {},
                    "steps": [
                        {
                            "id": "step1",
                            "type": "user_message",
                            "message": "Processing {{ inputs.filepath }}"  # Typo: filepath vs file_path
                        }
                    ]
                },
                "expected_undefined": "inputs.filepath",
                "expected_suggestion": "inputs.file_path"
            },
            # Completely undefined root-level state field
            {
                "workflow": {
                    "name": "test:undefined_field",
                    "description": "Test undefined field",
                    "version": "1.0.0",
                    "default_state": {"existing_field": "value"},
                    "steps": [
                        {
                            "id": "step1",
                            "type": "user_message",
                            "message": "Value: {{ state.nonexistent_field }}"
                        }
                    ]
                },
                "expected_undefined": "state.nonexistent_field",
                "expected_suggestion": "state.existing_field"
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            validator = self.create_validator_without_schema()
            is_valid = validator.validate(test_case["workflow"])
            
            assert not is_valid, f"Test case {i}: Workflow with invalid references should be invalid"
            
            # Check undefined reference is detected
            error_msg = validator.get_validation_error()
            assert test_case["expected_undefined"] in error_msg, f"Test case {i}: Expected undefined reference '{test_case['expected_undefined']}' not found in: {error_msg}"
            
            # Check suggestion is provided  
            assert "Did you mean" in error_msg, f"Test case {i}: No suggestion provided in error: {error_msg}"
            assert test_case["expected_suggestion"] in error_msg, f"Test case {i}: Expected suggestion '{test_case['expected_suggestion']}' not found in: {error_msg}"

        # Test edge case: Invalid namespace that doesn't get extracted (graceful handling)
        invalid_namespace_workflow = {
            "name": "test:invalid_namespace",
            "description": "Test invalid namespace",
            "version": "1.0.0",
            "default_state": {"counter": 0},
            "steps": [
                {
                    "id": "step1",
                    "type": "user_message",
                    "message": "Value: {{ stats.counter }}"  # Invalid namespace - not extracted
                }
            ]
        }
        
        validator = self.create_validator_without_schema()
        is_valid = validator.validate(invalid_namespace_workflow)
        
        # The validator should catch invalid namespace references and provide helpful suggestions
        # This demonstrates that the validator properly validates namespaces and provides guidance
        assert not is_valid, "Invalid namespace references should be caught by validator"
        error_msg = validator.get_validation_error()
        assert "stats.counter" in error_msg, "Expected undefined reference 'stats.counter' not found in error"
        assert "Invalid scope 'stats'" in error_msg, "Expected invalid scope error not found"
        assert "Did you mean" in error_msg, "Expected suggestions not found in error"

    def test_malformed_workflow_handling(self):
        """Test graceful handling of malformed workflows."""
        test_cases = [
            # Invalid step structure
            {
                "name": "Invalid step",
                "workflow": {
                    "name": "test:invalid_step",
                    "description": "Test invalid step",
                    "version": "1.0.0",
                    "steps": [
                        {"type": "invalid_type"},  # Invalid step type
                        {"id": "missing_type"},  # Missing type field
                        {}  # Missing required fields
                    ]
                },
                "expected_patterns": ["invalid_type", "type", "missing"]
            },
            # Invalid nested structures
            {
                "name": "Invalid nested",
                "workflow": {
                    "name": "test:nested",
                    "description": "Test nested",
                    "version": "1.0.0",
                    "inputs": {"invalid_input": {"type": "invalid_input_type"}},  # Invalid input type
                    "state_schema": {
                        "computed": {
                            "invalid_computed": {"missing_from": True}  # Missing required 'from' field
                        }
                    },
                    "steps": []
                },
                "expected_patterns": ["invalid_input_type", "missing"]
            },
            # Circular references in computed fields
            {
                "name": "Circular computed",
                "workflow": {
                    "name": "test:circular",
                    "description": "Test circular",
                    "version": "1.0.0",
                    "state_schema": {
                        "computed": {
                            "field_a": {"from": "computed.field_b", "transform": "input"},
                            "field_b": {"from": "computed.field_a", "transform": "input"}
                        }
                    },
                    "steps": []
                },
                "expected_patterns": ["circular", "dependency"]
            },
            # Invalid config values
            {
                "name": "Invalid config",
                "workflow": {
                    "name": "test:config",
                    "description": "Test config",
                    "version": "1.0.0",
                    "config": {
                        "timeout_seconds": -5,  # Should be positive
                        "max_retries": 3.5,  # Should be integer
                        "invalid_config": "value"
                    },
                    "steps": []
                },
                "expected_patterns": ["timeout", "positive", "max_retries", "integer"]
            }
        ]
        
        for test_case in test_cases:
            validator = self.create_validator_without_schema()
            is_valid = validator.validate(test_case["workflow"])
            
            assert not is_valid, f"{test_case['name']}: Malformed workflow should be invalid"
            
            # Check that validation doesn't crash and provides useful errors
            assert len(validator.errors) > 0, f"{test_case['name']}: Should have validation errors"
            
            error_text = ' '.join(validator.errors).lower()
            for pattern in test_case["expected_patterns"]:
                assert pattern.lower() in error_text, f"{test_case['name']}: Expected pattern '{pattern}' not found in errors: {validator.errors}"

    def test_memory_usage_with_large_workflows(self):
        """Test memory behavior with large workflows (100+ steps)."""
        # Get initial memory
        process = psutil.Process()
        initial_memory = process.memory_info().rss
        
        # Create a large workflow with 200 steps
        large_workflow = {
            "name": "test:large_workflow",
            "description": "Large workflow for memory testing",
            "version": "1.0.0",
            "default_state": {},
            "steps": []
        }
        
        # Add 200 steps with various types and references
        for i in range(200):
            step_type = ["user_message", "mcp_call", "shell_command"][i % 3]
            step = {
                "id": f"step_{i}",
                "type": step_type
            }
            
            if step_type == "user_message":
                step["message"] = f"Step {i} message with {{ state.counter_{i % 10} }}"
            elif step_type == "mcp_call":
                step["tool"] = f"tool_{i % 5}"
                step["parameters"] = {"param": f"value_{i}"}
            elif step_type == "shell_command":
                step["command"] = f"echo 'Step {i}'"
                step["state_update"] = {
                    "path": f"state.result_{i % 10}",
                    "value": f"result_{i}"
                }
            
            large_workflow["steps"].append(step)
        
        # Add state variables that some steps reference
        large_workflow["default_state"] = {f"counter_{i}": 0 for i in range(10)}
        large_workflow["default_state"].update({f"result_{i}": None for i in range(10)})
        
        # Validate the large workflow
        validator = self.create_validator_without_schema()
        start_memory = process.memory_info().rss
        
        is_valid = validator.validate(large_workflow)
        
        end_memory = process.memory_info().rss
        memory_increase = end_memory - start_memory
        
        # Memory increase should be reasonable (less than 100MB for 200 steps)
        assert memory_increase < 100 * 1024 * 1024, f"Memory usage too high: {memory_increase / 1024 / 1024:.2f}MB for 200 steps"
        
        # Validation should complete (may have errors due to undefined references, but shouldn't crash)
        assert validator.errors is not None, "Validator should complete without crashing"
        
        # Clean up
        del large_workflow
        del validator
        gc.collect()

    def test_circular_dependency_detection_in_workflows(self):
        """Test circular dependency detection in various workflow structures."""
        test_cases = [
            # Circular dependency in computed fields  
            {
                "name": "Computed field circular",
                "workflow": {
                    "name": "test:computed_circular",
                    "description": "Test computed circular",
                    "version": "1.0.0",
                    "state_schema": {
                        "computed": {
                            "field_a": {"from": "computed.field_b", "transform": "input + 1"},
                            "field_b": {"from": "computed.field_c", "transform": "input + 1"}, 
                            "field_c": {"from": "computed.field_a", "transform": "input + 1"}
                        }
                    },
                    "steps": []
                },
                "should_detect_circular": True
            },
            # Self-referencing computed field
            {
                "name": "Self-referencing computed",
                "workflow": {
                    "name": "test:self_ref",
                    "description": "Test self reference",
                    "version": "1.0.0", 
                    "state_schema": {
                        "computed": {
                            "recursive": {"from": "computed.recursive", "transform": "input"}
                        }
                    },
                    "steps": []
                },
                "should_detect_circular": True
            },
            # Valid computed dependency chain (no cycle)
            {
                "name": "Valid computed chain",
                "workflow": {
                    "name": "test:valid_chain",
                    "description": "Test valid chain",
                    "version": "1.0.0",
                    "default_state": {"value": 10},
                    "state_schema": {
                        "computed": {
                            "doubled": {"from": "state.value", "transform": "input * 2"},
                            "quadrupled": {"from": "computed.doubled", "transform": "input * 2"},
                            "octupled": {"from": "computed.quadrupled", "transform": "input * 2"}
                        }
                    },
                    "steps": []
                },
                "should_detect_circular": False
            },
            # Complex circular dependency through multiple fields
            {
                "name": "Complex circular",
                "workflow": {
                    "name": "test:complex_circular",
                    "description": "Test complex circular",
                    "version": "1.0.0",
                    "state_schema": {
                        "computed": {
                            "a": {"from": ["computed.b", "computed.c"], "transform": "input[0] + input[1]"},
                            "b": {"from": "computed.d", "transform": "input * 2"},
                            "c": {"from": "state.value", "transform": "input"},
                            "d": {"from": "computed.a", "transform": "input - 1"}  # Creates cycle: a -> b -> d -> a
                        }
                    },
                    "default_state": {"value": 5},
                    "steps": []
                },
                "should_detect_circular": True
            }
        ]
        
        for test_case in test_cases:
            validator = self.create_validator_without_schema()
            is_valid = validator.validate(test_case["workflow"])
            
            if test_case["should_detect_circular"]:
                # Should be invalid due to circular dependency
                assert not is_valid, f"{test_case['name']}: Should detect circular dependency"
                error_text = ' '.join(validator.errors).lower()
                assert "circular" in error_text or "cycle" in error_text or "dependency" in error_text, f"{test_case['name']}: Should report circular dependency in: {validator.errors}"
            else:
                # Should be valid (no circular dependency)
                circular_errors = [e for e in validator.errors if "circular" in e.lower() or "cycle" in e.lower()]
                assert len(circular_errors) == 0, f"{test_case['name']}: Should not report circular dependency: {circular_errors}"

    def test_edge_case_validation_scenarios(self):
        """Test boundary conditions and edge cases."""
        test_cases = [
            # Extremely long values
            {
                "name": "Long values",
                "workflow": {
                    "name": "test:" + "x" * 100,  # Very long name (but valid format)
                    "description": "y" * 1000,  # Very long description
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "z" * 100,  # Very long ID
                            "type": "user_message", 
                            "message": "Long message: " + "a" * 1000  # Very long message
                        }
                    ]
                },
                "should_not_crash": True
            },
            # Special characters and unicode
            {
                "name": "Special characters",
                "workflow": {
                    "name": "test:special_chars",
                    "description": "Description with émojis 🚀 and ünïcödé",
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "step_with_special_chars",
                            "type": "user_message",
                            "message": "Message with {{ state.field_with_üñïcødé }}"
                        }
                    ]
                },
                "expected_patterns": ["field_with_üñïcødé"]  # Should detect undefined unicode variable
            },
            # Very deeply nested template expressions (but valid since level1 exists as object)
            {
                "name": "Deep nesting with invalid reference",
                "workflow": {
                    "name": "test:deep_nesting",
                    "description": "Test deep nesting",
                    "version": "1.0.0",
                    "default_state": {
                        "level1": {"level2": {"value": 42}}
                    },
                    "steps": [
                        {
                            "id": "step1",
                            "type": "user_message",
                            "message": "Invalid root: {{ state.invalid_root.nested }}"  # invalid_root doesn't exist
                        }
                    ]
                },
                "expected_patterns": ["invalid_root"]
            },
            # Mixed valid and invalid references
            {
                "name": "Mixed references",
                "workflow": {
                    "name": "test:mixed",
                    "description": "Test mixed references",
                    "version": "1.0.0",
                    "default_state": {"valid_field": "value"},
                    "inputs": {"valid_input": {"type": "string"}},
                    "steps": [
                        {
                            "id": "step1",
                            "type": "user_message",
                            "message": "Valid: {{ state.valid_field }}, Invalid: {{ state.invalid_field }}, Valid input: {{ inputs.valid_input }}, Invalid input: {{ inputs.invalid_input }}"
                        }
                    ]
                },
                "expected_patterns": ["invalid_field", "invalid_input"]
            },
            # Empty required fields (note: validator doesn't check shell_command)
            {
                "name": "Empty required fields",
                "workflow": {
                    "name": "test:empty",
                    "description": "Test empty fields",
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "step1",
                            "type": "mcp_call"
                            # Missing "tool" field entirely (empty would still pass basic validation)
                        }
                    ]
                },
                "expected_patterns": ["tool"]
            }
        ]
        
        for test_case in test_cases:
            validator = self.create_validator_without_schema()
            
            # Validation should not crash regardless of input
            try:
                is_valid = validator.validate(test_case["workflow"])
                
                if test_case.get("should_not_crash"):
                    # Just ensure it doesn't crash, may be valid or invalid
                    assert validator.errors is not None, f"{test_case['name']}: Validator should not crash"
                else:
                    # Should be invalid and detect expected patterns
                    assert not is_valid, f"{test_case['name']}: Should be invalid"
                    
                    if "expected_patterns" in test_case:
                        error_text = ' '.join(validator.errors).lower()
                        for pattern in test_case["expected_patterns"]:
                            assert pattern.lower() in error_text, f"{test_case['name']}: Expected pattern '{pattern}' not found in: {validator.errors}"
                            
            except Exception as e:
                pytest.fail(f"{test_case['name']}: Validation should not crash but raised: {type(e).__name__}: {e}")

    def test_helpful_error_message_quality(self):
        """Verify error messages provide actionable guidance."""
        test_cases = [
            # Test descriptive error messages for missing required fields
            {
                "name": "Missing step fields",
                "workflow": {
                    "name": "test:missing_fields",
                    "description": "Test missing fields",
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "step1",
                            "type": "mcp_call"
                            # Missing required "tool" field
                        }
                    ]
                },
                "expected_guidance": ["tool", "missing"]
            },
            # Test suggestion system
            {
                "name": "Variable typo",
                "workflow": {
                    "name": "test:typo",
                    "description": "Test typo",
                    "version": "1.0.0",
                    "default_state": {"user_name": "Alice", "max_retries": 3},
                    "steps": [
                        {
                            "id": "step1",
                            "type": "user_message",
                            "message": "Hello {{ state.user_nam }}"  # Typo: user_nam
                        }
                    ]
                },
                "expected_guidance": ["Did you mean", "user_name", "Undefined"]
            },
            # Test invalid step type
            {
                "name": "Invalid step type",
                "workflow": {
                    "name": "test:invalid_type",
                    "description": "Test invalid type",
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "step1",
                            "type": "nonexistent_step_type",
                            "message": "Hello"
                        }
                    ]
                },
                "expected_guidance": ["invalid type", "nonexistent_step_type"]
            },
            # Test config validation with specific guidance
            {
                "name": "Invalid config values",
                "workflow": {
                    "name": "test:invalid_config",
                    "description": "Test invalid config",
                    "version": "1.0.0",
                    "config": {
                        "timeout_seconds": -10,  # Should be positive
                        "max_retries": -5  # Should be non-negative
                    },
                    "steps": []
                },
                "expected_guidance": ["timeout_seconds", "positive", "max_retries", "negative"]
            },
            # Test circular dependency detection with clear error
            {
                "name": "Circular dependency",
                "workflow": {
                    "name": "test:circular",
                    "description": "Test circular dependency",
                    "version": "1.0.0",
                    "state_schema": {
                        "computed": {
                            "field_a": {"from": "computed.field_b", "transform": "input"},
                            "field_b": {"from": "computed.field_a", "transform": "input"}
                        }
                    },
                    "steps": []
                },
                "expected_guidance": ["Circular", "dependency", "field_a"]
            }
        ]
        
        for test_case in test_cases:
            validator = self.create_validator_without_schema()
            is_valid = validator.validate(test_case["workflow"])
            
            assert not is_valid, f"{test_case['name']}: Should be invalid"
            
            # Get full error message with context
            full_error = validator.get_validation_error()
            
            # Check that error message contains helpful guidance
            for guidance in test_case["expected_guidance"]:
                assert guidance in full_error, f"{test_case['name']}: Expected guidance '{guidance}' not found in error message: {full_error}"
            
            # Error message should not be too generic
            assert len(full_error) > 20, f"{test_case['name']}: Error message too short/generic: {full_error}"
            
            # Should provide some location or context information
            assert any(keyword in full_error for keyword in ["step", "At", "in", "field", "Config", "Computed"]), f"{test_case['name']}: Error should provide some context: {full_error}"

    def test_schema_validation_completeness(self):
        """Test comprehensive schema compliance and validation completeness."""
        # Test that validator catches all schema violations
        schema_violation_cases = [
            # Invalid step structure completeness
            {
                "name": "Complete step validation",
                "workflow": {
                    "name": "test:complete_step",
                    "description": "Test complete step validation",
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "mcp_step",
                            "type": "mcp_call"
                            # Missing required "tool" field for mcp_call
                        },
                        {
                            "id": "conditional_step",
                            "type": "conditional"
                            # Missing required "condition" field
                        }
                    ]
                },
                "expected_violation": ["tool", "condition"]
            },
            # Invalid input parameter types
            {
                "name": "Invalid input types",
                "workflow": {
                    "name": "test:input_types", 
                    "description": "Test input types",
                    "version": "1.0.0",
                    "inputs": {
                        "invalid_type": {"type": "invalid_type"},
                        "bad_required": {"type": "string", "required": "yes"}  # Should be boolean
                    },
                    "steps": []
                },
                "expected_violation": ["invalid_type", "required"]
            },
            # Invalid step types
            {
                "name": "Invalid step types",
                "workflow": {
                    "name": "test:invalid_types",
                    "description": "Test invalid step types",
                    "version": "1.0.0",
                    "steps": [
                        {
                            "id": "invalid_step",
                            "type": "nonexistent_step_type"
                        }
                    ]
                },
                "expected_violation": ["invalid type", "nonexistent_step_type"]
            }
        ]
        
        for test_case in schema_violation_cases:
            validator = self.create_validator_without_schema()
            is_valid = validator.validate(test_case["workflow"])
            
            assert not is_valid, f"{test_case['name']}: Should detect schema violation"
            
            error_text = ' '.join(validator.errors)
            if isinstance(test_case["expected_violation"], list):
                for violation in test_case["expected_violation"]:
                    assert violation in error_text, f"{test_case['name']}: Should detect violation '{violation}' in: {validator.errors}"
            else:
                assert test_case["expected_violation"] in error_text, f"{test_case['name']}: Should detect violation '{test_case['expected_violation']}' in: {validator.errors}"
        
        # Test format validation (these generate warnings, not errors)
        warning_cases = [
            # Invalid workflow name format - generates warning
            {
                "name": "Invalid name format",
                "workflow": {
                    "name": "invalid name format",  # Should be namespace:name
                    "description": "Test", 
                    "version": "1.0.0",
                    "steps": []
                },
                "expected_warning": "namespace:name"
            },
            # Invalid version format - generates warning
            {
                "name": "Invalid version",
                "workflow": {
                    "name": "test:version",
                    "description": "Test",
                    "version": "not.semantic.version",  # Should be semantic versioning
                    "steps": []
                },
                "expected_warning": "semantic versioning"
            }
        ]
        
        for test_case in warning_cases:
            validator = self.create_validator_without_schema()
            validator.validate(test_case["workflow"])  # May still be valid, but should have warnings
            
            warning_text = ' '.join(validator.warnings)
            assert test_case["expected_warning"] in warning_text, f"{test_case['name']}: Should detect warning '{test_case['expected_warning']}' in: {validator.warnings}"
        
        # Test completeness: ensure validator checks all critical aspects
        complete_workflow = {
            "name": "test:complete_validation",
            "description": "Test complete validation coverage",
            "version": "1.0.0",
            "inputs": {
                "file_path": {"type": "string", "required": True},
                "max_retries": {"type": "number", "default": 3}
            },
            "config": {
                "timeout_seconds": 300,
                "max_retries": 5
            },
            "default_state": {
                "processed_files": [],
                "error_count": 0,
                "status": "pending"
            },
            "state_schema": {
                "computed": {
                    "progress_percent": {
                        "from": ["state.processed_files", "inputs.file_path"],
                        "transform": "(input[0].length / input[1].split(',').length) * 100"
                    }
                }
            },
            "steps": [
                {
                    "id": "process_files",
                    "type": "foreach",
                    "items": "{{ inputs.file_path.split(',') }}",
                    "body": [
                        {
                            "id": "process_file",
                            "type": "mcp_call",
                            "tool": "process_file",
                            "parameters": {"path": "{{ loop_item }}"}
                        }
                    ]
                }
            ],
            "sub_agent_tasks": {
                "file_processor": {
                    "description": "Process individual files",
                    "inputs": {"file": {"type": "string"}},
                    "steps": [
                        {
                            "id": "process",
                            "type": "shell_command",
                            "command": "process {{ inputs.file }}"
                        }
                    ]
                }
            }
        }
        
        validator = self.create_validator_without_schema()
        is_valid = validator.validate(complete_workflow)
        
        # This complete workflow should pass basic validation
        # (may have warnings about undefined references, but structure should be valid)
        structural_errors = [e for e in validator.errors if not "undefined" in e.lower()]
        assert len(structural_errors) == 0, f"Complete workflow should have valid structure: {structural_errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])