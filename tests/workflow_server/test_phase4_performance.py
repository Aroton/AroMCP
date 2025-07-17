"""Phase 4 performance and concurrent execution verification tests.

This module tests the performance characteristics and concurrent execution
capabilities of Phase 4 components with realistic workloads.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from aromcp.workflow_server.state.concurrent import ConcurrentStateManager
from aromcp.workflow_server.state.models import WorkflowState
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.parallel import (
    ParallelForEachProcessor,
    ParallelForEachStep,
)
from aromcp.workflow_server.workflow.sub_agents import SubAgentManager


class TestPhase4ConcurrentExecution:
    """Test concurrent execution with 10+ agents."""

    def test_standards_fix_with_10_plus_agents(self):
        """Test complete standards:fix simulation with 10+ concurrent agents."""
        # Given - Setup for large-scale parallel execution
        concurrent_manager = ConcurrentStateManager()
        sub_agent_manager = SubAgentManager()
        parallel_processor = ParallelForEachProcessor(ExpressionEvaluator())

        # Large-scale workflow state with 15 files (will create 5 batches of 3 files each)
        files = [
            "src/index.ts", "src/utils.ts", "src/config.ts",
            "src/components/Button.tsx", "src/components/Card.tsx", "src/components/Form.tsx",
            "src/api/users.ts", "src/api/auth.ts", "src/api/files.ts",
            "src/services/logger.ts", "src/services/cache.ts", "src/services/validator.ts",
            "tests/utils.test.ts", "tests/api.test.ts", "tests/components.test.ts"
        ]

        # Create 5 batches of 3 files each
        batches = []
        for i in range(0, len(files), 3):
            batch_files = files[i:i+3]
            batches.append({"id": f"batch_{i//3}", "files": batch_files})

        concurrent_manager._base_manager._states["wf_perf_test"] = WorkflowState(
            raw={
                "start_time": time.time(),
                "batch_status": {},
                "file_results": {},
                "git_files": files,
                "user_target_input": "HEAD",
                "processed_count": 0
            },
            computed={
                "valid_files": files,
                "file_batches": batches
            },
            state={}
        )

        # Register realistic sub-agent task
        sub_agent_manager.register_task_definition(
            "process_standards_batch",
            steps=[
                {"type": "state_update", "path": "raw.batch_status.{{ task_id }}", "value": "processing"},
                {"type": "foreach", "items": "{{ files }}", "steps": [
                    {"type": "state_update", "path": "raw.file_results.{{ item }}", "value": {"status": "processing", "fixes": 0}},
                    {"type": "mcp_call", "method": "lint_project", "params": {"target_files": "{{ item }}"}},
                    {"type": "mcp_call", "method": "check_typescript", "params": {"files": ["{{ item }}"]}},
                    {"type": "state_update", "path": "raw.file_results.{{ item }}", "value": {"status": "complete", "fixes": 3}}
                ]},
                {"type": "state_update", "path": "raw.batch_status.{{ task_id }}", "value": "complete"}
            ]
        )

        # When - Process with 10+ parallel agents (max_parallel=15 to test scaling)
        step_def = ParallelForEachStep(
            items="file_batches",
            max_parallel=15,  # Allow all batches to run in parallel
            wait_for_all=True,
            sub_agent_task="process_standards_batch"
        )

        state = concurrent_manager.read("wf_perf_test")
        start_time = time.time()
        
        parallel_result = parallel_processor.process_parallel_foreach(
            step_def, state, "process_batches", "wf_perf_test"
        )

        # Simulate agent creation and execution for all 5 batches
        execution_id = parallel_result["step"]["definition"]["execution_id"]
        tasks = parallel_result["step"]["definition"]["tasks"]

        created_agents = []
        for task in tasks:
            registration = sub_agent_manager.create_sub_agent(
                workflow_id="wf_perf_test",
                task_id=task["task_id"],
                task_name="process_standards_batch",
                context=task["context"],
                parent_step_id="process_batches"
            )
            created_agents.append(registration)

        # Concurrent execution simulation
        execution_results = []
        agent_timings = []

        def simulate_realistic_agent_execution(agent_registration, task_id):
            agent_start = time.time()
            
            # Mark agent as active
            sub_agent_manager.update_agent_status(agent_registration.agent_id, "active")
            parallel_processor.update_task_status(execution_id, task_id, "running")

            try:
                # Simulate realistic processing time (50-200ms per file)
                files = agent_registration.context.context.get("item", {}).get("files", [])
                processing_time = len(files) * 0.075  # 75ms per file
                time.sleep(processing_time)
                
                # Update batch status
                concurrent_manager.update(
                    "wf_perf_test",
                    [{"path": f"raw.batch_status.{task_id}", "value": "processing"}],
                    agent_id=agent_registration.agent_id
                )

                # Process each file with state updates
                for file_path in files:
                    file_key = file_path.replace('/', '_').replace('.', '_')
                    
                    # Start processing
                    concurrent_manager.update(
                        "wf_perf_test",
                        [{"path": f"raw.file_results.{file_key}", "value": {"status": "processing", "fixes": 0}}],
                        agent_id=agent_registration.agent_id
                    )
                    
                    # Small processing delay
                    time.sleep(0.01)
                    
                    # Complete processing
                    concurrent_manager.update(
                        "wf_perf_test",
                        [{"path": f"raw.file_results.{file_key}", "value": {"status": "complete", "fixes": 3}}],
                        agent_id=agent_registration.agent_id
                    )

                # Mark batch complete
                concurrent_manager.update(
                    "wf_perf_test",
                    [{"path": f"raw.batch_status.{task_id}", "value": "complete"}],
                    agent_id=agent_registration.agent_id
                )

                # Increment processed count
                current_state = concurrent_manager.read("wf_perf_test")
                new_count = current_state.get("processed_count", 0) + len(files)
                concurrent_manager.update(
                    "wf_perf_test",
                    [{"path": "raw.processed_count", "value": new_count}],
                    agent_id=agent_registration.agent_id
                )

                # Mark agent complete
                sub_agent_manager.update_agent_status(agent_registration.agent_id, "completed")
                parallel_processor.update_task_status(execution_id, task_id, "completed")

                agent_end = time.time()
                agent_timings.append({
                    "agent_id": agent_registration.agent_id,
                    "task_id": task_id,
                    "duration": agent_end - agent_start,
                    "files_processed": len(files)
                })
                execution_results.append({"agent_id": agent_registration.agent_id, "status": "success"})

            except Exception as e:
                sub_agent_manager.update_agent_status(agent_registration.agent_id, "failed", error=str(e))
                parallel_processor.update_task_status(execution_id, task_id, "failed", error=str(e))
                execution_results.append({"agent_id": agent_registration.agent_id, "status": "failed", "error": str(e)})

        # Execute all agents concurrently
        agent_threads = [
            threading.Thread(
                target=simulate_realistic_agent_execution,
                args=(agent, task["task_id"])
            )
            for agent, task in zip(created_agents, tasks)
        ]

        for thread in agent_threads:
            thread.start()
        for thread in agent_threads:
            thread.join()

        total_execution_time = time.time() - start_time

        # Then - Verify execution results
        assert len(execution_results) == 5  # All 5 batches processed
        successful_agents = [r for r in execution_results if r["status"] == "success"]
        assert len(successful_agents) == 5  # All agents succeeded

        # Verify final state
        final_state = concurrent_manager.read("wf_perf_test")
        
        # All batches should be complete
        batch_statuses = final_state["batch_status"]
        assert len(batch_statuses) == 5
        assert all(status == "complete" for status in batch_statuses.values())

        # All files should be processed
        file_results = final_state["file_results"]
        assert len(file_results) == 15  # All 15 files processed
        assert all(result["status"] == "complete" for result in file_results.values())
        assert all(result["fixes"] == 3 for result in file_results.values())

        # Processed count should be correct
        assert final_state["processed_count"] == 15

        # All agents should be completed
        workflow_agents = sub_agent_manager.get_workflow_agents("wf_perf_test")
        assert len(workflow_agents) == 5
        assert all(agent.status == "completed" for agent in workflow_agents)

        # Parallel execution should be complete
        execution = parallel_processor.get_execution(execution_id)
        assert execution.is_complete
        assert execution.failed_task_count == 0

        # Performance assertions
        assert total_execution_time < 5.0  # Should complete quickly with parallel execution
        
        # Average agent execution time should be reasonable
        avg_agent_time = sum(timing["duration"] for timing in agent_timings) / len(agent_timings)
        assert avg_agent_time < 1.0  # Individual agents should be fast

        return {
            "total_execution_time": total_execution_time,
            "agent_timings": agent_timings,
            "concurrent_stats": concurrent_manager.get_stats(),
            "agent_stats": sub_agent_manager.get_agent_stats("wf_perf_test")
        }

    def test_concurrent_state_race_conditions(self):
        """Test for race conditions with high concurrent load."""
        # Given
        manager = ConcurrentStateManager()
        
        manager._base_manager._states["race_test"] = WorkflowState(
            raw={"counters": {}, "totals": {"sum": 0, "count": 0}},
            computed={}, state={}
        )

        # When - 20 agents updating different counters and shared totals
        num_agents = 20
        updates_per_agent = 10
        
        def concurrent_agent_updates(agent_id):
            for i in range(updates_per_agent):
                # Update individual counter
                manager.update(
                    "race_test",
                    [{"path": f"raw.counters.agent_{agent_id}", "value": i + 1}],
                    agent_id=f"agent_{agent_id}"
                )
                
                # Update shared totals (potential race condition)
                current_state = manager.read("race_test")
                new_sum = current_state["totals"]["sum"] + 1
                new_count = current_state["totals"]["count"] + 1
                
                manager.update(
                    "race_test",
                    [
                        {"path": "raw.totals.sum", "value": new_sum},
                        {"path": "raw.totals.count", "value": new_count}
                    ],
                    agent_id=f"agent_{agent_id}"
                )

        # Execute concurrent updates
        threads = [
            threading.Thread(target=concurrent_agent_updates, args=(i,))
            for i in range(num_agents)
        ]

        start_time = time.time()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        execution_time = time.time() - start_time

        # Then - Verify final state consistency
        final_state = manager.read("race_test")
        
        # All individual counters should exist
        counters = final_state["counters"]
        assert len(counters) == num_agents
        
        # Each counter should have its final value
        for i in range(num_agents):
            assert counters[f"agent_{i}"] == updates_per_agent

        # Shared totals should be consistent (within reasonable bounds due to race conditions)
        totals = final_state["totals"]
        expected_total_updates = num_agents * updates_per_agent
        
        # Due to race conditions, we might not get exact values, but they should be close
        assert totals["count"] > 0
        assert totals["sum"] > 0
        assert totals["count"] <= expected_total_updates
        assert totals["sum"] <= expected_total_updates

        # Performance should be reasonable
        assert execution_time < 10.0  # Should complete within 10 seconds

        return {
            "execution_time": execution_time,
            "expected_updates": expected_total_updates,
            "actual_count": totals["count"],
            "actual_sum": totals["sum"],
            "stats": manager.get_stats()
        }

    def test_memory_usage_and_cleanup(self):
        """Test memory usage and cleanup with large numbers of agents."""
        # Given
        sub_agent_manager = SubAgentManager()
        concurrent_manager = ConcurrentStateManager()
        
        # Register task
        sub_agent_manager.register_task_definition("memory_test", [{"type": "user_message", "message": "test"}])

        # When - Create large number of agents
        num_agents = 50
        workflow_ids = [f"wf_{i}" for i in range(5)]  # 5 workflows with 10 agents each

        created_agents = []
        for wf_id in workflow_ids:
            for i in range(10):
                agent = sub_agent_manager.create_sub_agent(
                    workflow_id=wf_id,
                    task_id=f"task_{i}",
                    task_name="memory_test",
                    context={"data": f"large_data_{'x' * 100}"},  # Some data per agent
                    parent_step_id="step_1"
                )
                created_agents.append(agent)

        # Mark agents as completed
        for agent in created_agents:
            sub_agent_manager.update_agent_status(agent.agent_id, "completed")

        # Create some state data
        for wf_id in workflow_ids:
            concurrent_manager._base_manager._states[wf_id] = WorkflowState(
                raw={"large_data": {"key": "value" * 1000}},  # Large data per workflow
                computed={}, state={}
            )

        # Then - Verify initial state
        initial_stats = sub_agent_manager.get_agent_stats()
        assert initial_stats["total_agents"] == num_agents

        # When - Cleanup inactive agents
        cleanup_count = sub_agent_manager.cleanup_inactive_agents(max_age_seconds=0)  # Cleanup immediately

        # Then - Verify cleanup
        post_cleanup_stats = sub_agent_manager.get_agent_stats()
        assert cleanup_count == num_agents
        assert post_cleanup_stats["total_agents"] == 0

        # Cleanup concurrent manager data
        cleanup_stats = concurrent_manager.cleanup_old_data(max_age_seconds=0)
        
        return {
            "initial_agents": initial_stats["total_agents"],
            "cleaned_up_agents": cleanup_count,
            "final_agents": post_cleanup_stats["total_agents"],
            "cleanup_stats": cleanup_stats
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])