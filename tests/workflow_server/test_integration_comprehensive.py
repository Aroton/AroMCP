"""
Comprehensive integration tests for workflow_server.

Tests cross-component integration, ensuring all components work together seamlessly
in realistic scenarios.
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from aromcp.workflow_server.debugging.debug_tools import DebugManager
from aromcp.workflow_server.errors.handlers import ErrorHandler
from aromcp.workflow_server.monitoring.metrics import MetricsCollector
from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as QueuedWorkflowExecutor
from aromcp.workflow_server.workflow.resource_manager import WorkflowResourceManager
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager
from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager

# Create aliases for compatibility
StepDefinition = WorkflowStep


class WorkflowStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TestCrossComponentIntegration:
    """Test integration between major workflow components."""

    @pytest.fixture
    def integrated_system(self):
        """Create a fully integrated workflow system."""
        # Initialize core components
        state_manager = StateManager()
        resource_manager = WorkflowResourceManager(max_workflows=5)
        performance_monitor = PerformanceMonitor()
        metrics_collector = MetricsCollector()
        error_handler = ErrorHandler()
        timeout_manager = TimeoutManager()
        debug_manager = DebugManager()
        subagent_manager = SubAgentManager()

        # Create executor with all components
        executor = QueuedWorkflowExecutor(
            state_manager=state_manager,
            resource_manager=resource_manager,
            performance_monitor=performance_monitor,
            error_handler=error_handler,
            timeout_manager=timeout_manager,
            debug_manager=debug_manager,
            subagent_manager=subagent_manager,
        )

        return {
            "executor": executor,
            "state_manager": state_manager,
            "resource_manager": resource_manager,
            "performance_monitor": performance_monitor,
            "metrics_collector": metrics_collector,
            "error_handler": error_handler,
            "timeout_manager": timeout_manager,
            "debug_manager": debug_manager,
            "subagent_manager": subagent_manager,
        }

    @pytest.mark.asyncio
    async def test_complete_workflow_lifecycle_with_all_features(self, integrated_system):
        """Test a workflow using all major features."""
        executor = integrated_system["executor"]

        # Complex workflow with all features
        workflow_def = WorkflowDefinition(
            name="complete_integration_test",
            description="Integration test workflow",
            version="1.0",
            default_state={"state": {}},
            state_schema=StateSchema(state={}, computed={}, inputs={}),
            inputs={
                "items": {"type": "array", "description": "Items to process", "required": True},
                "batch_size": {"type": "integer", "description": "Batch size", "default": 10},
            },
            steps=[
                # Parallel batch processing
                WorkflowStep(
                    id="batch_process",
                    type="foreach",
                    definition={
                        "items": "{{ inputs.items }}",
                        "parallel": True,
                        "max_concurrent": 3,
                        "steps": [
                            {
                                "id": "process_item",
                                "type": "agent_prompt",
                                "config": {"prompt": "Process item: {{ item }}", "timeout": 30},
                            }
                        ],
                    },
                ),
                # Conditional aggregation
                StepDefinition(
                    id="check_results",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ state.batch_process.success_count > 0 }}",
                                "then": [
                                    {
                                        "id": "aggregate_results",
                                        "type": "state_update",
                                        "config": {
                                            "updates": {
                                                "summary": "Processed {{ state.batch_process.success_count }} items"
                                            }
                                        },
                                    }
                                ],
                            }
                        ],
                        "else": [
                            {
                                "id": "handle_no_results",
                                "type": "agent_prompt",
                                "config": {"prompt": "No items processed successfully"},
                            }
                        ],
                    },
                ),
                # Sub-agent delegation
                StepDefinition(
                    id="delegate_to_subagent",
                    type="agent_prompt",
                    config={
                        "prompt": "Analyze results: {{ state.summary }}",
                        "sub_agent": {"id": "analyzer", "capabilities": ["analysis", "reporting"]},
                    },
                ),
            ],
        )

        # Start workflow with monitoring
        start_time = time.time()
        inputs = {"items": ["item1", "item2", "item3", "item4", "item5"], "batch_size": 2}

        result = await executor.start_workflow(workflow_def, inputs)
        workflow_id = result["workflow_id"]

        # Verify initial state
        assert result["status"] == WorkflowStatus.PENDING.value
        assert integrated_system["resource_manager"].get_active_workflow_count() == 1

        # Simulate execution with monitoring
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = {"content": "Processed"}

        with patch("src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client", return_value=mock_mcp):
            # Execute workflow
            await executor.execute_next()

            # Check performance metrics during execution
            metrics = integrated_system["performance_monitor"].get_metrics(workflow_id)
            assert "execution_start" in metrics
            assert metrics["step_count"] > 0

            # Verify parallel execution
            active_steps = integrated_system["state_manager"].get_active_steps(workflow_id)
            assert len(active_steps) <= 3  # max_concurrent limit

            # Complete execution
            while executor.has_pending_workflows():
                await executor.execute_next()
                await asyncio.sleep(0.1)

        # Verify final state
        final_state = integrated_system["state_manager"].get_workflow_state(workflow_id)
        assert final_state["status"] == WorkflowStatus.COMPLETED.value

        # Check monitoring data
        final_metrics = integrated_system["performance_monitor"].get_metrics(workflow_id)
        assert final_metrics["total_duration"] > 0
        assert final_metrics["step_count"] > 5  # Multiple steps executed

        # Verify resource cleanup
        assert integrated_system["resource_manager"].get_active_workflow_count() == 0

        # Check error tracking (should be none)
        errors = integrated_system["error_handler"].get_workflow_errors(workflow_id)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_cross_component_error_propagation(self, integrated_system):
        """Test error propagation across components."""
        executor = integrated_system["executor"]

        # Workflow that will fail
        workflow_def = WorkflowDefinition(
            name="error_propagation_test",
            version="1.0",
            steps=[
                StepDefinition(
                    id="failing_step",
                    type="shell_command",
                    config={"command": "exit 1", "error_handling": {"strategy": "fail"}},
                ),
                StepDefinition(
                    id="should_not_execute", type="agent_prompt", config={"prompt": "This should not execute"}
                ),
            ],
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Execute and handle error
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Command failed"

            await executor.execute_next()

        # Verify error handling across components
        workflow_state = integrated_system["state_manager"].get_workflow_state(workflow_id)
        assert workflow_state["status"] == WorkflowStatus.FAILED.value

        # Check error tracking
        errors = integrated_system["error_handler"].get_workflow_errors(workflow_id)
        assert len(errors) == 1
        assert errors[0]["step_id"] == "failing_step"
        assert "Command failed" in str(errors[0]["error"])

        # Verify second step didn't execute
        step_states = workflow_state["step_states"]
        assert "should_not_execute" not in step_states

        # Check monitoring captured the error
        metrics = integrated_system["performance_monitor"].get_metrics(workflow_id)
        assert metrics.get("error_count", 0) > 0

        # Verify resources were cleaned up
        assert integrated_system["resource_manager"].get_active_workflow_count() == 0

    @pytest.mark.asyncio
    async def test_resource_management_under_concurrent_load(self, integrated_system):
        """Test resource management with concurrent workflows."""
        executor = integrated_system["executor"]
        max_concurrent = 5

        # Simple workflow definition
        workflow_def = WorkflowDefinition(
            name="concurrent_test",
            version="1.0",
            steps=[
                StepDefinition(id="wait_step", type="wait", config={"duration": 0.5}),
                StepDefinition(
                    id="complete_step", type="state_update", config={"updates": {"completed_at": "{{ now() }}"}}
                ),
            ],
        )

        # Start more workflows than allowed concurrent
        workflow_ids = []
        for i in range(max_concurrent + 3):
            result = await executor.start_workflow(workflow_def, {"workflow_num": i})
            workflow_ids.append(result["workflow_id"])

        # Check resource limits
        assert integrated_system["resource_manager"].get_active_workflow_count() <= max_concurrent
        assert integrated_system["resource_manager"].get_queued_workflow_count() == 3

        # Execute all workflows
        execution_count = 0
        while executor.has_pending_workflows():
            await executor.execute_next()
            execution_count += 1

            # Verify concurrent limit maintained
            active = integrated_system["resource_manager"].get_active_workflow_count()
            assert active <= max_concurrent

            await asyncio.sleep(0.1)

        # Verify all completed
        for workflow_id in workflow_ids:
            state = integrated_system["state_manager"].get_workflow_state(workflow_id)
            assert state["status"] == WorkflowStatus.COMPLETED.value

        # Check final resource state
        assert integrated_system["resource_manager"].get_active_workflow_count() == 0
        assert integrated_system["resource_manager"].get_queued_workflow_count() == 0

    @pytest.mark.asyncio
    async def test_monitoring_and_debugging_integration(self, integrated_system):
        """Test monitoring and debugging features working together."""
        executor = integrated_system["executor"]
        debug_manager = integrated_system["debug_manager"]

        # Enable debug mode
        debug_manager.enable_debug_mode()

        # Workflow with debug points
        workflow_def = WorkflowDefinition(
            name="debug_monitoring_test",
            version="1.0",
            metadata={"debug": True},
            steps=[
                StepDefinition(
                    id="step1",
                    type="state_update",
                    config={"updates": {"counter": 0}, "debug": {"breakpoint": True, "log_level": "DEBUG"}},
                ),
                StepDefinition(
                    id="step2",
                    type="while",
                    config={
                        "condition": "{{ state.counter < 3 }}",
                        "steps": [
                            {
                                "id": "increment",
                                "type": "state_update",
                                "config": {
                                    "updates": {"counter": "{{ state.counter + 1 }}"},
                                    "debug": {"watch": ["counter"]},
                                },
                            }
                        ],
                    },
                ),
                StepDefinition(id="step3", type="agent_prompt", config={"prompt": "Final count: {{ state.counter }}"}),
            ],
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Execute with debug monitoring
        execution_log = []

        def debug_callback(event):
            execution_log.append(event)

        debug_manager.register_callback(debug_callback)

        # Execute step by step
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = {"content": "Completed"}

        with patch("src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client", return_value=mock_mcp):
            while executor.has_pending_workflows():
                await executor.execute_next()

                # Check debug state
                debug_state = debug_manager.get_debug_state(workflow_id)
                if debug_state and debug_state.get("breakpoint_hit"):
                    # Simulate debugger interaction
                    await debug_manager.resume_workflow(workflow_id)

        # Verify monitoring data collected
        metrics = integrated_system["performance_monitor"].get_metrics(workflow_id)
        assert metrics["step_count"] >= 6  # Initial steps + 3 loop iterations
        assert "step_timings" in metrics

        # Check debug log
        assert len(execution_log) > 0
        breakpoint_events = [e for e in execution_log if e.get("type") == "breakpoint"]
        assert len(breakpoint_events) > 0

        # Verify watched variables
        watch_events = [e for e in execution_log if e.get("type") == "watch"]
        counter_values = [e.get("value") for e in watch_events if e.get("variable") == "counter"]
        assert counter_values == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_state_management_with_concurrent_operations(self, integrated_system):
        """Test state management under concurrent access."""
        executor = integrated_system["executor"]
        state_manager = integrated_system["state_manager"]

        # Workflow with concurrent state updates
        workflow_def = WorkflowDefinition(
            name="concurrent_state_test",
            version="1.0",
            steps=[
                StepDefinition(
                    id="init_state", type="state_update", config={"updates": {"shared_counter": 0, "results": []}}
                ),
                StepDefinition(
                    id="parallel_updates",
                    type="foreach",
                    config={
                        "items": "[1, 2, 3, 4, 5]",
                        "parallel": True,
                        "steps": [
                            {
                                "id": "update_counter",
                                "type": "state_update",
                                "config": {
                                    "updates": {
                                        "shared_counter": "{{ state.shared_counter + item }}",
                                        "results": "{{ state.results + [item] }}",
                                    }
                                },
                            }
                        ],
                    },
                ),
            ],
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Execute workflow
        while executor.has_pending_workflows():
            await executor.execute_next()
            await asyncio.sleep(0.05)

        # Verify final state consistency
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state["status"] == WorkflowStatus.COMPLETED.value

        # Check state updates
        workflow_state = final_state["state"]
        assert workflow_state["shared_counter"] == 15  # 1+2+3+4+5
        assert len(workflow_state["results"]) == 5
        assert set(workflow_state["results"]) == {1, 2, 3, 4, 5}

    @pytest.mark.asyncio
    async def test_subagent_coordination_with_parent_workflow(self, integrated_system):
        """Test sub-agent management integration."""
        executor = integrated_system["executor"]
        subagent_manager = integrated_system["subagent_manager"]

        # Parent workflow with sub-agent delegation
        workflow_def = WorkflowDefinition(
            name="parent_workflow",
            version="1.0",
            steps=[
                StepDefinition(
                    id="prepare_data", type="state_update", config={"updates": {"data": ["task1", "task2", "task3"]}}
                ),
                StepDefinition(
                    id="delegate_tasks",
                    type="foreach",
                    config={
                        "items": "{{ state.data }}",
                        "steps": [
                            {
                                "id": "process_task",
                                "type": "agent_prompt",
                                "config": {
                                    "prompt": "Process {{ item }}",
                                    "sub_agent": {
                                        "id": "worker_{{ loop.index }}",
                                        "capabilities": ["processing"],
                                        "resource_limits": {"max_tokens": 1000, "timeout": 60},
                                    },
                                },
                            }
                        ],
                    },
                ),
                StepDefinition(id="aggregate_results", type="agent_prompt", config={"prompt": "Summarize all results"}),
            ],
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Mock sub-agent responses
        mock_mcp = AsyncMock()
        responses = ["Task 1 complete", "Task 2 complete", "Task 3 complete", "All tasks summarized"]
        mock_mcp.call_tool.side_effect = [{"content": resp} for resp in responses]

        with patch("src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client", return_value=mock_mcp):
            # Execute workflow
            while executor.has_pending_workflows():
                await executor.execute_next()

                # Check sub-agent allocations
                active_agents = subagent_manager.get_active_subagents(workflow_id)
                assert len(active_agents) <= 3

                await asyncio.sleep(0.05)

        # Verify completion
        final_state = integrated_system["state_manager"].get_workflow_state(workflow_id)
        assert final_state["status"] == WorkflowStatus.COMPLETED.value

        # Check sub-agent cleanup
        active_agents = subagent_manager.get_active_subagents(workflow_id)
        assert len(active_agents) == 0

        # Verify sub-agent metrics
        metrics = integrated_system["performance_monitor"].get_metrics(workflow_id)
        assert "subagent_count" in metrics
        assert metrics["subagent_count"] == 3


class TestComponentFailureRecovery:
    """Test system behavior when individual components fail."""

    @pytest.fixture
    def fault_tolerant_system(self):
        """Create system with fault tolerance features."""
        state_manager = StateManager()
        resource_manager = WorkflowResourceManager(max_workflows=3, enable_circuit_breaker=True, failure_threshold=3)
        error_handler = ErrorHandler(max_retries=2)
        timeout_manager = TimeoutManager(default_timeout=30)

        executor = QueuedWorkflowExecutor(
            state_manager=state_manager,
            resource_manager=resource_manager,
            error_handler=error_handler,
            timeout_manager=timeout_manager,
        )

        return {
            "executor": executor,
            "state_manager": state_manager,
            "resource_manager": resource_manager,
            "error_handler": error_handler,
            "timeout_manager": timeout_manager,
        }

    @pytest.mark.asyncio
    async def test_state_manager_failure_recovery(self, fault_tolerant_system):
        """Test recovery when state manager has issues."""
        executor = fault_tolerant_system["executor"]
        state_manager = fault_tolerant_system["state_manager"]

        workflow_def = WorkflowDefinition(
            name="state_failure_test",
            version="1.0",
            steps=[StepDefinition(id="step1", type="state_update", config={"updates": {"value": "test"}})],
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Simulate state manager failure
        original_update = state_manager.update_step_state
        call_count = 0

        def failing_update(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("State manager temporary failure")
            return original_update(*args, **kwargs)

        state_manager.update_step_state = failing_update

        # Execute with retry
        await executor.execute_next()

        # Verify recovery
        final_state = state_manager.get_workflow_state(workflow_id)
        assert final_state["status"] == WorkflowStatus.COMPLETED.value
        assert call_count == 2  # Failed once, succeeded on retry

    @pytest.mark.asyncio
    async def test_resource_manager_circuit_breaker(self, fault_tolerant_system):
        """Test circuit breaker activation on repeated failures."""
        executor = fault_tolerant_system["executor"]
        resource_manager = fault_tolerant_system["resource_manager"]

        # Workflow that always fails
        failing_workflow = WorkflowDefinition(
            name="failing_workflow",
            version="1.0",
            steps=[StepDefinition(id="fail_step", type="shell_command", config={"command": "exit 1"})],
        )

        # Start multiple failing workflows
        workflow_ids = []
        for i in range(4):
            result = await executor.start_workflow(failing_workflow, {})
            workflow_ids.append(result["workflow_id"])

        # Execute failures
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            for _ in range(3):
                if executor.has_pending_workflows():
                    await executor.execute_next()

        # Circuit breaker should be open after 3 failures
        assert resource_manager.is_circuit_breaker_open()

        # New workflows should be rejected
        with pytest.raises(Exception, match="Circuit breaker"):
            await executor.start_workflow(failing_workflow, {})

        # Wait for circuit breaker reset
        await asyncio.sleep(1)

        # Should allow new workflows after reset
        resource_manager.reset_circuit_breaker()
        result = await executor.start_workflow(failing_workflow, {})
        assert result["status"] == WorkflowStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_timeout_manager_enforcement(self, fault_tolerant_system):
        """Test timeout enforcement across components."""
        executor = fault_tolerant_system["executor"]
        timeout_manager = fault_tolerant_system["timeout_manager"]

        # Workflow with short timeout
        workflow_def = WorkflowDefinition(
            name="timeout_test",
            version="1.0",
            metadata={"timeout": 1},  # 1 second timeout
            steps=[StepDefinition(id="long_running_step", type="wait", config={"duration": 5})],  # Will timeout
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Start execution
        start_time = time.time()

        # Execute with timeout monitoring
        while executor.has_pending_workflows() and time.time() - start_time < 2:
            await executor.execute_next()
            await asyncio.sleep(0.1)

        # Verify timeout occurred
        final_state = fault_tolerant_system["state_manager"].get_workflow_state(workflow_id)
        assert final_state["status"] == WorkflowStatus.FAILED.value

        # Check timeout was enforced
        errors = fault_tolerant_system["error_handler"].get_workflow_errors(workflow_id)
        assert any("timeout" in str(e.get("error", "")).lower() for e in errors)


class TestMonitoringIntegration:
    """Test monitoring and observability features."""

    @pytest.fixture
    def monitored_system(self):
        """Create system with comprehensive monitoring."""
        from aromcp.workflow_server.monitoring.observability import ObservabilityManager

        state_manager = StateManager()
        performance_monitor = PerformanceMonitor()
        metrics_collector = MetricsCollector()
        observability = ObservabilityManager()

        executor = QueuedWorkflowExecutor(
            state_manager=state_manager, performance_monitor=performance_monitor, observability_manager=observability
        )

        return {
            "executor": executor,
            "performance_monitor": performance_monitor,
            "metrics_collector": metrics_collector,
            "observability": observability,
        }

    @pytest.mark.asyncio
    async def test_comprehensive_metrics_collection(self, monitored_system):
        """Test all metrics are collected properly."""
        executor = monitored_system["executor"]
        performance_monitor = monitored_system["performance_monitor"]

        workflow_def = WorkflowDefinition(
            name="metrics_test",
            version="1.0",
            steps=[
                StepDefinition(id="cpu_intensive", type="shell_command", config={"command": "echo 'Processing'"}),
                StepDefinition(
                    id="memory_intensive",
                    type="state_update",
                    config={"updates": {"large_data": "[" + ",".join([f'"{i}"' for i in range(1000)]) + "]"}},
                ),
                StepDefinition(
                    id="io_intensive", type="agent_prompt", config={"prompt": "Analyze {{ state.large_data }}"}
                ),
            ],
        )

        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result["workflow_id"]

        # Execute with monitoring
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = {"content": "Analysis complete"}

        with patch("src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client", return_value=mock_mcp):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "Processing"

                while executor.has_pending_workflows():
                    await executor.execute_next()

        # Verify comprehensive metrics
        metrics = performance_monitor.get_metrics(workflow_id)

        # Timing metrics
        assert "execution_start" in metrics
        assert "execution_end" in metrics
        assert "total_duration" in metrics
        assert metrics["total_duration"] > 0

        # Step metrics
        assert "step_count" in metrics
        assert metrics["step_count"] == 3
        assert "step_timings" in metrics
        assert len(metrics["step_timings"]) == 3

        # Resource metrics
        assert "peak_memory" in metrics
        assert "cpu_usage" in metrics

        # Check individual step metrics
        for step_id in ["cpu_intensive", "memory_intensive", "io_intensive"]:
            step_metrics = next((s for s in metrics["step_timings"] if s["step_id"] == step_id), None)
            assert step_metrics is not None
            assert "duration" in step_metrics
            assert step_metrics["duration"] >= 0

    @pytest.mark.asyncio
    async def test_monitoring_data_export(self, monitored_system):
        """Test monitoring data can be exported."""
        executor = monitored_system["executor"]
        observability = monitored_system["observability"]

        # Execute multiple workflows
        workflow_ids = []
        for i in range(3):
            workflow_def = WorkflowDefinition(
                name=f"export_test_{i}",
                version="1.0",
                steps=[StepDefinition(id="simple_step", type="state_update", config={"updates": {"index": i}})],
            )

            result = await executor.start_workflow(workflow_def, {})
            workflow_ids.append(result["workflow_id"])

        # Execute all workflows
        while executor.has_pending_workflows():
            await executor.execute_next()

        # Export monitoring data
        export_data = observability.export_metrics(workflow_ids=workflow_ids, format="json")

        assert "workflows" in export_data
        assert len(export_data["workflows"]) == 3

        # Verify each workflow data
        for workflow_data in export_data["workflows"]:
            assert "workflow_id" in workflow_data
            assert "metrics" in workflow_data
            assert "status" in workflow_data
            assert workflow_data["status"] == WorkflowStatus.COMPLETED.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
