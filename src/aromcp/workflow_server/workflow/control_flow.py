"""Control flow models for MCP Workflow System.

Defines data structures for conditional execution, loops, and advanced workflow control.
"""

from dataclasses import dataclass, field
from typing import Any

from .models import WorkflowStep


@dataclass
class ConditionalStep:
    """Represents an if/then/else conditional step."""

    condition: str  # Expression to evaluate
    then_steps: list[WorkflowStep]
    else_steps: list[WorkflowStep] | None = None

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(
            id=step_id,
            type="conditional",
            definition={
                "condition": self.condition,
                "then_steps": [step.definition for step in self.then_steps],
                "else_steps": [step.definition for step in self.else_steps] if self.else_steps else None,
            },
        )


@dataclass
class WhileLoopStep:
    """Represents a while loop with safety limits."""

    condition: str  # Expression to evaluate for continuation
    max_iterations: int = 100  # Safety limit
    body: list[WorkflowStep] = field(default_factory=list)

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(
            id=step_id,
            type="while_loop",
            definition={
                "condition": self.condition,
                "max_iterations": self.max_iterations,
                "body": [step.definition for step in self.body],
            },
        )


@dataclass
class ForEachStep:
    """Represents iteration over an array."""

    items: str  # Expression returning array to iterate over
    variable_name: str = "item"  # Variable name for current item
    index_name: str = "index"  # Variable name for current index
    body: list[WorkflowStep] = field(default_factory=list)

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(
            id=step_id,
            type="foreach",
            definition={
                "items": self.items,
                "variable_name": self.variable_name,
                "index_name": self.index_name,
                "body": [step.definition for step in self.body],
            },
        )


@dataclass
class UserInputStep:
    """Represents a user input step with validation."""

    prompt: str
    variable_name: str  # Where to store the input
    validation_pattern: str | None = None  # Regex pattern for validation
    validation_message: str | None = None  # Error message for invalid input
    input_type: str = "string"  # "string", "number", "boolean"
    required: bool = True
    max_attempts: int = 3

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(
            id=step_id,
            type="user_input",
            definition={
                "prompt": self.prompt,
                "variable_name": self.variable_name,
                "validation_pattern": self.validation_pattern,
                "validation_message": self.validation_message,
                "input_type": self.input_type,
                "required": self.required,
                "max_attempts": self.max_attempts,
            },
        )


@dataclass
class BreakStep:
    """Represents a break statement to exit a loop."""

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(id=step_id, type="break", definition={})


@dataclass
class ContinueStep:
    """Represents a continue statement to skip to next iteration."""

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(id=step_id, type="continue", definition={})


@dataclass
class ParallelForEachStep:
    """Represents parallel iteration using sub-agents."""

    items: str  # Expression returning array to iterate over
    sub_agent_task: str  # Name of the sub-agent task to delegate
    max_parallel: int = 10  # Maximum number of parallel executions
    variable_name: str = "item"  # Variable name for current item
    index_name: str = "index"  # Variable name for current index

    def to_workflow_step(self, step_id: str) -> WorkflowStep:
        """Convert to a WorkflowStep for execution."""
        return WorkflowStep(
            id=step_id,
            type="parallel_foreach",
            definition={
                "items": self.items,
                "sub_agent_task": self.sub_agent_task,
                "max_parallel": self.max_parallel,
                "variable_name": self.variable_name,
                "index_name": self.index_name,
            },
        )


class LoopControl:
    """Represents loop control operations (break/continue)."""

    BREAK = "break"
    CONTINUE = "continue"


@dataclass
class LoopState:
    """Tracks the state of a currently executing loop."""

    loop_type: str  # "while", "foreach", "parallel_foreach"
    loop_id: str  # Unique identifier for this loop instance
    current_iteration: int = 0
    max_iterations: int = 100
    items: list[Any] | None = None  # For foreach loops
    current_item_index: int = 0  # For foreach loops
    variable_bindings: dict[str, Any] = field(default_factory=dict)  # Loop variables
    control_signal: str | None = None  # "break" or "continue"
    variable_name: str = "item"  # Custom variable name for foreach loop item
    index_name: str = "index"  # Custom variable name for foreach loop index

    def is_complete(self) -> bool:
        """Check if the loop should terminate."""
        if self.control_signal == LoopControl.BREAK:
            return True

        if self.current_iteration >= self.max_iterations:
            return True

        if self.loop_type == "foreach" and self.items is not None:
            return self.current_item_index >= len(self.items)

        return False

    def get_current_item(self) -> Any:
        """Get the current item for foreach loops."""
        if self.items and 0 <= self.current_item_index < len(self.items):
            return self.items[self.current_item_index]
        return None

    def update_loop_variables(self):
        """Update loop variables in variable_bindings based on current state."""
        if self.loop_type == "foreach":
            # Set custom loop variables for foreach loops
            current_item = self.get_current_item()
            self.variable_bindings.update({
                self.variable_name: current_item,
                self.index_name: self.current_item_index
            })
        elif self.loop_type == "while":
            # Set loop.iteration for while loops (1-based iteration counter)
            self.variable_bindings["iteration"] = self.current_iteration + 1

    def advance_iteration(self):
        """Advance to the next iteration and update loop variables."""
        # print(f"DEBUG: advance_iteration called for {self.loop_id}: {self.current_iteration} -> {self.current_iteration + 1}")
        self.current_iteration += 1
        if self.loop_type == "foreach":
            self.current_item_index += 1
        self.control_signal = None  # Reset control signal
        
        # Update loop variables after advancing
        self.update_loop_variables()

    def prepare_for_iteration(self):
        """Prepare loop variables for the current iteration without advancing."""
        self.update_loop_variables()

    def clear_loop_variables(self):
        """Clear all loop variables when the loop exits."""
        self.variable_bindings.clear()


@dataclass
class ConditionalResult:
    """Result of evaluating a conditional expression."""

    condition_result: bool
    original_condition: str
    evaluated_values: dict[str, Any] = field(default_factory=dict)
    branch_taken: str = ""  # "then" or "else"

    def to_step_definition(self) -> dict[str, Any]:
        """Convert to step definition for MCP response."""
        return {
            "condition_result": self.condition_result,
            "original_condition": self.original_condition,
            "evaluated_values": self.evaluated_values,
            "branch_taken": self.branch_taken,
        }


class ControlFlowError(Exception):
    """Raised when control flow execution fails."""

    pass


class InfiniteLoopError(ControlFlowError):
    """Raised when a loop exceeds maximum iterations."""

    pass


class ValidationError(ControlFlowError):
    """Raised when user input validation fails."""

    pass
