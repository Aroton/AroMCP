"""
Comprehensive sub-agent resource management testing for sub-agent management.

Covers missing acceptance criteria:
- AC-SAM-010: Sub-agent timeouts are handled gracefully
- AC-SAM-019: Sub-agent status tracking and monitoring works
- AC-SAM-020: Sub-agent failures are handled without affecting others
- AC-SAM-021: Resource cleanup occurs after sub-agent completion

Focus: Sub-agent timeout handling, error isolation, resource cleanup
Pillar: Sub-Agent Management
"""

import os
import tempfile
import threading
import time
from unittest.mock import Mock

import psutil
import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.step_context import StepContext
from aromcp.workflow_server.workflow.subagent_test_adapter import SubAgentManager
from aromcp.workflow_server.workflow.workflow_state import WorkflowState


class TestSubAgentResourceManagement:
    """Test comprehensive sub-agent resource management and cleanup."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock state manager for testing."""
        manager = Mock(spec=StateManager)
        manager.get_flattened_view.return_value = {"items": ["item1", "item2", "item3"]}
        manager.resolve_variables = Mock(side_effect=lambda x: x)
        manager.update_state = Mock()
        manager.create_isolated_context = Mock(side_effect=self._create_mock_context)
        return manager

    def _create_mock_context(self, task_inputs):
        """Create mock isolated context for sub-agents."""
        context_manager = Mock(spec=StateManager)
        context_manager.get_flattened_view.return_value = {**task_inputs, "isolated": True}
        context_manager.update_state = Mock()
        return context_manager

    @pytest.fixture
    def subagent_manager(self, mock_state_manager):
        """Create sub-agent manager for testing."""
        return SubAgentManager(workflow_id="wf_resource_test", state_manager=mock_state_manager)

    @pytest.fixture
    def step_context(self, mock_state_manager):
        """Create step context for testing."""
        return StepContext(
            workflow_id="wf_resource_test",
            step_id="parallel_step",
            state_manager=mock_state_manager,
            workflow_config={"timeout_seconds": 60},
        )

    @pytest.fixture
    def workflow_state(self):
        """Create workflow state for testing."""
        return WorkflowState(
            workflow_id="wf_resource_test",
            status="running",
            current_step_index=2,
            total_steps=5,
            state={"inputs": {}, "state": {"items": ["item1", "item2", "item3"]}, "computed": {}},
            execution_context={"subagent_contexts": {}},
        )

    def test_subagent_timeout_handling_graceful(self, subagent_manager):
        """
        Test AC-SAM-010: Sub-agent timeouts are handled gracefully
        Focus: Individual sub-agents exceeding timeout don't affect others
        """
        # Create sub-agent tasks with different timeout characteristics
        task_definitions = {
            "fast_task": {
                "description": "Fast completing task",
                "inputs": {"timeout_seconds": 2},
                "steps": [{"type": "shell_command", "command": "echo 'fast'"}],
            },
            "slow_task": {
                "description": "Slow task that will timeout",
                "inputs": {"timeout_seconds": 2},
                "steps": [{"type": "shell_command", "command": "sleep 5"}],  # Exceeds timeout
            },
        }

        work_items = [
            {"id": "item1", "task": "fast_task", "data": "fast_data"},
            {"id": "item2", "task": "slow_task", "data": "slow_data"},
            {"id": "item3", "task": "fast_task", "data": "more_fast_data"},
        ]

        # Mock sub-agent execution
        execution_results = {}
        execution_times = {}

        def mock_execute_subagent(item, task_def):
            start_time = time.time()
            item_id = item["id"]
            task_type = item["task"]

            if task_type == "fast_task":
                time.sleep(0.1)  # Quick execution
                execution_times[item_id] = time.time() - start_time
                return {"status": "completed", "result": f"processed_{item_id}"}
            else:  # slow_task
                try:
                    time.sleep(3)  # Would exceed 2s timeout
                    execution_times[item_id] = time.time() - start_time
                    return {"status": "completed", "result": f"processed_{item_id}"}
                except:
                    execution_times[item_id] = time.time() - start_time
                    raise TimeoutError(f"Sub-agent {item_id} timed out")

        subagent_manager.execute_subagent = Mock(side_effect=mock_execute_subagent)

        # Execute with timeout handling
        start_time = time.time()
        results = subagent_manager.execute_parallel_tasks(work_items, task_definitions, timeout_seconds=2)
        total_time = time.time() - start_time

        # Verify timeout behavior
        assert "item1" in results
        assert "item3" in results
        assert results["item1"]["status"] == "completed"
        assert results["item3"]["status"] == "completed"

        # Verify timeout handling for slow task
        if "item2" in results:
            assert results["item2"]["status"] in ["timeout", "failed"]

        # Verify fast tasks completed successfully despite slow task timeout
        assert execution_times["item1"] < 1.0
        assert execution_times["item3"] < 1.0

        # Total execution should not be significantly delayed by timeout (should be ~2s, not 5s)
        assert total_time < 4.0

    def test_subagent_status_tracking_monitoring(self, subagent_manager):
        """
        Test AC-SAM-019: Sub-agent status tracking and monitoring works
        Focus: Accurate status information during execution lifecycle
        """
        task_definition = {
            "process_item": {
                "description": "Process item with status updates",
                "inputs": {"item_data": "string"},
                "steps": [
                    {
                        "type": "user_message",
                        "message": "Processing item",
                        "state_update": {"path": "this.status", "value": "processing"},
                    },
                    {"type": "shell_command", "command": "echo 'processing {{ inputs.item_data }}'"},
                    {
                        "type": "user_message",
                        "message": "Processing completed",
                        "state_update": {"path": "this.status", "value": "completed"},
                    },
                ],
            }
        }

        work_items = [
            {"id": "item1", "task": "process_item", "item_data": "data1"},
            {"id": "item2", "task": "process_item", "item_data": "data2"},
            {"id": "item3", "task": "process_item", "item_data": "data3"},
        ]

        # Track status changes
        status_updates = {}

        def mock_status_callback(item_id, status, metadata=None):
            if item_id not in status_updates:
                status_updates[item_id] = []
            status_updates[item_id].append({"status": status, "timestamp": time.time(), "metadata": metadata})

        subagent_manager.set_status_callback(mock_status_callback)

        # Mock sub-agent execution with status updates
        def mock_execute_with_status(item, task_def):
            item_id = item["id"]

            # Simulate status progression
            mock_status_callback(item_id, "starting")
            time.sleep(0.1)

            mock_status_callback(item_id, "processing", {"step": "set_variable"})
            time.sleep(0.1)

            mock_status_callback(item_id, "processing", {"step": "shell_command"})
            time.sleep(0.1)

            mock_status_callback(item_id, "completed", {"result": f"processed_{item_id}"})

            return {"status": "completed", "result": f"processed_{item_id}"}

        subagent_manager.execute_subagent = Mock(side_effect=mock_execute_with_status)

        # Execute and monitor
        results = subagent_manager.execute_parallel_tasks(work_items, task_definition)

        # Verify status tracking
        assert len(status_updates) == 3

        for item_id in ["item1", "item2", "item3"]:
            assert item_id in status_updates
            statuses = [update["status"] for update in status_updates[item_id]]

            # Verify status progression
            assert "starting" in statuses
            assert "processing" in statuses
            assert "completed" in statuses

            # Verify chronological order
            timestamps = [update["timestamp"] for update in status_updates[item_id]]
            assert timestamps == sorted(timestamps)

        # Verify monitoring API
        monitoring_data = subagent_manager.get_monitoring_summary()
        assert monitoring_data["total_subagents"] == 3
        assert monitoring_data["completed_subagents"] == 3
        assert monitoring_data["failed_subagents"] == 0
        assert monitoring_data["success_rate"] == 1.0

    def test_subagent_failure_isolation(self, subagent_manager):
        """
        Test AC-SAM-020: Sub-agent failures are handled without affecting others
        Focus: Individual failures don't cascade to other sub-agents
        """
        task_definition = {
            "risky_task": {
                "description": "Task that may fail randomly",
                "inputs": {"item_data": "string", "should_fail": "boolean"},
                "steps": [
                    {
                        "type": "conditional",
                        "condition": "inputs.should_fail",
                        "then_steps": [{"type": "shell_command", "command": "exit 1"}],  # Will fail
                        "else_steps": [{"type": "shell_command", "command": "echo 'success'"}],
                    }
                ],
            }
        }

        work_items = [
            {"id": "item1", "task": "risky_task", "item_data": "data1", "should_fail": False},
            {"id": "item2", "task": "risky_task", "item_data": "data2", "should_fail": True},  # Will fail
            {"id": "item3", "task": "risky_task", "item_data": "data3", "should_fail": False},
            {"id": "item4", "task": "risky_task", "item_data": "data4", "should_fail": True},  # Will fail
            {"id": "item5", "task": "risky_task", "item_data": "data5", "should_fail": False},
        ]

        # Track execution attempts and results
        execution_log = {}

        def mock_execute_with_failures(item, task_def):
            item_id = item["id"]
            execution_log[item_id] = {"attempted": True, "start_time": time.time()}

            if item.get("should_fail", False):
                execution_log[item_id]["failed"] = True
                raise Exception(f"Sub-agent {item_id} failed as expected")
            else:
                execution_log[item_id]["succeeded"] = True
                return {"status": "completed", "result": f"processed_{item_id}"}

        subagent_manager.execute_subagent = Mock(side_effect=mock_execute_with_failures)

        # Execute with error isolation
        results = subagent_manager.execute_parallel_tasks(work_items, task_definition, error_isolation=True)

        # Verify failure isolation
        assert len(execution_log) == 5  # All items were attempted

        # Verify successful items completed despite failures
        successful_items = ["item1", "item3", "item5"]
        failed_items = ["item2", "item4"]

        for item_id in successful_items:
            assert execution_log[item_id]["attempted"] == True
            assert execution_log[item_id].get("succeeded") == True
            assert item_id in results
            assert results[item_id]["status"] == "completed"

        for item_id in failed_items:
            assert execution_log[item_id]["attempted"] == True
            assert execution_log[item_id].get("failed") == True
            # Failed items should be in results with error status
            if item_id in results:
                assert results[item_id]["status"] in ["failed", "error"]

        # Verify overall success rate
        success_count = len([r for r in results.values() if r["status"] == "completed"])
        total_count = len(work_items)
        expected_success_rate = 3 / 5  # 3 out of 5 should succeed
        actual_success_rate = success_count / total_count
        assert abs(actual_success_rate - expected_success_rate) < 0.1

    def test_resource_cleanup_after_completion(self, subagent_manager):
        """
        Test AC-SAM-021: Resource cleanup occurs after sub-agent completion
        Focus: Proper cleanup of contexts, temporary files, processes
        """
        # Create temporary directories to simulate resource usage
        temp_dirs = {}
        temp_files = {}

        def create_temp_resources(item_id):
            """Simulate creating temporary resources for sub-agent."""
            temp_dir = tempfile.mkdtemp(prefix=f"subagent_{item_id}_")
            temp_file = os.path.join(temp_dir, "temp_data.txt")

            with open(temp_file, "w") as f:
                f.write(f"Temporary data for {item_id}")

            temp_dirs[item_id] = temp_dir
            temp_files[item_id] = temp_file

            return temp_dir, temp_file

        def cleanup_temp_resources(item_id):
            """Simulate cleaning up temporary resources."""
            if item_id in temp_files:
                try:
                    os.remove(temp_files[item_id])
                    os.rmdir(temp_dirs[item_id])
                except:
                    pass  # May already be cleaned up

        task_definition = {
            "resource_task": {
                "description": "Task that creates and cleans up resources",
                "inputs": {"item_data": "string"},
                "steps": [
                    {"type": "shell_command", "command": "echo 'Creating resources'"},
                    {"type": "shell_command", "command": "echo 'Processing data'"},
                    {"type": "shell_command", "command": "echo 'Cleaning up'"},
                ],
            }
        }

        work_items = [
            {"id": "item1", "task": "resource_task", "item_data": "data1"},
            {"id": "item2", "task": "resource_task", "item_data": "data2"},
            {"id": "item3", "task": "resource_task", "item_data": "data3"},
        ]

        # Track resource lifecycle
        resource_lifecycle = {}

        def mock_execute_with_resources(item, task_def):
            item_id = item["id"]
            resource_lifecycle[item_id] = {"created": False, "cleaned_up": False}

            try:
                # Create resources
                temp_dir, temp_file = create_temp_resources(item_id)
                resource_lifecycle[item_id]["created"] = True
                resource_lifecycle[item_id]["temp_dir"] = temp_dir
                resource_lifecycle[item_id]["temp_file"] = temp_file

                # Simulate work
                time.sleep(0.1)

                return {"status": "completed", "result": f"processed_{item_id}"}

            finally:
                # Cleanup resources (should happen even if execution fails)
                cleanup_temp_resources(item_id)
                resource_lifecycle[item_id]["cleaned_up"] = True

        subagent_manager.execute_subagent = Mock(side_effect=mock_execute_with_resources)

        # Enable resource tracking
        subagent_manager.enable_resource_tracking(True)

        # Execute with resource cleanup
        results = subagent_manager.execute_parallel_tasks(work_items, task_definition)

        # Verify resource cleanup
        for item_id in ["item1", "item2", "item3"]:
            assert item_id in resource_lifecycle
            assert resource_lifecycle[item_id]["created"] == True
            assert resource_lifecycle[item_id]["cleaned_up"] == True

            # Verify temporary files/directories were actually cleaned up
            temp_dir = resource_lifecycle[item_id]["temp_dir"]
            temp_file = resource_lifecycle[item_id]["temp_file"]
            assert not os.path.exists(temp_file)
            assert not os.path.exists(temp_dir)

        # Verify sub-agent contexts were cleaned up
        active_contexts = subagent_manager.get_active_contexts()
        assert len(active_contexts) == 0

        # Verify resource tracking summary
        resource_summary = subagent_manager.get_resource_summary()
        assert resource_summary["contexts_created"] == 3
        assert resource_summary["contexts_cleaned_up"] == 3
        assert resource_summary["cleanup_success_rate"] == 1.0

    def test_concurrent_subagent_resource_management(self, subagent_manager):
        """
        Test resource management under high concurrency
        Focus: Resource limits and cleanup under concurrent execution
        """
        # Large number of work items to test concurrency
        work_items = [{"id": f"item{i}", "task": "concurrent_task", "data": f"data{i}"} for i in range(20)]

        task_definition = {
            "concurrent_task": {
                "description": "Task for concurrency testing",
                "inputs": {"data": "string"},
                "steps": [
                    {
                        "type": "user_message",
                        "message": "Processing data",
                        "state_update": {"path": "this.processed", "value": "{{ inputs.data }}"},
                    },
                    {"type": "shell_command", "command": "echo 'concurrent processing'"},
                ],
            }
        }

        # Track concurrent resource usage
        concurrent_contexts = {}
        max_concurrent = 0
        current_concurrent = 0
        lock = threading.Lock()

        def mock_concurrent_execute(item, task_def):
            nonlocal current_concurrent, max_concurrent

            item_id = item["id"]

            with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)
                concurrent_contexts[item_id] = {"start_time": time.time(), "active": True}

            try:
                # Simulate work
                time.sleep(0.2)  # 200ms work simulation

                return {"status": "completed", "result": f"processed_{item_id}"}

            finally:
                with lock:
                    current_concurrent -= 1
                    concurrent_contexts[item_id]["active"] = False
                    concurrent_contexts[item_id]["end_time"] = time.time()

        subagent_manager.execute_subagent = Mock(side_effect=mock_concurrent_execute)

        # Execute with concurrency limits
        start_time = time.time()
        results = subagent_manager.execute_parallel_tasks(
            work_items, task_definition, max_parallel=5  # Limit to 5 concurrent sub-agents
        )
        total_time = time.time() - start_time

        # Verify concurrency control
        assert max_concurrent <= 5  # Should respect max_parallel limit
        assert len(results) == 20  # All items should be processed

        # Verify all completed successfully
        completed_count = len([r for r in results.values() if r["status"] == "completed"])
        assert completed_count == 20

        # Verify timing - with 5 concurrent and 20 items, should take ~4 batches * 0.2s ≈ 0.8s
        # Allow some overhead but shouldn't take much longer
        assert total_time < 2.0

        # Verify resource cleanup
        active_contexts = subagent_manager.get_active_contexts()
        assert len(active_contexts) == 0

    def test_subagent_memory_management(self, subagent_manager):
        """
        Test memory management for sub-agent contexts
        Focus: Memory usage stays reasonable with many sub-agents
        """

        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Create many sub-agents with substantial state
        large_work_items = []
        for i in range(50):
            # Each item has substantial data to test memory management
            large_data = {
                "id": f"item{i}",
                "task": "memory_task",
                "large_payload": "x" * 10000,  # 10KB per item
                "nested_data": {"level1": {"level2": {"level3": [f"data{j}" for j in range(100)]}}},
                "array_data": list(range(1000)),
            }
            large_work_items.append(large_data)

        task_definition = {
            "memory_task": {
                "description": "Task that processes large data",
                "inputs": {"large_payload": "string", "nested_data": "object", "array_data": "array"},
                "steps": [
                    {
                        "type": "user_message",
                        "message": "Calculating size",
                        "state_update": {"path": "this.processed_size", "value": "{{ inputs.large_payload.length }}"},
                    },
                    {
                        "type": "user_message",
                        "message": "Calculating array length",
                        "state_update": {"path": "this.array_length", "value": "{{ inputs.array_data.length }}"},
                    },
                ],
            }
        }

        def mock_memory_execute(item, task_def):
            # Simulate processing the large data
            data_size = len(item.get("large_payload", ""))
            array_length = len(item.get("array_data", []))

            return {
                "status": "completed",
                "result": f"processed_{item['id']}",
                "data_size": data_size,
                "array_length": array_length,
            }

        subagent_manager.execute_subagent = Mock(side_effect=mock_memory_execute)

        # Execute with memory monitoring
        subagent_manager.enable_memory_monitoring(True)

        results = subagent_manager.execute_parallel_tasks(large_work_items, task_definition, max_parallel=10)

        # Check final memory usage
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Verify all items processed
        assert len(results) == 50

        # Memory increase should be reasonable (less than 100MB for this test)
        # This is a rough check - actual limits depend on system and implementation
        assert memory_increase < 100 * 1024 * 1024  # 100MB limit

        # Verify memory tracking
        memory_stats = subagent_manager.get_memory_statistics()
        assert memory_stats["peak_memory_usage"] > initial_memory
        assert memory_stats["contexts_created"] == 50
        assert memory_stats["average_memory_per_context"] > 0


class TestSubAgentResourceIntegration:
    """Test sub-agent resource management in realistic workflow scenarios."""

    def test_production_parallel_processing_resource_management(self):
        """
        Test resource management in production-like parallel processing scenario
        Focus: Resource handling similar to code quality workflows
        """
        # Simulate a code quality workflow with parallel file processing
        state_manager = Mock(spec=StateManager)
        state_manager.get_flattened_view.return_value = {
            "files": ["file1.js", "file2.js", "file3.js", "file4.js", "file5.js"]
        }

        subagent_manager = SubAgentManager("wf_quality_check", state_manager)

        # Define sub-agent task similar to code quality checking
        task_definition = {
            "quality_check": {
                "description": "Check code quality for a file",
                "inputs": {"file_path": "string", "check_types": "array"},
                "timeout_seconds": 30,
                "steps": [
                    {"type": "shell_command", "command": "eslint {{ inputs.file_path }}", "timeout": 10},
                    {"type": "shell_command", "command": "tsc --noEmit {{ inputs.file_path }}", "timeout": 15},
                    {
                        "type": "user_message",
                        "message": "Quality analysis complete",
                        "state_update": {"path": "this.quality_score", "value": "95"},
                    },
                ],
            }
        }

        work_items = [
            {"id": "file1", "task": "quality_check", "file_path": "file1.js", "check_types": ["lint", "type"]},
            {"id": "file2", "task": "quality_check", "file_path": "file2.js", "check_types": ["lint", "type"]},
            {"id": "file3", "task": "quality_check", "file_path": "file3.js", "check_types": ["lint", "type"]},
            {"id": "file4", "task": "quality_check", "file_path": "file4.js", "check_types": ["lint", "type"]},
            {"id": "file5", "task": "quality_check", "file_path": "file5.js", "check_types": ["lint", "type"]},
        ]

        # Mock execution with realistic timing and resource usage
        def mock_quality_check_execute(item, task_def):
            # Simulate realistic execution times
            if "file2" in item["file_path"]:
                time.sleep(0.3)  # Slower file
            else:
                time.sleep(0.1)  # Normal files

            return {
                "status": "completed",
                "result": {"file": item["file_path"], "lint_errors": 0, "type_errors": 0, "quality_score": 95},
            }

        subagent_manager.execute_subagent = Mock(side_effect=mock_quality_check_execute)

        # Execute with production-like settings
        start_time = time.time()
        results = subagent_manager.execute_parallel_tasks(
            work_items, task_definition, max_parallel=3, timeout_seconds=30  # Typical production concurrency limit
        )
        execution_time = time.time() - start_time

        # Verify production-like results
        assert len(results) == 5
        assert all(r["status"] == "completed" for r in results.values())

        # Should complete faster than sequential (would be ~0.7s sequential, should be <0.5s parallel)
        assert execution_time < 0.5

        # Verify resource cleanup
        assert len(subagent_manager.get_active_contexts()) == 0

        # Verify monitoring data
        monitoring = subagent_manager.get_monitoring_summary()
        assert monitoring["success_rate"] == 1.0
        assert monitoring["average_execution_time"] < 0.3
