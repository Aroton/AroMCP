"""
Comprehensive system resilience testing for performance and reliability.

Covers missing acceptance criteria:
- AC-PR-017: System gracefully handles resource exhaustion
- AC-PR-018: Workflow recovery works after system failures
- AC-PR-019: Circuit breaker patterns protect against cascading failures
- AC-PR-020: Load balancing distributes workflow execution efficiently
- AC-PR-025: High availability configuration supports failover
- AC-PR-026: Horizontal scaling supports increased load
- AC-PR-027: Database connection pooling optimizes resource usage
- AC-PR-028: Monitoring integration provides production visibility

Focus: Resource exhaustion handling, circuit breakers, high availability, horizontal scaling
Pillar: Performance & Reliability
"""

import pytest
import time
import threading
import psutil
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, Any, List
import asyncio
import queue
import sqlite3

from aromcp.workflow_server.monitoring.test_adapters import (
    MetricsCollectorTestAdapter as MetricsCollector,
    HAManagerTestAdapter as HAManager,
    ScalingManagerTestAdapter as ScalingManager,
    ConnectionManagerTestAdapter as ConnectionManager,
    ProductionIntegrationTestAdapter as ProductionIntegration
)
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowInstance
from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.workflow_state import WorkflowState
from aromcp.workflow_server.workflow.resource_manager import WorkflowResourceManager, ResourceExhaustionError, CircuitBreakerOpenError, OperationFailureError


class TestSystemResilience:
    """Test comprehensive system resilience and fault tolerance mechanisms."""

    @pytest.fixture
    def resource_manager(self):
        """Create resource manager for testing."""
        return WorkflowResourceManager(max_memory_mb=1000, max_cpu_percent=80, max_workflows=10)

    @pytest.fixture
    def ha_manager(self):
        """Create high availability manager for testing."""
        return HAManager(cluster_size=3, failover_timeout=30)

    @pytest.fixture
    def scaling_manager(self):
        """Create scaling manager for testing."""
        return ScalingManager(min_instances=2, max_instances=10, scale_threshold=75)

    @pytest.fixture
    def connection_manager(self):
        """Create connection manager with test database."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        return ConnectionManager(database_url=f"sqlite:///{temp_db.name}", pool_size=5)

    @pytest.fixture
    def production_integration(self):
        """Create production integration manager for testing."""
        return ProductionIntegration()

    def test_resource_exhaustion_graceful_handling(self, resource_manager):
        """
        Test AC-PR-017: System gracefully handles resource exhaustion
        Focus: Appropriate error handling and recovery when approaching limits
        """
        # Simulate workflows consuming increasing resources
        workflow_resources = [
            {"id": "wf_1", "memory_mb": 200, "cpu_percent": 20, "status": "running"},
            {"id": "wf_2", "memory_mb": 300, "cpu_percent": 25, "status": "running"},
            {"id": "wf_3", "memory_mb": 250, "cpu_percent": 15, "status": "running"},
            {"id": "wf_4", "memory_mb": 400, "cpu_percent": 30, "status": "pending"},  # Would exceed limits
        ]

        # Track resource allocation decisions
        allocation_results = []
        degradation_actions = []

        def mock_degradation_callback(action, details):
            degradation_actions.append({"action": action, "details": details})

        resource_manager.set_degradation_callback(mock_degradation_callback)

        # Attempt to allocate resources for each workflow
        for workflow in workflow_resources:
            try:
                allocation_result = resource_manager.allocate_resources(
                    workflow_id=workflow["id"],
                    memory_mb=workflow["memory_mb"],
                    cpu_percent=workflow["cpu_percent"]
                )
                allocation_results.append({
                    "workflow_id": workflow["id"],
                    "allocated": True,
                    "result": allocation_result
                })
            except ResourceExhaustionError as e:
                allocation_results.append({
                    "workflow_id": workflow["id"],
                    "allocated": False,
                    "error": str(e)
                })

        # Verify resource exhaustion handling
        successful_allocations = [r for r in allocation_results if r["allocated"]]
        failed_allocations = [r for r in allocation_results if not r["allocated"]]

        # First 3 workflows should succeed (total: 750MB memory, 60% CPU - within limits)
        assert len(successful_allocations) == 3
        assert all(wf["workflow_id"] in ["wf_1", "wf_2", "wf_3"] for wf in successful_allocations)

        # 4th workflow should fail (would push memory to 1150MB, exceeding 1000MB limit)
        assert len(failed_allocations) == 1
        assert failed_allocations[0]["workflow_id"] == "wf_4"
        assert "memory limit" in failed_allocations[0]["error"].lower()

        # Verify graceful degradation actions
        assert len(degradation_actions) > 0
        degradation_types = [action["action"] for action in degradation_actions]
        assert "resource_limit_approached" in degradation_types

        # Test resource cleanup and retry
        resource_manager.release_resources("wf_1")  # Release 200MB, 20% CPU

        # Now wf_4 should be allocatable
        retry_result = resource_manager.allocate_resources("wf_4", 400, 30)
        assert retry_result["allocated"] == True
        assert retry_result["available_memory_mb"] >= 0

    def test_workflow_recovery_after_system_failures(self, resource_manager):
        """
        Test AC-PR-018: Workflow recovery works after system failures
        Focus: State preservation and execution resumption after interruptions
        """
        # Create workflow state before "failure"
        pre_failure_state = WorkflowState(
            workflow_id="wf_recovery_test",
            status="running",
            current_step_index=3,
            total_steps=8,
            state={
                "inputs": {"config": "production"},
                "state": {"processed_files": 15, "errors": 2},
                "computed": {"completion_rate": 0.4}
            },
            execution_context={
                "start_time": time.time() - 120,  # Started 2 minutes ago
                "checkpoint_data": {
                    "last_checkpoint": time.time() - 30,
                    "completed_steps": ["step1", "step2", "step3"],
                    "pending_steps": ["step4", "step5", "step6", "step7", "step8"]
                }
            }
        )

        # Simulate system failure and recovery
        resource_manager.enable_failure_recovery(True)
        
        # Store workflow state before failure
        resource_manager.store_recovery_checkpoint(pre_failure_state)

        # Simulate system restart/recovery
        time.sleep(0.1)  # Brief delay to simulate downtime

        # Attempt to recover workflow
        recovered_workflows = resource_manager.recover_interrupted_workflows()

        # Verify recovery
        assert len(recovered_workflows) == 1
        recovered_workflow = recovered_workflows[0]
        
        assert recovered_workflow.workflow_id == "wf_recovery_test"
        assert recovered_workflow.status == "recovering"
        assert recovered_workflow.current_step_index == 3  # Resume from checkpoint
        
        # Verify state preservation
        assert recovered_workflow.state["state"]["processed_files"] == 15
        assert recovered_workflow.state["state"]["errors"] == 2
        assert recovered_workflow.state["computed"]["completion_rate"] == 0.4

        # Verify execution context restoration
        assert "checkpoint_data" in recovered_workflow.execution_context
        assert len(recovered_workflow.execution_context["checkpoint_data"]["completed_steps"]) == 3

        # Test resumption capability
        resumption_result = resource_manager.resume_workflow_execution(recovered_workflow)
        assert resumption_result["success"] == True
        assert resumption_result["resume_point"] == "step4"  # Next step after checkpoint

    def test_circuit_breaker_cascading_failure_protection(self, resource_manager):
        """
        Test AC-PR-019: Circuit breaker patterns protect against cascading failures
        Focus: Circuit breakers activate to prevent system-wide failures
        """
        # Configure circuit breakers for different operation types
        circuit_breaker_configs = [
            {"operation": "database_query", "failure_threshold": 5, "timeout": 10, "recovery_time": 30},
            {"operation": "external_api_call", "failure_threshold": 3, "timeout": 5, "recovery_time": 20},
            {"operation": "file_system_operation", "failure_threshold": 10, "timeout": 15, "recovery_time": 15}
        ]

        for config in circuit_breaker_configs:
            resource_manager.configure_circuit_breaker(
                operation_type=config["operation"],
                failure_threshold=config["failure_threshold"],
                timeout_seconds=config["timeout"],
                recovery_time_seconds=config["recovery_time"]
            )

        # Simulate failures to trigger circuit breakers
        failure_scenarios = [
            # Database failures
            *[{"operation": "database_query", "should_fail": True} for _ in range(6)],  # Exceed threshold
            # API failures  
            *[{"operation": "external_api_call", "should_fail": True} for _ in range(4)],  # Exceed threshold
            # File system operations (below threshold)
            *[{"operation": "file_system_operation", "should_fail": True} for _ in range(3)],  # Under threshold
        ]

        circuit_breaker_states = {}

        # Execute operations and track circuit breaker state
        for scenario in failure_scenarios:
            try:
                result = resource_manager.execute_protected_operation(
                    operation_type=scenario["operation"],
                    operation_params={"test": True},
                    simulate_failure=scenario["should_fail"]
                )
                # Should not reach here if circuit breaker is open
                circuit_breaker_states[scenario["operation"]] = "closed"
            except CircuitBreakerOpenError:
                circuit_breaker_states[scenario["operation"]] = "open"
            except OperationFailureError:
                # Operation failed but circuit breaker still closed  
                circuit_breaker_states[scenario["operation"]] = "closed"

        # Verify circuit breaker activation
        assert circuit_breaker_states.get("database_query") == "open"  # Should trip after 5 failures
        assert circuit_breaker_states.get("external_api_call") == "open"  # Should trip after 3 failures
        assert circuit_breaker_states.get("file_system_operation") == "closed"  # Only 3 failures, under threshold

        # Test circuit breaker recovery
        time.sleep(0.5)  # Wait for recovery (shortened for testing)
        
        # Attempt operations after recovery window
        recovery_attempts = [
            {"operation": "database_query", "should_fail": False},  # Healthy operation
            {"operation": "external_api_call", "should_fail": False}  # Healthy operation
        ]

        recovery_results = {}
        for attempt in recovery_attempts:
            try:
                result = resource_manager.execute_protected_operation(
                    operation_type=attempt["operation"],
                    operation_params={"test": True},
                    simulate_failure=attempt["should_fail"]
                )
                recovery_results[attempt["operation"]] = "recovered"
            except CircuitBreakerOpenError:
                recovery_results[attempt["operation"]] = "still_open"

        # Circuit breakers should allow healthy operations after recovery
        assert recovery_results.get("database_query") == "recovered"
        assert recovery_results.get("external_api_call") == "recovered"

    def test_load_balancing_workflow_distribution(self, scaling_manager):
        """
        Test AC-PR-020: Load balancing distributes workflow execution efficiently
        Focus: Efficient distribution across available resources
        """
        # Configure multiple execution instances
        execution_instances = [
            {"id": "instance_1", "capacity": 100, "current_load": 20, "health": "healthy"},
            {"id": "instance_2", "capacity": 100, "current_load": 60, "health": "healthy"}, 
            {"id": "instance_3", "capacity": 100, "current_load": 15, "health": "healthy"},
            {"id": "instance_4", "capacity": 100, "current_load": 90, "health": "degraded"},
            {"id": "instance_5", "capacity": 100, "current_load": 5, "health": "healthy"}
        ]

        for instance in execution_instances:
            scaling_manager.register_execution_instance(
                instance_id=instance["id"],
                capacity=instance["capacity"],
                current_load=instance["current_load"],
                health_status=instance["health"]
            )

        # Simulate incoming workflows with different resource requirements
        incoming_workflows = [
            {"id": "wf_light", "resource_requirement": 10, "priority": "low"},
            {"id": "wf_medium", "resource_requirement": 25, "priority": "medium"},
            {"id": "wf_heavy", "resource_requirement": 40, "priority": "high"},
            {"id": "wf_batch_1", "resource_requirement": 15, "priority": "low"},
            {"id": "wf_batch_2", "resource_requirement": 20, "priority": "medium"},
            {"id": "wf_critical", "resource_requirement": 30, "priority": "critical"}
        ]

        # Distribute workflows using load balancing
        distribution_results = []
        for workflow in incoming_workflows:
            assignment = scaling_manager.assign_workflow_to_instance(
                workflow_id=workflow["id"],
                resource_requirement=workflow["resource_requirement"],
                priority=workflow["priority"]
            )
            distribution_results.append(assignment)

        # Verify load balancing efficiency
        instance_assignments = {}
        for result in distribution_results:
            instance_id = result["assigned_instance"]
            if instance_id not in instance_assignments:
                instance_assignments[instance_id] = []
            instance_assignments[instance_id].append(result)

        # Verify distribution logic
        # Instance 4 should get fewer/no assignments due to degraded health and high load
        instance_4_assignments = len(instance_assignments.get("instance_4", []))
        assert instance_4_assignments <= 1  # Should avoid degraded instance

        # Instance 5 should get assignments due to low load (5%)
        instance_5_assignments = len(instance_assignments.get("instance_5", []))
        assert instance_5_assignments >= 1

        # Critical priority workflow should get best available instance
        critical_assignment = next(r for r in distribution_results if r["workflow_id"] == "wf_critical")
        critical_instance_id = critical_assignment["assigned_instance"]
        
        # Should be assigned to instance with good health and available capacity
        assigned_instance = next(i for i in execution_instances if i["id"] == critical_instance_id)
        assert assigned_instance["health"] == "healthy"
        assert assigned_instance["current_load"] < 80  # Reasonable load level

        # Verify load balancing metrics
        balancing_metrics = scaling_manager.get_load_balancing_metrics()
        assert balancing_metrics["total_assignments"] == len(incoming_workflows)
        assert balancing_metrics["healthy_instances_used"] >= 3
        assert balancing_metrics["load_distribution_variance"] < 50  # Reasonably balanced

    def test_high_availability_failover_support(self, ha_manager):
        """
        Test AC-PR-025: High availability configuration supports failover
        Focus: Failover mechanisms maintain workflow execution continuity
        """
        # Configure HA cluster
        cluster_nodes = [
            {"id": "node_1", "role": "primary", "health": "healthy", "load": 45},
            {"id": "node_2", "role": "secondary", "health": "healthy", "load": 30},
            {"id": "node_3", "role": "secondary", "health": "healthy", "load": 25}
        ]

        for node in cluster_nodes:
            ha_manager.register_cluster_node(
                node_id=node["id"],
                role=node["role"],
                health_status=node["health"],
                current_load=node["load"]
            )

        # Simulate active workflows on primary node
        active_workflows = [
            {"id": "wf_ha_1", "node": "node_1", "status": "running", "progress": 0.3},
            {"id": "wf_ha_2", "node": "node_1", "status": "running", "progress": 0.7},
            {"id": "wf_ha_3", "node": "node_1", "status": "paused", "progress": 0.5}
        ]

        for workflow in active_workflows:
            ha_manager.track_workflow(
                workflow_id=workflow["id"],
                current_node=workflow["node"],
                status=workflow["status"],
                progress=workflow["progress"]
            )

        # Simulate primary node failure
        ha_manager.report_node_failure("node_1", failure_type="network_partition")

        # Trigger failover process
        failover_result = ha_manager.execute_failover(failed_node="node_1")

        # Verify failover execution
        assert failover_result["success"] == True
        assert failover_result["new_primary"] in ["node_2", "node_3"]
        assert len(failover_result["migrated_workflows"]) == 3

        # Verify workflow migration
        migrated_workflows = failover_result["migrated_workflows"]
        workflow_migrations = {wf["workflow_id"]: wf for wf in migrated_workflows}

        assert "wf_ha_1" in workflow_migrations
        assert "wf_ha_2" in workflow_migrations
        assert "wf_ha_3" in workflow_migrations

        # Verify state preservation during migration
        for original_wf in active_workflows:
            migrated_wf = workflow_migrations[original_wf["id"]]
            assert migrated_wf["progress"] == original_wf["progress"]
            assert migrated_wf["original_status"] == original_wf["status"]
            
            # Migrated workflows should be in "recovering" state initially
            assert migrated_wf["current_status"] == "recovering"

        # Verify new cluster topology
        cluster_status = ha_manager.get_cluster_status()
        assert cluster_status["primary_node"] == failover_result["new_primary"]
        assert cluster_status["failed_nodes"] == ["node_1"]
        assert cluster_status["healthy_nodes"] == 2

        # Test failover completion and resumption
        resumption_results = []
        for workflow in migrated_workflows:
            resumption_result = ha_manager.resume_migrated_workflow(workflow["workflow_id"])
            resumption_results.append(resumption_result)

        # All workflows should resume successfully
        assert all(result["resumed"] for result in resumption_results)
        assert len([r for r in resumption_results if r["resumed"]]) == 3

    def test_horizontal_scaling_increased_load(self, scaling_manager):
        """
        Test AC-PR-026: Horizontal scaling supports increased load
        Focus: Additional instances deployed to handle increased demand
        """
        # Start with baseline instances
        initial_instances = [
            {"id": "base_1", "capacity": 100, "load": 30},
            {"id": "base_2", "capacity": 100, "load": 25}
        ]

        for instance in initial_instances:
            scaling_manager.add_instance(instance["id"], instance["capacity"])
            scaling_manager.update_instance_load(instance["id"], instance["load"])

        # Simulate increasing load over time
        load_scenarios = [
            {"time": 0, "new_workflows": 5, "avg_workflow_load": 15},    # Total: 5*15 = 75
            {"time": 10, "new_workflows": 8, "avg_workflow_load": 20},   # Total: 8*20 = 160  
            {"time": 20, "new_workflows": 12, "avg_workflow_load": 18},  # Total: 12*18 = 216
            {"time": 30, "new_workflows": 15, "avg_workflow_load": 22},  # Total: 15*22 = 330 - triggers scaling
            {"time": 40, "new_workflows": 20, "avg_workflow_load": 25},  # Total: 20*25 = 500 - more scaling
        ]

        scaling_events = []
        current_load = 55  # Initial load from both instances

        for scenario in load_scenarios:
            # Add new load
            new_load = scenario["new_workflows"] * scenario["avg_workflow_load"]
            current_load += new_load

            # Update load and check scaling decision
            scaling_manager.update_system_load(current_load)
            scaling_decision = scaling_manager.evaluate_scaling_need()

            if scaling_decision["action"] == "scale_up":
                # Execute scaling up
                scale_result = scaling_manager.scale_up(
                    instances_to_add=scaling_decision["instances_needed"]
                )
                scaling_events.append({
                    "time": scenario["time"],
                    "action": "scale_up",
                    "instances_added": scale_result["instances_added"],
                    "total_instances": scale_result["total_instances"]
                })
                
                # Distribute load across new instances
                scaling_manager.redistribute_load()

        # Verify scaling events occurred
        assert len(scaling_events) >= 2  # Should have scaled up at least twice

        # Verify scaling triggers at appropriate thresholds
        scale_up_events = [e for e in scaling_events if e["action"] == "scale_up"]
        assert len(scale_up_events) >= 2

        # Verify final system capacity
        final_status = scaling_manager.get_scaling_status()
        assert final_status["total_instances"] > 2  # More than initial 2 instances
        assert final_status["total_capacity"] > 200  # More than initial 200 capacity
        assert final_status["average_utilization"] < 90  # Load well-distributed

        # Test scale-down after load reduction
        scaling_manager.update_system_load(80)  # Significant load reduction
        scale_down_decision = scaling_manager.evaluate_scaling_need()

        if scale_down_decision["action"] == "scale_down":
            scale_result = scaling_manager.scale_down(
                instances_to_remove=scale_down_decision["instances_excess"]
            )
            
            # Verify scale-down preserves minimum instances
            assert scale_result["total_instances"] >= scaling_manager.min_instances
            assert scale_result["instances_removed"] > 0

    def test_database_connection_pooling_optimization(self, connection_manager):
        """
        Test AC-PR-027: Database connection pooling optimizes resource usage
        Focus: Connection pool prevents connection exhaustion
        """
        # Test concurrent database operations
        connection_usage_log = []
        operation_results = []
        
        def database_operation(operation_id, duration=0.1):
            """Simulate database operation requiring connection."""
            try:
                connection = connection_manager.get_connection()
                connection_usage_log.append({
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "action": "acquired",
                    "connection_id": id(connection),
                    "pool_size": connection_manager.get_pool_size(),
                    "active_connections": connection_manager.get_active_connection_count()
                })
                
                # Simulate database work
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                time.sleep(duration)
                
                # Return connection to pool
                connection_manager.return_connection(connection)
                connection_usage_log.append({
                    "operation_id": operation_id,
                    "timestamp": time.time(),
                    "action": "returned",
                    "connection_id": id(connection),
                    "pool_size": connection_manager.get_pool_size(),
                    "active_connections": connection_manager.get_active_connection_count()
                })
                
                operation_results.append({"operation_id": operation_id, "success": True, "result": result})
                
            except Exception as e:
                operation_results.append({"operation_id": operation_id, "success": False, "error": str(e)})

        # Execute many concurrent database operations (more than pool size)
        threads = []
        for i in range(15):  # Pool size is 5, so 15 operations should test pooling
            thread = threading.Thread(target=database_operation, args=(i, 0.2))
            threads.append(thread)

        start_time = time.time()
        
        # Start all operations concurrently
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        total_time = time.time() - start_time

        # Verify connection pooling efficiency
        successful_operations = [op for op in operation_results if op["success"]]
        assert len(successful_operations) == 15  # All operations should succeed

        # Verify pool usage patterns
        max_active = max(log["active_connections"] for log in connection_usage_log)
        assert max_active <= 5  # Should not exceed pool size

        # Verify connection reuse
        connection_ids = [log["connection_id"] for log in connection_usage_log]
        unique_connections = set(connection_ids)
        assert len(unique_connections) <= 5  # Should reuse connections from pool

        # Verify performance benefit of pooling
        # With pooling, should complete faster than serial execution (15 * 0.2 = 3s)
        assert total_time < 2.0  # Should benefit from concurrency despite pool limits

        # Test connection pool health monitoring
        pool_health = connection_manager.get_pool_health()
        assert pool_health["pool_size"] == 5
        assert pool_health["available_connections"] == 5  # All returned after operations
        assert pool_health["connection_leaks"] == 0  # No leaked connections
        assert pool_health["total_operations"] == 15

    def test_monitoring_integration_production_visibility(self, production_integration):
        """
        Test AC-PR-028: Monitoring integration provides production visibility
        Focus: System health, performance, and workflow metrics available to monitoring
        """
        # Configure production monitoring integrations
        monitoring_systems = [
            {"name": "prometheus", "endpoint": "http://prometheus:9090", "scrape_interval": 15},
            {"name": "grafana", "endpoint": "http://grafana:3000", "dashboard_id": "workflow_metrics"},
            {"name": "datadog", "api_key": "mock_key", "tags": ["env:production", "service:workflow"]},
            {"name": "newrelic", "license_key": "mock_license", "app_name": "workflow_server"}
        ]

        for system in monitoring_systems:
            production_integration.configure_monitoring_system(system)

        # Generate production metrics
        production_metrics = {
            # System health metrics
            "system_health": {
                "cpu_usage_percent": 65,
                "memory_usage_percent": 78,
                "disk_usage_percent": 45,
                "network_io_mbps": 12.5,
                "uptime_seconds": 86400  # 24 hours
            },
            
            # Workflow performance metrics
            "workflow_performance": {
                "active_workflows": 23,
                "completed_workflows_24h": 145,
                "failed_workflows_24h": 8,
                "average_workflow_duration": 34.2,
                "p95_workflow_duration": 67.8,
                "workflow_success_rate": 0.945
            },
            
            # Resource utilization metrics
            "resource_utilization": {
                "thread_pool_usage": 0.72,
                "connection_pool_usage": 0.68,
                "memory_pool_usage": 0.81,
                "cache_hit_rate": 0.89
            },
            
            # Business metrics
            "business_metrics": {
                "workflows_per_minute": 2.4,
                "step_execution_rate": 15.3,
                "user_interactions_per_hour": 45,
                "error_rate_per_thousand": 5.5
            }
        }

        # Push metrics to all configured systems
        integration_results = production_integration.publish_metrics(production_metrics)

        # Verify metrics publishing
        assert len(integration_results) == 4  # One result per monitoring system
        
        for system_name, result in integration_results.items():
            assert result["status"] == "success"
            assert result["metrics_sent"] > 0
            assert "endpoint" in result

        # Test alerting integration
        alert_conditions = [
            {"metric": "cpu_usage_percent", "threshold": 80, "severity": "warning"},
            {"metric": "memory_usage_percent", "threshold": 85, "severity": "critical"},
            {"metric": "workflow_success_rate", "threshold": 0.9, "operator": "<", "severity": "critical"},
            {"metric": "error_rate_per_thousand", "threshold": 10, "operator": ">", "severity": "warning"}
        ]

        alerts_triggered = []
        for condition in alert_conditions:
            alert_result = production_integration.evaluate_alert_condition(
                condition, production_metrics
            )
            if alert_result["triggered"]:
                alerts_triggered.append(alert_result)

        # Verify alert evaluation
        # memory_usage_percent (78%) should not trigger (threshold 85%)
        # workflow_success_rate (0.945) should not trigger (threshold 0.9, operator <)
        # error_rate_per_thousand (5.5) should not trigger (threshold 10, operator >)
        assert len(alerts_triggered) == 0  # No alerts should trigger with current metrics

        # Test dashboard data export
        dashboard_data = production_integration.generate_dashboard_data(
            time_range="1h",
            granularity="5m"
        )

        # Verify dashboard data structure
        assert "time_series" in dashboard_data
        assert "summary_stats" in dashboard_data
        assert "health_indicators" in dashboard_data

        # Verify time series data
        time_series = dashboard_data["time_series"]
        assert len(time_series) > 0
        assert all("timestamp" in point and "values" in point for point in time_series)

        # Test custom metric queries
        custom_queries = [
            "avg(workflow_duration) by (workflow_type)",
            "rate(workflow_failures[5m])",
            "histogram_quantile(0.95, workflow_step_duration_bucket)"
        ]

        query_results = {}
        for query in custom_queries:
            result = production_integration.execute_custom_query(query)
            query_results[query] = result

        # Verify custom queries executed
        assert len(query_results) == 3
        for query, result in query_results.items():
            assert result["status"] == "success"
            assert "data" in result


class TestSystemResilienceIntegration:
    """Test system resilience integration in realistic failure scenarios."""

    def test_cascading_failure_prevention_comprehensive(self):
        """
        Test comprehensive cascading failure prevention across all resilience mechanisms
        Focus: Multiple simultaneous failures and coordinated recovery
        """
        # Initialize all resilience components
        resource_manager = MetricsCollector(max_memory_mb=800, max_cpu_percent=75)
        ha_manager = HAManager(cluster_size=3, failover_timeout=15)
        scaling_manager = ScalingManager(min_instances=2, max_instances=8)
        
        # Simulate production environment under stress
        initial_system_state = {
            "memory_usage": 60,  # 60% memory usage
            "cpu_usage": 45,     # 45% CPU usage
            "active_workflows": 12,
            "healthy_nodes": 3,
            "instance_count": 3
        }

        # Configure circuit breakers
        resource_manager.configure_circuit_breaker("database_query", failure_threshold=3, recovery_time=10)
        resource_manager.configure_circuit_breaker("external_api", failure_threshold=2, recovery_time=15)

        # Simulate cascading failure scenario
        failure_events = [
            {"time": 0, "event": "high_load_spike", "impact": {"memory": +25, "cpu": +20}},
            {"time": 5, "event": "database_slowdown", "impact": {"database_failures": 4}},
            {"time": 10, "event": "node_failure", "impact": {"failed_nodes": ["node_1"]}},
            {"time": 15, "event": "api_service_degradation", "impact": {"api_failures": 3}},
            {"time": 20, "event": "memory_pressure", "impact": {"memory": +15}},
        ]

        system_responses = []
        current_state = initial_system_state.copy()

        for event in failure_events:
            # Apply failure impact
            if "memory" in event["impact"]:
                current_state["memory_usage"] += event["impact"]["memory"]
            if "cpu" in event["impact"]:
                current_state["cpu_usage"] += event["impact"]["cpu"]

            # Trigger resilience mechanisms
            responses = []

            # Resource management response
            if current_state["memory_usage"] > 80:
                resource_response = resource_manager.handle_resource_pressure(
                    memory_usage=current_state["memory_usage"],
                    cpu_usage=current_state["cpu_usage"]
                )
                responses.append({"component": "resource_manager", "action": resource_response})

            # Circuit breaker response
            if "database_failures" in event["impact"]:
                cb_response = resource_manager.handle_operation_failures(
                    "database_query", event["impact"]["database_failures"]
                )
                responses.append({"component": "circuit_breaker", "action": cb_response})

            # High availability response
            if "failed_nodes" in event["impact"]:
                ha_response = ha_manager.handle_node_failures(event["impact"]["failed_nodes"])
                responses.append({"component": "ha_manager", "action": ha_response})

            # Scaling response
            if current_state["memory_usage"] > 85 or current_state["cpu_usage"] > 70:
                scaling_response = scaling_manager.handle_capacity_shortage(
                    current_instances=current_state["instance_count"],
                    resource_pressure={"memory": current_state["memory_usage"], "cpu": current_state["cpu_usage"]}
                )
                responses.append({"component": "scaling_manager", "action": scaling_response})
                
                if scaling_response.get("scaled_up"):
                    current_state["instance_count"] += scaling_response["instances_added"]
                    # Scaling reduces per-instance resource usage
                    current_state["memory_usage"] *= 0.8  
                    current_state["cpu_usage"] *= 0.8

            system_responses.append({
                "time": event["time"],
                "event": event["event"],
                "system_state": current_state.copy(),
                "responses": responses
            })

        # Verify cascading failure prevention
        final_state = system_responses[-1]["system_state"]
        
        # System should remain operational despite multiple failures
        assert final_state["memory_usage"] < 95  # Didn't reach complete exhaustion
        assert final_state["instance_count"] > initial_system_state["instance_count"]  # Scaled up to handle load

        # Verify coordinated responses
        all_responses = []
        for response_set in system_responses:
            all_responses.extend(response_set["responses"])

        response_components = set(r["component"] for r in all_responses)
        assert len(response_components) >= 3  # Multiple components responded

        # Verify no single point of failure
        ha_responses = [r for r in all_responses if r["component"] == "ha_manager"]
        assert len(ha_responses) > 0  # HA manager handled node failure

        circuit_breaker_responses = [r for r in all_responses if r["component"] == "circuit_breaker"]
        assert len(circuit_breaker_responses) > 0  # Circuit breakers activated

        scaling_responses = [r for r in all_responses if r["component"] == "scaling_manager"]
        assert len(scaling_responses) > 0  # Scaling occurred

        # System should be in a stable state after coordinated recovery
        assert final_state["memory_usage"] < 90
        assert final_state["cpu_usage"] < 80

    def test_production_resilience_validation(self):
        """
        Test production-level resilience validation
        Focus: System meets production SLA requirements under stress
        """
        # Production SLA requirements
        sla_requirements = {
            "uptime_percentage": 99.9,      # 99.9% uptime
            "max_response_time_ms": 5000,   # 5 second max response
            "error_rate_threshold": 0.01,   # 1% error rate max
            "recovery_time_max_seconds": 30, # 30 second max recovery
            "data_consistency": True         # No data loss during failures
        }

        # Initialize production-grade resilience system
        resilience_system = ProductionResilienceSystem(sla_requirements)

        # Simulate 24-hour production workload with failures
        simulation_results = resilience_system.run_24hour_simulation(
            base_load_workflows_per_hour=100,
            peak_load_multiplier=3.0,
            failure_injection_rate=0.05,  # 5% failure injection rate
            failure_types=["node_failure", "network_partition", "resource_exhaustion", "database_timeout"]
        )

        # Verify SLA compliance
        sla_compliance = simulation_results["sla_compliance"]
        
        assert sla_compliance["uptime_percentage"] >= sla_requirements["uptime_percentage"]
        assert sla_compliance["max_response_time_ms"] <= sla_requirements["max_response_time_ms"]
        assert sla_compliance["error_rate"] <= sla_requirements["error_rate_threshold"]
        assert sla_compliance["max_recovery_time_seconds"] <= sla_requirements["recovery_time_max_seconds"]
        assert sla_compliance["data_consistency_maintained"] == True

        # Verify resilience mechanisms effectiveness
        resilience_metrics = simulation_results["resilience_metrics"]
        assert resilience_metrics["failures_detected"] > 0
        assert resilience_metrics["successful_recoveries"] >= resilience_metrics["failures_detected"] * 0.95  # 95% recovery rate
        assert resilience_metrics["cascading_failures_prevented"] >= 0

        # Verify production readiness score
        production_readiness = simulation_results["production_readiness_score"]
        assert production_readiness >= 0.95  # 95% production readiness