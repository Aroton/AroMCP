"""Error handler implementations for the MCP Workflow System."""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from .models import (
    CircuitBreakerState,
    ErrorHandler,
    ErrorStrategyType,
    RetryState,
    WorkflowError,
)

logger = logging.getLogger(__name__)


class ErrorHandlerRegistry:
    """Registry for error handlers and circuit breaker states."""

    def __init__(self):
        self._handlers: dict[str, ErrorHandler] = {}
        self._circuit_breakers: dict[str, CircuitBreakerState] = {}
        self._retry_states: dict[str, RetryState] = {}
        self._error_handlers: dict[ErrorStrategyType, Callable] = {
            ErrorStrategyType.FAIL: self._handle_fail,
            ErrorStrategyType.CONTINUE: self._handle_continue,
            ErrorStrategyType.RETRY: self._handle_retry,
            ErrorStrategyType.FALLBACK: self._handle_fallback,
            ErrorStrategyType.CIRCUIT_BREAKER: self._handle_circuit_breaker,
        }

    def register_handler(self, key: str, handler: ErrorHandler):
        """Register an error handler for a specific key."""
        self._handlers[key] = handler

        if handler.strategy == ErrorStrategyType.CIRCUIT_BREAKER:
            self._circuit_breakers[key] = CircuitBreakerState()

    def get_handler(self, key: str) -> ErrorHandler | None:
        """Get error handler for a key."""
        return self._handlers.get(key)

    def handle_error(
        self,
        error: WorkflowError,
        handler_key: str | None = None,
        default_handler: ErrorHandler | None = None,
    ) -> dict[str, Any]:
        """Handle an error using registered or default handler."""

        # Get the appropriate handler
        handler = None
        if handler_key:
            handler = self.get_handler(handler_key)

        if not handler:
            handler = default_handler or ErrorHandler(strategy=ErrorStrategyType.FAIL)

        # Execute the appropriate strategy
        strategy_handler = self._error_handlers.get(handler.strategy)
        if not strategy_handler:
            logger.error(f"Unknown error strategy: {handler.strategy}")
            return self._handle_fail(error, handler)

        try:
            return strategy_handler(error, handler)
        except Exception as e:
            logger.error(f"Error in error handler: {e}")
            return self._handle_fail(error, handler)

    def _handle_fail(self, error: WorkflowError, handler: ErrorHandler) -> dict[str, Any]:
        """Handle fail strategy - propagate the error."""
        logger.error(f"Workflow {error.workflow_id} failed at step {error.step_id}: {error.message}")

        result = {
            "action": "fail",
            "error": error.to_dict(),
            "should_continue": False,
        }

        # Update error state if specified
        if handler.error_state_path:
            result["state_updates"] = [
                {
                    "path": handler.error_state_path,
                    "value": error.to_dict(),
                }
            ]

        return result

    def _handle_continue(self, error: WorkflowError, handler: ErrorHandler) -> dict[str, Any]:
        """Handle continue strategy - log error and continue execution."""
        logger.warning(f"Workflow {error.workflow_id} error at step {error.step_id}: {error.message} (continuing)")

        result = {
            "action": "continue",
            "error": error.to_dict(),
            "should_continue": True,
        }

        # Update error state if specified
        if handler.error_state_path:
            result["state_updates"] = [
                {
                    "path": handler.error_state_path,
                    "value": error.to_dict(),
                }
            ]

        return result

    def _handle_retry(self, error: WorkflowError, handler: ErrorHandler) -> dict[str, Any]:
        """Handle retry strategy - attempt retry with exponential backoff."""
        retry_key = f"{error.workflow_id}:{error.step_id}"
        retry_state = self._retry_states.get(retry_key, RetryState())

        # Check if we should retry this error type
        if not self._should_retry_error_type(error, handler):
            logger.info(f"Skipping retry for error type: {error.error_type}")
            return self._handle_fail(error, handler)

        # Check retry limits
        if not retry_state.should_retry(handler.retry_count):
            logger.error(f"Max retries ({handler.retry_count}) exceeded for {retry_key}")
            return self._handle_fail(error, handler)

        # Calculate retry delay with exponential backoff
        retry_delay = min(
            handler.retry_delay * (handler.retry_backoff_multiplier**retry_state.attempt_count), handler.retry_max_delay
        )

        # Update retry state
        retry_state.add_error(error)
        retry_state.next_retry_time = datetime.now() + timedelta(milliseconds=retry_delay)
        retry_state.cumulative_delay += int(retry_delay)
        self._retry_states[retry_key] = retry_state

        logger.info(
            f"Retrying {retry_key} in {retry_delay}ms " f"(attempt {retry_state.attempt_count}/{handler.retry_count})"
        )

        result = {
            "action": "retry",
            "error": error.to_dict(),
            "should_continue": False,
            "retry_delay_ms": retry_delay,
            "retry_attempt": retry_state.attempt_count,
            "next_retry_time": retry_state.next_retry_time.isoformat(),
        }

        # Update error state if specified
        if handler.error_state_path:
            result["state_updates"] = [
                {
                    "path": handler.error_state_path,
                    "value": {
                        "error": error.to_dict(),
                        "retry_state": {
                            "attempt": retry_state.attempt_count,
                            "max_retries": handler.retry_count,
                            "next_retry": retry_state.next_retry_time.isoformat(),
                        },
                    },
                }
            ]

        return result

    def _handle_fallback(self, error: WorkflowError, handler: ErrorHandler) -> dict[str, Any]:
        """Handle fallback strategy - use fallback value and continue."""
        logger.warning(f"Using fallback value for {error.workflow_id}:{error.step_id}: {error.message}")

        result = {
            "action": "fallback",
            "error": error.to_dict(),
            "should_continue": True,
            "fallback_value": handler.fallback_value,
        }

        # Update error state if specified
        if handler.error_state_path:
            result["state_updates"] = [
                {
                    "path": handler.error_state_path,
                    "value": error.to_dict(),
                }
            ]

        return result

    def _handle_circuit_breaker(self, error: WorkflowError, handler: ErrorHandler) -> dict[str, Any]:
        """Handle circuit breaker strategy - prevent cascading failures."""
        breaker_key = f"{error.workflow_id}:{error.step_id}"
        breaker_state = self._circuit_breakers.get(breaker_key, CircuitBreakerState())

        # Update failure count
        breaker_state.failure_count += 1
        breaker_state.last_failure_time = datetime.now()

        # Check if we should open the circuit
        if breaker_state.failure_count >= handler.failure_threshold:
            breaker_state.state = "open"
            breaker_state.next_attempt_time = datetime.now() + timedelta(milliseconds=handler.circuit_timeout)
            logger.error(f"Circuit breaker opened for {breaker_key} after {breaker_state.failure_count} failures")

        self._circuit_breakers[breaker_key] = breaker_state

        result = {
            "action": "circuit_breaker",
            "error": error.to_dict(),
            "should_continue": False,
            "circuit_state": breaker_state.state,
            "failure_count": breaker_state.failure_count,
            "next_attempt_time": (
                breaker_state.next_attempt_time.isoformat() if breaker_state.next_attempt_time else None
            ),
        }

        # Update error state if specified
        if handler.error_state_path:
            result["state_updates"] = [
                {
                    "path": handler.error_state_path,
                    "value": {
                        "error": error.to_dict(),
                        "circuit_breaker": {
                            "state": breaker_state.state,
                            "failure_count": breaker_state.failure_count,
                            "threshold": handler.failure_threshold,
                        },
                    },
                }
            ]

        return result

    def _should_retry_error_type(self, error: WorkflowError, handler: ErrorHandler) -> bool:
        """Check if error type should be retried based on handler configuration."""
        if handler.retry_on_error_types:
            return error.error_type in handler.retry_on_error_types

        if handler.skip_retry_on_error_types:
            return error.error_type not in handler.skip_retry_on_error_types

        # Default: retry all error types
        return True

    def check_circuit_breaker(self, workflow_id: str, step_id: str) -> bool:
        """Check if circuit breaker allows execution."""
        breaker_key = f"{workflow_id}:{step_id}"
        breaker_state = self._circuit_breakers.get(breaker_key)

        if not breaker_state:
            return True

        return breaker_state.should_attempt()

    def reset_circuit_breaker(self, workflow_id: str, step_id: str):
        """Reset circuit breaker state on successful execution."""
        breaker_key = f"{workflow_id}:{step_id}"
        breaker_state = self._circuit_breakers.get(breaker_key)

        if breaker_state:
            if breaker_state.state == "half-open":
                # Success in half-open state - close the circuit
                breaker_state.state = "closed"
                breaker_state.failure_count = 0
                logger.info(f"Circuit breaker closed for {breaker_key}")
            elif breaker_state.state == "open":
                # Transition to half-open
                breaker_state.state = "half-open"
                logger.info(f"Circuit breaker half-open for {breaker_key}")

    def clear_retry_state(self, workflow_id: str, step_id: str):
        """Clear retry state on successful execution."""
        retry_key = f"{workflow_id}:{step_id}"
        if retry_key in self._retry_states:
            del self._retry_states[retry_key]

    def get_error_stats(self) -> dict[str, Any]:
        """Get error handling statistics."""
        return {
            "handlers_registered": len(self._handlers),
            "circuit_breakers": {
                key: {
                    "state": breaker.state,
                    "failure_count": breaker.failure_count,
                    "last_failure": breaker.last_failure_time.isoformat() if breaker.last_failure_time else None,
                }
                for key, breaker in self._circuit_breakers.items()
            },
            "active_retries": {
                key: {
                    "attempt_count": retry.attempt_count,
                    "last_attempt": retry.last_attempt_time.isoformat() if retry.last_attempt_time else None,
                    "next_retry": retry.next_retry_time.isoformat() if retry.next_retry_time else None,
                }
                for key, retry in self._retry_states.items()
            },
        }


class DefaultErrorHandlers:
    """Default error handler configurations."""

    @staticmethod
    def get_default_handlers() -> dict[str, ErrorHandler]:
        """Get default error handlers for common scenarios."""
        return {
            "shell_command_transient": ErrorHandler(
                strategy=ErrorStrategyType.RETRY,
                retry_count=3,
                retry_delay=1000,
                retry_on_error_types=["CalledProcessError", "TimeoutError", "ConnectionError"],
            ),
            "mcp_call_transient": ErrorHandler(
                strategy=ErrorStrategyType.RETRY,
                retry_count=5,
                retry_delay=500,
                retry_backoff_multiplier=1.5,
                retry_on_error_types=["ConnectionError", "TimeoutError", "ServerError"],
            ),
            "transformation_error": ErrorHandler(
                strategy=ErrorStrategyType.FALLBACK,
                fallback_value=None,
                error_state_path="raw.transformation_errors",
            ),
            "validation_error": ErrorHandler(
                strategy=ErrorStrategyType.FAIL,
                error_state_path="raw.validation_errors",
            ),
            "external_service": ErrorHandler(
                strategy=ErrorStrategyType.CIRCUIT_BREAKER,
                failure_threshold=5,
                circuit_timeout=60000,
                retry_count=3,
                retry_delay=2000,
            ),
        }

    @staticmethod
    def get_step_error_handler(step_type: str) -> ErrorHandler:
        """Get appropriate error handler for step type."""
        handlers = {
            "shell_command": ErrorHandler(
                strategy=ErrorStrategyType.RETRY,
                retry_count=2,
                retry_delay=1000,
            ),
            "mcp_call": ErrorHandler(
                strategy=ErrorStrategyType.RETRY,
                retry_count=3,
                retry_delay=500,
            ),
            "state_update": ErrorHandler(
                strategy=ErrorStrategyType.FAIL,
            ),
            "conditional": ErrorHandler(
                strategy=ErrorStrategyType.FAIL,
            ),
            "user_input": ErrorHandler(
                strategy=ErrorStrategyType.CONTINUE,
            ),
        }

        return handlers.get(step_type, ErrorHandler(strategy=ErrorStrategyType.FAIL))
