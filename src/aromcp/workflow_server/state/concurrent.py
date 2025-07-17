"""Concurrent state management for parallel workflow execution.

This module provides thread-safe state operations with conflict resolution
and optimistic locking for multi-agent workflows.
"""

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .models import StateUpdate
from .transformer import TransformationEngine


@dataclass
class StateVersion:
    """Tracks version information for optimistic locking."""

    version: int
    updated_at: float
    updated_by: str | None = None  # agent_id or system
    checksum: str | None = None


@dataclass
class ConflictResolution:
    """Configuration for handling state update conflicts."""

    strategy: str = "merge"  # merge, overwrite, reject, manual
    merge_policy: str = "last_writer_wins"  # last_writer_wins, first_writer_wins, field_level
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass
class BatchUpdate:
    """A batch of state updates to be applied atomically."""

    updates: list[StateUpdate]
    agent_id: str | None = None
    expected_version: int | None = None
    timeout_seconds: int = 10
    created_at: float = field(default_factory=time.time)


@dataclass
class UpdateConflict:
    """Represents a conflict between concurrent updates."""

    conflicting_paths: set[str]
    original_update: BatchUpdate
    conflicting_update: BatchUpdate
    detected_at: float = field(default_factory=time.time)


class ConcurrentStateManager:
    """Thread-safe state manager with conflict resolution."""

    def __init__(self, base_manager=None):
        """Initialize with optional base state manager for delegation."""
        from .manager import StateManager

        self._base_manager = base_manager or StateManager()
        self._locks: dict[str, threading.RLock] = {}
        self._global_lock = threading.RLock()
        self._versions: dict[str, StateVersion] = {}
        self._pending_updates: dict[str, list[BatchUpdate]] = defaultdict(list)
        self._conflict_resolution = ConflictResolution()
        self._transformation_engine = TransformationEngine()
        self._update_history: dict[str, list[tuple[float, str, list[StateUpdate]]]] = defaultdict(list)

        # Performance tracking
        self._stats = {
            "total_updates": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0,
            "update_retries": 0,
            "average_update_time": 0.0,
        }

    def _get_workflow_lock(self, workflow_id: str) -> threading.RLock:
        """Get or create a lock for a specific workflow."""
        with self._global_lock:
            if workflow_id not in self._locks:
                self._locks[workflow_id] = threading.RLock()
            return self._locks[workflow_id]

    def _get_version(self, workflow_id: str) -> StateVersion:
        """Get current version for a workflow."""
        with self._global_lock:
            if workflow_id not in self._versions:
                self._versions[workflow_id] = StateVersion(version=1, updated_at=time.time())
            return self._versions[workflow_id]

    def _increment_version(self, workflow_id: str, agent_id: str | None = None) -> StateVersion:
        """Increment version for a workflow."""
        with self._global_lock:
            current = self._get_version(workflow_id)
            new_version = StateVersion(version=current.version + 1, updated_at=time.time(), updated_by=agent_id)
            self._versions[workflow_id] = new_version
            return new_version

    def read(self, workflow_id: str, paths: list[str] | None = None, include_version: bool = False) -> dict[str, Any]:
        """Thread-safe read operation.

        Args:
            workflow_id: Workflow to read from
            paths: Specific paths to read (None for all)
            include_version: Whether to include version info

        Returns:
            State data with optional version info
        """
        lock = self._get_workflow_lock(workflow_id)

        with lock:
            # Delegate to base manager for actual read
            result = self._base_manager.read(workflow_id, paths)

            if include_version:
                version = self._get_version(workflow_id)
                result["__version__"] = {
                    "version": version.version,
                    "updated_at": version.updated_at,
                    "updated_by": version.updated_by,
                }

            return result

    def update(
        self,
        workflow_id: str,
        updates: list[StateUpdate] | list[dict[str, Any]],
        agent_id: str | None = None,
        expected_version: int | None = None,
        batch_timeout: int = 10,
    ) -> dict[str, Any]:
        """Thread-safe atomic update operation.

        Args:
            workflow_id: Workflow to update
            updates: List of updates to apply
            agent_id: ID of agent making the update
            expected_version: Expected current version for optimistic locking
            batch_timeout: Timeout for batch operation

        Returns:
            Result with success/failure info
        """
        start_time = time.time()

        # Convert dict updates to StateUpdate objects
        state_updates = []
        for update in updates:
            if isinstance(update, dict):
                state_updates.append(StateUpdate(**update))
            else:
                state_updates.append(update)

        # Create batch update
        batch = BatchUpdate(
            updates=state_updates, agent_id=agent_id, expected_version=expected_version, timeout_seconds=batch_timeout
        )

        lock = self._get_workflow_lock(workflow_id)

        try:
            with lock:
                # Check version if specified
                if expected_version is not None:
                    current_version = self._get_version(workflow_id)
                    if current_version.version != expected_version:
                        return {
                            "success": False,
                            "error": "VERSION_CONFLICT",
                            "message": f"Expected version {expected_version}, got {current_version.version}",
                            "current_version": current_version.version,
                        }

                # Detect conflicts with pending updates
                conflict = self._detect_conflicts(workflow_id, batch)
                if conflict:
                    resolution_result = self._resolve_conflict(workflow_id, conflict)
                    if not resolution_result["success"]:
                        return resolution_result

                # Apply updates through base manager
                try:
                    # Convert StateUpdate objects back to dicts for base manager
                    update_dicts = [
                        {"path": update.path, "value": update.value, "operation": update.operation}
                        for update in state_updates
                    ]

                    result = self._base_manager.update(workflow_id, update_dicts)

                    if result.get("success", True):
                        # Update version
                        new_version = self._increment_version(workflow_id, agent_id)

                        # Record in history
                        self._update_history[workflow_id].append((time.time(), agent_id or "system", state_updates))

                        # Update stats
                        self._stats["total_updates"] += 1
                        update_time = time.time() - start_time
                        self._stats["average_update_time"] = (
                            self._stats["average_update_time"] * (self._stats["total_updates"] - 1) + update_time
                        ) / self._stats["total_updates"]

                        return {
                            "success": True,
                            "new_version": new_version.version,
                            "updated_at": new_version.updated_at,
                            "update_time_ms": (time.time() - start_time) * 1000,
                        }
                    else:
                        return result

                except Exception as e:
                    return {"success": False, "error": "UPDATE_FAILED", "message": str(e)}

        except Exception as e:
            return {"success": False, "error": "LOCK_ERROR", "message": str(e)}

    def _detect_conflicts(self, workflow_id: str, new_batch: BatchUpdate) -> UpdateConflict | None:
        """Detect conflicts between new batch and pending updates."""
        pending = self._pending_updates.get(workflow_id, [])
        if not pending:
            return None

        # Get paths affected by new batch
        new_paths = {update.path for update in new_batch.updates}

        # Check for path conflicts
        for pending_batch in pending:
            pending_paths = {update.path for update in pending_batch.updates}
            conflicting_paths = new_paths.intersection(pending_paths)

            if conflicting_paths:
                return UpdateConflict(
                    conflicting_paths=conflicting_paths, original_update=pending_batch, conflicting_update=new_batch
                )

        return None

    def _resolve_conflict(self, workflow_id: str, conflict: UpdateConflict) -> dict[str, Any]:
        """Resolve update conflict based on resolution strategy."""
        strategy = self._conflict_resolution.strategy

        self._stats["conflicts_detected"] += 1

        try:
            if strategy == "merge":
                return self._merge_updates(workflow_id, conflict)
            elif strategy == "overwrite":
                return self._overwrite_updates(workflow_id, conflict)
            elif strategy == "reject":
                return {
                    "success": False,
                    "error": "CONFLICT_REJECTED",
                    "message": f"Update conflicts on paths: {conflict.conflicting_paths}",
                }
            else:
                return {
                    "success": False,
                    "error": "UNKNOWN_STRATEGY",
                    "message": f"Unknown conflict resolution strategy: {strategy}",
                }

        except Exception as e:
            return {"success": False, "error": "RESOLUTION_FAILED", "message": str(e)}

    def _merge_updates(self, workflow_id: str, conflict: UpdateConflict) -> dict[str, Any]:
        """Merge conflicting updates based on merge policy."""
        policy = self._conflict_resolution.merge_policy

        if policy == "last_writer_wins":
            # New update takes precedence, remove conflicting paths from pending
            original_batch = conflict.original_update
            original_batch.updates = [
                update for update in original_batch.updates if update.path not in conflict.conflicting_paths
            ]

            self._stats["conflicts_resolved"] += 1
            return {"success": True, "resolution": "last_writer_wins"}

        elif policy == "first_writer_wins":
            # Original update takes precedence, reject conflicting paths from new
            conflict.conflicting_update.updates = [
                update
                for update in conflict.conflicting_update.updates
                if update.path not in conflict.conflicting_paths
            ]

            self._stats["conflicts_resolved"] += 1
            return {"success": True, "resolution": "first_writer_wins"}

        else:
            return {
                "success": False,
                "error": "UNSUPPORTED_MERGE_POLICY",
                "message": f"Merge policy {policy} not implemented",
            }

    def _overwrite_updates(self, workflow_id: str, conflict: UpdateConflict) -> dict[str, Any]:
        """Overwrite strategy - new update completely replaces conflicting ones."""
        # Remove all conflicting updates from pending
        pending = self._pending_updates[workflow_id]
        self._pending_updates[workflow_id] = [
            batch for batch in pending if not any(update.path in conflict.conflicting_paths for update in batch.updates)
        ]

        self._stats["conflicts_resolved"] += 1
        return {"success": True, "resolution": "overwrite"}

    def batch_update(self, workflow_id: str, batch: BatchUpdate) -> dict[str, Any]:
        """Execute a batch update with conflict detection and resolution."""
        return self.update(
            workflow_id=workflow_id,
            updates=batch.updates,
            agent_id=batch.agent_id,
            expected_version=batch.expected_version,
            batch_timeout=batch.timeout_seconds,
        )

    def create_checkpoint(self, workflow_id: str) -> dict[str, Any]:
        """Create a checkpoint of current state for recovery."""
        lock = self._get_workflow_lock(workflow_id)

        with lock:
            try:
                # Get current raw state structure (not flattened)
                workflow_state = self._base_manager._states.get(workflow_id)
                if not workflow_state:
                    return {
                        "success": False,
                        "error": "WORKFLOW_NOT_FOUND",
                        "message": f"Workflow {workflow_id} not found",
                    }

                # Store the three-tier structure (deep copy to avoid reference issues)
                import copy
                state_data = {
                    "raw": copy.deepcopy(workflow_state.raw),
                    "computed": copy.deepcopy(workflow_state.computed),
                    "state": copy.deepcopy(workflow_state.state),
                }

                version = self._get_version(workflow_id)

                checkpoint = {
                    "workflow_id": workflow_id,
                    "state": state_data,
                    "version": version.version,
                    "created_at": time.time(),
                    "created_by": "system",
                }

                return {"success": True, "checkpoint": checkpoint}

            except Exception as e:
                return {"success": False, "error": "CHECKPOINT_FAILED", "message": str(e)}

    def restore_from_checkpoint(self, workflow_id: str, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """Restore state from a checkpoint."""
        lock = self._get_workflow_lock(workflow_id)

        with lock:
            try:
                # Clear current state and replace with checkpoint
                checkpoint_state = checkpoint["state"]

                # Remove version info if present
                if "__version__" in checkpoint_state:
                    del checkpoint_state["__version__"]

                # Clear all concurrent manager state for this workflow
                with self._global_lock:
                    # Clear pending updates
                    if workflow_id in self._pending_updates:
                        del self._pending_updates[workflow_id]

                    # Clear update history
                    if workflow_id in self._update_history:
                        del self._update_history[workflow_id]

                # Restore state by updating through base manager
                # First clear the current state
                if workflow_id in self._base_manager._states:
                    del self._base_manager._states[workflow_id]

                # Create new state with checkpoint data
                from .models import WorkflowState

                restored_state = WorkflowState(
                    raw=checkpoint_state.get("raw", {}),
                    computed=checkpoint_state.get("computed", {}),
                    state=checkpoint_state.get("state", {}),
                )

                self._base_manager._states[workflow_id] = restored_state

                # If there are schemas, recalculate computed fields
                if hasattr(self._base_manager, "_schemas") and workflow_id in self._base_manager._schemas:
                    # Use the update mechanism to trigger recalculation
                    schema = self._base_manager._schemas[workflow_id]
                    self._base_manager._calculate_computed_fields(restored_state, schema.computed_fields)

                # Update version to checkpoint version + 1
                with self._global_lock:
                    self._versions[workflow_id] = StateVersion(
                        version=checkpoint["version"] + 1, updated_at=time.time(), updated_by="checkpoint_restore"
                    )

                return {
                    "success": True,
                    "restored_version": checkpoint["version"],
                    "new_version": checkpoint["version"] + 1,
                }

            except Exception as e:
                return {"success": False, "error": "RESTORE_FAILED", "message": str(e)}

    def get_update_history(self, workflow_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent update history for a workflow."""
        history = self._update_history.get(workflow_id, [])
        recent = history[-limit:] if limit > 0 else history

        return [
            {
                "timestamp": timestamp,
                "agent_id": agent_id,
                "updates": [
                    {"path": update.path, "operation": update.operation, "value_type": type(update.value).__name__}
                    for update in updates
                ],
            }
            for timestamp, agent_id, updates in recent
        ]

    def get_stats(self) -> dict[str, Any]:
        """Get performance and conflict statistics."""
        return dict(self._stats)

    def cleanup_old_data(self, max_age_seconds: int = 3600) -> dict[str, int]:
        """Clean up old data to prevent memory leaks."""
        current_time = time.time()
        cleanup_stats = {"workflows_cleaned": 0, "history_entries_removed": 0, "pending_updates_removed": 0}

        with self._global_lock:
            # Clean up old history entries
            for workflow_id in list(self._update_history.keys()):
                old_count = len(self._update_history[workflow_id])
                self._update_history[workflow_id] = [
                    entry for entry in self._update_history[workflow_id] if current_time - entry[0] < max_age_seconds
                ]
                new_count = len(self._update_history[workflow_id])
                cleanup_stats["history_entries_removed"] += old_count - new_count

                if not self._update_history[workflow_id]:
                    del self._update_history[workflow_id]
                    cleanup_stats["workflows_cleaned"] += 1

            # Clean up old pending updates
            for workflow_id in list(self._pending_updates.keys()):
                old_count = len(self._pending_updates[workflow_id])
                self._pending_updates[workflow_id] = [
                    batch
                    for batch in self._pending_updates[workflow_id]
                    if current_time - batch.created_at < max_age_seconds
                ]
                new_count = len(self._pending_updates[workflow_id])
                cleanup_stats["pending_updates_removed"] += old_count - new_count

                if not self._pending_updates[workflow_id]:
                    del self._pending_updates[workflow_id]

        return cleanup_stats

    def configure_conflict_resolution(
        self,
        strategy: str = "merge",
        merge_policy: str = "last_writer_wins",
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        """Configure conflict resolution behavior."""
        self._conflict_resolution = ConflictResolution(
            strategy=strategy, merge_policy=merge_policy, timeout_seconds=timeout_seconds, max_retries=max_retries
        )
