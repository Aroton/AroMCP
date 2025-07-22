"""Integration test for set_variable steps with scoped paths.

Tests that set_variable steps can use the new scoped path syntax:
- this.variable -> workflow state
- global.variable -> execution context global variables
"""

import pytest
from unittest.mock import Mock

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.context import ExecutionContext
from aromcp.workflow_server.workflow.models import WorkflowStep


class TestScopedSetVariableIntegration:
    """Test set_variable step integration with scoped paths."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = StateManager()
        self.workflow_id = "test_workflow"
        self.context = ExecutionContext(self.workflow_id)
        
        # Initialize workflow state
        initial_state = self.manager._get_or_create_state(self.workflow_id)
        self.manager._states[self.workflow_id] = initial_state
    
    def test_set_variable_with_this_scope(self):
        """Test set_variable step with 'this' scoped path."""
        # Simulate a set_variable step
        updates = [{"path": "this.step_result", "value": "completed"}]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify the variable was set in workflow state
        state = self.manager._states[self.workflow_id]
        assert state.state["step_result"] == "completed"
        
        # Should not be in global variables
        assert "step_result" not in self.context.global_variables
    
    def test_set_variable_with_global_scope(self):
        """Test set_variable step with 'global' scoped path.""" 
        # Simulate a set_variable step
        updates = [{"path": "global.shared_counter", "value": 42}]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify the variable was set in global variables
        assert self.context.global_variables["shared_counter"] == 42
        
        # Should not be in workflow state
        state = self.manager._states[self.workflow_id]
        assert "shared_counter" not in state.state
    
    def test_set_variable_mixed_scopes(self):
        """Test set_variable step with mixed scopes."""
        # Simulate multiple set_variable steps
        updates = [
            {"path": "this.local_var", "value": "local_value"},
            {"path": "global.global_var", "value": "global_value"},
            {"path": "state.legacy_var", "value": "legacy_value"}  # Legacy path
        ]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify each variable went to correct location
        state = self.manager._states[self.workflow_id]
        assert state.state["local_var"] == "local_value"
        assert state.state["legacy_var"] == "legacy_value"
        assert self.context.global_variables["global_var"] == "global_value"
    
    def test_set_variable_with_nested_paths(self):
        """Test set_variable step with nested scoped paths."""
        updates = [
            {"path": "this.config.debug", "value": True},
            {"path": "global.settings.timeout", "value": 30}
        ]
        
        result = self.manager.update(self.workflow_id, updates, self.context)
        
        # Verify nested paths work correctly
        state = self.manager._states[self.workflow_id]
        assert state.state["config"]["debug"] is True
        assert self.context.global_variables["settings"]["timeout"] == 30
    
    def test_global_variables_accessible_across_workflows(self):
        """Test that global variables persist and are accessible across different workflows."""
        # Set global variable in one workflow
        updates1 = [{"path": "global.shared_data", "value": {"key": "value"}}]
        self.manager.update(self.workflow_id, updates1, self.context)
        
        # Create second workflow with same context (simulating shared execution context)
        workflow_id_2 = "test_workflow_2"
        context_2 = ExecutionContext(workflow_id_2)
        # In real implementation, global variables would be shared through context manager
        # For this test, simulate by copying
        context_2.global_variables = self.context.global_variables.copy()
        
        # Initialize second workflow state
        initial_state_2 = self.manager._get_or_create_state(workflow_id_2)
        self.manager._states[workflow_id_2] = initial_state_2
        
        # Update global variable and add workflow-specific state from second workflow
        updates2 = [
            {"path": "global.shared_data", "value": {"key": "updated_value"}, "operation": "merge"},
            {"path": "this.workflow_specific", "value": "workflow_2_data"}
        ]
        self.manager.update(workflow_id_2, updates2, context_2)
        
        # Add workflow-specific state to first workflow too
        updates3 = [{"path": "this.workflow_specific", "value": "workflow_1_data"}]
        self.manager.update(self.workflow_id, updates3, self.context)
        
        # Verify global variable was updated
        assert context_2.global_variables["shared_data"]["key"] == "updated_value"
        
        # Workflow-specific state should remain separate
        state_1 = self.manager._states[self.workflow_id]
        state_2 = self.manager._states[workflow_id_2]
        assert state_1.state["workflow_specific"] == "workflow_1_data"
        assert state_2.state["workflow_specific"] == "workflow_2_data"
    
    def test_set_variable_operation_types_with_scoped_paths(self):
        """Test different operation types work with scoped paths."""
        # Set initial values
        initial_updates = [
            {"path": "this.counter", "value": 0},
            {"path": "global.items", "value": ["initial"]}
        ]
        self.manager.update(self.workflow_id, initial_updates, self.context)
        
        # Test increment and append operations
        operation_updates = [
            {"path": "this.counter", "value": 5, "operation": "increment"},
            {"path": "global.items", "value": "appended", "operation": "append"}
        ]
        
        result = self.manager.update(self.workflow_id, operation_updates, self.context)
        
        # Verify operations worked correctly with scoped paths
        state = self.manager._states[self.workflow_id]
        assert state.state["counter"] == 5  # 0 + 5
        assert self.context.global_variables["items"] == ["initial", "appended"]


if __name__ == "__main__":
    pytest.main([__file__])