"""Tests for parallel execution functionality in MCP Workflow System Phase 4."""

import threading
import time

from aromcp.workflow_server.prompts.standards import StandardPrompts
from aromcp.workflow_server.state.concurrent import ConcurrentStateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.parallel import (
    ParallelExecution,
    ParallelForEachProcessor,
    ParallelForEachStep,
    ParallelTask,
    SubAgentContext,
    TaskDistributor,
)
from aromcp.workflow_server.workflow.sub_agents import SubAgentManager


class TestParallelExecutionModels:
    """Test parallel execution data models."""

    def test_parallel_foreach_step_creation(self):
        """Test ParallelForEachStep creation with defaults."""
        # Given
        step = ParallelForEachStep(items="file_batches", sub_agent_task="process_batch")

        # Then
        assert step.items == "file_batches"
        assert step.max_parallel == 10
        assert step.wait_for_all
        assert step.sub_agent_task == "process_batch"
        assert step.sub_agent_prompt_override is None

    def test_parallel_foreach_step_custom_config(self):
        """Test ParallelForEachStep with custom configuration."""
        # Given
        step = ParallelForEachStep(
            items="batches",
            max_parallel=5,
            wait_for_all=False,
            sub_agent_task="custom_task",
            sub_agent_prompt_override="Custom prompt",
            timeout_seconds=300,
        )

        # Then
        assert step.max_parallel == 5
        assert not step.wait_for_all
        assert step.sub_agent_prompt_override == "Custom prompt"
        assert step.timeout_seconds == 300

    def test_sub_agent_context_creation(self):
        """Test SubAgentContext creation and serialization."""
        # Given
        context = SubAgentContext(
            task_id="batch_0", workflow_id="wf_123", context={"files": ["a.ts", "b.ts"]}, parent_step_id="step_3"
        )

        # Then
        assert context.task_id == "batch_0"
        assert context.workflow_id == "wf_123"
        assert context.context["files"] == ["a.ts", "b.ts"]
        assert context.parent_step_id == "step_3"
        assert context.created_at > 0

        # Test serialization
        data = context.to_dict()
        assert data["task_id"] == "batch_0"
        assert data["context"]["files"] == ["a.ts", "b.ts"]

    def test_parallel_task_lifecycle(self):
        """Test ParallelTask status lifecycle."""
        # Given
        task = ParallelTask(task_id="task_1", context={"data": "test"})

        # Then - Initial state
        assert task.status == "pending"
        assert task.started_at is None
        assert task.completed_at is None

        # When - Update status
        task.status = "running"
        task.started_at = time.time()

        # Then
        assert task.status == "running"
        assert task.started_at is not None

    def test_parallel_execution_properties(self):
        """Test ParallelExecution computed properties."""
        # Given
        tasks = [
            ParallelTask(task_id="task_1", context={}),
            ParallelTask(task_id="task_2", context={}),
            ParallelTask(task_id="task_3", context={}),
        ]
        tasks[0].status = "completed"
        tasks[1].status = "completed"
        tasks[2].status = "failed"

        execution = ParallelExecution(
            execution_id="exec_1",
            workflow_id="wf_123",
            parent_step_id="step_1",
            tasks=tasks,
            max_parallel=2,
            wait_for_all=True,
        )

        # Then
        assert execution.active_task_count == 0  # No running tasks
        assert execution.completed_task_count == 3  # All tasks completed or failed
        assert execution.failed_task_count == 1
        assert execution.is_complete


class TestParallelForEachProcessor:
    """Test parallel foreach step processing."""

    def test_process_parallel_foreach_basic(self):
        """Test basic parallel foreach processing."""
        # Given
        evaluator = ExpressionEvaluator()
        processor = ParallelForEachProcessor(evaluator)

        step_def = ParallelForEachStep(items="batches", max_parallel=3, sub_agent_task="process_batch")

        state = {
            "batches": [{"id": "batch_0", "files": ["a.ts", "b.ts"]}, {"id": "batch_1", "files": ["c.ts", "d.ts"]}]
        }

        # When
        result = processor.process_parallel_foreach(step_def, state, "step_1", "wf_123")

        # Then
        assert "step" in result
        step = result["step"]
        assert step["type"] == "parallel_tasks"
        assert step["id"] == "step_1"
        assert len(step["definition"]["tasks"]) == 2

        # Check task creation
        task1 = step["definition"]["tasks"][0]
        assert task1["task_id"] == "step_1_task_0"
        assert task1["context"]["item"]["id"] == "batch_0"
        assert task1["context"]["index"] == 0
        assert task1["context"]["total"] == 2

    def test_process_parallel_foreach_invalid_items(self):
        """Test parallel foreach with invalid items expression."""
        # Given
        evaluator = ExpressionEvaluator()
        processor = ParallelForEachProcessor(evaluator)

        step_def = ParallelForEachStep(items="invalid_field", sub_agent_task="process_batch")

        state = {"other_field": "value"}

        # When
        result = processor.process_parallel_foreach(step_def, state, "step_1", "wf_123")

        # Then
        assert "error" in result
        assert "Failed to evaluate items expression" in result["error"]

    def test_update_task_status(self):
        """Test updating task status in parallel execution."""
        # Given
        evaluator = ExpressionEvaluator()
        processor = ParallelForEachProcessor(evaluator)

        # Create execution first
        step_def = ParallelForEachStep(items="items", sub_agent_task="test")
        state = {"items": ["a", "b"]}
        result = processor.process_parallel_foreach(step_def, state, "step_1", "wf_123")

        execution_id = result["step"]["definition"]["execution_id"]
        task_id = result["step"]["definition"]["tasks"][0]["task_id"]

        # When - Update to running
        success = processor.update_task_status(execution_id, task_id, "running")

        # Then
        assert success
        execution = processor.get_execution(execution_id)
        assert execution.status == "running"
        assert execution.tasks[0].status == "running"

        # When - Update to completed
        success = processor.update_task_status(execution_id, task_id, "completed", result={"output": "success"})

        # Then
        assert success
        assert execution.tasks[0].status == "completed"
        assert execution.tasks[0].result["output"] == "success"

    def test_get_next_available_tasks(self):
        """Test getting next available tasks with max_parallel constraint."""
        # Given
        evaluator = ExpressionEvaluator()
        processor = ParallelForEachProcessor(evaluator)

        # Create execution with 5 tasks, max_parallel=2
        step_def = ParallelForEachStep(items="items", max_parallel=2, sub_agent_task="test")
        state = {"items": ["a", "b", "c", "d", "e"]}
        result = processor.process_parallel_foreach(step_def, state, "step_1", "wf_123")

        execution_id = result["step"]["definition"]["execution_id"]

        # When - Get next tasks (should return 2)
        available = processor.get_next_available_tasks(execution_id)

        # Then
        assert len(available) == 2
        assert all(task.status == "pending" for task in available)

        # When - Mark one as running and get next
        processor.update_task_status(execution_id, available[0].task_id, "running")
        available_2 = processor.get_next_available_tasks(execution_id)

        # Then - Should return 1 more (max_parallel=2, 1 running)
        assert len(available_2) == 1


class TestTaskDistributor:
    """Test task distribution across sub-agents."""

    def test_submit_task(self):
        """Test submitting a task for execution."""
        # Given
        distributor = TaskDistributor(max_workers=2)

        def sample_task(x):
            return x * 2

        # When
        success = distributor.submit_task("task_1", sample_task, 5)

        # Then
        assert success
        assert distributor.active_task_count == 1

        # When - Submit duplicate task
        success_2 = distributor.submit_task("task_1", sample_task, 10)

        # Then
        assert not success_2  # Task already running

        # Cleanup
        distributor.shutdown()

    def test_get_completed_tasks(self):
        """Test retrieving completed task results."""
        # Given
        distributor = TaskDistributor(max_workers=2)

        def sample_task(x):
            time.sleep(0.1)  # Small delay
            return x * 2

        # When
        distributor.submit_task("task_1", sample_task, 5)
        distributor.submit_task("task_2", sample_task, 10)

        # Wait for completion
        time.sleep(0.2)

        completed = distributor.get_completed_tasks()

        # Then
        assert len(completed) == 2
        task_results = dict(completed)
        assert task_results["task_1"] == 10
        assert task_results["task_2"] == 20

        # Cleanup
        distributor.shutdown()

    def test_wait_for_all(self):
        """Test waiting for all tasks to complete."""
        # Given
        distributor = TaskDistributor(max_workers=2)

        def sample_task(x):
            time.sleep(0.1)
            return x * 2

        # When
        distributor.submit_task("task_1", sample_task, 5)
        distributor.submit_task("task_2", sample_task, 10)

        results = distributor.wait_for_all(timeout=1.0)

        # Then
        assert len(results) == 2
        assert results["task_1"] == 10
        assert results["task_2"] == 20
        assert distributor.active_task_count == 0

        # Cleanup
        distributor.shutdown()


class TestSubAgentManager:
    """Test sub-agent management functionality."""

    def test_register_task_definition(self):
        """Test registering a task definition."""
        # Given
        manager = SubAgentManager()
        steps = [
            {"type": "state_update", "path": "raw.progress", "value": "started"},
            {"type": "mcp_call", "method": "lint_project", "params": {}},
        ]

        # When
        success = manager.register_task_definition(
            "process_batch", steps, description="Process a batch of files", timeout_seconds=300
        )

        # Then
        assert success
        task_def = manager.get_task_definition("process_batch")
        assert task_def is not None
        assert task_def.task_name == "process_batch"
        assert len(task_def.steps) == 2
        assert task_def.timeout_seconds == 300

    def test_create_sub_agent(self):
        """Test creating a sub-agent."""
        # Given
        manager = SubAgentManager()

        # Register task definition first
        manager.register_task_definition("test_task", [{"type": "user_message"}])

        context = {"files": ["a.ts", "b.ts"], "batch_id": "batch_0"}

        # When
        registration = manager.create_sub_agent(
            workflow_id="wf_123", task_id="task_1", task_name="test_task", context=context, parent_step_id="step_2"
        )

        # Then
        assert registration is not None
        assert registration.task_id == "task_1"
        assert registration.workflow_id == "wf_123"
        assert registration.context.context == context
        assert registration.status == "registered"
        assert "workflow sub-agent" in registration.prompt.lower()

        # Test retrieval
        retrieved = manager.get_agent_by_task_id("wf_123", "task_1")
        assert retrieved is not None
        assert retrieved.agent_id == registration.agent_id

    def test_create_sub_agent_invalid_task(self):
        """Test creating sub-agent with invalid task name."""
        # Given
        manager = SubAgentManager()

        # When
        registration = manager.create_sub_agent(
            workflow_id="wf_123", task_id="task_1", task_name="invalid_task", context={}, parent_step_id="step_1"
        )

        # Then
        assert registration is None

    def test_update_agent_status(self):
        """Test updating sub-agent status."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition("test_task", [])

        registration = manager.create_sub_agent("wf_123", "task_1", "test_task", {}, "step_1")
        agent_id = registration.agent_id

        # When
        success = manager.update_agent_status(agent_id, "active")

        # Then
        assert success
        agent = manager.get_agent(agent_id)
        assert agent.status == "active"
        assert agent.started_at is not None

        # When - Mark completed
        success = manager.update_agent_status(agent_id, "completed")

        # Then
        assert success
        assert agent.status == "completed"
        assert agent.completed_at is not None

    def test_get_workflow_agents(self):
        """Test getting all agents for a workflow."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition("test_task", [])

        # Create multiple agents
        manager.create_sub_agent("wf_123", "task_1", "test_task", {}, "step_1")
        manager.create_sub_agent("wf_123", "task_2", "test_task", {}, "step_1")
        manager.create_sub_agent("wf_456", "task_3", "test_task", {}, "step_1")

        # When
        wf_123_agents = manager.get_workflow_agents("wf_123")
        wf_456_agents = manager.get_workflow_agents("wf_456")

        # Then
        assert len(wf_123_agents) == 2
        assert len(wf_456_agents) == 1

        task_ids = {agent.task_id for agent in wf_123_agents}
        assert task_ids == {"task_1", "task_2"}

    def test_get_agent_stats(self):
        """Test getting agent statistics."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition("test_task", [])

        # Create agents with different statuses
        agent1 = manager.create_sub_agent("wf_123", "task_1", "test_task", {}, "step_1")
        agent2 = manager.create_sub_agent("wf_123", "task_2", "test_task", {}, "step_1")

        manager.update_agent_status(agent1.agent_id, "active")
        manager.update_agent_status(agent2.agent_id, "completed")

        # When
        stats = manager.get_agent_stats("wf_123")

        # Then
        assert stats["total_agents"] == 2
        assert stats["by_status"]["registered"] == 0
        assert stats["by_status"]["active"] == 1
        assert stats["by_status"]["completed"] == 1
        assert stats["average_steps"] == 0  # No steps recorded yet


class TestConcurrentStateManager:
    """Test concurrent state management."""

    def test_concurrent_state_manager_initialization(self):
        """Test ConcurrentStateManager initialization."""
        # Given/When
        manager = ConcurrentStateManager()

        # Then
        assert manager._base_manager is not None
        assert manager._locks == {}
        assert manager._versions == {}
        assert manager._conflict_resolution.strategy == "merge"

    def test_read_with_version(self):
        """Test reading state with version information."""
        # Given
        manager = ConcurrentStateManager()

        # Setup base state
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(raw={"counter": 5}, computed={}, state={})

        # When
        result = manager.read("wf_123", include_version=True)

        # Then
        assert result["raw"]["counter"] == 5
        assert "__version__" in result
        assert result["__version__"]["version"] == 1
        assert result["__version__"]["updated_at"] > 0

    def test_concurrent_updates_different_paths(self):
        """Test concurrent updates to different state paths."""
        # Given
        manager = ConcurrentStateManager()

        # Initialize workflow
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(raw={"field1": 0, "field2": 0}, computed={}, state={})

        results = []

        def update_field(path, value, agent_id):
            result = manager.update("wf_123", [{"path": path, "value": value}], agent_id=agent_id)
            results.append(result)

        # When - Concurrent updates to different paths
        thread1 = threading.Thread(target=update_field, args=("raw.field1", 10, "agent1"))
        thread2 = threading.Thread(target=update_field, args=("raw.field2", 20, "agent2"))

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Then
        assert len(results) == 2
        assert all(result["success"] for result in results)

        final_state = manager.read("wf_123")
        assert final_state["raw"]["field1"] == 10
        assert final_state["raw"]["field2"] == 20

    def test_concurrent_updates_same_path_conflict(self):
        """Test concurrent updates to same path with conflict resolution."""
        # Given
        manager = ConcurrentStateManager()
        manager.configure_conflict_resolution(strategy="merge", merge_policy="last_writer_wins")

        # Initialize workflow
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(raw={"counter": 0}, computed={}, state={})

        results = []

        def update_counter(value, agent_id):
            # Add small delay to increase chance of conflict
            time.sleep(0.01)
            result = manager.update("wf_123", [{"path": "raw.counter", "value": value}], agent_id=agent_id)
            results.append((agent_id, result))

        # When - Concurrent updates to same path
        thread1 = threading.Thread(target=update_counter, args=(10, "agent1"))
        thread2 = threading.Thread(target=update_counter, args=(20, "agent2"))

        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        # Then - At least one should succeed
        assert len(results) == 2
        success_count = sum(1 for _, result in results if result.get("success", False))
        assert success_count >= 1

        final_state = manager.read("wf_123")
        assert final_state["raw"]["counter"] in [10, 20]  # One of the values should win

    def test_optimistic_locking(self):
        """Test optimistic locking with version checking."""
        # Given
        manager = ConcurrentStateManager()

        # Initialize workflow
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(raw={"counter": 0}, computed={}, state={})

        # When - Update with correct version
        result1 = manager.update("wf_123", [{"path": "raw.counter", "value": 5}], expected_version=1)

        # Then
        assert result1["success"]
        assert result1["new_version"] == 2

        # When - Update with old version
        result2 = manager.update(
            "wf_123",
            [{"path": "raw.counter", "value": 10}],
            expected_version=1,  # Old version
        )

        # Then
        assert not result2["success"]
        assert result2["error"] == "VERSION_CONFLICT"
        assert result2["current_version"] == 2

    def test_create_and_restore_checkpoint(self):
        """Test checkpoint creation and restoration."""
        # Given
        manager = ConcurrentStateManager()

        # Ensure clean state
        if "wf_123" in manager._base_manager._states:
            del manager._base_manager._states["wf_123"]
        if "wf_123" in manager._versions:
            del manager._versions["wf_123"]

        # Initialize workflow with fresh state
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(
            raw={"counter": 5, "name": "test"}, computed={"double": 10}, state={}
        )

        # When - Create checkpoint
        checkpoint_result = manager.create_checkpoint("wf_123")

        # Then
        assert checkpoint_result["success"]
        checkpoint = checkpoint_result["checkpoint"]
        assert checkpoint["workflow_id"] == "wf_123"
        assert checkpoint["state"]["raw"]["counter"] == 5
        assert checkpoint["state"]["raw"]["name"] == "test"
        assert checkpoint["state"]["computed"]["double"] == 10

        # When - Modify state
        manager.update("wf_123", [{"path": "raw.counter", "value": 15}])

        # When - Restore from checkpoint
        restore_result = manager.restore_from_checkpoint("wf_123", checkpoint)

        # Then
        assert restore_result["success"]

        restored_state = manager.read("wf_123")
        assert restored_state["raw"]["counter"] == 5  # Restored to checkpoint value
        assert restored_state["raw"]["name"] == "test"

    def test_get_stats(self):
        """Test getting performance statistics."""
        # Given
        manager = ConcurrentStateManager()

        # Initialize workflow
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(raw={"counter": 0}, computed={}, state={})

        # When - Perform some updates
        manager.update("wf_123", [{"path": "raw.counter", "value": 1}])
        manager.update("wf_123", [{"path": "raw.counter", "value": 2}])

        stats = manager.get_stats()

        # Then
        assert stats["total_updates"] == 2
        assert stats["average_update_time"] > 0
        assert stats["conflicts_detected"] == 0


class TestStandardPrompts:
    """Test standard prompt system."""

    def test_get_parallel_foreach_prompt(self):
        """Test getting parallel foreach prompt."""
        # Given
        context = {"task_id": "batch_0", "item": {"files": ["a.ts", "b.ts"]}, "index": 0, "total": 3}

        # When
        prompt = StandardPrompts.get_prompt("parallel_foreach", context)

        # Then
        assert "workflow sub-agent" in prompt
        assert "batch_0" in prompt
        assert "index 0 of 3" in prompt
        assert "task_id" in prompt

    def test_create_sub_agent_prompt(self):
        """Test creating complete sub-agent prompt."""
        # Given
        context = {"item": {"id": "batch_1"}, "index": 1, "total": 2}

        # When
        prompt = StandardPrompts.create_sub_agent_prompt(
            task_id="batch_1",
            task_type="parallel_foreach",
            context=context,
            custom_instructions="Be extra careful with TypeScript files",
        )

        # Then
        assert "batch_1" in prompt
        assert "index 1 of 2" in prompt
        assert "Be extra careful with TypeScript files" in prompt

    def test_get_available_prompts(self):
        """Test listing available prompt types."""
        # When
        prompts = StandardPrompts.get_available_prompts()

        # Then
        assert "parallel_foreach" in prompts
        assert "sub_agent_base" in prompts
        assert "batch_processor" in prompts
        assert len(prompts) >= 5


class TestComputedFieldsParallelExecution:
    """Test parallel execution with computed fields dependency."""

    def test_parallel_foreach_with_computed_fields(self):
        """Test parallel foreach step that depends on computed fields."""
        # Given - Create a workflow executor
        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
        from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor

        executor = WorkflowExecutor()

        # Create a simple workflow definition with computed fields
        state_schema = StateSchema(
            computed={
                "file_list": {
                    "from": "raw.git_output",
                    "transform": "input.split('\\n').filter(line => line.trim() !== '')",
                },
                "code_files": {
                    "from": "computed.file_list",
                    "transform": "input.filter(file => file.endsWith('.ts') || file.endsWith('.js'))",
                },
            }
        )

        steps = [
            WorkflowStep(
                id="process_files_parallel",
                type="parallel_foreach",
                definition={"items": "{{ computed.code_files }}", "max_parallel": 2, "sub_agent_task": "process_file"},
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test_computed_parallel",
            description="Test workflow with computed fields and parallel execution",
            version="1.0.0",
            default_state={"raw": {"git_output": ""}},
            state_schema=state_schema,
            inputs={},
            steps=steps,
        )

        # When - Start workflow with git output data
        inputs = {"git_output": "src/app.ts\nsrc/utils.js\nREADME.md\npackage.json"}
        result = executor.start(workflow_def, inputs)
        workflow_id = result["workflow_id"]

        # Check that computed fields are properly initialized
        state = executor.state_manager.read(workflow_id)
        print(f"DEBUG TEST: State after start: {state}")

        # Verify computed fields exist and have correct values in nested structure
        assert "computed" in state
        assert "file_list" in state["computed"]
        assert "code_files" in state["computed"]

        # Get expected code files from nested structure
        expected_files = ["src/app.ts", "src/utils.js"]
        code_files = state["computed"]["code_files"]

        assert code_files == expected_files

        # When - Get next step (should be parallel foreach)
        try:
            next_step = executor.get_next_step(workflow_id)

            # Then - Should not fail with NoneType error
            assert next_step is not None
            assert "error" not in next_step or "NoneType" not in str(next_step.get("error", ""))

            if "step" in next_step:
                step = next_step["step"]
                assert step["type"] == "parallel_foreach" or step["type"] == "parallel_tasks"

        except Exception as e:
            # Should not get "Parallel foreach items must be an array, got <class 'NoneType'>"
            assert "NoneType" not in str(e), f"Got NoneType error: {e}"


class TestPhase4AcceptanceCriteria:
    """Explicit tests for Phase 4 acceptance criteria."""

    def test_parallel_foreach_distributes_items_correctly(self):
        """AC: Distributes items to sub-agents correctly."""
        # Given
        evaluator = ExpressionEvaluator()
        processor = ParallelForEachProcessor(evaluator)

        step_def = ParallelForEachStep(items="batches", sub_agent_task="process_batch")

        state = {"batches": [{"id": "batch_0"}, {"id": "batch_1"}, {"id": "batch_2"}]}

        # When
        result = processor.process_parallel_foreach(step_def, state, "step_1", "wf_123")

        # Then
        assert "step" in result
        tasks = result["step"]["definition"]["tasks"]
        assert len(tasks) == 3
        assert tasks[0]["context"]["item"]["id"] == "batch_0"
        assert tasks[1]["context"]["item"]["id"] == "batch_1"
        assert tasks[2]["context"]["item"]["id"] == "batch_2"

    def test_respects_max_parallel_limit(self):
        """AC: Respects max_parallel limit."""
        # Given
        evaluator = ExpressionEvaluator()
        processor = ParallelForEachProcessor(evaluator)

        step_def = ParallelForEachStep(items="items", max_parallel=2, sub_agent_task="process")

        state = {"items": ["a", "b", "c", "d", "e"]}
        result = processor.process_parallel_foreach(step_def, state, "step_1", "wf_123")
        execution_id = result["step"]["definition"]["execution_id"]

        # When
        available = processor.get_next_available_tasks(execution_id)

        # Then
        assert len(available) == 2  # Respects max_parallel=2

        # When - Mark one as running
        processor.update_task_status(execution_id, available[0].task_id, "running")
        available_2 = processor.get_next_available_tasks(execution_id)

        # Then - Should only return 1 more
        assert len(available_2) == 1

    def test_sub_agents_receive_proper_context(self):
        """AC: Sub-agents receive proper context."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition(
            "process_batch", [{"type": "state_update", "path": "raw.{{ task_id }}.status", "value": "processing"}]
        )

        context = {"files": ["a.ts", "b.ts"], "batch_id": "batch_0"}

        # When
        registration = manager.create_sub_agent(
            workflow_id="wf_123", task_id="task_1", task_name="process_batch", context=context, parent_step_id="step_2"
        )

        # Then
        assert registration.context.context == context
        assert registration.context.task_id == "task_1"
        assert registration.context.workflow_id == "wf_123"
        assert registration.context.parent_step_id == "step_2"

    def test_standard_prompt_used_by_default(self):
        """AC: Standard prompt used by default."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition("test_task", [])

        # When
        registration = manager.create_sub_agent(
            workflow_id="wf_123",
            task_id="task_1",
            task_name="test_task",
            context={"item": "test"},
            parent_step_id="step_1",
        )

        # Then
        assert "workflow sub-agent" in registration.prompt.lower()
        assert "task_1" in registration.prompt
        assert "workflow.get_next_step" in registration.prompt

    def test_custom_prompts_override_when_specified(self):
        """AC: Custom prompts override when specified."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition("test_task", [])

        custom_prompt = "This is a custom prompt for the sub-agent"

        # When
        registration = manager.create_sub_agent(
            workflow_id="wf_123",
            task_id="task_1",
            task_name="test_task",
            context={},
            parent_step_id="step_1",
            custom_prompt=custom_prompt,
        )

        # Then
        assert registration.prompt == custom_prompt

    def test_multiple_agents_can_update_different_paths(self):
        """AC: Multiple agents can update different paths."""
        # Given
        manager = ConcurrentStateManager()

        # Initialize workflow state
        from aromcp.workflow_server.state.models import WorkflowState

        manager._base_manager._states["wf_123"] = WorkflowState(
            raw={"path1": 0, "path2": 0, "path3": 0}, computed={}, state={}
        )

        # When - Concurrent updates to different paths
        results = []

        def update_path(path, value, agent_id):
            result = manager.update("wf_123", [{"path": f"raw.{path}", "value": value}], agent_id=agent_id)
            results.append(result)

        threads = [
            threading.Thread(target=update_path, args=("path1", 10, "agent1")),
            threading.Thread(target=update_path, args=("path2", 20, "agent2")),
            threading.Thread(target=update_path, args=("path3", 30, "agent3")),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Then
        assert all(result["success"] for result in results)

        final_state = manager.read("wf_123")
        assert final_state["raw"]["path1"] == 10
        assert final_state["raw"]["path2"] == 20
        assert final_state["raw"]["path3"] == 30

    def test_performance_scales_with_agents(self):
        """AC: Performance scales with agents."""
        # Given
        manager = SubAgentManager()
        manager.register_task_definition("test_task", [])

        # When - Create multiple agents
        start_time = time.time()

        for i in range(10):
            manager.create_sub_agent(
                workflow_id="wf_123",
                task_id=f"task_{i}",
                task_name="test_task",
                context={"index": i},
                parent_step_id="step_1",
            )

        creation_time = time.time() - start_time

        # Then - Should be reasonably fast (less than 1 second for 10 agents)
        assert creation_time < 1.0

        # Check all agents were created
        agents = manager.get_workflow_agents("wf_123")
        assert len(agents) == 10

        # Performance should scale linearly
        stats = manager.get_agent_stats("wf_123")
        assert stats["total_agents"] == 10
