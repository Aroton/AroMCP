"""Tests for pending actions manager."""

import pytest
import threading
import time
from datetime import datetime, timedelta

from aromcp.workflow_server.pending_actions import PendingActionsManager, get_pending_actions_manager
from aromcp.workflow_server.models.workflow_models import PendingAction


class TestPendingActionsManager:
    """Test class for PendingActionsManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = PendingActionsManager(max_capacity=5)

    def test_basic_operations(self):
        """Test basic add/get/remove operations."""
        action = PendingAction(
            workflow_id="wf-1",
            step_id="step-1",
            action_type="shell",
            parameters={"command": "echo hello"}
        )
        
        # Test add
        self.manager.add_action(action)
        assert len(self.manager._actions) == 1
        
        # Test get
        retrieved = self.manager.get_action("wf-1")
        assert retrieved is not None
        assert retrieved.workflow_id == "wf-1"
        assert retrieved.step_id == "step-1"
        
        # Test remove
        self.manager.remove_action("wf-1")
        assert self.manager.get_action("wf-1") is None
        assert len(self.manager._actions) == 0

    def test_capacity_management(self):
        """Test that capacity limits are enforced with LRU eviction."""
        # Add actions up to capacity
        for i in range(5):
            action = PendingAction(
                workflow_id=f"wf-{i}",
                step_id=f"step-{i}",
                action_type="shell",
                parameters={"command": f"echo {i}"}
            )
            self.manager.add_action(action)
            time.sleep(0.01)  # Ensure different timestamps
        
        assert len(self.manager._actions) == 5
        
        # Add one more - should evict oldest
        new_action = PendingAction(
            workflow_id="wf-new",
            step_id="step-new",
            action_type="shell",
            parameters={"command": "echo new"}
        )
        self.manager.add_action(new_action)
        
        assert len(self.manager._actions) == 5
        assert self.manager.get_action("wf-0") is None  # Oldest should be evicted
        assert self.manager.get_action("wf-new") is not None  # New should be present

    def test_update_operation(self):
        """Test updating existing pending actions."""
        action = PendingAction(
            workflow_id="wf-1",
            step_id="step-1",
            action_type="shell",
            parameters={"command": "echo hello"}
        )
        self.manager.add_action(action)
        
        # Update the action
        updated = self.manager.update_action(
            "wf-1", 
            step_id="step-2", 
            action_type="mcp_call", 
            parameters={"tool": "list_files"}
        )
        assert updated is True
        
        retrieved = self.manager.get_action("wf-1")
        assert retrieved.step_id == "step-2"
        assert retrieved.action_type == "mcp_call"

    def test_expiration_cleanup(self):
        """Test that expired actions are cleaned up."""
        # Create action with short timeout
        action = PendingAction(
            workflow_id="wf-1",
            step_id="step-1",
            action_type="shell",
            parameters={"command": "echo hello"},
            timeout=1  # 1 second timeout
        )
        # Set created_at to past
        action.created_at = datetime.now() - timedelta(seconds=2)
        
        self.manager.add(action)
        assert self.manager.count() == 1
        
        # Clean up expired actions
        cleaned = self.manager.cleanup_expired()
        assert cleaned == 1
        assert self.manager.count() == 0

    def test_list_operations(self):
        """Test list_all and list_for_workflow operations."""
        # Add multiple actions
        for i in range(3):
            action = PendingAction(
                workflow_id=f"wf-{i}",
                step_id=f"step-{i}",
                action_type="shell",
                parameters={"command": f"echo {i}"}
            )
            self.manager.add(action)
        
        # Test list_all
        all_actions = self.manager.list_all()
        assert len(all_actions) == 3
        
        # Test list_for_workflow (not implemented in current version, but we can test the structure)
        action_for_wf1 = self.manager.get("wf-1")
        assert action_for_wf1 is not None

    def test_thread_safety(self):
        """Test thread-safe operations."""
        def add_actions(start_idx, count):
            for i in range(start_idx, start_idx + count):
                action = PendingAction(
                    workflow_id=f"wf-{i}",
                    step_id=f"step-{i}",
                    action_type="shell",
                    parameters={"command": f"echo {i}"}
                )
                self.manager.add(action)
        
        # Start multiple threads adding actions
        threads = []
        for i in range(3):
            thread = threading.Thread(target=add_actions, args=(i * 10, 5))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Should have actions from all threads (limited by capacity)
        assert self.manager.count() == 5  # Limited by max_actions

    def test_statistics(self):
        """Test statistics functionality."""
        # Add some actions
        for i in range(3):
            action = PendingAction(
                workflow_id=f"wf-{i}",
                step_id=f"step-{i}",
                action_type="shell" if i % 2 == 0 else "mcp_call",
                parameters={"command": f"echo {i}"}
            )
            self.manager.add(action)
        
        stats = self.manager.get_statistics()
        assert stats["total_actions"] == 3
        assert "action_types" in stats
        assert stats["action_types"]["shell"] >= 1
        assert stats["action_types"]["mcp_call"] >= 1

    def test_clear_all(self):
        """Test clearing all actions."""
        # Add some actions
        for i in range(3):
            action = PendingAction(
                workflow_id=f"wf-{i}",
                step_id=f"step-{i}",
                action_type="shell",
                parameters={"command": f"echo {i}"}
            )
            self.manager.add(action)
        
        assert self.manager.count() == 3
        
        # Clear all
        cleared = self.manager.clear_all()
        assert cleared == 3
        assert self.manager.count() == 0


class TestGlobalPendingActionsManager:
    """Test global pending actions manager singleton."""

    def test_global_manager_singleton(self):
        """Test that global manager is a singleton."""
        manager1 = get_pending_actions_manager()
        manager2 = get_pending_actions_manager()
        
        assert manager1 is manager2

    def test_global_manager_functionality(self):
        """Test that global manager works correctly."""
        manager = get_pending_actions_manager()
        
        action = PendingAction(
            workflow_id="global-test",
            step_id="step-1",
            action_type="shell",
            parameters={"command": "echo global"}
        )
        
        manager.add(action)
        retrieved = manager.get("global-test")
        assert retrieved is not None
        assert retrieved.workflow_id == "global-test"
        
        # Clean up
        manager.remove("global-test")