"""Sub-agent management for parallel workflow execution."""

from typing import Any

from ..state.manager import StateManager
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
    
    def prepare_parallel_foreach(self, instance: WorkflowInstance, step: WorkflowStep,
                                definition: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Prepare parallel_foreach step by creating sub-agent contexts and task definitions."""
        items_expr = definition.get("items", "")
        sub_agent_task_name = definition.get("sub_agent_task", "")
        max_parallel = definition.get("max_parallel", 10)
        
        if not items_expr:
            return {"error": "Missing 'items' in parallel_foreach step"}
        if not sub_agent_task_name:
            return {"error": "Missing 'sub_agent_task' in parallel_foreach step"}
        
        # Get sub-agent task definition
        sub_agent_task = instance.definition.sub_agent_tasks.get(sub_agent_task_name)
        if not sub_agent_task:
            return {"error": f"Sub-agent task not found: {sub_agent_task_name}"}
        
        # Evaluate items expression
        try:
            if items_expr.startswith("{{") and items_expr.endswith("}}"):
                items_expr = items_expr[2:-2].strip()
            
            items = self.expression_evaluator.evaluate(items_expr, state)
            if not isinstance(items, list):
                return {"error": f"parallel_foreach items must be a list, got {type(items)}"}
        except Exception as e:
            return {"error": f"Error evaluating items: {str(e)}"}
        
        # Create task definitions for client orchestration
        tasks = []
        for i, item in enumerate(items[:max_parallel]):  # Limit to max_parallel
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
            
            # Store sub-agent context for execution
            self.sub_agent_contexts[task_id] = {
                "sub_agent_task": sub_agent_task,
                "task_context": task_context,
                "workflow_id": instance.id
            }
            
            # Create queue for sub-agent
            self.sub_agent_queues[task_id] = WorkflowQueue(task_id, sub_agent_task.steps.copy())
            
            tasks.append({
                "task_id": task_id,
                "context": task_context,
                "inputs": sub_agent_inputs
            })
        
        # Get the template prompt for sub-agents
        prompt_template = getattr(sub_agent_task, 'prompt_template', '')
        
        # Append inputs information to the prompt
        # The agent will do variable replacement to save tokens
        if prompt_template:
            # Always append the inputs JSON structure for the agent to use
            prompt_with_inputs = prompt_template + "\n\nSUB_AGENT_INPUTS:\n```json\n{\n  \"inputs\": {{ inputs }}\n}\n```"
        else:
            # Use a default prompt if none provided
            prompt_with_inputs = "Process the assigned task.\n\nSUB_AGENT_INPUTS:\n```json\n{\n  \"inputs\": {{ inputs }}\n}\n```"
        
        # Return enhanced definition
        enhanced_definition = definition.copy()
        enhanced_definition["tasks"] = tasks
        enhanced_definition["subagent_prompt"] = prompt_with_inputs
        
        return {"definition": enhanced_definition}
    
    def get_next_sub_agent_step(self, task_id: str, workflow_lock) -> dict[str, Any] | None:
        """Get the next step for a sub-agent task."""
        if task_id not in self.sub_agent_contexts:
            return {"error": f"Sub-agent task not found: {task_id}"}
        
        context = self.sub_agent_contexts[task_id]
        workflow_id = context["workflow_id"]
        
        # Use the workflow lock since sub-agents are part of the parent workflow
        with workflow_lock:
            queue = self.sub_agent_queues.get(task_id)
            if not queue:
                return {"error": f"Sub-agent queue not found: {task_id}"}
            
            sub_agent_task = context["sub_agent_task"]
            task_context = context["task_context"]
            
            # Get workflow state for variable replacement
            workflow_state = self.state_manager.read(workflow_id)
            
            # Create replacement context combining workflow state and task context
            # Use nested state for template expressions
            replacement_state = workflow_state.copy()
            replacement_state.update(task_context)
            
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
                    # Process server step for sub-agent
                    queue.pop_next()
                    # For sub-agents, we don't process server steps directly
                    # They should be converted to client steps
                    continue
                    
                elif step_config["execution"] == "client":
                    # Return client step for sub-agent
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
                        "step_index": len(sub_agent_task.steps) - len(queue.main_queue),
                        "total_steps": len(sub_agent_task.steps)
                    }
            
            # No more steps - task complete
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
        """Replace template variables in an object."""
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
                        # Handle None/undefined values
                        if result is None:
                            # For undefined variables, return empty string for state updates
                            return ""
                        return str(result)
                    except:
                        # For undefined variables, return empty string
                        return ""
                
                # Replace all {{expr}} patterns
                result = re.sub(r'\{\{([^}]+)\}\}', replace_template, obj)
                return result
            return obj
        else:
            return obj