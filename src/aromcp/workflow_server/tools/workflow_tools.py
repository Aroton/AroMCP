"""MCP tools for workflow management and execution."""

import json
from typing import Any

from ...utils.json_parameter_middleware import json_convert
from ..state.manager import StateManager
from ..workflow.executor import WorkflowExecutor
from ..workflow.loader import WorkflowLoader
from ..workflow.models import WorkflowExecutionError, WorkflowNotFoundError

# Global instances for workflow management
_workflow_loader = None
_workflow_executor = None
_state_manager = None


def get_workflow_loader() -> WorkflowLoader:
    """Get or create workflow loader instance."""
    global _workflow_loader
    if _workflow_loader is None:
        _workflow_loader = WorkflowLoader()
    return _workflow_loader


def get_workflow_executor() -> WorkflowExecutor:
    """Get or create workflow executor instance."""
    global _workflow_executor, _state_manager
    if _workflow_executor is None:
        if _state_manager is None:
            _state_manager = StateManager()
        _workflow_executor = WorkflowExecutor(_state_manager)
    return _workflow_executor


def get_state_manager() -> StateManager:
    """Get or create state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def register_workflow_tools(mcp):
    """Register all workflow management tools with FastMCP server."""

    @mcp.tool
    @json_convert
    def workflow_get_info(workflow: str) -> dict[str, Any]:
        """Get workflow metadata and input requirements.

        Use this tool when:
        - You need to understand what inputs a workflow requires
        - You want to see workflow description and version
        - You're preparing to start a workflow and need input schema
        - You want to validate a workflow exists before starting

        Args:
            workflow: Name of the workflow (e.g., "test:simple", "standards:fix")

        Returns:
            Workflow metadata including inputs, description, and requirements

        Example:
            workflow_get_info("test:simple")
            → {"name": "test:simple", "inputs": {...}, "description": "..."}
        """
        try:
            loader = get_workflow_loader()
            workflow_def = loader.load(workflow)

            # Extract input requirements
            input_info = {}
            for name, input_def in workflow_def.inputs.items():
                input_info[name] = {
                    "type": input_def.type,
                    "description": input_def.description,
                    "required": input_def.required,
                    "default": input_def.default
                }

            return {
                "data": {
                    "name": workflow_def.name,
                    "description": workflow_def.description,
                    "version": workflow_def.version,
                    "inputs": input_info,
                    "total_steps": len(workflow_def.steps),
                    "source": workflow_def.source,
                    "loaded_from": workflow_def.loaded_from
                }
            }

        except WorkflowNotFoundError as e:
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(e)
                }
            }
        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to get workflow info: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_start(workflow: str, inputs: dict[str, Any] | str | None = None) -> dict[str, Any]:
        """Initialize and start a workflow instance.

        Use this tool when:
        - You're ready to begin executing a workflow
        - You have gathered all required inputs for the workflow
        - You want to create a new workflow instance for execution
        - You need to initialize workflow state with default values

        Args:
            workflow: Name of the workflow to start
            inputs: Input values for the workflow (optional)

        Returns:
            Workflow instance info with ID, initial state, and status

        Example:
            workflow_start("test:simple", {"name": "example"})
            → {"workflow_id": "wf_abc123", "state": {...}, "status": "running"}
        """
        try:
            loader = get_workflow_loader()
            executor = get_workflow_executor()

            # Load workflow definition
            workflow_def = loader.load(workflow)

            # Parse inputs if provided as string
            if isinstance(inputs, str):
                try:
                    inputs = json.loads(inputs)
                except json.JSONDecodeError:
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": "Inputs must be valid JSON if provided as string"
                        }
                    }

            # Start workflow
            result = executor.start(workflow_def, inputs)

            return {"data": result}

        except WorkflowNotFoundError as e:
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": str(e)
                }
            }
        except WorkflowExecutionError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": str(e)
                }
            }
        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to start workflow: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_list(include_global: bool = True) -> dict[str, Any]:
        """List available workflows from project and optionally global directories.

        Use this tool when:
        - You want to see what workflows are available
        - You're looking for a specific workflow to execute
        - You need to browse workflow options for a task
        - You want to see both project and global workflows

        Args:
            include_global: Whether to include global user workflows (default: True)

        Returns:
            List of available workflows with metadata

        Example:
            workflow_list()
            → {"workflows": [{"name": "test:simple", "source": "project", ...}]}
        """
        try:
            loader = get_workflow_loader()
            workflows = loader.list_available_workflows(include_global)

            return {
                "data": {
                    "workflows": workflows,
                    "count": len(workflows)
                }
            }

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to list workflows: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_get_next_step(workflow_id: str) -> dict[str, Any]:
        """Get the next atomic step to execute for a workflow.

        Use this tool when:
        - You need the next step to execute in a workflow
        - You're implementing workflow execution logic
        - You want to advance a workflow to its next action
        - You need to know what action to take next

        Args:
            workflow_id: ID of the workflow instance

        Returns:
            Next step to execute or completion status

        Example:
            workflow_get_next_step("wf_abc123")
            → {"step": {"type": "state_update", "definition": {...}}}
        """
        try:
            executor = get_workflow_executor()
            next_step = executor.get_next_step(workflow_id)

            if next_step is None:
                # Workflow is complete
                status = executor.get_workflow_status(workflow_id)
                return {
                    "data": {
                        "completed": True,
                        "status": status["status"],
                        "workflow_id": workflow_id
                    }
                }

            return {"data": next_step}

        except WorkflowExecutionError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": str(e)
                }
            }
        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to get next step: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_step_complete(workflow_id: str, step_id: str, status: str = "success",
                              result: dict[str, Any] | str | None = None) -> dict[str, Any]:
        """Mark a workflow step as complete and advance to next step.

        Use this tool when:
        - You have finished executing a workflow step
        - You need to report step completion status
        - You want to advance the workflow to the next step
        - You have results or errors to report from step execution

        Args:
            workflow_id: ID of the workflow instance
            step_id: ID of the completed step
            status: "success" or "failed" (default: "success")
            result: Optional result data from step execution

        Returns:
            Updated workflow status and progress

        Example:
            workflow_step_complete("wf_abc123", "step_1", "success", {"output": "..."})
            → {"status": "running", "current_step_index": 1}
        """
        try:
            executor = get_workflow_executor()

            # Parse result if provided as string
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {"raw_result": result}

            # Extract error message if step failed
            error_message = None
            if status == "failed" and result:
                error_message = result.get("error", "Step execution failed")

            completion_result = executor.step_complete(
                workflow_id,
                step_id,
                status,
                result,
                error_message
            )

            return {"data": completion_result}

        except WorkflowExecutionError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": str(e)
                }
            }
        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to complete step: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_get_status(workflow_id: str) -> dict[str, Any]:
        """Get current status and progress of a workflow instance.

        Use this tool when:
        - You want to check workflow progress
        - You need current workflow state information
        - You're monitoring workflow execution
        - You want to see completion status

        Args:
            workflow_id: ID of the workflow instance

        Returns:
            Current workflow status, progress, and state

        Example:
            workflow_get_status("wf_abc123")
            → {"status": "running", "current_step_index": 2, "state": {...}}
        """
        try:
            executor = get_workflow_executor()
            status = executor.get_workflow_status(workflow_id)

            return {"data": status}

        except WorkflowExecutionError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": str(e)
                }
            }
        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to get workflow status: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_update_state(workflow_id: str, updates: list[dict[str, Any]] | str) -> dict[str, Any]:
        """Update workflow state with one or more changes.

        Use this tool when:
        - You need to update workflow state from step results
        - You want to store intermediate results in workflow state
        - You need to modify state based on external inputs
        - You're implementing state changes from step execution

        Args:
            workflow_id: ID of the workflow instance
            updates: List of state updates with path and value

        Returns:
            Updated workflow state

        Example:
            workflow_update_state("wf_abc123", [{"path": "raw.counter", "value": 5}])
            → {"counter": 5, "computed_field": 10}
        """
        try:
            executor = get_workflow_executor()

            # Parse updates if provided as string
            if isinstance(updates, str):
                try:
                    updates = json.loads(updates)
                except json.JSONDecodeError:
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": "Updates must be valid JSON if provided as string"
                        }
                    }

            updated_state = executor.update_workflow_state(workflow_id, updates)

            return {"data": {"state": updated_state}}

        except WorkflowExecutionError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": str(e)
                }
            }
        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to update workflow state: {e}"
                }
            }

    @mcp.tool
    @json_convert
    def workflow_list_active() -> dict[str, Any]:
        """List all currently active workflow instances.

        Use this tool when:
        - You want to see what workflows are currently running
        - You need to monitor active workflow instances
        - You're debugging workflow execution issues
        - You want to check for incomplete workflows

        Returns:
            List of active workflow instances with basic info

        Example:
            workflow_list_active()
            → {"workflows": [{"workflow_id": "wf_abc123", "status": "running", ...}]}
        """
        try:
            executor = get_workflow_executor()
            active_workflows = executor.list_active_workflows()

            return {
                "data": {
                    "workflows": active_workflows,
                    "count": len(active_workflows)
                }
            }

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to list active workflows: {e}"
                }
            }
