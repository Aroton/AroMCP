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
    type: str  # "mcp_call", "state_update", "user_message", "shell_command"
    definition: dict[str, Any]


@dataclass
class SubAgentTask:
    """Definition of a task that can be delegated to sub-agents."""

    name: str
    description: str
    inputs: dict[str, InputDefinition]
    steps: list[WorkflowStep]
    context_template: dict[str, Any] = field(default_factory=dict)
    prompt_template: str = ""


@dataclass
class WorkflowDefinition:
    """Complete definition of a workflow."""

    name: str
    description: str
    version: str
    default_state: dict[str, Any]
    state_schema: StateSchema
    inputs: dict[str, InputDefinition]
    steps: list[WorkflowStep]
    sub_agent_tasks: dict[str, SubAgentTask] = field(default_factory=dict)
    loaded_from: str = ""  # File path where loaded
    source: str = ""  # "project" | "global"


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
