"""
Test suite for Error Handling & Resilience - Acceptance Criteria 8

This file tests the following acceptance criteria:
- AC 8.1: Step-Level Error Handling - error handling strategies (retry, continue, fail, fallback)
- AC 8.2: Timeout Management - step and workflow-level timeout handling
- AC 8.3: Validation Error Recovery - recovery and reporting for validation failures
- AC-EH-019: Parallel Error Aggregation - error handling in parallel execution
- AC-EH-020: Timeout Cascading - timeout propagation in nested operations

Maps to: /documentation/acceptance-criteria/workflow_server/error-handling-validation.md
"""

import time
from datetime import datetime, timedelta

import pytest

from aromcp.workflow_server.errors.handlers import (
    DefaultErrorHandlers,
    ErrorHandlerRegistry,
)
from aromcp.workflow_server.errors.models import (
    CircuitBreakerState,
    ErrorHandler,
    ErrorSeverity,
    ErrorStrategyType,
    RetryState,
    WorkflowError,
)
from aromcp.workflow_server.errors.tracking import (
    ErrorHistory,
    ErrorTracker,
)
from aromcp.workflow_server.workflow.retry import (
    ExponentialBackoffCalculator,
    RetryManager,
    SubAgentRetryCoordinator,
)


class TestErrorModels:
    """Test error model creation and validation."""

    def test_error_handler_creation(self):
        """Test ErrorHandler model creation."""
        handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=5,
            retry_delay=2000,
            retry_backoff_multiplier=1.5,
            fallback_value="default",
        )

        assert handler.strategy == ErrorStrategyType.RETRY
        assert handler.retry_count == 5
        assert handler.retry_delay == 2000
        assert handler.retry_backoff_multiplier == 1.5
        assert handler.fallback_value == "default"

    def test_workflow_error_from_exception(self):
        """Test creating WorkflowError from exception."""
        exception = ValueError("Test error message")

        error = WorkflowError.from_exception(
            exception,
            workflow_id="wf_test",
            step_id="step_1",
            retry_count=2,
            severity=ErrorSeverity.HIGH,
        )

        assert error.workflow_id == "wf_test"
        assert error.step_id == "step_1"
        assert error.error_type == "ValueError"
        assert error.message == "Test error message"
        assert error.retry_count == 2
        assert error.severity == ErrorSeverity.HIGH
        assert error.original_exception == exception
        assert error.stack_trace is not None
        # Verify error structure matches expected format
        assert error.workflow_id.startswith("wf_"), "Workflow ID should follow format"

    def test_workflow_error_to_dict(self):
        """Test WorkflowError serialization."""
        error = WorkflowError(
            id="err_123",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test message",
            stack_trace="Stack trace",
            timestamp=datetime.now(),
            retry_count=1,
            severity=ErrorSeverity.MEDIUM,
        )

        error_dict = error.to_dict()

        assert error_dict["id"] == "err_123"
        assert error_dict["workflow_id"] == "wf_test"
        assert error_dict["error_type"] == "TestError"
        assert error_dict["message"] == "Test message"
        assert error_dict["retry_count"] == 1
        assert error_dict["severity"] == "medium"
        # Verify error strategy validation
        assert "id" in error_dict and "message" in error_dict, "Error dict should have required fields"

    def test_circuit_breaker_state(self):
        """Test CircuitBreakerState functionality."""
        breaker = CircuitBreakerState()

        # Initially closed
        assert not breaker.is_open()
        assert breaker.should_attempt()

        # Open the circuit
        breaker.state = "open"
        breaker.next_attempt_time = datetime.now() + timedelta(minutes=1)

        assert breaker.is_open()
        assert not breaker.should_attempt()

        # Test half-open
        breaker.state = "half-open"
        assert breaker.is_half_open()
        assert breaker.should_attempt()

    def test_retry_state(self):
        """Test RetryState functionality."""
        retry_state = RetryState()

        # Initially should retry
        assert retry_state.should_retry(3)
        assert retry_state.attempt_count == 0

        # Add errors and check retry logic
        error1 = WorkflowError(
            id="err_1",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="First error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        retry_state.add_error(error1)
        assert retry_state.attempt_count == 1
        assert retry_state.should_retry(3)

        # Exceed retry limit
        for i in range(3):
            error = WorkflowError(
                id=f"err_{i+2}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type="TestError",
                message=f"Error {i+2}",
                stack_trace="",
                timestamp=datetime.now(),
            )
            retry_state.add_error(error)

        assert retry_state.attempt_count == 4
        assert not retry_state.should_retry(3)


class TestErrorHandlerRegistry:
    """Test error handler registry functionality."""

    def test_register_and_get_handler(self):
        """Test handler registration and retrieval."""
        registry = ErrorHandlerRegistry()

        handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
        )

        registry.register_handler("test_key", handler)
        retrieved = registry.get_handler("test_key")

        assert retrieved == handler
        assert registry.get_handler("nonexistent") is None

    def test_handle_fail_strategy(self):
        """Test fail error handling strategy."""
        registry = ErrorHandlerRegistry()

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        handler = ErrorHandler(strategy=ErrorStrategyType.FAIL)
        result = registry.handle_error(error, default_handler=handler)

        assert result["action"] == "fail"
        assert not result["should_continue"]
        assert result["error"]["id"] == "err_test"
        # Verify error message structure
        assert "error" in result and "code" in result["error"] or "message" in result["error"]

    def test_handle_continue_strategy(self):
        """Test continue error handling strategy."""
        registry = ErrorHandlerRegistry()

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        handler = ErrorHandler(strategy=ErrorStrategyType.CONTINUE)
        result = registry.handle_error(error, default_handler=handler)

        assert result["action"] == "continue"
        assert result["should_continue"]
        assert result["error"]["id"] == "err_test"
        # Verify error message structure
        assert "error" in result and "id" in result["error"]

    def test_handle_fallback_strategy(self):
        """Test fallback error handling strategy."""
        registry = ErrorHandlerRegistry()

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        handler = ErrorHandler(
            strategy=ErrorStrategyType.FALLBACK,
            fallback_value={"status": "fallback"},
        )
        result = registry.handle_error(error, default_handler=handler)

        assert result["action"] == "fallback"
        assert result["should_continue"]
        assert result["fallback_value"] == {"status": "fallback"}
        # Verify error structure format
        assert "error" in result

    def test_handle_retry_strategy(self):
        """Test retry error handling strategy."""
        registry = ErrorHandlerRegistry()

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_delay=1000,
        )
        result = registry.handle_error(error, default_handler=handler)

        assert result["action"] == "retry"
        assert not result["should_continue"]
        assert "retry_delay_ms" in result
        assert result["retry_attempt"] == 1

    def test_handle_circuit_breaker_strategy(self):
        """Test circuit breaker error handling strategy."""
        registry = ErrorHandlerRegistry()

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        handler = ErrorHandler(
            strategy=ErrorStrategyType.CIRCUIT_BREAKER,
            failure_threshold=3,
            circuit_timeout=30000,
        )
        result = registry.handle_error(error, default_handler=handler)

        assert result["action"] == "circuit_breaker"
        assert not result["should_continue"]
        assert "circuit_state" in result
        assert "failure_count" in result

    def test_circuit_breaker_functionality(self):
        """Test circuit breaker state management."""
        registry = ErrorHandlerRegistry()

        # Register circuit breaker handler
        handler = ErrorHandler(
            strategy=ErrorStrategyType.CIRCUIT_BREAKER,
            failure_threshold=2,
            circuit_timeout=1000,
        )
        registry.register_handler("test_circuit", handler)

        # Initially should allow attempts
        assert registry.check_circuit_breaker("wf_test", "step_1")

        # Trigger failures to open circuit
        for i in range(3):
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type="TestError",
                message=f"Error {i}",
                stack_trace="",
                timestamp=datetime.now(),
            )
            registry.handle_error(error, "test_circuit")

        # Circuit should be open now
        assert not registry.check_circuit_breaker("wf_test", "step_1")

    def test_retry_with_error_type_filtering(self):
        """Test retry with error type filtering."""
        registry = ErrorHandlerRegistry()

        # Handler that only retries specific error types
        handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_on_error_types=["ConnectionError", "TimeoutError"],
        )

        # Test with retryable error type
        retryable_error = WorkflowError(
            id="err_retryable",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="ConnectionError",
            message="Connection failed",
            stack_trace="",
            timestamp=datetime.now(),
        )

        result = registry.handle_error(retryable_error, default_handler=handler)
        assert result["action"] == "retry"

        # Test with non-retryable error type
        non_retryable_error = WorkflowError(
            id="err_non_retryable",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="ValidationError",
            message="Invalid input",
            stack_trace="",
            timestamp=datetime.now(),
        )

        result = registry.handle_error(non_retryable_error, default_handler=handler)
        assert result["action"] == "fail"


class TestErrorTracking:
    """Test error tracking and history functionality."""

    def test_error_history_basic_functionality(self):
        """Test basic error history operations."""
        history = ErrorHistory()

        error1 = WorkflowError(
            id="err_1",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="First error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        error2 = WorkflowError(
            id="err_2",
            workflow_id="wf_test",
            step_id="step_2",
            error_type="TestError",
            message="Second error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        history.add_error(error1)
        history.add_error(error2)

        # Test retrieval
        workflow_errors = history.get_workflow_errors("wf_test")
        assert len(workflow_errors) == 2
        assert workflow_errors[0].id == "err_1"
        assert workflow_errors[1].id == "err_2"

        # Test get by ID
        found_error = history.get_error_by_id("err_1")
        assert found_error is not None
        assert found_error.id == "err_1"

        # Test get by step
        step_errors = history.get_errors_by_step("wf_test", "step_1")
        assert len(step_errors) == 1
        assert step_errors[0].id == "err_1"

    def test_error_summary(self):
        """Test error summary generation."""
        history = ErrorHistory()

        # Add errors with different severities
        for i, severity in enumerate([ErrorSeverity.LOW, ErrorSeverity.MEDIUM, ErrorSeverity.HIGH]):
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type="TestError",
                message=f"Error {i}",
                stack_trace="",
                timestamp=datetime.now(),
                severity=severity,
            )
            history.add_error(error)

        summary = history.get_error_summary("wf_test")

        assert summary["total_errors"] == 3
        assert summary["by_severity"]["low"] == 1
        assert summary["by_severity"]["medium"] == 1
        assert summary["by_severity"]["high"] == 1
        assert summary["by_type"]["TestError"] == 3

    def test_error_tracker_functionality(self):
        """Test ErrorTracker comprehensive functionality."""
        tracker = ErrorTracker()

        # Track errors
        error1 = WorkflowError(
            id="err_1",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="ConnectionError",
            message="Connection failed",
            stack_trace="",
            timestamp=datetime.now(),
        )

        tracker.track_error(error1, "retry")

        # Mark as recovered
        tracker.mark_error_recovered("err_1")

        # Check recovery
        recovered_error = tracker.history.get_error_by_id("err_1")
        assert recovered_error is not None
        assert recovered_error.recovered

        # Check recovery stats
        recovery_stats = tracker.get_recovery_stats()
        assert recovery_stats["recovery_actions"]["retry"] == 1
        assert recovery_stats["recovery_actions"]["recovered"] == 1

    def test_error_pattern_detection(self):
        """Test error pattern detection."""
        tracker = ErrorTracker()

        # Simulate repeated errors
        base_time = datetime.now() - timedelta(hours=2)
        for i in range(5):
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type="ConnectionError",
                message="Connection failed",
                stack_trace="",
                timestamp=base_time + timedelta(minutes=i * 10),
            )
            tracker.track_error(error)

        patterns = tracker.detect_error_patterns()

        # Should detect pattern for ConnectionError on step_1
        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern["error_type"] == "ConnectionError"
        assert pattern["step_id"] == "step_1"
        assert pattern["occurrences"] == 5

    def test_error_trends(self):
        """Test error trend analysis."""
        tracker = ErrorTracker()

        # Add errors at different times
        base_time = datetime.now() - timedelta(hours=2)
        for i in range(10):
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type="TestError",
                message=f"Error {i}",
                stack_trace="",
                timestamp=base_time + timedelta(minutes=i * 15),
                severity=ErrorSeverity.HIGH if i < 3 else ErrorSeverity.MEDIUM,
            )
            tracker.track_error(error)

        trends = tracker.get_error_trends(hours=4)

        assert trends["total_recent"] == 10
        assert len(trends["hourly_counts"]) > 0
        assert len(trends["severity_trends"]) > 0

    def test_top_errors(self):
        """Test top errors analysis."""
        tracker = ErrorTracker()

        # Add different types of errors
        error_types = ["ConnectionError", "TimeoutError", "ConnectionError", "ValidationError", "ConnectionError"]

        for i, error_type in enumerate(error_types):
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type=error_type,
                message=f"{error_type} occurred",
                stack_trace="",
                timestamp=datetime.now(),
            )
            tracker.track_error(error)

        top_errors = tracker.get_top_errors(limit=3)

        assert len(top_errors) <= 3
        # ConnectionError should be top (3 occurrences)
        assert top_errors[0]["count"] == 3
        assert "ConnectionError" in top_errors[0]["error_signature"]


class TestRetryMechanism:
    """Test retry mechanisms and retry manager."""

    def test_exponential_backoff_calculator(self):
        """Test exponential backoff calculation."""
        # Test basic calculation
        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt=0,
            base_delay=1000,
            multiplier=2.0,
            max_delay=10000,
            jitter=False,
        )
        assert delay == 1000

        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt=1,
            base_delay=1000,
            multiplier=2.0,
            max_delay=10000,
            jitter=False,
        )
        assert delay == 2000

        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt=2,
            base_delay=1000,
            multiplier=2.0,
            max_delay=10000,
            jitter=False,
        )
        assert delay == 4000

        # Test max delay limit
        delay = ExponentialBackoffCalculator.calculate_delay(
            attempt=10,
            base_delay=1000,
            multiplier=2.0,
            max_delay=5000,
            jitter=False,
        )
        assert delay == 5000

        # Test total delay calculation
        total = ExponentialBackoffCalculator.calculate_total_delay(
            max_attempts=3,
            base_delay=1000,
            multiplier=2.0,
            max_delay=10000,
        )
        assert total == 7000  # 1000 + 2000 + 4000

    @pytest.mark.asyncio
    async def test_retry_manager_basic_functionality(self):
        """Test basic retry manager functionality."""
        retry_manager = RetryManager()

        # Mock operation that fails twice then succeeds
        call_count = 0

        async def mock_operation(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Mock failure")
            return {"success": True, "attempt": call_count}

        error_handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_delay=100,  # Short delay for testing
        )

        result = await retry_manager.execute_with_retry(
            mock_operation,
            "test_operation",
            error_handler,
            {"workflow_id": "wf_test", "step_id": "step_1"},
        )

        assert result["success"]
        assert result["attempts"] == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_manager_max_retries_exceeded(self):
        """Test retry manager when max retries exceeded."""
        retry_manager = RetryManager()

        # Mock operation that always fails
        async def mock_operation(**kwargs):
            raise Exception("Always fails")

        error_handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=2,
            retry_delay=50,
        )

        result = await retry_manager.execute_with_retry(
            mock_operation,
            "test_operation",
            error_handler,
            {"workflow_id": "wf_test", "step_id": "step_1"},
        )

        assert not result["success"]
        assert result["action"] == "fail_max_retries"
        assert result["total_attempts"] == 2

    @pytest.mark.asyncio
    async def test_retry_manager_with_error_type_filtering(self):
        """Test retry manager with error type filtering."""
        retry_manager = RetryManager()

        # Mock operation that throws non-retryable error
        async def mock_operation(**kwargs):
            raise ValueError("Validation error")

        error_handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_delay=50,
            retry_on_error_types=["ConnectionError", "TimeoutError"],
        )

        result = await retry_manager.execute_with_retry(
            mock_operation,
            "test_operation",
            error_handler,
            {"workflow_id": "wf_test", "step_id": "step_1"},
        )

        assert not result["success"]
        assert result["action"] == "fail_no_retry"

    def test_retry_manager_stats(self):
        """Test retry manager statistics."""
        retry_manager = RetryManager()

        # Create some retry states manually for testing
        from aromcp.workflow_server.errors.models import RetryState

        retry_state = RetryState()
        retry_state.attempt_count = 2
        retry_state.last_attempt_time = datetime.now()
        retry_manager._retry_states["wf_test:step_1"] = retry_state

        stats = retry_manager.get_retry_stats()

        assert "active_retries" in stats
        assert "wf_test:step_1" in stats["active_retries"]
        assert stats["active_retries"]["wf_test:step_1"]["attempt_count"] == 2
        assert stats["total_retry_operations"] == 1

    @pytest.mark.asyncio
    async def test_sub_agent_retry_coordinator(self):
        """Test sub-agent retry coordination."""
        retry_manager = RetryManager()
        coordinator = SubAgentRetryCoordinator(retry_manager)

        failed_task = {
            "task_id": "task_1",
            "batch_id": "batch_1",
            "error": "Processing failed",
        }

        error_handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_delay=1000,
        )

        # First retry attempt
        result = await coordinator.coordinate_sub_agent_retry(
            "wf_parent",
            "sub_agent_1",
            failed_task,
            error_handler,
        )

        assert result["action"] == "retry"
        assert result["retry_count"] == 1
        assert "delay_ms" in result

        # Subsequent retry attempts
        for i in range(2, 4):
            result = await coordinator.coordinate_sub_agent_retry(
                "wf_parent",
                "sub_agent_1",
                failed_task,
                error_handler,
            )
            assert result["action"] == "retry"
            assert result["retry_count"] == i

        # Should fail after max retries
        result = await coordinator.coordinate_sub_agent_retry(
            "wf_parent",
            "sub_agent_1",
            failed_task,
            error_handler,
        )

        assert result["action"] == "fail"
        assert result["reason"] == "max_retries_exceeded"


class TestDefaultErrorHandlers:
    """Test default error handler configurations."""

    def test_get_default_handlers(self):
        """Test default handler configurations."""
        handlers = DefaultErrorHandlers.get_default_handlers()

        assert "shell_command_transient" in handlers
        assert "mcp_call_transient" in handlers
        assert "transformation_error" in handlers
        assert "validation_error" in handlers
        assert "external_service" in handlers

        # Check shell command handler
        shell_handler = handlers["shell_command_transient"]
        assert shell_handler.strategy == ErrorStrategyType.RETRY
        assert shell_handler.retry_count == 3
        assert shell_handler.retry_on_error_types is not None
        assert "CalledProcessError" in shell_handler.retry_on_error_types

        # Check transformation handler
        transform_handler = handlers["transformation_error"]
        assert transform_handler.strategy == ErrorStrategyType.FALLBACK
        assert transform_handler.fallback_value is None

        # Check external service handler
        external_handler = handlers["external_service"]
        assert external_handler.strategy == ErrorStrategyType.CIRCUIT_BREAKER
        assert external_handler.failure_threshold == 5

    def test_get_step_error_handler(self):
        """Test step-specific error handlers."""
        shell_handler = DefaultErrorHandlers.get_step_error_handler("shell_command")
        assert shell_handler.strategy == ErrorStrategyType.RETRY
        assert shell_handler.retry_count == 2

        mcp_handler = DefaultErrorHandlers.get_step_error_handler("mcp_call")
        assert mcp_handler.strategy == ErrorStrategyType.RETRY
        assert mcp_handler.retry_count == 3

        state_handler = DefaultErrorHandlers.get_step_error_handler("state_update")
        assert state_handler.strategy == ErrorStrategyType.FAIL

        unknown_handler = DefaultErrorHandlers.get_step_error_handler("unknown_type")
        assert unknown_handler.strategy == ErrorStrategyType.FAIL


class TestPhase5AcceptanceCriteria:
    """Test Phase 5 acceptance criteria."""

    def test_step_level_error_handlers_work(self):
        """AC: Step-level error handlers work."""
        registry = ErrorHandlerRegistry()

        # Register step-specific handler
        handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=2,
            retry_delay=500,
        )
        registry.register_handler("step_1_handler", handler)

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Step error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        result = registry.handle_error(error, "step_1_handler")

        assert result["action"] == "retry"
        assert result["retry_attempt"] == 1

    def test_retry_with_exponential_backoff(self):
        """AC: Retry with exponential backoff."""
        registry = ErrorHandlerRegistry()

        handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_delay=1000,
            retry_backoff_multiplier=2.0,
        )

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        # First retry
        result1 = registry.handle_error(error, default_handler=handler)
        assert result1["action"] == "retry"
        delay1 = result1["retry_delay_ms"]

        # Second retry (same error key)
        result2 = registry.handle_error(error, default_handler=handler)
        assert result2["action"] == "retry"
        delay2 = result2["retry_delay_ms"]

        # Delay should increase (exponential backoff)
        assert delay2 > delay1

    def test_fallback_values_applied_correctly(self):
        """AC: Fallback values applied correctly."""
        registry = ErrorHandlerRegistry()

        fallback_data = {"status": "fallback", "value": 42}
        handler = ErrorHandler(
            strategy=ErrorStrategyType.FALLBACK,
            fallback_value=fallback_data,
        )

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        result = registry.handle_error(error, default_handler=handler)

        assert result["action"] == "fallback"
        assert result["should_continue"]
        assert result["fallback_value"] == fallback_data

    def test_error_state_tracking_works(self):
        """AC: Error state tracking works."""
        registry = ErrorHandlerRegistry()

        handler = ErrorHandler(
            strategy=ErrorStrategyType.FAIL,
            error_state_path="raw.last_error",
        )

        error = WorkflowError(
            id="err_test",
            workflow_id="wf_test",
            step_id="step_1",
            error_type="TestError",
            message="Test error",
            stack_trace="",
            timestamp=datetime.now(),
        )

        result = registry.handle_error(error, default_handler=handler)

        assert "state_updates" in result
        updates = result["state_updates"]
        assert len(updates) == 1
        assert updates[0]["path"] == "raw.last_error"
        assert updates[0]["value"]["id"] == "err_test"

    def test_circuit_breakers_prevent_cascading_failures(self):
        """AC: Circuit breakers prevent cascading failures."""
        registry = ErrorHandlerRegistry()

        handler = ErrorHandler(
            strategy=ErrorStrategyType.CIRCUIT_BREAKER,
            failure_threshold=2,
            circuit_timeout=5000,
        )
        registry.register_handler("circuit_test", handler)

        # Initial check - should allow
        assert registry.check_circuit_breaker("wf_test", "step_1")

        # Trigger failures to open circuit
        for i in range(3):
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_test",
                step_id="step_1",
                error_type="TestError",
                message=f"Error {i}",
                stack_trace="",
                timestamp=datetime.now(),
            )
            registry.handle_error(error, "circuit_test")  # Result not used

        # Circuit should be open, preventing further attempts
        assert not registry.check_circuit_breaker("wf_test", "step_1")

        # Get stats to verify circuit state
        stats = registry.get_error_stats()
        assert "wf_test:step_1" in stats["circuit_breakers"]
        breaker_state = stats["circuit_breakers"]["wf_test:step_1"]
        assert breaker_state["state"] == "open"
        assert breaker_state["failure_count"] >= 2


class TestTimeoutManagement:
    """Test comprehensive timeout management - AC 8.2 and AC-EH-020"""

    def test_step_level_timeout_enforcement(self):
        """Test step-level timeout enforcement with TimeoutManager (AC 8.2)."""
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        timeout_manager = TimeoutManager()

        # Set step timeout
        timeout_manager.set_step_timeout("step_1", timeout_seconds=1.0)

        # Start step execution
        timeout_manager.start_step("step_1")

        # Check timeout immediately - should not be timed out
        assert not timeout_manager.check_timeout("step_1")

        # Wait for timeout
        import time

        time.sleep(1.1)

        # Should now be timed out
        assert timeout_manager.check_timeout("step_1")

        # Get timeout info
        info = timeout_manager.get_timeout_status("step_1")
        assert info["exceeded"]
        assert info["elapsed_seconds"] > 1.0

    def test_workflow_level_timeout_management(self):
        """Test workflow-level timeout management (AC 8.2)."""
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        timeout_manager = TimeoutManager()

        # Set workflow timeout
        timeout_manager.set_workflow_timeout("wf_123", timeout_seconds=5.0)

        # Start workflow
        timeout_manager.start_workflow("wf_123")

        # Execute multiple steps
        for i in range(3):
            timeout_manager.start_step(f"step_{i}", workflow_id="wf_123")
            time.sleep(0.5)
            timeout_manager.end_step(f"step_{i}")

        # Check workflow timeout - should not exceed yet
        assert not timeout_manager.check_workflow_timeout("wf_123")

        # Continue with more steps until timeout
        timeout_manager.start_step("step_long", workflow_id="wf_123")
        time.sleep(4.0)

        # Should now exceed workflow timeout
        assert timeout_manager.check_workflow_timeout("wf_123")

    def test_timeout_cascading_in_nested_operations(self):
        """Test timeout cascading in nested operations (AC-EH-020)."""
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        timeout_manager = TimeoutManager()

        # Set parent and child timeouts
        timeout_manager.set_step_timeout("parent_step", timeout_seconds=2.0)
        timeout_manager.set_step_timeout("child_step", timeout_seconds=1.0)

        # Start parent operation
        timeout_manager.start_step("parent_step")
        parent_start = time.time()

        # Start child operation
        time.sleep(0.5)
        timeout_manager.start_step("child_step", parent_step="parent_step")

        # Child should timeout first (after 1.0s from child start)
        time.sleep(1.1)  # Total 1.6s from parent start, 1.1s from child start
        assert timeout_manager.check_timeout("child_step")
        assert not timeout_manager.check_timeout("parent_step")

        # Parent should timeout later
        time.sleep(0.5)  # Total 2.1s from parent start
        assert timeout_manager.check_timeout("parent_step")

        # Verify cascade relationship
        cascade_info = timeout_manager.get_cascade_info("parent_step")
        assert "child_step" in cascade_info["child_timeouts"]

    def test_timeout_with_resource_cleanup(self):
        """Test timeout handling with resource cleanup (AC-EH-020)."""
        from aromcp.workflow_server.workflow.resource_manager import ResourceManager
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        timeout_manager = TimeoutManager()
        resource_manager = ResourceManager()

        workflow_id = "wf_timeout"

        # Allocate resources
        resource_manager.allocate_resources(workflow_id=workflow_id, requested_memory_mb=50)

        # Set timeout with cleanup callback
        def cleanup_resources():
            resource_manager.release_resources(workflow_id)

        timeout_manager.set_workflow_timeout(workflow_id, timeout_seconds=1.0, cleanup_callback=cleanup_resources)

        # Start workflow
        timeout_manager.start_workflow(workflow_id)

        # Wait for timeout
        time.sleep(1.1)

        # Check timeout and trigger cleanup
        if timeout_manager.check_workflow_timeout(workflow_id):
            timeout_manager.handle_timeout(workflow_id)

        # Verify resources were cleaned up
        usage = resource_manager.get_workflow_usage(workflow_id)
        assert usage is None or usage.get("memory_mb", 0) == 0


class TestParallelErrorAggregation:
    """Test error handling in parallel execution - AC-EH-019"""

    def test_parallel_error_collection(self):
        """Test error collection from parallel tasks (AC-EH-019)."""
        from aromcp.workflow_server.errors.parallel import ParallelErrorAggregator

        aggregator = ParallelErrorAggregator()

        # Simulate parallel task errors
        task_errors = [
            WorkflowError(
                id=f"err_task_{i}",
                workflow_id="wf_parallel",
                step_id=f"parallel_task_{i}",
                error_type="TaskError",
                message=f"Task {i} failed",
                stack_trace="",
                timestamp=datetime.now(),
            )
            for i in range(5)
        ]

        # Add errors from different tasks
        for error in task_errors:
            aggregator.add_task_error(error.step_id, error)

        # Get aggregated errors
        aggregated = aggregator.get_aggregated_errors()
        assert len(aggregated) == 5

        # Get summary
        summary = aggregator.get_error_summary()
        assert summary["total_tasks"] == 5
        assert summary["failed_tasks"] == 5
        assert summary["error_types"]["TaskError"] == 5

    def test_parallel_error_strategies(self):
        """Test different error strategies in parallel execution (AC-EH-019)."""
        from aromcp.workflow_server.errors.parallel import ParallelErrorHandler

        handler = ParallelErrorHandler()

        # Configure fail-fast strategy
        handler.set_strategy("fail_fast")

        # First error should stop execution
        error1 = WorkflowError(
            id="err_1",
            workflow_id="wf_parallel",
            step_id="task_1",
            error_type="CriticalError",
            message="Critical failure",
            stack_trace="",
            timestamp=datetime.now(),
        )

        result = handler.handle_task_error(error1, total_tasks=10)
        assert result["action"] == "stop_all"
        assert result["reason"] == "fail_fast"

        # Test continue strategy
        handler.set_strategy("continue_on_error")

        result = handler.handle_task_error(error1, total_tasks=10)
        assert result["action"] == "continue"
        assert result["failed_count"] == 1

    def test_parallel_error_threshold_handling(self):
        """Test error threshold handling in parallel execution (AC-EH-019)."""
        from aromcp.workflow_server.errors.parallel import ParallelErrorHandler

        handler = ParallelErrorHandler()
        handler.set_strategy("threshold", error_threshold=0.3)  # 30% failure threshold

        # Simulate errors accumulating
        errors_added = 0
        total_tasks = 10

        for i in range(4):  # 40% failure rate
            error = WorkflowError(
                id=f"err_{i}",
                workflow_id="wf_parallel",
                step_id=f"task_{i}",
                error_type="TaskError",
                message=f"Task {i} failed",
                stack_trace="",
                timestamp=datetime.now(),
            )

            result = handler.handle_task_error(error, total_tasks=total_tasks)
            errors_added += 1

            if errors_added / total_tasks > 0.3:
                assert result["action"] == "stop_all"
                assert result["reason"] == "threshold_exceeded"
                break
            else:
                assert result["action"] == "continue"

    def test_parallel_error_recovery_coordination(self):
        """Test error recovery coordination in parallel tasks (AC-EH-019)."""
        from aromcp.workflow_server.errors.parallel import ParallelRecoveryCoordinator

        coordinator = ParallelRecoveryCoordinator()

        # Configure recovery for specific error types
        coordinator.add_recovery_rule(error_type="TransientError", recovery_action="retry", max_retries=3)

        coordinator.add_recovery_rule(error_type="DataError", recovery_action="skip", log_level="warning")

        # Test transient error recovery
        transient_error = WorkflowError(
            id="err_transient",
            workflow_id="wf_parallel",
            step_id="task_1",
            error_type="TransientError",
            message="Network timeout",
            stack_trace="",
            timestamp=datetime.now(),
        )

        recovery = coordinator.coordinate_recovery(transient_error)
        assert recovery["action"] == "retry"
        assert recovery["retry_count"] == 1

        # Test data error recovery
        data_error = WorkflowError(
            id="err_data",
            workflow_id="wf_parallel",
            step_id="task_2",
            error_type="DataError",
            message="Invalid input data",
            stack_trace="",
            timestamp=datetime.now(),
        )

        recovery = coordinator.coordinate_recovery(data_error)
        assert recovery["action"] == "skip"
        assert recovery["log_level"] == "warning"


class TestTimeoutIntegrationWithErrors:
    """Test timeout integration with error handling"""

    def test_timeout_error_handler_interaction(self):
        """Test interaction between timeout and error handlers (AC 8.2 + AC-EH-020)."""
        from aromcp.workflow_server.errors.handlers import ErrorHandlerRegistry
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        timeout_manager = TimeoutManager()
        error_registry = ErrorHandlerRegistry()

        # Register timeout error handler
        timeout_handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY, retry_count=2, retry_delay=500, retry_on_error_types=["TimeoutError"]
        )
        error_registry.register_handler("timeout_handler", timeout_handler)

        # Simulate timeout error
        timeout_error = WorkflowError(
            id="err_timeout",
            workflow_id="wf_test",
            step_id="slow_step",
            error_type="TimeoutError",
            message="Step execution timed out after 5 seconds",
            stack_trace="",
            timestamp=datetime.now(),
        )

        # Handle timeout error
        result = error_registry.handle_error(timeout_error, "timeout_handler")
        assert result["action"] == "retry"
        assert result["retry_delay_ms"] == 500

    def test_cascading_timeout_with_monitoring(self):
        """Test cascading timeouts with performance monitoring (AC-EH-020)."""
        from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        timeout_manager = TimeoutManager()
        monitor = PerformanceMonitor()

        # Monitor timeout events
        monitor.start_operation("timeout_cascade_test")

        # Set up cascading timeouts
        parent_timeout = 5.0
        child_timeouts = [1.0, 2.0, 3.0]

        timeout_manager.set_step_timeout("parent", timeout_seconds=parent_timeout)
        timeout_manager.start_step("parent")

        # Start child operations with their own timeouts
        for i, child_timeout in enumerate(child_timeouts):
            child_id = f"child_{i}"
            timeout_manager.set_step_timeout(child_id, timeout_seconds=child_timeout)
            timeout_manager.start_step(child_id, parent_step="parent")

            # Record timeout configuration
            monitor.record_metric("timeout_configured", child_timeout, {"step": child_id})

        # Simulate execution and check timeouts
        time.sleep(1.5)

        # First child should timeout
        assert timeout_manager.check_timeout("child_0")
        monitor.record_event("timeout_triggered", {"step": "child_0"})

        # Check monitoring data
        events = monitor.get_events("timeout_triggered")
        assert len(events) >= 1
        assert events[0]["data"]["step"] == "child_0"

    def test_parallel_timeout_error_aggregation(self):
        """Test timeout errors in parallel execution with aggregation (AC-EH-019 + AC-EH-020)."""
        from aromcp.workflow_server.errors.parallel import ParallelErrorAggregator
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

        aggregator = ParallelErrorAggregator()
        timeout_manager = TimeoutManager()

        # Simulate parallel tasks with different timeouts
        task_configs = [
            ("task_fast", 1.0),
            ("task_medium", 2.0),
            ("task_slow", 0.5),  # This will timeout first
        ]

        # Start all tasks
        for task_id, timeout in task_configs:
            timeout_manager.set_step_timeout(task_id, timeout_seconds=timeout)
            timeout_manager.start_step(task_id)

        # Wait and check for timeouts
        time.sleep(0.6)

        # Collect timeout errors
        for task_id, _ in task_configs:
            if timeout_manager.check_timeout(task_id):
                timeout_error = WorkflowError(
                    id=f"err_{task_id}",
                    workflow_id="wf_parallel",
                    step_id=task_id,
                    error_type="TimeoutError",
                    message=f"{task_id} timed out",
                    stack_trace="",
                    timestamp=datetime.now(),
                )
                aggregator.add_task_error(task_id, timeout_error)

        # Check aggregated timeout errors
        summary = aggregator.get_error_summary()
        assert summary["error_types"]["TimeoutError"] >= 1
        assert "task_slow" in [e.step_id for e in aggregator.get_aggregated_errors()]
