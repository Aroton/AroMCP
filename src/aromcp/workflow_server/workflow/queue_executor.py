"""Queue-based workflow executor implementation.

This executor uses a queue-based approach instead of recursive execution,
making it simpler, more debuggable, and less prone to infinite loops.
"""

import os
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from ..state.manager import StateManager
from ..utils.error_tracking import create_workflow_error, enhance_exception_message, log_exception_with_location
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
        
        # Debug mode detection
        self._debug_serial = os.getenv("AROMCP_WORKFLOW_DEBUG", "").lower() == "serial"

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
            raise ValueError(f"Failed to read state for workflow {workflow_id}: {str(e)}") from e

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
            raise ValueError(f"Failed to update state for workflow {workflow_id}: {str(e)}") from e

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
            inputs=inputs or {},
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
            frame_id=str(uuid.uuid4()), frame_type="workflow", step_id="main", steps=workflow_def.steps
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
            "execution_context": context.get_execution_summary(),
        }

    def get_next_step(self, workflow_id: str) -> dict[str, Any] | None:
        """Get the next batch of steps for the client to execute."""
        if workflow_id not in self.workflows:
            return {"error": f"Workflow {workflow_id} not found"}

        lock = self._get_workflow_lock(workflow_id)
        with lock:
            queue = self.queues[workflow_id]
            instance = self.workflows[workflow_id]

            # Implicitly complete any pending client steps from previous get_next_step call
            if queue.pending_client_steps:
                for pending_step in queue.pending_client_steps:
                    self._implicitly_complete_step(workflow_id, pending_step["id"], instance)
                queue.clear_pending_steps()

            # Process steps until we hit a client step or run out
            while queue.has_steps():
                step = queue.peek_next()
                if not step:
                    break

                step_config = self.step_registry.get(step.type)
                if not step_config:
                    # Unknown step type - treat as client step
                    queue.pop_next()
                    queue.client_queue.append(
                        {
                            "id": step.id,
                            "type": step.type,
                            "definition": step.definition,
                            "error": f"Unknown step type: {step.type}",
                        }
                    )
                    break

                if step_config["execution"] == "server":
                    # Process server step
                    queue.pop_next()
                    result = self._process_server_step(instance, step, queue)

                    if result.get("error"):
                        # Server step failed - return error to client
                        # For backward compatibility, flatten the error structure
                        error_data = result["error"]
                        if isinstance(error_data, dict) and "message" in error_data:
                            error_message = error_data["message"]
                        else:
                            error_message = str(error_data)
                        return {"error": error_message, "step_id": step.id, "workflow_id": workflow_id}

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
                    processed_definition = self.step_processor._replace_variables(
                        step.definition, current_state, False, instance, preserve_templates
                    )

                    # Special handling for parallel_foreach
                    if step.type == "parallel_foreach":
                        result = self._prepare_parallel_foreach(instance, step, processed_definition, current_state)
                        if result.get("error"):
                            # For backward compatibility, flatten the error structure
                            error_data = result["error"]
                            if isinstance(error_data, dict) and "message" in error_data:
                                error_message = error_data["message"]
                            else:
                                error_message = str(error_data)
                            return {"error": error_message, "step_id": step.id, "workflow_id": workflow_id}
                        # Add enhanced definition with tasks
                        processed_definition = result["definition"]

                        # Handle debug mode - extract internal data and store in queue, then clean definition
                        if processed_definition.get("debug_serial"):
                            # Extract temporary debug data and store in queue
                            temp_sub_agent_steps = processed_definition.pop("_temp_debug_sub_agent_steps", [])
                            temp_sub_agent_task_def = processed_definition.pop("_temp_debug_sub_agent_task_def", None)
                            
                            if temp_sub_agent_steps:
                                # Store in queue for debug expansion access
                                debug_key = f"_debug_{step.id}"
                                setattr(queue, f"{debug_key}_sub_agent_steps", temp_sub_agent_steps)
                                setattr(queue, f"{debug_key}_sub_agent_task_def", temp_sub_agent_task_def)
                            
                            # Now handle debug expansion with clean definition
                            debug_result = self._handle_debug_serial_foreach(
                                instance, step, processed_definition, queue
                            )
                            if debug_result is not None and "error" in debug_result:
                                # Debug expansion failed - return error
                                error_data = debug_result["error"]
                                if isinstance(error_data, dict) and "message" in error_data:
                                    error_message = error_data["message"]
                                else:
                                    error_message = str(error_data)
                                return {"error": error_message, "step_id": step.id, "workflow_id": workflow_id}
                            elif debug_result is None:
                                # Debug expansion was skipped (e.g., no tasks) - continue with normal processing
                                pass  # Fall through to normal parallel_foreach handling
                            elif debug_result.get("debug_expansion_completed"):
                                # Debug expansion succeeded - also skip any waiting/monitoring loops that follow
                                self._skip_parallel_waiting_loops(queue)
                                continue

                    queue.client_queue.append({"id": step.id, "type": step.type, "definition": processed_definition})

                    # If not batchable, stop here
                    # In debug mode, return steps one at a time even if batchable
                    if step_config["queuing"] != "batch" or self._debug_serial:
                        break

            # Return client steps and server completed
            if queue.client_queue:
                response = {
                    "steps": queue.client_queue,
                    "server_completed_steps": queue.server_completed,
                    "workflow_id": workflow_id,
                    "execution_context": self._get_execution_context(workflow_id),
                }

                # Move client steps to pending (for implicit completion on next call)
                queue.move_client_steps_to_pending()
                queue.server_completed = []  # Clear server completed steps
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


    def _implicitly_complete_step(self, workflow_id: str, step_id: str, instance: "WorkflowInstance") -> None:
        """Implicitly complete a client step (called when get_next_step is called again).
        
        This handles the same logic as the old step_complete method but without returning anything.
        """
        # Special handling for parallel_foreach steps in debug mode
        if self._debug_serial and workflow_id in self.queues:
            queue = self.queues[workflow_id] 
            
            # Check if this is a parallel_foreach step that needs to be re-processed for expansion
            for workflow_step in instance.definition.steps:
                if workflow_step.id == step_id and workflow_step.type == "parallel_foreach":
                    debug_step_key = f"_debug_seen_{step_id}"
                    if hasattr(queue, debug_step_key):
                        # Re-add the step to the front of the queue for expansion
                        queue.main_queue.insert(0, workflow_step)
                        break

        # Note: result and state updates would be handled here if we had access to step results
        # For now, implicit completion just advances the workflow without specific result handling

    def _process_server_step(
        self, instance: WorkflowInstance, step: WorkflowStep, queue: WorkflowQueue
    ) -> dict[str, Any]:
        """Process a server-side step."""
        step_config = self.step_registry.get(step.type)
        return self.step_processor.process_server_step(instance, step, queue, step_config)

    def _prepare_parallel_foreach(
        self, instance: WorkflowInstance, step: WorkflowStep, definition: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare parallel_foreach step by creating sub-agent contexts and task definitions."""
        return self.subagent_manager.prepare_parallel_foreach(instance, step, definition, state)

    def _handle_debug_serial_foreach(
        self, instance: WorkflowInstance, step: WorkflowStep, definition: dict[str, Any], queue: WorkflowQueue
    ) -> dict[str, Any]:
        """Handle debug serial execution of parallel_foreach by expanding sub-agent steps ONE AT A TIME."""
        tasks = definition.get("tasks", [])
        
        # Get sub-agent steps from queue storage (not from definition)
        debug_key = f"_debug_{step.id}"
        sub_agent_steps = getattr(queue, f"{debug_key}_sub_agent_steps", [])

        if not tasks:
            # No tasks to process - skip debug expansion and let normal parallel_foreach handle it
            return None

        if not sub_agent_steps:
            return create_workflow_error("Debug mode requires sub_agent_steps in definition", instance.id, step.id)

        # Check if this is the first time we're seeing this parallel_foreach step
        debug_step_key = f"_debug_seen_{step.id}"
        first_time_seeing_step = not hasattr(queue, debug_step_key)
        
        if first_time_seeing_step:
            # First time - mark as seen and return None to let the parallel_foreach step be shown with debug info
            setattr(queue, debug_step_key, True)
            return None
        
        # Track current task and step positions (subsequent calls)
        processed_task_count = getattr(queue, '_debug_processed_tasks', 0)
        current_step_index = getattr(queue, '_debug_current_step_index', 0)
        
        if processed_task_count >= len(tasks):
            # All tasks completed - continue with next workflow step
            return {"debug_expansion_completed": True}
        
        # Get current task
        current_task = tasks[processed_task_count]
        task_id = current_task["task_id"]
        task_context = current_task["context"]
        
        # Get the ordered list of actionable steps for this task
        flattened_steps = self._flatten_sub_agent_steps_for_debug(sub_agent_steps)
        
        if current_step_index >= len(flattened_steps):
            # All steps for current task completed - move to next task
            queue._debug_processed_tasks = processed_task_count + 1
            queue._debug_current_step_index = 0
            
            # Add task completion marker and re-trigger foreach for next task
            task_completion_step = WorkflowStep(
                id=f"{task_id}.completion_marker",
                type="debug_task_completion",
                definition={
                    "task_id": task_id,
                    "total_tasks": len(tasks),
                    "completed_task_index": processed_task_count
                }
            )
            queue.main_queue.insert(0, task_completion_step)
            return None
        
        # Get the NEXT step for the current task
        next_step_def = flattened_steps[current_step_index]
        
        # Create enhanced context for this specific step
        enhanced_context = task_context.copy()
        
        # Add sub-agent task inputs with defaults from queue storage
        sub_agent_task = getattr(queue, f"{debug_key}_sub_agent_task_def", None)
        if sub_agent_task and hasattr(sub_agent_task, 'inputs'):
            for input_name, input_def in sub_agent_task.inputs.items():
                if input_name == "file_path":
                    enhanced_context[input_name] = task_context.get("item", "")
                elif hasattr(input_def, 'default') and input_def.default is not None:
                    enhanced_context[input_name] = input_def.default
                elif input_name in task_context:
                    enhanced_context[input_name] = task_context[input_name]
        
        # Convert raw YAML step format to WorkflowStep definition format
        # Raw steps have properties at top level, but WorkflowStep expects them in definition
        if "definition" in next_step_def:
            # Already in WorkflowStep format
            step_definition = next_step_def["definition"]
        else:
            # Convert from raw YAML format to WorkflowStep definition format
            step_definition = {k: v for k, v in next_step_def.items() if k not in ["id", "type"]}
        
        # Merge enhanced context into step definition
        merged_definition = self._merge_context(step_definition, enhanced_context, next_step_def.get("type"))
        
        # Create the single next step
        next_step = WorkflowStep(
            id=f"{task_id}.{next_step_def['id']}", 
            type=next_step_def["type"], 
            definition=merged_definition
        )
        
        # Add step advancement marker that will trigger the next step in sequence
        step_advancement_step = WorkflowStep(
            id=f"{task_id}.step_advance_marker",
            type="debug_step_advance",
            definition={
                "task_id": task_id,
                "current_step_index": current_step_index,
                "total_steps": len(flattened_steps),
                "total_tasks": len(tasks),
                "current_task_index": processed_task_count
            }
        )
        
        # Add both steps to queue in reverse order (advancement marker first, then actual step)
        queue.main_queue.insert(0, step_advancement_step)
        queue.main_queue.insert(0, next_step)
        
        # Increment step index for next call
        queue._debug_current_step_index = current_step_index + 1
        
        # Return debug_expansion_completed to skip parallel_foreach and continue with expanded steps
        return {"debug_expansion_completed": True}

    def _flatten_sub_agent_steps_for_debug(self, sub_agent_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten nested control flow steps to get actionable steps for debug mode."""
        flattened = []
        
        def extract_actionable_steps(steps: list[dict[str, Any]], depth: int = 0) -> None:
            """Recursively extract actionable steps from nested structures."""
            indent = "  " * depth
            for step in steps:
                step_type = step.get('type', '')
                step_id = step.get('id', '')
                print(f"🐛 DEBUG: {indent}Examining: {step_id} ({step_type})")
                
                if step_type in ['mcp_call', 'user_message', 'shell_command']:
                    # This is an actionable step
                    flattened.append(step)
                    print(f"🐛 DEBUG: {indent}  ✓ Added actionable step")
                elif step_type == 'conditional':
                    # Recursively extract from conditional branches
                    # Handle both WorkflowStep objects (with definition) and raw dicts
                    if 'definition' in step:
                        # WorkflowStep object
                        definition = step['definition']
                        then_steps = definition.get('then_steps', [])
                        else_steps = definition.get('else_steps', [])
                    else:
                        # Raw dict from YAML
                        then_steps = step.get('then_steps', [])
                        else_steps = step.get('else_steps', [])
                    
                    print(f"🐛 DEBUG: {indent}  Diving into conditional: {len(then_steps)} then, {len(else_steps)} else")
                    print(f"🐛 DEBUG: {indent}    Step keys: {list(step.keys())}")
                    extract_actionable_steps(then_steps, depth + 1)
                    extract_actionable_steps(else_steps, depth + 1)
                elif step_type == 'while_loop':
                    # Recursively extract from while loop body
                    body = step.get('definition', {}).get('body', [])
                    print(f"🐛 DEBUG: {indent}  Diving into while_loop body: {len(body)} steps")
                    extract_actionable_steps(body, depth + 1)
                elif step_type == 'foreach':
                    # Recursively extract from foreach body
                    body = step.get('definition', {}).get('body', [])
                    print(f"🐛 DEBUG: {indent}  Diving into foreach body: {len(body)} steps")
                    extract_actionable_steps(body, depth + 1)
                else:
                    print(f"🐛 DEBUG: {indent}  Skipping {step_type}")
        
        print(f"🐛 DEBUG: Starting flattening process for {len(sub_agent_steps)} steps")
        extract_actionable_steps(sub_agent_steps)
        print(f"🐛 DEBUG: Flattening complete: found {len(flattened)} actionable steps")
        
        return flattened

    def _merge_context(self, definition: dict[str, Any], task_context: dict[str, Any], step_type: str = None) -> dict[str, Any]:
        """Merge task context into step definition for debug mode."""
        # Get the sub-agent's initialized state from the sub-agent manager
        task_id = task_context.get("task_id", "")
        
        if task_id and hasattr(self, 'subagent_manager'):
            # Try to get sub-agent state
            with self.subagent_manager._lock:
                sub_agent_context = self.subagent_manager.sub_agent_contexts.get(task_id, {})
                sub_agent_state = sub_agent_context.get("sub_agent_state", {})
                
                if sub_agent_state:
                    # Use sub-agent's initialized state which includes computed fields
                    context_state = sub_agent_state.copy()
                    context_state.update(task_context)  # Add task context variables
                else:
                    # Fallback to basic context structure
                    context_state = {"raw": task_context, **task_context}
        else:
            # Fallback to basic context structure
            context_state = {"raw": task_context, **task_context}

        # For control flow steps, preserve templates that reference computed state
        # that may not be available in the task context
        preserve_templates = step_type in ["while_loop", "foreach", "conditional"]
        
        # Use the step processor to replace variables in the definition
        result = self.step_processor._replace_variables(
            definition,
            context_state,
            preserve_conditions=step_type == "conditional",
            instance=None,
            preserve_templates=preserve_templates,
        )

        return result

    def _handle_store_result(self, workflow_id: str, step_id: str, result: dict[str, Any], instance) -> None:
        """Handle store_result functionality for mcp_call steps."""
        # Find the original step definition to check for store_result field
        original_step = None
        
        # Check in main workflow steps
        for step in instance.definition.steps:
            if step.id == step_id:
                original_step = step
                break
                
        # Check in sub-agent task steps
        if not original_step and "." in step_id:
            # This might be a sub-agent step like "enforce_standards_on_file.item0.get_hints"
            parts = step_id.split(".")
            if len(parts) >= 3:
                sub_task_name = parts[0]
                step_name = parts[2]  # Skip the item identifier
                
                if hasattr(instance.definition, 'sub_agent_tasks') and sub_task_name in instance.definition.sub_agent_tasks:
                    sub_task = instance.definition.sub_agent_tasks[sub_task_name]
                    if hasattr(sub_task, 'steps'):
                        for sub_step in sub_task.steps:
                            if sub_step.id == step_name:
                                original_step = sub_step
                                break
        
        # If we found the step and it has store_result, store the result
        if original_step and hasattr(original_step, 'definition') and original_step.definition.get('store_result'):
            store_path = original_step.definition['store_result']
            
            # Store the entire result at the specified path
            state_updates = [{
                "path": store_path,
                "value": result
            }]
            
            self._update_state(workflow_id, state_updates)

    def _skip_parallel_waiting_loops(self, queue: WorkflowQueue) -> None:
        """Skip while loops that wait for parallel processing completion in debug mode."""
        # In debug mode, we don't need loops that wait for parallel completion
        # Look for while loops with conditions like "!computed.all_processed"
        steps_to_skip = []

        for i, step in enumerate(queue.main_queue):
            if step.type == "while_loop":
                condition = step.definition.get("condition", "")
                # Skip loops that wait for processing completion
                # Convert condition to string in case it was evaluated as boolean
                condition_str = str(condition) if condition is not None else ""
                if any(
                    wait_pattern in condition_str
                    for wait_pattern in ["all_processed", "!computed.all_processed", "processing_results"]
                ):
                    # Debug logging removed for production
                    steps_to_skip.append(i)

        # Remove the waiting loops (in reverse order to maintain indices)
        for i in reversed(steps_to_skip):
            queue.main_queue.pop(i)

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
                "loop_depth": len(queue.loop_stack),
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
                "state": self._get_state(workflow_id),
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
                    active.append(
                        {
                            "workflow_id": workflow_id,
                            "workflow_name": instance.workflow_name,
                            "status": instance.status,
                            "created_at": instance.created_at,
                        }
                    )
            return active

    def get_next_sub_agent_step(self, workflow_id: str, task_id: str) -> dict[str, Any] | None:
        """Get the next step for a sub-agent task."""
        # Delegate to sub-agent manager with explicit workflow_id
        lock = self._get_workflow_lock(workflow_id)
        return self.subagent_manager.get_next_sub_agent_step(task_id, lock)

    def execute_sub_agent_step(
        self, workflow_id: str, task_id: str, step_id: str, result: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a sub-agent step with the given result."""
        return self.subagent_manager.execute_sub_agent_step(workflow_id, task_id, step_id, result)
