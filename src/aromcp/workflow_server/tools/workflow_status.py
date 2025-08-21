"""Implementation of workflow_status MCP tool."""

import logging

from ..models.workflow_models import GetWorkflowStatusResponse
from ..pending_actions import get_pending_actions_manager
from ..temporal_client import get_temporal_manager

logger = logging.getLogger(__name__)


def workflow_status_impl(workflow_id: str) -> GetWorkflowStatusResponse:
    """Get status of a workflow execution.
    
    Args:
        workflow_id: ID of the workflow to get status for
        
    Returns:
        GetWorkflowStatusResponse with current workflow status
        
    Raises:
        ValueError: If workflow_id is invalid
        RuntimeError: If Temporal client connection fails
    """
    logger.info(f"Getting status for workflow: {workflow_id}")

    try:
        # Get Temporal manager
        logger.debug("Getting Temporal manager")
        manager = get_temporal_manager()
        if not manager.connected:
            logger.error("Not connected to Temporal server")
            return GetWorkflowStatusResponse(
                workflow_id=workflow_id,
                status="failed",
                current_step=None,
                pending_action=None,
                state=None,
                error={"code": "OPERATION_FAILED", "message": "Not connected to Temporal server"}
            )

        # Get workflow handle
        logger.debug(f"Getting workflow handle for: {workflow_id}")
        handle = manager.get_workflow(workflow_id)
        if handle is None:
            logger.error(f"Workflow not found: {workflow_id}")
            return GetWorkflowStatusResponse(
                workflow_id=workflow_id,
                status="failed",
                current_step=None,
                pending_action=None,
                state=None,
                error={"code": "NOT_FOUND", "message": f"Workflow not found: {workflow_id}"}
            )

        # Get workflow status
        logger.debug("Getting workflow status from handle")
        status = handle.get_status()
        logger.debug(f"Workflow {workflow_id} status: {status['status']}")

        # Get pending action if exists
        logger.debug("Checking for pending actions")
        pending_manager = get_pending_actions_manager()
        pending_action = pending_manager.get_action(workflow_id)

        # Prepare pending action dict
        pending_action_dict = None
        if pending_action:
            logger.debug(f"Found pending action of type: {pending_action.action_type}")
            pending_action_dict = {
                "type": pending_action.action_type,
                "step_id": pending_action.step_id,
                "parameters": pending_action.parameters,
                "timeout": pending_action.timeout,
                "created_at": pending_action.created_at.isoformat(),
                "retry_count": pending_action.retry_count,
            }
        else:
            logger.debug("No pending actions found")

        response = GetWorkflowStatusResponse(
            workflow_id=workflow_id,
            status=status["status"],
            current_step=status.get("current_step"),
            pending_action=pending_action_dict,
            state=status.get("state"),
            error=status.get("error"),
        )

        logger.info(f"Successfully retrieved status for workflow {workflow_id}: {response.status}")
        return response

    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error for workflow {workflow_id}: {str(e)}")
        return GetWorkflowStatusResponse(
            workflow_id=workflow_id,
            status="failed",
            current_step=None,
            pending_action=None,
            state=None,
            error={"code": "INVALID_INPUT", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to get workflow status for {workflow_id}: {str(e)}")
        return GetWorkflowStatusResponse(
            workflow_id=workflow_id,
            status="failed",
            current_step=None,
            pending_action=None,
            state=None,
            error={"code": "OPERATION_FAILED", "message": f"Failed to get workflow status: {str(e)}"}
        )
