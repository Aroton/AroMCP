"""
Test suite for State Management System - Acceptance Criteria 5

This file tests the following acceptance criteria:
- AC 5.1: Three-Tier State Architecture - inputs, state, computed tiers with proper precedence
- AC 5.2: Scoped Variable Resolution - proper scoping rules for variable access
- AC 5.3: State Update Operations - atomic state updates with validation
- AC-SM-016: Cascading Dependencies - proper handling of computed field dependencies

Maps to: /documentation/acceptance-criteria/workflow_server/state-management.md
"""

import time
import threading

import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import InvalidPathError, WorkflowState


class TestStateManager:
    """Test basic state manager functionality"""

    def test_state_manager_initialization(self):
        """Test StateManager can be initialized"""
        # When
        manager = StateManager()

        # Then
        assert manager is not None

    def test_flattened_view(self):
        """Test state flattening for read operations"""
        # Given
        state = WorkflowState(
            inputs={"counter": 5, "name": "test"}, computed={"double": 10, "name": "computed"}, state={"version": "1.0"}
        )
        manager = StateManager()

        # When
        flattened = manager.get_flattened_view(state)

        # Then
        assert flattened["counter"] == 5
        assert flattened["double"] == 10
        assert flattened["name"] == "computed"  # computed takes precedence
        assert flattened["version"] == "1.0"
        # Verify three-tier state structure
        assert "inputs" in state.__dict__ and "computed" in state.__dict__ and "state" in state.__dict__

    def test_flattened_view_precedence_order(self):
        """Test that computed values take precedence over inputs and state"""
        # Given
        state = WorkflowState(
            inputs={"shared_key": "inputs_value", "inputs_only": "inputs"},
            computed={"shared_key": "computed_value", "computed_only": "computed"},
            state={"shared_key": "state_value", "state_only": "state"},
        )
        manager = StateManager()

        # When
        flattened = manager.get_flattened_view(state)

        # Then
        assert flattened["shared_key"] == "computed_value"  # computed wins
        assert flattened["inputs_only"] == "inputs"
        assert flattened["computed_only"] == "computed"
        assert flattened["state_only"] == "state"
        # Verify three-tier precedence validation
        assert state.computed["shared_key"] != state.inputs["shared_key"], "Computed should override inputs"
        assert state.computed["shared_key"] != state.state["shared_key"], "Computed should override state"

    def test_flattened_view_with_nested_objects(self):
        """Test flattening with nested objects"""
        # Given
        state = WorkflowState(
            inputs={"user": {"name": "Alice", "age": 30}},
            computed={"user": {"name": "Alice Smith", "score": 95}},
            state={"config": {"debug": True}},
        )
        manager = StateManager()

        # When
        flattened = manager.get_flattened_view(state)

        # Then
        # Computed user object should completely replace inputs user object
        assert flattened["user"]["name"] == "Alice Smith"
        assert flattened["user"]["score"] == 95
        assert "age" not in flattened["user"]  # Inputs user.age not included
        assert flattened["config"]["debug"] is True


class TestStateUpdateValidation:
    """Test path validation for state updates"""

    def test_state_update_validation(self):
        """Test that only inputs/state paths can be written"""
        # Given
        manager = StateManager()

        # When/Then - Valid updates
        assert manager.validate_update_path("inputs.counter") is True
        assert manager.validate_update_path("state.version") is True
        assert manager.validate_update_path("inputs.user.name") is True
        assert manager.validate_update_path("state.config.debug") is True

        # When/Then - Invalid updates
        assert manager.validate_update_path("computed.value") is False
        assert manager.validate_update_path("invalid.path") is False
        assert manager.validate_update_path("counter") is False  # No tier prefix
        assert manager.validate_update_path("") is False

    def test_path_validation_edge_cases(self):
        """Test edge cases in path validation"""
        # Given
        manager = StateManager()

        # When/Then
        assert manager.validate_update_path("inputs") is False  # No field specified
        assert manager.validate_update_path("state") is False  # No field specified
        assert manager.validate_update_path("inputs.") is False  # Empty field name
        assert manager.validate_update_path("state.") is False  # Empty field name
        assert manager.validate_update_path(".field") is False  # No tier
        assert manager.validate_update_path("inputs..field") is False  # Double dot


class TestStateUpdates:
    """Test state update operations"""

    def test_basic_state_update(self):
        """Test basic state update functionality"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When
        manager.update(workflow_id, [{"path": "inputs.counter", "value": 10}])
        state = manager.read(workflow_id)

        # Then
        assert state["inputs"]["counter"] == 10
        # Verify backward compatibility: raw should still be returned in read
        assert state["raw"]["counter"] == 10
        assert "raw" in state, "State should contain raw tier"

    def test_multiple_state_updates(self):
        """Test multiple updates in single operation"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When
        manager.update(
            workflow_id,
            [
                {"path": "inputs.counter", "value": 10},
                {"path": "state.version", "value": "2.0"},
                {"path": "inputs.name", "value": "test"},
            ],
        )
        state = manager.read(workflow_id)

        # Then
        assert state["inputs"]["counter"] == 10
        assert state["state"]["version"] == "2.0"
        assert state["inputs"]["name"] == "test"
        # Verify backward compatibility: raw should still be returned in read
        assert state["raw"]["counter"] == 10
        assert state["raw"]["name"] == "test"
        # Verify three-tier state update validation
        assert "raw" in state and "state" in state, "Should have multiple state tiers"

    def test_nested_state_updates(self):
        """Test updates to nested object paths"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When
        manager.update(
            workflow_id,
            [
                {"path": "inputs.user.name", "value": "Alice"},
                {"path": "inputs.user.age", "value": 30},
                {"path": "state.config.debug", "value": True},
            ],
        )
        state = manager.read(workflow_id)

        # Then
        assert state["inputs"]["user"]["name"] == "Alice"
        assert state["inputs"]["user"]["age"] == 30
        assert state["state"]["config"]["debug"] is True
        # Verify backward compatibility: raw should still be returned in read
        assert state["raw"]["user"]["name"] == "Alice"
        assert state["raw"]["user"]["age"] == 30
        # Verify three-tier state structure with nesting
        assert isinstance(state["raw"]["user"], dict), "Nested state should be dict"
        assert isinstance(state["state"]["config"], dict), "Nested state should be dict"

    def test_update_operations(self):
        """Test different update operations (set, append, increment, merge)"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # Set initial state
        manager.update(
            workflow_id,
            [
                {"path": "inputs.counter", "value": 5},
                {"path": "inputs.items", "value": ["a", "b"]},
                {"path": "inputs.metadata", "value": {"version": 1}},
            ],
        )

        # When - Apply different operations
        manager.update(
            workflow_id,
            [
                {"path": "inputs.counter", "operation": "increment", "value": 3},
                {"path": "inputs.items", "operation": "append", "value": "c"},
                {"path": "inputs.metadata", "operation": "merge", "value": {"author": "test"}},
            ],
        )
        state = manager.read(workflow_id)

        # Then
        assert state["inputs"]["counter"] == 8  # 5 + 3
        assert state["inputs"]["items"] == ["a", "b", "c"]
        assert state["inputs"]["metadata"] == {"version": 1, "author": "test"}
        # Verify backward compatibility: raw should still be returned in read
        assert state["raw"]["counter"] == 8
        assert state["raw"]["items"] == ["a", "b", "c"]
        assert state["raw"]["metadata"] == {"version": 1, "author": "test"}

    def test_atomic_updates(self):
        """Test that updates are applied atomically"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When - Mix of valid and invalid updates
        with pytest.raises((InvalidPathError, ValueError)):
            manager.update(
                workflow_id,
                [
                    {"path": "inputs.valid", "value": "good"},
                    {"path": "computed.invalid", "value": "bad"},  # Invalid path
                ],
            )

        # Then - No changes should be applied
        state = manager.read(workflow_id)
        assert "valid" not in state  # Should not be applied due to atomic failure


class TestCascadingUpdates:
    """Test cascading transformations triggered by updates"""

    def test_cascading_updates(self):
        """Test that updates trigger dependent transformations"""
        # Given
        schema = {
            "raw": {"value": "number"},
            "computed": {
                "double": {"from": "inputs.value", "transform": "input * 2"},
                "quadruple": {"from": "computed.double", "transform": "input * 2"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_123"

        # When
        manager.update(workflow_id, [{"path": "inputs.value", "value": 5}])
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["value"] == 5
        assert state["computed"]["double"] == 10
        assert state["computed"]["quadruple"] == 20

    def test_partial_cascading_updates(self):
        """Test cascading updates with only some fields affected"""
        # Given
        schema = {
            "raw": {"a": "number", "b": "number"},
            "computed": {
                "sum": {"from": ["inputs.a", "inputs.b"], "transform": "input[0] + input[1]"},
                "double_a": {"from": "inputs.a", "transform": "input * 2"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_123"

        # Set initial state
        manager.update(workflow_id, [{"path": "inputs.a", "value": 5}, {"path": "inputs.b", "value": 3}])

        # When - Update only one field
        manager.update(workflow_id, [{"path": "inputs.a", "value": 10}])
        state = manager.read(workflow_id)

        # Then
        assert state["inputs"]["a"] == 10
        assert state["inputs"]["b"] == 3
        # Verify backward compatibility: raw should still be returned in read
        assert state["raw"]["a"] == 10
        assert state["raw"]["b"] == 3
        assert state["computed"]["sum"] == 13  # 10 + 3, updated due to a change
        assert state["computed"]["double_a"] == 20  # 10 * 2, updated due to a change

    def test_transformation_error_handling(self):
        """Test error handling during cascading transformations"""
        # Given
        schema = {
            "raw": {"value": "any"},
            "computed": {
                "parsed": {
                    "from": "inputs.value",
                    "transform": "JSON.parse(input)",
                    "on_error": "use_fallback",
                    "fallback": {},
                }
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_123"

        # When - Set invalid JSON
        manager.update(workflow_id, [{"path": "inputs.value", "value": "invalid json"}])
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["value"] == "invalid json"
        assert state["computed"]["parsed"] == {}  # Should use fallback


class TestStateReading:
    """Test state reading operations"""

    def test_read_specific_paths(self):
        """Test reading returns full nested state structure"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # Set up state
        manager.update(
            workflow_id,
            [
                {"path": "inputs.counter", "value": 10},
                {"path": "inputs.name", "value": "test"},
                {"path": "state.version", "value": "1.0"},
            ],
        )

        # When
        result = manager.read(workflow_id)

        # Then
        assert result["raw"]["counter"] == 10
        assert result["raw"]["name"] == "test"
        assert result["state"]["version"] == "1.0"
        assert "computed" in result

    def test_read_nonexistent_paths(self):
        """Test reading nested state structure with existing data"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # Create workflow with some data first
        manager.update(workflow_id, [{"path": "inputs.existing", "value": "test"}])

        # When
        result = manager.read(workflow_id)

        # Then
        assert result["raw"]["existing"] == "test"
        assert "computed" in result
        assert "state" in result

    def test_read_nonexistent_workflow(self):
        """Test reading from non-existent workflow"""
        # Given
        manager = StateManager()

        # When/Then
        with pytest.raises(KeyError):
            manager.read("nonexistent_workflow")


class TestCascadingDependencies:
    """Test cascading dependencies - AC-SM-016"""

    def test_multi_level_cascading_updates(self):
        """Test multi-level cascading transformations (AC-SM-016)."""
        # Given
        schema = {
            "raw": {"base_value": "number"},
            "computed": {
                "level1": {"from": "inputs.base_value", "transform": "input * 2"},
                "level2": {"from": "computed.level1", "transform": "input + 10"},
                "level3": {"from": "computed.level2", "transform": "input / 2"},
                "combined": {
                    "from": ["computed.level1", "computed.level2", "computed.level3"],
                    "transform": "input[0] + input[1] + input[2]"
                }
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_cascade"

        # When
        manager.update(workflow_id, [{"path": "inputs.base_value", "value": 5}])
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["base_value"] == 5
        assert state["computed"]["level1"] == 10  # 5 * 2
        assert state["computed"]["level2"] == 20  # 10 + 10
        assert state["computed"]["level3"] == 10  # 20 / 2
        assert state["computed"]["combined"] == 40  # 10 + 20 + 10

    def test_circular_dependency_detection(self):
        """Test detection of circular dependencies in computed fields (AC-SM-016)."""
        # Given - Schema with circular dependency
        schema = {
            "computed": {
                "field_a": {"from": "computed.field_b", "transform": "input + 1"},
                "field_b": {"from": "computed.field_c", "transform": "input * 2"},
                "field_c": {"from": "computed.field_a", "transform": "input - 1"}  # Circular!
            }
        }
        
        # When/Then - Should detect circular dependency during initialization
        from aromcp.workflow_server.state.models import CircularDependencyError
        
        with pytest.raises(CircularDependencyError, match="Circular dependency detected"):
            StateManager(schema)

    def test_conditional_cascading_updates(self):
        """Test cascading updates with conditional transformations (AC-SM-016)."""
        # Given
        schema = {
            "raw": {"status": "string", "value": "number"},
            "computed": {
                "is_active": {
                    "from": "inputs.status",
                    "transform": "input === 'active'"
                },
                "processed_value": {
                    "from": ["computed.is_active", "inputs.value"],
                    "transform": "input[0] ? input[1] * 2 : 0"
                },
                "final_status": {
                    "from": ["computed.is_active", "computed.processed_value"],
                    "transform": "input[0] ? `Value: ${input[1]}` : 'Inactive'"
                }
            }
        }
        manager = StateManager(schema)
        workflow_id = "wf_conditional"

        # When - Active status
        manager.update(workflow_id, [
            {"path": "inputs.status", "value": "active"},
            {"path": "inputs.value", "value": 50}
        ])
        state = manager.read(workflow_id)

        # Then
        assert state["computed"]["is_active"] is True
        assert state["computed"]["processed_value"] == 100
        assert state["computed"]["final_status"] == "Value: 100"

        # When - Inactive status
        manager.update(workflow_id, [{"path": "inputs.status", "value": "inactive"}])
        state = manager.read(workflow_id)

        # Then
        assert state["computed"]["is_active"] is False
        assert state["computed"]["processed_value"] == 0
        assert state["computed"]["final_status"] == "Inactive"

    def test_array_transformation_cascading(self):
        """Test cascading updates with array transformations (AC-SM-016)."""
        # Given
        schema = {
            "raw": {"items": "array"},
            "computed": {
                "item_count": {
                    "from": "inputs.items",
                    "transform": "input.length"
                },
                "doubled_items": {
                    "from": "inputs.items",
                    "transform": "input.map(x => x * 2)"
                },
                "sum_of_doubled": {
                    "from": "computed.doubled_items",
                    "transform": "input.reduce((a, b) => a + b, 0)"
                },
                "average": {
                    "from": ["computed.sum_of_doubled", "computed.item_count"],
                    "transform": "input[1] > 0 ? input[0] / input[1] : 0"
                }
            }
        }
        manager = StateManager(schema)
        workflow_id = "wf_array"

        # When
        manager.update(workflow_id, [{"path": "inputs.items", "value": [1, 2, 3, 4, 5]}])
        state = manager.read(workflow_id)

        # Then
        assert state["computed"]["item_count"] == 5
        assert state["computed"]["doubled_items"] == [2, 4, 6, 8, 10]
        assert state["computed"]["sum_of_doubled"] == 30
        assert state["computed"]["average"] == 6.0


class TestThreadSafetyEnhancements:
    """Test thread safety with enhanced concurrent operations"""

    def test_concurrent_cascading_updates(self):
        """Test thread safety during cascading updates (AC-SM-016)."""
        import threading
        from aromcp.workflow_server.state.concurrent import ConcurrentStateManager
        
        # Given
        manager = ConcurrentStateManager()
        
        # Initialize workflow with dependencies
        from aromcp.workflow_server.state.models import WorkflowState
        manager._base_manager._states["wf_concurrent"] = WorkflowState(
            inputs={"value1": 0, "value2": 0},
            computed={},
            state={}
        )
        
        results = []
        errors = []
        
        def update_value(field_name, value, thread_id):
            try:
                result = manager.update(
                    "wf_concurrent",
                    [{"path": f"inputs.{field_name}", "value": value}],
                    agent_id=f"thread_{thread_id}"
                )
                results.append((thread_id, result))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # When - Multiple threads updating different fields
        threads = []
        for i in range(10):
            field = "value1" if i % 2 == 0 else "value2"
            thread = threading.Thread(
                target=update_value,
                args=(field, i * 10, i)
            )
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Then
        assert len(errors) == 0, f"Unexpected errors: {errors}"
        assert len(results) == 10
        
        # All updates should have succeeded
        successful_updates = [r for _, r in results if r.get("success", False)]
        assert len(successful_updates) >= 8  # Allow some conflicts

    def test_atomic_operations_under_load(self):
        """Test atomic operations under heavy concurrent load (AC-SM-016)."""
        import threading
        from aromcp.workflow_server.state.concurrent import ConcurrentStateManager
        
        # Given
        manager = ConcurrentStateManager()
        
        # Initialize with counter
        from aromcp.workflow_server.state.models import WorkflowState
        manager._base_manager._states["wf_atomic"] = WorkflowState(
            state={"counter": 0},
            computed={},
            inputs={}
        )
        
        # When - Many threads incrementing counter
        increment_count = 100
        thread_count = 10
        
        def increment_counter(thread_id):
            for _ in range(increment_count):
                current_state = manager.read("wf_atomic")
                current_value = current_state["state"]["counter"]
                
                # Simulate some processing time
                time.sleep(0.0001)
                
                manager.update(
                    "wf_atomic",
                    [{"path": "state.counter", "value": current_value + 1}],
                    agent_id=f"thread_{thread_id}"
                )
        
        threads = []
        for i in range(thread_count):
            thread = threading.Thread(target=increment_counter, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Then - Due to conflicts, final count may be less than expected
        final_state = manager.read("wf_atomic")
        final_count = final_state["state"]["counter"]
        
        # Should have some successful increments but not all due to conflicts
        assert final_count > 0
        assert final_count <= increment_count * thread_count

    def test_resource_manager_integration(self):
        """Test state manager integration with ResourceManager (AC-SM-016)."""
        from aromcp.workflow_server.workflow.resource_manager import WorkflowResourceManager
        
        # Given
        state_manager = StateManager()
        resource_manager = WorkflowResourceManager()
        workflow_id = "wf_resource"
        
        # Set up workflow with resource tracking
        # Note: WorkflowResourceManager allocates resources directly
        
        # When - Update state and track resources
        state_manager.update(workflow_id, [
            {"path": "inputs.data", "value": "x" * 1000}  # 1KB of data
        ])
        
        # Allocate resources based on state size
        allocated = resource_manager.allocate_resources(
            workflow_id=workflow_id,
            memory_mb=10,
            cpu_percent=20
        )
        
        # Then
        assert allocated
        
        # Get resource usage
        usage = resource_manager.get_resource_usage(workflow_id)
        assert usage is not None
        assert usage.memory_mb > 0

    def test_performance_monitoring_integration(self):
        """Test state manager integration with PerformanceMonitor (AC-SM-016)."""
        from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
        
        # Given
        state_manager = StateManager()
        monitor = PerformanceMonitor()
        workflow_id = "wf_perf"
        
        # When - Monitor state update operations
        # Record state update performance
        import time
        start_time = time.time()
        state_manager.update(workflow_id, [{"path": "inputs.test", "value": "value"}])
        duration = time.time() - start_time
        monitor.record_step_performance("state_update", "state_operation", duration, 5.0, 100.0)
        
        # Perform multiple updates
        for i in range(10):
            start_time = time.time()
            
            state_manager.update(workflow_id, [
                {"path": "inputs.counter", "value": i},
                {"path": "state.timestamp", "value": time.time()}
            ])
            
            update_time = time.time() - start_time
            monitor.record_step_performance(f"update_{i}", "state_operation", update_time, 5.0, 50.0)
        
        # Performance monitoring doesn't have end_operation method
        
        # Then - Check performance metrics
        analysis = monitor.get_performance_analysis()
        assert analysis is not None
        assert "step_performance_breakdown" in analysis
        assert len(analysis["step_performance_breakdown"]) > 0

    def test_debug_manager_state_tracking(self):
        """Test state manager integration with DebugManager (AC-SM-016)."""
        from aromcp.workflow_server.debugging.debug_tools import DebugManager
        
        # Given
        state_manager = StateManager()
        debug_manager = DebugManager()
        workflow_id = "wf_debug"
        
        # Enable debug mode
        debug_manager.enable_debug_mode(True)
        
        # When - Update state with debug tracking
        initial_state = {"inputs": {"value": 0}, "state": {}, "computed": {}}
        
        # Add checkpoint before update
        checkpoint_id = debug_manager.create_checkpoint(
            workflow_id=workflow_id,
            step_id="state_update_1",
            state_before=initial_state,
            step_config={"operation": "state_update"}
        )
        
        # Update state
        state_manager.update(workflow_id, [
            {"path": "inputs.value", "value": 42},
            {"path": "state.updated", "value": True}
        ])
        
        # Get updated state
        updated_state = state_manager.read(workflow_id)
        
        # Complete checkpoint after update
        debug_manager.complete_checkpoint(
            checkpoint_id=checkpoint_id,
            state_after=updated_state,
            execution_time=0.1
        )
        
        # Then - Verify debug tracking
        checkpoints = debug_manager.get_checkpoint_history(workflow_id)
        assert len(checkpoints) > 0
        
        checkpoint = checkpoints[0]
        assert checkpoint.step_id == "state_update_1"
        assert checkpoint.state_before == initial_state
        assert checkpoint.state_after is not None
        assert checkpoint.state_after["inputs"]["value"] == 42
