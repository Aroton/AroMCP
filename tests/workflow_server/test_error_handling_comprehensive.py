"""
Comprehensive test suite for Error Handling Infrastructure - Phase 2

These tests are designed to fail initially and guide infrastructure development.
They test advanced error handling features that don't exist yet.

Covers acceptance criteria:
- AC-EHV-009, AC-EHV-011, AC-EHV-012: Workflow-level timeout coordination
- AC-EHV-019, AC-EHV-020, AC-EHV-021: Parallel execution error handling
- AC-EHV-022, AC-EHV-023, AC-EHV-026: Error reporting integration
"""

import json
import threading
import time

import pytest

# These imports will fail initially - that's expected
try:
    from aromcp.workflow_server.error_handling.cascading_timeout_manager import CascadingTimeoutManager
    from aromcp.workflow_server.error_handling.error_aggregator import ErrorAggregator
    from aromcp.workflow_server.error_handling.error_reporter import ErrorReporter
    from aromcp.workflow_server.error_handling.parallel_error_handler import ParallelErrorHandler
    from aromcp.workflow_server.error_handling.partial_failure_handler import PartialFailureHandler
    from aromcp.workflow_server.error_handling.structured_error_formatter import StructuredErrorFormatter
    from aromcp.workflow_server.error_handling.timeout_coordinator import TimeoutCoordinator
    from aromcp.workflow_server.error_handling.timeout_propagation import TimeoutPropagationManager
except ImportError:
    # Expected to fail - infrastructure doesn't exist yet
    TimeoutCoordinator = None
    CascadingTimeoutManager = None
    ParallelErrorHandler = None
    ErrorAggregator = None
    ErrorReporter = None
    StructuredErrorFormatter = None
    TimeoutPropagationManager = None
    PartialFailureHandler = None

from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep


class TestWorkflowTimeoutCoordination:
    """Test workflow-level timeout coordination (AC-EHV-009, AC-EHV-011, AC-EHV-012)."""

    @pytest.mark.xfail(reason="TimeoutCoordinator not implemented yet")
    def test_workflow_timeout_enforcement(self):
        """Test enforcement of workflow-level timeouts across all operations (AC-EHV-009)."""
        if not TimeoutCoordinator:
            pytest.skip("TimeoutCoordinator infrastructure not implemented")

        # Infrastructure needed: TimeoutCoordinator for workflow-wide timeout management
        coordinator = TimeoutCoordinator()

        # Set workflow timeout
        workflow_id = "timeout_test_1"
        workflow_timeout = 10.0  # 10 seconds

        coordinator.set_workflow_timeout(workflow_id, workflow_timeout)

        # Track step executions
        steps = ["step1", "step2", "step3", "step4"]

        # Execute steps with tracking
        start_time = time.time()

        # Step 1: 2 seconds
        with coordinator.track_step(workflow_id, "step1"):
            time.sleep(2)

        # Step 2: 3 seconds
        with coordinator.track_step(workflow_id, "step2"):
            time.sleep(3)

        # Step 3: 4 seconds
        with coordinator.track_step(workflow_id, "step3"):
            time.sleep(4)

        # Step 4: Should timeout (total > 10 seconds)
        with pytest.raises(TimeoutCoordinator.WorkflowTimeoutError) as exc_info:
            with coordinator.track_step(workflow_id, "step4"):
                time.sleep(3)

        # Verify timeout details
        assert exc_info.value.workflow_id == workflow_id
        assert exc_info.value.timeout_at_step == "step4"
        assert exc_info.value.elapsed_time > 9
        assert exc_info.value.remaining_time < 1

        # Get execution report
        report = coordinator.get_timeout_report(workflow_id)
        assert report["total_elapsed"] > 9
        assert report["timeout_reached"] == True
        assert len(report["step_durations"]) == 3  # Only completed steps

    @pytest.mark.xfail(reason="CascadingTimeoutManager not implemented yet")
    def test_cascading_timeout_cancellation(self):
        """Test cascading timeout cancellation in nested operations (AC-EHV-011)."""
        if not CascadingTimeoutManager:
            pytest.skip("CascadingTimeoutManager infrastructure not implemented")

        # Infrastructure needed: Manager for cascading timeout cancellations
        manager = CascadingTimeoutManager()

        workflow_id = "cascade_test_1"

        # Set up timeout hierarchy
        manager.set_timeout(workflow_id, level="workflow", timeout=5.0)
        manager.set_timeout(workflow_id, level="step", step_id="step1", timeout=3.0)
        manager.set_timeout(workflow_id, level="operation", operation_id="op1", timeout=1.0)

        # Track cancellations
        cancelled_operations = []

        def operation_with_cleanup(op_id: str):
            try:
                # Register cleanup handler
                manager.register_cleanup(workflow_id, op_id, lambda: cancelled_operations.append(op_id))

                # Simulate long operation
                time.sleep(10)
            except manager.TimeoutCancellationError:
                # Properly handle cancellation
                pass

        # Start nested operations
        threads = []
        for i in range(5):
            thread = threading.Thread(target=operation_with_cleanup, args=(f"op_{i}",))
            thread.start()
            threads.append(thread)

        # Trigger workflow timeout
        time.sleep(1)
        manager.trigger_workflow_timeout(workflow_id)

        # Wait for cascading cancellation
        for thread in threads:
            thread.join(timeout=2)

        # Verify all operations were cancelled
        assert len(cancelled_operations) == 5

        # Verify cancellation order (deepest first)
        cancellation_report = manager.get_cancellation_report(workflow_id)
        assert cancellation_report["trigger"] == "workflow_timeout"
        assert cancellation_report["cascaded_cancellations"] >= 5
        assert cancellation_report["cleanup_handlers_executed"] == 5

    @pytest.mark.xfail(reason="TimeoutPropagationManager not implemented yet")
    def test_timeout_propagation_subagents(self):
        """Test timeout constraint propagation to sub-agents (AC-EHV-012)."""
        if not TimeoutPropagationManager:
            pytest.skip("TimeoutPropagationManager infrastructure not implemented")

        # Infrastructure needed: Timeout propagation across sub-agent boundaries
        propagator = TimeoutPropagationManager()

        # Parent workflow with timeout
        parent_workflow_id = "parent_1"
        parent_timeout = 60.0  # 60 seconds total

        propagator.set_workflow_timeout(parent_workflow_id, parent_timeout)

        # Execute some steps in parent (consuming time)
        propagator.record_elapsed_time(parent_workflow_id, 20.0)

        # Create sub-agents with propagated timeouts
        subagent_configs = []

        for i in range(3):
            subagent_id = f"subagent_{i}"

            # Calculate remaining timeout for sub-agent
            config = propagator.create_subagent_timeout_config(
                parent_workflow_id=parent_workflow_id,
                subagent_id=subagent_id,
                parallel_execution=True,
                estimated_duration=15.0,
            )

            subagent_configs.append(config)

        # Verify timeout propagation
        assert all(c["timeout"] <= 40.0 for c in subagent_configs)  # Parent has 40s remaining

        # For parallel execution, all get the same timeout
        assert all(c["timeout"] == subagent_configs[0]["timeout"] for c in subagent_configs)

        # Test serial sub-agent timeout calculation
        serial_configs = []
        for i in range(3):
            config = propagator.create_subagent_timeout_config(
                parent_workflow_id=parent_workflow_id,
                subagent_id=f"serial_sub_{i}",
                parallel_execution=False,
                estimated_duration=10.0,
                position_in_sequence=i,
            )
            serial_configs.append(config)

        # Serial timeouts should decrease for later sub-agents
        assert serial_configs[0]["timeout"] > serial_configs[2]["timeout"]

        # Verify timeout inheritance chain
        inheritance = propagator.get_timeout_inheritance_chain("serial_sub_2")
        assert inheritance["parent_timeout"] == 60.0
        assert inheritance["parent_elapsed"] == 20.0
        assert inheritance["propagated_timeout"] < 40.0


class TestParallelExecutionErrorHandling:
    """Test error handling in parallel execution (AC-EHV-019, AC-EHV-020, AC-EHV-021)."""

    @pytest.mark.xfail(reason="ParallelErrorHandler not implemented yet")
    def test_parallel_step_error_isolation(self):
        """Test error isolation in parallel step execution (AC-EHV-019)."""
        if not ParallelErrorHandler:
            pytest.skip("ParallelErrorHandler infrastructure not implemented")

        # Infrastructure needed: Handler for parallel execution errors
        handler = ParallelErrorHandler()

        # Define parallel tasks with mixed success/failure
        tasks = [
            {"id": "task1", "will_fail": False, "duration": 1.0},
            {"id": "task2", "will_fail": True, "error": "Connection timeout"},
            {"id": "task3", "will_fail": False, "duration": 1.5},
            {"id": "task4", "will_fail": True, "error": "Invalid input"},
            {"id": "task5", "will_fail": False, "duration": 0.5},
        ]

        # Execute tasks in parallel
        results = handler.execute_parallel_tasks(
            tasks=tasks, fail_fast=False, max_workers=5  # Continue despite failures
        )

        # Verify error isolation
        assert results["completed_tasks"] == 3
        assert results["failed_tasks"] == 2
        assert results["success_rate"] == 0.6

        # Check successful tasks completed despite failures
        successful = results["task_results"]["successful"]
        assert len(successful) == 3
        assert all(t["status"] == "completed" for t in successful)

        # Check failed tasks have error details
        failed = results["task_results"]["failed"]
        assert len(failed) == 2
        assert all(t["error"] is not None for t in failed)

        # Verify no cross-contamination
        assert results["error_contamination_detected"] == False

    @pytest.mark.xfail(reason="ErrorAggregator not implemented yet")
    def test_parallel_error_aggregation(self):
        """Test aggregation of errors from parallel operations (AC-EHV-020)."""
        if not ErrorAggregator:
            pytest.skip("ErrorAggregator infrastructure not implemented")

        # Infrastructure needed: Aggregator for parallel execution errors
        aggregator = ErrorAggregator()

        # Simulate parallel operations with various errors
        operation_errors = [
            {
                "operation_id": "op1",
                "error_type": "TimeoutError",
                "message": "Operation timed out after 30s",
                "severity": "high",
                "timestamp": time.time(),
            },
            {
                "operation_id": "op2",
                "error_type": "ValidationError",
                "message": "Invalid data format",
                "severity": "medium",
                "timestamp": time.time() + 1,
            },
            {
                "operation_id": "op3",
                "error_type": "TimeoutError",
                "message": "Operation timed out after 30s",
                "severity": "high",
                "timestamp": time.time() + 2,
            },
            {
                "operation_id": "op4",
                "error_type": "ResourceError",
                "message": "Insufficient memory",
                "severity": "critical",
                "timestamp": time.time() + 3,
            },
        ]

        # Add errors to aggregator
        for error in operation_errors:
            aggregator.add_error(**error)

        # Get aggregated analysis
        analysis = aggregator.analyze_errors()

        # Verify error grouping
        assert analysis["total_errors"] == 4
        assert analysis["unique_error_types"] == 3
        assert analysis["error_distribution"]["TimeoutError"] == 2
        assert analysis["error_distribution"]["ValidationError"] == 1
        assert analysis["error_distribution"]["ResourceError"] == 1

        # Verify severity analysis
        assert analysis["severity_breakdown"]["critical"] == 1
        assert analysis["severity_breakdown"]["high"] == 2
        assert analysis["severity_breakdown"]["medium"] == 1

        # Get aggregated error report
        report = aggregator.generate_error_report()

        assert report["summary"]["most_common_error"] == "TimeoutError"
        assert report["summary"]["highest_severity"] == "critical"
        assert len(report["grouped_errors"]["TimeoutError"]) == 2

        # Verify pattern detection
        patterns = report.get("detected_patterns", [])
        assert any(p["pattern"] == "repeated_timeout" for p in patterns)

    @pytest.mark.xfail(reason="PartialFailureHandler not implemented yet")
    def test_partial_failure_recovery_strategies(self):
        """Test recovery strategies for partial failures in parallel execution (AC-EHV-021)."""
        if not PartialFailureHandler:
            pytest.skip("PartialFailureHandler infrastructure not implemented")

        # Infrastructure needed: Handler for partial failure scenarios
        handler = PartialFailureHandler()

        # Configure recovery strategies
        handler.set_recovery_strategy("retry_failed", max_retries=3)
        handler.set_recovery_strategy("compensate_failed", compensation_timeout=30)
        handler.set_recovery_strategy("continue_successful", merge_partial_results=True)

        # Simulate partial failure scenario
        parallel_results = {
            "successful": [
                {"task_id": "task1", "result": {"data": "processed1"}},
                {"task_id": "task3", "result": {"data": "processed3"}},
                {"task_id": "task5", "result": {"data": "processed5"}},
            ],
            "failed": [
                {"task_id": "task2", "error": "Network error", "retryable": True},
                {"task_id": "task4", "error": "Data corruption", "retryable": False},
            ],
        }

        # Apply recovery strategy
        recovery_result = handler.handle_partial_failure(
            parallel_results=parallel_results,
            strategy="mixed",  # Try multiple strategies
            workflow_context={"critical": False},
        )

        # Verify retry attempts for retryable failures
        assert recovery_result["retried_tasks"] == ["task2"]
        assert recovery_result["retry_outcomes"]["task2"]["attempts"] <= 3

        # Verify compensation for non-retryable failures
        assert recovery_result["compensated_tasks"] == ["task4"]
        assert recovery_result["compensation_actions"]["task4"] is not None

        # Verify partial results handling
        assert recovery_result["final_result"]["status"] == "partial_success"
        assert len(recovery_result["final_result"]["merged_data"]) == 3  # Only successful
        assert recovery_result["final_result"]["success_rate"] == 0.6

        # Test different strategy - fail fast
        fail_fast_result = handler.handle_partial_failure(
            parallel_results=parallel_results, strategy="fail_fast", workflow_context={"critical": True}
        )

        assert fail_fast_result["final_result"]["status"] == "failed"
        assert fail_fast_result["rollback_performed"] == True


class TestErrorReportingIntegration:
    """Test error reporting and integration features (AC-EHV-022, AC-EHV-023, AC-EHV-026)."""

    @pytest.mark.xfail(reason="ErrorReporter not implemented yet")
    def test_structured_error_reporting(self):
        """Test structured error reporting with full context (AC-EHV-022)."""
        if not ErrorReporter:
            pytest.skip("ErrorReporter infrastructure not implemented")

        # Infrastructure needed: Comprehensive error reporting system
        reporter = ErrorReporter()

        # Create a complex error scenario
        workflow_id = "error_workflow_1"

        # Report workflow error with full context
        error_context = {
            "workflow_id": workflow_id,
            "workflow_name": "data_processing_pipeline",
            "step_id": "transform_step",
            "step_type": "parallel_foreach",
            "error_type": "PartialFailure",
            "error_message": "3 of 10 parallel tasks failed",
            "timestamp": time.time(),
            "workflow_state": {"processed_items": 7, "failed_items": 3, "pending_items": 0},
            "execution_context": {"environment": "production", "version": "1.2.0", "runtime": "python3.9"},
            "stack_trace": "Traceback...",
            "related_errors": [
                {"task": "item_3", "error": "Validation failed"},
                {"task": "item_7", "error": "Timeout"},
                {"task": "item_9", "error": "Resource limit"},
            ],
        }

        report_id = reporter.report_error(**error_context)

        # Retrieve structured report
        report = reporter.get_error_report(report_id)

        # Verify report structure
        assert report["id"] == report_id
        assert report["workflow_id"] == workflow_id
        assert report["severity"] == "high"  # Partial failure in production
        assert report["categorization"]["category"] == "partial_failure"
        assert report["categorization"]["subcategory"] == "parallel_execution"

        # Verify context preservation
        assert report["workflow_state"]["processed_items"] == 7
        assert len(report["related_errors"]) == 3

        # Verify error analysis
        analysis = report["analysis"]
        assert analysis["failure_rate"] == 0.3
        assert analysis["error_diversity"] == 3  # 3 different error types
        assert "recovery_suggestions" in analysis

        # Test error search functionality
        search_results = reporter.search_errors(
            filters={"error_type": "PartialFailure", "environment": "production", "time_range": "last_hour"}
        )

        assert len(search_results) > 0
        assert all(r["error_type"] == "PartialFailure" for r in search_results)

    @pytest.mark.xfail(reason="StructuredErrorFormatter not implemented yet")
    def test_monitoring_system_error_integration(self):
        """Test integration with monitoring systems for error tracking (AC-EHV-023)."""
        if not StructuredErrorFormatter:
            pytest.skip("StructuredErrorFormatter infrastructure not implemented")

        # Infrastructure needed: Error formatter for monitoring integrations
        formatter = StructuredErrorFormatter()

        # Configure formatters for different systems
        formatter.configure_format("prometheus", {"include_labels": True, "metric_prefix": "workflow_errors"})

        formatter.configure_format(
            "elasticsearch", {"index_pattern": "workflow-errors-*", "include_full_context": True}
        )

        formatter.configure_format(
            "cloudwatch",
            {"namespace": "WorkflowEngine", "dimension_keys": ["workflow_name", "step_type", "error_type"]},
        )

        # Create error event
        error_event = {
            "workflow_name": "etl_pipeline",
            "step_type": "transform",
            "error_type": "DataValidationError",
            "severity": "warning",
            "count": 5,
            "timestamp": time.time(),
            "details": {
                "invalid_records": 5,
                "total_records": 1000,
                "validation_rules_failed": ["date_format", "required_fields"],
            },
        }

        # Format for different systems
        prometheus_format = formatter.format_error("prometheus", error_event)
        assert "workflow_errors_total" in prometheus_format
        assert 'workflow_name="etl_pipeline"' in prometheus_format
        assert prometheus_format.endswith(" 5")

        elasticsearch_format = formatter.format_error("elasticsearch", error_event)
        es_doc = json.loads(elasticsearch_format)
        assert es_doc["workflow_name"] == "etl_pipeline"
        assert es_doc["details"]["invalid_records"] == 5
        assert "@timestamp" in es_doc

        cloudwatch_format = formatter.format_error("cloudwatch", error_event)
        assert cloudwatch_format["MetricName"] == "ErrorCount"
        assert cloudwatch_format["Value"] == 5
        assert len(cloudwatch_format["Dimensions"]) == 3

        # Test batch formatting
        error_batch = [error_event] * 10

        batch_formats = formatter.format_error_batch("prometheus", error_batch)
        assert len(batch_formats.split("\n")) == 10

    @pytest.mark.xfail(reason="Debug error enrichment not implemented yet")
    def test_debug_mode_error_enrichment(self):
        """Test error message enrichment in debug mode (AC-EHV-026)."""
        if not ErrorReporter:
            pytest.skip("Debug error enrichment not implemented")

        # Infrastructure needed: Debug mode error enrichment
        from aromcp.workflow_server.error_handling.debug_enrichment import DebugErrorEnricher

        enricher = DebugErrorEnricher()

        # Enable debug mode
        enricher.set_debug_mode(True)

        # Create base error
        base_error = {
            "type": "StepExecutionError",
            "message": "Failed to execute transformation step",
            "step_id": "transform_1",
            "workflow_id": "debug_workflow",
        }

        # Enrich error with debug information
        enriched = enricher.enrich_error(base_error)

        # Verify debug enrichments
        assert "debug_info" in enriched
        debug_info = enriched["debug_info"]

        # Execution context
        assert "execution_trace" in debug_info
        assert len(debug_info["execution_trace"]) > 0
        assert debug_info["execution_trace"][-1]["step_id"] == "transform_1"

        # Variable state at error
        assert "variable_snapshot" in debug_info
        assert "workflow_variables" in debug_info["variable_snapshot"]
        assert "step_variables" in debug_info["variable_snapshot"]

        # System state
        assert "system_state" in debug_info
        assert "memory_usage_mb" in debug_info["system_state"]
        assert "active_threads" in debug_info["system_state"]

        # Suggestions for debugging
        assert "debug_suggestions" in debug_info
        assert len(debug_info["debug_suggestions"]) > 0

        # Test production mode (no enrichment)
        enricher.set_debug_mode(False)
        prod_enriched = enricher.enrich_error(base_error)

        assert "debug_info" not in prod_enriched
        assert prod_enriched["message"] == base_error["message"]

        # Test conditional enrichment based on error type
        enricher.set_debug_mode(True)
        enricher.set_enrichment_rules(
            {
                "StepExecutionError": ["execution_trace", "variable_snapshot"],
                "TimeoutError": ["execution_trace", "performance_metrics"],
                "ValidationError": ["variable_snapshot", "validation_rules"],
            }
        )

        timeout_error = {"type": "TimeoutError", "message": "Step exceeded timeout of 30s", "step_id": "slow_step"}

        timeout_enriched = enricher.enrich_error(timeout_error)
        assert "performance_metrics" in timeout_enriched["debug_info"]
        assert "variable_snapshot" not in timeout_enriched["debug_info"]


class TestErrorHandlingIntegration:
    """Test integration of error handling components."""

    @pytest.mark.xfail(reason="Integrated error handling not implemented yet")
    def test_end_to_end_error_handling_workflow(self):
        """Test complete error handling workflow from detection to reporting."""
        if not all([TimeoutCoordinator, ParallelErrorHandler, ErrorReporter]):
            pytest.skip("Complete error handling infrastructure not implemented")

        # Create integrated error handling system
        timeout_coordinator = TimeoutCoordinator()
        parallel_handler = ParallelErrorHandler()
        error_reporter = ErrorReporter()

        # Configure integration
        parallel_handler.set_error_reporter(error_reporter)
        timeout_coordinator.set_error_reporter(error_reporter)

        # Simulate complex workflow with errors
        workflow_id = "integrated_test_workflow"

        # Set workflow timeout
        timeout_coordinator.set_workflow_timeout(workflow_id, 10.0)

        # Execute parallel tasks with mixed results
        tasks = [
            {"id": "task1", "duration": 2.0, "will_fail": False},
            {"id": "task2", "duration": 15.0, "will_fail": False},  # Will timeout
            {"id": "task3", "duration": 1.0, "will_fail": True, "error": "Data error"},
            {"id": "task4", "duration": 3.0, "will_fail": False},
        ]

        # Execute with timeout coordination
        try:
            with timeout_coordinator.track_workflow(workflow_id):
                results = parallel_handler.execute_parallel_tasks(
                    tasks=tasks, fail_fast=False, timeout=timeout_coordinator.get_remaining_time(workflow_id)
                )
        except TimeoutCoordinator.WorkflowTimeoutError:
            # Handle workflow timeout
            pass

        # Get comprehensive error report
        error_reports = error_reporter.get_workflow_errors(workflow_id)

        # Should have multiple error types
        error_types = [r["error_type"] for r in error_reports]
        assert "TimeoutError" in error_types
        assert "DataError" in error_types

        # Verify error correlation
        correlation = error_reporter.get_error_correlation(workflow_id)
        assert correlation["root_cause"] == "workflow_timeout"
        assert correlation["cascaded_failures"] > 0

        # Get actionable summary
        summary = error_reporter.get_error_summary(workflow_id)
        assert summary["total_errors"] >= 2
        assert summary["recovery_possible"] == False  # Due to workflow timeout
        assert len(summary["recommended_actions"]) > 0

    @pytest.mark.xfail(reason="Error handling metrics not implemented yet")
    def test_error_handling_performance_metrics(self):
        """Test performance metrics for error handling operations."""
        if not ErrorReporter:
            pytest.skip("Error handling metrics not implemented")

        from aromcp.workflow_server.error_handling.metrics import ErrorHandlingMetrics

        metrics = ErrorHandlingMetrics()

        # Track error handling operations
        with metrics.track_operation("error_detection"):
            time.sleep(0.01)  # Simulate detection time

        with metrics.track_operation("error_analysis"):
            time.sleep(0.05)  # Simulate analysis time

        with metrics.track_operation("error_reporting"):
            time.sleep(0.02)  # Simulate reporting time

        # Get performance metrics
        perf_metrics = metrics.get_performance_metrics()

        assert perf_metrics["error_detection"]["avg_duration_ms"] > 0
        assert perf_metrics["error_analysis"]["avg_duration_ms"] > 0
        assert perf_metrics["error_reporting"]["avg_duration_ms"] > 0

        assert perf_metrics["total_overhead_ms"] < 100  # Should be fast

        # Track error handling effectiveness
        metrics.record_error_handled(handled_successfully=True, recovery_time_ms=500)
        metrics.record_error_handled(handled_successfully=False, recovery_time_ms=0)
        metrics.record_error_handled(handled_successfully=True, recovery_time_ms=300)

        effectiveness = metrics.get_effectiveness_metrics()
        assert effectiveness["success_rate"] > 0.6
        assert effectiveness["avg_recovery_time_ms"] > 0
        assert effectiveness["total_errors_handled"] == 3


def create_test_workflow() -> WorkflowDefinition:
    """Helper to create test workflow definitions."""
    return WorkflowDefinition(
        name="test_error_workflow",
        description="Test workflow for error handling",
        version="1.0.0",
        steps=[WorkflowStep(id="step1", type="shell_command", definition={"command": "echo 'test'"})],
    )
