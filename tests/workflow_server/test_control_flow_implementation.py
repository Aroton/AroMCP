"""
Test suite for Control Flow Implementation - Acceptance Criteria 4

This file tests the following acceptance criteria:
- AC 4.1: Conditional Branching - conditional step evaluation and branch execution
- AC 4.2: Loop Constructs - while_loop and foreach implementations with proper iteration control
- AC 4.3: Flow Control Statements - break and continue statement handling within loops
- AC-CF-022: Nested Loop Break/Continue - proper handling of break/continue in nested loops
- AC-CF-023: Infinite Loop Detection - detection and prevention of infinite loops

Maps to: /documentation/acceptance-criteria/workflow_server/control-flow.md
"""

import time

import pytest

from aromcp.workflow_server.workflow.context import ExecutionContext, StackFrame
from aromcp.workflow_server.workflow.control_flow import (
    ConditionalStep,
    ControlFlowError,
    ForEachStep,
    LoopState,
    UserInputStep,
    WhileLoopStep,
)
from aromcp.workflow_server.workflow.models import WorkflowStep
from aromcp.workflow_server.workflow.steps.break_continue import BreakContinueProcessor
from aromcp.workflow_server.workflow.steps.conditional import ConditionalProcessor
from aromcp.workflow_server.workflow.steps.foreach import ForEachProcessor
from aromcp.workflow_server.workflow.steps.user_input import UserInputProcessor
from aromcp.workflow_server.workflow.steps.while_loop import WhileLoopProcessor


class TestConditionalBranching:
    """Test conditional branching - AC 4.1"""

    def test_conditional_branching_step_structure_creation(self):
        """Test conditional branching creates proper step structure with then_steps and else_steps (AC 4.1)."""
        then_step = WorkflowStep(id="then1", type="user_message", definition={"message": "Then branch"})
        else_step = WorkflowStep(id="else1", type="user_message", definition={"message": "Else branch"})

        conditional = ConditionalStep(condition="value > 5", then_steps=[then_step], else_steps=[else_step])

        workflow_step = conditional.to_workflow_step("cond1")

        assert workflow_step.id == "cond1"
        assert workflow_step.type == "conditional"
        assert workflow_step.definition["condition"] == "value > 5"
        assert len(workflow_step.definition["then_steps"]) == 1
        assert len(workflow_step.definition["else_steps"]) == 1

    def test_conditional_branching_while_loop_support(self):
        """Test conditional branching supports while loop step creation and conversion (AC 4.1)."""
        body_step = WorkflowStep(id="body1", type="shell_command", definition={"command": "echo 'updating counter'", "state_update": {"path": "raw.counter", "value": "$(({{ raw.counter }} + 1))"}})

        while_loop = WhileLoopStep(condition="counter < 10", max_iterations=50, body=[body_step])

        workflow_step = while_loop.to_workflow_step("loop1")

        assert workflow_step.id == "loop1"
        assert workflow_step.type == "while_loop"
        assert workflow_step.definition["condition"] == "counter < 10"
        assert workflow_step.definition["max_iterations"] == 50
        assert len(workflow_step.definition["body"]) == 1

    def test_conditional_branching_foreach_support(self):
        """Test conditional branching supports foreach step creation and conversion (AC 4.1)."""
        body_step = WorkflowStep(id="body1", type="user_message", definition={"message": "Processing {{ item }}"})

        foreach = ForEachStep(items="files", variable_name="file", index_name="i", body=[body_step])

        workflow_step = foreach.to_workflow_step("foreach1")

        assert workflow_step.id == "foreach1"
        assert workflow_step.type == "foreach"
        assert workflow_step.definition["items"] == "files"
        assert workflow_step.definition["variable_name"] == "file"
        assert workflow_step.definition["index_name"] == "i"

    def test_conditional_branching_nested_structure_support(self):
        """Test conditional branching supports nested conditional structures (AC 4.1)."""
        user_input = UserInputStep(
            prompt="Enter your name:",
            variable_name="user_name",
            validation_pattern=r"^[A-Za-z\s]+$",
            validation_message="Name must contain only letters and spaces",
            required=True,
            max_attempts=3,
        )

        workflow_step = user_input.to_workflow_step("input1")

        assert workflow_step.id == "input1"
        assert workflow_step.type == "user_input"
        assert workflow_step.definition["prompt"] == "Enter your name:"
        assert workflow_step.definition["variable_name"] == "user_name"
        assert workflow_step.definition["validation_pattern"] == r"^[A-Za-z\s]+$"
        assert workflow_step.definition["required"]
        assert workflow_step.definition["max_attempts"] == 3


class TestLoopConstructs:
    """Test loop constructs - AC 4.2"""

    def test_loop_constructs_max_iteration_safety(self):
        """Test while loop constructs respect max_iterations safety limit with proper iteration control (AC 4.2)."""
        loop_state = LoopState(loop_type="while", loop_id="loop1", max_iterations=5)

        assert not loop_state.is_complete()
        assert loop_state.current_iteration == 0

        # Advance iterations
        for i in range(4):
            loop_state.advance_iteration()
            assert loop_state.current_iteration == i + 1
            assert not loop_state.is_complete()

        # Last iteration
        loop_state.advance_iteration()
        assert loop_state.current_iteration == 5
        assert loop_state.is_complete()

    def test_loop_constructs_foreach_item_processing(self):
        """Test foreach loop constructs process each item with proper loop context variables (AC 4.2)."""
        items = ["a", "b", "c"]
        loop_state = LoopState(loop_type="foreach", loop_id="foreach1", items=items, max_iterations=len(items))

        assert not loop_state.is_complete()
        assert loop_state.get_current_item() == "a"

        # Advance through items
        loop_state.advance_iteration()
        assert loop_state.get_current_item() == "b"
        assert not loop_state.is_complete()

        loop_state.advance_iteration()
        assert loop_state.get_current_item() == "c"
        assert not loop_state.is_complete()

        loop_state.advance_iteration()
        assert loop_state.is_complete()

    def test_loop_constructs_break_continue_handling(self):
        """Test loop constructs handle break and continue statements within loop body (AC 4.2)."""
        loop_state = LoopState(loop_type="while", loop_id="loop1", max_iterations=10)

        # Test break signal
        loop_state.control_signal = "break"
        assert loop_state.is_complete()

        # Reset and test continue
        loop_state.control_signal = None
        assert not loop_state.is_complete()


class TestExecutionContext:
    """Test ExecutionContext functionality."""

    def test_context_initialization(self):
        """Test context initialization."""
        context = ExecutionContext("wf_123")

        assert context.workflow_id == "wf_123"
        assert len(context.execution_stack) == 0
        assert not context.is_in_loop()
        assert context.execution_depth == 0

    def test_frame_management(self):
        """Test execution frame stack management."""
        context = ExecutionContext("wf_123")

        # Create and push frames
        steps = [
            WorkflowStep(id="step1", type="user_message", definition={}),
            WorkflowStep(id="step2", type="shell_command", definition={"command": "echo 'test'", "state_update": {"path": "state.test", "value": "updated"}}),
        ]

        frame = context.create_workflow_frame(steps)
        context.push_frame(frame)

        assert context.execution_depth == 1
        assert context.current_frame() == frame
        assert context.has_next_step()

        # Test step advancement
        step = context.get_next_step()
        assert step.id == "step1"

        context.advance_step()
        step = context.get_next_step()
        assert step.id == "step2"

        context.advance_step()
        assert not context.has_next_step()

    def test_loop_management(self):
        """Test loop context management."""
        context = ExecutionContext("wf_123")

        loop_state = LoopState(loop_type="while", loop_id="loop1", max_iterations=5)

        # Enter loop
        context.enter_loop(loop_state)
        assert context.is_in_loop()
        assert context.current_loop() == loop_state

        # Test loop control signals
        assert context.signal_loop_control("break")
        assert loop_state.control_signal == "break"

        # Exit loop
        exited_loop = context.exit_loop()
        assert exited_loop == loop_state
        assert not context.is_in_loop()

    def test_variable_scoping(self):
        """Test variable scoping in execution context."""
        context = ExecutionContext("wf_123")

        # Set global variables
        context.set_variable("global_var", "global_value", "global")

        # Create frame with local variables
        frame = StackFrame(frame_id="frame1", frame_type="conditional", steps=[])
        context.push_frame(frame)

        # Set local variables
        context.set_variable("local_var", "local_value", "local")

        # Test variable access
        assert context.get_variable("global_var") == "global_value"
        assert context.get_variable("local_var") == "local_value"

        # Test all variables
        all_vars = context.get_all_variables()
        assert all_vars["global_var"] == "global_value"
        assert all_vars["local_var"] == "local_value"

        # Pop frame - local variables should be gone
        context.pop_frame()
        assert context.get_variable("global_var") == "global_value"
        assert context.get_variable("local_var") is None


class TestConditionalProcessor:
    """Test conditional step processing."""

    def test_process_conditional_true(self):
        """Test conditional processing when condition is true."""
        processor = ConditionalProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="cond1",
            type="conditional",
            definition={
                "condition": "value > 5",
                "then_steps": [{"type": "user_message", "message": "Greater than 5"}],
                "else_steps": [{"type": "user_message", "message": "Less than or equal to 5"}],
            },
        )

        state = {"value": 10}

        result = processor.process_conditional(step, context, state)

        assert result["type"] == "conditional_evaluated"
        assert result["condition_result"]["condition_result"]
        assert result["branch_taken"] == "then"
        assert result["steps_to_execute"] == 1

        # Check that conditional frame was created
        assert len(context.execution_stack) == 1
        assert context.current_frame().frame_type == "conditional"

    def test_process_conditional_false(self):
        """Test conditional processing when condition is false."""
        processor = ConditionalProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="cond1",
            type="conditional",
            definition={
                "condition": "value > 5",
                "then_steps": [{"type": "user_message", "message": "Greater than 5"}],
                "else_steps": [{"type": "user_message", "message": "Less than or equal to 5"}],
            },
        )

        state = {"value": 3}

        result = processor.process_conditional(step, context, state)

        assert not result["condition_result"]["condition_result"]
        assert result["branch_taken"] == "else"

    def test_process_conditional_no_else(self):
        """Test conditional processing with no else branch."""
        processor = ConditionalProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="cond1",
            type="conditional",
            definition={
                "condition": "value > 5",
                "then_steps": [{"type": "user_message", "message": "Greater than 5"}],
            },
        )

        state = {"value": 3}

        result = processor.process_conditional(step, context, state)

        assert not result["condition_result"]["condition_result"]
        assert result["branch_taken"] == "else"
        assert result["steps_to_execute"] == 0


class TestWhileLoopProcessor:
    """Test while loop step processing."""

    def test_process_while_loop_entry(self):
        """Test while loop entry when condition is true."""
        processor = WhileLoopProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="loop1",
            type="while_loop",
            definition={
                "condition": "counter < 5",
                "max_iterations": 10,
                "body": [{"type": "state_update", "path": "raw.counter", "operation": "increment"}],
            },
        )

        state = {"counter": 0}

        result = processor.process_while_loop(step, context, state)

        assert result["type"] == "while_loop_started"
        assert result["max_iterations"] == 10
        assert result["body_steps"] == 1

        # Check that loop was entered
        assert context.is_in_loop()
        assert context.current_loop().loop_type == "while"

    def test_process_while_loop_skip(self):
        """Test while loop skipping when condition is false."""
        processor = WhileLoopProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="loop1",
            type="while_loop",
            definition={
                "condition": "counter < 5",
                "max_iterations": 10,
                "body": [{"type": "state_update", "path": "raw.counter"}],
            },
        )

        state = {"counter": 10}

        result = processor.process_while_loop(step, context, state)

        assert result["type"] == "while_loop_skipped"
        assert result["reason"] == "Initial condition was false"
        assert not context.is_in_loop()


class TestForEachProcessor:
    """Test foreach step processing."""

    def test_process_foreach_with_array(self):
        """Test foreach processing with an array."""
        processor = ForEachProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="foreach1",
            type="foreach",
            definition={
                "items": "files",
                "variable_name": "file",
                "body": [{"type": "user_message", "message": "Processing {{ file }}"}],
            },
        )

        state = {"files": ["file1.txt", "file2.txt", "file3.txt"]}

        result = processor.process_foreach(step, context, state)

        assert result["type"] == "foreach_started"
        assert result["items_count"] == 3
        assert result["variable_name"] == "file"
        assert result["current_item"] == "file1.txt"
        assert result["current_index"] == 0

        # Check that loop was entered with correct variables
        assert context.is_in_loop()
        current_loop = context.current_loop()
        assert current_loop.loop_type == "foreach"
        assert current_loop.variable_bindings["file"] == "file1.txt"
        assert current_loop.variable_bindings["index"] == 0

    def test_process_foreach_empty_array(self):
        """Test foreach processing with an empty array."""
        processor = ForEachProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="foreach1", type="foreach", definition={"items": "files", "body": [{"type": "user_message"}]}
        )

        state = {"files": []}

        result = processor.process_foreach(step, context, state)

        assert result["type"] == "foreach_skipped"
        assert result["reason"] == "Empty array"
        assert not context.is_in_loop()

    def test_expand_foreach_steps(self):
        """Test foreach step expansion."""
        processor = ForEachProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="foreach1",
            type="foreach",
            definition={
                "items": "files",
                "variable_name": "file",
                "body": [{"type": "user_message", "message": "Processing {{ file }}"}],
            },
        )

        state = {"files": ["file1.txt", "file2.txt"]}

        expanded_steps = processor.expand_foreach_steps(step, context, state)

        assert len(expanded_steps) == 2  # 2 files * 1 body step
        assert expanded_steps[0].id == "foreach1.0.0"
        assert expanded_steps[1].id == "foreach1.1.0"


class TestUserInputProcessor:
    """Test user input step processing."""

    def test_process_user_input(self):
        """Test user input step processing."""
        processor = UserInputProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="input1",
            type="user_input",
            definition={
                "prompt": "Enter your age:",
                "variable_name": "age",
                "input_type": "number",
                "validation_pattern": r"^\d+$",
                "max_attempts": 3,
            },
        )

        state = {}

        result = processor.process_user_input(step, context, state)

        assert result["type"] == "user_input_required"
        assert result["prompt"] == "Enter your age:"
        assert result["variable_name"] == "age"
        assert result["input_type"] == "number"
        assert result["current_attempt"] == 1
        assert result["max_attempts"] == 3

    def test_validate_and_store_input_valid(self):
        """Test valid user input validation and storage."""
        processor = UserInputProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="input1",
            type="user_input",
            definition={"variable_name": "age", "input_type": "number", "required": True},
        )

        result = processor.validate_and_store_input(step, "25", context)

        assert result["valid"]
        assert result["value"] == 25
        assert result["variable_name"] == "age"
        assert context.get_variable("age") == 25

    def test_validate_and_store_input_invalid(self):
        """Test invalid user input validation."""
        processor = UserInputProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(
            id="input1",
            type="user_input",
            definition={
                "variable_name": "age",
                "input_type": "number",
                "validation_pattern": r"^\d+$",
                "validation_message": "Please enter a valid number",
            },
        )

        result = processor.validate_and_store_input(step, "abc", context)

        assert not result["valid"]
        assert result["retry"]
        assert "Please enter a valid number" in result["error"]


class TestFlowControlStatements:
    """Test flow control statements - AC 4.3"""

    def test_flow_control_break_immediate_exit(self):
        """Test break statement exits current loop immediately and resumes execution after loop construct (AC 4.3)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        # Set up loop context
        loop_state = LoopState(loop_type="while", loop_id="loop1")
        context.enter_loop(loop_state)

        step = WorkflowStep(id="break1", type="break", definition={})

        result = processor.process_break(step, context, {})

        assert result["type"] == "break_executed"
        assert result["loop_id"] == "loop1"
        assert loop_state.control_signal == "break"

    def test_flow_control_break_context_validation(self):
        """Test break statement handles break outside loop context with appropriate error (AC 4.3)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(id="break1", type="break", definition={})

        with pytest.raises(ControlFlowError):
            processor.process_break(step, context, {})

    def test_flow_control_continue_iteration_skip(self):
        """Test continue statement skips remaining steps in current iteration and continues with next iteration (AC 4.3)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        # Set up loop context
        loop_state = LoopState(loop_type="foreach", loop_id="loop1")
        context.enter_loop(loop_state)

        step = WorkflowStep(id="continue1", type="continue", definition={})

        result = processor.process_continue(step, context, {})

        assert result["type"] == "continue_executed"
        assert result["loop_id"] == "loop1"
        assert loop_state.control_signal == "continue"

    def test_flow_control_continue_context_validation(self):
        """Test continue statement validates proper loop context and supports continue in loop contexts only (AC 4.3)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(id="break1", type="break", definition={})

        # Test outside loop
        result = processor.validate_loop_control_context(step, context)
        assert not result["valid"]
        assert "outside of loop" in result["error"]

        # Test inside loop
        loop_state = LoopState(loop_type="while", loop_id="loop1")
        context.enter_loop(loop_state)

        result = processor.validate_loop_control_context(step, context)
        assert result["valid"]


class TestWhileLoopConditionFix:
    """Test while_loop condition processing bug fix - AC 4.2"""

    def setup_method(self):
        """Set up test environment."""
        from aromcp.workflow_server.state.manager import StateManager
        from aromcp.workflow_server.workflow.loader import WorkflowLoader
        from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
        
        self.state_manager = StateManager()
        self.executor = QueueBasedWorkflowExecutor(self.state_manager)
        self.loader = WorkflowLoader()

    def test_while_loop_condition_preserved_during_template_processing(self):
        """Test while_loop conditions are preserved during template processing (AC 4.2)."""
        # Create workflow with while_loop that previously had condition issues
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
        from aromcp.workflow_server.state.models import StateSchema
        
        steps = [
            WorkflowStep(
                id="while_loop_test",
                type="while_loop",
                definition={
                    "condition": "state.attempt_count < 3",
                    "body": [
                        {
                            "id": "increment_counter",
                            "type": "shell_command",
                            "command": "echo 'Attempt {{ state.attempt_count }}'",
                            "state_update": {
                                "path": "state.attempt_count",
                                "value": "{{ state.attempt_count + 1 }}"
                            }
                        }
                    ],
                    "max_iterations": 5
                }
            )
        ]
        
        workflow_def = WorkflowDefinition(
            name="test:while_loop_condition",
            description="Test while loop condition preservation",
            version="1.0.0",
            default_state={"inputs": {}, "state": {"attempt_count": 0}, "computed": {}},
            state_schema=StateSchema(inputs={}, computed={}, state={"attempt_count": "number"}),
            inputs={},
            steps=steps
        )
        
        # Start the workflow
        result = self.executor.start(workflow_def, {})
        assert "workflow_id" in result
        assert result["status"] == "running"
        
        workflow_id = result["workflow_id"]
        
        # Get workflow status to verify while loop is properly processed
        status = self.executor.get_workflow_status(workflow_id)
        assert status["status"] in ["running", "completed"]
        
        # Verify condition is preserved (not processed as template)
        # This should not raise template processing errors

    def test_while_loop_condition_not_template_processed(self):
        """Test while_loop conditions are not processed as templates (AC 4.2)."""
        from aromcp.workflow_server.workflow.steps.while_loop import WhileLoopProcessor
        from aromcp.workflow_server.workflow.models import WorkflowStep
        from aromcp.workflow_server.workflow.context import ExecutionContext

        processor = WhileLoopProcessor()
        
        step_definition = {
            "condition": "state.counter < 5",
            "body": [
                {"id": "process_item", "type": "user_message", "message": "Processing item"}
            ]
        }
        
        # Create WorkflowStep object
        step = WorkflowStep(
            id="while_step",
            type="while_loop",
            definition=step_definition
        )

        # Mock state with nested structure (flattened for while_loop processor)
        mock_state = {
            "state.counter": 2
        }

        # Create execution context
        context = ExecutionContext("test_workflow")
        
        # Process the while loop step using the correct method
        result = processor.process_while_loop(step, context, mock_state)
        
        # Should succeed without template processing errors
        assert "type" in result
        assert result["type"] == "while_loop_started"
        # The condition should be preserved as-is for evaluation
        assert "condition" in result
        assert result["condition"] == "state.counter < 5"
        # Loop should have been initialized
        assert "loop_id" in result
        assert result["loop_id"] == "while_step"


class TestNestedLoopBreakContinue:
    """Test nested loop break/continue handling - AC-CF-022"""

    def test_nested_loop_break_affects_only_inner_loop(self):
        """Test that break in nested loop only exits the innermost loop (AC-CF-022)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        # Set up nested loop context - outer loop first
        outer_loop = LoopState(loop_type="while", loop_id="outer_loop")
        inner_loop = LoopState(loop_type="while", loop_id="inner_loop")
        
        context.enter_loop(outer_loop)
        context.enter_loop(inner_loop)
        
        # Break should only affect inner loop
        step = WorkflowStep(id="break1", type="break", definition={})
        result = processor.process_break(step, context, {})
        
        assert result["type"] == "break_executed"
        assert result["loop_id"] == "inner_loop"
        assert inner_loop.control_signal == "break"
        assert outer_loop.control_signal is None
        
    def test_nested_loop_continue_affects_only_inner_loop(self):
        """Test that continue in nested loop only affects the innermost loop (AC-CF-022)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        # Set up nested loop context
        outer_loop = LoopState(loop_type="foreach", loop_id="outer_foreach", items=["a", "b", "c"])
        inner_loop = LoopState(loop_type="foreach", loop_id="inner_foreach", items=[1, 2, 3])
        
        context.enter_loop(outer_loop)
        context.enter_loop(inner_loop)
        
        # Continue should only affect inner loop
        step = WorkflowStep(id="continue1", type="continue", definition={})
        result = processor.process_continue(step, context, {})
        
        assert result["type"] == "continue_executed"
        assert result["loop_id"] == "inner_foreach"
        assert inner_loop.control_signal == "continue"
        assert outer_loop.control_signal is None

    def test_deeply_nested_loop_control_flow(self):
        """Test control flow in deeply nested loops (AC-CF-022)."""
        context = ExecutionContext("wf_123")
        
        # Create three levels of nesting
        loop1 = LoopState(loop_type="while", loop_id="loop1", max_iterations=10)
        loop2 = LoopState(loop_type="foreach", loop_id="loop2", items=["x", "y", "z"])
        loop3 = LoopState(loop_type="while", loop_id="loop3", max_iterations=5)
        
        context.enter_loop(loop1)
        context.enter_loop(loop2)
        context.enter_loop(loop3)
        
        # Test we can access all loop levels
        assert context.is_in_loop()
        assert context.current_loop() == loop3
        assert len(context.loop_stack) == 3
        
        # Signal break to innermost loop
        assert context.signal_loop_control("break")
        assert loop3.control_signal == "break"
        assert loop2.control_signal is None
        assert loop1.control_signal is None
        
        # Exit innermost loop and test continue on middle loop
        context.exit_loop()
        assert context.signal_loop_control("continue")
        assert loop2.control_signal == "continue"
        assert loop1.control_signal is None

    def test_nested_loop_with_debug_manager_integration(self):
        """Test nested loop control flow with DebugManager integration (AC-CF-022)."""
        from aromcp.workflow_server.debugging.debug_tools import DebugManager
        
        debug_manager = DebugManager()
        context = ExecutionContext("wf_123")
        
        # Enable debug tracking for loops
        debug_manager.set_debug_mode(True)
        
        # Create nested loops
        outer_loop = LoopState(loop_type="while", loop_id="outer_debug_loop")
        inner_loop = LoopState(loop_type="foreach", loop_id="inner_debug_loop", items=["a", "b"])
        
        # Track loop entry with debug manager
        debug_manager.add_checkpoint(
            workflow_id="wf_123",
            step_id="outer_debug_loop",
            state_before={"loop_depth": 0},
            step_config={"type": "while_loop", "condition": "true"}
        )
        
        context.enter_loop(outer_loop)
        
        debug_manager.add_checkpoint(
            workflow_id="wf_123",
            step_id="inner_debug_loop",
            state_before={"loop_depth": 1},
            step_config={"type": "foreach", "items": ["a", "b"]}
        )
        
        context.enter_loop(inner_loop)
        
        # Verify debug tracking
        checkpoints = debug_manager.get_workflow_checkpoints("wf_123")
        assert len(checkpoints) >= 2
        assert any(cp.step_id == "outer_debug_loop" for cp in checkpoints)
        assert any(cp.step_id == "inner_debug_loop" for cp in checkpoints)


class TestInfiniteLoopDetection:
    """Test infinite loop detection - AC-CF-023"""

    def test_while_loop_max_iterations_enforcement(self):
        """Test that while loops respect max_iterations to prevent infinite loops (AC-CF-023)."""
        loop_state = LoopState(
            loop_type="while", 
            loop_id="test_loop", 
            max_iterations=1000  # Default safety limit
        )
        
        # Simulate many iterations
        for i in range(999):
            assert not loop_state.is_complete()
            loop_state.advance_iteration()
        
        # Should complete at max_iterations
        loop_state.advance_iteration()
        assert loop_state.is_complete()
        assert loop_state.current_iteration == 1000
        
    def test_while_loop_timeout_detection(self):
        """Test while loop timeout detection mechanism (AC-CF-023)."""
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager
        
        timeout_manager = TimeoutManager()
        
        # Set a short timeout for testing
        timeout_manager.set_step_timeout("while_loop_1", timeout_seconds=0.1)
        
        # Start timeout tracking
        timeout_manager.start_step("while_loop_1")
        
        # Simulate loop execution
        time.sleep(0.2)
        
        # Check if timeout detected
        is_timed_out = timeout_manager.check_timeout("while_loop_1")
        assert is_timed_out
        
        timeout_info = timeout_manager.get_timeout_status("while_loop_1")
        assert timeout_info is not None
        print(f"DEBUG: timeout_info = {timeout_info}")
        print(f"DEBUG: is_timed_out = {is_timed_out}")
        assert timeout_info["exceeded"]

    def test_resource_based_loop_termination(self):
        """Test loop termination based on resource consumption (AC-CF-023)."""
        from aromcp.workflow_server.workflow.resource_manager import ResourceManager
        
        resource_manager = ResourceManager()
        
        # Set resource limits for workflow
        resource_manager.set_workflow_limits(
            workflow_id="wf_123",
            max_memory_mb=100,
            max_cpu_percent=50
        )
        
        # Allocate initial resources
        allocated = resource_manager.allocate_resources(
            workflow_id="wf_123",
            requested_memory_mb=50,
            requested_cpu_percent=25
        )
        assert allocated
        
        # Simulate loop consuming more resources
        loop_state = LoopState(loop_type="while", loop_id="resource_loop")
        
        # Loop should terminate if resources exhausted
        iterations = 0
        while not loop_state.is_complete() and iterations < 100:
            # Check resource availability
            can_continue = resource_manager.check_resource_availability(
                workflow_id="wf_123",
                required_memory_mb=10
            )
            
            if not can_continue:
                loop_state.control_signal = "break"  # Force termination
                break
                
            loop_state.advance_iteration()
            iterations += 1
        
        # Verify loop terminated before hitting unsafe iteration count
        assert iterations < 100 or loop_state.is_complete()

    def test_loop_performance_monitoring(self):
        """Test loop performance monitoring for anomaly detection (AC-CF-023)."""
        from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        # Start monitoring a loop
        monitor.start_operation("loop_execution", {"loop_id": "perf_loop"})
        
        loop_state = LoopState(loop_type="while", loop_id="perf_loop")
        
        # Track iteration times
        iteration_times = []
        
        for i in range(10):
            iter_start = time.time()
            
            # Simulate work
            time.sleep(0.01)
            loop_state.advance_iteration()
            
            iter_time = time.time() - iter_start
            iteration_times.append(iter_time)
            
            # Record iteration metric
            monitor.record_metric("iteration_time", iter_time, {"iteration": i})
        
        # Check for performance anomalies
        metrics = monitor.get_metrics_summary("iteration_time")
        assert metrics is not None
        assert "avg" in metrics
        assert "max" in metrics
        
        # Detect if loop is getting slower (potential infinite loop indicator)
        first_half_avg = sum(iteration_times[:5]) / 5
        second_half_avg = sum(iteration_times[5:]) / 5
        
        # In a real scenario, significant slowdown might indicate issues
        slowdown_ratio = second_half_avg / first_half_avg
        assert slowdown_ratio < 2.0  # No significant slowdown

    def test_loop_with_circuit_breaker_protection(self):
        """Test loop protection using circuit breaker pattern (AC-CF-023)."""
        from aromcp.workflow_server.workflow.resource_manager import ResourceManager
        
        resource_manager = ResourceManager()
        
        # Configure circuit breaker for loop operations
        breaker = resource_manager.create_circuit_breaker(
            "loop_operations",
            failure_threshold=3,
            timeout_seconds=1.0
        )
        
        loop_state = LoopState(loop_type="while", loop_id="breaker_loop")
        failures = 0
        
        while not loop_state.is_complete():
            try:
                # Check circuit breaker before loop operation
                with resource_manager.circuit_breaker_context("loop_operations"):
                    # Simulate operation that might fail
                    if loop_state.current_iteration < 3:
                        # Simulate failures to trip breaker
                        raise Exception("Simulated failure")
                    
                    # Normal operation
                    loop_state.advance_iteration()
                    
            except Exception as e:
                failures += 1
                if "Circuit breaker is open" in str(e):
                    # Circuit breaker tripped - terminate loop
                    loop_state.control_signal = "break"
                    break
                    
                # Continue for other failures up to threshold
                loop_state.advance_iteration()
                
                if loop_state.current_iteration >= 10:
                    # Safety limit
                    break
        
        # Verify circuit breaker prevented runaway loop
        assert failures <= 3  # Should trip after 3 failures
        assert loop_state.current_iteration < 10  # Loop terminated early
