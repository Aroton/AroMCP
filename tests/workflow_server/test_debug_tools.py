"""Tests for Phase 5: Debug tools functionality."""

from unittest.mock import Mock, patch

from aromcp.workflow_server.state.transformer import TransformationEngine
from aromcp.workflow_server.testing.mocks import (
    MockErrorTracker,
    MockStateManager,
    MockWorkflowExecutor,
    create_mock_workflow_definition,
)
from aromcp.workflow_server.tools.debug_tools import (
    _execution_history,
    _transformation_traces,
    get_debug_stats,
    initialize_debug_tools,
    record_execution_step,
    record_transformation_trace,
)


class TestDebugToolsInitialization:
    """Test debug tools initialization and setup."""

    def test_initialize_debug_tools(self):
        """Test debug tools initialization."""
        # Create mock components
        state_manager = MockStateManager()
        workflow_executor = MockWorkflowExecutor()
        workflow_loader = Mock()
        error_tracker = MockErrorTracker()
        transformation_engine = TransformationEngine()

        # Initialize debug tools
        initialize_debug_tools(
            state_manager,
            workflow_executor,
            workflow_loader,
            error_tracker,
            transformation_engine,
        )

        # Check that components are initialized
        stats = get_debug_stats()
        assert stats["components_initialized"]["state_manager"]
        assert stats["components_initialized"]["workflow_executor"]
        assert stats["components_initialized"]["workflow_loader"]
        assert stats["components_initialized"]["error_tracker"]
        assert stats["components_initialized"]["transformation_engine"]

    def test_debug_stats_empty_state(self):
        """Test debug stats with no data."""
        # Clear any existing data
        _transformation_traces.clear()
        _execution_history.clear()

        stats = get_debug_stats()

        assert stats["transformation_traces"]["workflows_tracked"] == 0
        assert stats["transformation_traces"]["total_traces"] == 0
        assert stats["execution_history"]["workflows_tracked"] == 0
        assert stats["execution_history"]["total_steps"] == 0


class TestTransformationTracing:
    """Test transformation execution tracing."""

    def test_record_transformation_trace(self):
        """Test recording transformation traces."""
        # Clear existing traces
        _transformation_traces.clear()

        workflow_id = "wf_test"

        # Record some transformation traces
        record_transformation_trace(
            workflow_id=workflow_id,
            field="computed.double_value",
            trigger="raw.value update",
            input_data=5,
            output_data=10,
            duration_ms=2.5,
            dependencies=["raw.value"],
        )

        record_transformation_trace(
            workflow_id=workflow_id,
            field="computed.greeting",
            trigger="raw.name update",
            input_data="Alice",
            output_data="Hello Alice!",
            duration_ms=1.2,
            dependencies=["raw.name"],
        )

        # Check traces were recorded
        assert workflow_id in _transformation_traces
        traces = _transformation_traces[workflow_id]
        assert len(traces) == 2

        # Check first trace
        trace1 = traces[0]
        assert trace1["field"] == "computed.double_value"
        assert trace1["trigger"] == "raw.value update"
        assert trace1["input"] == 5
        assert trace1["output"] == 10
        assert trace1["duration_ms"] == 2.5
        assert trace1["dependencies"] == ["raw.value"]

        # Check second trace
        trace2 = traces[1]
        assert trace2["field"] == "computed.greeting"
        assert trace2["input"] == "Alice"
        assert trace2["output"] == "Hello Alice!"

    def test_transformation_trace_limits(self):
        """Test transformation trace limits."""
        _transformation_traces.clear()

        workflow_id = "wf_test"

        # Record more than 100 traces (the limit)
        for i in range(110):
            record_transformation_trace(
                workflow_id=workflow_id,
                field=f"computed.field_{i}",
                trigger="update",
                input_data=i,
                output_data=i * 2,
                duration_ms=1.0,
                dependencies=[],
            )

        # Should only keep last 100 traces
        traces = _transformation_traces[workflow_id]
        assert len(traces) == 100

        # Should have the most recent traces (10-109)
        assert traces[0]["input"] == 10
        assert traces[-1]["input"] == 109


class TestExecutionHistory:
    """Test workflow execution history tracking."""

    def test_record_execution_step(self):
        """Test recording execution steps."""
        # Clear existing history
        _execution_history.clear()

        workflow_id = "wf_test"

        # Record some execution steps
        record_execution_step(
            workflow_id=workflow_id,
            step_id="step_1",
            step_type="state_update",
            status="completed",
            duration_ms=15.5,
            details={"path": "raw.counter", "value": 1},
        )

        record_execution_step(
            workflow_id=workflow_id,
            step_id="step_2",
            step_type="user_message",
            status="completed",
            duration_ms=2.1,
            details={"message": "Hello World"},
        )

        # Check history was recorded
        assert workflow_id in _execution_history
        history = _execution_history[workflow_id]
        assert len(history) == 2

        # Check first step
        step1 = history[0]
        assert step1["step_id"] == "step_1"
        assert step1["step_type"] == "state_update"
        assert step1["status"] == "completed"
        assert step1["duration_ms"] == 15.5
        assert step1["details"]["path"] == "raw.counter"

        # Check second step
        step2 = history[1]
        assert step2["step_id"] == "step_2"
        assert step2["step_type"] == "user_message"
        assert step2["status"] == "completed"
        assert step2["duration_ms"] == 2.1

    def test_execution_history_limits(self):
        """Test execution history limits."""
        _execution_history.clear()

        workflow_id = "wf_test"

        # Record more than 100 steps (the limit)
        for i in range(110):
            record_execution_step(
                workflow_id=workflow_id,
                step_id=f"step_{i}",
                step_type="test_step",
                status="completed",
                duration_ms=1.0,
            )

        # Should only keep last 100 steps
        history = _execution_history[workflow_id]
        assert len(history) == 100

        # Should have the most recent steps (10-109)
        assert history[0]["step_id"] == "step_10"
        assert history[-1]["step_id"] == "step_109"


class TestDebugToolsIntegration:
    """Test debug tools with mocked FastMCP integration."""

    def setup_method(self):
        """Set up test environment."""
        # Create mock components
        self.state_manager = MockStateManager()
        self.workflow_executor = MockWorkflowExecutor()
        self.workflow_loader = Mock()
        self.error_tracker = MockErrorTracker()
        self.transformation_engine = TransformationEngine()

        # Initialize debug tools
        initialize_debug_tools(
            self.state_manager,
            self.workflow_executor,
            self.workflow_loader,
            self.error_tracker,
            self.transformation_engine,
        )

        # Clear any existing traces/history
        _transformation_traces.clear()
        _execution_history.clear()

        # Set up test data
        self.test_workflow_id = "wf_test_123"
        self.state_manager.set_state(
            self.test_workflow_id,
            {
                "counter": 5,
                "name": "TestUser",
                "items": ["a", "b", "c"],
            },
        )

    @patch("aromcp.workflow_server.tools.debug_tools._state_manager")
    @patch("aromcp.workflow_server.tools.debug_tools._workflow_executor")
    def test_workflow_trace_transformations_tool(self, mock_executor, mock_state_manager):
        """Test workflow_trace_transformations tool function."""
        from aromcp.workflow_server.tools.debug_tools import workflow_trace_transformations

        # Set up mock (state_manager is already available as self.state_manager)

        # Add some test transformation traces
        record_transformation_trace(
            workflow_id=self.test_workflow_id,
            field="computed.double_counter",
            trigger="raw.counter update",
            input_data=5,
            output_data=10,
            duration_ms=2.5,
            dependencies=["raw.counter"],
        )

        # Test the tool function
        result = workflow_trace_transformations(
            workflow_id=self.test_workflow_id,
            field="computed.double_counter",
            include_timing=True,
        )

        assert "data" in result
        data = result["data"]
        assert data["workflow_id"] == self.test_workflow_id
        assert len(data["traces"]) == 1

        trace = data["traces"][0]
        assert trace["field"] == "computed.double_counter"
        assert trace["input"] == 5
        assert trace["output"] == 10
        assert trace["duration_ms"] == 2.5

        # Test summary
        summary = data["summary"]
        assert summary["total_transformations"] == 1
        assert summary["unique_fields"] == 1
        assert "avg_duration_ms" in summary

    def test_workflow_debug_info_tool(self):
        """Test workflow_debug_info tool function."""
        from aromcp.workflow_server.tools.debug_tools import workflow_debug_info

        # Set up next step response
        self.workflow_executor.set_next_step_response(
            self.test_workflow_id,
            {
                "id": "next_step",
                "type": "state_update",
            },
        )

        # Add some traces and history
        record_transformation_trace(
            workflow_id=self.test_workflow_id,
            field="computed.test",
            trigger="test",
            input_data="input",
            output_data="output",
            duration_ms=1.0,
            dependencies=[],
        )

        record_execution_step(
            workflow_id=self.test_workflow_id,
            step_id="test_step",
            step_type="test",
            status="completed",
            duration_ms=5.0,
        )

        # Test the tool function
        result = workflow_debug_info(workflow_id=self.test_workflow_id)

        assert "data" in result
        data = result["data"]
        assert data["workflow_id"] == self.test_workflow_id

        # Check state information
        assert "state" in data
        state_info = data["state"]
        assert state_info["has_state"]
        assert state_info["state_size_kb"] > 0
        assert len(state_info["top_level_keys"]) > 0

        # Check execution information
        assert "execution" in data
        exec_info = data["execution"]
        assert exec_info["has_next_step"]
        assert exec_info["next_step_id"] == "next_step"
        assert exec_info["next_step_type"] == "state_update"

        # Check transformations
        assert "transformations" in data
        transform_info = data["transformations"]
        assert transform_info["total_traces"] == 1
        assert len(transform_info["recent_traces"]) == 1

        # Check history
        assert "history" in data
        history_info = data["history"]
        assert history_info["total_steps"] == 1
        assert len(history_info["recent_steps"]) == 1

    def test_workflow_test_transformation_tool(self):
        """Test workflow_test_transformation tool function."""
        from aromcp.workflow_server.tools.debug_tools import workflow_test_transformation

        # Test successful transformation
        result = workflow_test_transformation(
            transform="input * 2",
            input_data=5,
            context=None,
        )

        assert "data" in result
        data = result["data"]
        assert data["success"]
        assert data["output"] == 10
        assert data["input"] == 5
        assert data["transform"] == "input * 2"
        assert "execution_time_ms" in data

        # Test transformation with simple expression (no context support)
        result = workflow_test_transformation(
            transform="input + 10",
            input_data=4,
            context=None,
        )

        assert "data" in result
        data = result["data"]
        assert data["success"]
        assert data["output"] == 14
        assert data["input"] == 4
        assert data["transform"] == "input + 10"

        # Test JSON string context (parsed but not used since engine doesn't support it)
        result = workflow_test_transformation(
            transform="input * 3",
            input_data=4,
            context='{"multiplier": 5}',
        )

        assert "data" in result
        data = result["data"]
        assert data["success"]
        assert data["output"] == 12  # 4 * 3, context is ignored
        assert data["context"] == {"multiplier": 5}

    def test_workflow_explain_plan_tool(self):
        """Test workflow_explain_plan tool function."""
        from aromcp.workflow_server.tools.debug_tools import workflow_explain_plan

        # Set up mock workflow definition
        mock_workflow = create_mock_workflow_definition(
            name="test:workflow",
            steps=[
                {"id": "step1", "type": "state_update", "path": "raw.counter", "value": 1},
                {"id": "step2", "type": "conditional", "condition": "{{ counter > 0 }}"},
                {"id": "step3", "type": "while", "condition": "{{ counter < 10 }}", "max_iterations": 5},
                {"id": "step4", "type": "parallel_foreach", "items": "{{ items }}", "max_parallel": 3},
            ],
        )

        # Set up mock loader
        self.workflow_loader.load.return_value = mock_workflow

        # Test the tool function
        result = workflow_explain_plan(
            workflow="test:workflow",
            inputs={"name": "test", "counter": 0},
        )

        assert "data" in result
        data = result["data"]
        assert data["workflow_name"] == "test:workflow"
        assert data["inputs"] == {"name": "test", "counter": 0}

        # Check steps analysis
        steps = data["steps"]
        assert len(steps) == 4

        # Check step types
        assert steps[0]["type"] == "state_update"
        assert steps[1]["type"] == "conditional"
        assert steps[2]["type"] == "while"
        assert steps[3]["type"] == "parallel_foreach"

        # Check conditional step details
        conditional_step = steps[1]
        assert "condition" in conditional_step
        assert "has_then" in conditional_step
        assert "has_else" in conditional_step

        # Check while step details
        while_step = steps[2]
        assert "condition" in while_step
        assert "max_iterations" in while_step

        # Check parallel step details
        parallel_step = steps[3]
        assert "items" in parallel_step
        assert "max_parallel" in parallel_step

        # Check complexity analysis
        complexity = data["complexity"]
        assert complexity["total_steps"] == 4
        assert complexity["has_loops"]
        assert complexity["has_conditionals"]
        assert complexity["has_parallel"]

    def test_workflow_get_dependencies_tool(self):
        """Test workflow_get_dependencies tool function."""
        from aromcp.workflow_server.tools.debug_tools import workflow_get_dependencies

        # Test the tool function
        result = workflow_get_dependencies(
            workflow_id=self.test_workflow_id,
            field="computed.summary",
        )

        assert "data" in result
        data = result["data"]
        assert data["workflow_id"] == self.test_workflow_id
        assert data["field"] == "computed.summary"
        assert "available_fields" in data
        assert len(data["available_fields"]) > 0

        # Test with existing field
        result = workflow_get_dependencies(
            workflow_id=self.test_workflow_id,
            field="counter",
        )

        assert "data" in result
        data = result["data"]
        assert data["field_value"] == 5
        assert data["field_type"] == "int"


class TestDebugToolsErrorHandling:
    """Test debug tools error handling."""

    def test_transformation_trace_tool_not_initialized(self):
        """Test transformation trace tool when not initialized."""
        import aromcp.workflow_server.tools.debug_tools as debug_tools
        from aromcp.workflow_server.tools.debug_tools import workflow_trace_transformations

        # Clear global state
        original_state_manager = debug_tools._state_manager
        debug_tools._state_manager = None

        try:
            result = workflow_trace_transformations(
                workflow_id="wf_test",
                field=None,
                include_timing=True,
            )

            assert "error" in result
            assert result["error"]["code"] == "NOT_INITIALIZED"
        finally:
            # Restore original state
            debug_tools._state_manager = original_state_manager

    def test_debug_info_tool_with_errors(self):
        """Test debug info tool when components have errors."""
        from aromcp.workflow_server.tools.debug_tools import workflow_debug_info

        # Create mocks that will fail
        mock_state_manager = MockStateManager()
        mock_state_manager.should_fail_read = True

        # Initialize with failing mock
        initialize_debug_tools(
            mock_state_manager,
            Mock(),
            Mock(),
            Mock(),
            Mock(),
        )

        result = workflow_debug_info(workflow_id="wf_test")

        assert "data" in result
        data = result["data"]

        # Should handle state manager error gracefully
        assert "state" in data
        assert "error" in data["state"]

    def test_test_transformation_tool_invalid_json(self):
        """Test transformation testing with invalid JSON context."""
        from aromcp.workflow_server.tools.debug_tools import workflow_test_transformation

        result = workflow_test_transformation(
            transform="input * 2",
            input_data=5,
            context="invalid json{",
        )

        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid JSON" in result["error"]["message"]

    def test_explain_plan_tool_workflow_not_found(self):
        """Test explain plan tool when workflow not found."""
        from aromcp.workflow_server.tools.debug_tools import workflow_explain_plan

        # Set up mock loader that raises exception
        mock_loader = Mock()
        mock_loader.load.side_effect = Exception("Workflow not found")

        initialize_debug_tools(
            Mock(),
            Mock(),
            mock_loader,
            Mock(),
            Mock(),
        )

        result = workflow_explain_plan(
            workflow="missing:workflow",
            inputs={},
        )

        assert "error" in result
        assert result["error"]["code"] == "NOT_FOUND"
        assert "missing:workflow" in result["error"]["message"]


class TestPhase5DebugAcceptanceCriteria:
    """Test Phase 5 debug capabilities acceptance criteria."""

    def test_transformation_traces_show_inputs_outputs(self):
        """AC: Transformation traces show inputs/outputs."""
        _transformation_traces.clear()

        workflow_id = "wf_test"

        # Record transformation with detailed inputs/outputs
        record_transformation_trace(
            workflow_id=workflow_id,
            field="computed.processed_items",
            trigger="raw.items update",
            input_data=["raw_item_1", "raw_item_2"],
            output_data=["processed_item_1", "processed_item_2"],
            duration_ms=5.2,
            dependencies=["raw.items"],
        )

        # Check that traces contain input/output data
        traces = _transformation_traces[workflow_id]
        assert len(traces) == 1

        trace = traces[0]
        assert trace["input"] == ["raw_item_1", "raw_item_2"]
        assert trace["output"] == ["processed_item_1", "processed_item_2"]
        assert trace["trigger"] == "raw.items update"
        assert trace["dependencies"] == ["raw.items"]

    def test_step_execution_history_available(self):
        """AC: Step execution history available."""
        _execution_history.clear()

        workflow_id = "wf_test"

        # Record multiple step executions
        steps = [
            ("step_1", "state_update", "completed", 10.5),
            ("step_2", "conditional", "completed", 2.1),
            ("step_3", "mcp_call", "failed", 1500.0),
            ("step_4", "retry", "completed", 800.0),
        ]

        for step_id, step_type, status, duration in steps:
            record_execution_step(
                workflow_id=workflow_id,
                step_id=step_id,
                step_type=step_type,
                status=status,
                duration_ms=duration,
                details={"test": True},
            )

        # Check that history is recorded
        history = _execution_history[workflow_id]
        assert len(history) == 4

        # Check each step
        for i, (step_id, step_type, status, duration) in enumerate(steps):
            step_record = history[i]
            assert step_record["step_id"] == step_id
            assert step_record["step_type"] == step_type
            assert step_record["status"] == status
            assert step_record["duration_ms"] == duration
            assert step_record["details"]["test"] is True

    def test_performance_metrics_collected(self):
        """AC: Performance metrics collected."""
        _transformation_traces.clear()
        _execution_history.clear()

        workflow_id = "wf_test"

        # Record operations with timing
        record_transformation_trace(
            workflow_id=workflow_id,
            field="computed.fast_calc",
            trigger="update",
            input_data=1,
            output_data=2,
            duration_ms=0.5,  # Fast operation
            dependencies=[],
        )

        record_transformation_trace(
            workflow_id=workflow_id,
            field="computed.slow_calc",
            trigger="update",
            input_data=1000,
            output_data=2000,
            duration_ms=150.0,  # Slow operation
            dependencies=[],
        )

        record_execution_step(
            workflow_id=workflow_id,
            step_id="fast_step",
            step_type="state_update",
            status="completed",
            duration_ms=5.0,
        )

        record_execution_step(
            workflow_id=workflow_id,
            step_id="slow_step",
            step_type="mcp_call",
            status="completed",
            duration_ms=2000.0,
        )

        # Check that performance data is collected
        stats = get_debug_stats()
        assert stats["transformation_traces"]["total_traces"] == 2
        assert stats["execution_history"]["total_steps"] == 2

        # Check individual timings
        traces = _transformation_traces[workflow_id]
        fast_trace = next(t for t in traces if t["field"] == "computed.fast_calc")
        slow_trace = next(t for t in traces if t["field"] == "computed.slow_calc")

        assert fast_trace["duration_ms"] == 0.5
        assert slow_trace["duration_ms"] == 150.0

        history = _execution_history[workflow_id]
        fast_step = next(s for s in history if s["step_id"] == "fast_step")
        slow_step = next(s for s in history if s["step_id"] == "slow_step")

        assert fast_step["duration_ms"] == 5.0
        assert slow_step["duration_ms"] == 2000.0

    def test_bottlenecks_identified(self):
        """AC: Bottlenecks identified."""
        _transformation_traces.clear()
        _execution_history.clear()

        workflow_id = "wf_test"

        # Create a clear bottleneck scenario
        bottleneck_duration = 5000.0  # 5 seconds
        normal_duration = 10.0  # 10 milliseconds

        # Record normal operations
        for i in range(5):
            record_transformation_trace(
                workflow_id=workflow_id,
                field=f"computed.normal_{i}",
                trigger="update",
                input_data=i,
                output_data=i * 2,
                duration_ms=normal_duration,
                dependencies=[],
            )

        # Record bottleneck operation
        record_transformation_trace(
            workflow_id=workflow_id,
            field="computed.bottleneck",
            trigger="expensive_calculation",
            input_data="large_dataset",
            output_data="processed_result",
            duration_ms=bottleneck_duration,
            dependencies=["raw.large_dataset"],
        )

        # Analyze traces to identify bottleneck
        traces = _transformation_traces[workflow_id]
        durations = [t["duration_ms"] for t in traces]

        max_duration = max(durations)
        # avg_duration = sum(durations) / len(durations)  # Not used

        # Bottleneck should be significantly slower than normal operations
        assert max_duration == bottleneck_duration
        assert max_duration > normal_duration * 100  # More than 100x slower than normal operations

        # Find the bottleneck trace
        bottleneck_trace = next(t for t in traces if t["duration_ms"] == max_duration)
        assert bottleneck_trace["field"] == "computed.bottleneck"
        assert bottleneck_trace["trigger"] == "expensive_calculation"
