"""Execution context management for MCP Workflow System.

Manages execution state, stack frames, variable scoping, and control flow context.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .control_flow import LoopControl, LoopState
from .models import WorkflowStep


@dataclass
class StackFrame:
    """Represents a single execution frame in the call stack."""

    frame_id: str
    frame_type: str  # "workflow", "conditional", "loop", "foreach"
    step_id: str | None = None
    steps: list[WorkflowStep] = field(default_factory=list)
    current_step_index: int = 0
    local_variables: dict[str, Any] = field(default_factory=dict)
    loop_state: LoopState | None = None
    created_at: datetime = field(default_factory=datetime.now)

    def has_more_steps(self) -> bool:
        """Check if there are more steps to execute in this frame."""
        return self.current_step_index < len(self.steps)

    def get_current_step(self) -> WorkflowStep | None:
        """Get the current step to execute."""
        if self.has_more_steps():
            return self.steps[self.current_step_index]
        return None

    def advance_step(self) -> bool:
        """Advance to the next step. Returns True if successful."""
        if self.has_more_steps():
            self.current_step_index += 1
            return True
        return False

    def jump_to_step(self, step_index: int) -> bool:
        """Jump to a specific step index."""
        if 0 <= step_index < len(self.steps):
            self.current_step_index = step_index
            return True
        return False


@dataclass
class SubAgentContext:
    """Context for sub-agent task delegation."""

    task_id: str
    parent_workflow_id: str
    task_name: str
    context_data: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending", "running", "completed", "failed"
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


class ExecutionContext:
    """Manages execution context for workflow runs with control flow support."""

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self.execution_stack: list[StackFrame] = []
        self.global_variables: dict[str, Any] = {}
        self.loop_stack: list[LoopState] = []
        self.sub_agent_contexts: dict[str, SubAgentContext] = {}
        self.execution_depth = 0
        self.max_depth = 100  # Prevent stack overflow
        self.created_at = datetime.now()
        self.last_updated = datetime.now()

    def push_frame(self, frame: StackFrame):
        """Push a new execution frame onto the stack."""
        if self.execution_depth >= self.max_depth:
            raise RuntimeError(f"Maximum execution depth ({self.max_depth}) exceeded")

        self.execution_stack.append(frame)
        self.execution_depth += 1
        self.last_updated = datetime.now()

    def pop_frame(self) -> StackFrame | None:
        """Pop the top execution frame from the stack."""
        if self.execution_stack:
            frame = self.execution_stack.pop()
            self.execution_depth -= 1
            self.last_updated = datetime.now()
            return frame
        return None

    def current_frame(self) -> StackFrame | None:
        """Get the current (top) execution frame."""
        return self.execution_stack[-1] if self.execution_stack else None

    def create_workflow_frame(self, steps: list[WorkflowStep]) -> StackFrame:
        """Create a new workflow frame."""
        return StackFrame(frame_id=str(uuid.uuid4()), frame_type="workflow", steps=steps)

    def create_conditional_frame(self, steps: list[WorkflowStep], condition_id: str) -> StackFrame:
        """Create a new conditional execution frame."""
        return StackFrame(frame_id=str(uuid.uuid4()), frame_type="conditional", step_id=condition_id, steps=steps)

    def create_loop_frame(self, steps: list[WorkflowStep], loop_state: LoopState) -> StackFrame:
        """Create a new loop execution frame."""
        return StackFrame(
            frame_id=str(uuid.uuid4()),
            frame_type="loop",
            step_id=loop_state.loop_id,
            steps=steps,
            loop_state=loop_state,
        )

    def enter_loop(self, loop_state: LoopState):
        """Enter a new loop context with proper variable isolation."""
        # Ensure loop variables are prepared
        loop_state.prepare_for_iteration()
        self.loop_stack.append(loop_state)
        self.last_updated = datetime.now()

    def exit_loop(self) -> LoopState | None:
        """Exit the current loop context and clean up loop variables."""
        if self.loop_stack:
            loop_state = self.loop_stack.pop()
            # Clear loop variables when exiting
            loop_state.clear_loop_variables()
            self.last_updated = datetime.now()
            return loop_state
        return None

    def current_loop(self) -> LoopState | None:
        """Get the current loop state."""
        return self.loop_stack[-1] if self.loop_stack else None

    def is_in_loop(self) -> bool:
        """Check if currently executing within a loop."""
        return len(self.loop_stack) > 0

    def get_nested_loop_variables(self) -> dict[str, Any]:
        """Get loop variables from all nested loops, with innermost taking precedence.

        Returns:
            Dictionary containing loop variables from all active loops
        """
        loop_vars = {}
        # Process from outermost to innermost so inner loops override outer ones
        for loop_state in self.loop_stack:
            if loop_state.variable_bindings:
                loop_vars.update(loop_state.variable_bindings)
        return loop_vars

    def signal_loop_control(self, signal: str) -> bool:
        """Signal break or continue for the current loop."""
        current_loop = self.current_loop()
        if current_loop and signal in (LoopControl.BREAK, LoopControl.CONTINUE):
            current_loop.control_signal = signal
            self.last_updated = datetime.now()
            return True
        return False

    def set_variable(self, name: str, value: Any, scope: str = "local"):
        """Set a variable in the appropriate scope."""
        if scope == "global":
            self.global_variables[name] = value
        else:
            # Set in current frame's local variables
            current_frame = self.current_frame()
            if current_frame:
                current_frame.local_variables[name] = value
            else:
                # Fallback to global if no current frame
                self.global_variables[name] = value

        self.last_updated = datetime.now()

    def set_global_variable(self, name: str, value: Any):
        """Set a global variable directly."""
        self.global_variables[name] = value
        self.last_updated = datetime.now()

    def get_global_variable(self, name: str, default: Any = None) -> Any:
        """Get a global variable value."""
        return self.global_variables.get(name, default)

    def get_scoped_variables(self) -> dict[str, dict[str, Any]]:
        """
        Get all variables organized by scope for template evaluation.

        Returns:
            Dictionary with scopes: global, local (current frame), loop (nested loops)
        """
        scoped_vars = {"global": dict(self.global_variables), "local": {}, "loop": {}}

        # Add current frame's local variables
        current_frame = self.current_frame()
        if current_frame:
            scoped_vars["local"] = dict(current_frame.local_variables)

        # Add nested loop variables (innermost takes precedence)
        scoped_vars["loop"] = self.get_nested_loop_variables()

        return scoped_vars

    def get_variable(self, name: str) -> Any:
        """Get a variable value, checking local scope first, then global."""
        # Check current frame's local variables first
        current_frame = self.current_frame()
        if current_frame and name in current_frame.local_variables:
            return current_frame.local_variables[name]

        # Check loop variables
        current_loop = self.current_loop()
        if current_loop and name in current_loop.variable_bindings:
            return current_loop.variable_bindings[name]

        # Check global variables
        return self.global_variables.get(name)

    def get_all_variables(self) -> dict[str, Any]:
        """Get all variables in scope, with local variables taking precedence."""
        variables = dict(self.global_variables)

        # Add nested loop variables (innermost takes precedence)
        variables.update(self.get_nested_loop_variables())

        # Add local variables from all frames (outer to inner)
        for frame in self.execution_stack:
            variables.update(frame.local_variables)

        return variables

    def create_sub_agent_context(self, task_name: str, context_data: dict[str, Any]) -> SubAgentContext:
        """Create a new sub-agent context."""
        task_id = str(uuid.uuid4())
        context = SubAgentContext(
            task_id=task_id, parent_workflow_id=self.workflow_id, task_name=task_name, context_data=context_data
        )
        self.sub_agent_contexts[task_id] = context
        self.last_updated = datetime.now()
        return context

    def update_sub_agent_status(
        self, task_id: str, status: str, result: dict[str, Any] | None = None, error: str | None = None
    ):
        """Update the status of a sub-agent task."""
        if task_id in self.sub_agent_contexts:
            context = self.sub_agent_contexts[task_id]
            context.status = status
            if result is not None:
                context.result = result
            if error is not None:
                context.error_message = error
            if status in ("completed", "failed"):
                context.completed_at = datetime.now()
            self.last_updated = datetime.now()

    def get_pending_sub_agent_tasks(self) -> list[SubAgentContext]:
        """Get all pending sub-agent tasks."""
        return [ctx for ctx in self.sub_agent_contexts.values() if ctx.status == "pending"]

    def get_completed_sub_agent_tasks(self) -> list[SubAgentContext]:
        """Get all completed sub-agent tasks."""
        return [ctx for ctx in self.sub_agent_contexts.values() if ctx.status == "completed"]

    def all_sub_agent_tasks_complete(self) -> bool:
        """Check if all sub-agent tasks are complete."""
        return all(ctx.status in ("completed", "failed") for ctx in self.sub_agent_contexts.values())

    def has_next_step(self) -> bool:
        """Check if there are more steps to execute."""
        current_frame = self.current_frame()
        return current_frame is not None and current_frame.has_more_steps()

    def get_next_step(self) -> WorkflowStep | None:
        """Get the next step to execute."""
        current_frame = self.current_frame()
        if current_frame:
            return current_frame.get_current_step()
        return None

    def advance_step(self) -> bool:
        """Advance to the next step in the current frame."""
        current_frame = self.current_frame()
        if current_frame:
            success = current_frame.advance_step()
            if success:
                self.last_updated = datetime.now()
            return success
        return False

    def is_complete(self) -> bool:
        """Check if the entire execution is complete."""
        return len(self.execution_stack) == 0 and self.all_sub_agent_tasks_complete()


class ExecutionContextManager:
    """Manages execution contexts for multiple workflows."""

    def __init__(self):
        self.contexts: dict[str, ExecutionContext] = {}

    def create_context(self, workflow_id: str) -> ExecutionContext:
        """Create a new execution context."""
        context = ExecutionContext(workflow_id)
        self.contexts[workflow_id] = context
        return context

    def get_context(self, workflow_id: str) -> ExecutionContext | None:
        """Get an existing execution context."""
        return self.contexts.get(workflow_id)

    def remove_context(self, workflow_id: str) -> bool:
        """Remove an execution context."""
        if workflow_id in self.contexts:
            del self.contexts[workflow_id]
            return True
        return False

    def list_active_contexts(self) -> list[str]:
        """List all active workflow contexts."""
        return list(self.contexts.keys())

    def cleanup_completed_contexts(self):
        """Remove contexts for completed workflows."""
        completed = [wf_id for wf_id, ctx in self.contexts.items() if ctx.is_complete()]
        for wf_id in completed:
            del self.contexts[wf_id]


# Global context manager instance
context_manager = ExecutionContextManager()
