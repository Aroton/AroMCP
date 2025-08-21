"""Temporal client management for workflow operations."""

import asyncio
import logging
import threading
import time
from datetime import datetime
from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from .config import WorkflowServerConfig, get_config
from .models.workflow_models import PendingAction
from .pending_actions import get_pending_actions_manager

logger = logging.getLogger(__name__)


class MockWorkflowHandle:
    """Mock workflow handle for Phase 1."""

    def __init__(self, workflow_id: str, workflow_def: dict[str, Any]):
        self.workflow_id = workflow_id
        self.workflow_def = workflow_def
        self.status = "running"
        self.current_step_index = 0
        self.state = {}
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def get_status(self) -> dict[str, Any]:
        """Get current workflow status."""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "current_step": self._get_current_step_id(),
            "state": self.state.copy(),
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": {
                "current_step": self.current_step_index,
                "total_steps": len(self.workflow_def.get("steps", [])),
                "percentage": self._calculate_progress_percentage(),
            }
        }

    def _get_current_step_id(self) -> str | None:
        """Get the current step ID."""
        steps = self.workflow_def.get("steps", [])
        if 0 <= self.current_step_index < len(steps):
            step = steps[self.current_step_index]
            return step.get("id", f"step_{self.current_step_index}")
        return None

    def _calculate_progress_percentage(self) -> float:
        """Calculate workflow progress percentage."""
        total_steps = len(self.workflow_def.get("steps", []))
        if total_steps == 0:
            return 100.0
        return (self.current_step_index / total_steps) * 100.0

    def advance_to_next_step(self) -> dict[str, Any] | None:
        """Advance to next step and return pending action if needed."""
        steps = self.workflow_def.get("steps", [])

        if self.current_step_index >= len(steps):
            # Workflow completed
            self.status = "completed"
            self.updated_at = datetime.now()
            return None

        current_step = steps[self.current_step_index]
        step_type = current_step.get("type", "shell")

        # Create pending action based on step type
        action = self._create_pending_action(current_step)
        if action:
            self.status = "pending_action"
        else:
            # No action needed, auto-advance
            self.current_step_index += 1
            self.status = "running"
            return self.advance_to_next_step()

        self.updated_at = datetime.now()
        return action

    def _create_pending_action(self, step: dict[str, Any]) -> dict[str, Any] | None:
        """Create a pending action from a workflow step."""
        step_type = step.get("type", "shell")
        step_id = step.get("id", f"step_{self.current_step_index}")

        # For Phase 1, all step types that require Claude interaction become pending actions
        if step_type in ["shell", "mcp_call", "prompt", "delegate"]:
            return {
                "type": step_type,
                "step_id": step_id,
                "parameters": step.copy(),
                "workflow_id": self.workflow_id,
                "requires_claude": True,
            }
        elif step_type == "wait":
            # Wait steps can be handled automatically in mock mode
            wait_seconds = step.get("seconds", 1)
            config = get_config()
            if config.mock_mode:
                # In mock mode, simulate wait with minimal delay
                time.sleep(min(wait_seconds, config.mock_step_delay))
                return None  # Auto-advance
            else:
                # Real wait becomes a pending action
                return {
                    "type": "wait",
                    "step_id": step_id,
                    "parameters": step.copy(),
                    "workflow_id": self.workflow_id,
                    "requires_claude": False,
                }
        elif step_type == "set_state":
            # State operations can be handled automatically
            self._handle_set_state_step(step)
            return None  # Auto-advance

        # Unknown step type - create generic pending action
        return {
            "type": step_type,
            "step_id": step_id,
            "parameters": step.copy(),
            "workflow_id": self.workflow_id,
            "requires_claude": True,
        }

    def _handle_set_state_step(self, step: dict[str, Any]) -> None:
        """Handle set_state step automatically."""
        updates = step.get("updates", {})
        for key, value in updates.items():
            self.state[key] = value

    def submit_result(self, result: Any) -> dict[str, Any] | None:
        """Submit result for current step and advance."""
        # Store result in state if specified
        current_step_id = self._get_current_step_id()
        if current_step_id:
            self.state[f"{current_step_id}_result"] = result

        # Advance to next step
        self.current_step_index += 1
        return self.advance_to_next_step()

    def fail_workflow(self, error: str) -> None:
        """Mark workflow as failed."""
        self.status = "failed"
        self.error = error
        self.updated_at = datetime.now()


class TemporalManager:
    """Temporal client manager as specified in Phase 1."""

    def __init__(self, config: WorkflowServerConfig):
        self.config = config
        self.client: Client | None = None
        self.worker: Worker | None = None
        self.connected = False
        self.workflows: dict[str, MockWorkflowHandle] = {}
        self._lock = threading.RLock()

    async def connect(self) -> bool:
        """Establish connection to Temporal server."""
        if self.config.mock_mode:
            logger.info("Connecting to Temporal in mock mode")
            # Always succeed in mock mode
            await asyncio.sleep(0.1)  # Simulate connection delay
            self.connected = True
            logger.info("Successfully connected to Temporal (mock mode)")
            return True
        else:
            # Real Temporal connection
            logger.info(f"Connecting to Temporal server at {self.config.temporal_host}")
            try:
                self.client = await Client.connect(
                    self.config.temporal_host,
                    namespace=self.config.temporal_namespace
                )
                self.connected = True
                logger.info(f"Successfully connected to Temporal server at {self.config.temporal_host}")
                return True
            except Exception as e:
                logger.error(f"Failed to connect to Temporal server: {str(e)}")
                self.connected = False
                return False

    async def health_check(self) -> bool:
        """Verify Temporal connection is healthy."""
        if self.config.mock_mode:
            return self.connected
        else:
            if not self.client:
                return False
            try:
                # Simple workflow list query to test connection
                await self.client.list_workflows(
                    query="WorkflowType='HealthCheck'",
                    page_size=1
                )
                return True
            except Exception:
                return False

    def get_health_info(self) -> dict[str, Any]:
        """Get detailed health information."""
        return {
            "connected": self.connected,
            "mock_mode": self.config.mock_mode,
            "temporal_host": self.config.temporal_host,
            "temporal_namespace": self.config.temporal_namespace,
            "task_queue": self.config.temporal_task_queue,
            "active_workflows": len(self.workflows),
            "health_check_time": datetime.now().isoformat(),
        }

    async def start_workflow(
        self,
        workflow_type: str,
        workflow_id: str,
        args: list[Any],
        task_queue: str | None = None
    ):
        """Start a new workflow execution."""
        if self.config.mock_mode:
            # Mock mode - create mock workflow handle
            workflow_def = args[0] if args else {}
            handle = self._start_mock_workflow(workflow_def, workflow_id)
            return handle
        else:
            # Real Temporal workflow start
            if not self.client:
                raise RuntimeError("Not connected to Temporal server")

            return await self.client.start_workflow(
                workflow_type,
                args,
                id=workflow_id,
                task_queue=task_queue or self.config.temporal_task_queue
            )

    def _start_mock_workflow(self, workflow_def: dict[str, Any], workflow_id: str) -> MockWorkflowHandle:
        """Start a mock workflow for Phase 1."""
        with self._lock:
            handle = MockWorkflowHandle(workflow_id, workflow_def)
            self.workflows[workflow_id] = handle

        # Start workflow execution by advancing to first step
        next_action = handle.advance_to_next_step()

        if next_action:
            # Create pending action for Claude
            pending_action = PendingAction(
                workflow_id=workflow_id,
                step_id=next_action["step_id"],
                action_type=next_action["type"],
                parameters=next_action["parameters"],
                timeout=3600  # 1 hour default timeout
            )

            pending_manager = get_pending_actions_manager()
            pending_manager.add_action(pending_action)

        return handle

    def get_workflow(self, workflow_id: str) -> MockWorkflowHandle | None:
        """Get workflow handle by ID."""
        with self._lock:
            return self.workflows.get(workflow_id)

    def signal_workflow(self, workflow_id: str, signal_name: str, payload: Any) -> bool:
        """Send signal to workflow (mock implementation)."""
        with self._lock:
            handle = self.workflows.get(workflow_id)
            if handle is None:
                return False

            # In Phase 1, signals are just stored in state
            signal_key = f"signal_{signal_name}"
            if signal_key not in handle.state:
                handle.state[signal_key] = []
            handle.state[signal_key].append({
                "payload": payload,
                "timestamp": datetime.now().isoformat(),
            })

            handle.updated_at = datetime.now()
            return True

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a workflow execution."""
        with self._lock:
            handle = self.workflows.get(workflow_id)
            if handle is None:
                return False

            handle.status = "cancelled"
            handle.updated_at = datetime.now()

            # Remove any pending actions
            pending_manager = get_pending_actions_manager()
            pending_manager.remove_action(workflow_id)

            return True

    def list_workflows(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        """List all workflows, optionally filtered by status."""
        with self._lock:
            workflows = []
            for handle in self.workflows.values():
                workflow_info = handle.get_status()
                if status_filter is None or workflow_info["status"] == status_filter:
                    workflows.append(workflow_info)
            return workflows

    def cleanup_completed_workflows(self, max_age_hours: int = 24) -> int:
        """Clean up completed workflows older than specified age."""
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        removed_count = 0

        with self._lock:
            workflow_ids_to_remove = []

            for workflow_id, handle in self.workflows.items():
                if handle.status in ["completed", "failed", "cancelled"]:
                    if handle.updated_at.timestamp() < cutoff_time:
                        workflow_ids_to_remove.append(workflow_id)

            for workflow_id in workflow_ids_to_remove:
                del self.workflows[workflow_id]
                removed_count += 1

        return removed_count

    async def close(self) -> None:
        """Close connection to Temporal server."""
        self.connected = False
        with self._lock:
            self.workflows.clear()


# Global singleton instance
_temporal_manager: TemporalManager | None = None
_manager_lock = threading.Lock()


def get_temporal_manager() -> TemporalManager:
    """Get the global Temporal manager instance."""
    global _temporal_manager

    if _temporal_manager is None:
        with _manager_lock:
            if _temporal_manager is None:
                config = get_config()
                _temporal_manager = TemporalManager(config)

    return _temporal_manager


def reset_temporal_manager() -> None:
    """Reset the global Temporal manager (for testing)."""
    global _temporal_manager
    with _manager_lock:
        _temporal_manager = None
