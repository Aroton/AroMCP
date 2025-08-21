"""Implementation of submit_result MCP tool."""

import logging
from typing import Any

from ..models.workflow_models import SubmitResultResponse
from ..pending_actions import get_pending_actions_manager
from ..temporal_client import get_temporal_manager

logger = logging.getLogger(__name__)


def submit_result_impl(workflow_id: str, result: Any) -> SubmitResultResponse:
    """Submit result for a pending workflow action.
    
    Args:
        workflow_id: ID of the workflow to submit result for
        result: Result data from the completed action
        
    Returns:
        SubmitResultResponse with next action or completion status
        
    Raises:
        ValueError: If workflow_id is invalid or no pending action exists
        RuntimeError: If workflow execution fails
    """
    logger.info(f"Submitting result for workflow {workflow_id}: {result}")

    try:
        # Get Temporal manager
        logger.debug("Getting Temporal manager")
        manager = get_temporal_manager()
        if not manager.connected:
            logger.error("Not connected to Temporal server")
            return SubmitResultResponse(
                workflow_id=workflow_id,
                status="failed",
                action=None,
                result=None,
                error={"code": "OPERATION_FAILED", "message": "Not connected to Temporal server"}
            )

        # Get workflow handle
        logger.debug(f"Getting workflow handle for: {workflow_id}")
        handle = manager.get_workflow(workflow_id)
        if handle is None:
            logger.error(f"Workflow not found: {workflow_id}")
            return SubmitResultResponse(
                workflow_id=workflow_id,
                status="failed",
                action=None,
                result=None,
                error={"code": "NOT_FOUND", "message": f"Workflow not found: {workflow_id}"}
            )

        # Get pending action manager
        logger.debug("Getting pending action manager")
        pending_manager = get_pending_actions_manager()
        pending_action = pending_manager.get_action(workflow_id)

        if pending_action is None:
            logger.debug("No pending action found, checking workflow status")
            # Check if workflow is already completed/failed
            status = handle.get_status()
            if status["status"] in ["completed", "failed"]:
                logger.info(f"Workflow {workflow_id} already in terminal state: {status['status']}")
                return SubmitResultResponse(
                    workflow_id=workflow_id,
                    status=status["status"],
                    action=None,
                    result=status.get("result"),
                    error=status.get("error"),
                )
            else:
                logger.error(f"No pending action found for workflow: {workflow_id}")
                return SubmitResultResponse(
                    workflow_id=workflow_id,
                    status="failed",
                    action=None,
                    result=None,
                    error={"code": "INVALID_INPUT", "message": f"No pending action found for workflow: {workflow_id}"}
                )

        # Store the completed step ID
        completed_step_id = pending_action.step_id
        logger.info(f"Completing step '{completed_step_id}' for workflow {workflow_id}")

        # Remove the pending action
        pending_manager.remove_action(workflow_id)
        logger.debug("Removed pending action from manager")

        try:
            # Submit result to workflow and get next action
            logger.debug("Submitting result to workflow handle")
            next_action_data = handle.submit_result(result)

            # Get updated status
            status = handle.get_status()
            logger.debug(f"Updated workflow status: {status['status']}")

            # Prepare next action if exists
            action_dict = None
            if next_action_data and handle.status == "pending_action":
                logger.info(f"Creating new pending action of type: {next_action_data['type']}")
                # Create new pending action

                from ..models.workflow_models import PendingAction

                new_pending_action = PendingAction(
                    workflow_id=workflow_id,
                    step_id=next_action_data["step_id"],
                    action_type=next_action_data["type"],
                    parameters=next_action_data["parameters"],
                    timeout=3600  # 1 hour default timeout
                )

                pending_manager.add_action(new_pending_action)

                action_dict = {
                    "type": new_pending_action.action_type,
                    "step_id": new_pending_action.step_id,
                    "parameters": new_pending_action.parameters,
                    "timeout": new_pending_action.timeout,
                    "created_at": new_pending_action.created_at.isoformat(),
                }
            else:
                logger.debug("No further actions pending")

            response = SubmitResultResponse(
                workflow_id=workflow_id,
                status=status["status"],
                action=action_dict,
                result=status.get("result"),
                error=status.get("error"),
            )

            logger.info(f"Successfully submitted result for workflow {workflow_id}, new status: {response.status}")
            return response

        except Exception as e:
            # If workflow execution fails, mark workflow as failed
            logger.error(f"Step execution failed for workflow {workflow_id}: {str(e)}")
            handle.fail_workflow(f"Step execution failed: {str(e)}")

            return SubmitResultResponse(
                workflow_id=workflow_id,
                status="failed",
                action=None,
                result=None,
                error={"code": "OPERATION_FAILED", "message": f"Step execution failed: {str(e)}"}
            )

    except ValueError as e:
        # Handle validation errors
        logger.error(f"Validation error for workflow {workflow_id}: {str(e)}")
        return SubmitResultResponse(
            workflow_id=workflow_id,
            status="failed",
            action=None,
            result=None,
            error={"code": "INVALID_INPUT", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Failed to submit workflow result for {workflow_id}: {str(e)}")
        return SubmitResultResponse(
            workflow_id=workflow_id,
            status="failed",
            action=None,
            result=None,
            error={"code": "OPERATION_FAILED", "message": f"Failed to submit workflow result: {str(e)}"}
        )
