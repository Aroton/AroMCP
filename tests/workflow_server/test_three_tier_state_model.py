"""
Test suite for Three-Tier State Architecture - Acceptance Criteria 5.1

This file tests the following acceptance criteria:
- AC 5.1: Three-Tier State Architecture - inputs, state, computed tiers with proper precedence
- AC 5.4: Computed Field Processing - recalculation when dependencies change

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import (
    ComputedFieldDefinition,
    InvalidPathError,
    StateSchema,
    WorkflowState,
)


class TestThreeTierStateModel:
    """Test enforcement of the three-tier state model"""

    def test_workflow_state_has_three_tiers(self):
        """Test that WorkflowState only has inputs, state, and computed tiers"""
        # Given
        state = WorkflowState()

        # Then - verify only the three tiers exist
        assert hasattr(state, "inputs")
        assert hasattr(state, "state")
        assert hasattr(state, "computed")

        # Verify no legacy 'raw' attribute exists
        assert not hasattr(state, "raw")

    def test_workflow_state_initialization_with_all_tiers(self):
        """Test WorkflowState initialization with all three tiers"""
        # Given
        initial_data = {
            "inputs": {"user_id": "123", "config": {"debug": True}},
            "state": {"counter": 0, "status": "active"},
            "computed": {"display_name": "User 123", "counter_doubled": 0},
        }

        # When
        state = WorkflowState(**initial_data)

        # Then
        assert state.inputs == {"user_id": "123", "config": {"debug": True}}
        assert state.state == {"counter": 0, "status": "active"}
        assert state.computed == {"display_name": "User 123", "counter_doubled": 0}

    def test_workflow_state_empty_initialization(self):
        """Test WorkflowState initializes with empty dictionaries for all tiers"""
        # When
        state = WorkflowState()

        # Then
        assert state.inputs == {}
        assert state.state == {}
        assert state.computed == {}

    def test_workflow_state_invalid_tier_types_are_corrected(self):
        """Test that invalid types for tiers are corrected to empty dicts"""
        # Given - pass invalid types for tiers
        state = WorkflowState(inputs="invalid_string", state=None, computed=123)

        # Then - should be corrected to empty dicts
        assert state.inputs == {}
        assert state.state == {}
        assert state.computed == {}


class TestDeprecatedRawNamespaceRemoval:
    """Test that deprecated 'raw' namespace is completely removed"""

    def test_workflow_state_no_raw_property(self):
        """Test that WorkflowState no longer has 'raw' property"""
        # Given
        state = WorkflowState()

        # Then
        with pytest.raises(AttributeError):
            _ = state.raw

    def test_workflow_state_no_raw_setter(self):
        """Test that WorkflowState no longer has 'raw' setter"""
        # Given
        state = WorkflowState()

        # Then - setting raw should create a new attribute, not affect inputs
        original_inputs = state.inputs.copy()
        state.raw = {"test": "value"}

        # inputs should be unchanged since raw is no longer a property
        assert state.inputs == original_inputs
        # and raw should just be a regular attribute, not affecting the inputs tier
        assert hasattr(state, "raw")
        assert state.raw == {"test": "value"}

    def test_state_schema_no_raw_property(self):
        """Test that StateSchema no longer has 'raw' property"""
        # Given
        schema = StateSchema()

        # Then
        with pytest.raises(AttributeError):
            _ = schema.raw

    def test_state_schema_no_raw_setter(self):
        """Test that StateSchema no longer has 'raw' setter"""
        # Given
        schema = StateSchema()

        # Then - setting raw should create a new attribute, not affect inputs
        original_inputs = schema.inputs.copy()
        schema.raw = {"test": "str"}

        # inputs should be unchanged since raw is no longer a property
        assert schema.inputs == original_inputs
        # and raw should just be a regular attribute, not affecting the inputs tier
        assert hasattr(schema, "raw")
        assert schema.raw == {"test": "str"}


class TestStateManagerThreeTierEnforcement:
    """Test that StateManager enforces the three-tier model properly"""

    def test_state_manager_only_allows_inputs_and_state_updates(self):
        """Test that StateManager only allows updates to inputs and state tiers"""
        # Given
        manager = StateManager()
        workflow_id = "test_workflow"

        # When/Then - inputs and state updates should be allowed
        assert manager.validate_update_path("inputs.counter") is True
        assert manager.validate_update_path("state.status") is True
        assert manager.validate_update_path("inputs.user.name") is True
        assert manager.validate_update_path("state.config.debug") is True

    def test_state_manager_rejects_computed_updates(self):
        """Test that StateManager rejects updates to computed tier"""
        # Given
        manager = StateManager()

        # When/Then - computed updates should be rejected
        assert manager.validate_update_path("computed.double_counter") is False
        assert manager.validate_update_path("computed.user_summary") is False

    def test_state_manager_rejects_invalid_tier_updates(self):
        """Test that StateManager rejects updates to invalid tiers"""
        # Given
        manager = StateManager()

        # When/Then - invalid tiers should be rejected (but raw is allowed for backward compatibility)
        assert manager.validate_update_path("raw.counter") is True  # Legacy support
        assert manager.validate_update_path("invalid.field") is False
        assert manager.validate_update_path("unknown.value") is False

    def test_state_manager_read_returns_three_tier_structure(self):
        """Test that StateManager read returns proper three-tier structure"""
        # Given
        manager = StateManager()
        workflow_id = "test_workflow"

        # Initialize with some data
        updates = [{"path": "inputs.user_id", "value": "123"}, {"path": "state.counter", "value": 5}]
        manager.update(workflow_id, updates)

        # When
        result = manager.read(workflow_id)

        # Then
        assert "inputs" in result
        assert "state" in result
        assert "computed" in result
        assert result["inputs"]["user_id"] == "123"
        assert result["state"]["counter"] == 5
        assert isinstance(result["computed"], dict)

    def test_state_manager_update_fails_with_invalid_paths(self):
        """Test that StateManager update fails with invalid paths"""
        # Given
        manager = StateManager()
        workflow_id = "test_workflow"

        # When/Then - updating computed should fail
        with pytest.raises(InvalidPathError):
            manager.update(workflow_id, [{"path": "computed.value", "value": 10}])

        # When/Then - updating truly invalid tier should fail (but raw is allowed for backward compatibility)
        with pytest.raises(InvalidPathError):
            manager.update(workflow_id, [{"path": "invalid.value", "value": 10}])

        # Raw should work (legacy support)
        result = manager.update(workflow_id, [{"path": "raw.value", "value": 10}])
        assert result is not None  # Should succeed


class TestComputedFieldErrorHandling:
    """Test computed field error handling strategies"""

    def test_computed_field_use_fallback_strategy(self):
        """Test 'use_fallback' error handling strategy"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["inputs.value"],
            transform="invalid_expression",
            on_error="use_fallback",
            fallback="default_value",
        )

        # Then
        assert field_def.on_error == "use_fallback"
        assert field_def.fallback == "default_value"

    def test_computed_field_propagate_strategy(self):
        """Test 'propagate' error handling strategy"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["inputs.value"], transform="input * 2", on_error="propagate", fallback=None
        )

        # Then
        assert field_def.on_error == "propagate"

    def test_computed_field_ignore_strategy(self):
        """Test 'ignore' error handling strategy"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["inputs.value"], transform="input * 2", on_error="ignore", fallback=None
        )

        # Then
        assert field_def.on_error == "ignore"

    def test_computed_field_invalid_error_strategy_raises_error(self):
        """Test that invalid error strategies raise ValueError"""
        # When/Then
        with pytest.raises(ValueError, match="on_error must be one of"):
            ComputedFieldDefinition(from_paths=["inputs.value"], transform="input * 2", on_error="invalid_strategy")

    def test_computed_field_error_strategies_are_enforced(self):
        """Test that all valid error strategies are accepted"""
        valid_strategies = ["use_fallback", "propagate", "ignore"]

        for strategy in valid_strategies:
            # Should not raise any exception
            field_def = ComputedFieldDefinition(from_paths=["inputs.value"], transform="input * 2", on_error=strategy)
            assert field_def.on_error == strategy


class TestComputedFieldDefinitionValidation:
    """Test validation of ComputedFieldDefinition"""

    def test_computed_field_requires_from_paths(self):
        """Test that from_paths cannot be empty"""
        # When/Then
        with pytest.raises(ValueError, match="from_paths cannot be empty"):
            ComputedFieldDefinition(from_paths=[], transform="input * 2")

    def test_computed_field_requires_transform(self):
        """Test that transform cannot be empty"""
        # When/Then
        with pytest.raises(ValueError, match="transform cannot be empty"):
            ComputedFieldDefinition(from_paths=["inputs.value"], transform="")

    def test_computed_field_with_inputs_paths(self):
        """Test computed field with inputs tier paths"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["inputs.counter", "inputs.multiplier"], transform="input[0] * input[1]"
        )

        # Then
        assert "inputs.counter" in field_def.from_paths
        assert "inputs.multiplier" in field_def.from_paths

    def test_computed_field_with_state_paths(self):
        """Test computed field with state tier paths"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["state.active", "state.count"], transform="input[0] ? input[1] : 0"
        )

        # Then
        assert "state.active" in field_def.from_paths
        assert "state.count" in field_def.from_paths

    def test_computed_field_with_mixed_paths(self):
        """Test computed field with mixed inputs and state paths"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["inputs.base_value", "state.multiplier"], transform="input[0] * input[1]"
        )

        # Then
        assert "inputs.base_value" in field_def.from_paths
        assert "state.multiplier" in field_def.from_paths
