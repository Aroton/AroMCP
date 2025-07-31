"""
Comprehensive queue execution testing for workflow execution engine.

Covers missing acceptance criteria:
- AC-WEE-002: Queue-based execution model maintains order
- AC-WEE-007: Blocking steps pause execution for client interaction
- AC-WEE-008: Immediate processing for server-side steps

Focus: Production workflow queue behaviors (batch, blocking, immediate, expand, wait)
Pillar: Workflow Execution Engine
"""

import time
from unittest.mock import AsyncMock, Mock

import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.workflow.step_processors import StepProcessor


class TestQueueExecutionComprehensive:
    """Test comprehensive queue execution behaviors across all queue modes."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock state manager for testing."""
        state_manager = Mock(spec=StateManager)
        state_manager.get_flattened_state.return_value = {"test": "value"}
        state_manager.update_state = Mock()
        state_manager.resolve_variables = Mock(side_effect=lambda x: x)
        return state_manager

    @pytest.fixture
    def mock_step_processor(self):
        """Mock step processor for testing."""
        processor = Mock(spec=StepProcessor)
        processor.process_step = AsyncMock(return_value={"status": "completed", "result": "test_result"})
        return processor

    @pytest.fixture
    def queue_executor(self, mock_state_manager, mock_step_processor):
        """Create queue executor with mocked dependencies."""
        executor = QueueBasedWorkflowExecutor(state_manager=mock_state_manager, step_processor=mock_step_processor)
        return executor

    @pytest.fixture
    def sample_workflow_state(self):
        """Sample workflow state for testing."""
        return WorkflowState(
            workflow_id="wf_test123",
            status="running",
            current_step_index=0,
            total_steps=5,
            state={"inputs": {}, "state": {}, "computed": {}},
            execution_context={"queue_stats": {"pending": 0, "processing": 0, "completed": 0}},
        )

    def test_batch_queue_maintains_order_with_priority(self, queue_executor, sample_workflow_state):
        """
        Test AC-WEE-002: Queue-based execution model maintains order
        Focus: Batch queue processing with proper priority and ordering
        """
        # Create steps with different queue modes and priorities
        steps = [
            {"id": "step1", "type": "user_message", "queue_mode": "batch", "priority": 1, "message": "First batch"},
            {"id": "step2", "type": "user_message", "queue_mode": "batch", "priority": 2, "message": "High priority"},
            {"id": "step3", "type": "user_message", "queue_mode": "batch", "priority": 1, "message": "Second batch"},
            {"id": "step4", "type": "user_message", "queue_mode": "immediate", "message": "Immediate"},
            {"id": "step5", "type": "user_message", "queue_mode": "batch", "priority": 1, "message": "Third batch"},
        ]

        # Queue all steps
        for step in steps:
            queue_executor.queue_step(step, sample_workflow_state)

        # Verify queue ordering - immediate steps should process first
        queued_steps = queue_executor.get_queued_steps()

        # Immediate steps should be first
        assert queued_steps[0]["queue_mode"] == "immediate"

        # Within batch queue, higher priority (priority 2) should come before lower priority (priority 1)
        batch_steps = [s for s in queued_steps if s["queue_mode"] == "batch"]
        priorities = [s["priority"] for s in batch_steps]

        # Find first occurrence of each priority level
        priority_2_index = next(i for i, p in enumerate(priorities) if p == 2)
        priority_1_indices = [i for i, p in enumerate(priorities) if p == 1]

        # Priority 2 should come before all priority 1 steps
        assert all(priority_2_index < idx for idx in priority_1_indices)

    def test_blocking_steps_pause_execution_correctly(self, queue_executor, sample_workflow_state):
        """
        Test AC-WEE-007: Blocking steps pause execution for client interaction
        Focus: user_input and wait_step blocking behavior
        """
        # Create workflow with blocking steps
        steps = [
            {"id": "step1", "type": "shell_command", "command": "echo 'start'", "queue_mode": "immediate"},
            {
                "id": "step2",
                "type": "user_input",
                "queue_mode": "blocking",
                "prompt": "Enter value",
                "input_type": "string",
            },
            {"id": "step3", "type": "user_message", "queue_mode": "batch", "message": "Should not execute yet"},
            {"id": "step4", "type": "wait_step", "queue_mode": "blocking", "message": "Waiting for client"},
            {"id": "step5", "type": "shell_command", "command": "echo 'end'", "queue_mode": "immediate"},
        ]

        # Queue all steps
        for step in steps:
            queue_executor.queue_step(step, sample_workflow_state)

        # Process first immediate step
        processed = queue_executor.process_next_batch()
        assert len(processed) == 1
        assert processed[0]["type"] == "shell_command"
        assert processed[0]["command"] == "echo 'start'"

        # Next processing should encounter blocking step and pause
        blocked_step = queue_executor.get_next_blocking_step()
        assert blocked_step is not None
        assert blocked_step["type"] == "user_input"
        assert blocked_step["queue_mode"] == "blocking"

        # Verify remaining steps are still queued
        remaining = queue_executor.get_queued_steps()
        assert len(remaining) >= 3  # user_message, wait_step, final shell_command

        # Simulate client providing input and resuming
        queue_executor.resolve_blocking_step("step2", {"user_input": "test_value"})

        # Now batch step should be processable
        batch_processed = queue_executor.process_next_batch()
        assert len(batch_processed) == 1
        assert batch_processed[0]["type"] == "user_message"

        # Should hit next blocking step (wait_step)
        next_blocked = queue_executor.get_next_blocking_step()
        assert next_blocked["type"] == "wait_step"

    @pytest.mark.asyncio
    async def test_immediate_processing_server_side_steps(self, queue_executor, sample_workflow_state):
        """
        Test AC-WEE-008: Immediate processing for server-side steps
        Focus: shell_command, conditional, control flow immediate execution
        """
        # Create mix of immediate server-side steps and client-side steps
        steps = [
            {"id": "step1", "type": "user_message", "queue_mode": "batch", "message": "User message"},
            {"id": "step2", "type": "shell_command", "queue_mode": "immediate", "command": "echo 'immediate'"},
            {"id": "step3", "type": "conditional", "queue_mode": "immediate", "condition": "true", "then_steps": []},
            {"id": "step4", "type": "user_input", "queue_mode": "blocking", "prompt": "Input required"},
            {
                "id": "step5",
                "type": "user_message",
                "queue_mode": "immediate",
                "message": "Setting test variable",
                "state_update": {"path": "this.test", "value": "immediate_value"},
            },
            {
                "id": "step6",
                "type": "mcp_call",
                "queue_mode": "immediate",
                "tool": "test_tool",
                "execution_context": "server",
            },
        ]

        start_time = time.time()

        # Queue all steps
        for step in steps:
            queue_executor.queue_step(step, sample_workflow_state)

        # Process immediate steps - should execute without delay
        immediate_processed = []
        while True:
            immediate_step = queue_executor.get_next_immediate_step()
            if not immediate_step:
                break

            # Process immediately
            result = await queue_executor.process_step_immediately(immediate_step, sample_workflow_state)
            immediate_processed.append(result)

        immediate_time = time.time() - start_time

        # Verify immediate steps were processed
        assert len(immediate_processed) == 4  # shell_command, conditional, set_variable, mcp_call

        # Verify immediate processing completed quickly (< 100ms)
        assert immediate_time < 0.1

        # Verify immediate step types
        processed_types = [step["type"] for step in immediate_processed]
        expected_immediate_types = ["shell_command", "conditional", "set_variable", "mcp_call"]
        assert all(t in processed_types for t in expected_immediate_types)

        # Verify non-immediate steps are still queued
        remaining = queue_executor.get_queued_steps()
        remaining_types = [s["type"] for s in remaining]
        assert "user_message" in remaining_types
        assert "user_input" in remaining_types

    def test_expand_queue_mode_handles_dynamic_steps(self, queue_executor, sample_workflow_state):
        """
        Test queue mode "expand" for dynamic step generation (foreach, parallel_foreach)
        """
        # Create foreach step that should expand into multiple steps
        foreach_step = {
            "id": "foreach1",
            "type": "foreach",
            "queue_mode": "expand",
            "items": ["item1", "item2", "item3"],
            "steps": [
                {"type": "user_message", "message": "Processing {{ loop.item }}"},
                {"type": "shell_command", "command": "echo '{{ loop.item }}'", "queue_mode": "immediate"},
            ],
        }

        # Queue the foreach step
        queue_executor.queue_step(foreach_step, sample_workflow_state)

        # Process expansion
        expanded_steps = queue_executor.expand_dynamic_step(foreach_step, sample_workflow_state)

        # Verify expansion created individual steps for each item
        assert len(expanded_steps) == 6  # 3 items × 2 steps per item

        # Verify loop context is properly set
        message_steps = [s for s in expanded_steps if s["type"] == "user_message"]
        assert len(message_steps) == 3

        # Check that loop variables are substituted
        messages = [s["message"] for s in message_steps]
        assert "Processing item1" in messages
        assert "Processing item2" in messages
        assert "Processing item3" in messages

        # Verify immediate steps within expansion are properly marked
        immediate_steps = [s for s in expanded_steps if s.get("queue_mode") == "immediate"]
        assert len(immediate_steps) == 3  # One shell_command per item

    def test_wait_queue_mode_coordination(self, queue_executor, sample_workflow_state):
        """
        Test queue mode "wait" for coordinated execution with other queue types
        """
        # Create steps with wait coordination
        steps = [
            {"id": "step1", "type": "shell_command", "queue_mode": "immediate", "command": "echo 'start'"},
            {
                "id": "step2",
                "type": "user_message",
                "queue_mode": "wait",
                "message": "Wait for coordination",
                "wait_for": ["step4"],
            },
            {"id": "step3", "type": "user_message", "queue_mode": "batch", "message": "Batch message"},
            {
                "id": "step4",
                "type": "user_message",
                "queue_mode": "immediate",
                "message": "Synchronization ready",
                "state_update": {"path": "this.sync", "value": "ready"},
            },
            {
                "id": "step5",
                "type": "user_message",
                "queue_mode": "wait",
                "message": "Second wait",
                "wait_for": ["step4"],
            },
        ]

        # Queue all steps
        for step in steps:
            queue_executor.queue_step(step, sample_workflow_state)

        # Process immediate steps first
        immediate_results = []
        while True:
            immediate_step = queue_executor.get_next_immediate_step()
            if not immediate_step:
                break
            immediate_results.append(immediate_step)

        # Should have processed step1 and step4
        assert len(immediate_results) == 2
        immediate_ids = [s["id"] for s in immediate_results]
        assert "step1" in immediate_ids
        assert "step4" in immediate_ids

        # Now wait steps should be ready (their dependencies are complete)
        wait_steps = queue_executor.get_ready_wait_steps()
        assert len(wait_steps) == 2
        wait_ids = [s["id"] for s in wait_steps]
        assert "step2" in wait_ids
        assert "step5" in wait_ids

        # Batch step should still be in regular queue
        batch_steps = queue_executor.get_queued_steps_by_mode("batch")
        assert len(batch_steps) == 1
        assert batch_steps[0]["id"] == "step3"

    def test_queue_timeout_enforcement(self, queue_executor, sample_workflow_state):
        """
        Test queue processing respects 30-second timeout requirement from production
        """
        # Create long-running step simulation
        long_step = {
            "id": "long_step",
            "type": "shell_command",
            "queue_mode": "immediate",
            "command": "sleep 35",  # Exceeds 30s timeout
            "timeout": 30,
        }

        start_time = time.time()

        # Queue the step
        queue_executor.queue_step(long_step, sample_workflow_state)

        # Process with timeout enforcement
        with pytest.raises(TimeoutError) as exc_info:
            queue_executor.process_step_with_timeout(long_step, sample_workflow_state, timeout=30)

        elapsed_time = time.time() - start_time

        # Verify timeout was enforced around 30 seconds (allow some tolerance)
        assert 29 <= elapsed_time <= 32
        assert "timeout" in str(exc_info.value).lower()

    def test_queue_statistics_tracking(self, queue_executor, sample_workflow_state):
        """
        Test queue statistics are properly tracked for monitoring
        """
        # Create various steps to generate statistics
        steps = [
            {"id": "immediate1", "type": "shell_command", "queue_mode": "immediate", "command": "echo 'test'"},
            {"id": "batch1", "type": "user_message", "queue_mode": "batch", "message": "Batch 1"},
            {"id": "batch2", "type": "user_message", "queue_mode": "batch", "message": "Batch 2"},
            {"id": "blocking1", "type": "user_input", "queue_mode": "blocking", "prompt": "Input"},
            {
                "id": "immediate2",
                "type": "user_message",
                "queue_mode": "immediate",
                "message": "Setting variable x",
                "state_update": {"path": "this.x", "value": "1"},
            },
        ]

        # Queue all steps
        for step in steps:
            queue_executor.queue_step(step, sample_workflow_state)

        # Get initial statistics
        stats = queue_executor.get_queue_statistics()

        # Verify queue counts
        assert stats["immediate_queue_size"] == 2
        assert stats["batch_queue_size"] == 2
        assert stats["blocking_queue_size"] == 1
        assert stats["total_queued"] == 5

        # Process some steps and verify statistics update
        immediate_step = queue_executor.get_next_immediate_step()
        queue_executor.mark_step_completed(immediate_step["id"])

        updated_stats = queue_executor.get_queue_statistics()
        assert updated_stats["immediate_queue_size"] == 1
        assert updated_stats["completed_steps"] == 1
        assert updated_stats["total_queued"] == 4


class TestQueueModeIntegration:
    """Test integration between different queue modes in production-like scenarios."""

    @pytest.fixture
    def production_workflow_steps(self):
        """Steps similar to code-standards:enforce.yaml production workflow."""
        return [
            # Initial immediate setup
            {
                "id": "init",
                "type": "user_message",
                "queue_mode": "immediate",
                "message": "Initializing workflow",
                "state_update": {"path": "this.status", "value": "starting"},
            },
            # User communication (batch)
            {
                "id": "start_msg",
                "type": "user_message",
                "queue_mode": "batch",
                "message": "Starting code standards enforcement...",
            },
            # Server-side processing (immediate)
            {"id": "lint", "type": "shell_command", "queue_mode": "immediate", "command": "npm run lint"},
            {"id": "typecheck", "type": "shell_command", "queue_mode": "immediate", "command": "npm run typecheck"},
            {"id": "test", "type": "shell_command", "queue_mode": "immediate", "command": "npm test"},
            # Conditional processing (immediate)
            {
                "id": "check_results",
                "type": "conditional",
                "queue_mode": "immediate",
                "condition": "this.lint_success && this.test_success",
            },
            # User interaction if needed (blocking)
            {
                "id": "user_review",
                "type": "user_input",
                "queue_mode": "blocking",
                "prompt": "Review results and confirm",
                "condition": "!this.all_passed",
            },
            # Final status update (batch)
            {
                "id": "final_msg",
                "type": "user_message",
                "queue_mode": "batch",
                "message": "Code standards check completed",
            },
            # Cleanup (immediate)
            {
                "id": "cleanup",
                "type": "user_message",
                "queue_mode": "immediate",
                "message": "Workflow completed",
                "state_update": {"path": "this.status", "value": "completed"},
            },
        ]

    def test_production_workflow_queue_flow(self, production_workflow_steps):
        """
        Test production workflow queue processing matches expected execution order
        """
        state_manager = Mock(spec=StateManager)
        state_manager.get_flattened_state.return_value = {
            "lint_success": True,
            "test_success": True,
            "all_passed": True,
        }

        step_processor = Mock(spec=StepProcessor)
        step_processor.process_step = AsyncMock(return_value={"status": "completed"})

        queue_executor = QueueBasedWorkflowExecutor(state_manager=state_manager, step_processor=step_processor)

        workflow_state = WorkflowState(
            workflow_id="wf_production",
            status="running",
            current_step_index=0,
            total_steps=len(production_workflow_steps),
            state={"inputs": {}, "state": {}, "computed": {}},
            execution_context={},
        )

        # Queue all workflow steps
        for step in production_workflow_steps:
            queue_executor.queue_step(step, workflow_state)

        execution_order = []

        # Process immediate steps first (should include init, lint, typecheck, test, check_results, cleanup)
        while True:
            immediate_step = queue_executor.get_next_immediate_step()
            if not immediate_step:
                break
            execution_order.append((immediate_step["id"], "immediate"))

        # Process batch steps (should include start_msg, final_msg)
        batch_steps = queue_executor.process_next_batch()
        for step in batch_steps:
            execution_order.append((step["id"], "batch"))

        # Check for blocking steps (user_review should be skipped due to condition)
        blocking_step = queue_executor.get_next_blocking_step()
        if blocking_step:
            execution_order.append((blocking_step["id"], "blocking"))

        # Verify expected execution pattern
        immediate_steps = [item for item in execution_order if item[1] == "immediate"]
        batch_steps = [item for item in execution_order if item[1] == "batch"]

        # Should have processed 6 immediate steps: init, lint, typecheck, test, check_results, cleanup
        assert len(immediate_steps) == 6

        # Should have 2 batch steps: start_msg, final_msg
        assert len(batch_steps) == 2

        # Verify no blocking step due to condition
        blocking_steps = [item for item in execution_order if item[1] == "blocking"]
        assert len(blocking_steps) == 0  # Condition should prevent user_review

        # Verify specific step order for immediate steps
        immediate_ids = [item[0] for item in immediate_steps]
        assert immediate_ids[0] == "init"  # Should be first
        assert "lint" in immediate_ids
        assert "typecheck" in immediate_ids
        assert "test" in immediate_ids
        assert "check_results" in immediate_ids
        assert immediate_ids[-1] == "cleanup"  # Should be last immediate step
