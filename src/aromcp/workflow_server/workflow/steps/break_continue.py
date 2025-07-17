"""Break and continue step processors for MCP Workflow System.

Handles loop control operations (break/continue) within while and foreach loops.
"""

from typing import Any

from ..context import ExecutionContext
from ..control_flow import ControlFlowError, LoopControl
from ..models import WorkflowStep


class BreakContinueProcessor:
    """Processes break and continue workflow steps."""

    def process_break(
        self,
        step: WorkflowStep,
        context: ExecutionContext,
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a break statement to exit the current loop.

        Args:
            step: The break step to process
            context: Current execution context
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing break processing result
        """
        if not context.is_in_loop():
            raise ControlFlowError(f"Break statement '{step.id}' used outside of loop context")

        current_loop = context.current_loop()
        if not current_loop:
            raise ControlFlowError("No active loop found for break statement")

        # Signal break to the current loop
        success = context.signal_loop_control(LoopControl.BREAK)
        if not success:
            raise ControlFlowError("Failed to signal break to current loop")

        # Jump to end of current frame to trigger loop exit check
        current_frame = context.current_frame()
        if current_frame:
            current_frame.current_step_index = len(current_frame.steps)

        return {
            "type": "break_executed",
            "step_id": step.id,
            "loop_id": current_loop.loop_id,
            "loop_type": current_loop.loop_type,
            "iteration": current_loop.current_iteration,
            "message": f"Break statement executed in {current_loop.loop_type} loop"
        }

    def process_continue(
        self,
        step: WorkflowStep,
        context: ExecutionContext,
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a continue statement to skip to the next loop iteration.

        Args:
            step: The continue step to process
            context: Current execution context
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing continue processing result
        """
        if not context.is_in_loop():
            raise ControlFlowError(f"Continue statement '{step.id}' used outside of loop context")

        current_loop = context.current_loop()
        if not current_loop:
            raise ControlFlowError("No active loop found for continue statement")

        # Signal continue to the current loop
        success = context.signal_loop_control(LoopControl.CONTINUE)
        if not success:
            raise ControlFlowError("Failed to signal continue to current loop")

        # Jump to end of current frame to trigger loop continuation check
        current_frame = context.current_frame()
        if current_frame:
            current_frame.current_step_index = len(current_frame.steps)

        return {
            "type": "continue_executed",
            "step_id": step.id,
            "loop_id": current_loop.loop_id,
            "loop_type": current_loop.loop_type,
            "iteration": current_loop.current_iteration,
            "message": f"Continue statement executed in {current_loop.loop_type} loop"
        }

    def is_loop_control_step(self, step_type: str) -> bool:
        """
        Check if a step type is a loop control operation.

        Args:
            step_type: The type of the workflow step

        Returns:
            True if the step is a break or continue operation
        """
        return step_type in ("break", "continue")

    def validate_loop_control_context(self, step: WorkflowStep, context: ExecutionContext) -> dict[str, Any]:
        """
        Validate that a loop control step is in the correct context.

        Args:
            step: The loop control step to validate
            context: Current execution context

        Returns:
            Dictionary containing validation result
        """
        step_type = step.type

        if not self.is_loop_control_step(step_type):
            return {
                "valid": True,
                "message": "Not a loop control step"
            }

        if not context.is_in_loop():
            return {
                "valid": False,
                "error": f"{step_type.capitalize()} statement used outside of loop",
                "step_id": step.id
            }

        current_loop = context.current_loop()
        if not current_loop:
            return {
                "valid": False,
                "error": f"No active loop found for {step_type} statement",
                "step_id": step.id
            }

        # Check if loop type supports break/continue
        supported_loop_types = ("while", "foreach")
        if current_loop.loop_type not in supported_loop_types:
            return {
                "valid": False,
                "error": f"{step_type.capitalize()} not supported in {current_loop.loop_type} loop",
                "step_id": step.id,
                "loop_type": current_loop.loop_type
            }

        return {
            "valid": True,
            "message": f"{step_type.capitalize()} statement is valid in current {current_loop.loop_type} loop",
            "loop_id": current_loop.loop_id,
            "loop_type": current_loop.loop_type
        }

    def get_loop_control_info(self, context: ExecutionContext) -> dict[str, Any]:
        """
        Get information about the current loop control state.

        Args:
            context: Current execution context

        Returns:
            Dictionary containing loop control information
        """
        if not context.is_in_loop():
            return {
                "in_loop": False,
                "message": "Not currently in a loop"
            }

        current_loop = context.current_loop()
        if not current_loop:
            return {
                "in_loop": False,
                "message": "No active loop state found"
            }

        return {
            "in_loop": True,
            "loop_id": current_loop.loop_id,
            "loop_type": current_loop.loop_type,
            "current_iteration": current_loop.current_iteration,
            "max_iterations": current_loop.max_iterations,
            "control_signal": current_loop.control_signal,
            "supports_break_continue": current_loop.loop_type in ("while", "foreach"),
            "loop_depth": len(context.loop_stack),
            "nested_loops": [
                {
                    "loop_id": loop.loop_id,
                    "loop_type": loop.loop_type,
                    "iteration": loop.current_iteration
                }
                for loop in context.loop_stack
            ]
        }
