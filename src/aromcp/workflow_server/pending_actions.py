"""Thread-safe in-memory storage for workflow actions awaiting Claude execution."""

import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any

from .models.workflow_models import PendingAction


class PendingActionsManager:
    """Thread-safe in-memory storage for pending workflow actions with LRU eviction."""

    def __init__(self, max_capacity: int = 50):
        """Initialize the pending actions manager.
        
        Args:
            max_capacity: Maximum number of pending actions to store
        """
        self.max_capacity = max_capacity
        self._actions: OrderedDict[str, PendingAction] = OrderedDict()
        self._lock = threading.RLock()

    def add_action(self, action: PendingAction) -> bool:
        """Add a pending action to storage.
        
        Args:
            action: The PendingAction to store
            
        Returns:
            True if action was added, False if workflow_id already exists
        """
        with self._lock:
            if action.workflow_id in self._actions:
                return False

            # If at capacity, remove the oldest (least recently used) action
            if len(self._actions) >= self.max_capacity:
                oldest_workflow_id = next(iter(self._actions))
                del self._actions[oldest_workflow_id]

            self._actions[action.workflow_id] = action
            return True

    def get_action(self, workflow_id: str) -> PendingAction | None:
        """Get a pending action by workflow ID.
        
        Args:
            workflow_id: The workflow ID to lookup
            
        Returns:
            PendingAction if found, None otherwise
        """
        with self._lock:
            action = self._actions.get(workflow_id)
            if action is not None:
                # Move to end (most recently used)
                self._actions.move_to_end(workflow_id)
            return action

    def remove_action(self, workflow_id: str) -> PendingAction | None:
        """Remove and return a pending action by workflow ID.
        
        Args:
            workflow_id: The workflow ID to remove
            
        Returns:
            PendingAction if found and removed, None otherwise
        """
        with self._lock:
            return self._actions.pop(workflow_id, None)

    def update_action(self, workflow_id: str, **updates) -> bool:
        """Update fields of an existing pending action.
        
        Args:
            workflow_id: The workflow ID to update
            **updates: Fields to update on the action
            
        Returns:
            True if action was updated, False if not found
        """
        with self._lock:
            action = self._actions.get(workflow_id)
            if action is None:
                return False

            # Update the action fields
            for field, value in updates.items():
                if hasattr(action, field):
                    setattr(action, field, value)

            # Move to end (most recently used)
            self._actions.move_to_end(workflow_id)
            return True

    def list_actions(self, workflow_ids: list[str] | None = None) -> list[PendingAction]:
        """List pending actions, optionally filtered by workflow IDs.
        
        Args:
            workflow_ids: Optional list of workflow IDs to filter by
            
        Returns:
            List of PendingAction objects
        """
        with self._lock:
            if workflow_ids is None:
                return list(self._actions.values())

            return [
                action for workflow_id, action in self._actions.items()
                if workflow_id in workflow_ids
            ]

    def cleanup_expired(self, timeout_seconds: int = 3600) -> list[str]:
        """Remove actions that have exceeded their timeout.
        
        Args:
            timeout_seconds: Default timeout in seconds for actions without explicit timeout
            
        Returns:
            List of workflow IDs that were removed
        """
        expired_workflow_ids = []
        current_time = datetime.now()

        with self._lock:
            # Collect expired actions
            for workflow_id, action in list(self._actions.items()):
                action_timeout = action.timeout or timeout_seconds
                expiry_time = action.created_at + timedelta(seconds=action_timeout)

                if current_time > expiry_time:
                    expired_workflow_ids.append(workflow_id)

            # Remove expired actions
            for workflow_id in expired_workflow_ids:
                del self._actions[workflow_id]

        return expired_workflow_ids

    def get_stats(self) -> dict[str, Any]:
        """Get statistics about the pending actions storage.
        
        Returns:
            Dictionary with storage statistics
        """
        with self._lock:
            current_time = datetime.now()

            # Calculate age statistics
            ages = []
            for action in self._actions.values():
                age_seconds = (current_time - action.created_at).total_seconds()
                ages.append(age_seconds)

            return {
                "total_actions": len(self._actions),
                "capacity": self.max_capacity,
                "capacity_used_percent": (len(self._actions) / self.max_capacity) * 100,
                "oldest_age_seconds": max(ages) if ages else 0,
                "newest_age_seconds": min(ages) if ages else 0,
                "average_age_seconds": sum(ages) / len(ages) if ages else 0,
                "action_types": self._get_action_type_counts(),
            }

    def _get_action_type_counts(self) -> dict[str, int]:
        """Get count of actions by type (internal helper)."""
        type_counts: dict[str, int] = {}
        for action in self._actions.values():
            type_counts[action.action_type] = type_counts.get(action.action_type, 0) + 1
        return type_counts

    def clear(self) -> int:
        """Clear all pending actions.
        
        Returns:
            Number of actions that were cleared
        """
        with self._lock:
            count = len(self._actions)
            self._actions.clear()
            return count


# Global singleton instance
_pending_actions_manager: PendingActionsManager | None = None
_manager_lock = threading.Lock()


def get_pending_actions_manager() -> PendingActionsManager:
    """Get the global pending actions manager instance."""
    global _pending_actions_manager

    if _pending_actions_manager is None:
        with _manager_lock:
            if _pending_actions_manager is None:
                from .config import get_config
                config = get_config()
                _pending_actions_manager = PendingActionsManager(
                    max_capacity=config.max_pending_actions
                )

    return _pending_actions_manager


def reset_pending_actions_manager() -> None:
    """Reset the global pending actions manager (for testing)."""
    global _pending_actions_manager
    with _manager_lock:
        _pending_actions_manager = None
