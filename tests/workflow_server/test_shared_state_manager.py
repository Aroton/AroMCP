"""
Tests for shared StateManager to ensure consistent state across workflow tools.

This test module verifies that workflow_tools and state_tools use the same
StateManager instance, preventing the NOT_FOUND errors that occurred when
they used separate instances.
"""

import pytest
from aromcp.workflow_server.state.shared import get_shared_state_manager, reset_shared_state_manager
from aromcp.workflow_server.tools.workflow_tools import get_state_manager as get_workflow_state_manager
from aromcp.workflow_server.tools.state_tools import get_state_manager as get_state_state_manager


class TestSharedStateManager:
    """Test shared StateManager consistency across workflow tools."""

    def setup_method(self):
        """Reset shared state before each test."""
        reset_shared_state_manager()

    def test_same_instance_across_modules(self):
        """Test that both modules return the same StateManager instance."""
        # Get StateManager from both modules
        workflow_manager = get_workflow_state_manager()
        state_manager = get_state_state_manager()
        shared_manager = get_shared_state_manager()

        # All should be the same instance
        assert workflow_manager is state_manager
        assert workflow_manager is shared_manager
        assert state_manager is shared_manager

    def test_state_persistence_across_modules(self):
        """Test that state created in one module is accessible in another."""
        workflow_manager = get_workflow_state_manager()
        state_manager = get_state_state_manager()

        # Create state via workflow_tools
        test_workflow_id = "test_workflow_123"
        workflow_manager.update(test_workflow_id, [{"path": "raw.counter", "value": 42}])

        # Read state via state_tools
        state = state_manager.read(test_workflow_id, ["counter"])
        assert state["raw"]["counter"] == 42

    def test_workflow_executor_uses_shared_state(self):
        """Test that WorkflowExecutor uses the shared StateManager."""
        from aromcp.workflow_server.tools.workflow_tools import get_workflow_executor

        executor = get_workflow_executor()
        shared_manager = get_shared_state_manager()

        # WorkflowExecutor should use the shared StateManager
        assert executor.state_manager is shared_manager

    def test_concurrent_state_manager_uses_shared_state(self):
        """Test that ConcurrentStateManager uses the shared StateManager."""
        from aromcp.workflow_server.tools.workflow_tools import get_concurrent_state_manager

        concurrent_manager = get_concurrent_state_manager()
        shared_manager = get_shared_state_manager()

        # ConcurrentStateManager should wrap the shared StateManager
        assert concurrent_manager._base_manager is shared_manager

    def test_multiple_calls_return_same_instance(self):
        """Test that multiple calls to get_shared_state_manager return the same instance."""
        manager1 = get_shared_state_manager()
        manager2 = get_shared_state_manager()
        manager3 = get_shared_state_manager()

        assert manager1 is manager2
        assert manager2 is manager3
        assert manager1 is manager3

    def test_reset_creates_new_instance(self):
        """Test that reset_shared_state_manager creates a new instance."""
        original_manager = get_shared_state_manager()

        # Reset and get new instance
        reset_shared_state_manager()
        new_manager = get_shared_state_manager()

        # Should be different instances
        assert original_manager is not new_manager

    def test_state_isolation_after_reset(self):
        """Test that state is isolated after reset."""
        manager1 = get_shared_state_manager()

        # Create some state
        test_workflow_id = "test_workflow_456"
        manager1.update(test_workflow_id, [{"path": "raw.value", "value": "original"}])

        # Verify state exists
        state1 = manager1.read(test_workflow_id, ["value"])
        assert state1["raw"]["value"] == "original"

        # Reset and get new manager
        reset_shared_state_manager()
        manager2 = get_shared_state_manager()

        # State should not exist in new manager
        with pytest.raises(KeyError, match="not found"):
            manager2.read(test_workflow_id, ["value"])

    def test_complex_state_operations_across_modules(self):
        """Test complex state operations work consistently across modules."""
        workflow_manager = get_workflow_state_manager()
        state_manager = get_state_state_manager()

        test_workflow_id = "complex_test_workflow"

        # Create initial state via workflow_tools
        workflow_manager.update(
            test_workflow_id, [{"path": "raw.items", "value": ["item1", "item2"]}, {"path": "raw.counter", "value": 0}]
        )

        # Update state via state_tools
        state_manager.update(
            test_workflow_id,
            [{"path": "raw.counter", "value": 5}, {"path": "raw.items", "value": "item3", "operation": "append"}],
        )

        # Read final state via workflow_tools
        final_state = workflow_manager.read(test_workflow_id, ["items", "counter"])

        # Should reflect all updates
        assert final_state["raw"]["counter"] == 5
        assert "item3" in final_state["raw"]["items"]
        assert len(final_state["raw"]["items"]) == 3

    def test_error_consistency_across_modules(self):
        """Test that errors are consistent across modules."""
        workflow_manager = get_workflow_state_manager()
        state_manager = get_state_state_manager()

        nonexistent_workflow = "nonexistent_workflow_789"

        # Both managers should raise the same error for nonexistent workflow
        with pytest.raises(KeyError, match="not found"):
            workflow_manager.read(nonexistent_workflow, ["some_field"])

        with pytest.raises(KeyError, match="not found"):
            state_manager.read(nonexistent_workflow, ["some_field"])

    def test_singleton_pattern_thread_safety(self):
        """Test that singleton pattern works correctly with threading."""
        from concurrent.futures import ThreadPoolExecutor

        managers = []

        def get_manager():
            """Function to get manager in thread."""
            managers.append(get_shared_state_manager())

        # Create multiple threads that get the manager
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_manager) for _ in range(50)]
            for future in futures:
                future.result()

        # All managers should be the same instance
        first_manager = managers[0]
        for manager in managers:
            assert manager is first_manager