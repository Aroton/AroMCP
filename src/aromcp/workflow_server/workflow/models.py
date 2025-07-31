"""Workflow definition models for the MCP Workflow System."""

from dataclasses import dataclass, field
from typing import Any

from ..state.models import StateSchema


@dataclass
class InputDefinition:
    """Definition of a workflow input parameter."""

    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None
    validation: dict[str, Any] | None = None


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    id: str
    type: str  # "mcp_call", "user_message", "shell_command", "agent_prompt", "agent_response", etc.
    definition: dict[str, Any] = field(default_factory=dict)
    execution_context: str = "server"  # "server" or "client" - where the step executes (only used for shell_command)

    def __init__(
        self,
        id: str,
        type: str,
        definition: dict[str, Any] = None,
        execution_context: str = "server",
        config: dict[str, Any] = None,
        **kwargs,
    ):
        """Initialize WorkflowStep with support for config parameter as alias for definition."""
        self.id = id
        self.type = type
        self.execution_context = execution_context

        # Support config as alias for definition for backwards compatibility
        if definition is not None:
            self.definition = definition
        elif config is not None:
            self.definition = config
        else:
            self.definition = {}

        # Add any additional kwargs to definition
        self.definition.update(kwargs)


@dataclass
class SubAgentTask:
    """Definition of a task that can be delegated to sub-agents."""

    name: str
    description: str
    inputs: dict[str, InputDefinition]
    steps: list[WorkflowStep]
    context_template: dict[str, Any] = field(default_factory=dict)
    prompt_template: str = ""
    default_state: dict[str, Any] = field(default_factory=dict)
    state_schema: "StateSchema" = field(default_factory=lambda: StateSchema())


@dataclass
class WorkflowDefinition:
    """Complete definition of a workflow."""

    name: str
    description: str = ""
    version: str = "1.0"
    default_state: dict[str, Any] = field(default_factory=dict)
    state_schema: StateSchema = field(default_factory=lambda: StateSchema())
    inputs: dict[str, InputDefinition] = field(default_factory=dict)
    steps: list[WorkflowStep] = field(default_factory=list)
    sub_agent_tasks: dict[str, SubAgentTask] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)  # Configuration for debug mode, execution mode, etc.
    loaded_from: str = ""  # File path where loaded
    source: str = ""  # "project" | "global"

    def __post_init__(self):
        """Convert dict steps to WorkflowStep objects."""
        if self.steps:
            converted_steps = []
            for step in self.steps:
                if isinstance(step, dict):
                    # Convert dict to WorkflowStep
                    step_id = step.get("id", f"step_{len(converted_steps)}")
                    step_type = step.get("type", "unknown")
                    # Create definition from all other fields
                    definition = {k: v for k, v in step.items() if k not in ["id", "type"]}
                    converted_steps.append(WorkflowStep(id=step_id, type=step_type, definition=definition))
                else:
                    converted_steps.append(step)
            self.steps = converted_steps


@dataclass
class WorkflowInstance:
    """A running instance of a workflow."""

    id: str
    workflow_name: str
    definition: WorkflowDefinition
    current_step_index: int = 0
    status: str = "running"  # "running", "completed", "failed", "paused"
    created_at: str = ""
    completed_at: str | None = None
    error_message: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)  # Store workflow inputs


@dataclass
class StepExecution:
    """Execution information for a workflow step."""

    workflow_id: str
    step_id: str
    step_index: int
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    started_at: str | None = None
    completed_at: str | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None


class WorkflowNotFoundError(Exception):
    """Raised when a workflow cannot be found."""

    pass


class WorkflowValidationError(Exception):
    """Raised when a workflow fails validation."""

    pass


class WorkflowExecutionError(Exception):
    """Raised when workflow execution fails."""

    pass


class WorkflowStateError(Exception):
    """Raised when workflow state operations fail."""

    pass
