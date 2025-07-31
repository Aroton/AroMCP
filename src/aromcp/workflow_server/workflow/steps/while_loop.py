"""While loop step processor for MCP Workflow System.

Handles while loop execution with safety limits and break/continue support.
"""

from typing import Any

from ..context import ExecutionContext
from ..control_flow import ControlFlowError, LoopControl, LoopState
from ..expressions import ExpressionError, ExpressionEvaluator
from ..models import WorkflowStep


class WhileLoopProcessor:
    """Processes while loop workflow steps."""

    def __init__(self):
        self.expression_evaluator = ExpressionEvaluator()

    def process_while_loop(
        self, step: WorkflowStep, context: ExecutionContext, state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a while loop step.

        Args:
            step: The while loop step to process
            context: Current execution context
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing loop initialization result
        """
        definition = step.definition
        condition = definition.get("condition", "")
        max_iterations = definition.get("max_iterations", 100)
        body_steps = definition.get("body", [])

        if not condition:
            raise ControlFlowError("While loop step missing 'condition' field")

        try:
            # Create loop state
            loop_state = LoopState(loop_type="while", loop_id=step.id, max_iterations=max_iterations)

            # Store the condition for later evaluation
            loop_state.condition = condition

            # Check if we should enter the loop
            should_continue = self._evaluate_loop_condition(condition, state, context)

            if should_continue:
                # Convert body step definitions to WorkflowStep objects
                workflow_steps = []
                for i, step_def in enumerate(body_steps):
                    step_id = f"{step.id}.body.{i}"
                    workflow_steps.append(
                        WorkflowStep(id=step_id, type=step_def.get("type", "unknown"), definition=step_def)
                    )

                # Enter the loop
                context.enter_loop(loop_state)

                # Create loop frame
                loop_frame = context.create_loop_frame(steps=workflow_steps, loop_state=loop_state)
                context.push_frame(loop_frame)

                return {
                    "type": "while_loop_started",
                    "step_id": step.id,
                    "loop_id": loop_state.loop_id,
                    "condition": condition,
                    "max_iterations": max_iterations,
                    "body_steps": len(workflow_steps),
                    "iteration": 0,
                }
            else:
                return {
                    "type": "while_loop_skipped",
                    "step_id": step.id,
                    "condition": condition,
                    "reason": "Initial condition was false",
                }

        except ExpressionError as e:
            raise ControlFlowError(f"Failed to evaluate while loop condition '{condition}': {str(e)}") from e
        except Exception as e:
            raise ControlFlowError(f"Error processing while loop step: {str(e)}") from e

    def check_loop_continuation(self, context: ExecutionContext, state: dict[str, Any]) -> dict[str, Any]:
        """
        Check if a while loop should continue to the next iteration.

        Args:
            context: Current execution context
            state: Current workflow state

        Returns:
            Dictionary containing loop continuation decision
        """
        current_loop = context.current_loop()
        if not current_loop or current_loop.loop_type != "while":
            raise ControlFlowError("Not currently in a while loop")

        # Check for control signals
        if current_loop.control_signal == LoopControl.BREAK:
            return self._exit_loop(context, "break_signal")

        # Check iteration limit
        if current_loop.current_iteration >= current_loop.max_iterations:
            return self._exit_loop(context, "max_iterations_reached")

        # Get the loop condition from the loop state
        condition = getattr(current_loop, "condition", None)
        if not condition:
            raise ControlFlowError("Loop condition not found in loop state")

        try:
            should_continue = self._evaluate_loop_condition(condition, state, context)

            if should_continue:
                # Continue loop - advance iteration and reset to beginning
                current_loop.advance_iteration()
                if current_loop.control_signal == LoopControl.CONTINUE:
                    current_loop.control_signal = None  # Clear continue signal

                # Reset frame to beginning of body
                current_frame = context.current_frame()
                if current_frame:
                    current_frame.current_step_index = 0

                return {
                    "type": "while_loop_continue",
                    "loop_id": current_loop.loop_id,
                    "iteration": current_loop.current_iteration,
                    "condition_result": True,
                }
            else:
                return self._exit_loop(context, "condition_false")

        except ExpressionError as e:
            return self._exit_loop(context, f"condition_error: {str(e)}")

    def _evaluate_loop_condition(self, condition: str, state: dict[str, Any], context: ExecutionContext) -> bool:
        """
        Evaluate the loop condition with current state and context variables.

        Args:
            condition: The condition expression to evaluate
            state: Current workflow state
            context: Current execution context

        Returns:
            Boolean result of the condition evaluation
        """
        # Clean the condition
        cleaned_condition = condition.strip()
        if cleaned_condition.startswith("{{") and cleaned_condition.endswith("}}"):
            cleaned_condition = cleaned_condition[2:-2].strip()

        # Merge state with context variables for evaluation
        evaluation_context = dict(state)
        evaluation_context.update(context.get_all_variables())

        # Evaluate the expression
        result = self.expression_evaluator.evaluate(cleaned_condition, evaluation_context)

        return bool(result)

    def _exit_loop(self, context: ExecutionContext, reason: str) -> dict[str, Any]:
        """
        Exit the current while loop.

        Args:
            context: Current execution context
            reason: Reason for exiting the loop

        Returns:
            Dictionary containing loop exit information
        """
        current_loop = context.current_loop()
        loop_id = current_loop.loop_id if current_loop else "unknown"
        iteration = current_loop.current_iteration if current_loop else 0

        # Exit the loop
        context.exit_loop()

        # Pop the loop frame
        context.pop_frame()

        return {"type": "while_loop_exited", "loop_id": loop_id, "reason": reason, "total_iterations": iteration}

    def process_break(self, context: ExecutionContext) -> dict[str, Any]:
        """
        Process a break statement within a loop.

        Args:
            context: Current execution context

        Returns:
            Dictionary containing break processing result
        """
        if not context.is_in_loop():
            raise ControlFlowError("Break statement outside of loop")

        success = context.signal_loop_control(LoopControl.BREAK)
        if not success:
            raise ControlFlowError("Failed to signal break to current loop")

        return {"type": "break_signaled", "loop_id": context.current_loop().loop_id if context.current_loop() else None}

    def process_continue(self, context: ExecutionContext) -> dict[str, Any]:
        """
        Process a continue statement within a loop.

        Args:
            context: Current execution context

        Returns:
            Dictionary containing continue processing result
        """
        if not context.is_in_loop():
            raise ControlFlowError("Continue statement outside of loop")

        success = context.signal_loop_control(LoopControl.CONTINUE)
        if not success:
            raise ControlFlowError("Failed to signal continue to current loop")

        # For continue, we need to jump to the end of the current frame
        # so that the loop continuation check will be triggered
        current_frame = context.current_frame()
        if current_frame:
            current_frame.current_step_index = len(current_frame.steps)

        return {
            "type": "continue_signaled",
            "loop_id": context.current_loop().loop_id if context.current_loop() else None,
        }
