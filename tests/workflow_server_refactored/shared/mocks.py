"""Mock components for workflow server testing."""

from typing import Any
from unittest.mock import Mock


class MockStateManager:
    """Mock state manager for testing state operations."""

    def __init__(self, initial_state: dict[str, Any] | None = None):
        self.states: dict[str, dict[str, Any]] = {}
        self.fail_on_read = False
        self.fail_on_write = False
        self.fail_on_update = False

        if initial_state:
            self.states["default"] = initial_state

    def read(self, workflow_id: str) -> dict[str, Any]:
        """Read workflow state."""
        if self.fail_on_read:
            raise Exception("Mock state read failure")
        return self.states.get(workflow_id, {})

    def write(self, workflow_id: str, state: dict[str, Any]) -> None:
        """Write workflow state."""
        if self.fail_on_write:
            raise Exception("Mock state write failure")
        self.states[workflow_id] = state

    def update(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update workflow state."""
        if self.fail_on_update:
            raise Exception("Mock state update failure")

        state = self.states.get(workflow_id, {})
        for update in updates:
            path = update["path"]
            value = update["value"]

            # Simple path setting for testing
            if "." in path:
                keys = path.split(".")
                current = state
                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[keys[-1]] = value
            else:
                state[path] = value

        self.states[workflow_id] = state
        return state

    def delete(self, workflow_id: str) -> None:
        """Delete workflow state."""
        if workflow_id in self.states:
            del self.states[workflow_id]

    def configure_failures(self, read: bool = False, write: bool = False, update: bool = False):
        """Configure failure conditions for testing."""
        self.fail_on_read = read
        self.fail_on_write = write
        self.fail_on_update = update


class MockWorkflowExecutor:
    """Mock workflow executor for testing."""

    def __init__(self):
        self.workflows: dict[str, Any] = {}
        self.step_results: dict[str, list[dict[str, Any]]] = {}
        self.fail_on_start = False
        self.fail_on_step = False

    def start(self, workflow_def: Any, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a workflow instance."""
        if self.fail_on_start:
            raise Exception("Mock workflow start failure")

        workflow_id = f"wf_mock_{len(self.workflows)}"

        result = {
            "workflow_id": workflow_id,
            "status": "running",
            "state": {"raw": inputs or {}, "computed": {}},
            "total_steps": 3,  # Mock step count
            "execution_context": {"current_step_index": 0},
        }

        self.workflows[workflow_id] = result
        return result

    def get_next_step(self, workflow_id: str) -> dict[str, Any] | None:
        """Get next step for execution."""
        if self.fail_on_step:
            return {"error": "Mock step failure"}

        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}

        # Return mock step
        return {"step": {"id": "mock_step_1", "type": "user_message", "definition": {"message": "Mock step execution"}}}

    # Note: step_complete method removed - using implicit completion via get_next_step

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow status."""
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}

        return self.workflows[workflow_id]

    def configure_failures(self, start: bool = False, step: bool = False):
        """Configure failure conditions for testing."""
        self.fail_on_start = start
        self.fail_on_step = step


class MockWorkflowLoader:
    """Mock workflow loader for testing."""

    def __init__(self):
        self.workflows: dict[str, Any] = {}
        self.fail_on_load = False

    def load(self, workflow_name: str) -> Any:
        """Load a workflow definition."""
        if self.fail_on_load:
            raise Exception(f"Mock workflow load failure for {workflow_name}")

        if workflow_name not in self.workflows:
            raise Exception(f"Workflow {workflow_name} not found")

        return self.workflows[workflow_name]

    def list_available_workflows(self, include_global: bool = True) -> list[dict[str, Any]]:
        """List available workflows."""
        return [
            {"name": name, "source": "mock", "description": f"Mock workflow {name}", "version": "1.0.0"}
            for name in self.workflows.keys()
        ]

    def add_workflow(self, name: str, definition: Any):
        """Add a workflow definition for testing."""
        self.workflows[name] = definition

    def configure_failures(self, load: bool = False):
        """Configure failure conditions for testing."""
        self.fail_on_load = load


def create_mock_workflow_definition(name: str, steps: list[dict[str, Any]] | None = None) -> Mock:
    """Create a mock workflow definition."""
    mock_workflow = Mock()
    mock_workflow.name = name
    mock_workflow.description = f"Mock workflow {name}"
    mock_workflow.version = "1.0.0"
    mock_workflow.default_state = {"raw": {}, "computed": {}}
    mock_workflow.inputs = {}
    mock_workflow.steps = steps or [
        {"id": "step1", "type": "user_message", "definition": {"message": "Hello"}},
        {"id": "step2", "type": "state_update", "definition": {"path": "raw.complete", "value": True}},
    ]
    mock_workflow.loaded_from = "mock"
    mock_workflow.source = "mock"
    return mock_workflow


def create_mock_sub_agent_task(task_id: str, item: str, index: int = 0, total: int = 1) -> dict[str, Any]:
    """Create a mock sub-agent task definition."""
    return {
        "task_id": task_id,
        "context": {"item": item, "index": index, "total": total, "workflow_id": "wf_mock_123"},
        "inputs": {"file_path": item, "max_attempts": 5},
    }


def create_mock_step_response(
    step_type: str, step_id: str, definition: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Create a mock step response."""
    return {
        "step": {"id": step_id, "type": step_type, "definition": definition or {"message": f"Mock {step_type} step"}}
    }


def create_mock_batch_response(
    steps: list[dict[str, Any]], server_completed: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Create a mock batched step response."""
    return {"steps": steps, "server_completed_steps": server_completed or []}
