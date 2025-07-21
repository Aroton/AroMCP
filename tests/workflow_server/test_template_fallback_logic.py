"""Unit tests for template variable fallback resolution logic."""

import pytest
from unittest.mock import MagicMock

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.step_processors import StepProcessor
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager


class TestTemplateFallbackLogic:
    """Test template variable fallback resolution for better error messages."""

    def setup_method(self):
        """Set up test dependencies."""
        self.state_manager = StateManager()
        self.expression_evaluator = ExpressionEvaluator()
        self.step_registry = StepRegistry()
        
        # Set up processors
        self.step_processor = StepProcessor(
            self.state_manager, 
            self.expression_evaluator
        )
        
        self.subagent_manager = SubAgentManager(
            self.state_manager, 
            self.expression_evaluator, 
            self.step_registry
        )

    def test_subagent_manager_fallback_resolution(self):
        """Test SubAgentManager fallback resolution for missing variables."""
        # Test state with some context
        state = {
            "item": "src/test.ts",
            "task_id": "test_task_001",
            "attempt_number": 3,
            "max_attempts": 5
        }
        
        # Test templates with missing variables
        test_cases = [
            {
                "template": "❌ Failed to enforce standards on {{ raw.file_path }} after {{ raw.attempt_number }} attempts",
                "expected": "❌ Failed to enforce standards on src/test.ts after 3 attempts"
            },
            {
                "template": "Processing {{ file_path }} (attempt {{ raw.attempt_number }}/{{ max_attempts }})",
                "expected": "Processing src/test.ts (attempt 3/5)"
            },
            {
                "template": "Task {{ task_id }}: {{ raw.nonexistent_field }}",
                "expected": "Task test_task_001: <raw.nonexistent_field>"
            },
            {
                "template": "Status: {{ raw.step_results.hints.success }}",
                "expected": "Status: <raw.step_results.hints.success>"
            }
        ]
        
        for case in test_cases:
            result = self.subagent_manager._replace_variables(case["template"], state)
            assert result == case["expected"], f"Expected '{case['expected']}', got '{result}'"

    def test_step_processor_fallback_resolution(self):
        """Test StepProcessor fallback resolution for missing variables."""
        # Test state with some context
        state = {
            "item": "src/component.tsx",
            "task_id": "test_task_002",
            "attempt_number": 2,
            "file_path": "src/component.tsx"
        }
        
        # Test templates with missing variables
        test_cases = [
            {
                "template": "✅ Successfully enforced standards on {{ file_path }} in {{ raw.attempt_number }} attempts",
                "expected": "✅ Successfully enforced standards on src/component.tsx in 2 attempts"
            },
            {
                "template": "Failed for {{ raw.file_path }} after {{ raw.max_attempts }} attempts",
                "expected": "Failed for src/component.tsx after 10 attempts"
            },
            {
                "template": "Processing {{ item }} with undefined {{ raw.undefined_var }}",
                "expected": "Processing src/component.tsx with undefined <raw.undefined_var>"
            }
        ]
        
        for case in test_cases:
            result = self.step_processor._replace_variables(case["template"], state)
            assert result == case["expected"], f"Expected '{case['expected']}', got '{result}'"

    def test_nested_property_fallback(self):
        """Test fallback for nested property access."""
        state = {
            "item": "src/utils.py",
            "raw": {
                "file_path": "src/utils.py",
                "step_results": {
                    "hints": {"success": True},
                    "lint": None,
                    "typescript": None
                }
            }
        }
        
        # Test nested property access
        test_cases = [
            {
                "template": "Hints: {{ raw.step_results.hints.success }}",
                "expected": "Hints: True"
            },
            {
                "template": "Lint: {{ raw.step_results.lint.success }}",
                "expected": "Lint: <raw.step_results.lint.success>"
            },
            {
                "template": "Missing: {{ raw.missing_field.nested.value }}",
                "expected": "Missing: <raw.missing_field.nested.value>"
            }
        ]
        
        for case in test_cases:
            result = self.subagent_manager._replace_variables(case["template"], state)
            assert result == case["expected"], f"Expected '{case['expected']}', got '{result}'"

    def test_single_expression_type_preservation(self):
        """Test that single expressions preserve appropriate types."""
        state = {
            "attempt_number": 3,
            "max_attempts": 10,
            "file_path": "src/test.js"
        }
        
        # Test single expressions that should return typed values
        test_cases = [
            {
                "template": "{{ raw.attempt_number }}",
                "expected": "3",  # Should use fallback as string
                "type": str
            },
            {
                "template": "{{ raw.max_attempts }}",
                "expected": "10",  # Should use fallback default for max_attempts
                "type": str
            },
            {
                "template": "{{ file_path }}",
                "expected": "src/test.js",  # Should find in state
                "type": str
            }
        ]
        
        for case in test_cases:
            result = self.step_processor._replace_variables(case["template"], state)
            assert str(result) == case["expected"], f"Expected '{case['expected']}', got '{result}'"

    def test_error_message_improvement(self):
        """Test that error messages are more informative with fallbacks."""
        # Simulate the original problematic case
        state = {
            "task_id": "enforce_standards_task_001",
            "item": "src/component.tsx",
            "index": 0,
            "total": 1
        }
        
        # This is the message that was showing empty values
        problematic_template = "❌ Failed to enforce standards on {{ file_path }} after {{ raw.attempt_number }} attempts"
        
        # With our fallback logic, it should show meaningful values
        result = self.subagent_manager._replace_variables(problematic_template, state)
        expected = "❌ Failed to enforce standards on src/component.tsx after 0 attempts"
        
        assert result == expected, f"Expected '{expected}', got '{result}'"
        
        # Verify it's not showing empty values (the key improvement)
        assert " on  after" not in result, "Template variables should not be empty"
        assert result != "❌ Failed to enforce standards on  after  attempts", "Should not have completely empty variables"

    def test_fallback_with_partial_state(self):
        """Test fallback behavior with minimal state information."""
        # Very minimal state - like what might happen in error conditions
        minimal_state = {"task_id": "minimal_task"}
        
        template = "Failed to process {{ file_path }} (attempt {{ raw.attempt_number }}/{{ raw.max_attempts }})"
        result = self.subagent_manager._replace_variables(template, minimal_state)
        
        # Should provide descriptive placeholders instead of empty strings
        expected = "Failed to process unknown_file (attempt 0/10)"
        assert result == expected, f"Expected '{expected}', got '{result}'"
        
        # Ensure no empty strings in the result
        assert "  " not in result, "Should not have double spaces from empty variables"
        assert "(attempt /)" not in result, "Should not have empty attempt values"

    def test_complex_message_with_conditionals(self):
        """Test complex messages that might include conditional logic."""
        state = {
            "item": "src/service.ts",
            "raw": {
                "file_path": "src/service.ts",
                "attempt_number": 2,
                "step_results": {
                    "hints": {"success": True},
                    "lint": {"success": False},
                    "typescript": None
                }
            },
            "computed": {
                "hints_completed": True,
                "lint_completed": False,
                "typescript_completed": False
            }
        }
        
        # Complex status message with multiple variables
        template = """Status for {{ raw.file_path }}:
- Hints: {{ computed.hints_completed ? '✅ Completed' : '❌ Failed' }}
- Lint: {{ computed.lint_completed ? '✅ Completed' : '❌ Failed' }}
- TypeScript: {{ computed.typescript_completed ? '✅ Completed' : '❌ Failed' }}
Attempt {{ raw.attempt_number }}/{{ raw.max_attempts }}"""
        
        result = self.subagent_manager._replace_variables(template, state)
        
        # Should preserve file path and attempt number with fallbacks
        assert "src/service.ts" in result
        assert "Attempt 2/" in result
        
        # Should show fallback for max_attempts
        assert "2/10" in result, f"Result should show attempt fallback, got: {result}"