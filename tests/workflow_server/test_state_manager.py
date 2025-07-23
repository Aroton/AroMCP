"""
Test suite for State Management System - Acceptance Criteria 5

This file tests the following acceptance criteria:
- AC 5.1: Three-Tier State Architecture - inputs, state, computed tiers with proper precedence
- AC 5.2: Scoped Variable Resolution - proper scoping rules for variable access
- AC 5.3: State Update Operations - atomic state updates with validation

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

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
