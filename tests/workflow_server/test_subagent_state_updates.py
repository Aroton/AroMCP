"""Test sub-agent state update functionality after the fix."""

import pytest
from unittest.mock import MagicMock

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.models import WorkflowStep
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager


class TestSubAgentStateUpdates:
    """Test that sub-agent state updates work correctly after the fix."""

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

    def test_sub_agent_state_update_step_processing(self):
        """Test that state_update steps are processed within sub-agent execution."""
        task_id = "test_state_update_001"
        
        # Set up sub-agent context
        self.subagent_manager.sub_agent_contexts[task_id] = {
            "sub_agent_state": {
                "raw": {
                    "attempt_number": 1,
                    "file_path": "src/test.ts"
                },
                "computed": {}
            },
            "task_context": {
                "task_id": task_id,
                "item": "src/test.ts",
                "index": 0,
                "total": 1
            }
        }
        
        # Create a shell_command with state_update step like the one in the workflow
        state_update_step = WorkflowStep(
            id="analyze_failure_reason",
            type="shell_command",
            definition={
                "command": "echo 'analyzing failure'",
                "state_update": {
                    "path": "raw.failure_analysis",
                    "value": "Test failure reason"
                }
            }
        )
        
        # Get the current context for the method call
        context = self.subagent_manager.sub_agent_contexts[task_id]
        current_state = context["sub_agent_state"].copy()
        current_state.update(context["task_context"])
        
        # Process the state update step (method returns None on success)
        try:
            self.subagent_manager._process_sub_agent_server_step(
                state_update_step, current_state, context
            )
            success = True
        except Exception as e:
            success = False
            print(f"State update failed: {e}")
        
        # Should not raise an exception
        assert success, "State update should succeed without raising an exception"
        
        # Verify the state was updated
        updated_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"]
        assert "failure_analysis" in updated_state["raw"]
        assert updated_state["raw"]["failure_analysis"] == "Test failure reason"

    def test_failure_analysis_template_resolution(self):
        """Test the actual failure analysis scenario that was failing."""
        task_id = "failure_analysis_test"
        
        # Set up sub-agent context with realistic failure state
        self.subagent_manager.sub_agent_contexts[task_id] = {
            "sub_agent_state": {
                "raw": {
                    "attempt_number": 2,
                    "file_path": "src/component.tsx"
                },
                "computed": {
                    "hints_completed": True,
                    "lint_completed": False,  # This causes the failure
                    "typescript_completed": False,
                    "is_typescript_file": True
                }
            },
            "task_context": {
                "task_id": task_id,
                "item": "src/component.tsx",
                "file_path": "src/component.tsx",
                "max_attempts": 10
            }
        }
        
        # Step 1: Process the failure analysis state update
        analyze_step = WorkflowStep(
            id="analyze_failure_reason",
            type="state_update", 
            definition={
                "path": "raw.failure_analysis",
                "value": """{{
                    !computed.hints_completed ? 'Hints step failed or never completed' :
                    !computed.lint_completed ? 'Linting errors not resolved' :
                    computed.is_typescript_file && !computed.typescript_completed ? 'TypeScript errors not resolved' :
                    raw.attempt_number >= max_attempts ? 'Maximum attempts exceeded' :
                    'Unknown failure condition'
                }}"""
            }
        )
        
        # Get context and current state
        context = self.subagent_manager.sub_agent_contexts[task_id]
        current_state = context["sub_agent_state"].copy()
        current_state.update(context["task_context"])
        
        # Process the state update
        try:
            self.subagent_manager._process_sub_agent_server_step(
                analyze_step, current_state, context
            )
            success = True
        except Exception as e:
            success = False
            print(f"Failure analysis step failed: {e}")
        
        assert success, "Failure analysis step should succeed"
        
        # Step 2: Verify the failure analysis was computed correctly
        updated_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"]
        assert "failure_analysis" in updated_state["raw"]
        assert updated_state["raw"]["failure_analysis"] == "Linting errors not resolved"
        
        # Step 3: Test that subsequent template replacement works
        failure_message_template = "🔍 Failure Analysis: {{ raw.failure_analysis }}"
        
        # Get current state for template replacement
        replacement_state = updated_state.copy()
        replacement_state.update(self.subagent_manager.sub_agent_contexts[task_id]["task_context"])
        
        result_message = self.subagent_manager._replace_variables(
            failure_message_template, replacement_state
        )
        
        # Should now show the actual failure reason, not a placeholder
        expected = "🔍 Failure Analysis: Linting errors not resolved"
        assert result_message == expected, f"Expected '{expected}', got '{result_message}'"

    def test_complex_state_update_with_nested_paths(self):
        """Test state updates with complex nested paths."""
        task_id = "nested_state_test"
        
        # Set up sub-agent context
        self.subagent_manager.sub_agent_contexts[task_id] = {
            "sub_agent_state": {
                "raw": {
                    "step_results": {
                        "hints": None,
                        "lint": None
                    }
                }
            },
            "task_context": {"task_id": task_id}
        }
        
        # Test updating nested path
        update_step = WorkflowStep(
            id="update_lint_results",
            type="state_update",
            definition={
                "path": "raw.step_results.lint",
                "value": {
                    "success": False,
                    "errors": 5,
                    "error_details": ["Missing semicolon", "Unused variable"]
                }
            }
        )
        
        # Get context and current state  
        context = self.subagent_manager.sub_agent_contexts[task_id]
        current_state = context["sub_agent_state"].copy()
        current_state.update(context["task_context"])
        
        # Process the update
        try:
            self.subagent_manager._process_sub_agent_server_step(
                update_step, current_state, context
            )
            success = True
        except Exception as e:
            success = False
            print(f"Nested state update failed: {e}")
        
        assert success, "Nested state update should succeed"
        
        # Verify nested update worked
        updated_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"]
        lint_result = updated_state["raw"]["step_results"]["lint"]
        
        assert lint_result["success"] is False
        assert lint_result["errors"] == 5
        assert len(lint_result["error_details"]) == 2
        assert "Missing semicolon" in lint_result["error_details"]

    def test_state_update_isolation_between_sub_agents(self):
        """Test that state updates are isolated between different sub-agents."""
        task_id_1 = "isolated_task_001"
        task_id_2 = "isolated_task_002"
        
        # Set up two sub-agent contexts
        for task_id in [task_id_1, task_id_2]:
            self.subagent_manager.sub_agent_contexts[task_id] = {
                "sub_agent_state": {"raw": {"shared_field": "initial_value"}},
                "task_context": {"task_id": task_id}
            }
        
        # Update only the first sub-agent's state
        update_step = WorkflowStep(
            id="update_first_agent",
            type="state_update", 
            definition={
                "path": "raw.shared_field",
                "value": "updated_by_first_agent"
            }
        )
        
        # Get context and current state for first agent
        context_1 = self.subagent_manager.sub_agent_contexts[task_id_1] 
        current_state_1 = context_1["sub_agent_state"].copy()
        current_state_1.update(context_1["task_context"])
        
        try:
            self.subagent_manager._process_sub_agent_server_step(
                update_step, current_state_1, context_1
            )
            success = True
        except Exception as e:
            success = False
            print(f"State update failed: {e}")
        
        assert success, "State update should succeed"
        
        # Verify isolation: first agent updated, second unchanged
        state_1 = self.subagent_manager.sub_agent_contexts[task_id_1]["sub_agent_state"]
        state_2 = self.subagent_manager.sub_agent_contexts[task_id_2]["sub_agent_state"]
        
        assert state_1["raw"]["shared_field"] == "updated_by_first_agent"
        assert state_2["raw"]["shared_field"] == "initial_value"  # Unchanged

    def test_template_replacement_after_state_update_sequence(self):
        """Test that template replacement sees state updates from the same sub-agent execution."""
        task_id = "template_sequence_test"
        
        # Set up sub-agent context
        self.subagent_manager.sub_agent_contexts[task_id] = {
            "sub_agent_state": {
                "raw": {
                    "step_count": 0,
                    "status": "starting"
                }
            },
            "task_context": {"task_id": task_id}
        }
        
        # Sequence of state updates
        steps = [
            WorkflowStep(
                id="increment_step_count",
                type="state_update",
                definition={"path": "raw.step_count", "value": 1}
            ),
            WorkflowStep(
                id="update_status",
                type="state_update", 
                definition={"path": "raw.status", "value": "processing"}
            ),
            WorkflowStep(
                id="increment_again",
                type="state_update",
                definition={"path": "raw.step_count", "value": 2}
            )
        ]
        
        # Process each state update step
        for step in steps:
            # Get current context and state for each step
            context = self.subagent_manager.sub_agent_contexts[task_id]
            current_state = context["sub_agent_state"].copy()
            current_state.update(context["task_context"])
            
            try:
                self.subagent_manager._process_sub_agent_server_step(
                    step, current_state, context
                )
                success = True
            except Exception as e:
                success = False
                print(f"Step {step.id} failed: {e}")
            
            assert success, f"Step {step.id} should succeed"
        
        # Test template that should see all the updates
        template = "Status: {{ raw.status }}, Completed {{ raw.step_count }} steps"
        
        # Get current state for template replacement  
        current_state = self.subagent_manager.sub_agent_contexts[task_id]["sub_agent_state"]
        replacement_state = current_state.copy()
        replacement_state.update({"task_id": task_id})
        
        result = self.subagent_manager._replace_variables(template, replacement_state)
        
        expected = "Status: processing, Completed 2 steps"
        assert result == expected, f"Expected '{expected}', got '{result}'"