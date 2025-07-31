"""
Shared StateManager factory to ensure consistent state across all workflow tools.

This module provides a single point of StateManager creation to prevent the issue
where workflow_tools.py and state_tools.py create separate StateManager instances
with independent state storage.
"""


from .manager import StateManager

# Global shared StateManager instance
_global_state_manager: StateManager | None = None


def get_shared_state_manager() -> StateManager:
    """
    Get the shared StateManager instance used across all workflow tools.

    Creates a single StateManager instance on first call and returns the same
    instance for all subsequent calls. This ensures that workflow_get_status,
    workflow_state_read, and all other workflow tools operate on the same
    underlying state storage.

    Returns:
        StateManager: The shared StateManager instance
    """
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = StateManager()
    return _global_state_manager


def reset_shared_state_manager() -> None:
    """
    Reset the shared StateManager instance. Primarily used for testing.

    Warning: This will clear all workflow state. Only use this in test
    environments or when explicitly resetting the workflow system.
    """
    global _global_state_manager
    _global_state_manager = None
