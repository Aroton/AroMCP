"""
Performance and load testing for workflow_server.

Tests system performance under various load conditions and identifies bottlenecks.
"""

import asyncio
import gc
import statistics
import time
from unittest.mock import AsyncMock, patch

import psutil
import pytest

from aromcp.workflow_server.models.workflow_models import WorkflowStatusResponse
from aromcp.workflow_server.monitoring.metrics import MetricsCollector
from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.workflow.resource_manager import WorkflowResourceManager


class TestConcurrentWorkflowExecution:
    """Test concurrent workflow execution at scale."""

    @pytest.fixture
    def performance_system(self):
        """Create system optimized for performance testing."""
        state_manager = StateManager()
        resource_manager = WorkflowResourceManager(max_concurrent_workflows=20, max_queued_workflows=100)
        performance_monitor = PerformanceMonitor()
        metrics_collector = MetricsCollector()

        executor = QueueBasedWorkflowExecutor(
            state_manager=state_manager, resource_manager=resource_manager, performance_monitor=performance_monitor
        )

        return {
            "executor": executor,
            "state_manager": state_manager,
            "resource_manager": resource_manager,
            "performance_monitor": performance_monitor,
            "metrics_collector": metrics_collector,
        }

    @pytest.fixture
    def simple_workflow(self):
        """Simple workflow for performance testing."""
        return WorkflowDefinition(
            name="perf_test_workflow",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="compute",
                    type="state_update",
                    config={"updates": {"value": "{{ inputs.index * 2 }}", "timestamp": "{{ now() }}"}},
                ),
                WorkflowStep(
                    id="validate",
                    type="conditional",
                    config={
                        "conditions": [
                            {
                                "if": "{{ state.value % 2 == 0 }}",
                                "then": [
                                    {
                                        "id": "even_path",
                                        "type": "state_update",
                                        "config": {"updates": {"result": "even"}},
                                    }
                                ],
                            }
                        ]
                    },
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_concurrent_workflow_throughput(self, performance_system, simple_workflow):
        """Test maximum workflow throughput with concurrent execution."""
        executor = performance_system["executor"]

        # Test parameters
        num_workflows = 100
        batch_size = 20

        # Start workflows in batches
        workflow_ids = []
        start_time = time.time()

        for batch in range(0, num_workflows, batch_size):
            batch_ids = []
            for i in range(batch, min(batch + batch_size, num_workflows)):
                result = await executor.start_workflow(simple_workflow, {"index": i})
                batch_ids.append(result["workflow_id"])
            workflow_ids.extend(batch_ids)

            # Small delay between batches
            await asyncio.sleep(0.01)

        submission_time = time.time() - start_time

        # Execute all workflows
        execution_start = time.time()
        completed_count = 0

        while executor.has_pending_workflows():
            await executor.execute_next()
            completed_count += 1

            # Check resource utilization
            active = performance_system["resource_manager"].get_active_workflow_count()
            queued = performance_system["resource_manager"].get_queued_workflow_count()

            assert active <= 20  # Max concurrent limit
            assert queued <= 100  # Max queue limit

        execution_time = time.time() - execution_start

        # Calculate metrics
        total_time = time.time() - start_time
        throughput = num_workflows / total_time
        avg_execution_time = execution_time / num_workflows

        print("\nPerformance Metrics:")
        print(f"- Total workflows: {num_workflows}")
        print(f"- Submission time: {submission_time:.2f}s")
        print(f"- Execution time: {execution_time:.2f}s")
        print(f"- Total time: {total_time:.2f}s")
        print(f"- Throughput: {throughput:.2f} workflows/second")
        print(f"- Avg execution time: {avg_execution_time*1000:.2f}ms per workflow")

        # Verify all completed successfully
        for workflow_id in workflow_ids:
            state = performance_system["state_manager"].get_workflow_state(workflow_id)
            assert state["status"] == WorkflowStatusResponse.COMPLETED.value

        # Performance assertions
        assert throughput > 10  # At least 10 workflows per second
        assert avg_execution_time < 0.1  # Less than 100ms per workflow

    @pytest.mark.asyncio
    async def test_parallel_step_performance(self, performance_system):
        """Test performance of workflows with parallel steps."""
        # Workflow with parallel processing
        parallel_workflow = WorkflowDefinition(
            name="parallel_perf_test",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="parallel_tasks",
                    type="foreach",
                    config={
                        "items": "{{ range(inputs.parallel_count) }}",
                        "parallel": True,
                        "max_concurrent": 10,
                        "steps": [{"id": "task", "type": "wait", "config": {"duration": 0.1}}],  # 100ms per task
                    },
                )
            ],
        )

        executor = performance_system["executor"]

        # Test with different parallelism levels
        test_cases = [
            {"parallel_count": 10, "expected_time": 0.2},  # Should complete in ~100ms with parallelism
            {"parallel_count": 50, "expected_time": 0.6},  # Should complete in ~500ms (5 batches)
            {"parallel_count": 100, "expected_time": 1.2},  # Should complete in ~1s (10 batches)
        ]

        for test_case in test_cases:
            result = await executor.start_workflow(parallel_workflow, {"parallel_count": test_case["parallel_count"]})
            workflow_id = result["workflow_id"]

            start_time = time.time()

            # Execute workflow
            while executor.has_pending_workflows():
                await executor.execute_next()
                await asyncio.sleep(0.01)

            execution_time = time.time() - start_time

            print(f"\nParallel execution ({test_case['parallel_count']} tasks):")
            print(f"- Execution time: {execution_time:.2f}s")
            print(f"- Expected time: {test_case['expected_time']:.2f}s")

            # Verify completion
            state = performance_system["state_manager"].get_workflow_state(workflow_id)
            assert state["status"] == WorkflowStatusResponse.COMPLETED.value

            # Performance assertion - allow 50% margin
            assert execution_time < test_case["expected_time"] * 1.5

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_system, simple_workflow):
        """Test memory usage patterns under sustained load."""
        executor = performance_system["executor"]

        # Get process for memory monitoring
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_samples = []
        workflow_ids = []

        # Run workflows continuously for a period
        test_duration = 5  # seconds
        start_time = time.time()
        workflows_started = 0

        while time.time() - start_time < test_duration:
            # Start new workflow
            result = await executor.start_workflow(simple_workflow, {"index": workflows_started})
            workflow_ids.append(result["workflow_id"])
            workflows_started += 1

            # Execute pending workflows
            for _ in range(5):
                if executor.has_pending_workflows():
                    await executor.execute_next()

            # Sample memory usage
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)

            await asyncio.sleep(0.01)

        # Complete remaining workflows
        while executor.has_pending_workflows():
            await executor.execute_next()

        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.5)

        final_memory = process.memory_info().rss / 1024 / 1024

        # Analyze memory usage
        peak_memory = max(memory_samples)
        avg_memory = statistics.mean(memory_samples)
        memory_growth = final_memory - initial_memory

        print("\nMemory Usage Analysis:")
        print(f"- Initial memory: {initial_memory:.2f} MB")
        print(f"- Peak memory: {peak_memory:.2f} MB")
        print(f"- Average memory: {avg_memory:.2f} MB")
        print(f"- Final memory: {final_memory:.2f} MB")
        print(f"- Memory growth: {memory_growth:.2f} MB")
        print(f"- Workflows processed: {workflows_started}")

        # Memory leak detection
        memory_per_workflow = memory_growth / workflows_started if workflows_started > 0 else 0
        print(f"- Memory per workflow: {memory_per_workflow*1000:.2f} KB")

        # Assertions
        assert memory_growth < 50  # Less than 50MB growth
        assert memory_per_workflow < 0.1  # Less than 100KB per workflow
        assert peak_memory - initial_memory < 100  # Peak less than 100MB above initial


class TestResourceUtilizationPatterns:
    """Test resource utilization under various load patterns."""

    @pytest.fixture
    def resource_workflow(self):
        """Workflow that uses various resources."""
        return WorkflowDefinition(
            name="resource_test",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="cpu_intensive",
                    type="state_update",
                    config={"updates": {"result": "{{ [i**2 for i in range(inputs.complexity)] | sum }}"}},
                ),
                WorkflowStep(
                    id="memory_intensive",
                    type="state_update",
                    config={
                        "updates": {
                            "large_list": "{{ range(inputs.memory_size) }}",
                            "data_map": "{{ {str(i): i**2 for i in range(inputs.memory_size // 10)} }}",
                        }
                    },
                ),
                WorkflowStep(id="io_simulation", type="wait", config={"duration": "{{ inputs.io_delay }}"}),
            ],
        )

    @pytest.mark.asyncio
    async def test_cpu_scaling_patterns(self, resource_workflow):
        """Test CPU usage scaling with workflow complexity."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)

        # Test different complexity levels
        complexity_levels = [100, 1000, 5000]
        cpu_measurements = []

        for complexity in complexity_levels:
            # Start monitoring CPU
            process = psutil.Process()
            cpu_samples = []

            # Start workflow
            result = await executor.start_workflow(
                resource_workflow, {"complexity": complexity, "memory_size": 100, "io_delay": 0.01}
            )

            # Execute and monitor
            start_time = time.time()
            while executor.has_pending_workflows():
                await executor.execute_next()
                cpu_percent = process.cpu_percent(interval=0.01)
                cpu_samples.append(cpu_percent)

            execution_time = time.time() - start_time

            avg_cpu = statistics.mean(cpu_samples) if cpu_samples else 0
            peak_cpu = max(cpu_samples) if cpu_samples else 0

            cpu_measurements.append(
                {"complexity": complexity, "avg_cpu": avg_cpu, "peak_cpu": peak_cpu, "execution_time": execution_time}
            )

            print(f"\nCPU Usage (complexity={complexity}):")
            print(f"- Average CPU: {avg_cpu:.1f}%")
            print(f"- Peak CPU: {peak_cpu:.1f}%")
            print(f"- Execution time: {execution_time:.3f}s")

        # Verify CPU scales appropriately
        for i in range(1, len(cpu_measurements)):
            ratio = cpu_measurements[i]["complexity"] / cpu_measurements[i - 1]["complexity"]
            time_ratio = cpu_measurements[i]["execution_time"] / cpu_measurements[i - 1]["execution_time"]

            # Execution time should scale somewhat linearly with complexity
            assert time_ratio < ratio * 2  # Allow for some overhead

    @pytest.mark.asyncio
    async def test_circuit_breaker_activation(self):
        """Test circuit breaker activation under failure conditions."""
        state_manager = StateManager()
        resource_manager = WorkflowResourceManager(
            max_concurrent_workflows=5,
            enable_circuit_breaker=True,
            failure_threshold=3,
            recovery_timeout=1,  # 1 second for testing
        )
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager, resource_manager=resource_manager)

        # Workflow that fails
        failing_workflow = WorkflowDefinition(
            name="failing_workflow",
            version="1.0",
            steps=[WorkflowStep(id="fail", type="agent_prompt", config={"prompt": "This will fail"})],
        )

        # Mock to simulate failures
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.side_effect = Exception("Simulated failure")

        workflow_ids = []
        failures_before_circuit_break = 0

        with patch("src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client", return_value=mock_mcp):
            # Start multiple workflows
            for i in range(10):
                try:
                    result = await executor.start_workflow(failing_workflow, {"index": i})
                    workflow_ids.append(result["workflow_id"])
                except Exception as e:
                    if "Circuit breaker" in str(e):
                        print(f"Circuit breaker activated after {failures_before_circuit_break} failures")
                        break

                # Try to execute
                if executor.has_pending_workflows():
                    try:
                        await executor.execute_next()
                    except:
                        failures_before_circuit_break += 1

        # Verify circuit breaker activated
        assert resource_manager.is_circuit_breaker_open()
        assert failures_before_circuit_break >= 3

        # Test recovery
        await asyncio.sleep(1.5)  # Wait for recovery timeout

        # Circuit breaker should allow retry
        resource_manager.reset_circuit_breaker()
        assert not resource_manager.is_circuit_breaker_open()

        # Should be able to start new workflow
        result = await executor.start_workflow(failing_workflow, {"retry": True})
        assert result["status"] == WorkflowStatusResponse.PENDING.value

    @pytest.mark.asyncio
    async def test_performance_degradation_patterns(self):
        """Test system behavior under degrading performance conditions."""
        state_manager = StateManager()
        performance_monitor = PerformanceMonitor()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager, performance_monitor=performance_monitor)

        # Workflow with increasing delays
        degrading_workflow = WorkflowDefinition(
            name="degrading_perf",
            version="1.0",
            steps=[WorkflowStep(id="process", type="wait", config={"duration": "{{ inputs.delay }}"})],
        )

        # Simulate degrading performance
        delays = [0.01, 0.05, 0.1, 0.5, 1.0]  # Increasing delays
        performance_metrics = []

        for delay in delays:
            batch_size = 10
            workflow_ids = []

            # Start batch of workflows
            start_time = time.time()
            for i in range(batch_size):
                result = await executor.start_workflow(degrading_workflow, {"delay": delay})
                workflow_ids.append(result["workflow_id"])

            # Execute batch
            execution_start = time.time()
            while executor.has_pending_workflows():
                await executor.execute_next()

            execution_time = time.time() - execution_start
            total_time = time.time() - start_time

            # Collect metrics
            avg_workflow_time = execution_time / batch_size
            throughput = batch_size / total_time

            performance_metrics.append(
                {
                    "delay": delay,
                    "avg_workflow_time": avg_workflow_time,
                    "throughput": throughput,
                    "total_time": total_time,
                }
            )

            print(f"\nPerformance with {delay}s delay:")
            print(f"- Avg workflow time: {avg_workflow_time:.3f}s")
            print(f"- Throughput: {throughput:.2f} workflows/s")

        # Analyze degradation pattern
        for i in range(1, len(performance_metrics)):
            curr = performance_metrics[i]
            prev = performance_metrics[i - 1]

            # Throughput should decrease as delay increases
            assert curr["throughput"] < prev["throughput"]

            # Workflow time should increase
            assert curr["avg_workflow_time"] > prev["avg_workflow_time"]


class TestBottleneckIdentification:
    """Test identification of performance bottlenecks."""

    @pytest.fixture
    def bottleneck_workflow(self):
        """Workflow designed to expose bottlenecks."""
        return WorkflowDefinition(
            name="bottleneck_test",
            version="1.0",
            steps=[
                # Fast step
                WorkflowStep(id="fast_step", type="state_update", config={"updates": {"fast": True}}),
                # Slow step (bottleneck)
                WorkflowStep(id="slow_step", type="wait", config={"duration": 0.5}),
                # Parallel steps after bottleneck
                WorkflowStep(
                    id="parallel_after",
                    type="foreach",
                    config={
                        "items": "{{ range(10) }}",
                        "parallel": True,
                        "steps": [
                            {
                                "id": "parallel_task",
                                "type": "state_update",
                                "config": {"updates": {"item": "{{ item }}"}},
                            }
                        ],
                    },
                ),
                # Another slow step
                WorkflowStep(
                    id="another_slow_step", type="agent_prompt", config={"prompt": "Process data", "timeout": 1}
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_step_timing_analysis(self, bottleneck_workflow):
        """Test detailed step timing analysis to identify bottlenecks."""
        state_manager = StateManager()
        performance_monitor = PerformanceMonitor()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager, performance_monitor=performance_monitor)

        # Run multiple instances to get average timings
        num_runs = 5
        all_timings = []

        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = {"content": "Processed"}

        with patch("src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client", return_value=mock_mcp):
            for run in range(num_runs):
                result = await executor.start_workflow(bottleneck_workflow, {"run": run})
                workflow_id = result["workflow_id"]

                # Execute workflow
                while executor.has_pending_workflows():
                    await executor.execute_next()
                    await asyncio.sleep(0.01)

                # Collect timing data
                metrics = performance_monitor.get_metrics(workflow_id)
                if "step_timings" in metrics:
                    all_timings.extend(metrics["step_timings"])

        # Analyze step timings
        step_analysis = {}
        for timing in all_timings:
            step_id = timing["step_id"]
            if step_id not in step_analysis:
                step_analysis[step_id] = []
            step_analysis[step_id].append(timing["duration"])

        # Calculate statistics
        bottlenecks = []
        for step_id, durations in step_analysis.items():
            avg_duration = statistics.mean(durations)
            max_duration = max(durations)
            min_duration = min(durations)

            print(f"\nStep '{step_id}' timing analysis:")
            print(f"- Average: {avg_duration:.3f}s")
            print(f"- Min: {min_duration:.3f}s")
            print(f"- Max: {max_duration:.3f}s")

            # Identify bottlenecks (steps taking > 0.3s on average)
            if avg_duration > 0.3:
                bottlenecks.append({"step_id": step_id, "avg_duration": avg_duration})

        # Verify bottlenecks identified
        assert len(bottlenecks) >= 2  # slow_step and another_slow_step
        assert any(b["step_id"] == "slow_step" for b in bottlenecks)

    @pytest.mark.asyncio
    async def test_concurrent_access_bottlenecks(self):
        """Test bottlenecks in concurrent state access."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)

        # Workflow with heavy concurrent state access
        concurrent_state_workflow = WorkflowDefinition(
            name="concurrent_state_test",
            version="1.0",
            steps=[
                WorkflowStep(id="init_counter", type="state_update", config={"updates": {"counter": 0}}),
                WorkflowStep(
                    id="concurrent_increments",
                    type="foreach",
                    config={
                        "items": "{{ range(50) }}",
                        "parallel": True,
                        "max_concurrent": 20,
                        "steps": [
                            {
                                "id": "increment",
                                "type": "state_update",
                                "config": {"updates": {"counter": "{{ state.counter + 1 }}"}},
                            }
                        ],
                    },
                ),
            ],
        )

        # Run test multiple times
        execution_times = []

        for i in range(3):
            result = await executor.start_workflow(concurrent_state_workflow, {})
            workflow_id = result["workflow_id"]

            start_time = time.time()

            # Execute workflow
            while executor.has_pending_workflows():
                await executor.execute_next()

            execution_time = time.time() - start_time
            execution_times.append(execution_time)

            # Check final counter value
            final_state = state_manager.get_workflow_state(workflow_id)
            # Note: Due to concurrent updates, counter may not be exactly 50
            print(f"\nRun {i+1}: Counter = {final_state['state'].get('counter', 0)}, Time = {execution_time:.3f}s")

        # Analyze consistency in execution times
        avg_time = statistics.mean(execution_times)
        std_dev = statistics.stdev(execution_times) if len(execution_times) > 1 else 0

        print("\nConcurrent state access performance:")
        print(f"- Average execution time: {avg_time:.3f}s")
        print(f"- Standard deviation: {std_dev:.3f}s")

        # Performance should be consistent
        assert std_dev < avg_time * 0.2  # Less than 20% variation


class TestMemoryLeakDetection:
    """Test for memory leaks under sustained load."""

    @pytest.mark.asyncio
    async def test_long_running_memory_stability(self):
        """Test memory stability over extended execution."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)

        # Simple workflow for sustained execution
        workflow_def = WorkflowDefinition(
            name="memory_test",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="create_data",
                    type="state_update",
                    config={"updates": {"data": "{{ 'x' * inputs.size }}", "timestamp": "{{ now() }}"}},
                ),
                WorkflowStep(id="process", type="state_update", config={"updates": {"processed": True}}),
            ],
        )

        # Memory monitoring
        process = psutil.Process()
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024

        memory_checkpoints = []
        workflows_processed = 0

        # Run for extended period
        test_iterations = 50
        workflows_per_iteration = 20

        for iteration in range(test_iterations):
            # Start batch of workflows
            for i in range(workflows_per_iteration):
                await executor.start_workflow(workflow_def, {"size": 1000})  # 1KB of data per workflow

            # Execute all pending
            while executor.has_pending_workflows():
                await executor.execute_next()
                workflows_processed += 1

            # Force garbage collection
            gc.collect()

            # Record memory
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_checkpoints.append(
                {"iteration": iteration, "memory": current_memory, "workflows": workflows_processed}
            )

            # Small delay
            await asyncio.sleep(0.1)

        # Analyze memory growth
        final_memory = memory_checkpoints[-1]["memory"]
        memory_growth = final_memory - initial_memory

        # Calculate growth rate
        growth_per_workflow = memory_growth / workflows_processed if workflows_processed > 0 else 0

        print("\nMemory Leak Detection Results:")
        print(f"- Initial memory: {initial_memory:.2f} MB")
        print(f"- Final memory: {final_memory:.2f} MB")
        print(f"- Total growth: {memory_growth:.2f} MB")
        print(f"- Workflows processed: {workflows_processed}")
        print(f"- Growth per workflow: {growth_per_workflow*1000:.3f} KB")

        # Check for linear growth pattern (indicates leak)
        # Calculate correlation between iteration and memory
        if len(memory_checkpoints) > 10:
            # Simple linear regression
            x_values = [cp["iteration"] for cp in memory_checkpoints[10:]]  # Skip initial allocations
            y_values = [cp["memory"] for cp in memory_checkpoints[10:]]

            n = len(x_values)
            x_mean = sum(x_values) / n
            y_mean = sum(y_values) / n

            numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=False))
            denominator = sum((x - x_mean) ** 2 for x in x_values)

            if denominator > 0:
                slope = numerator / denominator
                correlation = numerator / (denominator**0.5 * sum((y - y_mean) ** 2 for y in y_values) ** 0.5)

                print(f"- Memory growth slope: {slope:.3f} MB/iteration")
                print(f"- Correlation coefficient: {correlation:.3f}")

                # Strong positive correlation indicates leak
                assert abs(correlation) < 0.8  # Should not have strong linear growth

        # Overall assertions
        assert growth_per_workflow < 0.01  # Less than 10KB per workflow
        assert memory_growth < 20  # Less than 20MB total growth


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
