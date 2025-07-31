"""
Comprehensive control flow testing for enhanced functionality.

Covers missing acceptance criteria:
- AC-CF-022: Nested loop break/continue affects only innermost loop
- AC-CF-023: Infinite loop conditions are detected and handled

Focus: Advanced nested loop control, infinite loop detection and diagnostics
Pillar: Control Flow
"""

import tempfile
import time
from pathlib import Path

from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor


class TestControlFlowComprehensive:
    """Test advanced control flow scenarios including nested loops and infinite loop detection."""

    def setup_method(self):
        """Setup test environment for each test."""
        self.executor = WorkflowExecutor()
        self.temp_dir = None
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment after each test."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()
        if self.temp_dir:
            # Temp directory cleanup handled by Python automatically
            pass

    def _create_workflow_file(self, workflow_name: str, workflow_content: str) -> Path:
        """Helper to create a workflow file for testing."""
        if not self.temp_dir:
            self.temp_dir = tempfile.TemporaryDirectory()

        temp_path = Path(self.temp_dir.name)
        workflows_dir = temp_path / ".aromcp" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        workflow_file = workflows_dir / f"{workflow_name}.yaml"
        workflow_file.write_text(workflow_content)
        return temp_path

    def test_nested_loop_break_affects_innermost_only(self):
        """
        Test AC-CF-022: Nested loop break/continue affects only innermost loop.
        Focus: Break statement in inner loop doesn't affect outer loop execution.
        """
        workflow_content = """
name: "test-nested-loop-break"
description: "Test break in nested loops affects only innermost"
version: "1.0.0"

default_state:
  state:
    outer_iterations: []
    inner_iterations: []
    outer_count: 0
    inner_count: 0
    max_outer: 3
    max_inner: 5
    break_at_inner: 2

steps:
  - type: while_loop
    id: outer_loop
    condition: "state.outer_count < state.max_outer"
    max_iterations: 10
    body:
      - type: shell_command
        id: record_outer_start
        command: "echo 'Recording outer start'"
        state_updates:
          - path: "state.outer_iterations"
            value: "[...state.outer_iterations, `outer_${state.outer_count}_start`]"
      
      - type: shell_command
        id: reset_inner_count
        command: "echo 'Resetting inner count'"
        state_updates:
          - path: "state.inner_count"
            value: "0"
      
      - type: while_loop
        id: inner_loop
        condition: "state.inner_count < state.max_inner"
        max_iterations: 10
        body:
          - type: shell_command
            id: record_inner
            command: "echo 'Recording inner iteration'"
            state_updates:
              - path: "state.inner_iterations"
                value: "[...state.inner_iterations, `outer_${state.outer_count}_inner_${state.inner_count}`]"
          
          - type: conditional
            id: check_break_condition
            condition: "state.inner_count == state.break_at_inner"
            then_steps:
              - type: break
                id: break_inner
            
          - type: shell_command
            id: increment_inner
            command: "echo 'Incrementing inner count'"
            state_updates:
              - path: "state.inner_count"
                value: "state.inner_count + 1"
      
      - type: shell_command
        id: record_outer_end
        command: "echo 'Recording outer end'"
        state_updates:
          - path: "state.outer_iterations"
            value: "[...state.outer_iterations, `outer_${state.outer_count}_end`]"
      
      - type: shell_command
        id: increment_outer
        command: "echo 'Incrementing outer count'"
        state_updates:
          - path: "state.outer_count"
            value: "state.outer_count + 1"
"""

        project_path = self._create_workflow_file("test-nested-loop-break", workflow_content)
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-nested-loop-break")

        # Start workflow
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Process server-side steps by calling get_next_step
        while True:
            next_step = self.executor.get_next_step(workflow_id)
            if next_step is None:
                break

        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)

        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"

        state = final_status["state"]["state"]

        # Verify outer loop ran all iterations
        assert state["outer_count"] == 3, "Outer loop should complete all iterations"
        assert len([x for x in state["outer_iterations"] if x.endswith("_start")]) == 3
        assert len([x for x in state["outer_iterations"] if x.endswith("_end")]) == 3

        # Verify inner loop broke at the correct point for each outer iteration
        inner_iter = state["inner_iterations"]

        # For each outer loop iteration, inner loop should break at index 2
        for outer in range(3):
            inner_for_outer = [x for x in inner_iter if x.startswith(f"outer_{outer}_")]
            # Should have iterations 0, 1, 2 (break happens after recording 2)
            assert len(inner_for_outer) == 3, f"Inner loop for outer {outer} should have 3 iterations before break"
            assert f"outer_{outer}_inner_0" in inner_for_outer
            assert f"outer_{outer}_inner_1" in inner_for_outer
            assert f"outer_{outer}_inner_2" in inner_for_outer
            assert f"outer_{outer}_inner_3" not in inner_for_outer, "Should not reach inner_3 due to break"

    def test_nested_loop_continue_isolation(self):
        """
        Test AC-CF-022: Continue in inner loop doesn't affect outer loop.
        Focus: Continue statement skips only current inner loop iteration.
        """
        workflow_content = """
name: "test-nested-loop-continue"
description: "Test continue in nested loops affects only innermost"
version: "1.0.0"

default_state:
  state:
    outer_values: [1, 2, 3]
    inner_values: [10, 20, 30, 40, 50]
    skip_inner_value: 30
    processed_pairs: []
    skipped_pairs: []

steps:
  - type: foreach
    id: outer_foreach
    items: "state.outer_values"
    variable_name: "outer_val"
    body:
      - type: foreach
        id: inner_foreach
        items: "state.inner_values"
        variable_name: "inner_val"
        body:
          - type: conditional
            id: check_skip_condition
            condition: "loop.inner_val === state.skip_inner_value"
            then_steps:
              - type: shell_command
                id: record_skip
                command: "echo 'Recording skipped pair'"
                state_updates:
                  - path: "state.skipped_pairs"
                    value: "[...state.skipped_pairs, `${loop.outer_val}_${loop.inner_val}`]"
              
              - type: continue
                id: continue_inner
          
          - type: shell_command
            id: record_processed
            command: "echo 'Recording processed pair'"
            state_updates:
              - path: "state.processed_pairs"
                value: "[...state.processed_pairs, `${loop.outer_val}_${loop.inner_val}`]"
"""

        project_path = self._create_workflow_file("test-nested-loop-continue", workflow_content)
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-nested-loop-continue")

        # Start workflow
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Process server-side steps by calling get_next_step
        while True:
            next_step = self.executor.get_next_step(workflow_id)
            if next_step is None:
                break

        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)

        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"

        state = final_status["state"]["state"]

        # Verify all outer loop iterations completed
        processed = state["processed_pairs"]
        skipped = state["skipped_pairs"]

        # Should have 3 outer * 5 inner = 15 total iterations
        # But 3 should be skipped (one per outer loop when inner_val = 30)
        assert len(processed) == 12, "Should process 12 pairs (15 total - 3 skipped)"
        assert len(skipped) == 3, "Should skip 3 pairs"

        # Verify specific skipped pairs
        assert "1_30" in skipped
        assert "2_30" in skipped
        assert "3_30" in skipped

        # Verify these were NOT processed
        assert "1_30" not in processed
        assert "2_30" not in processed
        assert "3_30" not in processed

        # Verify all other combinations were processed
        for outer in [1, 2, 3]:
            for inner in [10, 20, 40, 50]:
                assert f"{outer}_{inner}" in processed

    def test_infinite_loop_detection_and_termination(self):
        """
        Test AC-CF-023: Enhanced infinite loop detection with diagnostics.
        Focus: System detects infinite loops and provides diagnostic information.
        """
        workflow_content = """
name: "test-infinite-loop-detection"
description: "Test infinite loop detection and diagnostic reporting"
version: "1.0.0"

default_state:
  state:
    counter: 0
    always_true: true
    loop_data: []
    last_values: []

state_schema:
  computed:
    is_stuck:
      from: ["this.counter"]
      transform: "input[0] > 0 && input[0] % 10 === 0"

steps:
  - type: while_loop
    id: potential_infinite_loop
    condition: "state.always_true"
    max_iterations: 25
    body:
      - type: shell_command
        id: increment_counter
        command: "echo 'Incrementing counter'"
        state_updates:
          - path: "state.counter"
            value: "state.counter + 1"
      
      - type: shell_command
        id: track_iterations
        command: "echo 'Tracking iteration'"
        state_updates:
          - path: "state.loop_data"
            value: "[...state.loop_data, {iteration: state.counter, timestamp: Date.now()}]"
      
      - type: conditional
        id: check_pattern
        condition: "computed.is_stuck"
        then_steps:
          - type: shell_command
            id: record_pattern
            command: "echo 'Recording pattern'"
            state_updates:
              - path: "state.last_values"
                value: "state.loop_data.slice(-5).map(d => d.iteration)"
"""

        project_path = self._create_workflow_file("test-infinite-loop-detection", workflow_content)
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-infinite-loop-detection")

        # Start workflow
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Process server-side steps by calling get_next_step
        while True:
            next_step = self.executor.get_next_step(workflow_id)
            if next_step is None:
                break

        # Wait for completion (should hit max_iterations)
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] in ["completed", "failed"]:
                break
            time.sleep(0.1)

        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)

        # The workflow should complete (not fail) but hit max iterations
        assert final_status["status"] == "completed", "Workflow should complete even when hitting max iterations"

        state = final_status["state"]["state"]

        # Verify loop hit max iterations limit
        assert state["counter"] == 25, "Loop should execute exactly max_iterations times"
        assert len(state["loop_data"]) == 25, "Should have diagnostic data for all iterations"

        # Verify diagnostic information was collected
        assert len(state["last_values"]) > 0, "Should have recorded pattern detection"

        # Verify the loop condition never changed (infinite loop scenario)
        assert state["always_true"] == True, "Loop condition remained true (infinite loop)"

    def test_max_iterations_diagnostic_information(self):
        """
        Test AC-CF-023: Detailed diagnostic info when max iterations reached.
        Focus: System provides useful debugging information for infinite loops.
        """
        workflow_content = """
name: "test-max-iterations-diagnostics"
description: "Test diagnostic information collection for max iterations"
version: "1.0.0"

default_state:
  state:
    iteration_count: 0
    state_snapshots: []
    condition_evaluations: []
    memory_usage: []
    performance_metrics: {}

steps:
  - type: while_loop
    id: diagnostic_loop
    condition: "state.iteration_count < 100"
    max_iterations: 15
    body:
      - type: shell_command
        id: capture_state_snapshot
        command: "echo 'Capturing state snapshot'"
        state_updates:
          - path: "state.state_snapshots"
            value: |
              [...state.state_snapshots.slice(-4), {
                iteration: state.iteration_count,
                timestamp: Date.now(),
                state_size: JSON.stringify(state).length,
                condition_check: state.iteration_count < 100
              }]
      
      - type: shell_command
        id: track_condition
        command: "echo 'Tracking condition'"
        state_updates:
          - path: "state.condition_evaluations"
            value: |
              [...state.condition_evaluations, {
                iteration: state.iteration_count,
                expected_iterations_remaining: 100 - state.iteration_count,
                will_continue: true
              }]
      
      - type: conditional
        id: periodic_diagnostic
        condition: "state.iteration_count % 5 === 0"
        then_steps:
          - type: shell_command
            id: memory_checkpoint
            command: "echo 'Memory checkpoint'"
            state_updates:
              - path: "state.memory_usage"
                value: |
                  [...state.memory_usage, {
                    iteration: state.iteration_count,
                    snapshots_count: state.state_snapshots.length,
                    evaluations_count: state.condition_evaluations.length
                  }]
      
      - type: shell_command
        id: increment_iteration
        command: "echo 'Incrementing iteration'"
        state_updates:
          - path: "state.iteration_count"
            value: "state.iteration_count + 1"
  
  - type: shell_command
    id: compile_diagnostics
    command: "echo 'Compiling diagnostics'"
    state_updates:
      - path: "state.performance_metrics"
        value: |
          {
            total_iterations: state.iteration_count,
            max_iterations_hit: state.iteration_count === 15,
            final_condition_value: state.iteration_count < 100,
            diagnostic_snapshots: state.state_snapshots.length,
            memory_checkpoints: state.memory_usage.length,
            average_state_size: state.state_snapshots.length > 0 
              ? state.state_snapshots.reduce((sum, s) => sum + s.state_size, 0) / state.state_snapshots.length
              : 0
          }
"""

        project_path = self._create_workflow_file("test-max-iterations-diagnostics", workflow_content)
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-max-iterations-diagnostics")

        # Start workflow
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Process server-side steps by calling get_next_step
        while True:
            next_step = self.executor.get_next_step(workflow_id)
            if next_step is None:
                break

        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)

        # Get final state
        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed", f"Workflow failed: {final_status.get('error')}"

        state = final_status["state"]["state"]

        # Verify diagnostic information was collected
        assert state["iteration_count"] == 15, "Should stop at max_iterations"
        assert len(state["condition_evaluations"]) == 15, "Should track all condition evaluations"

        # Verify state snapshots (keeps last 5)
        assert len(state["state_snapshots"]) == 5, "Should keep last 5 snapshots"
        last_snapshot = state["state_snapshots"][-1]
        assert last_snapshot["iteration"] == 14, "Last snapshot should be from iteration 14"
        assert last_snapshot["condition_check"] == True, "Condition was still true when stopped"

        # Verify memory checkpoints (every 5 iterations: 0, 5, 10)
        assert len(state["memory_usage"]) == 3, "Should have 3 memory checkpoints"
        assert state["memory_usage"][0]["iteration"] == 0
        assert state["memory_usage"][1]["iteration"] == 5
        assert state["memory_usage"][2]["iteration"] == 10

        # Verify performance metrics summary
        metrics = state["performance_metrics"]
        assert metrics["total_iterations"] == 15
        assert metrics["max_iterations_hit"] == True
        assert metrics["final_condition_value"] == True, "Condition was still true when max reached"
        assert metrics["diagnostic_snapshots"] == 5
        assert metrics["memory_checkpoints"] == 3
        assert metrics["average_state_size"] > 0, "Should calculate average state size"


class TestNestedLoopEdgeCases:
    """Test edge cases for nested loop control flow."""

    def setup_method(self):
        """Setup test environment."""
        self.executor = WorkflowExecutor()
        self.temp_dir = None
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()

    def _create_workflow_file(self, workflow_name: str, workflow_content: str) -> Path:
        """Helper to create a workflow file for testing."""
        if not self.temp_dir:
            self.temp_dir = tempfile.TemporaryDirectory()

        temp_path = Path(self.temp_dir.name)
        workflows_dir = temp_path / ".aromcp" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        workflow_file = workflows_dir / f"{workflow_name}.yaml"
        workflow_file.write_text(workflow_content)
        return temp_path

    def test_triple_nested_loop_break_continue(self):
        """
        Test AC-CF-022: Break/continue in triple-nested loops.
        Focus: Verify correct isolation of control flow in deeply nested structures.
        """
        workflow_content = """
name: "test-triple-nested-loops"
description: "Test break/continue in triple-nested loop structures"
version: "1.0.0"

default_state:
  state:
    levels: ["A", "B", "C"]
    numbers: [1, 2, 3, 4]
    colors: ["red", "green", "blue"]
    results: []
    skip_combinations: ["B_2_green", "C_3_red"]
    break_combinations: ["A_4_blue", "B_3_blue"]

steps:
  - type: foreach
    id: level_loop
    items: "state.levels"
    variable_name: "level"
    body:
      - type: foreach
        id: number_loop
        items: "state.numbers"
        variable_name: "num"
        body:
          - type: foreach
            id: color_loop
            items: "state.colors"
            variable_name: "color"
            body:
              - type: shell_command
                id: build_combo
                command: "echo 'Building combo'"
                state_updates:
                  - path: "state.current_combo"
                    value: "`${loop.level}_${loop.num}_${loop.color}`"
              
              - type: conditional
                id: check_skip
                condition: "state.skip_combinations.includes(state.current_combo)"
                then_steps:
                  - type: continue
                    id: skip_combo
              
              - type: conditional
                id: check_break
                condition: "state.break_combinations.includes(state.current_combo)"
                then_steps:
                  - type: break
                    id: break_color_loop
              
              - type: shell_command
                id: record_result
                command: "echo 'Recording result'"
                state_updates:
                  - path: "state.results"
                    value: "[...state.results, state.current_combo]"
"""

        project_path = self._create_workflow_file("test-triple-nested-loops", workflow_content)
        loader = WorkflowLoader(project_root=str(project_path))
        workflow_def = loader.load("test-triple-nested-loops")
        result = self.executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Process server-side steps by calling get_next_step
        while True:
            next_step = self.executor.get_next_step(workflow_id)
            if next_step is None:
                break

        # Wait for completion
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.executor.get_workflow_status(workflow_id)
            if status["status"] == "completed":
                break
            time.sleep(0.1)

        final_status = self.executor.get_workflow_status(workflow_id)
        assert final_status["status"] == "completed"

        results = final_status["state"]["state"]["results"]

        # Verify skipped combinations are not in results
        assert "B_2_green" not in results, "Should skip B_2_green"
        assert "C_3_red" not in results, "Should skip C_3_red"

        # Verify break only affected innermost loop
        # A_4_blue should break color loop, so no A_4_blue in results
        assert "A_4_blue" not in results, "Should not process A_4_blue"
        # But A_4_red and A_4_green should be processed
        assert "A_4_red" in results, "Should process colors before break"
        assert "A_4_green" in results, "Should process colors before break"

        # B_3_blue should break color loop for B_3
        assert "B_3_blue" not in results, "Should not process B_3_blue"
        assert "B_3_red" in results, "Should process B_3_red before break"
        assert "B_3_green" in results, "Should process B_3_green before break"

        # Verify other B_4 combinations still processed (break didn't affect number loop)
        assert "B_4_red" in results, "Break in B_3 shouldn't affect B_4"
        assert "B_4_green" in results, "Break in B_3 shouldn't affect B_4"
        assert "B_4_blue" in results, "Break in B_3 shouldn't affect B_4"
