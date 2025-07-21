"""Test case for the while_loop condition processing bug fix.

This test ensures that while_loop conditions are properly preserved during
template processing in both normal and debug modes, specifically for sub-agent workflows.
"""

import os
import pytest
from typing import Any, Dict

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor


class TestWhileLoopConditionFix:
    """Test the while_loop condition processing bug fix."""

    def setup_method(self):
        """Set up test environment."""
        self.state_manager = StateManager()
        self.executor = QueueBasedWorkflowExecutor(self.state_manager)
        self.loader = WorkflowLoader()

    def test_while_loop_condition_preserved_in_normal_mode(self):
        """Test that while_loop conditions are preserved in normal execution mode."""
        # Load the workflow that previously failed
        workflow_def = self.loader.load("code-standards:enforce")
        
        # Start the workflow
        result = self.executor.start(workflow_def, {})
        assert "workflow_id" in result
        assert result["status"] == "running"
        
        workflow_id = result["workflow_id"]
        
        # Get next steps - this should work without the condition error
        next_step_result = self.executor.get_next_step(workflow_id)
        
        # Should not contain the while_loop condition error
        assert "error" not in next_step_result
        assert "steps" in next_step_result
        
        # Verify that parallel_foreach steps are created properly
        steps = next_step_result["steps"]
        parallel_foreach_steps = [s for s in steps if s["type"] == "parallel_foreach"]
        assert len(parallel_foreach_steps) > 0
        
        # Each parallel_foreach should have tasks with proper context
        for step in parallel_foreach_steps:
            assert "tasks" in step["definition"]
            tasks = step["definition"]["tasks"]
            assert len(tasks) > 0
            
            # Verify task structure
            for task in tasks:
                assert "task_id" in task
                assert "context" in task
                assert "inputs" in task

    def test_while_loop_condition_preserved_in_debug_mode(self):
        """Test that while_loop conditions are preserved in debug serial mode."""
        # Set debug mode
        original_debug = os.environ.get("AROMCP_WORKFLOW_DEBUG")
        os.environ["AROMCP_WORKFLOW_DEBUG"] = "serial"
        
        try:
            # Reload components to pick up debug mode
            self.state_manager = StateManager()
            self.executor = QueueBasedWorkflowExecutor(self.state_manager)
            
            # Load the workflow
            workflow_def = self.loader.load("code-standards:enforce")
            
            # Start the workflow
            result = self.executor.start(workflow_def, {})
            assert "workflow_id" in result
            workflow_id = result["workflow_id"]
            
            # Get next steps - this should expand sub-agent steps in serial mode
            next_step_result = self.executor.get_next_step(workflow_id)
            
            # Should not contain the while_loop condition error that was previously occurring
            if "data" in next_step_result and "error" in next_step_result["data"]:
                error = next_step_result["data"]["error"]
                assert "Missing 'condition' in while_loop step" not in error.get("message", "")
                
            # Should contain expanded sub-agent steps
            assert "steps" in next_step_result
            steps = next_step_result["steps"]
            
            # Look for while_loop steps that should now have preserved conditions
            while_loop_steps = [s for s in steps if s["type"] == "while_loop"]
            for step in while_loop_steps:
                condition = step["definition"].get("condition", "")
                # Condition should not be empty
                assert condition != "", f"while_loop step {step['id']} has empty condition"
                # Should contain template expression (preserved, not evaluated)
                assert "{{" in condition and "}}" in condition, f"Condition should be preserved template: {condition}"
                
        finally:
            # Restore original debug mode
            if original_debug is None:
                os.environ.pop("AROMCP_WORKFLOW_DEBUG", None)
            else:
                os.environ["AROMCP_WORKFLOW_DEBUG"] = original_debug

    def test_template_processing_preserves_control_flow_conditions(self):
        """Test that template processing correctly preserves conditions for control flow steps."""
        from aromcp.workflow_server.workflow.step_processors import StepProcessor
        from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
        from aromcp.workflow_server.workflow.models import WorkflowInstance, WorkflowStep
        
        # Create a test while_loop step with template condition
        step_definition = {
            "condition": "{{ computed.can_continue }}",
            "max_iterations": 10,
            "body": [
                {"id": "test_step", "type": "user_message", "message": "Test"}
            ]
        }
        
        step = WorkflowStep(
            id="test_while_loop",
            type="while_loop", 
            definition=step_definition
        )
        
        # Create a minimal workflow instance
        instance = WorkflowInstance(
            id="test_workflow",
            workflow_name="test",
            definition=None,
            inputs={},
            status="running"
        )
        
        # Create step processor
        expression_evaluator = ExpressionEvaluator()
        step_processor = StepProcessor(self.state_manager, expression_evaluator)
        
        # Test state that doesn't contain the computed field
        test_state = {
            "raw": {"task_id": "test_task"},
            "computed": {}  # Missing can_continue field
        }
        
        # Process template variables - this should preserve the condition
        processed = step_processor._replace_variables(
            step_definition, 
            test_state,
            preserve_conditions=False,
            instance=instance,
            preserve_templates=True  # This should preserve while_loop conditions
        )
        
        # Condition should be preserved, not replaced with empty string
        assert processed["condition"] == "{{ computed.can_continue }}"
        assert processed["max_iterations"] == 10

    def test_merge_context_preserves_while_loop_conditions(self):
        """Test that _merge_context preserves conditions for while_loop steps."""
        # Test the specific method that was causing the bug
        definition = {
            "condition": "{{ computed.can_continue }}",
            "max_iterations": 10,
            "body": []
        }
        
        task_context = {
            "item": "test_file.py",
            "task_id": "test_task",
            "index": 0
        }
        
        # This should preserve the condition for while_loop steps
        merged = self.executor._merge_context(definition, task_context, "while_loop")
        
        # The condition should be preserved, not evaluated to empty string
        assert merged["condition"] == "{{ computed.can_continue }}"
        
        # But other fields that can be resolved should be
        # (max_iterations should remain unchanged since it's not a template)
        assert merged["max_iterations"] == 10

    def test_error_tracking_includes_location_info(self):
        """Test that error tracking includes file and line number information."""
        from aromcp.workflow_server.utils.error_tracking import create_workflow_error
        
        # Create an error using the new tracking system
        error_response = create_workflow_error("Test error message", "test_workflow", "test_step")
        
        # Verify error structure
        assert "error" in error_response
        error = error_response["error"]
        
        assert error["code"] == "WORKFLOW_ERROR"
        assert error["message"] == "Test error message"
        assert error["workflow_id"] == "test_workflow" 
        assert error["step_id"] == "test_step"
        
        # Should include location information
        assert "location" in error
        location = error["location"]
        assert "file" in location
        assert "line" in location
        assert "function" in location
        
        # File should be the utility file
        assert location["file"] == "error_tracking.py"
        assert isinstance(location["line"], int)
        assert location["function"] == "create_workflow_error"

    def test_regression_no_condition_error_in_subagent(self):
        """Regression test to ensure the specific error doesn't occur anymore."""
        # Set debug mode to trigger the original bug path
        original_debug = os.environ.get("AROMCP_WORKFLOW_DEBUG")
        os.environ["AROMCP_WORKFLOW_DEBUG"] = "serial"
        
        try:
            # Reload executor to pick up debug mode
            self.executor = QueueBasedWorkflowExecutor(self.state_manager)
            
            # Load and start the workflow
            workflow_def = self.loader.load("code-standards:enforce")
            result = self.executor.start(workflow_def, {})
            workflow_id = result["workflow_id"]
            
            # Get the next steps - this previously failed
            next_step_result = self.executor.get_next_step(workflow_id)
            
            # The specific error should not occur
            if "data" in next_step_result and "error" in next_step_result["data"]:
                error_message = next_step_result["data"]["error"].get("message", "")
                assert "Missing 'condition' in while_loop step" not in error_message
                
                # If there is an error, it should have enhanced tracking
                error = next_step_result["data"]["error"]
                assert "location" in error
                assert "file" in error["location"]
                assert "line" in error["location"]
                
        finally:
            # Restore debug mode
            if original_debug is None:
                os.environ.pop("AROMCP_WORKFLOW_DEBUG", None)
            else:
                os.environ["AROMCP_WORKFLOW_DEBUG"] = original_debug


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])