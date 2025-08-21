"""Workflow server tools implementations."""

import asyncio
from typing import Any

from ...utils.json_parameter_middleware import json_convert
from ..models.workflow_models import (
    GetWorkflowStatusResponse,
    HealthCheckResponse,
    StartWorkflowResponse,
    SubmitResultResponse,
)
from .health_check import health_check_impl
from .submit_result import submit_result_impl
from .workflow_start import workflow_start_impl
from .workflow_status import workflow_status_impl


def register_workflow_tools(mcp, temporal_manager, pending_actions, config):
    """Register workflow tools with the MCP server as specified in Phase 1."""

    @mcp.tool
    @json_convert
    def start_workflow(workflow: str, inputs: dict[str, Any] | str | None = None) -> StartWorkflowResponse:
        """Start a workflow execution.

        Use this tool when:
        - Starting a new workflow from a YAML definition
        - Initiating automated task sequences with Claude interaction points
        - Beginning multi-step processes that require state management
        - Launching workflows that need to wait for external actions

        Args:
            workflow: Path to workflow YAML file or workflow name (without extension)
            inputs: Optional input parameters for the workflow initialization

        Examples:
            workflow_start("deploy-app")
            → {"workflow_id": "abc-123", "status": "pending_action", "action": {"type": "shell", "parameters": {...}}}

            workflow_start("/path/to/custom-workflow.yaml", {"environment": "production"})
            → {"workflow_id": "def-456", "status": "running", "action": null}

        Note: In Phase 1, workflows run in mock mode. Set WORKFLOW_MOCK_MODE=true in environment.
        Returns pending actions that require Claude execution via workflow_submit.
        """
        # Convert inputs if it's a JSON string
        if isinstance(inputs, str):
            import json
            try:
                inputs = json.loads(inputs)
            except json.JSONDecodeError:
                inputs = None

        # Use asyncio to run the async implementation
        return asyncio.run(workflow_start_impl(workflow, inputs))

    @mcp.tool
    @json_convert
    def submit_result(workflow_id: str, result: Any) -> SubmitResultResponse:
        """Submit result for a pending workflow action and continue execution.

        Use this tool when:
        - Providing results from completed shell commands or MCP calls
        - Submitting user input or decisions back to waiting workflows
        - Continuing workflow execution after manual intervention
        - Advancing workflows that were paused for external actions

        Args:
            workflow_id: ID of the workflow awaiting result submission
            result: Result data from the completed action (any JSON-serializable value)

        Examples:
            workflow_submit("abc-123", {"exit_code": 0, "output": "Success"})
            → {"workflow_id": "abc-123", "status": "pending_action", "action": {"type": "mcp_call", ...}}

            workflow_submit("def-456", "user approved")
            → {"workflow_id": "def-456", "status": "completed", "result": "Workflow finished successfully"}

        Note: Use workflow_status to check current workflow state before submitting.
        Returns next action if workflow continues, or final result if completed.
        """
        return submit_result_impl(workflow_id, result)

    @mcp.tool
    @json_convert
    def get_workflow_status(workflow_id: str) -> GetWorkflowStatusResponse:
        """Get current status and details of a workflow execution.

        Use this tool when:
        - Checking if a workflow is waiting for action or completed
        - Monitoring workflow progress and current step
        - Retrieving workflow state and execution context
        - Debugging workflow execution issues

        Args:
            workflow_id: ID of the workflow to check status for

        Examples:
            workflow_status("abc-123")
            → {"workflow_id": "abc-123", "status": "pending_action", "current_step": "deploy", "pending_action": {...}}

            workflow_status("def-456")
            → {"workflow_id": "def-456", "status": "completed", "result": "Success", "progress": {"percentage": 100}}

        Note: Status can be "pending_action", "running", "completed", "failed", or "cancelled".
        Pending actions indicate the workflow is waiting for Claude to execute a step.
        """
        return workflow_status_impl(workflow_id)

    @mcp.tool
    @json_convert
    def health_check() -> HealthCheckResponse:
        """Check health of workflow server components.

        Use this tool when:
        - Verifying workflow server is operational and connected to Temporal
        - Diagnosing connection issues or server problems
        - Monitoring server status before starting workflows
        - Checking if server is in mock mode vs connected to real Temporal

        Examples:
            health_check()
            → {"status": "healthy", "components": {"temporal": {"status": "healthy", "connected": true}}}

            health_check()  # When not connected
            → {"status": "unhealthy", "components": {"temporal": {"status": "unhealthy", "connected": false}}}

        Note: In Phase 1, server typically runs in mock mode with WORKFLOW_MOCK_MODE=true.
        Returns detailed status of Temporal connection and active workflows.
        """
        return health_check_impl()


__all__ = [
    "workflow_start_impl",
    "submit_result_impl",
    "workflow_status_impl",
    "health_check_impl",
    "register_workflow_tools",
]
