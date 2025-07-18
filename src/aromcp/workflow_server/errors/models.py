"""Error handling models for the MCP Workflow System."""

import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ErrorStrategyType(Enum):
    """Error handling strategies."""
    FAIL = "fail"
    CONTINUE = "continue"
    RETRY = "retry"
    FALLBACK = "fallback"
    CIRCUIT_BREAKER = "circuit_breaker"


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorHandler:
    """Configuration for error handling behavior."""

    strategy: ErrorStrategyType
    retry_count: int = 3
    retry_delay: int = 1000  # milliseconds
    retry_backoff_multiplier: float = 2.0
    retry_max_delay: int = 30000  # milliseconds
    fallback_value: Any = None
    error_state_path: str | None = None

    # Circuit breaker configuration
    failure_threshold: int = 5
    circuit_timeout: int = 60000  # milliseconds

    # Conditional retry configuration
    retry_on_error_types: list[str] | None = None
    skip_retry_on_error_types: list[str] | None = None


@dataclass
class ErrorContext:
    """Context information about where an error occurred."""

    workflow_id: str
    step_id: str | None = None
    sub_agent_id: str | None = None
    task_id: str | None = None
    execution_context: dict[str, Any] | None = None
    state_snapshot: dict[str, Any] | None = None


@dataclass
class WorkflowError:
    """Detailed information about a workflow error."""

    id: str
    workflow_id: str
    step_id: str | None
    error_type: str
    message: str
    stack_trace: str | None
    timestamp: datetime
    retry_count: int = 0
    recovered: bool = False
    severity: ErrorSeverity = ErrorSeverity.MEDIUM

    # Context information
    context: ErrorContext | None = None

    # Error metadata
    original_exception: Exception | None = field(default=None, repr=False)
    error_data: dict[str, Any] | None = None

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        workflow_id: str,
        step_id: str | None = None,
        context: ErrorContext | None = None,
        retry_count: int = 0,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> "WorkflowError":
        """Create a WorkflowError from an exception."""
        import uuid

        return cls(
            id=f"err_{uuid.uuid4().hex[:8]}",
            workflow_id=workflow_id,
            step_id=step_id,
            error_type=type(exception).__name__,
            message=str(exception),
            stack_trace=traceback.format_exc(),
            timestamp=datetime.now(),
            retry_count=retry_count,
            context=context,
            original_exception=exception,
            severity=severity,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "error_type": self.error_type,
            "message": self.message,
            "stack_trace": self.stack_trace,
            "timestamp": self.timestamp.isoformat(),
            "retry_count": self.retry_count,
            "recovered": self.recovered,
            "severity": self.severity.value,
            "context": self.context.__dict__ if self.context else None,
            "error_data": self.error_data,
        }


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker pattern."""

    failure_count: int = 0
    last_failure_time: datetime | None = None
    state: str = "closed"  # "closed", "open", "half-open"
    next_attempt_time: datetime | None = None

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.state == "open"

    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == "half-open"

    def should_attempt(self) -> bool:
        """Check if we should attempt operation."""
        if self.state == "closed":
            return True
        elif self.state == "half-open":
            return True
        elif self.state == "open":
            return (
                self.next_attempt_time is not None and
                datetime.now() >= self.next_attempt_time
            )
        return False


@dataclass
class RetryState:
    """State tracking for retry operations."""

    attempt_count: int = 0
    last_attempt_time: datetime | None = None
    next_retry_time: datetime | None = None
    cumulative_delay: int = 0
    errors: list[WorkflowError] = field(default_factory=list)

    def should_retry(self, max_retries: int) -> bool:
        """Check if we should retry based on current state."""
        return self.attempt_count < max_retries

    def add_error(self, error: WorkflowError):
        """Add an error to the retry state."""
        self.errors.append(error)
        self.attempt_count += 1
        self.last_attempt_time = datetime.now()
