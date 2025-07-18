"""Dataclass models for workflow server MCP tool output schemas."""

from dataclasses import dataclass
from typing import Any


@dataclass
class WorkflowInfoResponse:
    """Response schema for workflow_get_info tool."""

    name: str
    description: str
    version: str
    inputs: dict[str, Any]
    total_steps: int
    source: str
    loaded_from: str


@dataclass
class WorkflowStartResponse:
    """Response schema for workflow_start tool."""

    workflow_id: str
    status: str
    state: dict[str, Any]
    total_steps: int
    execution_context: dict[str, Any]


@dataclass
class WorkflowListResponse:
    """Response schema for workflow_list tool."""

    workflows: list[dict[str, Any]]
    count: int


@dataclass
class WorkflowStepCompleteResponse:
    """Response schema for workflow_step_complete tool."""

    workflow_id: str
    status: str
    current_step_index: int
    step_result: dict[str, Any]
    next_step: dict[str, Any] | None


@dataclass
class WorkflowStatusResponse:
    """Response schema for workflow_get_status tool."""

    workflow_id: str
    status: str
    current_step_index: int
    total_steps: int
    state: dict[str, Any]
    execution_context: dict[str, Any]


@dataclass
class WorkflowStateUpdateResponse:
    """Response schema for workflow_update_state tool."""

    workflow_id: str
    state: dict[str, Any]
    updated_fields: list[str]


@dataclass
class WorkflowActiveListResponse:
    """Response schema for workflow_list_active tool."""

    workflows: list[dict[str, Any]]
    count: int


@dataclass
class WorkflowNextStepResponse:
    """Response schema for workflow_get_next_step tool."""

    workflow_id: str
    step: dict[str, Any] | None
    completed: bool
    status: str | None


@dataclass
class WorkflowCheckpointResponse:
    """Response schema for workflow_checkpoint tool."""

    checkpoint_id: str
    workflow_id: str
    step_id: str
    reason: str
    created_at: str
    version: int


@dataclass
class WorkflowResumeResponse:
    """Response schema for workflow_resume tool."""

    resumed: bool
    workflow_id: str
    status: str
    current_step_index: int
    message: str


@dataclass
class WorkflowSubAgentCreateResponse:
    """Response schema for workflow_create_sub_agent tool."""

    agent_id: str
    task_id: str
    workflow_id: str
    prompt: str
    context: dict[str, Any]
    status: str
    created_at: str


@dataclass
class WorkflowSubAgentStatusResponse:
    """Response schema for workflow_get_sub_agent_status tool."""

    workflow_id: str
    agents: list[dict[str, Any]]
    stats: dict[str, Any]
