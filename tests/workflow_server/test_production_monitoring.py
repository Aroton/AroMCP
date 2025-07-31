"""
Comprehensive production monitoring testing for monitoring and debugging.

Covers missing acceptance criteria:
- AC-MD-015: Workflow execution metrics are tracked comprehensively
- AC-MD-016: Performance bottleneck identification works automatically
- AC-MD-017: Resource usage monitoring tracks memory and CPU usage
- AC-MD-018: Performance comparison between serial and parallel modes
- AC-MD-019: Workflow status and progress monitoring APIs are available
- AC-MD-020: Integration with external monitoring systems works
- AC-MD-021: Workflow execution audit trails are generated
- AC-MD-022: Alerting and notification for workflow failures works

Focus: Performance monitoring, bottleneck identification, production observability APIs
Pillar: Monitoring & Debugging
"""

import time
from unittest.mock import Mock, patch

import pytest

from aromcp.workflow_server.monitoring.observability import ObservabilityManager
from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
from aromcp.workflow_server.monitoring.test_adapters import (
    MetricsCollectorTestAdapter as MetricsCollector,
)
from aromcp.workflow_server.workflow.workflow_state import WorkflowState


class TestProductionMonitoring:
    """Test comprehensive production monitoring and observability features."""

    @pytest.fixture
    def execution_tracker(self):
        """Create execution tracker for testing."""
        return MetricsCollector()

    @pytest.fixture
    def performance_monitor(self):
        """Create performance monitor for testing."""
        return PerformanceMonitor()

    @pytest.fixture
    def observability_manager(self):
        """Create observability manager for testing."""
        return ObservabilityManager()

    @pytest.fixture
    def mock_workflow_state(self):
        """Mock workflow state for testing."""
        return WorkflowState(
            workflow_id="wf_monitor_test",
            status="running",
            current_step_index=2,
            total_steps=10,
            state={"inputs": {}, "state": {"processed_files": 5}, "computed": {}},
            execution_context={
                "start_time": time.time() - 30,  # Started 30 seconds ago
                "step_durations": [1.2, 0.8, 2.3],
                "resource_usage": {"memory_mb": 150, "cpu_percent": 25},
            },
        )

    def test_comprehensive_execution_metrics_tracking(self, execution_tracker, mock_workflow_state):
        """
        Test AC-MD-015: Workflow execution metrics are tracked comprehensively
        Focus: Duration, success rate, error rate, and performance patterns
        """
        # Track various execution events
        execution_events = [
            {"step_id": "step1", "step_type": "shell_command", "duration": 1.2, "status": "completed"},
            {"step_id": "step2", "step_type": "user_message", "duration": 0.3, "status": "completed"},
            {"step_id": "step3", "step_type": "mcp_call", "duration": 2.8, "status": "failed"},
            {"step_id": "step4", "step_type": "shell_command", "duration": 0.9, "status": "completed"},
            {"step_id": "step5", "step_type": "agent_prompt", "duration": 4.1, "status": "completed"},
            {"step_id": "step6", "step_type": "conditional", "duration": 0.1, "status": "completed"},
            {"step_id": "step7", "step_type": "mcp_call", "duration": 1.5, "status": "timeout"},
        ]

        # Record execution events
        for event in execution_events:
            execution_tracker.record_step_execution(
                step_id=event["step_id"],
                step_type=event["step_type"],
                duration=event["duration"],
                status=event["status"],
                timestamp=time.time(),
            )

        # Get comprehensive metrics
        metrics = execution_tracker.get_comprehensive_metrics()

        # Verify basic execution metrics
        assert metrics["total_steps"] == 7
        assert metrics["completed_steps"] == 5
        assert metrics["failed_steps"] == 1
        assert metrics["timeout_steps"] == 1
        assert metrics["success_rate"] == 5 / 7  # ~0.714

        # Verify duration metrics
        assert metrics["total_duration"] == sum(e["duration"] for e in execution_events)
        assert metrics["average_step_duration"] == metrics["total_duration"] / 7
        assert metrics["min_step_duration"] == 0.1
        assert metrics["max_step_duration"] == 4.1

        # Verify step type breakdown
        step_type_metrics = metrics["step_type_breakdown"]
        assert step_type_metrics["shell_command"]["count"] == 2
        assert step_type_metrics["shell_command"]["success_rate"] == 1.0
        assert step_type_metrics["mcp_call"]["count"] == 2
        assert step_type_metrics["mcp_call"]["success_rate"] == 0.0  # Both failed/timeout

        # Verify error pattern analysis
        assert metrics["error_patterns"]["timeout_rate"] == 1 / 7
        assert metrics["error_patterns"]["failure_rate"] == 1 / 7

    def test_performance_bottleneck_identification(self, performance_monitor):
        """
        Test AC-MD-016: Performance bottleneck identification works automatically
        Focus: Automatic identification of slow operations and resource bottlenecks
        """
        # Simulate workflow execution data with performance bottlenecks
        execution_data = [
            # Normal steps
            {"step_id": "step1", "type": "shell_command", "duration": 0.5, "cpu": 10, "memory": 50},
            {"step_id": "step2", "type": "user_message", "duration": 0.1, "cpu": 5, "memory": 48},
            {"step_id": "step3", "type": "user_message", "duration": 0.05, "cpu": 3, "memory": 49},
            # Performance bottlenecks
            {"step_id": "step4", "type": "mcp_call", "duration": 8.2, "cpu": 85, "memory": 200},  # Slow + high CPU
            {"step_id": "step5", "type": "shell_command", "duration": 0.3, "cpu": 15, "memory": 800},  # High memory
            {"step_id": "step6", "type": "agent_prompt", "duration": 12.5, "cpu": 45, "memory": 150},  # Very slow
            # More normal steps
            {"step_id": "step7", "type": "conditional", "duration": 0.02, "cpu": 2, "memory": 49},
            {"step_id": "step8", "type": "user_input", "duration": 2.1, "cpu": 8, "memory": 55},  # User wait time
        ]

        # Feed data to performance monitor
        for data in execution_data:
            performance_monitor.record_step_performance(
                step_id=data["step_id"],
                step_type=data["type"],
                duration=data["duration"],
                cpu_usage=data["cpu"],
                memory_usage=data["memory"],
            )

        # Analyze for bottlenecks
        bottlenecks = performance_monitor.identify_bottlenecks()

        # Verify bottleneck detection
        assert len(bottlenecks) >= 3  # Should identify at least 3 bottlenecks

        # Verify duration bottlenecks
        duration_bottlenecks = [b for b in bottlenecks if b.type == "duration"]
        assert len(duration_bottlenecks) >= 2

        duration_step_ids = [b.step_id for b in duration_bottlenecks]
        assert "step4" in duration_step_ids  # 8.2s duration
        assert "step6" in duration_step_ids  # 12.5s duration

        # Verify CPU bottlenecks
        cpu_bottlenecks = [b for b in bottlenecks if b.type == "cpu"]
        assert len(cpu_bottlenecks) >= 1
        assert any(b.step_id == "step4" for b in cpu_bottlenecks)  # 85% CPU

        # Verify memory bottlenecks
        memory_bottlenecks = [b for b in bottlenecks if b.type == "memory"]
        assert len(memory_bottlenecks) >= 1
        assert any(b.step_id == "step5" for b in memory_bottlenecks)  # 800MB memory

        # Verify bottleneck recommendations
        for bottleneck in bottlenecks:
            assert hasattr(bottleneck, "recommendation")
            assert len(bottleneck.recommendation) > 0
            assert bottleneck.severity in ["low", "medium", "high", "critical"]

    def test_resource_usage_monitoring(self, performance_monitor):
        """
        Test AC-MD-017: Resource usage monitoring tracks memory and CPU usage
        Focus: Memory usage, CPU utilization, and resource patterns
        """
        # Enable resource monitoring
        performance_monitor.enable_resource_monitoring(True)

        # Simulate resource usage over time
        resource_timeline = [
            {"timestamp": time.time() - 60, "memory_mb": 100, "cpu_percent": 15, "step": "initialization"},
            {"timestamp": time.time() - 50, "memory_mb": 120, "cpu_percent": 25, "step": "step1"},
            {"timestamp": time.time() - 40, "memory_mb": 140, "cpu_percent": 45, "step": "step2"},
            {"timestamp": time.time() - 30, "memory_mb": 300, "cpu_percent": 80, "step": "step3_heavy"},
            {"timestamp": time.time() - 20, "memory_mb": 320, "cpu_percent": 85, "step": "step3_heavy_cont"},
            {"timestamp": time.time() - 10, "memory_mb": 180, "cpu_percent": 30, "step": "step4_cleanup"},
            {"timestamp": time.time(), "memory_mb": 110, "cpu_percent": 12, "step": "step5_final"},
        ]

        # Record resource usage
        for point in resource_timeline:
            performance_monitor.record_resource_usage(
                timestamp=point["timestamp"],
                memory_mb=point["memory_mb"],
                cpu_percent=point["cpu_percent"],
                context={"current_step": point["step"]},
            )

        # Get resource usage analysis
        resource_analysis = performance_monitor.get_resource_analysis()

        # Verify memory tracking
        memory_stats = resource_analysis["memory"]
        assert memory_stats["peak_usage_mb"] == 320
        assert memory_stats["average_usage_mb"] == sum(p["memory_mb"] for p in resource_timeline) / len(
            resource_timeline
        )
        assert memory_stats["memory_growth_rate"] > 0  # Memory increased during heavy step

        # Verify CPU tracking
        cpu_stats = resource_analysis["cpu"]
        assert cpu_stats["peak_cpu_percent"] == 85
        assert cpu_stats["average_cpu_percent"] == sum(p["cpu_percent"] for p in resource_timeline) / len(
            resource_timeline
        )

        # Verify pattern identification
        patterns = resource_analysis["patterns"]
        assert "memory_spike" in patterns  # Should detect step3 memory spike
        assert "cpu_intensive_period" in patterns  # Should detect high CPU during step3

        # Verify resource optimization suggestions
        optimizations = resource_analysis["optimization_suggestions"]
        assert len(optimizations) > 0
        assert any("memory" in opt["type"] for opt in optimizations)
        assert any("cpu" in opt["type"] for opt in optimizations)

    def test_workflow_status_progress_monitoring_apis(self, observability_manager, mock_workflow_state):
        """
        Test AC-MD-019: Workflow status and progress monitoring APIs are available
        Focus: Real-time workflow status, progress, and health information
        """
        # Register workflow for monitoring
        observability_manager.register_workflow(mock_workflow_state)

        # Simulate workflow progress updates
        progress_updates = [
            {"step_index": 3, "status": "running", "step_name": "lint_check", "progress": 0.3},
            {"step_index": 4, "status": "completed", "step_name": "type_check", "progress": 0.4},
            {"step_index": 5, "status": "running", "step_name": "test_execution", "progress": 0.5},
            {"step_index": 6, "status": "failed", "step_name": "build_step", "progress": 0.6, "error": "Build failed"},
        ]

        for update in progress_updates:
            observability_manager.update_workflow_progress(
                workflow_id="wf_monitor_test",
                step_index=update["step_index"],
                status=update["status"],
                step_name=update["step_name"],
                progress=update["progress"],
                error=update.get("error"),
            )

        # Test status monitoring API
        status_api = observability_manager.get_status_api()

        # Get current workflow status
        current_status = status_api.get_workflow_status("wf_monitor_test")
        assert current_status["workflow_id"] == "wf_monitor_test"
        assert current_status["current_step_index"] == 6
        assert current_status["overall_progress"] == 0.6
        assert current_status["status"] == "failed"
        assert current_status["last_error"] == "Build failed"

        # Get progress details
        progress_details = status_api.get_progress_details("wf_monitor_test")
        assert len(progress_details["step_history"]) == 4
        assert progress_details["failed_steps"] == 1
        assert progress_details["completed_steps"] == 1

        # Test health monitoring API
        health_status = status_api.get_workflow_health("wf_monitor_test")
        assert health_status["overall_health"] in ["healthy", "degraded", "unhealthy"]
        assert "resource_usage" in health_status
        assert "error_rate" in health_status
        assert "performance_indicators" in health_status

        # Test real-time monitoring API
        realtime_data = status_api.get_realtime_metrics("wf_monitor_test")
        assert "current_step" in realtime_data
        assert "execution_time" in realtime_data
        assert "resource_usage" in realtime_data

    def test_external_monitoring_system_integration(self, observability_manager):
        """
        Test AC-MD-020: Integration with external monitoring systems works
        Focus: Metrics export in compatible formats (Prometheus, DataDog, etc.)
        """
        # Configure external monitoring integrations
        monitoring_configs = [
            {
                "system": "prometheus",
                "endpoint": "http://prometheus:9090/metrics",
                "format": "prometheus",
                "metrics": ["workflow_duration", "step_success_rate", "resource_usage"],
            },
            {
                "system": "datadog",
                "api_key": "mock_api_key",
                "format": "datadog",
                "metrics": ["workflow.duration", "workflow.step.success_rate", "workflow.resource.memory"],
            },
            {
                "system": "cloudwatch",
                "region": "us-east-1",
                "format": "cloudwatch",
                "metrics": ["WorkflowDuration", "StepSuccessRate", "ResourceUsage"],
            },
        ]

        # Mock external monitoring clients
        mock_clients = {}
        for config in monitoring_configs:
            mock_client = Mock()
            mock_client.send_metrics = Mock()
            mock_clients[config["system"]] = mock_client

        with patch.dict("src.aromcp.workflow_server.monitoring.observability.EXTERNAL_CLIENTS", mock_clients):
            # Configure integrations
            for config in monitoring_configs:
                observability_manager.configure_external_integration(config)

            # Generate sample metrics
            sample_metrics = {
                "workflow_duration": 45.2,
                "step_success_rate": 0.85,
                "resource_usage_memory_mb": 250,
                "resource_usage_cpu_percent": 35,
                "active_workflows": 3,
                "failed_workflows": 1,
            }

            # Export metrics to all configured systems
            observability_manager.export_metrics(sample_metrics)

            # Verify Prometheus format export
            prometheus_client = mock_clients["prometheus"]
            prometheus_client.send_metrics.assert_called_once()
            prometheus_args = prometheus_client.send_metrics.call_args[0][0]

            # Prometheus format should be key-value pairs
            assert "workflow_duration 45.2" in prometheus_args
            assert "step_success_rate 0.85" in prometheus_args

            # Verify DataDog format export
            datadog_client = mock_clients["datadog"]
            datadog_client.send_metrics.assert_called_once()
            datadog_args = datadog_client.send_metrics.call_args[0][0]

            # DataDog format should be structured JSON
            assert isinstance(datadog_args, list)
            assert any(metric["metric"] == "workflow.duration" for metric in datadog_args)

            # Verify CloudWatch format export
            cloudwatch_client = mock_clients["cloudwatch"]
            cloudwatch_client.send_metrics.assert_called_once()
            cloudwatch_args = cloudwatch_client.send_metrics.call_args[0][0]

            # CloudWatch format should have MetricData structure
            assert "MetricData" in cloudwatch_args
            metric_data = cloudwatch_args["MetricData"]
            assert any(metric["MetricName"] == "WorkflowDuration" for metric in metric_data)

    def test_workflow_execution_audit_trail_generation(self, observability_manager):
        """
        Test AC-MD-021: Workflow execution audit trails are generated
        Focus: Complete execution history with decisions, changes, and outcomes
        """
        # Enable audit trail generation
        observability_manager.enable_audit_trail(True)

        # Simulate workflow execution with audit events
        audit_events = [
            {
                "timestamp": time.time() - 100,
                "event_type": "workflow_started",
                "workflow_id": "wf_audit_test",
                "details": {"initiated_by": "user123", "config": {"timeout": 300}},
            },
            {
                "timestamp": time.time() - 90,
                "event_type": "step_started",
                "step_id": "step1",
                "step_type": "shell_command",
                "details": {"command": "npm run lint"},
            },
            {
                "timestamp": time.time() - 85,
                "event_type": "step_completed",
                "step_id": "step1",
                "details": {"duration": 5.2, "exit_code": 0, "output_lines": 15},
            },
            {
                "timestamp": time.time() - 80,
                "event_type": "state_updated",
                "details": {"path": "lint_results", "old_value": None, "new_value": {"errors": 0, "warnings": 2}},
            },
            {
                "timestamp": time.time() - 75,
                "event_type": "decision_point",
                "step_id": "step2",
                "details": {"condition": "lint_results.errors == 0", "result": True, "branch_taken": "continue"},
            },
            {
                "timestamp": time.time() - 70,
                "event_type": "user_interaction",
                "step_id": "step3",
                "details": {"prompt": "Continue with deployment?", "response": "yes", "response_time": 3.2},
            },
            {
                "timestamp": time.time() - 60,
                "event_type": "error_occurred",
                "step_id": "step4",
                "details": {"error_type": "TimeoutError", "message": "Deploy timed out", "recovery_action": "retry"},
            },
            {
                "timestamp": time.time() - 50,
                "event_type": "workflow_completed",
                "details": {"final_status": "completed", "total_duration": 50.3, "steps_completed": 5},
            },
        ]

        # Record audit events
        for event in audit_events:
            observability_manager.record_audit_event(
                event_type=event["event_type"],
                timestamp=event["timestamp"],
                workflow_id=event.get("workflow_id", "wf_audit_test"),
                step_id=event.get("step_id"),
                details=event["details"],
            )

        # Generate audit trail
        audit_trail = observability_manager.generate_audit_trail("wf_audit_test")

        # Verify audit trail completeness
        assert len(audit_trail["events"]) == len(audit_events)
        assert audit_trail["workflow_id"] == "wf_audit_test"
        assert audit_trail["total_duration"] == 50.3

        # Verify chronological ordering
        timestamps = [event["timestamp"] for event in audit_trail["events"]]
        assert timestamps == sorted(timestamps)

        # Verify event types are captured
        event_types = [event["event_type"] for event in audit_trail["events"]]
        expected_types = [
            "workflow_started",
            "step_started",
            "step_completed",
            "state_updated",
            "decision_point",
            "user_interaction",
            "error_occurred",
            "workflow_completed",
        ]
        assert all(et in event_types for et in expected_types)

        # Verify decision point tracking
        decision_events = [e for e in audit_trail["events"] if e["event_type"] == "decision_point"]
        assert len(decision_events) == 1
        decision_event = decision_events[0]
        assert decision_event["details"]["condition"] == "lint_results.errors == 0"
        assert decision_event["details"]["result"] == True

        # Verify state change tracking
        state_events = [e for e in audit_trail["events"] if e["event_type"] == "state_updated"]
        assert len(state_events) == 1
        state_event = state_events[0]
        assert state_event["details"]["path"] == "lint_results"
        assert state_event["details"]["old_value"] is None

        # Verify error tracking
        error_events = [e for e in audit_trail["events"] if e["event_type"] == "error_occurred"]
        assert len(error_events) == 1
        error_event = error_events[0]
        assert error_event["details"]["error_type"] == "TimeoutError"
        assert error_event["details"]["recovery_action"] == "retry"

    def test_alerting_notification_workflow_failures(self, observability_manager):
        """
        Test AC-MD-022: Alerting and notification for workflow failures works
        Focus: Appropriate alerts through configured channels
        """
        # Configure alerting channels
        alert_configs = [
            {
                "channel": "email",
                "recipients": ["admin@example.com", "team@example.com"],
                "severity_threshold": "medium",
                "rate_limit": "5_per_hour",
            },
            {
                "channel": "slack",
                "webhook_url": "https://hooks.slack.com/mock",
                "channel_name": "#alerts",
                "severity_threshold": "high",
            },
            {"channel": "pagerduty", "service_key": "mock_service_key", "severity_threshold": "critical"},
        ]

        # Mock notification clients
        mock_notifiers = {}
        for config in alert_configs:
            mock_notifier = Mock()
            mock_notifier.send_alert = Mock()
            mock_notifiers[config["channel"]] = mock_notifier

        with patch.dict("src.aromcp.workflow_server.monitoring.observability.ALERT_CLIENTS", mock_notifiers):
            # Configure alert channels
            for config in alert_configs:
                observability_manager.configure_alert_channel(config)

            # Test different severity levels of failures
            failure_scenarios = [
                {
                    "workflow_id": "wf_minor_fail",
                    "error_type": "ValidationError",
                    "severity": "low",
                    "message": "Input validation failed",
                    "should_alert_email": False,
                    "should_alert_slack": False,
                    "should_alert_pagerduty": False,
                },
                {
                    "workflow_id": "wf_medium_fail",
                    "error_type": "TimeoutError",
                    "severity": "medium",
                    "message": "Step execution timed out",
                    "should_alert_email": True,
                    "should_alert_slack": False,
                    "should_alert_pagerduty": False,
                },
                {
                    "workflow_id": "wf_high_fail",
                    "error_type": "SystemError",
                    "severity": "high",
                    "message": "Database connection failed",
                    "should_alert_email": True,
                    "should_alert_slack": True,
                    "should_alert_pagerduty": False,
                },
                {
                    "workflow_id": "wf_critical_fail",
                    "error_type": "SecurityError",
                    "severity": "critical",
                    "message": "Security breach detected",
                    "should_alert_email": True,
                    "should_alert_slack": True,
                    "should_alert_pagerduty": True,
                },
            ]

            # Trigger alerts for each scenario
            for scenario in failure_scenarios:
                observability_manager.trigger_failure_alert(
                    workflow_id=scenario["workflow_id"],
                    error_type=scenario["error_type"],
                    severity=scenario["severity"],
                    message=scenario["message"],
                    context={"timestamp": time.time()},
                )

            # Verify email alerts
            email_notifier = mock_notifiers["email"]
            email_calls = email_notifier.send_alert.call_count
            expected_email_calls = sum(1 for s in failure_scenarios if s["should_alert_email"])
            assert email_calls == expected_email_calls

            # Verify Slack alerts
            slack_notifier = mock_notifiers["slack"]
            slack_calls = slack_notifier.send_alert.call_count
            expected_slack_calls = sum(1 for s in failure_scenarios if s["should_alert_slack"])
            assert slack_calls == expected_slack_calls

            # Verify PagerDuty alerts
            pagerduty_notifier = mock_notifiers["pagerduty"]
            pagerduty_calls = pagerduty_notifier.send_alert.call_count
            expected_pagerduty_calls = sum(1 for s in failure_scenarios if s["should_alert_pagerduty"])
            assert pagerduty_calls == expected_pagerduty_calls

            # Verify alert content for critical failure
            if pagerduty_calls > 0:
                critical_alert_call = pagerduty_notifier.send_alert.call_args_list[-1]
                alert_content = critical_alert_call[0][0]
                assert "SecurityError" in alert_content["error_type"]
                assert "critical" in alert_content["severity"]
                assert "Security breach detected" in alert_content["message"]

    def test_performance_comparison_serial_vs_parallel(self, performance_monitor):
        """
        Test AC-MD-018: Performance comparison between serial and parallel modes
        Focus: Execution time, resource usage, and performance metrics comparison
        """
        # Simulate parallel mode execution
        parallel_execution_data = {
            "mode": "parallel",
            "total_duration": 15.3,
            "step_durations": [2.1, 3.2, 1.8, 4.1, 2.9, 1.2],  # Steps can overlap
            "peak_memory_mb": 450,
            "average_cpu_percent": 65,
            "concurrent_steps": 3,
            "parallelizable_steps": 4,
            "serial_steps": 2,
        }

        # Simulate serial mode execution (same workflow)
        serial_execution_data = {
            "mode": "serial",
            "total_duration": 24.7,  # Sum of all step durations
            "step_durations": [2.3, 3.4, 2.0, 4.3, 3.1, 1.3],  # Sequential execution times
            "peak_memory_mb": 180,  # Lower peak due to no concurrency
            "average_cpu_percent": 35,  # Lower CPU due to single-threaded
            "concurrent_steps": 1,
            "parallelizable_steps": 0,  # All executed serially
            "serial_steps": 6,
        }

        # Record both execution modes
        performance_monitor.record_execution_mode("parallel", parallel_execution_data)
        performance_monitor.record_execution_mode("serial", serial_execution_data)

        # Generate performance comparison
        comparison = performance_monitor.compare_execution_modes("parallel", "serial")

        # Verify timing comparison
        timing_comparison = comparison["timing"]
        assert timing_comparison["parallel_duration"] == 15.3
        assert timing_comparison["serial_duration"] == 24.7
        assert timing_comparison["speedup_factor"] == 24.7 / 15.3  # ~1.61x speedup
        assert timing_comparison["time_saved_seconds"] == 24.7 - 15.3  # 9.4 seconds saved

        # Verify resource usage comparison
        resource_comparison = comparison["resources"]
        assert resource_comparison["parallel_peak_memory"] == 450
        assert resource_comparison["serial_peak_memory"] == 180
        assert resource_comparison["memory_overhead_factor"] == 450 / 180  # ~2.5x more memory
        assert resource_comparison["parallel_avg_cpu"] == 65
        assert resource_comparison["serial_avg_cpu"] == 35

        # Verify efficiency analysis
        efficiency = comparison["efficiency"]
        assert efficiency["parallel_efficiency"] < 1.0  # Due to overhead
        assert efficiency["resource_efficiency_score"] > 0  # Overall efficiency score
        assert "cpu_utilization_improvement" in efficiency
        assert "memory_cost_analysis" in efficiency

        # Verify recommendations
        recommendations = comparison["recommendations"]
        assert len(recommendations) > 0
        assert any("parallel" in rec["mode"] for rec in recommendations)

        # Should recommend parallel for this scenario (significant speedup despite memory cost)
        primary_recommendation = recommendations[0]
        assert primary_recommendation["recommended_mode"] == "parallel"
        assert "speedup" in primary_recommendation["reasoning"]


class TestProductionMonitoringIntegration:
    """Test production monitoring integration with realistic workflow scenarios."""

    def test_code_standards_workflow_comprehensive_monitoring(self):
        """
        Test comprehensive monitoring of code-standards:enforce.yaml workflow
        Focus: Real production workflow monitoring with all observability features
        """
        # Initialize monitoring components
        execution_tracker = MetricsCollector("wf_code_standards")
        performance_monitor = PerformanceMonitor()
        observability_manager = ObservabilityManager()

        # Simulate code standards workflow execution
        workflow_steps = [
            {"step": "lint_check", "type": "shell_command", "duration": 3.2, "memory": 120, "cpu": 25},
            {"step": "type_check", "type": "shell_command", "duration": 5.8, "memory": 180, "cpu": 45},
            {"step": "test_execution", "type": "shell_command", "duration": 12.3, "memory": 250, "cpu": 60},
            {"step": "security_scan", "type": "mcp_call", "duration": 8.1, "memory": 200, "cpu": 35},
            {"step": "build_check", "type": "shell_command", "duration": 15.4, "memory": 300, "cpu": 70},
            {"step": "results_summary", "type": "user_message", "duration": 0.2, "memory": 110, "cpu": 5},
            {"step": "cleanup", "type": "user_message", "duration": 0.1, "memory": 105, "cpu": 3},
        ]

        start_time = time.time()

        # Record execution with full monitoring
        for i, step_data in enumerate(workflow_steps):
            step_start = time.time()

            # Record step start
            execution_tracker.record_step_start(
                step_id=step_data["step"], step_type=step_data["type"], timestamp=step_start
            )

            # Simulate step execution time
            time.sleep(0.01)  # Minimal delay for testing

            # Record resource usage during step
            performance_monitor.record_resource_usage(
                timestamp=step_start + step_data["duration"] / 2,
                memory_mb=step_data["memory"],
                cpu_percent=step_data["cpu"],
                context={"step": step_data["step"]},
            )

            # Record step completion
            execution_tracker.record_step_completion(
                step_id=step_data["step"],
                duration=step_data["duration"],
                status="completed",
                timestamp=step_start + step_data["duration"],
            )

            # Record audit event
            observability_manager.record_audit_event(
                event_type="step_completed",
                workflow_id="wf_code_standards",
                step_id=step_data["step"],
                details={
                    "duration": step_data["duration"],
                    "resource_usage": {"memory": step_data["memory"], "cpu": step_data["cpu"]},
                    "status": "completed",
                },
            )

        total_duration = time.time() - start_time

        # Generate comprehensive monitoring report
        monitoring_report = {
            "execution_metrics": execution_tracker.get_comprehensive_metrics(),
            "performance_analysis": performance_monitor.get_performance_analysis(),
            "resource_usage": performance_monitor.get_resource_analysis(),
            "audit_trail": observability_manager.generate_audit_trail("wf_code_standards"),
            "bottlenecks": performance_monitor.identify_bottlenecks(),
        }

        # Verify comprehensive monitoring
        exec_metrics = monitoring_report["execution_metrics"]
        assert exec_metrics["total_steps"] == 7
        assert exec_metrics["completed_steps"] == 7
        assert exec_metrics["success_rate"] == 1.0

        # Verify performance analysis
        perf_analysis = monitoring_report["performance_analysis"]
        assert perf_analysis["total_workflow_duration"] == sum(s["duration"] for s in workflow_steps)
        assert "step_performance_breakdown" in perf_analysis

        # Verify bottleneck identification
        bottlenecks = monitoring_report["bottlenecks"]
        # Should identify build_check as duration bottleneck (15.4s)
        duration_bottlenecks = [b for b in bottlenecks if b["type"] == "duration"]
        assert any(b["step_id"] == "build_check" for b in duration_bottlenecks)

        # Verify audit trail completeness
        audit_trail = monitoring_report["audit_trail"]
        assert len(audit_trail["events"]) == 7  # One completion event per step
        assert all(event["event_type"] == "step_completed" for event in audit_trail["events"])

        # Verify resource tracking
        resource_analysis = monitoring_report["resource_usage"]
        assert resource_analysis["memory"]["peak_usage_mb"] == 300  # build_check peak
        assert resource_analysis["cpu"]["peak_cpu_percent"] == 70  # build_check peak

    def test_monitoring_system_health_and_alerting(self):
        """
        Test monitoring system health and failure alerting in production scenario
        Focus: System health monitoring and alert generation for real failures
        """
        observability_manager = ObservabilityManager()

        # Configure production-like alerting
        observability_manager.configure_alert_channel(
            {"channel": "email", "recipients": ["devops@company.com"], "severity_threshold": "medium"}
        )

        # Simulate system health degradation scenario
        health_events = [
            {"time": 0, "memory_usage": 60, "cpu_usage": 30, "error_rate": 0.02, "health": "healthy"},
            {"time": 10, "memory_usage": 75, "cpu_usage": 45, "error_rate": 0.05, "health": "healthy"},
            {"time": 20, "memory_usage": 85, "cpu_usage": 60, "error_rate": 0.08, "health": "degraded"},
            {"time": 30, "memory_usage": 92, "cpu_usage": 80, "error_rate": 0.15, "health": "degraded"},
            {"time": 40, "memory_usage": 98, "cpu_usage": 95, "error_rate": 0.25, "health": "unhealthy"},
        ]

        alerts_triggered = []

        def mock_alert_handler(alert_data):
            alerts_triggered.append(alert_data)

        observability_manager.set_alert_handler(mock_alert_handler)

        # Process health events
        for event in health_events:
            observability_manager.record_system_health(
                timestamp=time.time() + event["time"],
                memory_usage_percent=event["memory_usage"],
                cpu_usage_percent=event["cpu_usage"],
                error_rate=event["error_rate"],
            )

            # Check if health threshold triggers alert
            current_health = observability_manager.evaluate_system_health()

            if current_health["status"] != event["health"]:
                # Health status changed - trigger alert
                observability_manager.trigger_health_alert(
                    old_status=event["health"], new_status=current_health["status"], metrics=current_health["metrics"]
                )

        # Verify health monitoring and alerting
        assert len(alerts_triggered) >= 2  # Should alert on degraded and unhealthy

        # Verify alert escalation
        degraded_alerts = [a for a in alerts_triggered if "degraded" in a.get("message", "")]
        unhealthy_alerts = [a for a in alerts_triggered if "unhealthy" in a.get("message", "")]

        assert len(degraded_alerts) >= 1
        assert len(unhealthy_alerts) >= 1

        # Verify final system health assessment
        final_health = observability_manager.get_current_system_health()
        assert final_health["status"] == "unhealthy"
        assert final_health["memory_usage_percent"] == 98
        assert final_health["cpu_usage_percent"] == 95
        assert final_health["error_rate"] == 0.25
