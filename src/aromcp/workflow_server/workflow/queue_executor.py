"""Queue-based workflow executor implementation.

This executor uses a queue-based approach instead of recursive execution,
making it simpler, more debuggable, and less prone to infinite loops.
"""

import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from ..state.manager import StateManager
from .context import ExecutionContext, StackFrame, context_manager
from .expressions import ExpressionEvaluator
from .models import WorkflowDefinition, WorkflowInstance, WorkflowStep
from .queue import WorkflowQueue
from .step_processors import StepProcessor
from .step_registry import StepRegistry
from .subagent_manager import SubAgentManager


class QueueBasedWorkflowExecutor:
    """Queue-based workflow executor that processes steps sequentially."""
    
    def __init__(self, state_manager=None):
        self.workflows: dict[str, WorkflowInstance] = {}
        self.queues: dict[str, WorkflowQueue] = {}
        self.state_manager = state_manager if state_manager is not None else StateManager()
        self.step_registry = StepRegistry()
        self.expression_evaluator = ExpressionEvaluator()
        
        # Initialize processors
        self.step_processor = StepProcessor(self.state_manager, self.expression_evaluator)
        self.subagent_manager = SubAgentManager(self.state_manager, self.expression_evaluator, self.step_registry)
        
        # Add locks for thread safety
        self._workflow_locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()
    
    def _get_workflow_lock(self, workflow_id: str) -> threading.Lock:
        """Get or create a lock for a specific workflow."""
        with self._global_lock:
            if workflow_id not in self._workflow_locks:
                self._workflow_locks[workflow_id] = threading.Lock()
            return self._workflow_locks[workflow_id]
    
    def _get_state(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow state with proper error handling.
        
        Args:
            workflow_id: The workflow ID
            
        Returns:
            The workflow state
            
        Raises:
            ValueError: If workflow state not found
        """
        try:
            state = self.state_manager.read(workflow_id)
            if state is None:
                raise ValueError(f"No state found for workflow {workflow_id}")
            return state
        except Exception as e:
            raise ValueError(f"Failed to read state for workflow {workflow_id}: {str(e)}")
    
    def _update_state(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update workflow state with proper error handling.
        
        Args:
            workflow_id: The workflow ID
            updates: List of state updates to apply
            
        Returns:
            The result of the update operation
            
        Raises:
            ValueError: If update fails
        """
        try:
            return self.state_manager.update(workflow_id, updates)
        except Exception as e:
            raise ValueError(f"Failed to update state for workflow {workflow_id}: {str(e)}")
    
    def start(self, workflow_def: WorkflowDefinition, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Start a new workflow instance."""
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        
        # Initialize state
        initial_state = workflow_def.default_state.copy()
        if inputs:
            # Merge inputs into raw state
            if "raw" not in initial_state:
                initial_state["raw"] = {}
            initial_state["raw"].update(inputs)
        
        # Create workflow instance
        instance = WorkflowInstance(
            id=workflow_id,
            workflow_name=workflow_def.name,
            definition=workflow_def,
            status="running",
            created_at=datetime.now(UTC).isoformat(),
            inputs=inputs or {}
        )
        self.workflows[workflow_id] = instance
        
        # Initialize state manager with schema
        if not hasattr(self.state_manager, "_schema") or self.state_manager._schema != workflow_def.state_schema:
            self.state_manager._schema = workflow_def.state_schema
            self.state_manager._setup_transformations()
        
        # Set initial state by applying updates
        updates = []
        if initial_state:
            for tier_name, tier_data in initial_state.items():
                if tier_name in ["raw", "state"] and isinstance(tier_data, dict):
                    for key, value in tier_data.items():
                        updates.append({"path": f"{tier_name}.{key}", "value": value})
        
        # Always create the state, even if no initial updates
        if updates:
            self._update_state(workflow_id, updates)
        else:
            # Create empty state by doing a dummy update
            self._update_state(workflow_id, [])
        
        # Create execution context for compatibility
        context = ExecutionContext(workflow_id=workflow_id)
        # Initialize with main workflow frame
        main_frame = StackFrame(
            frame_id=str(uuid.uuid4()),
            frame_type="workflow",
            step_id="main",
            steps=workflow_def.steps
        )
        context.push_frame(main_frame)
        context_manager.contexts[workflow_id] = context
        
        # Initialize queue
        self.queues[workflow_id] = WorkflowQueue(workflow_id, workflow_def.steps)
        
        # Get the current state from state manager (includes computed fields)
        current_state = self._get_state(workflow_id)
        
        return {
            "workflow_id": workflow_id,
            "status": "running",
            "state": current_state,
            "total_steps": len(workflow_def.steps),
            "execution_context": context.get_execution_summary()
        }
    
    def get_next_step(self, workflow_id: str) -> dict[str, Any] | None:
        """Get the next batch of steps for the client to execute."""
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}
        
        lock = self._get_workflow_lock(workflow_id)
        with lock:
            queue = self.queues[workflow_id]
            instance = self.workflows[workflow_id]
            
            # Process steps until we hit a client step or run out
            while queue.has_steps():
                step = queue.peek_next()
                if not step:
                    break
                
                step_config = self.step_registry.get(step.type)
                if not step_config:
                    # Unknown step type - treat as client step
                    queue.pop_next()
                    queue.client_queue.append({
                        "id": step.id,
                        "type": step.type,
                        "definition": step.definition,
                        "error": f"Unknown step type: {step.type}"
                    })
                    break
                
                if step_config["execution"] == "server":
                    # Process server step
                    queue.pop_next()
                    result = self._process_server_step(instance, step, queue)
                    
                    if result.get("error"):
                        # Server step failed - return error to client
                        return {
                            "error": result["error"],
                            "step_id": step.id,
                            "workflow_id": workflow_id
                        }
                    
                    # Add to server completed if it produced a result
                    if result.get("executed"):
                        queue.server_completed.append(result)
                    
                elif step_config["execution"] == "client":
                    # Move to client queue
                    queue.pop_next()
                    
                    # Get current state for variable replacement
                    # IMPORTANT: Re-read state to get latest updates from server steps
                    current_state = self._get_state(workflow_id)
                    # Use nested state for template expressions (not flattened)
                    # Template expressions like "{{ raw.user_name }}" expect nested structure
                    # For control flow steps, preserve template expressions
                    preserve_templates = step.type in ["foreach", "parallel_foreach", "while_loop"]
                    processed_definition = self.step_processor._replace_variables(step.definition, current_state, False, instance, preserve_templates)
                    
                    # Special handling for parallel_foreach
                    if step.type == "parallel_foreach":
                        result = self._prepare_parallel_foreach(instance, step, processed_definition, current_state)
                        if result.get("error"):
                            return {
                                "error": result["error"],
                                "step_id": step.id,
                                "workflow_id": workflow_id
                            }
                        # Add enhanced definition with tasks
                        processed_definition = result["definition"]
                    
                    queue.client_queue.append({
                        "id": step.id,
                        "type": step.type,
                        "definition": processed_definition
                    })
                    
                    # If not batchable, stop here
                    if step_config["queuing"] != "batch":
                        break
            
            # Return client steps and server completed
            if queue.client_queue:
                response = {
                    "steps": queue.client_queue,
                    "server_completed_steps": queue.server_completed,
                    "workflow_id": workflow_id,
                    "execution_context": self._get_execution_context(workflow_id)
                }
                
                # Add backward compatibility for old API format (single step)
                if len(queue.client_queue) == 1:
                    single_step = queue.client_queue[0]
                    response["step"] = single_step
                
                queue.clear_client_queues()
                return response
            
            # Check if workflow is complete
            if not queue.has_steps() and not queue.loop_stack:
                # Don't change status if workflow is already failed
                if instance.status != "failed":
                    instance.status = "completed"
                    instance.completed_at = datetime.now(UTC).isoformat()
                context_manager.remove_context(workflow_id)
                return None
            
            # No more steps but might be in a loop
            return None
    
    def execute_step(self, workflow_id: str, step_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a step with the given result.
        
        This is an alias for step_complete with status="success".
        
        Args:
            workflow_id: ID of the workflow instance
            step_id: ID of the step to execute
            result: Result data from step execution
            
        Returns:
            Updated workflow status
        """
        return self.step_complete(workflow_id, step_id, "success", result)

    def step_complete(self, workflow_id: str, step_id: str, status: str = "success", 
                     result: Any = None, error_message: str | None = None) -> dict[str, Any]:
        """Mark a step as completed."""
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}
        
        lock = self._get_workflow_lock(workflow_id)
        with lock:
            instance = self.workflows[workflow_id]
            
            if status == "failed":
                instance.status = "failed"
                instance.error_message = error_message or "Step execution failed"
                instance.completed_at = datetime.now(UTC).isoformat()
                return {"status": "failed", "error": instance.error_message}
            
            # Update state if result contains state updates
            if result and isinstance(result, dict) and "state_updates" in result:
                self._update_state(workflow_id, result["state_updates"])
            
            return {"status": "success", "workflow_id": workflow_id}
    
    def _process_server_step(self, instance: WorkflowInstance, step: WorkflowStep, 
                           queue: WorkflowQueue) -> dict[str, Any]:
        """Process a server-side step."""
        step_config = self.step_registry.get(step.type)
        return self.step_processor.process_server_step(instance, step, queue, step_config)
    
    def _prepare_parallel_foreach(self, instance: WorkflowInstance, step: WorkflowStep,
                                 definition: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Prepare parallel_foreach step by creating sub-agent contexts and task definitions."""
        return self.subagent_manager.prepare_parallel_foreach(instance, step, definition, state)
    
    def _get_execution_context(self, workflow_id: str) -> dict[str, Any]:
        """Get execution context for a workflow."""
        context = context_manager.get_context(workflow_id)
        if context:
            return context.get_execution_summary()
        
        # Fallback context
        queue = self.queues.get(workflow_id)
        if queue:
            return {
                "workflow_id": workflow_id,
                "steps_remaining": len(queue.main_queue),
                "loop_depth": len(queue.loop_stack)
            }
        
        return {"workflow_id": workflow_id}
    
    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get the status of a workflow."""
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}
        
        lock = self._get_workflow_lock(workflow_id)
        with lock:
            instance = self.workflows[workflow_id]
            queue = self.queues.get(workflow_id)
            
            result = {
                "workflow_id": workflow_id,
                "workflow_name": instance.workflow_name,
                "status": instance.status,
                "created_at": instance.created_at,
                "completed_at": instance.completed_at,
                "error_message": instance.error_message,
                "steps_remaining": len(queue.main_queue) if queue else 0,
                "state": self._get_state(workflow_id)
            }
            
            # Add execution context if available
            context = context_manager.get_context(workflow_id)
            if context:
                result["execution_context"] = context.get_execution_summary()
            
            return result
    
    def update_workflow_state(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update the workflow state."""
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}
        
        return self._update_state(workflow_id, updates)
    
    def list_active_workflows(self) -> list[dict[str, Any]]:
        """List all active workflows."""
        with self._global_lock:
            active = []
            for workflow_id, instance in self.workflows.items():
                if instance.status == "running":
                    active.append({
                        "workflow_id": workflow_id,
                        "workflow_name": instance.workflow_name,
                        "status": instance.status,
                        "created_at": instance.created_at
                    })
            return active
    
    def get_next_sub_agent_step(self, task_id: str) -> dict[str, Any] | None:
        """Get the next step for a sub-agent task."""
        # Delegate to sub-agent manager
        # Extract workflow_id from task_id or sub_agent_contexts
        if task_id in self.subagent_manager.sub_agent_contexts:
            workflow_id = self.subagent_manager.sub_agent_contexts[task_id]["workflow_id"]
            lock = self._get_workflow_lock(workflow_id)
            return self.subagent_manager.get_next_sub_agent_step(task_id, lock)
        return {"error": f"Sub-agent task not found: {task_id}"}
    
    def execute_sub_agent_step(self, workflow_id: str, task_id: str, step_id: str, result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a sub-agent step with the given result."""
        return self.subagent_manager.execute_sub_agent_step(workflow_id, task_id, step_id, result)