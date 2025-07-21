"""Unit tests for debug mode step definition conversion.

Tests the conversion from raw YAML step format to WorkflowStep definition format
in the _merge_context method for debug mode execution.
"""

import pytest
from unittest.mock import MagicMock, patch

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.workflow.step_processors import StepProcessor
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager


class TestDebugModeStepConversion:
    """Test debug mode step definition conversion functionality."""

    def setup_method(self):
        """Set up test dependencies."""
        self.state_manager = StateManager()
        self.executor = QueueBasedWorkflowExecutor(self.state_manager)
        
        # Set up a mock sub-agent context
        self.executor.subagent_manager.sub_agent_contexts = {
            "test_task_001": {
                "sub_agent_state": {
                    "raw": {
                        "attempt_number": 1,
                        "file_path": "src/test.ts",
                        "max_attempts": 5
                    },
                    "computed": {
                        "can_continue": True,
                        "is_typescript_file": True
                    }
                }
            }
        }

    def test_merge_context_with_yaml_format_user_message(self):
        """Test _merge_context with raw YAML format user_message step."""
        # Raw YAML format step (properties at top level)
        definition = {
            "message": "Starting attempt {{ raw.attempt_number }} for {{ file_path }}"
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/test.ts",
            "index": 0,
            "total": 1,
            "file_path": "src/test.ts"  # Add the expected variable
        }
        
        result = self.executor._merge_context(definition, task_context, "user_message")
        
        # Verify template variables were replaced
        assert "message" in result
        assert "Starting attempt 1 for src/test.ts" == result["message"]

    def test_merge_context_with_yaml_format_mcp_call(self):
        """Test _merge_context with raw YAML format mcp_call step."""
        # Raw YAML format mcp_call step
        definition = {
            "tool": "hints_for_files",
            "parameters": {
                "file_paths": ["{{ file_path }}"]
            },
            "store_result": "hints_output"
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/component.tsx",
            "index": 0,
            "total": 1,
            "file_path": "src/component.tsx"
        }
        
        result = self.executor._merge_context(definition, task_context, "mcp_call")
        
        # Verify structure is preserved
        assert "tool" in result
        assert "parameters" in result
        assert "store_result" in result
        
        # Verify template variables were replaced
        assert result["tool"] == "hints_for_files"
        assert result["parameters"]["file_paths"] == ["src/component.tsx"]
        assert result["store_result"] == "hints_output"

    def test_merge_context_with_workflow_step_format(self):
        """Test _merge_context with already converted WorkflowStep format."""
        # WorkflowStep format step (properties in definition)
        definition = {
            "command": "echo 'Processing {{ file_path }}'",
            "output_format": "text"
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/utils.py",
            "index": 0,
            "total": 1,
            "file_path": "src/utils.py"
        }
        
        result = self.executor._merge_context(definition, task_context, "shell_command")
        
        # Verify template variables were replaced
        assert result["command"] == "echo 'Processing src/utils.py'"
        assert result["output_format"] == "text"

    def test_merge_context_with_complex_templates(self):
        """Test _merge_context with complex template expressions."""
        definition = {
            "message": "File {{ file_path }} - Attempt {{ raw.attempt_number }}/{{ raw.max_attempts }} ({{ computed.can_continue ? 'continuing' : 'stopping' }})",
            "format": "markdown"
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/app.ts",
            "index": 0,
            "total": 1,
            "file_path": "src/app.ts"
        }
        
        result = self.executor._merge_context(definition, task_context, "user_message")
        
        # Verify complex template was processed
        assert "File src/app.ts" in result["message"]
        assert "Attempt 1/5" in result["message"]
        # Note: Complex ternary expressions might not work with the current evaluator
        # but the basic template replacement should work

    def test_merge_context_with_nested_objects(self):
        """Test _merge_context with nested object structures."""
        definition = {
            "parameters": {
                "input_file": "{{ file_path }}",
                "config": {
                    "max_retries": "{{ raw.max_attempts }}",
                    "current_attempt": "{{ raw.attempt_number }}"
                },
                "metadata": {
                    "is_typescript": "{{ computed.is_typescript_file }}",
                    "can_continue": "{{ computed.can_continue }}"
                }
            },
            "timeout": 30
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/service.ts",
            "index": 0,
            "total": 1,
            "file_path": "src/service.ts"
        }
        
        result = self.executor._merge_context(definition, task_context, "mcp_call")
        
        # Verify nested template replacement
        assert result["parameters"]["input_file"] == "src/service.ts"
        assert result["parameters"]["config"]["max_retries"] == 5
        assert result["parameters"]["config"]["current_attempt"] == 1
        assert result["timeout"] == 30

    def test_merge_context_without_sub_agent_state(self):
        """Test _merge_context fallback when sub-agent state is not available."""
        # Clear the sub-agent contexts to test fallback
        self.executor.subagent_manager.sub_agent_contexts.clear()
        
        definition = {
            "message": "Processing {{ item }} at index {{ index }}"
        }
        
        task_context = {
            "task_id": "unknown_task",
            "item": "src/fallback.js",
            "index": 2,
            "total": 5
        }
        
        result = self.executor._merge_context(definition, task_context, "user_message")
        
        # Verify fallback context works
        assert "Processing src/fallback.js at index 2" == result["message"]

    def test_merge_context_with_empty_definition(self):
        """Test _merge_context with empty definition (edge case)."""
        definition = {}
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/empty.ts",
            "index": 0,
            "total": 1
        }
        
        result = self.executor._merge_context(definition, task_context, "user_message")
        
        # Should return empty dictionary unchanged
        assert result == {}

    def test_merge_context_preserves_template_for_control_flow(self):
        """Test _merge_context preserves templates for control flow steps."""
        definition = {
            "condition": "{{ computed.can_continue }}",
            "max_iterations": 10,
            "body": [
                {
                    "id": "test_step",
                    "type": "user_message",
                    "message": "Iteration {{ raw.attempt_number }}"
                }
            ]
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/loop.ts",
            "index": 0,
            "total": 1
        }
        
        result = self.executor._merge_context(definition, task_context, "while_loop")
        
        # For while_loop, templates should be preserved for later evaluation
        # The exact behavior depends on the preserve_templates flag
        assert "condition" in result
        assert "body" in result

    def test_merge_context_with_undefined_variables(self):
        """Test _merge_context handles undefined template variables gracefully."""
        definition = {
            "message": "File: {{ file_path }}, Status: {{ undefined_variable }}, Count: {{ raw.nonexistent_field }}"
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/test.py",
            "index": 0,
            "total": 1,
            "file_path": "src/test.py"
        }
        
        result = self.executor._merge_context(definition, task_context, "user_message")
        
        # Undefined variables should be replaced with empty string or handled gracefully
        assert "File: src/test.py" in result["message"]
        # The rest depends on the error handling in the expression evaluator

    def test_debug_mode_step_creation_workflow(self):
        """Test the complete workflow of creating a debug mode step with conversion."""
        # This tests the integration in _handle_debug_serial_foreach
        
        # Raw YAML step from flattening
        next_step_def = {
            "id": "attempt_message",
            "type": "user_message", 
            "message": "Starting attempt {{ raw.attempt_number }} for {{ file_path }}"
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/component.ts",
            "index": 0,
            "total": 1
        }
        
        # Enhanced context (this would be created in the actual method)
        enhanced_context = task_context.copy()
        enhanced_context["file_path"] = "src/component.ts"
        enhanced_context["max_attempts"] = 5
        
        # Test the format conversion logic
        if "definition" in next_step_def:
            # Already in WorkflowStep format
            step_definition = next_step_def["definition"]
        else:
            # Convert from raw YAML format to WorkflowStep definition format
            step_definition = {k: v for k, v in next_step_def.items() if k not in ["id", "type"]}
        
        # Verify conversion
        assert "message" in step_definition
        assert step_definition["message"] == "Starting attempt {{ raw.attempt_number }} for {{ file_path }}"
        
        # Test variable replacement
        merged_definition = self.executor._merge_context(
            step_definition, enhanced_context, next_step_def.get("type")
        )
        
        # Verify final result
        assert merged_definition["message"] == "Starting attempt 1 for src/component.ts"

    def test_merge_context_with_array_parameters(self):
        """Test _merge_context with array parameters containing templates."""
        definition = {
            "tool": "check_typescript",
            "parameters": {
                "file_paths": ["{{ file_path }}"],
                "options": ["--strict", "--noImplicitAny"],
                "include_patterns": ["{{ file_path }}", "**/*.d.ts"]
            }
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/types.ts",
            "index": 0,
            "total": 1,
            "file_path": "src/types.ts"
        }
        
        result = self.executor._merge_context(definition, task_context, "mcp_call")
        
        # Verify array elements with templates are replaced
        assert result["parameters"]["file_paths"] == ["src/types.ts"]
        assert result["parameters"]["options"] == ["--strict", "--noImplicitAny"]  # Unchanged
        assert result["parameters"]["include_patterns"] == ["src/types.ts", "**/*.d.ts"]

    def test_merge_context_preserves_non_template_values(self):
        """Test _merge_context preserves non-template values correctly."""
        definition = {
            "tool": "lint_project", 
            "parameters": {
                "target_files": ["{{ file_path }}"],
                "use_eslint_standards": True,
                "max_warnings": 10,
                "output_format": "json"
            },
            "store_result": "lint_output",
            "timeout": 60
        }
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/main.js",
            "index": 0,
            "total": 1,
            "file_path": "src/main.js"
        }
        
        result = self.executor._merge_context(definition, task_context, "mcp_call")
        
        # Verify non-template values are preserved exactly
        assert result["tool"] == "lint_project"
        assert result["parameters"]["use_eslint_standards"] is True
        assert result["parameters"]["max_warnings"] == 10
        assert result["parameters"]["output_format"] == "json"
        assert result["store_result"] == "lint_output"
        assert result["timeout"] == 60
        
        # Verify template was replaced
        assert result["parameters"]["target_files"] == ["src/main.js"]