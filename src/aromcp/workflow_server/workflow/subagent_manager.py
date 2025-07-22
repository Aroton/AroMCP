"""Sub-agent management for parallel workflow execution."""

import os
import threading
from typing import Any

from ..state.manager import StateManager
from ..utils.error_tracking import create_workflow_error, enhance_exception_message
from .expressions import ExpressionEvaluator
from .models import WorkflowInstance, WorkflowStep
from .queue import WorkflowQueue
from .step_registry import StepRegistry


class SubAgentManager:
    """Manages sub-agent execution for parallel workflow steps."""
    
    def __init__(self, state_manager: StateManager, expression_evaluator: ExpressionEvaluator, 
                 step_registry: StepRegistry):
        self.state_manager = state_manager
        self.expression_evaluator = expression_evaluator
        self.step_registry = step_registry
        
        # Sub-agent execution tracking
        self.sub_agent_contexts: dict[str, dict[str, Any]] = {}  # task_id -> context
        self.sub_agent_queues: dict[str, WorkflowQueue] = {}  # task_id -> queue
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Debug mode detection
        self._debug_serial = os.getenv("AROMCP_WORKFLOW_DEBUG", "").lower() == "serial"
    
    def prepare_parallel_foreach(self, instance: WorkflowInstance, step: WorkflowStep,
                                definition: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Prepare parallel_foreach step by creating sub-agent contexts and task definitions.
        
        In debug mode, this converts parallel_foreach to a serial foreach execution.
        """
        items_expr = definition.get("items", "")
        sub_agent_task_name = definition.get("sub_agent_task", "")
        max_parallel = definition.get("max_parallel", 10)
        
        if not items_expr:
            return create_workflow_error("Missing 'items' in parallel_foreach step", instance.id, step.id)
        if not sub_agent_task_name:
            return create_workflow_error("Missing 'sub_agent_task' in parallel_foreach step", instance.id, step.id)
        
        # Get sub-agent task definition
        sub_agent_task = instance.definition.sub_agent_tasks.get(sub_agent_task_name)
        if not sub_agent_task:
            return create_workflow_error(f"Sub-agent task not found: {sub_agent_task_name}", instance.id, step.id)
        
        # Evaluate items expression
        try:
            # Handle both string expressions and direct list values
            if isinstance(items_expr, list):
                # items is already a list - use directly
                items = items_expr
            elif isinstance(items_expr, str):
                # items is a string expression - evaluate it
                if items_expr.startswith("{{") and items_expr.endswith("}}"):
                    items_expr = items_expr[2:-2].strip()
                
                items = self.expression_evaluator.evaluate(items_expr, state)
            else:
                return create_workflow_error(f"parallel_foreach items must be a string expression or list, got {type(items_expr)}", instance.id, step.id)
            
            if not isinstance(items, list):
                return create_workflow_error(f"parallel_foreach items must be a list, got {type(items)}", instance.id, step.id)
        except Exception as e:
            return create_workflow_error(f"Error evaluating items: {enhance_exception_message(e)}", instance.id, step.id)
        
        # Create task definitions for client orchestration  
        tasks = []
        items_to_process = items if self._debug_serial else items[:max_parallel]
        
        for i, item in enumerate(items_to_process):
            task_id = f"{sub_agent_task_name}.item{i}"
            task_context = {
                "item": item,
                "index": i,
                "total": len(items),
                "task_id": task_id,
                "parent_step_id": step.id,
                "workflow_id": instance.id
            }
            
            # Create inputs for sub-agent based on the task definition
            sub_agent_inputs = {}
            if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
                for input_name, input_type in sub_agent_task.inputs.items():
                    # Map standard context variables to inputs
                    if input_name == "file_path" and "item" in task_context:
                        sub_agent_inputs[input_name] = task_context["item"]
                    elif input_name in task_context:
                        sub_agent_inputs[input_name] = task_context[input_name]
            
            # Store sub-agent context for execution (thread-safe)
            with self._lock:
                # Initialize sub-agent state from task's default_state
                sub_agent_state = self._initialize_sub_agent_state(sub_agent_task, task_context, instance.id)
                
                self.sub_agent_contexts[task_id] = {
                    "sub_agent_task": sub_agent_task,
                    "task_context": task_context,
                    "workflow_id": instance.id,
                    "sub_agent_state": sub_agent_state  # Add isolated state
                }
                
                # Create queue for sub-agent
                print(f"🐛 DEBUG: Creating queue for {task_id} with {len(sub_agent_task.steps)} steps")
                for i, step in enumerate(sub_agent_task.steps):
                    print(f"🐛 DEBUG:   Step {i}: {step.id} ({step.type})")
                self.sub_agent_queues[task_id] = WorkflowQueue(task_id, sub_agent_task.steps.copy())
            
            tasks.append({
                "task_id": task_id,
                "context": task_context,
                "inputs": sub_agent_inputs
            })
        
        # Get the template prompt for sub-agents
        prompt_template = getattr(sub_agent_task, 'prompt_template', '')
        
        if prompt_template:
            # Use custom prompt template
            prompt_with_inputs = prompt_template + "\n\nSUB_AGENT_INPUTS:\n```json\n{\n  \"inputs\": {{ inputs }}\n}\n```"
        else:
            # Use StandardPrompts.PARALLEL_FOREACH for parallel_foreach operations
            from ..prompts.standards import StandardPrompts
            
            # Create context for the standard prompt
            context = {
                'task_id': '{{ task_id }}',  # Will be replaced per task
                'item': '{{ item }}',
                'index': '{{ index }}', 
                'total': '{{ total }}'
            }
            
            base_prompt = StandardPrompts.get_prompt("parallel_foreach", context)
            
            # Format the inputs properly based on sub_agent_task definition
            inputs_json = {}
            if hasattr(sub_agent_task, 'inputs') and sub_agent_task.inputs:
                for input_name, input_def in sub_agent_task.inputs.items():
                    if hasattr(input_def, 'default') and input_def.default is not None:
                        inputs_json[input_name] = f"{{{{ {input_name} || {input_def.default} }}}}"
                    else:
                        inputs_json[input_name] = f"{{{{ {input_name} }}}}"
            
            # Convert to JSON string format
            import json
            inputs_json_str = json.dumps(inputs_json, indent=2).replace('"', '\\"')
            
            prompt_with_inputs = base_prompt + f'\n\nSUB_AGENT_INPUTS:\n```json\n{{\n  "inputs": {inputs_json_str}\n}}\n```'
        
        # Return enhanced definition
        enhanced_definition = definition.copy()
        enhanced_definition["tasks"] = tasks
        enhanced_definition["subagent_prompt"] = prompt_with_inputs
        
        # Add debug mode flag if enabled
        if self._debug_serial:
            enhanced_definition["debug_serial"] = True
            enhanced_definition["max_parallel"] = 1  # Override to force serial execution
            
            # Change instructions to clearly indicate TODO mode
            enhanced_definition["instructions"] = (
                "🚨 DEBUG MODE: Execute as TODOs in main agent. "
                "DO NOT spawn sub-agents. Use TodoWrite to track progress. "
                "Process each task serially by executing sub-agent steps directly in main agent context. "
                f"Sub-agent steps are defined in workflow sub_agent_tasks.{sub_agent_task_name}."
            )
            
            # Keep sub_agent_steps empty for client response - no internal fields exposed
            enhanced_definition["sub_agent_steps"] = []
            
            # Store debug data internally in the enhanced definition for later queue storage
            # This will be moved to queue storage by the queue executor
            enhanced_definition["_temp_debug_sub_agent_steps"] = [step.__dict__ for step in sub_agent_task.steps]
            enhanced_definition["_temp_debug_sub_agent_task_def"] = sub_agent_task
            
            print(f"🐛 DEBUG: Parallel_foreach converted to TODO mode (AROMCP_WORKFLOW_DEBUG=serial)")
            print(f"🐛 DEBUG: Created {len(tasks)} TODO items for serial execution in main agent")
        
        return {"definition": enhanced_definition}
    
    def get_next_sub_agent_step(self, task_id: str, workflow_lock) -> dict[str, Any] | None:
        """Get the next step for a sub-agent task."""
        # Thread-safe context lookup
        with self._lock:
            if task_id not in self.sub_agent_contexts:
                available_tasks = list(self.sub_agent_contexts.keys())
                error_msg = f"Sub-agent task not found: {task_id}"
                if available_tasks:
                    error_msg += f" (available tasks: {available_tasks})"
                else:
                    error_msg += " (no sub-agent contexts found)"
                return create_workflow_error(error_msg, "unknown", task_id)
            
            context = self.sub_agent_contexts[task_id].copy()  # Copy to avoid concurrent modification
            
        workflow_id = context["workflow_id"]
        
        # Use the workflow lock since sub-agents are part of the parent workflow
        with workflow_lock:
            queue = self.sub_agent_queues.get(task_id)
            if not queue:
                return create_workflow_error(f"Sub-agent queue not found: {task_id}", workflow_id, task_id)
            
            sub_agent_task = context["sub_agent_task"]
            task_context = context["task_context"]
            
            # Debug logging (always enabled for debugging)
            print(f"🐛 DEBUG: Getting next step for sub-agent task '{task_id}'")
            print(f"🐛 DEBUG: Task context: {task_context}")
            print(f"🐛 DEBUG: Queue has_steps: {queue.has_steps()}")
            print(f"🐛 DEBUG: Queue main_queue length: {len(queue.main_queue)}")
            if len(queue.main_queue) > 0:
                print(f"🐛 DEBUG: First step in queue: {queue.main_queue[0].id} ({queue.main_queue[0].type})")
            print(f"🐛 DEBUG: Sub-agent task steps: {len(sub_agent_task.steps)}")
            if len(sub_agent_task.steps) > 0:
                print(f"🐛 DEBUG: First sub-agent step: {sub_agent_task.steps[0].id} ({sub_agent_task.steps[0].type})")
            
            # Create replacement context combining sub-agent state and task context
            # Note: We'll refresh this state after each server-side step
            def get_current_replacement_state():
                with self._lock:
                    current_context = self.sub_agent_contexts.get(task_id, context)
                    current_sub_agent_state = current_context.get("sub_agent_state", {})
                    current_replacement_state = current_sub_agent_state.copy()
                    current_replacement_state.update(task_context)
                    return current_replacement_state
            
            replacement_state = get_current_replacement_state()
            
            # Debug initial state
            print(f"🐛 DEBUG: Sub-agent '{task_id}' isolated state:")
            current_sub_agent_state = replacement_state.copy()
            current_sub_agent_state.update({k: v for k, v in current_sub_agent_state.items() if k not in task_context})
            print(f"🐛 DEBUG:   Sub-agent state keys: {list(current_sub_agent_state.keys())}")
            print(f"🐛 DEBUG:   Task context: {task_context}")
            print(f"🐛 DEBUG:   Combined state keys: {list(replacement_state.keys())}")
            if 'raw' in replacement_state:
                print(f"🐛 DEBUG:   replacement_state.raw: {replacement_state['raw']}")
            if 'computed' in replacement_state:
                print(f"🐛 DEBUG:   replacement_state.computed: {replacement_state['computed']}")
            
            # Process steps similar to main workflow
            while queue.has_steps():
                step = queue.peek_next()
                if not step:
                    break
                
                step_config = self.step_registry.get(step.type)
                if not step_config:
                    # Unknown step type - treat as client step
                    queue.pop_next()
                    processed_definition = self._replace_variables(step.definition, replacement_state)
                    
                    return {
                        "step": {
                            "id": f"{task_id}.{step.id}",
                            "type": step.type,
                            "definition": processed_definition
                        },
                        "workflow_id": workflow_id,
                        "task_id": task_id,
                        "error": f"Unknown step type: {step.type}"
                    }
                
                if step_config["execution"] == "server":
                    # Handle server-side steps for sub-agent
                    if step_config["queuing"] == "expand":
                        # Handle control flow steps (while_loop, conditional, foreach)
                        queue.pop_next()
                        self._expand_control_flow_step(step, replacement_state, queue, context["workflow_id"])
                        continue
                    else:
                        # Handle immediate server steps (state_update, shell_command, etc.)
                        queue.pop_next()
                        # Process server steps in sub-agent's isolated context
                        self._process_sub_agent_server_step(step, replacement_state, context)
                        # Refresh replacement_state after server-side changes
                        replacement_state = get_current_replacement_state()
                        continue
                    
                elif step_config["execution"] == "client":
                    # Return client step for sub-agent
                    queue.pop_next()
                    processed_definition = self._replace_variables(step.definition, replacement_state)
                    
                    step_result = {
                        "step": {
                            "id": f"{task_id}.{step.id}",
                            "type": step.type,
                            "definition": processed_definition
                        },
                        "workflow_id": workflow_id,
                        "task_id": task_id,
                        "step_index": len(sub_agent_task.steps) - len(queue.main_queue),
                        "total_steps": len(sub_agent_task.steps)
                    }
                    
                    # Debug logging (always enabled for debugging)
                    print(f"🐛 DEBUG: Sub-agent '{task_id}' executing step '{step.id}' (type: {step.type})")
                    print(f"🐛 DEBUG: Step definition: {processed_definition}")
                        
                    return step_result
            
            # No more steps - task complete
            print(f"🐛 DEBUG: Sub-agent task '{task_id}' completed - no more steps")
            print(f"🐛 DEBUG: Final queue state - has_steps: {queue.has_steps()}, main_queue: {len(queue.main_queue)}")
                
            return None
    
    def execute_sub_agent_step(self, workflow_id: str, task_id: str, step_id: str, 
                              result: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a sub-agent step with the given result.
        
        This is a compatibility method for the old API.
        
        Args:
            workflow_id: ID of the workflow instance
            task_id: ID of the sub-agent task
            step_id: ID of the step to execute
            result: Result data from step execution
            
        Returns:
            Execution status
        """
        # For sub-agent steps, we don't need to do anything special
        # The get_next_sub_agent_step method already advances the step index
        return {"status": "success", "workflow_id": workflow_id, "task_id": task_id}
    
    def _replace_variables(self, obj: Any, state: dict[str, Any]) -> Any:
        """Replace template variables in an object with conditional fallback resolution."""
        if isinstance(obj, dict):
            return {k: self._replace_variables(v, state) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_variables(item, state) for item in obj]
        elif isinstance(obj, str):
            # Handle template strings with multiple variables
            if "{{" in obj and "}}" in obj:
                # Replace all template variables in the string
                import re
                def replace_template(match):
                    expr = match.group(1).strip()
                    try:
                        result = self.expression_evaluator.evaluate(expr, state)
                        # Handle None/undefined values with smart fallbacks
                        if result is None:
                            return self._get_fallback_value(expr, state)
                        return str(result)
                    except Exception as e:
                        # For evaluation errors, provide fallbacks
                        return self._get_fallback_value(expr, state)
                
                # Replace all {{expr}} patterns
                result = re.sub(r'\{\{([^}]+)\}\}', replace_template, obj)
                return result
            return obj
        else:
            return obj
    
    def _get_fallback_value(self, expr: str, state: dict[str, Any]) -> str:
        """Provide intelligent fallback values for undefined template variables."""
        # Log missing variable for debugging
        debug_mode = os.getenv("AROMCP_DEBUG_TEMPLATES", "").lower() == "true"
        if debug_mode:
            print(f"DEBUG: Template variable '{expr}' not found in state. Available keys: {list(state.keys())}")
        
        # Common fallback patterns for better error messages
        fallback_map = {
            "raw.file_path": state.get("item", "file_path"),
            "file_path": state.get("item", state.get("file_path", "unknown_file")),
            "raw.attempt_number": state.get("attempt_number", "0"),
            "raw.max_attempts": state.get("max_attempts", "10"),
            "max_attempts": state.get("max_attempts", "10"),
            "item": state.get("item", "unknown_item"),
            "task_id": state.get("task_id", "unknown_task"),
        }
        
        # Check for direct matches first
        if expr in fallback_map:
            return str(fallback_map[expr])
        
        # Check for nested property access patterns (e.g., raw.step_results.hints.success)
        if "." in expr:
            parts = expr.split(".")
            if len(parts) >= 2:
                # Try to get the value from nested state
                current = state
                try:
                    for part in parts:
                        if isinstance(current, dict):
                            current = current.get(part)
                        else:
                            break
                    if current is not None:
                        return str(current)
                except:
                    pass
                
                # Fallback based on the root key
                root_key = f"{parts[0]}.{parts[1]}" if len(parts) > 1 else parts[0]
                if root_key in fallback_map:
                    return str(fallback_map[root_key])
        
        # If it looks like a file path, try common state keys
        if "file" in expr.lower() or "path" in expr.lower():
            for key in ["item", "file_path", "target_file"]:
                if key in state and state[key]:
                    return str(state[key])
        
        # If it looks like an attempt number, provide a reasonable default
        if "attempt" in expr.lower() and "number" in expr.lower():
            return "unknown_attempt"
        
        # Return a descriptive placeholder instead of empty string
        if debug_mode:
            print(f"DEBUG: Using placeholder for '{expr}' - no fallback found")
        return f"<{expr}>"
    
    def _log_sub_agent_failure(self, task_id: str, step_id: str, error_info: dict[str, Any]) -> None:
        """Log detailed sub-agent failure information for debugging."""
        debug_mode = os.getenv("AROMCP_DEBUG_SUBAGENTS", "").lower() == "true"
        if debug_mode:
            print(f"DEBUG: Sub-agent {task_id} failed at step {step_id}")
            print(f"DEBUG: Error info: {error_info}")
            
            # Log the current sub-agent state
            if task_id in self.sub_agent_contexts:
                context = self.sub_agent_contexts[task_id]
                print(f"DEBUG: Sub-agent state: {context.get('sub_agent_state', {})}")
                print(f"DEBUG: Task context: {context.get('task_context', {})}")
    
    def _expand_control_flow_step(self, step: WorkflowStep, state: dict[str, Any], 
                                  queue: WorkflowQueue, workflow_id: str) -> None:
        """Expand control flow steps (while_loop, conditional, foreach) into their component steps."""
        try:
            if step.type == "while_loop":
                self._expand_while_loop(step, state, queue, workflow_id)
            elif step.type == "conditional":
                self._expand_conditional(step, state, queue, workflow_id)
            elif step.type == "foreach":
                self._expand_foreach(step, state, queue, workflow_id)
            else:
                print(f"🐛 DEBUG: Unknown control flow step type: {step.type}")
        except Exception as e:
            print(f"🐛 ERROR: Failed to expand control flow step {step.id}: {enhance_exception_message(e)}")
    
    def _expand_while_loop(self, step: WorkflowStep, state: dict[str, Any], 
                           queue: WorkflowQueue, workflow_id: str) -> None:
        """Expand while_loop step into its body steps."""
        condition = step.definition.get("condition", "")
        body = step.definition.get("body", [])
        max_iterations = step.definition.get("max_iterations", 100)
        
        print(f"🐛 DEBUG: Expanding while_loop '{step.id}' with condition: {condition}")
        print(f"🐛 DEBUG: While loop body has {len(body)} steps")
        
        # Get or create loop context for this step
        loop_context = None
        for ctx in queue.loop_stack:
            if ctx["context"].get("loop_id") == step.id:
                loop_context = ctx["context"]
                break
        
        if not loop_context:
            # First iteration
            loop_context = {
                "loop_id": step.id,
                "iteration": 0
            }
            queue.push_loop_context("while", loop_context)
            print(f"🐛 DEBUG: Created new while loop context for '{step.id}'")
        
        # Check iteration limit
        if loop_context["iteration"] >= max_iterations:
            queue.pop_loop_context()
            print(f"🐛 DEBUG: While loop '{step.id}' reached max iterations ({max_iterations})")
            return
        
        # Evaluate condition
        try:
            if condition.startswith("{{") and condition.endswith("}}"):
                condition_expr = condition[2:-2].strip()
            else:
                condition_expr = condition
            
            # Add loop variables to state
            eval_state = state.copy()
            eval_state["loop"] = {"iteration": loop_context["iteration"]}
            
            # Debug state contents
            print(f"🐛 DEBUG: While loop '{step.id}' condition evaluation:")
            print(f"🐛 DEBUG:   Condition: '{condition_expr}'")
            print(f"🐛 DEBUG:   Iteration: {loop_context['iteration']}")
            print(f"🐛 DEBUG:   State keys: {list(eval_state.keys())}")
            if 'raw' in eval_state:
                print(f"🐛 DEBUG:   raw: {eval_state['raw']}")
            if 'computed' in eval_state:
                print(f"🐛 DEBUG:   computed: {eval_state['computed']}")
            
            result = self.expression_evaluator.evaluate(condition_expr, eval_state)
            condition_result = bool(result)
            print(f"🐛 DEBUG:   Condition result: {condition_result}")
            print(f"🐛 DEBUG:   Raw result: {result}")
        except Exception as e:
            queue.pop_loop_context()
            print(f"🐛 ERROR: Error evaluating while condition '{condition}': {enhance_exception_message(e)}")
            return
        
        if condition_result and body:
            # Add body steps to queue
            from .models import WorkflowStep
            workflow_steps = []
            
            # Add body steps
            for i, step_def in enumerate(body):
                if "id" not in step_def:
                    step_def["id"] = f"{step.id}.body.{i}"
                workflow_step = WorkflowStep(
                    id=step_def["id"],
                    type=step_def["type"],
                    definition={k: v for k, v in step_def.items() if k not in ["id", "type"]}
                )
                workflow_steps.append(workflow_step)
                print(f"🐛 DEBUG: Added body step: {workflow_step.id} ({workflow_step.type})")
            
            # Add the while loop step again for next iteration
            workflow_steps.append(step)
            
            queue.prepend_steps(workflow_steps)
            loop_context["iteration"] += 1
            
            print(f"🐛 DEBUG: While loop '{step.id}' iteration {loop_context['iteration']} - added {len(body)} body steps")
        else:
            # Loop complete
            queue.pop_loop_context()
            print(f"🐛 DEBUG: While loop '{step.id}' completed - condition is false")
    
    def _expand_conditional(self, step: WorkflowStep, state: dict[str, Any], 
                            queue: WorkflowQueue, workflow_id: str) -> None:
        """Expand conditional step into its then/else steps."""
        condition = step.definition.get("condition", "")
        then_steps = step.definition.get("then_steps", [])
        else_steps = step.definition.get("else_steps", [])
        
        print(f"🐛 DEBUG: Expanding conditional '{step.id}' with condition: {condition}")
        
        # Evaluate condition
        try:
            if condition.startswith("{{") and condition.endswith("}}"):
                condition_expr = condition[2:-2].strip()
            else:
                condition_expr = condition
            
            result = self.expression_evaluator.evaluate(condition_expr, state)
            condition_result = bool(result)
            print(f"🐛 DEBUG: Conditional condition '{condition_expr}' evaluated to: {condition_result}")
        except Exception as e:
            print(f"🐛 ERROR: Error evaluating conditional condition '{condition}': {enhance_exception_message(e)}")
            return
        
        # Choose which steps to add
        steps_to_add = then_steps if condition_result else else_steps
        
        if steps_to_add:
            from .models import WorkflowStep
            workflow_steps = []
            
            for i, step_def in enumerate(steps_to_add):
                if "id" not in step_def:
                    branch = "then" if condition_result else "else"
                    step_def["id"] = f"{step.id}.{branch}.{i}"
                workflow_step = WorkflowStep(
                    id=step_def["id"],
                    type=step_def["type"],
                    definition={k: v for k, v in step_def.items() if k not in ["id", "type"]}
                )
                workflow_steps.append(workflow_step)
                print(f"🐛 DEBUG: Added conditional step: {workflow_step.id} ({workflow_step.type})")
            
            queue.prepend_steps(workflow_steps)
            print(f"🐛 DEBUG: Conditional '{step.id}' - added {len(workflow_steps)} steps from {'then' if condition_result else 'else'} branch")
    
    def _expand_foreach(self, step: WorkflowStep, state: dict[str, Any], 
                        queue: WorkflowQueue, workflow_id: str) -> None:
        """Expand foreach step into its body steps for each item."""
        items_expr = step.definition.get("items", "")
        body = step.definition.get("body", [])
        
        print(f"🐛 DEBUG: Expanding foreach '{step.id}' with items: {items_expr}")
        
        # Evaluate items expression
        try:
            if items_expr.startswith("{{") and items_expr.endswith("}}"):
                items_expr = items_expr[2:-2].strip()
            
            items = self.expression_evaluator.evaluate(items_expr, state)
            if not isinstance(items, list):
                print(f"🐛 ERROR: foreach items must be a list, got {type(items)}")
                return
        except Exception as e:
            print(f"🐛 ERROR: Error evaluating foreach items '{items_expr}': {enhance_exception_message(e)}")
            return
        
        # Get or create loop context
        loop_context = None
        for ctx in queue.loop_stack:
            if ctx["context"].get("loop_id") == step.id:
                loop_context = ctx["context"]
                break
        
        if not loop_context:
            # First iteration
            loop_context = {
                "loop_id": step.id,
                "items": items,
                "index": 0
            }
            queue.push_loop_context("foreach", loop_context)
            print(f"🐛 DEBUG: Created new foreach loop context for '{step.id}' with {len(items)} items")
        
        # Check if there are more items
        if loop_context["index"] < len(loop_context["items"]):
            item = loop_context["items"][loop_context["index"]]
            
            # Update state with current item
            try:
                self.state_manager.update(workflow_id, [
                    {"path": "raw.loop_item", "value": item},
                    {"path": "raw.loop_index", "value": loop_context["index"]}
                ])
            except Exception as e:
                print(f"🐛 ERROR: Failed to update state with foreach variables: {enhance_exception_message(e)}")
            
            # Add body steps
            from .models import WorkflowStep
            workflow_steps = []
            for i, step_def in enumerate(body):
                if "id" not in step_def:
                    step_def["id"] = f"{step.id}.body.{i}"
                workflow_step = WorkflowStep(
                    id=step_def["id"],
                    type=step_def["type"],
                    definition={k: v for k, v in step_def.items() if k not in ["id", "type"]}
                )
                workflow_steps.append(workflow_step)
            
            # Add foreach step again for next iteration
            workflow_steps.append(step)
            
            queue.prepend_steps(workflow_steps)
            loop_context["index"] += 1
            
            print(f"🐛 DEBUG: Foreach '{step.id}' iteration {loop_context['index']} - processing item: {item}")
        else:
            # Loop complete
            queue.pop_loop_context()
            print(f"🐛 DEBUG: Foreach '{step.id}' completed - processed {len(loop_context['items'])} items")
    
    def _initialize_sub_agent_state(self, sub_agent_task: "SubAgentTask", task_context: dict[str, Any], 
                                   workflow_id: str) -> dict[str, Any]:
        """Initialize isolated state for a sub-agent task.
        
        Each sub-agent gets its own state based on the sub_agent_task's default_state
        and state_schema, with computed fields properly evaluated.
        """
        from ..state.manager import StateManager
        
        # Start with sub-agent task's default state
        sub_agent_state = {}
        if hasattr(sub_agent_task, 'default_state') and sub_agent_task.default_state:
            import copy
            sub_agent_state = copy.deepcopy(sub_agent_task.default_state)
        
        # Ensure raw state exists
        if "raw" not in sub_agent_state:
            sub_agent_state["raw"] = {}
        
        # Add task context variables (like file_path, max_attempts)
        context_with_inputs = task_context.copy()
        if hasattr(sub_agent_task, 'inputs'):
            for input_name, input_def in sub_agent_task.inputs.items():
                if input_name == "file_path" and "item" in task_context:
                    context_with_inputs[input_name] = task_context["item"]
                elif input_name == "max_attempts" and hasattr(input_def, 'default'):
                    context_with_inputs[input_name] = input_def.default
                elif input_name not in context_with_inputs and hasattr(input_def, 'default'):
                    context_with_inputs[input_name] = input_def.default
        
        # Ensure inputs tier exists  
        if "inputs" not in sub_agent_state:
            sub_agent_state["inputs"] = {}
        
        # Add task context variables to appropriate tiers
        for key, value in context_with_inputs.items():
            if key not in ["item", "index", "total", "task_id", "parent_step_id", "workflow_id"]:
                # Put actual sub-agent inputs in the inputs tier
                if hasattr(sub_agent_task, 'inputs') and key in sub_agent_task.inputs:
                    sub_agent_state["inputs"][key] = value
                else:
                    # Other context variables go to raw
                    sub_agent_state["raw"][key] = value
        
        # Compute state fields if sub-agent has state_schema
        if hasattr(sub_agent_task, 'state_schema') and sub_agent_task.state_schema:
            # Manually compute the computed fields using expression evaluator
            computed_fields = {}
            if sub_agent_task.state_schema.computed:
                for field_name, field_def in sub_agent_task.state_schema.computed.items():
                    try:
                        # Get the transform expression
                        transform = field_def.get("transform", "")
                        if not transform:
                            computed_fields[field_name] = None
                            continue
                        
                        # Handle the 'from' field - it can be a string, a list, or contain template variables
                        from_field = field_def.get("from", "")
                        
                        if isinstance(from_field, str):
                            # Single from field - resolve template variables first
                            if from_field.startswith("{{") and from_field.endswith("}}"):
                                # This is a template variable, resolve it
                                resolved_from = self._replace_variables(from_field, context_with_inputs)
                                # The resolved value IS the input value (not a path to look up)
                                input_value = resolved_from
                            else:
                                # This is a state path like "raw.step_results"
                                input_value = self._get_nested_value(sub_agent_state, from_field)
                        elif isinstance(from_field, list):
                            # Multiple from fields - resolve each one
                            input_values = []
                            for from_item in from_field:
                                if isinstance(from_item, str) and from_item.startswith("{{") and from_item.endswith("}}"):
                                    # Template variable
                                    resolved_from = self._replace_variables(from_item, context_with_inputs)
                                    input_values.append(resolved_from)
                                else:
                                    # State path
                                    input_values.append(self._get_nested_value(sub_agent_state, from_item))
                            input_value = input_values
                        else:
                            input_value = from_field
                        
                        # Create evaluation context with 'input' variable
                        eval_context = {"input": input_value}
                        
                        # Evaluate the transform expression
                        result = self.expression_evaluator.evaluate(transform, eval_context)
                        computed_fields[field_name] = result
                        
                    except Exception as e:
                        # Some JavaScript expressions may not be compatible with our evaluator
                        # This is expected and we'll set the field to None as a fallback
                        print(f"🐛 DEBUG: Failed to compute field '{field_name}': {e}")
                        computed_fields[field_name] = None
            
            # Add computed fields to state
            if computed_fields:
                sub_agent_state["computed"] = computed_fields
        
        print(f"🐛 DEBUG: Initialized sub-agent state for {task_context.get('task_id', 'unknown')}:")
        print(f"🐛 DEBUG:   Raw state: {sub_agent_state.get('raw', {})}")
        print(f"🐛 DEBUG:   Computed fields: {sub_agent_state.get('computed', {})}")
        
        return sub_agent_state
    
    def _get_nested_value(self, obj: dict[str, Any], path: str) -> Any:
        """Get a nested value from a dictionary using dot notation (e.g., 'raw.step_results.hints')."""
        try:
            current = obj
            for part in path.split("."):
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    return None
                if current is None:
                    return None
            return current
        except Exception:
            return None
    
    def _recalculate_computed_fields(self, task_id: str, context_with_inputs: dict[str, Any]) -> None:
        """Recalculate computed fields for a sub-agent after state changes."""
        with self._lock:
            if task_id not in self.sub_agent_contexts:
                return
            
            sub_agent_context = self.sub_agent_contexts[task_id]
            sub_agent_task = sub_agent_context["sub_agent_task"]
            sub_agent_state = sub_agent_context["sub_agent_state"]
            
            if not (hasattr(sub_agent_task, 'state_schema') and sub_agent_task.state_schema):
                return
            
            # Recalculate computed fields
            computed_fields = sub_agent_state.get("computed", {})
            if sub_agent_task.state_schema.computed:
                for field_name, field_def in sub_agent_task.state_schema.computed.items():
                    try:
                        # Get the transform expression
                        transform = field_def.get("transform", "")
                        if not transform:
                            computed_fields[field_name] = None
                            continue
                        
                        # Handle the 'from' field - it can be a string, a list, or contain template variables
                        from_field = field_def.get("from", "")
                        
                        if isinstance(from_field, str):
                            # Single from field - resolve template variables first
                            if from_field.startswith("{{") and from_field.endswith("}}"):
                                # This is a template variable, resolve it
                                resolved_from = self._replace_variables(from_field, context_with_inputs)
                                if resolved_from in sub_agent_state:
                                    input_value = sub_agent_state[resolved_from]
                                else:
                                    # Try to get the value from nested state
                                    input_value = self._get_nested_value(sub_agent_state, resolved_from)
                            else:
                                # This is a state path like "raw.step_results"
                                input_value = self._get_nested_value(sub_agent_state, from_field)
                        elif isinstance(from_field, list):
                            # Multiple from fields - resolve each one
                            input_values = []
                            for from_item in from_field:
                                if isinstance(from_item, str) and from_item.startswith("{{") and from_item.endswith("}}"):
                                    # Template variable
                                    resolved_from = self._replace_variables(from_item, context_with_inputs)
                                    input_values.append(resolved_from)
                                else:
                                    # State path
                                    input_values.append(self._get_nested_value(sub_agent_state, from_item))
                            input_value = input_values
                        else:
                            input_value = from_field
                        
                        # Create evaluation context with 'input' variable
                        eval_context = {"input": input_value}
                        
                        # Evaluate the transform expression
                        result = self.expression_evaluator.evaluate(transform, eval_context)
                        computed_fields[field_name] = result
                        
                    except Exception as e:
                        # Some JavaScript expressions may not be compatible with our evaluator
                        print(f"🐛 DEBUG: Failed to recompute field '{field_name}': {e}")
                        computed_fields[field_name] = None
            
            # Update computed fields in state
            sub_agent_state["computed"] = computed_fields
            print(f"🐛 DEBUG: Recalculated computed fields for {task_id}: {computed_fields}")
    
    def _process_sub_agent_server_step(self, step: "WorkflowStep", state: dict[str, Any], context: dict[str, Any]) -> None:
        """Process server-side steps within sub-agent's isolated context.
        
        Args:
            step: The workflow step to process
            state: The sub-agent's current state (with template variables replaced)
            context: The sub-agent context containing isolated state
        """
        task_id = context.get("task_context", {}).get("task_id")
        
        try:
            # Replace template variables in step definition
            processed_definition = self._replace_variables(step.definition, state)
            
            if step.type == "state_update":
                self._handle_sub_agent_state_update(step, processed_definition, context, task_id)
            elif step.type == "shell_command":
                # For now, skip shell commands in sub-agents for security
                print(f"🐛 DEBUG: Skipping shell command in sub-agent {task_id}: {step.id}")
            else:
                print(f"🐛 DEBUG: Unsupported server step type in sub-agent {task_id}: {step.type}")
                
        except Exception as e:
            from ..utils.error_tracking import enhance_exception_message
            print(f"🐛 ERROR: Failed to process sub-agent server step {step.id}: {enhance_exception_message(e)}")
    
    def _handle_sub_agent_state_update(self, step: "WorkflowStep", processed_definition: dict[str, Any], 
                                      context: dict[str, Any], task_id: str) -> None:
        """Handle state_update steps in sub-agent's isolated context.
        
        Args:
            step: The state_update step
            processed_definition: Step definition with template variables replaced
            context: The sub-agent context
            task_id: Task ID for debugging
        """
        path = processed_definition.get("path")
        value = processed_definition.get("value")
        operation = processed_definition.get("operation", "set")
        
        if not path:
            print(f"🐛 ERROR: Missing 'path' in state_update step {step.id} for sub-agent {task_id}")
            return
            
        # Update the sub-agent's isolated state
        with self._lock:
            if task_id in self.sub_agent_contexts:
                sub_agent_state = self.sub_agent_contexts[task_id]["sub_agent_state"]
                
                # Apply the state update to isolated state
                self._apply_state_update_to_dict(sub_agent_state, path, value, operation)
                
                print(f"🐛 DEBUG: Applied state update to sub-agent {task_id}:")
                print(f"🐛 DEBUG:   Path: {path}")
                print(f"🐛 DEBUG:   Value: {value}")
                print(f"🐛 DEBUG:   Operation: {operation}")
                print(f"🐛 DEBUG:   Updated raw state: {sub_agent_state.get('raw', {})}")
                
                # Recalculate computed fields after state change
                task_context = self.sub_agent_contexts[task_id].get("task_context", {})
                context_with_inputs = task_context.copy()
                
                # Add inputs from sub-agent task definition
                sub_agent_task = self.sub_agent_contexts[task_id]["sub_agent_task"]
                if hasattr(sub_agent_task, 'inputs'):
                    for input_name, input_def in sub_agent_task.inputs.items():
                        if input_name == "file_path" and "item" in task_context:
                            context_with_inputs[input_name] = task_context["item"]
                        elif input_name == "max_attempts" and hasattr(input_def, 'default'):
                            context_with_inputs[input_name] = input_def.default
                        elif input_name not in context_with_inputs and hasattr(input_def, 'default'):
                            context_with_inputs[input_name] = input_def.default
                
                self._recalculate_computed_fields(task_id, context_with_inputs)
            else:
                print(f"🐛 ERROR: Sub-agent context not found for task_id: {task_id}")
    
    def _apply_state_update_to_dict(self, state_dict: dict[str, Any], path: str, value: Any, operation: str = "set") -> None:
        """Apply a state update directly to a dictionary.
        
        Args:
            state_dict: The state dictionary to update
            path: Dot notation path (e.g., "raw.failure_analysis")
            value: The value to set
            operation: The operation type ("set", "append", etc.)
        """
        path_parts = path.split(".")
        current = state_dict
        
        # Navigate to the parent of the target key
        for part in path_parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Apply the update
        final_key = path_parts[-1]
        if operation == "set":
            current[final_key] = value
        elif operation == "append" and isinstance(current.get(final_key), list):
            current[final_key].append(value)
        elif operation == "increment" and isinstance(current.get(final_key), (int, float)):
            current[final_key] = current.get(final_key, 0) + (value if isinstance(value, (int, float)) else 1)
        else:
            # Default to set operation
            current[final_key] = value