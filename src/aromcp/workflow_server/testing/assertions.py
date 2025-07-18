"""Assertion helpers for testing workflow components."""

import json
from typing import Any

from ..errors.models import ErrorSeverity, WorkflowError


class WorkflowAssertions:
    """Assertions for workflow testing."""

    @staticmethod
    def assert_workflow_started(result: dict[str, Any], expected_name: str | None = None):
        """Assert workflow started successfully."""
        assert "workflow_id" in result, "Workflow start result should contain workflow_id"
        assert result["workflow_id"].startswith("wf_"), "Workflow ID should start with 'wf_'"

        if expected_name:
            assert "workflow_name" in result, "Result should contain workflow_name"
            assert result["workflow_name"] == expected_name, f"Expected workflow name {expected_name}"

    @staticmethod
    def assert_workflow_completed(status: dict[str, Any], expected_steps: int | None = None):
        """Assert workflow completed successfully."""
        assert "status" in status, "Status should contain status field"
        assert status["status"] in ["completed", "finished"], f"Expected completed status, got {status['status']}"

        if expected_steps:
            completed = status.get("completed_steps", 0)
            assert completed == expected_steps, f"Expected {expected_steps} completed steps, got {completed}"

    @staticmethod
    def assert_workflow_failed(status: dict[str, Any], expected_error: str | None = None):
        """Assert workflow failed as expected."""
        assert "status" in status, "Status should contain status field"
        assert status["status"] in ["failed", "error"], f"Expected failed status, got {status['status']}"

        if expected_error:
            error_msg = status.get("error", {}).get("message", "")
            assert expected_error in error_msg, f"Expected error '{expected_error}' in '{error_msg}'"

    @staticmethod
    def assert_step_executed(step_result: dict[str, Any], expected_type: str | None = None):
        """Assert step executed successfully."""
        assert "success" in step_result, "Step result should contain success field"
        assert step_result["success"], f"Step should succeed, got {step_result}"

        if expected_type:
            assert "type" in step_result, "Step result should contain type"
            assert step_result["type"] == expected_type, f"Expected step type {expected_type}"

    @staticmethod
    def assert_step_failed(step_result: dict[str, Any], expected_error: str | None = None):
        """Assert step failed as expected."""
        assert "success" in step_result, "Step result should contain success field"
        assert not step_result["success"], f"Step should fail, got {step_result}"

        if expected_error:
            error_msg = step_result.get("error", "")
            assert expected_error in str(error_msg), f"Expected error '{expected_error}' in '{error_msg}'"

    @staticmethod
    def assert_next_step(
        next_step: dict[str, Any] | None,
        expected_id: str | None = None,
        expected_type: str | None = None,
    ):
        """Assert next step properties."""
        if expected_id is None and expected_type is None:
            assert next_step is None, "Expected no next step"
            return

        assert next_step is not None, "Expected next step but got None"

        if expected_id:
            assert next_step.get("id") == expected_id, f"Expected step ID {expected_id}, got {next_step.get('id')}"

        if expected_type:
            assert next_step.get("type") == expected_type, (
                f"Expected step type {expected_type}, got {next_step.get('type')}"
            )

    @staticmethod
    def assert_workflow_progress(status: dict[str, Any], min_progress: float, max_progress: float = 100.0):
        """Assert workflow progress is within expected range."""
        progress = status.get("progress", 0)
        assert min_progress <= progress <= max_progress, (
            f"Expected progress between {min_progress}-{max_progress}, got {progress}"
        )

    @staticmethod
    def assert_execution_time(result: dict[str, Any], max_duration_ms: float):
        """Assert execution completed within time limit."""
        duration = result.get("duration_ms", 0)
        assert duration <= max_duration_ms, f"Execution took {duration}ms, expected <={max_duration_ms}ms"

    @staticmethod
    def assert_workflow_inputs_applied(state: dict[str, Any], expected_inputs: dict[str, Any]):
        """Assert workflow inputs were applied to state."""
        for key, expected_value in expected_inputs.items():
            assert key in state, f"Expected input '{key}' not found in state"
            actual_value = state[key]
            assert actual_value == expected_value, f"Expected '{key}' = {expected_value}, got {actual_value}"


class StateAssertions:
    """Assertions for state testing."""

    @staticmethod
    def assert_state_contains(state: dict[str, Any], path: str, expected_value: Any = None):
        """Assert state contains a specific path."""
        assert path in state, f"State should contain path '{path}'. Available: {list(state.keys())}"

        if expected_value is not None:
            actual_value = state[path]
            assert actual_value == expected_value, f"Expected '{path}' = {expected_value}, got {actual_value}"

    @staticmethod
    def assert_state_not_contains(state: dict[str, Any], path: str):
        """Assert state does not contain a specific path."""
        assert path not in state, f"State should not contain path '{path}'"

    @staticmethod
    def assert_state_type(state: dict[str, Any], path: str, expected_type: type):
        """Assert state field has expected type."""
        assert path in state, f"State should contain path '{path}'"
        actual_value = state[path]
        assert isinstance(actual_value, expected_type), (
            f"Expected '{path}' to be {expected_type}, got {type(actual_value)}"
        )

    @staticmethod
    def assert_state_update_applied(
        before_state: dict[str, Any],
        after_state: dict[str, Any],
        updates: list[dict[str, Any]]
    ):
        """Assert state updates were applied correctly."""
        for update in updates:
            path = update["path"]
            expected_value = update["value"]
            operation = update.get("operation", "set")

            assert path in after_state, f"Updated path '{path}' should exist in after_state"

            if operation == "set":
                actual_value = after_state[path]
                assert actual_value == expected_value, f"Expected '{path}' = {expected_value}, got {actual_value}"
            elif operation == "increment":
                before_value = before_state.get(path, 0)
                increment = expected_value if expected_value is not None else 1
                expected_after = before_value + increment
                actual_value = after_state[path]
                assert actual_value == expected_after, f"Expected '{path}' = {expected_after}, got {actual_value}"
            elif operation == "append":
                before_list = before_state.get(path, [])
                expected_after = before_list + [expected_value]
                actual_value = after_state[path]
                assert actual_value == expected_after, f"Expected '{path}' = {expected_after}, got {actual_value}"

    @staticmethod
    def assert_computed_field_updated(state: dict[str, Any], field: str, dependencies: list[str]):
        """Assert computed field was updated when dependencies changed."""
        # This is a simplified check - in a real implementation, we'd track transformation history
        assert field in state, f"Computed field '{field}' should exist"

        for dep in dependencies:
            assert dep in state, f"Dependency '{dep}' should exist for computed field '{field}'"

    @staticmethod
    def assert_state_size_reasonable(state: dict[str, Any], max_size_kb: float = 1000):
        """Assert state size is within reasonable limits."""
        state_str = json.dumps(state)
        size_kb = len(state_str) / 1024
        assert size_kb <= max_size_kb, f"State size {size_kb:.1f}KB exceeds limit {max_size_kb}KB"

    @staticmethod
    def assert_flattened_view_precedence(
        flattened: dict[str, Any],
        raw_state: dict[str, Any],
        computed_state: dict[str, Any]
    ):
        """Assert flattened view follows correct precedence (computed > raw > state)."""
        # Check that computed values override raw values
        for key in computed_state:
            if key in raw_state:
                assert flattened[key] == computed_state[key], f"Computed value should override raw for '{key}'"

        # Check that raw values are present when no computed override
        for key in raw_state:
            if key not in computed_state:
                assert flattened[key] == raw_state[key], f"Raw value should be present for '{key}'"


class ErrorAssertions:
    """Assertions for error testing."""

    @staticmethod
    def assert_error_tracked(errors: list[WorkflowError], expected_type: str, workflow_id: str):
        """Assert specific error was tracked."""
        matching_errors = [
            e for e in errors
            if e.error_type == expected_type and e.workflow_id == workflow_id
        ]
        assert len(matching_errors) > 0, f"Expected error of type '{expected_type}' for workflow '{workflow_id}'"

    @staticmethod
    def assert_error_severity(error: WorkflowError, expected_severity: ErrorSeverity):
        """Assert error has expected severity."""
        assert error.severity == expected_severity, f"Expected severity {expected_severity}, got {error.severity}"

    @staticmethod
    def assert_error_recovered(error: WorkflowError):
        """Assert error was marked as recovered."""
        assert error.recovered, f"Error {error.id} should be marked as recovered"

    @staticmethod
    def assert_error_not_recovered(error: WorkflowError):
        """Assert error was not recovered."""
        assert not error.recovered, f"Error {error.id} should not be marked as recovered"

    @staticmethod
    def assert_error_retry_count(error: WorkflowError, expected_count: int):
        """Assert error has expected retry count."""
        assert error.retry_count == expected_count, f"Expected retry count {expected_count}, got {error.retry_count}"

    @staticmethod
    def assert_error_message_contains(error: WorkflowError, expected_text: str):
        """Assert error message contains expected text."""
        assert expected_text in error.message, f"Expected '{expected_text}' in error message: {error.message}"

    @staticmethod
    def assert_error_patterns_detected(patterns: list[dict[str, Any]], min_patterns: int = 1):
        """Assert error patterns were detected."""
        assert len(patterns) >= min_patterns, f"Expected at least {min_patterns} error patterns, got {len(patterns)}"

    @staticmethod
    def assert_error_rate_acceptable(error_rate: float, max_rate: float = 10.0):
        """Assert error rate is within acceptable limits."""
        assert error_rate <= max_rate, f"Error rate {error_rate}% exceeds limit {max_rate}%"

    @staticmethod
    def assert_mttr_acceptable(mttr_minutes: float | None, max_mttr: float = 60.0):
        """Assert Mean Time To Recovery is acceptable."""
        if mttr_minutes is not None:
            assert mttr_minutes <= max_mttr, f"MTTR {mttr_minutes:.1f}min exceeds limit {max_mttr}min"

    @staticmethod
    def assert_circuit_breaker_open(circuit_state: dict[str, Any]):
        """Assert circuit breaker is open."""
        assert circuit_state.get("state") == "open", (
            f"Expected circuit breaker to be open, got {circuit_state.get('state')}"
        )

    @staticmethod
    def assert_circuit_breaker_closed(circuit_state: dict[str, Any]):
        """Assert circuit breaker is closed."""
        assert circuit_state.get("state") == "closed", (
            f"Expected circuit breaker to be closed, got {circuit_state.get('state')}"
        )


class PerformanceAssertions:
    """Assertions for performance testing."""

    @staticmethod
    def assert_operation_time(duration_ms: float, max_duration_ms: float, operation_name: str = "operation"):
        """Assert operation completed within time limit."""
        assert duration_ms <= max_duration_ms, (
            f"{operation_name} took {duration_ms:.1f}ms, expected <={max_duration_ms}ms"
        )

    @staticmethod
    def assert_throughput(operations_per_second: float, min_throughput: float, operation_name: str = "operation"):
        """Assert minimum throughput was achieved."""
        assert operations_per_second >= min_throughput, (
            f"{operation_name} throughput {operations_per_second:.1f} ops/s below minimum {min_throughput}"
        )

    @staticmethod
    def assert_memory_usage(memory_mb: float, max_memory_mb: float):
        """Assert memory usage is within limits."""
        assert memory_mb <= max_memory_mb, f"Memory usage {memory_mb:.1f}MB exceeds limit {max_memory_mb}MB"

    @staticmethod
    def assert_cpu_usage(cpu_percent: float, max_cpu_percent: float):
        """Assert CPU usage is within limits."""
        assert cpu_percent <= max_cpu_percent, f"CPU usage {cpu_percent:.1f}% exceeds limit {max_cpu_percent}%"

    @staticmethod
    def assert_no_memory_leaks(before_memory_mb: float, after_memory_mb: float, tolerance_mb: float = 10.0):
        """Assert no significant memory leaks occurred."""
        memory_increase = after_memory_mb - before_memory_mb
        assert memory_increase <= tolerance_mb, (
            f"Memory increased by {memory_increase:.1f}MB, tolerance {tolerance_mb}MB"
        )

    @staticmethod
    def assert_scalability(
        single_user_time: float,
        multi_user_time: float,
        user_count: int,
        max_degradation_factor: float = 2.0
    ):
        """Assert performance scales reasonably with load."""
        degradation_factor = multi_user_time / single_user_time
        expected_max = max_degradation_factor * user_count
        assert degradation_factor <= expected_max, (
            f"Performance degraded by {degradation_factor:.1f}x with {user_count} users, expected <={expected_max:.1f}x"
        )


class IntegrationAssertions:
    """Assertions for integration testing."""

    @staticmethod
    def assert_end_to_end_workflow(
        start_result: dict[str, Any],
        final_state: dict[str, Any],
        expected_outputs: dict[str, Any],
        max_duration_ms: float = 30000
    ):
        """Assert end-to-end workflow execution."""
        # Check workflow started
        WorkflowAssertions.assert_workflow_started(start_result)

        # Check outputs are present
        for key, expected_value in expected_outputs.items():
            StateAssertions.assert_state_contains(final_state, key, expected_value)

        # Check timing
        duration = start_result.get("total_duration_ms", 0)
        PerformanceAssertions.assert_operation_time(duration, max_duration_ms, "end-to-end workflow")

    @staticmethod
    def assert_error_recovery_workflow(
        error_history: list[WorkflowError],
        final_state: dict[str, Any],
        expected_recoveries: int
    ):
        """Assert error recovery workflow completed successfully."""
        # Check errors were tracked
        assert len(error_history) > 0, "Expected some errors to be tracked"

        # Check recoveries
        recovered_errors = [e for e in error_history if e.recovered]
        assert len(recovered_errors) >= expected_recoveries, (
            f"Expected {expected_recoveries} recoveries, got {len(recovered_errors)}"
        )

        # Check final state is valid
        assert final_state is not None, "Final state should not be None after recovery"

    @staticmethod
    def assert_parallel_execution_results(
        results: list[dict[str, Any]],
        expected_count: int,
        max_duration_ms: float = 60000
    ):
        """Assert parallel execution completed successfully."""
        assert len(results) == expected_count, f"Expected {expected_count} parallel results, got {len(results)}"

        # Check all succeeded
        failed_results = [r for r in results if not r.get("success", False)]
        assert len(failed_results) == 0, f"Expected all parallel executions to succeed, {len(failed_results)} failed"

        # Check timing
        max_duration = max(r.get("duration_ms", 0) for r in results)
        PerformanceAssertions.assert_operation_time(max_duration, max_duration_ms, "parallel execution")
