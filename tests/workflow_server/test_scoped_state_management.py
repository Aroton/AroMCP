"""Tests for scoped state management system (Phase 3 of variable scoping).

Tests the enhanced StateManager with support for scoped variable paths:
- this.variable -> state.state (WorkflowState)
- global.variable -> ExecutionContext.global_variables
- inputs.variable -> state.inputs (read-only validation)
- loop.variable -> ExecutionContext current loop (read-only, auto-managed)
"""

import pytest
from unittest.mock import Mock

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import InvalidPathError, WorkflowState
from aromcp.workflow_server.workflow.context import ExecutionContext, StackFrame, LoopState


class TestScopedPathValidation:
    """Test scoped path validation logic."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = StateManager()
    
    def test_valid_scoped_paths(self):
        """Test validation of valid scoped paths."""
        valid_paths = [
            "this.variable",
            "global.counter", 
            "this.user.name",
            "global.config.setting",
            "inputs.test_value",  # Legacy support
            "state.workflow_var",  # Legacy support
            "raw.legacy_value"    # Legacy support (mapped to inputs)
        ]
        
        for path in valid_paths:
            assert self.manager.validate_update_path(path), f"Path {path} should be valid"
    
    def test_invalid_scoped_paths(self):
        """Test validation of invalid scoped paths."""
        invalid_paths = [
            "loop.variable",     # Read-only scope
            "unknown.variable",  # Unknown scope
            "this.",            # Empty field
            "global.",          # Empty field  
            ".variable",        # Empty scope
            "this..nested",     # Double dots
            "global.field.",    # Trailing dot
            "novariable",       # No dot
            "",                 # Empty path
            None               # Null path
        ]
        
        for path in invalid_paths:
            assert not self.manager.validate_update_path(path), f"Path {path} should be invalid"
    
    def test_read_only_scope_validation(self):
        """Test that read-only scopes are properly identified."""
        read_only_paths = [
            "loop.current_item",
            "loop.index",
            "loop.nested.value"
        ]
        
        for path in read_only_paths:
            assert not self.manager.validate_update_path(path), f"Read-only path {path} should be invalid"


class TestScopedStateUpdates:
    """Test scoped state update routing."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = StateManager()
        self.workflow_id = "test_workflow"
        self.context = ExecutionContext(self.workflow_id)
        
        # Initialize workflow state
        initial_state = WorkflowState()
        initial_state.inputs = {"input_value": "test"}
        initial_state.state = {"workflow_var": "initial"}
        self.manager._states[self.workflow_id] = initial_state
    
    def test_this_scope_updates_workflow_state(self):
        """Test that 'this' scope updates route to workflow state."""
        updates = [
            {"path": "this.new_variable", "value": "test_value"},
            {"path": "this.nested.field", "value": 42}
        ]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify updates went to workflow state
        state = self.manager._states[self.workflow_id]
        assert state.state["new_variable"] == "test_value"
        assert state.state["nested"]["field"] == 42
        
        # Verify result contains updated values
        assert "new_variable" in result
        assert result["new_variable"] == "test_value"
    
    def test_global_scope_updates_execution_context(self):
        """Test that 'global' scope updates route to ExecutionContext."""
        updates = [
            {"path": "global.counter", "value": 5},
            {"path": "global.config.debug", "value": True}
        ]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify updates went to global variables
        assert self.context.global_variables["counter"] == 5
        assert self.context.global_variables["config"]["debug"] is True
        
        # Workflow state should not be affected
        state = self.manager._states[self.workflow_id]
        assert "counter" not in state.state
        assert "config" not in state.state
    
    def test_legacy_paths_still_work(self):
        """Test backward compatibility with legacy 'state' and 'inputs' paths."""
        updates = [
            {"path": "state.legacy_var", "value": "legacy_value"},
            {"path": "inputs.input_var", "value": "input_value"}
        ]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify legacy paths work as expected
        state = self.manager._states[self.workflow_id]
        assert state.state["legacy_var"] == "legacy_value"
        assert state.inputs["input_var"] == "input_value"
    
    def test_scoped_operations(self):
        """Test different operations work with scoped paths."""
        # Set up initial values
        initial_updates = [
            {"path": "this.counter", "value": 0},
            {"path": "this.items", "value": ["a"]},
            {"path": "global.config", "value": {"existing": "value"}}
        ]
        self.manager.update(self.workflow_id, initial_updates, self.context)
        
        # Test different operations
        operation_updates = [
            {"path": "this.counter", "value": 5, "operation": "increment"},
            {"path": "this.items", "value": "b", "operation": "append"},
            {"path": "global.config", "value": {"bonus": 5}, "operation": "merge"}
        ]
        
        result = self.manager.update(self.workflow_id, operation_updates, self.context)
        
        # Verify operations worked correctly
        state = self.manager._states[self.workflow_id]
        assert state.state["counter"] == 5  # 0 + 5
        assert state.state["items"] == ["a", "b"]
        
        assert self.context.global_variables["config"]["bonus"] == 5
        assert self.context.global_variables["config"]["existing"] == "value"  # Original value preserved in merge
    
    def test_global_updates_without_context_fail(self):
        """Test that global updates fail without ExecutionContext."""
        updates = [{"path": "global.variable", "value": "test"}]
        
        with pytest.raises(ValueError, match="ExecutionContext required for global variable updates"):
            self.manager.update(self.workflow_id, updates, None)
    
    def test_mixed_scope_updates(self):
        """Test updates across multiple scopes in single operation."""
        updates = [
            {"path": "this.workflow_counter", "value": 1},
            {"path": "global.global_counter", "value": 100},
            {"path": "state.legacy_counter", "value": 999}  # Legacy path
        ]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify each update went to correct storage
        state = self.manager._states[self.workflow_id]
        assert state.state["workflow_counter"] == 1
        assert state.state["legacy_counter"] == 999
        assert self.context.global_variables["global_counter"] == 100


class TestGlobalVariablePersistence:
    """Test global variable persistence across step execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = StateManager()
        self.workflow_id = "test_workflow"
        self.context = ExecutionContext(self.workflow_id)
        
        # Initialize workflow state
        initial_state = WorkflowState()
        self.manager._states[self.workflow_id] = initial_state
    
    def test_global_variables_persist_across_updates(self):
        """Test that global variables persist across multiple update calls."""
        # First update
        updates1 = [{"path": "global.step1_result", "value": "completed"}]
        self.manager.update(self.workflow_id, updates1, self.context)
        
        # Second update
        updates2 = [{"path": "global.step2_result", "value": "also_completed"}]  
        self.manager.update(self.workflow_id, updates2, self.context)
        
        # Both variables should persist
        assert self.context.global_variables["step1_result"] == "completed"
        assert self.context.global_variables["step2_result"] == "also_completed"
    
    def test_global_variables_accessible_across_contexts(self):
        """Test that global variables are accessible across different execution contexts."""
        # Set global variable
        updates = [{"path": "global.shared_config", "value": {"debug": True, "timeout": 30}}]
        self.manager.update(self.workflow_id, updates, self.context)
        
        # Create new context for same workflow 
        new_context = ExecutionContext(self.workflow_id)
        # In real implementation, global variables would be shared through context manager
        # For this test, simulate by copying
        new_context.global_variables = self.context.global_variables.copy()
        
        # Access should work
        assert new_context.global_variables["shared_config"]["debug"] is True
        assert new_context.global_variables["shared_config"]["timeout"] == 30


class TestScopedPathErrorHandling:
    """Test error handling for scoped path operations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = StateManager()
        self.workflow_id = "test_workflow"
        self.context = ExecutionContext(self.workflow_id)
        
        # Initialize workflow state
        initial_state = WorkflowState()
        self.manager._states[self.workflow_id] = initial_state
    
    def test_invalid_scoped_path_raises_error(self):
        """Test that invalid scoped paths raise InvalidPathError."""
        updates = [{"path": "unknown.variable", "value": "test"}]
        
        with pytest.raises(InvalidPathError, match="Invalid update path"):
            self.manager.update(self.workflow_id, updates, self.context)
    
    def test_read_only_scope_access_blocked(self):
        """Test that attempts to write to read-only scopes are blocked."""
        updates = [{"path": "loop.current_item", "value": "should_fail"}]
        
        with pytest.raises(InvalidPathError, match="Invalid update path"):
            self.manager.update(self.workflow_id, updates, self.context)
    
    def test_malformed_scoped_path_handling(self):
        """Test handling of malformed scoped paths."""
        malformed_updates = [
            {"path": "this.", "value": "empty_field"},
            {"path": ".variable", "value": "empty_scope"},
            {"path": "this..nested", "value": "double_dots"}
        ]
        
        for update in malformed_updates:
            with pytest.raises(InvalidPathError):
                self.manager.update(self.workflow_id, [update], self.context)
    
    def test_atomic_failure_with_scoped_paths(self):
        """Test that failures in scoped updates are atomic."""
        # Mix valid and invalid updates
        updates = [
            {"path": "this.valid_var", "value": "should_not_persist"},
            {"path": "global.also_valid", "value": "should_not_persist"},
            {"path": "invalid_scope.variable", "value": "will_fail"}
        ]
        
        with pytest.raises(InvalidPathError):
            self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify no updates were applied
        state = self.manager._states[self.workflow_id]
        assert "valid_var" not in state.state
        assert "also_valid" not in self.context.global_variables


class TestScopedVariableIntegration:
    """Test integration of scoped variables with ExecutionContext."""
    
    def setup_method(self):
        """Set up test fixtures.""" 
        self.manager = StateManager()
        self.workflow_id = "test_workflow"
        self.context = ExecutionContext(self.workflow_id)
        
        # Initialize workflow state
        initial_state = WorkflowState()
        self.manager._states[self.workflow_id] = initial_state
    
    def test_execution_context_scoped_variables_method(self):
        """Test ExecutionContext.get_scoped_variables() method."""
        # Set up test data
        self.context.global_variables = {"global_var": "global_value"}
        
        # Create frame with local variables
        frame = StackFrame(
            frame_id="test_frame",
            frame_type="workflow",
            local_variables={"local_var": "local_value"}
        )
        self.context.push_frame(frame)
        
        # Create loop with variables
        loop_state = LoopState(
            loop_id="test_loop",
            loop_type="foreach",
            variable_bindings={"loop.item": "item1", "loop.index": 0}
        )
        self.context.enter_loop(loop_state)
        
        # Get scoped variables
        scoped_vars = self.context.get_scoped_variables()
        
        # Verify all scopes are present
        assert scoped_vars["global"]["global_var"] == "global_value"
        assert scoped_vars["local"]["local_var"] == "local_value"
        assert scoped_vars["loop"]["loop.item"] == "item1"
        assert scoped_vars["loop"]["loop.index"] == 0
    
    def test_execution_context_global_variable_methods(self):
        """Test ExecutionContext global variable helper methods.""" 
        # Test setting global variables
        self.context.set_global_variable("test_var", "test_value")
        assert self.context.global_variables["test_var"] == "test_value"
        
        # Test getting global variables
        result = self.context.get_global_variable("test_var")
        assert result == "test_value"
        
        # Test getting with default
        result = self.context.get_global_variable("nonexistent", "default_value")
        assert result == "default_value"


class TestBackwardCompatibility:
    """Test backward compatibility with existing state management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = StateManager()
        self.workflow_id = "test_workflow"
        
        # Initialize workflow state 
        initial_state = WorkflowState()
        initial_state.inputs = {"legacy_input": "test"}
        initial_state.state = {"legacy_state": "test"}
        self.manager._states[self.workflow_id] = initial_state
    
    def test_legacy_path_updates_work(self):
        """Test that legacy path format still works."""
        updates = [
            {"path": "inputs.new_input", "value": "new_value"},
            {"path": "state.new_state", "value": "state_value"}
        ]
        
        result = self.manager.update(self.workflow_id, updates)
        
        # Verify legacy paths work
        state = self.manager._states[self.workflow_id]
        assert state.inputs["new_input"] == "new_value"
        assert state.state["new_state"] == "state_value"
    
    def test_legacy_and_scoped_paths_mixed(self):
        """Test mixing legacy and scoped paths in same update."""
        context = ExecutionContext(self.workflow_id)
        
        updates = [
            {"path": "state.legacy_var", "value": "legacy"},      # Legacy
            {"path": "this.scoped_var", "value": "scoped"},       # New scoped (same target)
            {"path": "global.global_var", "value": "global"}     # New global
        ]
        
        result = self.manager.update(self.workflow_id, updates, context)
        
        # Verify both formats work together
        state = self.manager._states[self.workflow_id]
        assert state.state["legacy_var"] == "legacy"
        assert state.state["scoped_var"] == "scoped"
        assert context.global_variables["global_var"] == "global"
    
    def test_existing_api_compatibility(self):
        """Test that existing API calls without context still work."""
        updates = [{"path": "state.test_var", "value": "test_value"}]
        
        # This should work without context (legacy behavior)
        result = self.manager.update(self.workflow_id, updates)
        
        state = self.manager._states[self.workflow_id]
        assert state.state["test_var"] == "test_value"
    
    def test_validation_backward_compatibility(self):
        """Test that legacy path validation still works."""
        # These should still be valid
        assert self.manager.validate_update_path("inputs.variable")
        assert self.manager.validate_update_path("state.variable")
        assert self.manager.validate_update_path("raw.variable")  # Legacy raw support
        
        # These should still be invalid
        assert not self.manager.validate_update_path("computed.variable")
        assert not self.manager.validate_update_path("invalid_format")


if __name__ == "__main__":
    pytest.main([__file__])