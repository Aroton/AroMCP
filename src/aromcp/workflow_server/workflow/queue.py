"""Workflow queue management for step execution."""

from typing import Any

from .models import WorkflowStep


class WorkflowQueue:
    """Manages the three queues for a workflow instance."""
    
    def __init__(self, workflow_id: str, initial_steps: list[WorkflowStep]):
        self.workflow_id = workflow_id
        self.main_queue: list[WorkflowStep] = initial_steps.copy()
        self.client_queue: list[dict[str, Any]] = []
        self.server_completed: list[dict[str, Any]] = []
        self.loop_stack: list[dict[str, Any]] = []  # Track loop contexts
    
    def has_steps(self) -> bool:
        """Check if there are more steps to process."""
        return len(self.main_queue) > 0
    
    def peek_next(self) -> WorkflowStep | None:
        """Peek at the next step without removing it."""
        return self.main_queue[0] if self.main_queue else None
    
    def pop_next(self) -> WorkflowStep | None:
        """Remove and return the next step."""
        return self.main_queue.pop(0) if self.main_queue else None
    
    def prepend_steps(self, steps: list[WorkflowStep]):
        """Add steps to the front of the queue."""
        self.main_queue = steps + self.main_queue
    
    def push_loop_context(self, loop_type: str, context: dict[str, Any]):
        """Push a loop context onto the stack."""
        self.loop_stack.append({"type": loop_type, "context": context})
    
    def pop_loop_context(self):
        """Pop a loop context from the stack."""
        if self.loop_stack:
            self.loop_stack.pop()
    
    def get_current_loop(self) -> dict[str, Any] | None:
        """Get the current loop context if any."""
        return self.loop_stack[-1] if self.loop_stack else None
    
    def clear_client_queues(self):
        """Clear the client and server completed queues."""
        self.client_queue = []
        self.server_completed = []