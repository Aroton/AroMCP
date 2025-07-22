"""Tests for control flow components."""

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


class TestControlFlowModels:
    """Test control flow data models."""

    def test_conditional_step_creation(self):
        """Test ConditionalStep creation and conversion."""
        then_step = WorkflowStep(id="then1", type="user_message", definition={"message": "Then branch"})
        else_step = WorkflowStep(id="else1", type="user_message", definition={"message": "Else branch"})

        conditional = ConditionalStep(condition="value > 5", then_steps=[then_step], else_steps=[else_step])

        workflow_step = conditional.to_workflow_step("cond1")

        assert workflow_step.id == "cond1"
        assert workflow_step.type == "conditional"
        assert workflow_step.definition["condition"] == "value > 5"
        assert len(workflow_step.definition["then_steps"]) == 1
        assert len(workflow_step.definition["else_steps"]) == 1

    def test_while_loop_step_creation(self):
        """Test WhileLoopStep creation and conversion."""
        body_step = WorkflowStep(id="body1", type="shell_command", definition={"command": "echo 'updating counter'", "state_update": {"path": "raw.counter", "value": "$(({{ raw.counter }} + 1))"}})

        while_loop = WhileLoopStep(condition="counter < 10", max_iterations=50, body=[body_step])

        workflow_step = while_loop.to_workflow_step("loop1")

        assert workflow_step.id == "loop1"
        assert workflow_step.type == "while_loop"
        assert workflow_step.definition["condition"] == "counter < 10"
        assert workflow_step.definition["max_iterations"] == 50
        assert len(workflow_step.definition["body"]) == 1

    def test_foreach_step_creation(self):
        """Test ForEachStep creation and conversion."""
        body_step = WorkflowStep(id="body1", type="user_message", definition={"message": "Processing {{ item }}"})

        foreach = ForEachStep(items="files", variable_name="file", index_name="i", body=[body_step])

        workflow_step = foreach.to_workflow_step("foreach1")

        assert workflow_step.id == "foreach1"
        assert workflow_step.type == "foreach"
        assert workflow_step.definition["items"] == "files"
        assert workflow_step.definition["variable_name"] == "file"
        assert workflow_step.definition["index_name"] == "i"

    def test_user_input_step_creation(self):
        """Test UserInputStep creation and conversion."""
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


class TestLoopState:
    """Test LoopState functionality."""

    def test_while_loop_state(self):
        """Test while loop state management."""
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

    def test_foreach_loop_state(self):
        """Test foreach loop state management."""
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

    def test_loop_control_signals(self):
        """Test break and continue signals."""
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


class TestBreakContinueProcessor:
    """Test break and continue step processing."""

    def test_process_break_in_loop(self):
        """Test break processing within a loop."""
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

    def test_process_break_outside_loop(self):
        """Test break processing outside of a loop (should error)."""
        processor = BreakContinueProcessor()
        context = ExecutionContext("wf_123")

        step = WorkflowStep(id="break1", type="break", definition={})

        with pytest.raises(ControlFlowError):
            processor.process_break(step, context, {})

    def test_process_continue_in_loop(self):
        """Test continue processing within a loop."""
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

    def test_validate_loop_control_context(self):
        """Test validation of loop control context."""
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
