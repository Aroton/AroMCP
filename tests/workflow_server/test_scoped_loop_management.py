"""Tests for scoped loop management in the MCP Workflow System.

This test suite validates that loop variables (loop.item, loop.index, loop.iteration)
work correctly in scoped contexts with proper isolation for nested loops.
"""

import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.aromcp.workflow_server.state.manager import StateManager
from src.aromcp.workflow_server.state.models import WorkflowState
from src.aromcp.workflow_server.workflow.context import ExecutionContext
from src.aromcp.workflow_server.workflow.control_flow import LoopState
from src.aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from src.aromcp.workflow_server.workflow.models import WorkflowInstance, WorkflowStep
from src.aromcp.workflow_server.workflow.queue import WorkflowQueue
from src.aromcp.workflow_server.workflow.step_processors import StepProcessor


class TestScopedLoopManagement:
    """Test suite for scoped loop variable management."""

    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = StateManager()
        self.expression_evaluator = ExpressionEvaluator()
        self.step_processor = StepProcessor(self.state_manager, self.expression_evaluator)

        # Create test workflow instance
        from src.aromcp.workflow_server.state.models import StateSchema
        from src.aromcp.workflow_server.workflow.models import WorkflowDefinition

        test_definition = WorkflowDefinition(
            name="test_workflow",
            description="Test workflow for loop scoping",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[],
        )

        self.workflow_instance = WorkflowInstance(
            id="test_workflow",
            workflow_name="test_workflow",
            definition=test_definition,
            inputs={"test_files": ["file1.txt", "file2.txt", "file3.txt"]},
            status="running",
            created_at=datetime.now().isoformat(),
        )

        # Initialize workflow state
        initial_state = WorkflowState(inputs=self.workflow_instance.inputs, state={}, computed={})
        # Directly set the state in the state manager
        self.state_manager._states["test_workflow"] = initial_state

    def teardown_method(self):
        """Clean up after tests."""
        # Clean up state
        try:
            self.state_manager.delete("test_workflow")
        except:
            pass

    def test_foreach_loop_scoped_variables(self):
        """Test that foreach loops create proper scoped loop variables."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Create foreach loop state
        items = ["file1.txt", "file2.txt", "file3.txt"]
        loop_state = LoopState(loop_type="foreach", loop_id="foreach_test", items=items, max_iterations=len(items))

        # Test initial preparation
        loop_state.prepare_for_iteration()
        assert loop_state.variable_bindings["item"] == "file1.txt"
        assert loop_state.variable_bindings["index"] == 0

        # Test entering loop context
        context.enter_loop(loop_state)
        current_loop = context.current_loop()
        assert current_loop is not None
        assert current_loop.variable_bindings["item"] == "file1.txt"
        assert current_loop.variable_bindings["index"] == 0

        # Test scoped variables access
        scoped_vars = context.get_scoped_variables()
        assert "loop" in scoped_vars
        assert scoped_vars["loop"]["item"] == "file1.txt"
        assert scoped_vars["loop"]["index"] == 0

        # Test advancing iteration
        current_loop.advance_iteration()
        assert current_loop.variable_bindings["item"] == "file2.txt"
        assert current_loop.variable_bindings["index"] == 1

        # Test scoped variables after advance
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["item"] == "file2.txt"
        assert scoped_vars["loop"]["index"] == 1

    def test_while_loop_scoped_variables(self):
        """Test that while loops create proper scoped loop variables."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Create while loop state
        loop_state = LoopState(loop_type="while", loop_id="while_test", max_iterations=5)

        # Test initial preparation
        loop_state.prepare_for_iteration()
        assert loop_state.variable_bindings["iteration"] == 1  # 1-based for while loops

        # Test entering loop context
        context.enter_loop(loop_state)
        current_loop = context.current_loop()
        assert current_loop is not None
        assert current_loop.variable_bindings["iteration"] == 1

        # Test scoped variables access
        scoped_vars = context.get_scoped_variables()
        assert "loop" in scoped_vars
        assert scoped_vars["loop"]["iteration"] == 1

        # Test advancing iteration
        current_loop.advance_iteration()
        assert current_loop.variable_bindings["iteration"] == 2

        # Test scoped variables after advance
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["iteration"] == 2

    def test_nested_loops_variable_isolation(self):
        """Test that nested loops have proper variable isolation."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Create outer foreach loop
        outer_items = ["outer1", "outer2"]
        outer_loop = LoopState(
            loop_type="foreach", loop_id="outer_loop", items=outer_items, max_iterations=len(outer_items)
        )
        outer_loop.prepare_for_iteration()
        context.enter_loop(outer_loop)

        # Verify outer loop variables
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["item"] == "outer1"
        assert scoped_vars["loop"]["index"] == 0

        # Create inner while loop
        inner_loop = LoopState(loop_type="while", loop_id="inner_loop", max_iterations=3)
        inner_loop.prepare_for_iteration()
        context.enter_loop(inner_loop)

        # Verify nested loop variables (inner should take precedence)
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["iteration"] == 1  # From inner while loop
        assert scoped_vars["loop"]["item"] == "outer1"  # From outer foreach loop
        assert scoped_vars["loop"]["index"] == 0  # From outer foreach loop

        # Advance inner loop
        inner_loop.advance_iteration()
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["iteration"] == 2  # Updated inner loop
        assert scoped_vars["loop"]["item"] == "outer1"  # Unchanged outer loop

        # Exit inner loop
        context.exit_loop()
        scoped_vars = context.get_scoped_variables()
        assert "iteration" not in scoped_vars["loop"]  # Inner loop variables cleared
        assert scoped_vars["loop"]["item"] == "outer1"  # Outer loop variables remain
        assert scoped_vars["loop"]["index"] == 0

    def test_expression_evaluation_with_loop_variables(self):
        """Test expression evaluation using scoped loop variables."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Create foreach loop with test data
        items = [{"name": "file1.txt", "size": 100}, {"name": "file2.txt", "size": 200}]
        loop_state = LoopState(loop_type="foreach", loop_id="expr_test", items=items, max_iterations=len(items))
        loop_state.prepare_for_iteration()
        context.enter_loop(loop_state)

        # Build scoped context
        state = self.state_manager.read("test_workflow")
        scoped_context = self.step_processor._build_scoped_context(self.workflow_instance, state, context)

        # Test loop variable access in expressions
        result = self.expression_evaluator.evaluate("loop.item.name", state, scoped_context)
        assert result == "file1.txt"

        result = self.expression_evaluator.evaluate("loop.item.size", state, scoped_context)
        assert result == 100

        result = self.expression_evaluator.evaluate("loop.index", state, scoped_context)
        assert result == 0

        # Advance and test again
        current_loop = context.current_loop()
        current_loop.advance_iteration()

        # Rebuild scoped context after advance
        scoped_context = self.step_processor._build_scoped_context(self.workflow_instance, state, context)

        result = self.expression_evaluator.evaluate("loop.item.name", state, scoped_context)
        assert result == "file2.txt"

        result = self.expression_evaluator.evaluate("loop.index", state, scoped_context)
        assert result == 1

    def test_foreach_step_processor_integration(self):
        """Test foreach step processor with scoped loop variables."""
        # Create execution context
        context = ExecutionContext("test_workflow")
        queue = WorkflowQueue("test_workflow", [])

        # Create foreach step
        foreach_step = WorkflowStep(
            id="test_foreach",
            type="foreach",
            definition={
                "items": "{{inputs.test_files}}",
                "body": [
                    {
                        "id": "body_step",
                        "type": "shell_command",
                        "command": "echo {{loop.item}} at index {{loop.index}}",
                    }
                ],
            },
        )

        # Get current state
        state = self.state_manager.read("test_workflow")

        # Process the foreach step
        result = self.step_processor.process_foreach(
            self.workflow_instance, foreach_step, foreach_step.definition, queue, state, context
        )

        # Verify loop was created properly
        current_loop = context.current_loop()
        assert current_loop is not None
        assert current_loop.loop_type == "foreach"
        assert current_loop.variable_bindings["item"] == "file1.txt"
        assert current_loop.variable_bindings["index"] == 0

        # Verify steps were added to queue
        assert len(queue.main_queue) > 0

    def test_while_step_processor_integration(self):
        """Test while step processor with scoped loop variables."""
        # Set up initial state for while loop condition
        self.state_manager.update("test_workflow", [{"path": "state.counter", "value": 0}])

        # Create execution context
        context = ExecutionContext("test_workflow")
        queue = WorkflowQueue("test_workflow", [])

        # Create while step
        while_step = WorkflowStep(
            id="test_while",
            type="while_loop",
            definition={
                "condition": "state.counter < 3",  # No template braces - direct expression
                "max_iterations": 5,
                "body": [{"id": "body_step", "type": "shell_command", "command": "echo Iteration {{loop.iteration}}"}],
            },
        )

        # Get current state
        state = self.state_manager.read("test_workflow")

        # Process the while step
        result = self.step_processor.process_while_loop(
            self.workflow_instance, while_step, while_step.definition, queue, state, context
        )

        # Verify the loop was processed successfully
        assert result["executed"] == False  # Loop continues
        assert "iteration" in result  # Shows loop is running

    def test_loop_variable_cleanup(self):
        """Test that loop variables are properly cleaned up when loops exit."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Create and enter loop
        loop_state = LoopState(loop_type="foreach", loop_id="cleanup_test", items=["item1", "item2"], max_iterations=2)
        loop_state.prepare_for_iteration()
        context.enter_loop(loop_state)

        # Verify variables exist
        scoped_vars = context.get_scoped_variables()
        assert "item" in scoped_vars["loop"]
        assert "index" in scoped_vars["loop"]

        # Exit loop
        exited_loop = context.exit_loop()
        assert exited_loop is not None

        # Verify variables are cleaned up
        scoped_vars = context.get_scoped_variables()
        assert len(scoped_vars["loop"]) == 0

    def test_loop_variable_template_replacement(self):
        """Test template replacement using loop variables."""
        # Create execution context with loop
        context = ExecutionContext("test_workflow")

        loop_state = LoopState(
            loop_type="foreach", loop_id="template_test", items=[{"file": "test.txt", "type": "text"}], max_iterations=1
        )
        loop_state.prepare_for_iteration()
        context.enter_loop(loop_state)

        # Get current state
        state = self.state_manager.read("test_workflow")

        # Test template replacement with loop variables
        template_string = "Processing {{loop.item.file}} of type {{loop.item.type}} at index {{loop.index}}"
        result = self.step_processor._replace_variables(
            template_string, state, False, self.workflow_instance, False, context
        )

        expected = "Processing test.txt of type text at index 0"
        assert result == expected

    def test_nested_foreach_loops(self):
        """Test nested foreach loops with proper variable isolation."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Outer loop
        outer_items = [["inner1", "inner2"], ["inner3", "inner4"]]
        outer_loop = LoopState(loop_type="foreach", loop_id="outer", items=outer_items, max_iterations=len(outer_items))
        outer_loop.prepare_for_iteration()
        context.enter_loop(outer_loop)

        # Inner loop
        inner_items = outer_items[0]  # First inner array
        inner_loop = LoopState(loop_type="foreach", loop_id="inner", items=inner_items, max_iterations=len(inner_items))
        inner_loop.prepare_for_iteration()
        context.enter_loop(inner_loop)

        # Check nested variables
        scoped_vars = context.get_scoped_variables()
        # Inner loop variables should override outer loop variables of same name
        assert scoped_vars["loop"]["item"] == "inner1"  # From inner loop
        assert scoped_vars["loop"]["index"] == 0  # From inner loop (both have index 0)

        # Advance inner loop
        inner_loop.advance_iteration()
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["item"] == "inner2"  # Inner loop advanced
        assert scoped_vars["loop"]["index"] == 1  # Inner loop advanced

        # Exit inner loop
        context.exit_loop()
        scoped_vars = context.get_scoped_variables()
        # Should revert to outer loop variables
        assert scoped_vars["loop"]["item"] == ["inner1", "inner2"]  # Outer loop item
        assert scoped_vars["loop"]["index"] == 0  # Outer loop index

    def test_mixed_loop_types_nesting(self):
        """Test nesting different types of loops (foreach inside while)."""
        # Create execution context
        context = ExecutionContext("test_workflow")

        # Outer while loop
        while_loop = LoopState(loop_type="while", loop_id="while_outer", max_iterations=3)
        while_loop.prepare_for_iteration()
        context.enter_loop(while_loop)

        # Inner foreach loop
        items = ["a", "b", "c"]
        foreach_loop = LoopState(loop_type="foreach", loop_id="foreach_inner", items=items, max_iterations=len(items))
        foreach_loop.prepare_for_iteration()
        context.enter_loop(foreach_loop)

        # Check mixed loop variables
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["iteration"] == 1  # From while loop
        assert scoped_vars["loop"]["item"] == "a"  # From foreach loop
        assert scoped_vars["loop"]["index"] == 0  # From foreach loop

        # Advance foreach
        foreach_loop.advance_iteration()
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["iteration"] == 1  # Unchanged while
        assert scoped_vars["loop"]["item"] == "b"  # Advanced foreach
        assert scoped_vars["loop"]["index"] == 1  # Advanced foreach

        # Exit foreach, advance while
        context.exit_loop()
        while_loop.advance_iteration()
        scoped_vars = context.get_scoped_variables()
        assert scoped_vars["loop"]["iteration"] == 2  # Advanced while
        assert "item" not in scoped_vars["loop"]  # Foreach variables cleared
        assert "index" not in scoped_vars["loop"]  # Foreach variables cleared
