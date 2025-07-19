"""MCP tools for workflow management and execution."""

import json
import time
from typing import Any

from ...utils.json_parameter_middleware import json_convert
from ..models.workflow_models import WorkflowStartResponse
from ..state.concurrent import ConcurrentStateManager
from ..state.shared import get_shared_state_manager
from ..workflow.queue_executor import QueueBasedWorkflowExecutor
from ..workflow.loader import WorkflowLoader
from ..workflow.models import WorkflowExecutionError, WorkflowNotFoundError

# Global instances for workflow management
_workflow_loader = None
_workflow_executor = None
_concurrent_state_manager = None


def get_workflow_loader() -> WorkflowLoader:
    """Get or create workflow loader instance."""
    global _workflow_loader
    if _workflow_loader is None:
        _workflow_loader = WorkflowLoader()
    return _workflow_loader


def get_workflow_executor() -> QueueBasedWorkflowExecutor:
    """Get or create workflow executor instance."""
    global _workflow_executor
    if _workflow_executor is None:
        shared_state_manager = get_shared_state_manager()
        _workflow_executor = QueueBasedWorkflowExecutor(shared_state_manager)
    return _workflow_executor


def get_state_manager():
    """Get the shared state manager instance."""
    return get_shared_state_manager()


def get_concurrent_state_manager() -> ConcurrentStateManager:
    """Get or create concurrent state manager instance."""
    global _concurrent_state_manager
    if _concurrent_state_manager is None:
        state_manager = get_shared_state_manager()
        _concurrent_state_manager = ConcurrentStateManager(state_manager)
    return _concurrent_state_manager






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
                    "default": input_def.default,
                }

            return {
                "data": {
                    "name": workflow_def.name,
                    "description": workflow_def.description,
                    "version": workflow_def.version,
                    "inputs": input_info,
                    "total_steps": len(workflow_def.steps),
                    "source": workflow_def.source,
                    "loaded_from": workflow_def.loaded_from,
                }
            }

        except WorkflowNotFoundError as e:
            return {"error": {"code": "NOT_FOUND", "message": str(e)}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to get workflow info: {e}"}}

    @mcp.tool
    @json_convert
    def workflow_start(workflow: str, inputs: dict[str, Any] | str | None = None) -> WorkflowStartResponse:
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

            # @json_convert will have already converted string inputs to dict
            # Type cast since we know @json_convert ensures proper conversion
            parsed_inputs: dict[str, Any] | None = inputs  # type: ignore[assignment]

            # Start workflow
            result = executor.start(workflow_def, parsed_inputs)

            # Create response using dataclass
            response = WorkflowStartResponse(
                workflow_id=result["workflow_id"],
                status=result["status"],
                state=result["state"],
                total_steps=result["total_steps"],
                execution_context=result["execution_context"],
            )
            return response

        except WorkflowNotFoundError:
            raise
        except WorkflowExecutionError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to start workflow: {e}") from e

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

            return {"data": {"workflows": workflows, "count": len(workflows)}}

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to list workflows: {e}"}}

    @mcp.tool
    @json_convert
    def workflow_step_complete(
        workflow_id: str, step_id: str, status: str = "success", result: dict[str, Any] | str | None = None
    ) -> dict[str, Any]:
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
                if isinstance(result, dict):
                    error_message = result.get("error", "Step execution failed")
                else:
                    error_message = str(result)

            completion_result = executor.step_complete(workflow_id, step_id, status, result, error_message)

            return {"data": completion_result}

        except WorkflowExecutionError as e:
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to complete step: {e}"}}

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
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to get workflow status: {e}"}}

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
                            "message": "Updates must be valid JSON if provided as string",
                        }
                    }

            # Ensure updates is a list (json_convert handles this)
            if isinstance(updates, str):
                # This shouldn't happen with @json_convert, but just in case
                updates = json.loads(updates)
            
            # Type assertion for type checker
            parsed_updates: list[dict[str, Any]] = updates  # type: ignore[assignment]
            
            updated_state = executor.update_workflow_state(workflow_id, parsed_updates)

            return {"data": {"state": updated_state}}

        except WorkflowExecutionError as e:
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to update workflow state: {e}"}}

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

            return {"data": {"workflows": active_workflows, "count": len(active_workflows)}}

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to list active workflows: {e}"}}

    @mcp.tool
    @json_convert
    def workflow_get_next_step(workflow_id: str, task_id: str | None = None) -> dict[str, Any]:
        """Get next step in workflow execution or for a specific sub-agent task.

        Use this tool when:
        - You want to advance workflow execution
        - You are a sub-agent getting your next task step
        - You need the next actionable step
        - You want to check workflow completion status

        Args:
            workflow_id: ID of the workflow instance
            task_id: Optional task ID for sub-agent execution (e.g., "checkFile.item1")

        Returns:
            Next step for execution or completion status

        Example:
            workflow_get_next_step("wf_abc123")
            → {"step": {"type": "mcp_call", "definition": {...}}}
            
            workflow_get_next_step("wf_abc123", "checkFile.item1")
            → {"step": {"type": "mcp_call", "definition": {...}}}
            
        Note:
            If you get an error about "items must be an array", ensure your workflow state
            contains properly evaluated arrays instead of template strings. Use workflow_update_state
            to fix the state before calling this tool.
        """
        try:
            executor = get_workflow_executor()
            
            if task_id:
                # Sub-agent execution
                next_step = executor.get_next_sub_agent_step(task_id)
            else:
                # Main workflow execution
                next_step = executor.get_next_step(workflow_id)

            if next_step is None:
                if task_id:
                    return {"data": {"completed": True, "task_id": task_id, "workflow_id": workflow_id}}
                else:
                    status = executor.get_workflow_status(workflow_id)
                    return {"data": {"completed": True, "status": status["status"], "workflow_id": workflow_id}}

            return {"data": next_step}

        except WorkflowExecutionError as e:
            return {"error": {"code": "OPERATION_FAILED", "message": str(e)}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to get next step: {e}"}}

    @mcp.tool
    @json_convert
    def workflow_checkpoint(workflow_id: str, step_id: str, reason: str) -> dict[str, Any]:
        """Create workflow checkpoint for recovery.

        Use this tool when:
        - You want to save workflow state at a critical point
        - You need recovery capability for long-running workflows
        - You want to create save points before risky operations
        - You need to preserve state across system restarts

        Args:
            workflow_id: ID of the workflow instance
            step_id: Current step ID where checkpoint is created
            reason: Reason for creating checkpoint

        Returns:
            Checkpoint information and success status

        Example:
            workflow_checkpoint("wf_abc123", "step_5", "Before batch processing")
            → {"checkpoint_id": "cp_xyz", "created_at": "...", "version": 3}
        """
        try:
            concurrent_manager = get_concurrent_state_manager()

            # Create checkpoint
            checkpoint_result = concurrent_manager.create_checkpoint(workflow_id)

            if checkpoint_result["success"]:
                checkpoint = checkpoint_result["checkpoint"]
                checkpoint.update(
                    {"step_id": step_id, "reason": reason, "checkpoint_id": f"cp_{workflow_id}_{int(time.time())}"}
                )

                return {
                    "data": {
                        "checkpoint_id": checkpoint["checkpoint_id"],
                        "workflow_id": workflow_id,
                        "step_id": step_id,
                        "reason": reason,
                        "created_at": checkpoint["created_at"],
                        "version": checkpoint["version"],
                    }
                }
            else:
                return {
                    "error": {
                        "code": "CHECKPOINT_FAILED",
                        "message": checkpoint_result.get("message", "Failed to create checkpoint"),
                    }
                }

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to create checkpoint: {e}"}}

    @mcp.tool
    @json_convert
    def workflow_resume(workflow_id: str) -> dict[str, Any]:
        """Resume workflow from checkpoint.

        Use this tool when:
        - You want to restore a workflow from a saved checkpoint
        - You need to recover from a system failure or restart
        - You want to rollback to a previous workflow state
        - You need to continue execution from a known good state

        Args:
            workflow_id: ID of the workflow instance to resume

        Returns:
            Resume status and restored workflow information

        Example:
            workflow_resume("wf_abc123")
            → {"resumed": true, "restored_version": 3, "current_step": "step_5"}
        """
        try:
            # This is a simplified implementation
            # In a full system, you'd store checkpoints and restore from them
            executor = get_workflow_executor()
            status = executor.get_workflow_status(workflow_id)

            return {
                "data": {
                    "resumed": True,
                    "workflow_id": workflow_id,
                    "status": status["status"],
                    "current_step_index": status.get("current_step_index", 0),
                    "message": "Workflow resumed from current state",
                }
            }

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to resume workflow: {e}"}}


