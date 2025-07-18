"""Retry mechanisms for the MCP Workflow System."""

import asyncio
import logging
import random
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from ..errors.models import (
    CircuitBreakerState,
    ErrorHandler,
    ErrorStrategyType,
    RetryState,
    WorkflowError,
)

logger = logging.getLogger(__name__)


class RetryManager:
    """Manages retry operations for workflow steps."""

    def __init__(self):
        self._retry_states: dict[str, RetryState] = {}
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._retry_callbacks: dict[str, Callable] = {}

    def register_retry_callback(self, operation_type: str, callback: Callable):
        """Register a callback for retry operations."""
        self._retry_callbacks[operation_type] = callback

    async def execute_with_retry(
        self,
        operation: Callable,
        operation_key: str,
        error_handler: ErrorHandler,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute an operation with retry logic."""

        retry_state = self._retry_states.get(operation_key, RetryState())

        while retry_state.should_retry(error_handler.retry_count):
            try:
                # Check circuit breaker
                if error_handler.strategy == ErrorStrategyType.CIRCUIT_BREAKER:
                    if not self._check_circuit_breaker(operation_key, error_handler):
                        return {
                            "success": False,
                            "error": "Circuit breaker is open",
                            "action": "circuit_breaker_open",
                        }

                # Execute the operation
                result = await self._execute_operation(operation, context)

                # Success - clear retry state and reset circuit breaker
                self._clear_retry_state(operation_key)
                self._reset_circuit_breaker_on_success(operation_key)

                return {
                    "success": True,
                    "result": result,
                    "attempts": retry_state.attempt_count + 1,
                }

            except Exception as e:
                # Create workflow error
                workflow_error = WorkflowError.from_exception(
                    e,
                    workflow_id=context.get("workflow_id", "unknown") if context else "unknown",
                    step_id=context.get("step_id") if context else None,
                    retry_count=retry_state.attempt_count,
                )

                # Check if we should retry this error type
                if not self._should_retry_error(workflow_error, error_handler):
                    logger.info(f"Not retrying error type {workflow_error.error_type}")
                    retry_state.add_error(workflow_error)
                    return {
                        "success": False,
                        "error": workflow_error.to_dict(),
                        "action": "fail_no_retry",
                    }

                # Add error to state
                retry_state.add_error(workflow_error)

                # Check if we've exceeded retry limit
                if not retry_state.should_retry(error_handler.retry_count):
                    logger.error(f"Max retries exceeded for {operation_key}")
                    return {
                        "success": False,
                        "error": workflow_error.to_dict(),
                        "action": "fail_max_retries",
                        "total_attempts": retry_state.attempt_count,
                    }

                # Calculate retry delay
                delay = self._calculate_retry_delay(
                    retry_state.attempt_count,
                    error_handler
                )

                retry_state.next_retry_time = datetime.now() + timedelta(milliseconds=delay)
                retry_state.cumulative_delay += delay
                self._retry_states[operation_key] = retry_state

                logger.info(
                    f"Retrying {operation_key} in {delay}ms "
                    f"(attempt {retry_state.attempt_count}/{error_handler.retry_count})"
                )

                # Wait for retry delay
                await asyncio.sleep(delay / 1000.0)

        # If we get here, we've exhausted retries
        return {
            "success": False,
            "error": "Max retries exceeded",
            "action": "fail_max_retries",
            "total_attempts": retry_state.attempt_count,
        }

    def _calculate_retry_delay(self, attempt: int, handler: ErrorHandler) -> int:
        """Calculate retry delay with exponential backoff and jitter."""
        base_delay = handler.retry_delay
        backoff_delay = base_delay * (handler.retry_backoff_multiplier ** attempt)

        # Apply max delay limit
        delay = min(backoff_delay, handler.retry_max_delay)

        # Add jitter (±20% randomness)
        jitter = delay * 0.2 * (random.random() - 0.5) * 2  # noqa: S311
        final_delay = max(100, delay + jitter)  # Minimum 100ms

        return int(final_delay)

    def _should_retry_error(self, error: WorkflowError, handler: ErrorHandler) -> bool:
        """Check if error type should be retried."""
        if handler.retry_on_error_types:
            return error.error_type in handler.retry_on_error_types

        if handler.skip_retry_on_error_types:
            return error.error_type not in handler.skip_retry_on_error_types

        # Default: retry most errors except critical ones
        non_retryable = ["AssertionError", "ValidationError", "PermissionError"]
        return error.error_type not in non_retryable

    def _check_circuit_breaker(self, operation_key: str, handler: ErrorHandler) -> bool:
        """Check if circuit breaker allows execution."""
        breaker = self._circuit_breakers.get(operation_key)
        if not breaker:
            return True

        now = datetime.now()

        if breaker.is_open():
            # Check if we should transition to half-open
            if breaker.next_attempt_time and now >= breaker.next_attempt_time:
                breaker.state = "half-open"
                logger.info(f"Circuit breaker transitioning to half-open for {operation_key}")
                return True
            return False

        return True

    def _reset_circuit_breaker_on_success(self, operation_key: str):
        """Reset circuit breaker state on successful execution."""
        breaker = self._circuit_breakers.get(operation_key)
        if breaker:
            if breaker.is_half_open():
                breaker.state = "closed"
                breaker.failure_count = 0
                logger.info(f"Circuit breaker closed for {operation_key}")

    def _update_circuit_breaker_on_failure(self, operation_key: str, handler: ErrorHandler):
        """Update circuit breaker state on failure."""
        breaker = self._circuit_breakers.get(operation_key, CircuitBreakerState())

        breaker.failure_count += 1
        breaker.last_failure_time = datetime.now()

        if breaker.failure_count >= handler.failure_threshold:
            breaker.state = "open"
            breaker.next_attempt_time = datetime.now() + timedelta(
                milliseconds=handler.circuit_timeout
            )
            logger.error(f"Circuit breaker opened for {operation_key}")

        self._circuit_breakers[operation_key] = breaker

    def _clear_retry_state(self, operation_key: str):
        """Clear retry state on successful execution."""
        if operation_key in self._retry_states:
            del self._retry_states[operation_key]

    async def _execute_operation(
        self,
        operation: Callable,
        context: dict[str, Any] | None
    ) -> Any:
        """Execute an operation, handling both sync and async functions."""
        if asyncio.iscoroutinefunction(operation):
            if context:
                return await operation(**context)
            else:
                return await operation()
        else:
            if context:
                return operation(**context)
            else:
                return operation()

    def get_retry_stats(self) -> dict[str, Any]:
        """Get retry statistics."""
        active_retries = {}
        circuit_breaker_stats = {}

        for key, retry_state in self._retry_states.items():
            active_retries[key] = {
                "attempt_count": retry_state.attempt_count,
                "last_attempt": retry_state.last_attempt_time.isoformat() if retry_state.last_attempt_time else None,
                "next_retry": retry_state.next_retry_time.isoformat() if retry_state.next_retry_time else None,
                "cumulative_delay": retry_state.cumulative_delay,
                "error_count": len(retry_state.errors),
            }

        for key, breaker in self._circuit_breakers.items():
            circuit_breaker_stats[key] = {
                "state": breaker.state,
                "failure_count": breaker.failure_count,
                "last_failure": breaker.last_failure_time.isoformat() if breaker.last_failure_time else None,
                "next_attempt": breaker.next_attempt_time.isoformat() if breaker.next_attempt_time else None,
            }

        return {
            "active_retries": active_retries,
            "circuit_breakers": circuit_breaker_stats,
            "total_retry_operations": len(self._retry_states),
            "total_circuit_breakers": len(self._circuit_breakers),
        }

    def reset_circuit_breaker(self, operation_key: str):
        """Manually reset a circuit breaker."""
        if operation_key in self._circuit_breakers:
            self._circuit_breakers[operation_key] = CircuitBreakerState()
            logger.info(f"Manually reset circuit breaker for {operation_key}")

    def clear_retry_state_for_workflow(self, workflow_id: str):
        """Clear all retry states for a specific workflow."""
        keys_to_remove = []
        for key in self._retry_states:
            if key.startswith(f"{workflow_id}:"):
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._retry_states[key]

        logger.info(f"Cleared retry states for workflow {workflow_id}")


class SubAgentRetryCoordinator:
    """Coordinates retry operations across sub-agents."""

    def __init__(self, retry_manager: RetryManager):
        self.retry_manager = retry_manager
        self._sub_agent_retries: dict[str, dict[str, Any]] = {}

    async def coordinate_sub_agent_retry(
        self,
        parent_workflow_id: str,
        sub_agent_id: str,
        failed_task: dict[str, Any],
        error_handler: ErrorHandler,
    ) -> dict[str, Any]:
        """Coordinate retry for a failed sub-agent task."""

        retry_key = f"{parent_workflow_id}:sub_agent:{sub_agent_id}"

        # Track sub-agent retry
        if retry_key not in self._sub_agent_retries:
            self._sub_agent_retries[retry_key] = {
                "parent_workflow_id": parent_workflow_id,
                "sub_agent_id": sub_agent_id,
                "retry_count": 0,
                "first_failure": datetime.now(),
                "failed_tasks": [],
            }

        retry_info = self._sub_agent_retries[retry_key]
        retry_info["failed_tasks"].append(failed_task)
        retry_info["retry_count"] += 1

        # Check if we should retry
        if retry_info["retry_count"] > error_handler.retry_count:
            logger.error(f"Max retries exceeded for sub-agent {sub_agent_id}")
            return {
                "action": "fail",
                "reason": "max_retries_exceeded",
                "retry_count": retry_info["retry_count"],
            }

        # Calculate retry delay for sub-agent coordination
        delay = self.retry_manager._calculate_retry_delay(
            retry_info["retry_count"] - 1,
            error_handler
        )

        logger.info(f"Retrying sub-agent {sub_agent_id} in {delay}ms")

        return {
            "action": "retry",
            "delay_ms": delay,
            "retry_count": retry_info["retry_count"],
            "failed_task": failed_task,
        }

    def get_sub_agent_retry_stats(self) -> dict[str, Any]:
        """Get sub-agent retry statistics."""
        return {
            "active_sub_agent_retries": len(self._sub_agent_retries),
            "sub_agent_details": {
                key: {
                    "retry_count": info["retry_count"],
                    "first_failure": info["first_failure"].isoformat(),
                    "failed_task_count": len(info["failed_tasks"]),
                }
                for key, info in self._sub_agent_retries.items()
            }
        }

    def clear_sub_agent_retry(self, parent_workflow_id: str, sub_agent_id: str):
        """Clear retry state for a specific sub-agent."""
        retry_key = f"{parent_workflow_id}:sub_agent:{sub_agent_id}"
        if retry_key in self._sub_agent_retries:
            del self._sub_agent_retries[retry_key]


class ExponentialBackoffCalculator:
    """Utility for calculating exponential backoff delays."""

    @staticmethod
    def calculate_delay(
        attempt: int,
        base_delay: int = 1000,
        multiplier: float = 2.0,
        max_delay: int = 30000,
        jitter: bool = True,
    ) -> int:
        """Calculate exponential backoff delay with optional jitter."""

        # Calculate exponential delay
        delay = base_delay * (multiplier ** attempt)

        # Apply maximum delay limit
        delay = min(delay, max_delay)

        # Add jitter if requested
        if jitter:
            jitter_amount = delay * 0.2 * (random.random() - 0.5) * 2  # noqa: S311
            delay = max(100, delay + jitter_amount)  # Minimum 100ms

        return int(delay)

    @staticmethod
    def calculate_total_delay(
        max_attempts: int,
        base_delay: int = 1000,
        multiplier: float = 2.0,
        max_delay: int = 30000,
    ) -> int:
        """Calculate total delay for all retry attempts."""
        total = 0
        for attempt in range(max_attempts):
            total += ExponentialBackoffCalculator.calculate_delay(
                attempt, base_delay, multiplier, max_delay, jitter=False
            )
        return total
