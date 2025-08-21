"""Dataclass models for workflow server MCP tool output schemas."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Phase 1 Core Tool Response Models (matching specification exactly)

@dataclass
class StartWorkflowResponse:
    """Response schema for start_workflow tool."""

    workflow_id: str  # Unique workflow identifier
    status: str  # "pending_action" | "running" | "completed"
    action: dict[str, Any] | None = None  # First action if any
    result: Any | None = None  # Final result if completed
    error: str | None = None  # Error message if failed


@dataclass
class SubmitResultResponse:
    """Response schema for submit_result tool."""

    workflow_id: str
    status: str  # "pending_action" | "running" | "completed"
    action: dict[str, Any] | None = None  # Next action if any
    result: Any | None = None  # Final result if completed
    error: str | None = None


@dataclass
class GetWorkflowStatusResponse:
    """Response schema for get_workflow_status tool."""

    workflow_id: str
    status: str  # "pending_action" | "running" | "completed" | "failed"
    current_step: str | None = None  # Current step being executed
    pending_action: dict[str, Any] | None = None
    state: dict[str, Any] | None = None  # Current workflow state
    error: str | None = None


@dataclass
class HealthCheckResponse:
    """Response schema for health check tool."""

    status: str  # "healthy" | "unhealthy"
    components: dict[str, Any]
    timestamp: str | None = None
    mock_mode: bool | None = None
    error: str | None = None


# Legacy response models for compatibility with existing tools
WorkflowStartResponse = StartWorkflowResponse
WorkflowSubmitResponse = SubmitResultResponse
WorkflowStatusResponse = GetWorkflowStatusResponse


@dataclass
class WorkflowListResponse:
    """Response schema for workflow_list tool."""

    workflows: list[dict[str, Any]]
    total: int
    # Standard cursor pagination fields
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class WorkflowStepResponse:
    """Response schema for workflow_step tool."""

    step_id: str
    workflow_id: str
    status: str  # "completed" | "failed" | "pending_action"
    result: dict[str, Any] | None = None
    next_step: str | None = None
    action: dict[str, Any] | None = None  # If step requires Claude action


@dataclass
class StateGetResponse:
    """Response schema for state_get tool."""

    workflow_id: str
    state: dict[str, Any]
    keys_requested: list[str] | None = None  # Keys that were specifically requested
    full_state: bool = False  # Whether this is the complete state


@dataclass
class StateUpdateResponse:
    """Response schema for state_update tool."""

    workflow_id: str
    updated_keys: list[str]
    new_state: dict[str, Any]
    previous_values: dict[str, Any] | None = None


@dataclass
class StateTransformResponse:
    """Response schema for state_transform tool."""

    workflow_id: str
    transformation_applied: str  # Description of transformation
    new_state: dict[str, Any]
    previous_state: dict[str, Any] | None = None
    errors: list[str] | None = None  # JavaScript execution errors if any


@dataclass
class StateClearResponse:
    """Response schema for state_clear tool."""

    workflow_id: str
    cleared_keys: list[str] | None = None  # Specific keys cleared, None if all cleared
    previous_state: dict[str, Any] | None = None
    success: bool = True


# Internal models for workflow management

@dataclass
class PendingAction:
    """Internal model for tracking pending workflow actions."""

    workflow_id: str
    step_id: str
    action_type: str  # "shell" | "mcp_call" | "prompt" | "wait" | "delegate"
    parameters: dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    timeout: int | None = None  # Timeout in seconds
    retry_count: int = 0  # Number of retries attempted
