"""
Comprehensive test suite for Sub-Agent Management Infrastructure - Phase 2

These tests are designed to fail initially and guide infrastructure development.
They test advanced sub-agent management features that don't exist yet.

Covers acceptance criteria:
- AC-SAM-010: Sub-agent timeout handling and inheritance
- AC-SAM-020: Failure isolation between sub-agents
- AC-SAM-021: Resource cleanup for failed sub-agents
- AC-SAM-019: Sub-agent monitoring and metrics
"""

import pytest
import asyncio
import time
import threading
import psutil
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Dict, List, Any, Optional
import uuid
import weakref

# These imports will fail initially - that's expected
try:
    from aromcp.workflow_server.subagent.timeout_coordinator import SubAgentTimeoutCoordinator
    from aromcp.workflow_server.subagent.failure_isolator import SubAgentFailureIsolator
    from aromcp.workflow_server.subagent.resource_cleaner import SubAgentResourceCleaner
    from aromcp.workflow_server.subagent.monitor import SubAgentMonitor
    from aromcp.workflow_server.subagent.lifecycle_manager import SubAgentLifecycleManager
    from aromcp.workflow_server.subagent.communication_manager import SubAgentCommunicationManager
    from aromcp.workflow_server.subagent.state_isolator import SubAgentStateIsolator
    from aromcp.workflow_server.subagent.metrics_collector import SubAgentMetricsCollector
except ImportError:
    # Expected to fail - infrastructure doesn't exist yet
    SubAgentTimeoutCoordinator = None
    SubAgentFailureIsolator = None
    SubAgentResourceCleaner = None
    SubAgentMonitor = None
    SubAgentLifecycleManager = None
    SubAgentCommunicationManager = None
    SubAgentStateIsolator = None
    SubAgentMetricsCollector = None

from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
from aromcp.workflow_server.state.manager import StateManager


class TestSubAgentTimeoutHandling:
    """Test sub-agent timeout handling and inheritance (AC-SAM-010)."""
    
    @pytest.mark.xfail(reason="SubAgentTimeoutCoordinator not implemented yet")
    def test_timeout_inheritance_from_parent(self):
        """Test that sub-agents properly inherit timeout constraints from parent."""
        if not SubAgentTimeoutCoordinator:
            pytest.skip("SubAgentTimeoutCoordinator infrastructure not implemented")
            
        # Infrastructure needed: Timeout coordinator for sub-agents
        coordinator = SubAgentTimeoutCoordinator()
        
        # Set parent workflow timeout
        parent_id = "parent_workflow_1"
        coordinator.set_workflow_timeout(parent_id, total_timeout=300)  # 5 minutes
        
        # Simulate some time already consumed
        coordinator.record_elapsed_time(parent_id, 60)  # 1 minute used
        
        # Create sub-agents with different patterns
        parallel_agents = []
        for i in range(3):
            agent_config = coordinator.create_subagent_timeout(
                parent_id=parent_id,
                subagent_id=f"parallel_agent_{i}",
                execution_mode="parallel",
                estimated_duration=120  # 2 minutes each
            )
            parallel_agents.append(agent_config)
            
        # All parallel agents should get the same timeout (remaining time)
        assert all(a["timeout"] == 240 for a in parallel_agents)  # 4 minutes remaining
        assert all(a["hard_deadline"] == 240 for a in parallel_agents)
        
        # Create sequential sub-agents
        sequential_agents = []
        remaining_time = 240
        for i in range(3):
            agent_config = coordinator.create_subagent_timeout(
                parent_id=parent_id,
                subagent_id=f"sequential_agent_{i}",
                execution_mode="sequential",
                position=i,
                total_sequential_agents=3,
                estimated_duration=60
            )
            sequential_agents.append(agent_config)
            
        # Sequential agents should get proportional timeouts
        assert sequential_agents[0]["timeout"] <= 80  # ~1/3 of remaining
        assert sequential_agents[1]["timeout"] <= 80
        assert sequential_agents[2]["timeout"] <= 80
        
        # Test dynamic timeout adjustment
        # First sequential agent takes longer than expected
        coordinator.record_subagent_completion(
            parent_id, "sequential_agent_0", 
            actual_duration=100  # Took 100s instead of 60s
        )
        
        # Remaining agents should get adjusted timeouts
        adjusted_timeout = coordinator.get_adjusted_timeout(
            parent_id, "sequential_agent_1"
        )
        assert adjusted_timeout < sequential_agents[1]["timeout"]
        
    @pytest.mark.xfail(reason="Timeout propagation not implemented yet")
    def test_cascading_timeout_cancellation(self):
        """Test cascading timeout cancellation for sub-agents."""
        if not SubAgentTimeoutCoordinator:
            pytest.skip("Cascading timeout cancellation not implemented")
            
        coordinator = SubAgentTimeoutCoordinator()
        
        # Create parent with sub-agents
        parent_id = "parent_timeout_test"
        coordinator.set_workflow_timeout(parent_id, 60)  # 1 minute
        
        # Create nested sub-agent hierarchy
        sub_agents = {
            "level1_agent": {
                "timeout": 50,
                "children": ["level2_agent_1", "level2_agent_2"]
            },
            "level2_agent_1": {
                "timeout": 40,
                "children": ["level3_agent_1"]
            },
            "level2_agent_2": {
                "timeout": 40,
                "children": []
            },
            "level3_agent_1": {
                "timeout": 30,
                "children": []
            }
        }
        
        for agent_id, config in sub_agents.items():
            coordinator.register_subagent(
                parent_id=parent_id,
                agent_id=agent_id,
                timeout=config["timeout"],
                children=config["children"]
            )
            
        # Track cancellations
        cancelled_agents = []
        
        def cancellation_handler(agent_id, reason):
            cancelled_agents.append((agent_id, reason))
            
        coordinator.set_cancellation_handler(cancellation_handler)
        
        # Trigger parent timeout
        coordinator.trigger_timeout(parent_id)
        
        # Verify cascading cancellation
        assert len(cancelled_agents) == 4  # All sub-agents cancelled
        
        # Verify cancellation order (deepest first)
        cancelled_ids = [agent_id for agent_id, _ in cancelled_agents]
        assert cancelled_ids.index("level3_agent_1") < cancelled_ids.index("level2_agent_1")
        assert cancelled_ids.index("level2_agent_1") < cancelled_ids.index("level1_agent")
        
        # Verify cancellation reasons
        reasons = {agent_id: reason for agent_id, reason in cancelled_agents}
        assert "parent_timeout" in reasons["level1_agent"]
        assert "cascade_from_parent" in reasons["level3_agent_1"]
        
    @pytest.mark.xfail(reason="Timeout monitoring not implemented yet")
    def test_subagent_timeout_monitoring(self):
        """Test real-time monitoring of sub-agent timeout status."""
        if not SubAgentTimeoutCoordinator:
            pytest.skip("Sub-agent timeout monitoring not implemented")
            
        coordinator = SubAgentTimeoutCoordinator()
        monitor = SubAgentMonitor()
        
        # Configure monitoring
        monitor.configure_timeout_alerts({
            "warning_threshold": 0.2,  # Warn at 20% remaining
            "critical_threshold": 0.1,  # Critical at 10% remaining
            "check_interval": 1  # Check every second
        })
        
        # Create sub-agents with various timeouts
        parent_id = "monitored_parent"
        agents = [
            {"id": "fast_agent", "timeout": 10},
            {"id": "medium_agent", "timeout": 30},
            {"id": "slow_agent", "timeout": 60}
        ]
        
        for agent in agents:
            coordinator.create_subagent_timeout(
                parent_id=parent_id,
                subagent_id=agent["id"],
                execution_mode="parallel",
                estimated_duration=agent["timeout"]
            )
            
        # Start monitoring
        alerts = []
        
        def alert_handler(alert):
            alerts.append(alert)
            
        monitor.set_alert_handler(alert_handler)
        monitor.start_monitoring(coordinator, parent_id)
        
        # Simulate time passage
        time.sleep(8)  # Fast agent at 20% remaining
        
        # Check alerts
        fast_agent_alerts = [a for a in alerts if a["agent_id"] == "fast_agent"]
        assert len(fast_agent_alerts) > 0
        assert fast_agent_alerts[0]["level"] == "warning"
        assert fast_agent_alerts[0]["remaining_percentage"] <= 0.2
        
        # Get timeout dashboard
        dashboard = monitor.get_timeout_dashboard(parent_id)
        
        assert "fast_agent" in dashboard["agents"]
        assert dashboard["agents"]["fast_agent"]["status"] == "warning"
        assert dashboard["agents"]["fast_agent"]["time_remaining"] < 3
        assert dashboard["agents"]["medium_agent"]["status"] == "normal"


class TestSubAgentFailureIsolation:
    """Test failure isolation between sub-agents (AC-SAM-020)."""
    
    @pytest.mark.xfail(reason="SubAgentFailureIsolator not implemented yet")
    def test_failure_isolation_between_agents(self):
        """Test that failures in one sub-agent don't affect others."""
        if not SubAgentFailureIsolator:
            pytest.skip("SubAgentFailureIsolator infrastructure not implemented")
            
        # Infrastructure needed: Failure isolation system
        isolator = SubAgentFailureIsolator()
        
        # Create isolated execution contexts
        parent_id = "parent_workflow"
        agents = ["agent_1", "agent_2", "agent_3"]
        
        contexts = {}
        for agent_id in agents:
            context = isolator.create_isolated_context(
                parent_id=parent_id,
                agent_id=agent_id,
                isolation_level="strict"
            )
            contexts[agent_id] = context
            
        # Simulate agent executions with one failure
        def agent_1_execution():
            ctx = contexts["agent_1"]
            ctx.set_state("status", "running")
            ctx.allocate_resource("memory", 100)
            ctx.allocate_resource("connections", 5)
            # Success
            ctx.set_state("status", "completed")
            return {"result": "success"}
            
        def agent_2_execution():
            ctx = contexts["agent_2"]
            ctx.set_state("status", "running")
            ctx.allocate_resource("memory", 200)
            # Simulate failure
            raise Exception("Agent 2 failed with error")
            
        def agent_3_execution():
            ctx = contexts["agent_3"]
            ctx.set_state("status", "running")
            ctx.allocate_resource("memory", 150)
            # Should complete despite agent_2 failure
            ctx.set_state("status", "completed")
            return {"result": "success"}
            
        # Execute agents in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(agent_1_execution): "agent_1",
                executor.submit(agent_2_execution): "agent_2",
                executor.submit(agent_3_execution): "agent_3"
            }
            
            for future in futures:
                agent_id = futures[future]
                try:
                    results[agent_id] = future.result(timeout=5)
                except Exception as e:
                    results[agent_id] = {"error": str(e)}
                    
        # Verify isolation
        assert results["agent_1"]["result"] == "success"
        assert "error" in results["agent_2"]
        assert results["agent_3"]["result"] == "success"
        
        # Verify resource isolation
        isolation_report = isolator.get_isolation_report(parent_id)
        
        assert isolation_report["agent_1"]["resources_leaked"] == False
        assert isolation_report["agent_2"]["resources_leaked"] == False
        assert isolation_report["agent_3"]["resources_leaked"] == False
        
        # Verify no cross-contamination
        assert isolation_report["cross_contamination_detected"] == False
        
        # Check failure containment
        assert isolation_report["agent_2"]["failure_contained"] == True
        assert isolation_report["agent_2"]["affected_agents"] == []
        
    @pytest.mark.xfail(reason="State isolation not implemented yet")
    def test_state_isolation_mechanisms(self):
        """Test state isolation between sub-agents."""
        if not SubAgentStateIsolator:
            pytest.skip("SubAgentStateIsolator infrastructure not implemented")
            
        # Infrastructure needed: State isolation for sub-agents
        isolator = SubAgentStateIsolator()
        
        # Create parent state
        parent_state = {
            "global_config": {"api_key": "secret_key"},
            "shared_data": {"items": [1, 2, 3]},
            "workflow_status": "running"
        }
        
        # Create isolated states for sub-agents
        agent1_state = isolator.create_isolated_state(
            parent_state=parent_state,
            agent_id="agent_1",
            access_rules={
                "read": ["shared_data.items"],
                "write": ["agent_results.agent_1"]
            }
        )
        
        agent2_state = isolator.create_isolated_state(
            parent_state=parent_state,
            agent_id="agent_2",
            access_rules={
                "read": ["shared_data.items"],
                "write": ["agent_results.agent_2"],
                "deny": ["global_config"]  # Explicitly deny sensitive data
            }
        )
        
        # Test read access
        assert agent1_state.read("shared_data.items") == [1, 2, 3]
        assert agent2_state.read("shared_data.items") == [1, 2, 3]
        
        # Test write isolation
        agent1_state.write("agent_results.agent_1", {"processed": 10})
        agent2_state.write("agent_results.agent_2", {"processed": 20})
        
        # Verify writes don't affect each other
        assert agent1_state.read("agent_results.agent_1") == {"processed": 10}
        with pytest.raises(isolator.AccessDeniedError):
            agent1_state.read("agent_results.agent_2")
            
        # Test access control
        with pytest.raises(isolator.AccessDeniedError):
            agent2_state.read("global_config")
            
        # Test state snapshots
        snapshot1 = isolator.get_state_snapshot("agent_1")
        snapshot2 = isolator.get_state_snapshot("agent_2")
        
        assert "global_config" not in snapshot2  # Denied access
        assert snapshot1["agent_results"]["agent_1"] == {"processed": 10}
        assert "agent_2" not in snapshot1["agent_results"]  # Isolated
        
    @pytest.mark.xfail(reason="Communication isolation not implemented yet")
    def test_communication_channel_isolation(self):
        """Test isolation of communication channels between sub-agents."""
        if not SubAgentCommunicationManager:
            pytest.skip("Communication isolation not implemented")
            
        # Infrastructure needed: Isolated communication channels
        comm_manager = SubAgentCommunicationManager()
        
        # Create communication channels
        parent_id = "parent_workflow"
        
        # Set up isolated channels
        comm_manager.create_channel(parent_id, "agent_1", "isolated")
        comm_manager.create_channel(parent_id, "agent_2", "isolated")
        comm_manager.create_channel(parent_id, "agent_3", "isolated")
        
        # Create a broadcast channel for parent
        comm_manager.create_channel(parent_id, "broadcast", "broadcast")
        
        # Test isolated messaging
        comm_manager.send_message("agent_1", {
            "type": "task",
            "data": "process_item_1"
        })
        
        comm_manager.send_message("agent_2", {
            "type": "task", 
            "data": "process_item_2"
        })
        
        # Agents should only see their own messages
        agent1_messages = comm_manager.receive_messages("agent_1")
        agent2_messages = comm_manager.receive_messages("agent_2")
        agent3_messages = comm_manager.receive_messages("agent_3")
        
        assert len(agent1_messages) == 1
        assert agent1_messages[0]["data"] == "process_item_1"
        
        assert len(agent2_messages) == 1
        assert agent2_messages[0]["data"] == "process_item_2"
        
        assert len(agent3_messages) == 0  # No messages
        
        # Test broadcast channel
        comm_manager.broadcast_message(parent_id, {
            "type": "status_update",
            "message": "Phase 1 complete"
        })
        
        # All agents should receive broadcast
        for agent_id in ["agent_1", "agent_2", "agent_3"]:
            broadcasts = comm_manager.receive_broadcasts(agent_id)
            assert len(broadcasts) == 1
            assert broadcasts[0]["message"] == "Phase 1 complete"
            
        # Test channel security
        # Agent 1 tries to read agent 2's channel
        with pytest.raises(comm_manager.ChannelAccessError):
            comm_manager.receive_messages("agent_2", requester="agent_1")


class TestSubAgentResourceCleanup:
    """Test resource cleanup for failed sub-agents (AC-SAM-021)."""
    
    @pytest.mark.xfail(reason="SubAgentResourceCleaner not implemented yet")
    def test_automatic_resource_cleanup_on_failure(self):
        """Test automatic cleanup of resources when sub-agent fails."""
        if not SubAgentResourceCleaner:
            pytest.skip("SubAgentResourceCleaner infrastructure not implemented")
            
        # Infrastructure needed: Resource cleanup system
        cleaner = SubAgentResourceCleaner()
        
        # Register cleanup handlers
        cleaner.register_cleanup_handler("file", lambda r: os.remove(r["path"]))
        cleaner.register_cleanup_handler("connection", lambda r: r["conn"].close())
        cleaner.register_cleanup_handler("memory", lambda r: r["buffer"].release())
        
        # Track sub-agent resources
        agent_id = "failing_agent"
        
        # Allocate various resources
        resources = [
            cleaner.track_resource(agent_id, "file", {
                "path": "/tmp/agent_temp_file.txt",
                "created_at": time.time()
            }),
            cleaner.track_resource(agent_id, "connection", {
                "conn": Mock(close=Mock()),
                "type": "database"
            }),
            cleaner.track_resource(agent_id, "memory", {
                "buffer": Mock(release=Mock()),
                "size": 1024 * 1024  # 1MB
            }),
            cleaner.track_resource(agent_id, "file", {
                "path": "/tmp/agent_output.json",
                "created_at": time.time()
            })
        ]
        
        # Simulate agent failure
        try:
            # Agent processing
            raise Exception("Agent processing failed")
        except Exception:
            # Trigger cleanup
            cleanup_report = cleaner.cleanup_agent_resources(agent_id)
            
        # Verify cleanup
        assert cleanup_report["total_resources"] == 4
        assert cleanup_report["cleaned_up"] == 4
        assert cleanup_report["cleanup_errors"] == 0
        
        # Verify specific cleanups
        assert cleanup_report["by_type"]["file"] == 2
        assert cleanup_report["by_type"]["connection"] == 1
        assert cleanup_report["by_type"]["memory"] == 1
        
        # Verify cleanup handlers were called
        resources[1]["conn"].close.assert_called_once()
        resources[2]["buffer"].release.assert_called_once()
        
        # Verify resource tracking is cleared
        remaining = cleaner.get_agent_resources(agent_id)
        assert len(remaining) == 0
        
    @pytest.mark.xfail(reason="Resource lifecycle management not implemented yet")
    def test_resource_lifecycle_management(self):
        """Test complete resource lifecycle for sub-agents."""
        if not SubAgentLifecycleManager:
            pytest.skip("SubAgentLifecycleManager infrastructure not implemented")
            
        # Infrastructure needed: Lifecycle manager for sub-agents
        lifecycle_manager = SubAgentLifecycleManager()
        
        # Configure resource limits
        lifecycle_manager.configure_limits({
            "max_memory_per_agent": 100 * 1024 * 1024,  # 100MB
            "max_file_handles": 10,
            "max_connections": 5,
            "max_execution_time": 300  # 5 minutes
        })
        
        # Create sub-agent with lifecycle tracking
        agent_id = "lifecycle_test_agent"
        agent_context = lifecycle_manager.create_agent(
            agent_id=agent_id,
            parent_id="parent_workflow",
            resource_requirements={
                "estimated_memory": 50 * 1024 * 1024,
                "estimated_duration": 120
            }
        )
        
        # Verify initial state
        assert agent_context["status"] == "created"
        assert agent_context["resources"]["allocated"] == {}
        
        # Start agent
        lifecycle_manager.start_agent(agent_id)
        
        # Allocate resources during execution
        lifecycle_manager.allocate_resource(agent_id, "memory", 30 * 1024 * 1024)
        lifecycle_manager.allocate_resource(agent_id, "file_handle", 1)
        lifecycle_manager.allocate_resource(agent_id, "connection", 1)
        
        # Check resource usage
        usage = lifecycle_manager.get_resource_usage(agent_id)
        assert usage["memory"]["used"] == 30 * 1024 * 1024
        assert usage["memory"]["limit"] == 100 * 1024 * 1024
        assert usage["memory"]["percentage"] == 30
        
        # Try to exceed limits
        with pytest.raises(lifecycle_manager.ResourceLimitExceeded):
            lifecycle_manager.allocate_resource(agent_id, "memory", 80 * 1024 * 1024)
            
        # Complete agent normally
        lifecycle_manager.complete_agent(agent_id, {"result": "success"})
        
        # Verify cleanup
        final_report = lifecycle_manager.get_agent_report(agent_id)
        assert final_report["status"] == "completed"
        assert final_report["resources"]["released"] == True
        assert final_report["cleanup"]["automatic"] == True
        
        # Test failure scenario
        failing_agent = "failing_lifecycle_agent"
        lifecycle_manager.create_agent(failing_agent, "parent_workflow", {})
        lifecycle_manager.start_agent(failing_agent)
        
        # Allocate resources
        lifecycle_manager.allocate_resource(failing_agent, "memory", 20 * 1024 * 1024)
        lifecycle_manager.allocate_resource(failing_agent, "file_handle", 3)
        
        # Simulate failure
        lifecycle_manager.fail_agent(failing_agent, "Processing error")
        
        # Verify cleanup on failure
        failure_report = lifecycle_manager.get_agent_report(failing_agent)
        assert failure_report["status"] == "failed"
        assert failure_report["cleanup"]["triggered_by"] == "failure"
        assert failure_report["cleanup"]["resources_released"] == True
        
    @pytest.mark.xfail(reason="Cleanup policies not implemented yet")
    def test_configurable_cleanup_policies(self):
        """Test different cleanup policies for various scenarios."""
        if not SubAgentResourceCleaner:
            pytest.skip("Cleanup policies not implemented")
            
        cleaner = SubAgentResourceCleaner()
        
        # Configure different cleanup policies
        cleaner.set_cleanup_policy("immediate", {
            "trigger": "on_completion",
            "delay": 0,
            "preserve_on_error": False
        })
        
        cleaner.set_cleanup_policy("delayed", {
            "trigger": "on_completion",
            "delay": 300,  # 5 minutes
            "preserve_on_error": True
        })
        
        cleaner.set_cleanup_policy("manual", {
            "trigger": "manual_only",
            "preserve_on_error": True
        })
        
        # Test immediate cleanup
        agent1 = "immediate_cleanup_agent"
        cleaner.track_resource(agent1, "temp_file", {"path": "/tmp/immediate.txt"})
        cleaner.apply_cleanup_policy(agent1, "immediate", status="completed")
        
        # Should be cleaned immediately
        remaining = cleaner.get_agent_resources(agent1)
        assert len(remaining) == 0
        
        # Test delayed cleanup
        agent2 = "delayed_cleanup_agent"
        cleaner.track_resource(agent2, "cache_file", {"path": "/tmp/cache.dat"})
        cleaner.apply_cleanup_policy(agent2, "delayed", status="completed")
        
        # Should still have resources
        remaining = cleaner.get_agent_resources(agent2)
        assert len(remaining) == 1
        
        # Check cleanup schedule
        scheduled = cleaner.get_scheduled_cleanups()
        assert any(s["agent_id"] == agent2 for s in scheduled)
        
        # Test error preservation
        agent3 = "error_agent"
        cleaner.track_resource(agent3, "debug_log", {"path": "/tmp/debug.log"})
        cleaner.apply_cleanup_policy(agent3, "delayed", status="failed")
        
        # Resources should be preserved on error
        remaining = cleaner.get_agent_resources(agent3)
        assert len(remaining) == 1
        assert remaining[0]["preserved_reason"] == "error_occurred"


class TestSubAgentMonitoring:
    """Test sub-agent monitoring and metrics (AC-SAM-019)."""
    
    @pytest.mark.xfail(reason="SubAgentMetricsCollector not implemented yet")
    def test_comprehensive_subagent_metrics(self):
        """Test collection of comprehensive sub-agent metrics."""
        if not SubAgentMetricsCollector:
            pytest.skip("SubAgentMetricsCollector infrastructure not implemented")
            
        # Infrastructure needed: Metrics collection for sub-agents
        collector = SubAgentMetricsCollector()
        
        # Configure metrics collection
        collector.configure({
            "collect_interval": 1,  # Every second
            "metrics": [
                "execution_time",
                "memory_usage",
                "cpu_usage",
                "message_count",
                "error_rate",
                "state_size"
            ],
            "aggregation": True
        })
        
        # Simulate sub-agent execution
        agents = ["agent_1", "agent_2", "agent_3"]
        
        for agent_id in agents:
            collector.start_collection(agent_id)
            
        # Simulate metrics over time
        for i in range(10):
            for j, agent_id in enumerate(agents):
                collector.record_metric(agent_id, "memory_usage", 
                                      20 + j * 10 + i * 2)  # Growing memory
                collector.record_metric(agent_id, "cpu_usage", 
                                      30 + (j * 15) % 40)  # Varying CPU
                collector.record_metric(agent_id, "message_count", i * 2)
                
                if agent_id == "agent_2" and i % 3 == 0:
                    collector.record_metric(agent_id, "error_count", 1)
                    
            time.sleep(0.1)
            
        # Get individual agent metrics
        agent1_metrics = collector.get_agent_metrics("agent_1")
        
        assert agent1_metrics["execution_time"] > 0
        assert agent1_metrics["avg_memory_usage"] > 20
        assert agent1_metrics["peak_memory_usage"] > agent1_metrics["avg_memory_usage"]
        assert agent1_metrics["total_messages"] == 18  # 9 iterations * 2
        assert agent1_metrics["error_rate"] == 0
        
        # Get aggregated metrics
        aggregated = collector.get_aggregated_metrics()
        
        assert aggregated["total_agents"] == 3
        assert aggregated["active_agents"] == 3
        assert aggregated["total_memory_usage"] > 60  # Sum of all agents
        assert aggregated["avg_cpu_usage"] > 0
        assert aggregated["total_errors"] > 0  # From agent_2
        
        # Test real-time monitoring
        realtime = collector.get_realtime_status()
        
        assert len(realtime["agents"]) == 3
        assert all(a["status"] == "active" for a in realtime["agents"].values())
        assert realtime["system_healthy"] == True
        
        # Test metric history
        history = collector.get_metric_history("agent_1", "memory_usage", 
                                              last_seconds=5)
        assert len(history) > 4  # At least 4 data points
        assert all(h["value"] > 0 for h in history)
        
    @pytest.mark.xfail(reason="Performance profiling not implemented yet")
    def test_subagent_performance_profiling(self):
        """Test performance profiling for sub-agents."""
        if not SubAgentMonitor:
            pytest.skip("Performance profiling not implemented")
            
        monitor = SubAgentMonitor()
        
        # Enable profiling
        monitor.enable_profiling({
            "profile_cpu": True,
            "profile_memory": True,
            "profile_io": True,
            "sampling_interval": 0.1
        })
        
        # Simulate sub-agent with performance characteristics
        agent_id = "performance_test_agent"
        
        with monitor.profile_agent(agent_id):
            # Simulate CPU-intensive work
            data = []
            for i in range(100000):
                data.append(i ** 2)
                
            # Simulate memory allocation
            large_data = [0] * 1000000
            
            # Simulate I/O
            mock_io = Mock()
            for i in range(100):
                mock_io.read(1024)
                mock_io.write(1024)
                
        # Get profiling results
        profile = monitor.get_agent_profile(agent_id)
        
        assert profile["cpu"]["total_time"] > 0
        assert profile["cpu"]["user_time"] > 0
        assert profile["cpu"]["system_time"] >= 0
        
        assert profile["memory"]["peak_usage"] > 1000000  # At least 1MB
        assert profile["memory"]["allocations"] > 0
        
        assert profile["io"]["read_ops"] == 100
        assert profile["io"]["write_ops"] == 100
        assert profile["io"]["total_bytes"] == 204800  # 100 * 2 * 1024
        
        # Get performance insights
        insights = monitor.analyze_performance(agent_id)
        
        assert "bottlenecks" in insights
        assert "optimization_suggestions" in insights
        
        if insights["bottlenecks"]:
            assert insights["bottlenecks"][0]["type"] in ["cpu", "memory", "io"]
            assert insights["bottlenecks"][0]["severity"] in ["low", "medium", "high"]
            
    @pytest.mark.xfail(reason="Monitoring dashboard not implemented yet")
    def test_subagent_monitoring_dashboard(self):
        """Test comprehensive monitoring dashboard for sub-agents."""
        if not SubAgentMonitor:
            pytest.skip("Monitoring dashboard not implemented")
            
        monitor = SubAgentMonitor()
        
        # Set up dashboard configuration
        monitor.configure_dashboard({
            "refresh_rate": 1,
            "show_metrics": ["status", "progress", "resources", "errors"],
            "alert_thresholds": {
                "memory_usage_percent": 80,
                "error_rate": 0.1,
                "execution_time": 300
            }
        })
        
        # Simulate multiple sub-agents
        parent_id = "dashboard_test_parent"
        agents_config = [
            {"id": "data_processor", "total_items": 1000},
            {"id": "validator", "total_items": 1000},
            {"id": "aggregator", "depends_on": ["data_processor", "validator"]}
        ]
        
        for config in agents_config:
            monitor.register_agent(parent_id, config["id"], config)
            
        # Simulate execution progress
        for i in range(100):
            # Data processor progress
            monitor.update_progress("data_processor", {
                "processed": i * 10,
                "total": 1000,
                "current_memory": 50 + i % 20,
                "errors": 0
            })
            
            # Validator progress (slower)
            monitor.update_progress("validator", {
                "processed": i * 8,
                "total": 1000,
                "current_memory": 60 + i % 30,
                "errors": i // 20  # Some errors
            })
            
            if i > 50:  # Aggregator starts later
                monitor.update_progress("aggregator", {
                    "processed": (i - 50) * 5,
                    "total": 500,
                    "current_memory": 40,
                    "errors": 0
                })
                
        # Get dashboard snapshot
        dashboard = monitor.get_dashboard(parent_id)
        
        assert len(dashboard["agents"]) == 3
        
        # Check data processor status
        dp_status = dashboard["agents"]["data_processor"]
        assert dp_status["progress_percent"] == 99
        assert dp_status["status"] == "running"
        assert dp_status["health"] == "healthy"
        
        # Check validator status (has errors)
        val_status = dashboard["agents"]["validator"]
        assert val_status["error_count"] > 0
        assert val_status["error_rate"] > 0
        assert val_status["health"] == "warning"  # Due to errors
        
        # Check dependencies
        agg_status = dashboard["agents"]["aggregator"]
        assert agg_status["waiting_for"] == []  # Dependencies started
        
        # Check alerts
        alerts = dashboard["active_alerts"]
        assert any(a["type"] == "error_rate" for a in alerts)  # Validator errors
        
        # Get summary statistics
        summary = dashboard["summary"]
        assert summary["total_agents"] == 3
        assert summary["healthy_agents"] < 3  # Validator has issues
        assert summary["overall_progress"] > 0
        assert summary["estimated_completion_time"] is not None


def create_test_workflow() -> WorkflowDefinition:
    """Helper to create test workflow definitions."""
    return WorkflowDefinition(
        name="test_subagent_workflow",
        description="Test workflow for sub-agent management",
        version="1.0.0",
        steps=[
            WorkflowStep(
                id="parallel_step",
                type="parallel_foreach",
                definition={
                    "items": "[1, 2, 3]",
                    "agent": {
                        "instructions": "Process item {{ item }}"
                    }
                }
            )
        ]
    )