"""Mock implementations for testing workflow components."""

import copy
import threading
from datetime import datetime
from typing import Any

from ..errors.models import ErrorSeverity, WorkflowError
from ..state.models import StateSchema
from ..workflow.models import WorkflowDefinition


class MockStateManager:
    """Mock state manager for testing."""

    def __init__(self):
        self._states: dict[str, dict[str, Any]] = {}
        self._schemas: dict[str, StateSchema] = {}
        self._update_history: list[dict[str, Any]] = []
        self._read_history: list[str] = []
        self._lock = threading.RLock()

        # Configurable behavior
        self.should_fail_read = False
        self.should_fail_update = False
        self.read_delay = 0.0
        self.update_delay = 0.0

    def initialize_workflow(
        self,
        workflow_id: str,
        schema: StateSchema,
        initial_state: dict[str, Any] | None = None
    ):
        """Initialize a workflow with schema and initial state."""
        with self._lock:
            self._schemas[workflow_id] = schema
            self._states[workflow_id] = initial_state or {}

    def read(self, workflow_id: str, paths: list[str] | None = None) -> dict[str, Any] | None:
        """Read state from workflow."""
        with self._lock:
            self._read_history.append(workflow_id)

            if self.should_fail_read:
                raise Exception("Mock read failure")

            if workflow_id not in self._states:
                return None

            state = self._states[workflow_id]

            if paths:
                # Return only requested paths
                result = {}
                for path in paths:
                    if path in state:
                        result[path] = state[path]
                return result

            return copy.deepcopy(state)

    def update(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update workflow state."""
        with self._lock:
            self._update_history.append({
                "workflow_id": workflow_id,
                "updates": updates,
                "timestamp": datetime.now(),
            })

            if self.should_fail_update:
                raise Exception("Mock update failure")

            if workflow_id not in self._states:
                self._states[workflow_id] = {}

            state = self._states[workflow_id]

            for update in updates:
                path = update["path"]
                value = update["value"]
                operation = update.get("operation", "set")

                if operation == "set":
                    state[path] = value
                elif operation == "increment":
                    state[path] = state.get(path, 0) + (value if value is not None else 1)
                elif operation == "append":
                    if path not in state:
                        state[path] = []
                    state[path].append(value)

            return {"success": True, "updated_paths": [u["path"] for u in updates]}

    def get_flattened_view(self, workflow_id: str) -> dict[str, Any]:
        """Get flattened view of state."""
        with self._lock:
            state = self._states.get(workflow_id, {})
            return copy.deepcopy(state)

    def validate_update_path(self, path: str) -> bool:
        """Validate if path can be updated."""
        # Simple validation - allow raw.* and state.* paths
        return path.startswith(("raw.", "state."))

    def get_update_history(self) -> list[dict[str, Any]]:
        """Get history of updates for testing."""
        with self._lock:
            return copy.deepcopy(self._update_history)

    def get_read_history(self) -> list[str]:
        """Get history of reads for testing."""
        with self._lock:
            return copy.deepcopy(self._read_history)

    def clear_history(self):
        """Clear operation history."""
        with self._lock:
            self._update_history.clear()
            self._read_history.clear()

    def set_state(self, workflow_id: str, state: dict[str, Any]):
        """Directly set state for testing."""
        with self._lock:
            self._states[workflow_id] = copy.deepcopy(state)


class MockWorkflowExecutor:
    """Mock workflow executor for testing."""

    def __init__(self):
        self._workflows: dict[str, WorkflowDefinition] = {}
        self._execution_states: dict[str, dict[str, Any]] = {}
        self._step_history: list[dict[str, Any]] = []
        self._next_step_responses: dict[str, dict[str, Any]] = {}

        # Configurable behavior
        self.should_fail_start = False
        self.should_fail_get_next_step = False
        self.should_fail_step_complete = False

    def start(self, workflow_def: WorkflowDefinition, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a workflow."""
        if self.should_fail_start:
            raise Exception("Mock start failure")

        workflow_id = f"wf_{len(self._workflows) + 1:03d}"

        self._workflows[workflow_id] = workflow_def
        self._execution_states[workflow_id] = {
            "status": "running",
            "current_step_index": 0,
            "inputs": inputs or {},
            "start_time": datetime.now(),
        }

        return {
            "workflow_id": workflow_id,
            "status": "started",
            "state": inputs or {},
        }

    def get_next_step(self, workflow_id: str, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Get next step to execute."""
        if self.should_fail_get_next_step:
            raise Exception("Mock get_next_step failure")

        # Check for pre-configured response
        if workflow_id in self._next_step_responses:
            return self._next_step_responses[workflow_id]

        if workflow_id not in self._execution_states:
            return None

        exec_state = self._execution_states[workflow_id]
        workflow_def = self._workflows.get(workflow_id)

        if not workflow_def or not workflow_def.steps:
            return None

        step_index = exec_state["current_step_index"]
        if step_index >= len(workflow_def.steps):
            return None  # Workflow complete

        step = workflow_def.steps[step_index]
        return {
            "id": step.get("id", f"step_{step_index}"),
            "type": step.get("type", "unknown"),
            "definition": step,
            "context": context or {},
        }

    def step_complete(
        self,
        workflow_id: str,
        step_id: str,
        result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Mark step as complete."""
        if self.should_fail_step_complete:
            raise Exception("Mock step_complete failure")

        self._step_history.append({
            "workflow_id": workflow_id,
            "step_id": step_id,
            "result": result,
            "timestamp": datetime.now(),
        })

        if workflow_id in self._execution_states:
            self._execution_states[workflow_id]["current_step_index"] += 1

        return {"success": True, "step_id": step_id}

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any] | None:
        """Get workflow status."""
        if workflow_id not in self._execution_states:
            return None

        exec_state = self._execution_states[workflow_id]
        workflow_def = self._workflows.get(workflow_id)

        total_steps = len(workflow_def.steps) if workflow_def and workflow_def.steps else 0
        current_step = exec_state["current_step_index"]

        return {
            "workflow_id": workflow_id,
            "status": exec_state["status"],
            "current_step_index": current_step,
            "total_steps": total_steps,
            "progress": (current_step / total_steps * 100) if total_steps > 0 else 0,
            "start_time": exec_state["start_time"].isoformat(),
        }

    def set_next_step_response(self, workflow_id: str, response: dict[str, Any]):
        """Set pre-configured response for get_next_step."""
        self._next_step_responses[workflow_id] = response

    def get_step_history(self) -> list[dict[str, Any]]:
        """Get step execution history for testing."""
        return copy.deepcopy(self._step_history)

    def clear_history(self):
        """Clear execution history."""
        self._step_history.clear()


class MockErrorTracker:
    """Mock error tracker for testing."""

    def __init__(self):
        self.history = MockErrorHistory()
        self._error_patterns = []
        self._recovery_stats = {}

        # Configurable behavior
        self.should_fail_track_error = False
        self.should_fail_detect_patterns = False

    def track_error(self, error: WorkflowError, recovery_action: str | None = None):
        """Track an error."""
        if self.should_fail_track_error:
            raise Exception("Mock track_error failure")

        self.history.add_error(error)

        if recovery_action:
            self._recovery_stats[recovery_action] = self._recovery_stats.get(recovery_action, 0) + 1

    def mark_error_recovered(self, error_id: str):
        """Mark error as recovered."""
        error = self.history.get_error_by_id(error_id)
        if error:
            error.recovered = True

    def detect_error_patterns(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Detect error patterns."""
        if self.should_fail_detect_patterns:
            raise Exception("Mock detect_patterns failure")

        return copy.deepcopy(self._error_patterns)

    def set_error_patterns(self, patterns: list[dict[str, Any]]):
        """Set error patterns for testing."""
        self._error_patterns = patterns

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get recovery statistics."""
        return copy.deepcopy(self._recovery_stats)


class MockErrorHistory:
    """Mock error history for testing."""

    def __init__(self):
        self._errors: dict[str, list[WorkflowError]] = {}
        self._global_errors: list[WorkflowError] = []

    def add_error(self, error: WorkflowError):
        """Add error to history."""
        if error.workflow_id not in self._errors:
            self._errors[error.workflow_id] = []

        self._errors[error.workflow_id].append(error)
        self._global_errors.append(error)

    def get_workflow_errors(self, workflow_id: str) -> list[WorkflowError]:
        """Get errors for workflow."""
        return copy.deepcopy(self._errors.get(workflow_id, []))

    def get_error_by_id(self, error_id: str) -> WorkflowError | None:
        """Get error by ID."""
        for error in self._global_errors:
            if error.id == error_id:
                return error
        return None

    def get_error_summary(self, workflow_id: str | None = None) -> dict[str, Any]:
        """Get error summary."""
        errors = self._errors.get(workflow_id, []) if workflow_id else self._global_errors

        return {
            "total_errors": len(errors),
            "by_severity": {},
            "by_type": {},
            "recent_errors": 0,
        }


class MockMCPTool:
    """Mock MCP tool for testing."""

    def __init__(self, name: str):
        self.name = name
        self.call_history: list[dict[str, Any]] = []
        self.responses: dict[str, Any] = {}
        self.should_fail = False
        self.call_delay = 0.0

    def __call__(self, *args, **kwargs) -> Any:
        """Mock tool call."""
        call_record = {
            "name": self.name,
            "args": args,
            "kwargs": kwargs,
            "timestamp": datetime.now(),
        }
        self.call_history.append(call_record)

        if self.should_fail:
            raise Exception(f"Mock {self.name} failure")

        # Return pre-configured response or default
        key = f"{args}_{kwargs}" if args or kwargs else "default"
        return self.responses.get(key, {"success": True, "mock": True})

    def set_response(self, response: Any, args: tuple = (), kwargs: dict | None = None):
        """Set response for specific arguments."""
        if kwargs is None:
            kwargs = {}
        key = f"{args}_{kwargs}" if args or kwargs else "default"
        self.responses[key] = response

    def get_call_history(self) -> list[dict[str, Any]]:
        """Get call history."""
        return copy.deepcopy(self.call_history)

    def clear_history(self):
        """Clear call history."""
        self.call_history.clear()


def create_mock_workflow_definition(
    name: str = "test:workflow",
    steps: list[dict[str, Any]] | None = None,
    state_schema: dict[str, Any] | None = None,
) -> WorkflowDefinition:
    """Create a mock workflow definition for testing."""

    if steps is None:
        steps = [
            {"id": "step1", "type": "state_update", "path": "raw.counter", "value": 1},
            {"id": "step2", "type": "user_message", "message": "Hello {{ name }}"},
        ]

    if state_schema is None:
        state_schema = {
            "raw": {"counter": "number", "name": "string"},
            "computed": {},
            "state": {"version": "string"},
        }

    # Convert steps to WorkflowStep objects
    from ..workflow.models import WorkflowStep
    workflow_steps = []
    for i, step in enumerate(steps):
        workflow_steps.append(WorkflowStep(
            id=step.get("id", f"step_{i}"),
            type=step.get("type", "unknown"),
            definition=step,
        ))

    return WorkflowDefinition(
        name=name,
        description="Test workflow",
        version="1.0.0",
        steps=workflow_steps,
        state_schema=StateSchema(**state_schema),
        default_state={"raw": {"counter": 0}, "state": {"version": "1.0"}},
        inputs={},
    )


def create_mock_error(
    workflow_id: str = "wf_test",
    step_id: str = "step_1",
    error_type: str = "TestError",
    message: str = "Test error message",
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
) -> WorkflowError:
    """Create a mock workflow error for testing."""

    return WorkflowError(
        id=f"err_test_{datetime.now().timestamp()}",
        workflow_id=workflow_id,
        step_id=step_id,
        error_type=error_type,
        message=message,
        stack_trace="Mock stack trace",
        timestamp=datetime.now(),
        severity=severity,
    )
