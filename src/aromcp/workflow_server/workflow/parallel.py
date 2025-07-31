"""Parallel execution models for MCP Workflow System.

This module provides data structures and processors for parallel task execution
with sub-agent delegation.
"""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from ..workflow.expressions import ExpressionEvaluator


@dataclass
class ParallelForEachStep:
    """Configuration for parallel_foreach step type."""

    items: str  # Expression returning array
    max_parallel: int = 10
    wait_for_all: bool = True
    sub_agent_task: str = "default"
    sub_agent_prompt_override: str | None = None
    timeout_seconds: int | None = None


@dataclass
class SubAgentContext:
    """Context provided to each sub-agent in parallel execution."""

    task_id: str
    workflow_id: str
    context: dict[str, Any]
    parent_step_id: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "context": self.context,
            "parent_step_id": self.parent_step_id,
            "created_at": self.created_at,
        }


@dataclass
class ParallelTask:
    """A single task to be executed by a sub-agent."""

    task_id: str
    context: dict[str, Any]
    sub_agent_prompt: str | None = None
    status: str = "pending"  # pending, running, completed, failed
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


@dataclass
class ParallelExecution:
    """Tracks state of a parallel execution."""

    execution_id: str
    workflow_id: str
    parent_step_id: str
    tasks: list[ParallelTask]
    max_parallel: int
    wait_for_all: bool
    status: str = "pending"  # pending, running, completed, failed
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def active_task_count(self) -> int:
        """Number of tasks currently running."""
        return len([t for t in self.tasks if t.status == "running"])

    @property
    def completed_task_count(self) -> int:
        """Number of tasks completed (success or failure)."""
        return len([t for t in self.tasks if t.status in ("completed", "failed")])

    @property
    def failed_task_count(self) -> int:
        """Number of tasks that failed."""
        return len([t for t in self.tasks if t.status == "failed"])

    @property
    def is_complete(self) -> bool:
        """Whether the parallel execution is complete."""
        return self.completed_task_count == len(self.tasks)


class ParallelForEachProcessor:
    """Processes parallel_foreach steps."""

    def __init__(self, expression_evaluator: ExpressionEvaluator):
        self.expression_evaluator = expression_evaluator
        self._executions: dict[str, ParallelExecution] = {}
        self._lock = threading.RLock()

    def process_parallel_foreach(
        self, step_def: ParallelForEachStep, state: dict[str, Any], step_id: str, workflow_id: str
    ) -> dict[str, Any]:
        """Process a parallel_foreach step by creating parallel tasks.

        Returns atomic step for the agent to create sub-agents.
        """
        # Evaluate items expression to get array
        try:
            items = self.expression_evaluator.evaluate(step_def.items, state)
            if not isinstance(items, list):
                raise ValueError(f"Items expression must return array, got: {type(items)}")
        except Exception as e:
            return {"error": f"Failed to evaluate items expression '{step_def.items}': {str(e)}"}

        # Create parallel tasks
        tasks = []
        for i, item in enumerate(items):
            task_id = f"{step_id}_task_{i}"
            task = ParallelTask(
                task_id=task_id,
                context={"item": item, "index": i, "total": len(items)},
                sub_agent_prompt=step_def.sub_agent_prompt_override,
            )
            tasks.append(task)

        # Create parallel execution tracker
        execution_id = f"exec_{uuid.uuid4().hex[:8]}"
        execution = ParallelExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            parent_step_id=step_id,
            tasks=tasks,
            max_parallel=step_def.max_parallel,
            wait_for_all=step_def.wait_for_all,
        )

        with self._lock:
            self._executions[execution_id] = execution

        # Return atomic step for agent
        return {
            "step": {
                "id": step_id,
                "type": "parallel_tasks",
                "instructions": "Create sub-agents for ALL tasks. Execute in parallel.",
                "definition": {
                    "execution_id": execution_id,
                    "tasks": [
                        {"task_id": task.task_id, "context": task.context, "sub_agent_prompt": task.sub_agent_prompt}
                        for task in tasks
                    ],
                    "max_parallel": step_def.max_parallel,
                    "wait_for_all": step_def.wait_for_all,
                    "sub_agent_task": step_def.sub_agent_task,
                },
            }
        }

    def get_execution(self, execution_id: str) -> ParallelExecution | None:
        """Get parallel execution by ID."""
        with self._lock:
            return self._executions.get(execution_id)

    def update_task_status(
        self,
        execution_id: str,
        task_id: str,
        status: str,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> bool:
        """Update the status of a task in parallel execution."""
        with self._lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return False

            task = next((t for t in execution.tasks if t.task_id == task_id), None)
            if not task:
                return False

            old_status = task.status
            task.status = status

            if status == "running" and old_status == "pending":
                task.started_at = time.time()
                if execution.status == "pending":
                    execution.status = "running"
                    execution.started_at = time.time()
            elif status in ("completed", "failed"):
                task.completed_at = time.time()
                if error:
                    task.error = error
                if result:
                    task.result = result

                # Check if execution is complete
                if execution.is_complete:
                    execution.status = "completed" if execution.failed_task_count == 0 else "failed"
                    execution.completed_at = time.time()

            return True

    def get_next_available_tasks(self, execution_id: str, limit: int | None = None) -> list[ParallelTask]:
        """Get next available tasks that can be started."""
        with self._lock:
            execution = self._executions.get(execution_id)
            if not execution:
                return []

            # Find pending tasks
            pending_tasks = [t for t in execution.tasks if t.status == "pending"]

            # Apply max_parallel constraint
            available_slots = execution.max_parallel - execution.active_task_count
            if available_slots <= 0:
                return []

            # Apply limit if specified
            max_tasks = min(available_slots, len(pending_tasks))
            if limit is not None:
                max_tasks = min(max_tasks, limit)

            return pending_tasks[:max_tasks]

    def cleanup_execution(self, execution_id: str) -> bool:
        """Clean up completed execution."""
        with self._lock:
            execution = self._executions.get(execution_id)
            if execution and execution.is_complete:
                del self._executions[execution_id]
                return True
            return False


class TaskDistributor:
    """Distributes tasks across available sub-agents."""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._active_tasks: dict[str, Any] = {}
        self._lock = threading.RLock()

    def submit_task(self, task_id: str, task_function: callable, *args, **kwargs) -> bool:
        """Submit a task for execution."""
        with self._lock:
            if task_id in self._active_tasks:
                return False  # Task already running

            future = self._executor.submit(task_function, *args, **kwargs)
            self._active_tasks[task_id] = {"future": future, "started_at": time.time()}
            return True

    def get_completed_tasks(self) -> list[tuple[str, Any]]:
        """Get list of completed tasks with their results."""
        completed = []
        with self._lock:
            for task_id, task_info in list(self._active_tasks.items()):
                future = task_info["future"]
                if future.done():
                    try:
                        result = future.result()
                        completed.append((task_id, result))
                    except Exception as e:
                        completed.append((task_id, {"error": str(e)}))
                    del self._active_tasks[task_id]
        return completed

    def wait_for_all(self, timeout: float | None = None) -> dict[str, Any]:
        """Wait for all active tasks to complete."""
        results = {}
        with self._lock:
            futures = {tid: info["future"] for tid, info in self._active_tasks.items()}

        for task_id, future in futures.items():
            try:
                result = future.result(timeout=timeout)
                results[task_id] = result
            except Exception as e:
                results[task_id] = {"error": str(e)}

        with self._lock:
            for task_id in futures:
                self._active_tasks.pop(task_id, None)

        return results

    def shutdown(self, wait: bool = True):
        """Shutdown the task distributor."""
        self._executor.shutdown(wait=wait)

    @property
    def active_task_count(self) -> int:
        """Number of currently active tasks."""
        with self._lock:
            return len(self._active_tasks)
