"""Test fixtures for workflow testing."""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ..errors.models import ErrorSeverity, WorkflowError
from ..state.models import StateSchema, WorkflowState
from ..workflow.models import WorkflowDefinition, WorkflowStep


class WorkflowTestFixtures:
    """Provides common test fixtures for workflow testing."""

    def __init__(self):
        self.temp_dirs = []
        self.temp_files = []

    def create_temp_workflow_dir(self) -> str:
        """Create temporary directory for workflow files."""
        temp_dir = tempfile.mkdtemp(prefix="workflow_test_")
        self.temp_dirs.append(temp_dir)

        # Create .aromcp/workflows directory structure
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)

        return str(workflows_dir)

    def create_workflow_file(self, workflows_dir: str, name: str, workflow_def: dict[str, Any]) -> str:
        """Create a workflow YAML file."""
        file_path = Path(workflows_dir) / f"{name}.yaml"

        with open(file_path, "w") as f:
            yaml.dump(workflow_def, f, default_flow_style=False)

        self.temp_files.append(str(file_path))
        return str(file_path)

    def cleanup(self):
        """Clean up temporary files and directories."""
        for temp_file in self.temp_files:
            try:
                Path(temp_file).unlink(missing_ok=True)
            except Exception:  # noqa: S112
                # Best effort cleanup - ignore errors
                continue

        for temp_dir in self.temp_dirs:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:  # noqa: S112
                # Best effort cleanup - ignore errors
                continue

        self.temp_dirs.clear()
        self.temp_files.clear()


def create_test_workflow(
    name: str = "test:simple",
    description: str = "Test workflow",
    steps: list[dict[str, Any]] | None = None,
    state_schema: dict[str, Any] | None = None,
    default_state: dict[str, Any] | None = None,
) -> WorkflowDefinition:
    """Create a test workflow definition."""

    if steps is None:
        steps = [
            {"id": "init", "type": "state_update", "path": "raw.initialized", "value": True},
            {"id": "greet", "type": "user_message", "message": "Hello {{ name | default('World') }}!"},
            {"id": "count", "type": "state_update", "path": "raw.counter", "operation": "increment"},
        ]

    if state_schema is None:
        state_schema = {
            "raw": {"name": "string", "counter": "number", "initialized": "boolean"},
            "computed": {"greeting": {"from": ["raw.name"], "transform": "`Hello ${input[0] || 'World'}!`"}},
            "state": {"version": "string"},
        }

    if default_state is None:
        default_state = {"raw": {"counter": 0, "initialized": False}, "state": {"version": "1.0"}}

    # Convert steps to WorkflowStep objects
    workflow_steps = []
    for i, step in enumerate(steps):
        workflow_steps.append(
            WorkflowStep(
                id=step.get("id", f"step_{i}"),
                type=step.get("type", "unknown"),
                definition=step,
            )
        )

    return WorkflowDefinition(
        name=name,
        description=description,
        version="1.0.0",
        steps=workflow_steps,
        state_schema=StateSchema(**state_schema),
        default_state=default_state,
        inputs={},
    )


def create_test_state(
    raw: dict[str, Any] | None = None,
    computed: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> WorkflowState:
    """Create a test workflow state."""

    if raw is None:
        raw = {"counter": 5, "name": "TestUser", "items": ["a", "b", "c"], "flag": True}

    if computed is None:
        computed = {"doubled_counter": 10, "item_count": 3, "greeting": "Hello TestUser!"}

    if state is None:
        state = {"version": "1.0", "created_at": "2024-01-01T00:00:00Z"}

    return WorkflowState(raw=raw, computed=computed, state=state)


def create_complex_workflow() -> WorkflowDefinition:
    """Create a complex workflow for testing advanced features."""

    steps = [
        {
            "id": "validate_input",
            "type": "conditional",
            "condition": "{{ input_count > 0 }}",
            "then": [{"id": "process_input", "type": "state_update", "path": "raw.status", "value": "processing"}],
            "else": [{"id": "no_input_error", "type": "error", "message": "No input provided"}],
        },
        {
            "id": "process_items",
            "type": "foreach",
            "items": "{{ items }}",
            "body": [
                {
                    "id": "process_item",
                    "type": "mcp_call",
                    "method": "process_item",
                    "params": {"item": "{{ item }}", "index": "{{ index }}"},
                }
            ],
        },
        {
            "id": "parallel_work",
            "type": "parallel_foreach",
            "items": "{{ ready_batches }}",
            "max_parallel": 5,
            "sub_agent_task": "process_batch",
        },
        {
            "id": "retry_loop",
            "type": "while",
            "condition": "{{ !success && attempts < 3 }}",
            "max_iterations": 3,
            "body": [
                {"id": "attempt_operation", "type": "shell_command", "command": "echo 'Attempt {{ attempts }}'"},
                {"id": "increment_attempts", "type": "state_update", "path": "raw.attempts", "operation": "increment"},
            ],
        },
        {
            "id": "user_confirmation",
            "type": "user_input",
            "prompt": "Confirm processing {{ processed_count }} items?",
            "validation": {"type": "regex", "pattern": "^(yes|no)$", "flags": "i"},
            "store_path": "raw.user_confirmed",
        },
        {
            "id": "finalize",
            "type": "conditional",
            "condition": "{{ user_confirmed == 'yes' }}",
            "then": [{"id": "complete", "type": "state_update", "path": "raw.status", "value": "completed"}],
            "else": [{"id": "cancel", "type": "state_update", "path": "raw.status", "value": "cancelled"}],
        },
    ]

    state_schema = {
        "raw": {
            "items": "array",
            "status": "string",
            "attempts": "number",
            "user_confirmed": "string",
            "processed_items": "array",
        },
        "computed": {
            "input_count": {"from": ["raw.items"], "transform": "input[0] ? input[0].length : 0"},
            "ready_batches": {
                "from": ["raw.items"],
                "transform": "input[0] ? input[0].map((item, i) => ({id: i, item})) : []",
            },
            "processed_count": {"from": ["raw.processed_items"], "transform": "input[0] ? input[0].length : 0"},
            "success": {"from": ["raw.status"], "transform": "input[0] === 'completed'"},
        },
        "state": {"version": "string", "workflow_type": "string"},
    }

    default_state = {
        "raw": {"items": [], "status": "pending", "attempts": 0, "processed_items": []},
        "state": {"version": "1.0", "workflow_type": "complex_test"},
    }

    # Convert steps to WorkflowStep objects
    workflow_steps = []
    for i, step in enumerate(steps):
        workflow_steps.append(
            WorkflowStep(
                id=step.get("id", f"step_{i}"),
                type=step.get("type", "unknown"),
                definition=step,
            )
        )

    return WorkflowDefinition(
        name="test:complex",
        description="Complex workflow for testing advanced features",
        version="1.0.0",
        steps=workflow_steps,
        state_schema=StateSchema(**state_schema),
        default_state=default_state,
        inputs={},
    )


def create_error_prone_workflow() -> WorkflowDefinition:
    """Create a workflow designed to test error handling."""

    steps = [
        {
            "id": "risky_operation",
            "type": "shell_command",
            "command": "exit {{ failure_rate > 50 ? 1 : 0 }}",
            "on_error": "retry",
            "retry_count": 3,
            "retry_delay": 1000,
        },
        {
            "id": "transformation_error",
            "type": "state_update",
            "path": "computed.risky_calc",
            "value": "{{ 1 / zero_value }}",  # Division by zero
        },
        {
            "id": "external_service",
            "type": "mcp_call",
            "method": "unreliable_service",
            "params": {},
            "on_error": "circuit_breaker",
            "failure_threshold": 3,
            "circuit_timeout": 30000,
        },
        {
            "id": "validation_check",
            "type": "conditional",
            "condition": "{{ required_field }}",
            "then": [{"id": "continue_processing", "type": "state_update", "path": "raw.validated", "value": True}],
            "else": [{"id": "validation_error", "type": "error", "message": "Required field missing"}],
        },
    ]

    state_schema = {
        "raw": {"failure_rate": "number", "zero_value": "number", "required_field": "string", "validated": "boolean"},
        "computed": {
            "risky_calc": {
                "from": ["raw.zero_value"],
                "transform": "1 / input[0]",
                "on_error": "use_fallback",
                "fallback": 0,
            }
        },
        "state": {"version": "string"},
    }

    default_state = {
        "raw": {
            "failure_rate": 75,  # High failure rate for testing
            "zero_value": 0,  # Will cause division by zero
            "validated": False,
        },
        "state": {"version": "1.0"},
    }

    # Convert steps to WorkflowStep objects
    workflow_steps = []
    for i, step in enumerate(steps):
        workflow_steps.append(
            WorkflowStep(
                id=step.get("id", f"step_{i}"),
                type=step.get("type", "unknown"),
                definition=step,
            )
        )

    return WorkflowDefinition(
        name="test:error_prone",
        description="Workflow designed to test error handling",
        version="1.0.0",
        steps=workflow_steps,
        state_schema=StateSchema(**state_schema),
        default_state=default_state,
        inputs={},
    )


def create_performance_test_workflow(item_count: int = 1000) -> WorkflowDefinition:
    """Create a workflow for performance testing."""

    steps = [
        {"id": "generate_items", "type": "state_update", "path": "raw.items", "value": list(range(item_count))},
        {
            "id": "process_all_items",
            "type": "foreach",
            "items": "{{ items }}",
            "body": [
                {
                    "id": "process_item",
                    "type": "state_update",
                    "path": "raw.processed_items",
                    "operation": "append",
                    "value": "{{ item * 2 }}",
                }
            ],
        },
        {
            "id": "parallel_batch_processing",
            "type": "parallel_foreach",
            "items": "{{ batches }}",
            "max_parallel": 10,
            "sub_agent_task": "process_batch",
        },
    ]

    state_schema = {
        "raw": {"items": "array", "processed_items": "array"},
        "computed": {
            "batches": {
                "from": ["raw.items"],
                "transform": """
                    const batchSize = 100;
                    const items = input[0] || [];
                    const batches = [];
                    for (let i = 0; i < items.length; i += batchSize) {
                        batches.push({
                            id: Math.floor(i / batchSize),
                            items: items.slice(i, i + batchSize)
                        });
                    }
                    return batches;
                """,
            },
            "total_processed": {"from": ["raw.processed_items"], "transform": "input[0] ? input[0].length : 0"},
        },
        "state": {"version": "string"},
    }

    default_state = {"raw": {"items": [], "processed_items": []}, "state": {"version": "1.0"}}

    # Convert steps to WorkflowStep objects
    workflow_steps = []
    for i, step in enumerate(steps):
        workflow_steps.append(
            WorkflowStep(
                id=step.get("id", f"step_{i}"),
                type=step.get("type", "unknown"),
                definition=step,
            )
        )

    return WorkflowDefinition(
        name="test:performance",
        description=f"Performance test workflow with {item_count} items",
        version="1.0.0",
        steps=workflow_steps,
        state_schema=StateSchema(**state_schema),
        default_state=default_state,
        inputs={},
    )


def create_test_workflow_yaml_dict(name: str = "test:simple") -> dict[str, Any]:
    """Create a workflow definition as a dictionary (for YAML serialization)."""

    return {
        "name": name,
        "description": "Simple test workflow",
        "version": "1.0.0",
        "state_schema": {
            "raw": {"counter": "number", "name": "string"},
            "computed": {"greeting": {"from": ["raw.name"], "transform": "`Hello ${input[0] || 'World'}!`"}},
            "state": {"version": "string"},
        },
        "default_state": {"raw": {"counter": 0}, "state": {"version": "1.0"}},
        "steps": [
            {"id": "increment", "type": "state_update", "path": "raw.counter", "operation": "increment"},
            {"id": "show_greeting", "type": "user_message", "message": "{{ greeting }}"},
        ],
    }


def create_sample_errors() -> list[WorkflowError]:
    """Create sample workflow errors for testing."""

    errors = [
        WorkflowError(
            id="err_001",
            workflow_id="wf_001",
            step_id="step_1",
            error_type="ValidationError",
            message="Invalid input parameter",
            stack_trace="Traceback...",
            timestamp=datetime.now(),
            severity=ErrorSeverity.HIGH,
        ),
        WorkflowError(
            id="err_002",
            workflow_id="wf_001",
            step_id="step_2",
            error_type="ConnectionError",
            message="Failed to connect to external service",
            stack_trace="Traceback...",
            timestamp=datetime.now(),
            retry_count=2,
            severity=ErrorSeverity.MEDIUM,
        ),
        WorkflowError(
            id="err_003",
            workflow_id="wf_002",
            step_id="step_1",
            error_type="TimeoutError",
            message="Operation timed out after 30 seconds",
            stack_trace="Traceback...",
            timestamp=datetime.now(),
            recovered=True,
            severity=ErrorSeverity.LOW,
        ),
    ]

    return errors
