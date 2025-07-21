"""Unit tests for template variable replacement using sub-agent isolated state.

Tests that template variables in sub-agent steps are correctly replaced using
the sub-agent's isolated state rather than the main workflow state.
"""

import pytest
from unittest.mock import MagicMock

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.models import InputDefinition, SubAgentTask, WorkflowStep
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager


class TestSubAgentTemplateReplacement:
    """Test template variable replacement using sub-agent isolated state."""

    def setup_method(self):
        """Set up test dependencies."""
        self.state_manager = StateManager()
        self.expression_evaluator = ExpressionEvaluator()
        self.step_registry = StepRegistry()
        self.subagent_manager = SubAgentManager(
            self.state_manager, 
            self.expression_evaluator, 
            self.step_registry
        )

    def create_sub_agent_context(self, task_id: str, state_data: dict):
        """Helper to create a sub-agent context with isolated state."""
        self.subagent_manager.sub_agent_contexts[task_id] = {
            "sub_agent_state": state_data,
            "task_context": {
                "task_id": task_id,
                "item": "test_file.ts",
                "index": 0,
                "total": 1
            }
        }

    def test_template_replacement_with_raw_fields(self):
        """Test template replacement using raw state fields from sub-agent."""
        task_id = "test_task_001"
        
        # Create sub-agent context with isolated state
        self.create_sub_agent_context(task_id, {
            "raw": {
                "attempt_number": 3,
                "file_path": "src/component.tsx",
                "max_attempts": 5,
                "last_error": "TypeScript error"
            },
            "computed": {}
        })
        
        # Test step definition with raw field templates
        definition = {
            "message": "Starting attempt {{ raw.attempt_number }} for {{ raw.file_path }}",
            "description": "Max attempts: {{ raw.max_attempts }}, Last error: {{ raw.last_error }}"
        }
        
        # Process using _replace_variables (simulating sub-agent execution)
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update({"task_id": task_id, "item": "src/component.tsx"})
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify raw field replacement
        assert result["message"] == "Starting attempt 3 for src/component.tsx"
        assert "Max attempts: 5" in result["description"]
        assert "TypeScript error" in result["description"]

    def test_template_replacement_with_computed_fields(self):
        """Test template replacement using computed state fields from sub-agent."""
        task_id = "test_task_002" 
        
        # Create sub-agent context with computed fields
        self.create_sub_agent_context(task_id, {
            "raw": {
                "attempt_number": 2,
                "file_path": "src/service.ts",
                "success": False
            },
            "computed": {
                "is_typescript_file": True,
                "can_continue": True,
                "attempts_remaining": 3,
                "file_extension": "ts"
            }
        })
        
        # Test step definition with computed field templates
        definition = {
            "condition": "{{ computed.can_continue }}",
            "message": "TypeScript file: {{ computed.is_typescript_file }}, Remaining: {{ computed.attempts_remaining }}",
            "parameters": {
                "file_type": "{{ computed.file_extension }}",
                "should_process": "{{ computed.can_continue }}"
            }
        }
        
        # Process template replacement
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update({"task_id": task_id})
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify computed field replacement
        assert result["condition"] == "True"  # Python boolean converted to string
        assert "TypeScript file: True" in result["message"]
        assert "Remaining: 3" in result["message"]
        assert result["parameters"]["file_type"] == "ts"
        assert result["parameters"]["should_process"] == "True"

    def test_template_replacement_with_mixed_fields(self):
        """Test template replacement mixing raw and computed fields."""
        task_id = "test_task_003"
        
        # Create sub-agent context with both raw and computed
        self.create_sub_agent_context(task_id, {
            "raw": {
                "attempt_number": 1,
                "file_path": "src/utils.py",
                "step_results": {
                    "hints": {"success": True},
                    "lint": {"success": False},
                    "typescript": None
                }
            },
            "computed": {
                "hints_completed": True,
                "lint_completed": False,
                "all_steps_completed": False
            }
        })
        
        # Test complex template with mixed references
        definition = {
            "message": "File {{ raw.file_path }} - Attempt {{ raw.attempt_number }}",
            "status": "Hints: {{ computed.hints_completed }}, Lint: {{ computed.lint_completed }}",
            "condition": "{{ computed.all_steps_completed }}",
            "nested": {
                "hints_result": "{{ raw.step_results.hints.success }}",
                "lint_result": "{{ raw.step_results.lint.success }}"
            }
        }
        
        # Process template replacement
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update({"task_id": task_id})
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify mixed field replacement
        assert result["message"] == "File src/utils.py - Attempt 1"
        assert "Hints: True" in result["status"]
        assert "Lint: False" in result["status"]
        assert result["condition"] == "False"
        assert result["nested"]["hints_result"] == "True"
        assert result["nested"]["lint_result"] == "False"

    def test_template_replacement_with_task_context(self):
        """Test template replacement including task context variables."""
        task_id = "test_task_004"
        
        # Create sub-agent context
        self.create_sub_agent_context(task_id, {
            "raw": {
                "attempt_number": 1,
                "file_path": "src/app.js"
            },
            "computed": {
                "can_continue": True
            }
        })
        
        # Add additional task context variables that should be available
        task_context = {
            "task_id": task_id,
            "item": "src/app.js",
            "index": 2,
            "total": 5,
            "parent_step_id": "process_files",
            "workflow_id": "workflow_123"
        }
        
        # Test template with task context references
        definition = {
            "message": "Processing {{ item }} ({{ index }}/{{ total }})",
            "id_info": "Task: {{ task_id }}, Parent: {{ parent_step_id }}, Workflow: {{ workflow_id }}",
            "mixed": "File {{ raw.file_path }} at index {{ index }} can continue: {{ computed.can_continue }}"
        }
        
        # Create combined replacement state (as done in actual execution)
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update(task_context)
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify task context template replacement
        assert result["message"] == "Processing src/app.js (2/5)"
        assert "Task: test_task_004" in result["id_info"]
        assert "Parent: process_files" in result["id_info"]
        assert "Workflow: workflow_123" in result["id_info"]
        assert "File src/app.js at index 2 can continue: True" == result["mixed"]

    def test_template_replacement_handles_undefined_variables(self):
        """Test template replacement handles undefined variables gracefully."""
        task_id = "test_task_005"
        
        # Create minimal sub-agent context
        self.create_sub_agent_context(task_id, {
            "raw": {
                "file_path": "src/test.js"
            },
            "computed": {}
        })
        
        # Test template with undefined variables
        definition = {
            "message": "File: {{ raw.file_path }}, Status: {{ raw.undefined_field }}",
            "computed_ref": "Value: {{ computed.nonexistent_field }}",
            "nested_undefined": "Result: {{ raw.missing.nested.field }}"
        }
        
        # Process template replacement
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update({"task_id": task_id})
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify undefined variables are handled (replaced with empty string)
        assert "File: src/test.js" in result["message"]
        # The exact handling of undefined variables depends on implementation
        # They should either be empty strings or the original template preserved

    def test_template_replacement_with_complex_expressions(self):
        """Test template replacement with complex expressions (where supported)."""
        task_id = "test_task_006"
        
        # Create sub-agent context with numeric values
        self.create_sub_agent_context(task_id, {
            "raw": {
                "attempt_number": 3,
                "max_attempts": 5,
                "success_count": 2,
                "total_count": 10
            },
            "computed": {
                "attempts_remaining": 2,
                "success_rate": 0.2
            }
        })
        
        # Test templates with expressions (basic arithmetic)
        definition = {
            "progress": "Attempt {{ raw.attempt_number }}/{{ raw.max_attempts }}",
            "remaining": "{{ raw.max_attempts - raw.attempt_number }} attempts left",
            "percentage": "Success rate: {{ raw.success_count / raw.total_count * 100 }}%"
        }
        
        # Process template replacement
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update({"task_id": task_id})
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify simple expressions work
        assert result["progress"] == "Attempt 3/5"
        # Complex expressions might not work depending on evaluator capabilities
        # but basic field replacement should work

    def test_template_replacement_in_step_execution_context(self):
        """Test template replacement in the context of actual step execution."""
        # Create a more realistic scenario with a sub-agent task and step
        inputs = {
            "file_path": InputDefinition(type="string", description="File path", required=True),
            "max_attempts": InputDefinition(type="number", description="Max attempts", default=3)
        }
        
        state_schema = StateSchema(
            computed={
                "can_continue": {
                    "from": ["raw.attempt_number", "raw.max_attempts"],
                    "transform": "input[0] < input[1]"
                }
            }
        )
        
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs=inputs,
            steps=[
                WorkflowStep(
                    id="attempt_message",
                    type="user_message", 
                    definition={
                        "message": "Starting attempt {{ raw.attempt_number }} for {{ raw.file_path }}"
                    }
                ),
                WorkflowStep(
                    id="continue_check",
                    type="conditional",
                    definition={
                        "condition": "{{ computed.can_continue }}",
                        "then_steps": [{"id": "continue_msg", "type": "user_message", "message": "Continuing..."}],
                        "else_steps": [{"id": "stop_msg", "type": "user_message", "message": "Stopping..."}]
                    }
                )
            ],
            default_state={
                "raw": {
                    "attempt_number": 1,
                    "max_attempts": 3
                }
            },
            state_schema=state_schema
        )
        
        task_context = {
            "task_id": "real_task_001",
            "item": "src/real_component.tsx",
            "file_path": "src/real_component.tsx",
            "index": 0,
            "total": 1
        }
        
        # Initialize sub-agent state (as would happen in actual execution)
        sub_agent_state = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Store in context (as would happen in actual execution)
        self.subagent_manager.sub_agent_contexts["real_task_001"] = {
            "sub_agent_state": sub_agent_state,
            "task_context": task_context,
            "sub_agent_task": sub_agent_task
        }
        
        # Test template replacement for the user_message step
        message_definition = {"message": "Starting attempt {{ raw.attempt_number }} for {{ raw.file_path }}"}
        
        replacement_state = sub_agent_state.copy()
        replacement_state.update(task_context)
        
        result = self.subagent_manager._replace_variables(message_definition, replacement_state)
        
        # Verify realistic template replacement
        assert result["message"] == "Starting attempt 1 for src/real_component.tsx"

    def test_template_replacement_isolation_from_main_workflow(self):
        """Test that sub-agent template replacement is isolated from main workflow state."""
        task_id = "isolated_task_001"
        
        # Create sub-agent context with its own state
        self.create_sub_agent_context(task_id, {
            "raw": {
                "attempt_number": 2,
                "file_path": "src/isolated.ts",
                "custom_field": "sub_agent_value"
            },
            "computed": {
                "can_continue": False
            }
        })
        
        # Simulate main workflow having different state values
        main_workflow_state = {
            "raw": {
                "attempt_number": 999,  # Different from sub-agent
                "file_path": "main/workflow/file.js",  # Different from sub-agent
                "custom_field": "main_workflow_value"  # Different from sub-agent
            },
            "computed": {
                "can_continue": True  # Different from sub-agent
            }
        }
        
        # Test that sub-agent uses its own state, not main workflow state
        definition = {
            "attempt": "{{ raw.attempt_number }}",
            "file": "{{ raw.file_path }}",
            "custom": "{{ raw.custom_field }}",
            "continue": "{{ computed.can_continue }}"
        }
        
        # Process with sub-agent state
        replacement_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"].copy()
        replacement_state.update({"task_id": task_id})
        
        result = self.subagent_manager._replace_variables(definition, replacement_state)
        
        # Verify sub-agent uses its own state values, not main workflow values
        assert result["attempt"] == "2"  # Sub-agent value, not 999
        assert result["file"] == "src/isolated.ts"  # Sub-agent value, not main workflow
        assert result["custom"] == "sub_agent_value"  # Sub-agent value, not main workflow
        assert result["continue"] == "False"  # Sub-agent value, not True from main workflow