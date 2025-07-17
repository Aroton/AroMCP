"""
Test file for Phase 1: Core State Engine - State Models

Tests the basic state model structures and computed field definitions.
"""

# Import implemented models
from aromcp.workflow_server.state.models import ComputedFieldDefinition, WorkflowState


class TestWorkflowState:
    """Test WorkflowState initialization and structure"""

    def test_workflow_state_initialization(self):
        """Test that WorkflowState initializes with three tiers"""
        # Given
        initial_state = {"raw": {"counter": 0}, "computed": {}, "state": {"version": "1.0"}}

        # When
        workflow_state = WorkflowState(**initial_state)

        # Then
        assert workflow_state.raw["counter"] == 0
        assert workflow_state.computed == {}
        assert workflow_state.state["version"] == "1.0"

    def test_workflow_state_empty_initialization(self):
        """Test WorkflowState can be initialized empty"""
        # When
        workflow_state = WorkflowState(raw={}, computed={}, state={})

        # Then
        assert workflow_state.raw == {}
        assert workflow_state.computed == {}
        assert workflow_state.state == {}

    def test_workflow_state_with_complex_data(self):
        """Test WorkflowState with complex nested data"""
        # Given
        complex_state = {
            "raw": {"counter": 0, "user": {"name": "Alice", "age": 30}, "items": ["a", "b", "c"]},
            "computed": {"double_counter": 0, "user_summary": "Alice (30)"},
            "state": {"version": "1.0", "config": {"debug": True}},
        }

        # When
        workflow_state = WorkflowState(**complex_state)

        # Then
        assert workflow_state.raw["user"]["name"] == "Alice"
        assert workflow_state.raw["items"] == ["a", "b", "c"]
        assert workflow_state.computed["user_summary"] == "Alice (30)"
        assert workflow_state.state["config"]["debug"] is True


class TestComputedFieldDefinition:
    """Test ComputedFieldDefinition structure and validation"""

    def test_computed_field_definition(self):
        """Test computed field definition structure"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["raw.value"], transform="input * 2", on_error="use_fallback", fallback=0
        )

        # Then
        assert field_def.from_paths == ["raw.value"]
        assert field_def.transform == "input * 2"
        assert field_def.on_error == "use_fallback"
        assert field_def.fallback == 0

    def test_computed_field_with_multiple_dependencies(self):
        """Test computed field with multiple from_paths"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["raw.a", "raw.b", "state.c"],
            transform="input[0] + input[1] + input[2]",
            on_error="propagate",
            fallback=None,
        )

        # Then
        assert field_def.from_paths == ["raw.a", "raw.b", "state.c"]
        assert field_def.transform == "input[0] + input[1] + input[2]"
        assert field_def.on_error == "propagate"
        assert field_def.fallback is None

    def test_computed_field_error_strategies(self):
        """Test all error handling strategies are valid"""
        valid_strategies = ["use_fallback", "propagate", "ignore"]

        for strategy in valid_strategies:
            # When
            field_def = ComputedFieldDefinition(
                from_paths=["raw.value"], transform="input", on_error=strategy, fallback="default"
            )

            # Then
            assert field_def.on_error == strategy

    def test_computed_field_complex_transform(self):
        """Test computed field with complex JavaScript transformation"""
        # Given
        field_def = ComputedFieldDefinition(
            from_paths=["raw.items"],
            transform="input.filter(x => x > 5).map(x => x * 2)",
            on_error="use_fallback",
            fallback=[],
        )

        # Then
        assert field_def.transform == "input.filter(x => x > 5).map(x => x * 2)"
        assert field_def.fallback == []
