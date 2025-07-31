"""Parallel error handling for the MCP Workflow System."""

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .models import WorkflowError

logger = logging.getLogger(__name__)


class ParallelErrorStrategy(Enum):
    """Strategies for handling errors in parallel execution."""

    FAIL_FAST = "fail_fast"  # Stop on first error
    COLLECT_ALL = "collect_all"  # Collect all errors before failing
    BEST_EFFORT = "best_effort"  # Continue with successful tasks
    THRESHOLD = "threshold"  # Fail when error threshold exceeded


@dataclass
class ParallelErrorConfig:
    """Configuration for parallel error handling."""

    strategy: ParallelErrorStrategy = ParallelErrorStrategy.FAIL_FAST
    error_threshold: float = 0.5  # Fail when > 50% of tasks fail
    max_errors: int = 10  # Maximum errors to collect
    timeout_seconds: float = 30.0
    retry_failed_tasks: bool = False
    recovery_action: str | None = None


@dataclass
class TaskErrorInfo:
    """Information about a task error."""

    task_id: str
    error: WorkflowError
    retry_count: int = 0
    recovered: bool = False
    recovery_actions: list[str] = field(default_factory=list)


class ParallelErrorAggregator:
    """Aggregates errors from parallel task execution."""

    def __init__(self, config: ParallelErrorConfig | None = None):
        """Initialize the error aggregator."""
        self.config = config or ParallelErrorConfig()
        self._lock = threading.RLock()
        self._task_errors: dict[str, TaskErrorInfo] = {}
        self._error_counts: dict[str, int] = defaultdict(int)
        self._total_tasks = 0
        self._failed_tasks = 0

    def add_task_error(self, task_id: str, error: WorkflowError) -> None:
        """Add an error from a parallel task."""
        with self._lock:
            if task_id not in self._task_errors:
                self._failed_tasks += 1

            task_error = TaskErrorInfo(task_id=task_id, error=error)
            self._task_errors[task_id] = task_error
            self._error_counts[error.error_type] += 1

            logger.error(f"Task {task_id} failed: {error.message}")

            # Auto-set total tasks to match the number of unique failed tasks
            if self._total_tasks < len(self._task_errors):
                self._total_tasks = len(self._task_errors)

    def set_total_tasks(self, total: int) -> None:
        """Set the total number of tasks."""
        with self._lock:
            self._total_tasks = total

    def get_aggregated_errors(self) -> list[WorkflowError]:
        """Get all aggregated errors."""
        with self._lock:
            return [info.error for info in self._task_errors.values()]

    def get_error_summary(self) -> dict[str, Any]:
        """Get a summary of errors."""
        with self._lock:
            return {
                "total_tasks": self._total_tasks,
                "failed_tasks": self._failed_tasks,
                "success_rate": (self._total_tasks - self._failed_tasks) / max(1, self._total_tasks),
                "error_types": dict(self._error_counts),
                "threshold_exceeded": self._failed_tasks / max(1, self._total_tasks) > self.config.error_threshold,
            }

    def get_task_errors(self) -> dict[str, TaskErrorInfo]:
        """Get detailed task error information."""
        with self._lock:
            return self._task_errors.copy()

    def should_fail_fast(self) -> bool:
        """Check if we should fail fast based on strategy."""
        with self._lock:
            if self.config.strategy == ParallelErrorStrategy.FAIL_FAST:
                return len(self._task_errors) > 0
            elif self.config.strategy == ParallelErrorStrategy.THRESHOLD:
                if self._total_tasks > 0:
                    error_rate = self._failed_tasks / self._total_tasks
                    return error_rate > self.config.error_threshold
            return False

    def clear(self) -> None:
        """Clear all collected errors."""
        with self._lock:
            self._task_errors.clear()
            self._error_counts.clear()
            self._failed_tasks = 0
            self._total_tasks = 0


class ParallelErrorHandler:
    """Handles errors in parallel execution contexts."""

    def __init__(self, config: ParallelErrorConfig | None = None):
        """Initialize the parallel error handler."""
        self.config = config or ParallelErrorConfig()
        self.aggregator = ParallelErrorAggregator(config)
        self._strategy = self.config.strategy
        self._error_callbacks: list[Callable[[WorkflowError], None]] = []
        self._recovery_callbacks: dict[str, Callable] = {}

    def set_strategy(self, strategy: str, **kwargs) -> None:
        """Set the error handling strategy."""
        if strategy == "fail_fast":
            self._strategy = ParallelErrorStrategy.FAIL_FAST
        elif strategy == "collect_all":
            self._strategy = ParallelErrorStrategy.COLLECT_ALL
        elif strategy == "best_effort":
            self._strategy = ParallelErrorStrategy.BEST_EFFORT
        elif strategy == "threshold":
            self._strategy = ParallelErrorStrategy.THRESHOLD
        elif strategy == "continue_on_error":
            self._strategy = ParallelErrorStrategy.BEST_EFFORT  # Map to existing strategy
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # Update config with additional parameters
        self.config.strategy = self._strategy
        if "error_threshold" in kwargs:
            self.config.error_threshold = kwargs["error_threshold"]
        if "max_errors" in kwargs:
            self.config.max_errors = kwargs["max_errors"]
        if "timeout_seconds" in kwargs:
            self.config.timeout_seconds = kwargs["timeout_seconds"]

        self.aggregator.config = self.config

    def handle_task_error(self, error: WorkflowError, total_tasks: int = None) -> dict[str, Any]:
        """Handle an error from a parallel task.

        Returns:
            Dict with action and reason for the error handling decision
        """
        # Set total tasks if provided
        if total_tasks is not None:
            self.aggregator.set_total_tasks(total_tasks)

        # Add error to aggregator (use step_id as task_id)
        task_id = error.step_id or f"task_{error.id}"
        self.aggregator.add_task_error(task_id, error)

        # Notify error callbacks
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

        # Get current stats
        summary = self.aggregator.get_error_summary()
        failed_count = summary["failed_tasks"]

        # Apply strategy and return decision
        if self._strategy == ParallelErrorStrategy.FAIL_FAST:
            return {"action": "stop_all", "reason": "fail_fast", "failed_count": failed_count}
        elif self._strategy == ParallelErrorStrategy.COLLECT_ALL:
            return {"action": "continue", "reason": "collect_all", "failed_count": failed_count}
        elif self._strategy == ParallelErrorStrategy.BEST_EFFORT:
            return {"action": "continue", "reason": "best_effort", "failed_count": failed_count}
        elif self._strategy == ParallelErrorStrategy.THRESHOLD:
            if self.aggregator.should_fail_fast():
                return {"action": "stop_all", "reason": "threshold_exceeded", "failed_count": failed_count}
            else:
                return {"action": "continue", "reason": "threshold_not_exceeded", "failed_count": failed_count}

        return {"action": "continue", "reason": "default", "failed_count": failed_count}

    def add_error_callback(self, callback: Callable[[WorkflowError], None]) -> None:
        """Add a callback to be called when errors occur."""
        self._error_callbacks.append(callback)

    def add_recovery_callback(self, error_type: str, callback: Callable) -> None:
        """Add a recovery callback for specific error types."""
        self._recovery_callbacks[error_type] = callback

    def attempt_recovery(self, task_id: str, error: WorkflowError) -> bool:
        """Attempt to recover from a task error."""
        error_type = error.error_type
        if error_type in self._recovery_callbacks:
            try:
                recovery_callback = self._recovery_callbacks[error_type]
                result = recovery_callback(task_id, error)

                # Mark as recovered if successful
                if result and task_id in self.aggregator._task_errors:
                    self.aggregator._task_errors[task_id].recovered = True
                    self.aggregator._task_errors[task_id].recovery_actions.append(error_type)

                return result
            except Exception as e:
                logger.error(f"Recovery callback failed for {task_id}: {e}")
                return False

        return False

    def get_results_summary(self) -> dict[str, Any]:
        """Get a summary of parallel execution results."""
        summary = self.aggregator.get_error_summary()
        summary.update(
            {
                "strategy": self._strategy.value,
                "should_fail": self.aggregator.should_fail_fast(),
                "recoverable_errors": sum(1 for info in self.aggregator._task_errors.values() if info.recovered),
            }
        )
        return summary


class ParallelRecoveryCoordinator:
    """Coordinates recovery actions across parallel tasks."""

    def __init__(self):
        """Initialize the recovery coordinator."""
        self._lock = threading.RLock()
        self._recovery_actions: dict[str, list[str]] = defaultdict(list)
        self._task_dependencies: dict[str, list[str]] = {}
        self._recovery_callbacks: dict[str, Callable] = {}
        self._coordination_callbacks: list[Callable] = []

    def register_recovery_action(self, action_type: str, callback: Callable) -> None:
        """Register a recovery action callback."""
        with self._lock:
            self._recovery_callbacks[action_type] = callback

    def add_coordination_callback(self, callback: Callable) -> None:
        """Add a callback for coordinating recovery across tasks."""
        self._coordination_callbacks.append(callback)

    def add_recovery_rule(self, error_type: str, recovery_action: str, max_retries: int = 3, **kwargs) -> None:
        """Add a recovery rule for a specific error type."""
        log_level = kwargs.get("log_level", "info")

        # Store rule metadata for later access
        rule_metadata = {"action": recovery_action, "max_retries": max_retries, "log_level": log_level, **kwargs}

        def recovery_callback(task_id: str, error: WorkflowError) -> dict:
            # Simple recovery logic based on action type
            if recovery_action == "retry":
                # In a real implementation, this would trigger a retry
                if log_level == "warning":
                    logger.warning(f"Retrying task {task_id} for error type {error_type}")
                else:
                    logger.info(f"Retrying task {task_id} for error type {error_type}")
                return {"success": True, "metadata": rule_metadata}
            elif recovery_action == "skip":
                if log_level == "warning":
                    logger.warning(f"Skipping task {task_id} for error type {error_type}")
                else:
                    logger.info(f"Skipping task {task_id} for error type {error_type}")
                return {"success": True, "metadata": rule_metadata}
            elif recovery_action == "fallback":
                if log_level == "warning":
                    logger.warning(f"Using fallback for task {task_id} for error type {error_type}")
                else:
                    logger.info(f"Using fallback for task {task_id} for error type {error_type}")
                return {"success": True, "metadata": rule_metadata}
            return {"success": False, "metadata": rule_metadata}

        self.register_recovery_action(error_type, recovery_callback)

    def set_task_dependencies(self, task_id: str, dependencies: list[str]) -> None:
        """Set dependencies for a task."""
        with self._lock:
            self._task_dependencies[task_id] = dependencies

    def coordinate_recovery(self, failed_tasks) -> dict[str, Any]:
        """Coordinate recovery actions across failed tasks."""
        # Handle single error case
        if hasattr(failed_tasks, "error_type"):  # It's a WorkflowError
            error = failed_tasks
            task_id = error.step_id or f"task_{error.id}"

            # Try to find a recovery action for this error type
            if error.error_type in self._recovery_callbacks:
                try:
                    callback = self._recovery_callbacks[error.error_type]
                    result = callback(task_id, error)
                    if isinstance(result, dict) and result.get("success"):
                        metadata = result.get("metadata", {})
                        action = metadata.get("action", "unknown")
                        response = {"action": action}

                        # Add specific fields based on action
                        if action == "retry":
                            response["retry_count"] = 1
                        if "log_level" in metadata:
                            response["log_level"] = metadata["log_level"]
                        if "max_retries" in metadata:
                            response["max_retries"] = metadata["max_retries"]

                        return response
                    else:
                        return {"action": "fail", "success": False}
                except Exception as e:
                    logger.error(f"Recovery callback failed for {task_id}: {e}")
                    return {"action": "fail", "success": False}
            else:
                return {"action": "no_recovery", "success": False}

        # Handle multiple tasks case (original implementation)
        with self._lock:
            recovery_results = {}

            # Sort tasks by dependencies (recover dependencies first)
            sorted_tasks = self._sort_by_dependencies(list(failed_tasks.keys()))

            for task_id in sorted_tasks:
                task_info = failed_tasks[task_id]
                error = task_info.error

                # Attempt recovery
                recovery_successful = False

                # Try registered recovery actions
                for action_type, callback in self._recovery_callbacks.items():
                    try:
                        if callback(task_id, error):
                            recovery_successful = True
                            task_info.recovered = True
                            task_info.recovery_actions.append(action_type)
                            self._recovery_actions[task_id].append(action_type)
                            break
                    except Exception as e:
                        logger.error(f"Recovery action {action_type} failed for {task_id}: {e}")

                recovery_results[task_id] = recovery_successful

                # Notify coordination callbacks
                for callback in self._coordination_callbacks:
                    try:
                        callback(task_id, recovery_successful, task_info)
                    except Exception as e:
                        logger.error(f"Coordination callback failed: {e}")

            return recovery_results

    def _sort_by_dependencies(self, task_ids: list[str]) -> list[str]:
        """Sort tasks by their dependencies."""
        # Simple topological sort
        sorted_tasks = []
        remaining_tasks = set(task_ids)

        while remaining_tasks:
            # Find tasks with no unmet dependencies
            ready_tasks = []
            for task_id in remaining_tasks:
                dependencies = self._task_dependencies.get(task_id, [])
                if all(dep not in remaining_tasks for dep in dependencies):
                    ready_tasks.append(task_id)

            if not ready_tasks:
                # Circular dependency or orphaned tasks, just add remaining
                ready_tasks = list(remaining_tasks)

            sorted_tasks.extend(ready_tasks)
            remaining_tasks.difference_update(ready_tasks)

        return sorted_tasks

    def get_recovery_summary(self) -> dict[str, Any]:
        """Get a summary of recovery actions taken."""
        with self._lock:
            return {
                "total_recovery_attempts": len(self._recovery_actions),
                "recovery_actions_by_task": dict(self._recovery_actions),
                "available_recovery_types": list(self._recovery_callbacks.keys()),
                "task_dependencies": dict(self._task_dependencies),
            }

    def clear_recovery_history(self) -> None:
        """Clear recovery action history."""
        with self._lock:
            self._recovery_actions.clear()
