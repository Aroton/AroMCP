"""
Test file for Phase 1: Core State Engine - State Manager

Tests state management, flattened views, path validation, and atomic updates.
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
            raw={"counter": 5, "name": "test"}, computed={"double": 10, "name": "computed"}, state={"version": "1.0"}
        )
        manager = StateManager()

        # When
        flattened = manager.get_flattened_view(state)

        # Then
        assert flattened["counter"] == 5
        assert flattened["double"] == 10
        assert flattened["name"] == "computed"  # computed takes precedence
        assert flattened["version"] == "1.0"

    def test_flattened_view_precedence_order(self):
        """Test that computed values take precedence over raw and state"""
        # Given
        state = WorkflowState(
            raw={"shared_key": "raw_value", "raw_only": "raw"},
            computed={"shared_key": "computed_value", "computed_only": "computed"},
            state={"shared_key": "state_value", "state_only": "state"},
        )
        manager = StateManager()

        # When
        flattened = manager.get_flattened_view(state)

        # Then
        assert flattened["shared_key"] == "computed_value"  # computed wins
        assert flattened["raw_only"] == "raw"
        assert flattened["computed_only"] == "computed"
        assert flattened["state_only"] == "state"

    def test_flattened_view_with_nested_objects(self):
        """Test flattening with nested objects"""
        # Given
        state = WorkflowState(
            raw={"user": {"name": "Alice", "age": 30}},
            computed={"user": {"name": "Alice Smith", "score": 95}},
            state={"config": {"debug": True}},
        )
        manager = StateManager()

        # When
        flattened = manager.get_flattened_view(state)

        # Then
        # Computed user object should completely replace raw user object
        assert flattened["user"]["name"] == "Alice Smith"
        assert flattened["user"]["score"] == 95
        assert "age" not in flattened["user"]  # Raw user.age not included
        assert flattened["config"]["debug"] is True


class TestStateUpdateValidation:
    """Test path validation for state updates"""

    def test_state_update_validation(self):
        """Test that only raw/state paths can be written"""
        # Given
        manager = StateManager()

        # When/Then - Valid updates
        assert manager.validate_update_path("raw.counter") is True
        assert manager.validate_update_path("state.version") is True
        assert manager.validate_update_path("raw.user.name") is True
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
        assert manager.validate_update_path("raw") is False  # No field specified
        assert manager.validate_update_path("state") is False  # No field specified
        assert manager.validate_update_path("raw.") is False  # Empty field name
        assert manager.validate_update_path("state.") is False  # Empty field name
        assert manager.validate_update_path(".field") is False  # No tier
        assert manager.validate_update_path("raw..field") is False  # Double dot


class TestStateUpdates:
    """Test state update operations"""

    def test_basic_state_update(self):
        """Test basic state update functionality"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When
        manager.update(workflow_id, [{"path": "raw.counter", "value": 10}])
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["counter"] == 10

    def test_multiple_state_updates(self):
        """Test multiple updates in single operation"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When
        manager.update(
            workflow_id,
            [
                {"path": "raw.counter", "value": 10},
                {"path": "state.version", "value": "2.0"},
                {"path": "raw.name", "value": "test"},
            ],
        )
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["counter"] == 10
        assert state["state"]["version"] == "2.0"
        assert state["raw"]["name"] == "test"

    def test_nested_state_updates(self):
        """Test updates to nested object paths"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # When
        manager.update(
            workflow_id,
            [
                {"path": "raw.user.name", "value": "Alice"},
                {"path": "raw.user.age", "value": 30},
                {"path": "state.config.debug", "value": True},
            ],
        )
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["user"]["name"] == "Alice"
        assert state["raw"]["user"]["age"] == 30
        assert state["state"]["config"]["debug"] is True

    def test_update_operations(self):
        """Test different update operations (set, append, increment, merge)"""
        # Given
        manager = StateManager()
        workflow_id = "wf_123"

        # Set initial state
        manager.update(
            workflow_id,
            [
                {"path": "raw.counter", "value": 5},
                {"path": "raw.items", "value": ["a", "b"]},
                {"path": "raw.metadata", "value": {"version": 1}},
            ],
        )

        # When - Apply different operations
        manager.update(
            workflow_id,
            [
                {"path": "raw.counter", "operation": "increment", "value": 3},
                {"path": "raw.items", "operation": "append", "value": "c"},
                {"path": "raw.metadata", "operation": "merge", "value": {"author": "test"}},
            ],
        )
        state = manager.read(workflow_id)

        # Then
        assert state["raw"]["counter"] == 8  # 5 + 3
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
                    {"path": "raw.valid", "value": "good"},
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
                "double": {"from": "raw.value", "transform": "input * 2"},
                "quadruple": {"from": "computed.double", "transform": "input * 2"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_123"

        # When
        manager.update(workflow_id, [{"path": "raw.value", "value": 5}])
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
                "sum": {"from": ["raw.a", "raw.b"], "transform": "input[0] + input[1]"},
                "double_a": {"from": "raw.a", "transform": "input * 2"},
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_123"

        # Set initial state
        manager.update(workflow_id, [{"path": "raw.a", "value": 5}, {"path": "raw.b", "value": 3}])

        # When - Update only one field
        manager.update(workflow_id, [{"path": "raw.a", "value": 10}])
        state = manager.read(workflow_id)

        # Then
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
                    "from": "raw.value",
                    "transform": "JSON.parse(input)",
                    "on_error": "use_fallback",
                    "fallback": {},
                }
            },
        }
        manager = StateManager(schema)
        workflow_id = "wf_123"

        # When - Set invalid JSON
        manager.update(workflow_id, [{"path": "raw.value", "value": "invalid json"}])
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
                {"path": "raw.counter", "value": 10},
                {"path": "raw.name", "value": "test"},
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
        manager.update(workflow_id, [{"path": "raw.existing", "value": "test"}])

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
