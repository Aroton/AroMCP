"""Step processors for different workflow step types."""

from typing import Any

from ..state.manager import StateManager
from .expressions import ExpressionEvaluator
from .models import WorkflowInstance, WorkflowStep
from .queue import WorkflowQueue
from .steps.shell_command import ShellCommandProcessor


class StepProcessor:
    """Processes different types of workflow steps."""
    
    def __init__(self, state_manager: StateManager, expression_evaluator: ExpressionEvaluator):
        self.state_manager = state_manager
        self.expression_evaluator = expression_evaluator
        self.shell_command_processor = ShellCommandProcessor()
    
    def process_server_step(self, instance: WorkflowInstance, step: WorkflowStep, 
                           queue: WorkflowQueue, step_config: dict[str, Any]) -> dict[str, Any]:
        """Process a server-side step."""
        current_state = self.state_manager.read(instance.id)
        
        # Replace variables in step definition
        # For conditional steps, preserve the condition string
        preserve_conditions = step.type == "conditional"
        # For control flow steps that evaluate expressions themselves, preserve template strings
        preserve_templates = step.type in ["foreach", "parallel_foreach", "while_loop"]
        # Use nested state for template expressions (not flattened)
        # Pass instance to have access to workflow inputs
        processed_definition = self._replace_variables(step.definition, current_state, preserve_conditions, instance, preserve_templates)
        
        if step.type == "state_update":
            return self._process_state_update(instance, step, processed_definition)
        
        elif step.type == "batch_state_update":
            return self._process_batch_state_update(instance, step, processed_definition)
        
        elif step.type == "shell_command":
            return self._process_shell_command(instance, step, processed_definition)
        
        elif step.type == "conditional":
            return self.process_conditional(instance, step, processed_definition, queue, current_state)
        
        elif step.type == "while_loop":
            return self.process_while_loop(instance, step, processed_definition, queue, current_state)
        
        elif step.type == "foreach":
            return self.process_foreach(instance, step, processed_definition, queue, current_state)
        
        elif step.type == "break":
            return self.process_break(queue)
        
        elif step.type == "continue":
            return self.process_continue(queue)
        
        return {"error": f"Unsupported server step type: {step.type}"}
    
    def _process_state_update(self, instance: WorkflowInstance, step: WorkflowStep,
                             processed_definition: dict[str, Any]) -> dict[str, Any]:
        """Process a state update step."""
        path = processed_definition.get("path")
        value = processed_definition.get("value")
        operation = processed_definition.get("operation", "set")
        
        if not path:
            return {"error": "Missing 'path' in state_update step"}
        
        updates = [{"path": path, "value": value, "operation": operation}]
        self.state_manager.update(instance.id, updates)
        
        return {
            "executed": True,
            "id": step.id,
            "type": "state_update",
            "definition": processed_definition,
            "result": {"status": "success", "updates_applied": 1}
        }
    
    def _process_batch_state_update(self, instance: WorkflowInstance, step: WorkflowStep,
                                   processed_definition: dict[str, Any]) -> dict[str, Any]:
        """Process a batch state update step."""
        updates = processed_definition.get("updates", [])
        if not updates:
            return {"error": "Missing 'updates' in batch_state_update step"}
        
        self.state_manager.update(instance.id, updates)
        
        return {
            "executed": True,
            "id": step.id,
            "type": "batch_state_update",
            "definition": processed_definition,
            "result": {"status": "success", "updates_applied": len(updates)}
        }
    
    def _process_shell_command(self, instance: WorkflowInstance, step: WorkflowStep,
                              processed_definition: dict[str, Any]) -> dict[str, Any]:
        """Process a shell command step."""
        result = self.shell_command_processor.process(
            processed_definition, instance.id, self.state_manager
        )
        
        return {
            "executed": True,
            "id": step.id,
            "type": "shell_command",
            "definition": processed_definition,
            "result": result
        }
    
    def process_conditional(self, instance: WorkflowInstance, step: WorkflowStep,
                           definition: dict[str, Any], queue: WorkflowQueue,
                           state: dict[str, Any]) -> dict[str, Any]:
        """Process a conditional step by adding branch steps to queue."""
        condition = definition.get("condition", "")
        if not condition:
            return {"error": "Missing 'condition' in conditional step"}
        
        # Evaluate condition
        try:
            # Remove template braces if present
            if condition.startswith("{{") and condition.endswith("}}"):
                condition = condition[2:-2].strip()
            
            # Use nested state for condition evaluation (not flattened)
            # This allows expressions like "computed.has_files" to work
            eval_state = self.state_manager.read(instance.id)
            
            result = self.expression_evaluator.evaluate(condition, eval_state)
            condition_result = bool(result)
        except Exception as e:
            return {"error": f"Error evaluating condition: {str(e)}"}
        
        # Get branch steps
        if condition_result:
            branch_steps = definition.get("then_steps", [])
        else:
            branch_steps = definition.get("else_steps", [])
        
        # Convert to WorkflowStep objects and add to queue
        if branch_steps:
            workflow_steps = []
            for i, step_def in enumerate(branch_steps):
                # Ensure step has an ID
                if "id" not in step_def:
                    step_def["id"] = f"{step.id}.{'then' if condition_result else 'else'}.{i}"
                
                workflow_step = WorkflowStep(
                    id=step_def["id"],
                    type=step_def["type"],
                    definition={k: v for k, v in step_def.items() if k not in ["id", "type"]}
                )
                workflow_steps.append(workflow_step)
            
            queue.prepend_steps(workflow_steps)
        
        return {
            "executed": False,  # No result to show
            "condition_result": condition_result,
            "steps_added": len(branch_steps)
        }
    
    def process_while_loop(self, instance: WorkflowInstance, step: WorkflowStep,
                          definition: dict[str, Any], queue: WorkflowQueue,
                          state: dict[str, Any]) -> dict[str, Any]:
        """Process a while loop by evaluating condition and adding body steps."""
        condition = definition.get("condition", "")
        body = definition.get("body", [])
        max_iterations = definition.get("max_iterations", 100)
        
        if not condition:
            return {"error": "Missing 'condition' in while_loop step"}
        
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
                "iteration": 0,
                "max_iterations": max_iterations
            }
            queue.push_loop_context("while", loop_context)
        
        # Check iteration limit
        if loop_context["iteration"] >= max_iterations:
            queue.pop_loop_context()
            return {"executed": False, "reason": "Max iterations reached"}
        
        # Evaluate condition
        try:
            if condition.startswith("{{") and condition.endswith("}}"):
                condition = condition[2:-2].strip()
            
            # Add loop variables to state
            eval_state = state.copy()
            eval_state["loop"] = {"iteration": loop_context["iteration"]}
            
            result = self.expression_evaluator.evaluate(condition, eval_state)
            condition_result = bool(result)
        except Exception as e:
            queue.pop_loop_context()
            return {"error": f"Error evaluating while condition: {str(e)}"}
        
        if condition_result and body:
            # Add body steps and loop step again
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
            
            # Add the while loop step again for next iteration
            workflow_steps.append(step)
            
            queue.prepend_steps(workflow_steps)
            loop_context["iteration"] += 1
            
            return {"executed": False, "iteration": loop_context["iteration"]}
        else:
            # Loop complete
            queue.pop_loop_context()
            return {"executed": False, "reason": "Condition false"}
    
    def process_foreach(self, instance: WorkflowInstance, step: WorkflowStep,
                       definition: dict[str, Any], queue: WorkflowQueue,
                       state: dict[str, Any]) -> dict[str, Any]:
        """Process a foreach loop by iterating over items."""
        items_expr = definition.get("items", "")
        body = definition.get("body", [])
        
        if not items_expr:
            return {"error": "Missing 'items' in foreach step"}
        
        # Evaluate items expression
        try:
            if items_expr.startswith("{{") and items_expr.endswith("}}"):
                items_expr = items_expr[2:-2].strip()
            
            items = self.expression_evaluator.evaluate(items_expr, state)
            if not isinstance(items, list):
                return {"error": f"foreach items must be a list, got {type(items)}"}
        except Exception as e:
            return {"error": f"Error evaluating foreach items: {str(e)}"}
        
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
        
        # Check if there are more items
        if loop_context["index"] < len(loop_context["items"]):
            # Set loop variables in state
            item = loop_context["items"][loop_context["index"]]
            self.state_manager.update(instance.id, [
                {"path": "state.loop_item", "value": item},
                {"path": "state.loop_index", "value": loop_context["index"]}
            ])
            
            # Add body steps
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
            
            # Add the foreach step again for next iteration
            workflow_steps.append(step)
            
            queue.prepend_steps(workflow_steps)
            loop_context["index"] += 1
            
            return {"executed": False, "index": loop_context["index"] - 1}
        else:
            # Loop complete - clean up loop variables
            queue.pop_loop_context()
            # Set loop variables to None (cleanup)
            self.state_manager.update(instance.id, [
                {"path": "state.loop_item", "value": None},
                {"path": "state.loop_index", "value": None}
            ])
            return {"executed": False, "reason": "All items processed"}
    
    def process_break(self, queue: WorkflowQueue) -> dict[str, Any]:
        """Process a break statement by exiting the current loop."""
        current_loop = queue.get_current_loop()
        if not current_loop:
            return {"error": "break used outside of loop"}
        
        # Remove all steps until we find the loop step
        loop_id = current_loop["context"]["loop_id"]
        steps_removed = 0
        
        while queue.main_queue:
            step = queue.main_queue[0]
            if step.id == loop_id:
                # Remove the loop step too
                queue.pop_next()
                steps_removed += 1
                break
            queue.pop_next()
            steps_removed += 1
        
        # Pop the loop context
        queue.pop_loop_context()
        
        return {"executed": False, "steps_removed": steps_removed}
    
    def process_continue(self, queue: WorkflowQueue) -> dict[str, Any]:
        """Process a continue statement by skipping to next iteration."""
        current_loop = queue.get_current_loop()
        if not current_loop:
            return {"error": "continue used outside of loop"}
        
        # Remove all steps until we find the loop step
        loop_id = current_loop["context"]["loop_id"]
        steps_removed = 0
        
        while queue.main_queue:
            step = queue.main_queue[0]
            if step.id == loop_id:
                # Keep the loop step for next iteration
                break
            queue.pop_next()
            steps_removed += 1
        
        return {"executed": False, "steps_removed": steps_removed}
    
    def _replace_variables(self, obj: Any, state: dict[str, Any], preserve_conditions: bool = False, 
                          instance: WorkflowInstance | None = None, preserve_templates: bool = False) -> Any:
        """Replace template variables in an object."""
        # Create evaluation context with workflow inputs at top level
        eval_context = state.copy()
        if instance and instance.inputs:
            # Add workflow inputs at top level for template evaluation
            eval_context.update(instance.inputs)
        
        if isinstance(obj, dict):
            # Special handling for conditional steps - preserve the condition string
            if preserve_conditions and "condition" in obj:
                result = {}
                for k, v in obj.items():
                    if k == "condition":
                        result[k] = v  # Keep condition as-is
                    else:
                        result[k] = self._replace_variables(v, state, preserve_conditions, instance, preserve_templates)
                return result
            # Special handling for control flow steps - preserve items/condition fields
            elif preserve_templates and ("items" in obj or "condition" in obj):
                result = {}
                for k, v in obj.items():
                    if k in ["items", "condition"]:
                        result[k] = v  # Keep template expression as-is
                    else:
                        result[k] = self._replace_variables(v, state, preserve_conditions, instance, preserve_templates)
                return result
            else:
                return {k: self._replace_variables(v, state, preserve_conditions, instance, preserve_templates) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_variables(item, state, preserve_conditions, instance, preserve_templates) for item in obj]
        elif isinstance(obj, str):
            # Handle template strings with multiple variables
            if "{{" in obj and "}}" in obj:
                # Check if the entire string is a single template expression
                import re
                single_expr_match = re.match(r'^\{\{([^}]+)\}\}$', obj)
                if single_expr_match:
                    # For single expressions, return the actual value (not stringified)
                    expr = single_expr_match.group(1).strip()
                    try:
                        result = self.expression_evaluator.evaluate(expr, eval_context)
                        # For single expressions, return the actual value
                        return result if result is not None else ""
                    except:
                        # For undefined variables, return empty string
                        return ""
                else:
                    # Multiple expressions or embedded in text - stringify results
                    def replace_template(match):
                        expr = match.group(1).strip()
                        try:
                            result = self.expression_evaluator.evaluate(expr, eval_context)
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