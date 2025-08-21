"""Implementation of workflow_start MCP tool."""

import logging
from typing import Any

from ..models.workflow_models import StartWorkflowResponse
from ..temporal_client import get_temporal_manager
from ..yaml_loader import load_workflow_yaml

logger = logging.getLogger(__name__)


async def workflow_start_impl(workflow: str, inputs: dict[str, Any] | None = None) -> StartWorkflowResponse:
    """Start a workflow execution.
    
    Args:
        workflow: Path to workflow YAML file or workflow name
        inputs: Optional input parameters for the workflow
        
    Returns:
        StartWorkflowResponse with workflow execution details
        
    Raises:
        ValueError: If workflow path/name is invalid or YAML is malformed
        FileNotFoundError: If workflow file does not exist
        RuntimeError: If Temporal client connection fails
    """
    logger.info(f"Starting workflow: {workflow} with inputs: {inputs}")

    try:
        # Load workflow definition from YAML
        logger.debug(f"Loading workflow definition for: {workflow}")
        try:
            workflow_def = load_workflow_yaml(workflow)
            logger.debug(f"Loaded workflow definition directly from path: {workflow}")
        except FileNotFoundError:
            # If direct path fails, try as workflow name in default directory
            logger.debug("Direct path failed, trying as workflow name in default directory")
            from ..config import get_config
            config = get_config()
            workflow_path = f"{config.workflow_definitions_path}{workflow}.yaml"
            try:
                workflow_def = load_workflow_yaml(workflow_path)
                logger.debug(f"Loaded workflow definition from: {workflow_path}")
            except FileNotFoundError:
                # Try with .yml extension
                workflow_path_yml = f"{config.workflow_definitions_path}{workflow}.yml"
                workflow_def = load_workflow_yaml(workflow_path_yml)
                logger.debug(f"Loaded workflow definition from: {workflow_path_yml}")

        # Get Temporal manager and ensure connection
        logger.debug("Getting Temporal manager and checking connection")
        manager = get_temporal_manager()
        if not manager.connected:
            # Attempt to connect
            logger.info("Temporal not connected, attempting to connect")
            connected = await manager.connect()
            if not connected:
                logger.error("Failed to connect to Temporal server")
                raise RuntimeError(
                    "Unable to connect to Temporal server. "
                    "In Phase 1, ensure WORKFLOW_MOCK_MODE=true is set."
                )
            logger.info("Successfully connected to Temporal")

        # Start workflow execution
        workflow_id = str(workflow_def.get("name", "workflow"))
        logger.info(f"Starting Temporal workflow with ID: {workflow_id}")
        handle = await manager.start_workflow(
            workflow_type="AroCMPWorkflow",
            workflow_id=workflow_id,
            args=[workflow_def, inputs or {}]
        )

        # Get initial status
        if hasattr(handle, 'get_status'):
            status = handle.get_status()
            logger.debug(f"Got workflow status: {status['status']}")
        else:
            # For real Temporal workflows, get status differently
            status = {
                "workflow_id": handle.id if hasattr(handle, 'id') else str(handle),
                "status": "running",
                "result": None,
                "error": None,
            }
            logger.debug("Created default status for real Temporal workflow")

        # Check if there's a pending action
        logger.debug("Checking for pending actions")
        from ..pending_actions import get_pending_actions_manager
        pending_manager = get_pending_actions_manager()
        pending_action = pending_manager.get_action(status["workflow_id"])

        # Prepare response
        action_dict = None
        if pending_action:
            logger.info(f"Found pending action of type: {pending_action.action_type}")
            action_dict = {
                "type": pending_action.action_type,
                "step_id": pending_action.step_id,
                "parameters": pending_action.parameters,
                "timeout": pending_action.timeout,
                "created_at": pending_action.created_at.isoformat(),
            }
        else:
            logger.debug("No pending actions found")

        response = StartWorkflowResponse(
            workflow_id=status["workflow_id"],
            status=status["status"],
            action=action_dict,
            result=status.get("result"),
            error=status.get("error"),
        )

        logger.info(f"Successfully started workflow {response.workflow_id} with status: {response.status}")
        return response

    except FileNotFoundError as e:
        logger.error(f"Workflow file not found: {workflow}. {str(e)}")
        return StartWorkflowResponse(
            workflow_id="",
            status="failed",
            action=None,
            result=None,
            error={"code": "NOT_FOUND", "message": f"Workflow not found: {workflow}. {str(e)}"}
        )
    except ValueError as e:
        logger.error(f"Invalid workflow definition: {str(e)}")
        return StartWorkflowResponse(
            workflow_id="",
            status="failed",
            action=None,
            result=None,
            error={"code": "INVALID_INPUT", "message": f"Invalid workflow definition: {str(e)}"}
        )
    except Exception as e:
        logger.error(f"Failed to start workflow: {str(e)}")
        return StartWorkflowResponse(
            workflow_id="",
            status="failed",
            action=None,
            result=None,
            error={"code": "OPERATION_FAILED", "message": f"Failed to start workflow: {str(e)}"}
        )
