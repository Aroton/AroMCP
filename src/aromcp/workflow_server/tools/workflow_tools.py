"""MCP tools for workflow management and execution."""

import json
import time
from typing import Any

from ...utils.json_parameter_middleware import json_convert
from ..models.workflow_models import WorkflowStartResponse
from ..state.concurrent import ConcurrentStateManager
from ..state.shared import get_shared_state_manager
from ..workflow.executor import WorkflowExecutor
from ..workflow.loader import WorkflowLoader
from ..workflow.models import WorkflowExecutionError, WorkflowNotFoundError
from ..workflow.parallel import ParallelForEachProcessor
from ..workflow.sub_agents import SubAgentManager

# Global instances for workflow management
_workflow_loader = None
_workflow_executor = None
_concurrent_state_manager = None
_sub_agent_manager = None
_parallel_processor = None


def get_workflow_loader() -> WorkflowLoader:
    """Get or create workflow loader instance."""
    global _workflow_loader
    if _workflow_loader is None:
        _workflow_loader = WorkflowLoader()
    return _workflow_loader


def get_workflow_executor() -> WorkflowExecutor:
    """Get or create workflow executor instance."""
    global _workflow_executor
    if _workflow_executor is None:
        state_manager = get_shared_state_manager()
        _workflow_executor = WorkflowExecutor(state_manager)
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


def get_sub_agent_manager() -> SubAgentManager:
    """Get or create sub-agent manager instance."""
    global _sub_agent_manager
    if _sub_agent_manager is None:
        _sub_agent_manager = SubAgentManager()
    return _sub_agent_manager


def get_parallel_processor() -> ParallelForEachProcessor:
    """Get or create parallel processor instance."""
    global _parallel_processor
    if _parallel_processor is None:
        from ..workflow.expressions import ExpressionEvaluator

        _parallel_processor = ParallelForEachProcessor(ExpressionEvaluator())
    return _parallel_processor


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
                error_message = result.get("error", "Step execution failed")

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

            updated_state = executor.update_workflow_state(workflow_id, updates)

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
    def workflow_get_next_step(
        workflow_id: str, sub_agent_context: dict[str, Any] | str | None = None
    ) -> dict[str, Any]:
        """Get next step with sub-agent context support.

        Use this tool when:
        - You are a sub-agent getting your next task step
        - You need workflow guidance with your specific context
        - You are executing parallel tasks and need filtered steps
        - You want to advance workflow execution with context isolation

        Args:
            workflow_id: ID of the workflow instance
            sub_agent_context: Sub-agent context including task_id and context data

        Returns:
            Next step filtered for sub-agent or main workflow step

        Example:
            workflow_get_next_step("wf_abc123", {"task_id": "batch_0", "context": {...}})
            → {"step": {"type": "mcp_call", "definition": {...}}}
        """
        try:
            executor = get_workflow_executor()

            # Parse sub_agent_context if provided as string
            if isinstance(sub_agent_context, str):
                try:
                    sub_agent_context = json.loads(sub_agent_context)
                except json.JSONDecodeError:
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": "Sub-agent context must be valid JSON if provided as string",
                        }
                    }

            # If sub-agent context provided, get filtered steps
            if sub_agent_context and "task_id" in sub_agent_context:
                sub_agent_manager = get_sub_agent_manager()
                agent = sub_agent_manager.get_agent_by_task_id(workflow_id, sub_agent_context["task_id"])

                if agent:
                    # Record activity
                    sub_agent_manager.record_agent_activity(agent.agent_id)

                    # Get filtered steps for this sub-agent
                    filtered_steps = sub_agent_manager.get_filtered_steps_for_agent(agent.agent_id)

                    if filtered_steps:
                        next_step = filtered_steps[0]  # Get next step
                        return {"data": {"step": next_step}}
                    else:
                        # Sub-agent task complete
                        sub_agent_manager.update_agent_status(agent.agent_id, "completed")
                        return {
                            "data": {
                                "completed": True,
                                "task_id": sub_agent_context["task_id"],
                                "workflow_id": workflow_id,
                            }
                        }
                else:
                    return {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"Sub-agent not found for task_id: {sub_agent_context['task_id']}",
                        }
                    }

            # Regular workflow step processing
            next_step = executor.get_next_step(workflow_id)

            if next_step is None:
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

    @mcp.tool
    @json_convert
    def workflow_create_sub_agent(
        workflow_id: str,
        task_id: str,
        task_name: str,
        context: dict[str, Any] | str,
        parent_step_id: str,
        custom_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Create a sub-agent for parallel task execution.

        Use this tool when:
        - You need to delegate work to a sub-agent
        - You are implementing parallel_foreach step execution
        - You want to isolate task context for specific work
        - You need to distribute work across multiple agents

        Args:
            workflow_id: Parent workflow ID
            task_id: Unique identifier for this task
            task_name: Name of task definition to execute
            context: Context data for the sub-agent
            parent_step_id: ID of step that created this sub-agent
            custom_prompt: Optional custom prompt override

        Returns:
            Sub-agent registration information and prompt

        Example:
            workflow_create_sub_agent("wf_abc123", "batch_0", "process_batch",
                                    {"files": ["a.ts", "b.ts"]}, "step_3")
            → {"agent_id": "agent_xyz", "task_id": "batch_0", "prompt": "..."}
        """
        try:
            # Parse context if provided as string
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except json.JSONDecodeError:
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": "Context must be valid JSON if provided as string",
                        }
                    }

            sub_agent_manager = get_sub_agent_manager()

            # Create sub-agent
            registration = sub_agent_manager.create_sub_agent(
                workflow_id=workflow_id,
                task_id=task_id,
                task_name=task_name,
                context=context,
                parent_step_id=parent_step_id,
                custom_prompt=custom_prompt,
            )

            if registration:
                return {
                    "data": {
                        "agent_id": registration.agent_id,
                        "task_id": registration.task_id,
                        "workflow_id": registration.workflow_id,
                        "prompt": registration.prompt,
                        "context": registration.context.to_dict(),
                        "status": registration.status,
                        "created_at": registration.created_at,
                    }
                }
            else:
                return {
                    "error": {"code": "CREATION_FAILED", "message": f"Failed to create sub-agent for task: {task_name}"}
                }

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to create sub-agent: {e}"}}

    @mcp.tool
    @json_convert
    def workflow_get_sub_agent_status(workflow_id: str, task_id: str | None = None) -> dict[str, Any]:
        """Get status of sub-agents for a workflow.

        Use this tool when:
        - You want to monitor parallel task execution progress
        - You need to check if sub-agents have completed their work
        - You want to see which tasks are still running
        - You need to coordinate between parallel sub-agents

        Args:
            workflow_id: Workflow ID to check sub-agents for
            task_id: Optional specific task ID to check

        Returns:
            Sub-agent status information and statistics

        Example:
            workflow_get_sub_agent_status("wf_abc123")
            → {"total_agents": 3, "completed": 2, "active": 1, "agents": [...]}
        """
        try:
            sub_agent_manager = get_sub_agent_manager()

            if task_id:
                # Get specific sub-agent
                agent = sub_agent_manager.get_agent_by_task_id(workflow_id, task_id)
                if agent:
                    return {
                        "data": {
                            "agent_id": agent.agent_id,
                            "task_id": agent.task_id,
                            "status": agent.status,
                            "step_count": agent.step_count,
                            "last_activity": agent.last_activity,
                            "error": agent.error,
                        }
                    }
                else:
                    return {"error": {"code": "NOT_FOUND", "message": f"Sub-agent not found for task_id: {task_id}"}}
            else:
                # Get all sub-agents for workflow
                agents = sub_agent_manager.get_workflow_agents(workflow_id)
                stats = sub_agent_manager.get_agent_stats(workflow_id)

                agent_data = [
                    {
                        "agent_id": agent.agent_id,
                        "task_id": agent.task_id,
                        "status": agent.status,
                        "step_count": agent.step_count,
                        "last_activity": agent.last_activity,
                        "error": agent.error,
                    }
                    for agent in agents
                ]

                return {"data": {"workflow_id": workflow_id, "agents": agent_data, "stats": stats}}

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to get sub-agent status: {e}"}}
