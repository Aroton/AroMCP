"""Step processors for different workflow step types."""

from typing import Any

from ..state.manager import StateManager
from ..utils.error_tracking import create_workflow_error, enhance_exception_message
from .context import ExecutionContext
from .expressions import ExpressionEvaluator
from .models import WorkflowInstance, WorkflowStep
from .parallel import ParallelForEachProcessor, ParallelForEachStep
from .queue import WorkflowQueue
from .steps.agent_prompt import AgentPromptProcessor
from .steps.agent_response import AgentResponseProcessor
from .steps.mcp_call import MCPCallProcessor
from .steps.shell_command import ShellCommandProcessor
from .steps.user_message import UserMessageProcessor
from .steps.wait_step import WaitStepProcessor


class StepProcessor:
    """Processes different types of workflow steps."""

    def __init__(self, state_manager: StateManager, expression_evaluator: ExpressionEvaluator):
        self.state_manager = state_manager
        self.expression_evaluator = expression_evaluator
        self.shell_command_processor = ShellCommandProcessor()
        self.agent_prompt_processor = AgentPromptProcessor()
        self.agent_response_processor = AgentResponseProcessor()
        self.parallel_foreach_processor = ParallelForEachProcessor(expression_evaluator)

    # Note: user_input, user_message, and mcp_call processors use static methods

    def process_server_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        queue: WorkflowQueue,
        step_config: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process a server-side step."""
        # print(f"DEBUG: Processing step {step.id} of type {step.type}")
        current_state = self.state_manager.read(instance.id)

        # Replace variables in step definition
        # For conditional steps, preserve the condition string
        preserve_conditions = step.type == "conditional"
        # For control flow steps that evaluate expressions themselves, preserve template strings
        preserve_templates = step.type in ["foreach", "parallel_foreach", "while_loop"]

        # Use nested state for template expressions (not flattened)
        # Pass instance and context for scoped variable resolution
        processed_definition = self._replace_variables(
            step.definition, current_state, preserve_conditions, instance, preserve_templates, context
        )

        if step.type == "shell_command":
            result = self._process_shell_command(instance, step, processed_definition)
            # Process embedded state updates if present
            self._process_embedded_state_updates(instance, step, processed_definition, result, context)
            return result

        elif step.type == "agent_prompt":
            # Create flattened state for agent prompt processor
            flattened_state = self._flatten_state(current_state)
            return self.agent_prompt_processor.process_agent_prompt(step, flattened_state)

        elif step.type == "agent_response":
            # Agent response steps should be processed on client side
            # Return placeholder indicating this step requires agent response
            return {"executed": False, "requires_agent_response": True}

        elif step.type == "conditional":
            return self.process_conditional(instance, step, processed_definition, queue, current_state, context)

        elif step.type == "while_loop":
            return self.process_while_loop(instance, step, processed_definition, queue, current_state, context)

        elif step.type == "while_loop_continuation":
            return self.process_while_loop_continuation(instance, step, processed_definition, queue, context)

        elif step.type == "foreach":
            return self.process_foreach(instance, step, processed_definition, queue, current_state, context)

        elif step.type == "debug_task_completion":
            return self.process_debug_task_completion(instance, step, processed_definition, queue)

        elif step.type == "debug_step_advance":
            return self.process_debug_step_advance(instance, step, processed_definition, queue)

        elif step.type == "break":
            return self.process_break(queue, context)

        elif step.type == "continue":
            return self.process_continue(queue, context)

        elif step.type == "mcp_call":
            # Handle workflow_state_update MCP calls server-side
            return self._process_mcp_call(instance, step, processed_definition)

        return create_workflow_error(f"Unsupported server step type: {step.type}", instance.id, step.id)

    def process_client_step(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        step_config: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process a client-side step by formatting it appropriately."""
        current_state = self.state_manager.read(instance.id)

        # Replace variables in step definition using the same logic as server steps
        processed_definition = self._replace_variables(step.definition, current_state, False, instance, False, context)

        if step.type == "user_message":
            return self._process_user_message(instance, step, processed_definition)

        elif step.type == "user_input":
            return self._process_user_input(instance, step, processed_definition)

        elif step.type == "mcp_call":
            return self._process_mcp_call(instance, step, processed_definition)

        elif step.type == "agent_prompt":
            # Create flattened state for agent prompt processor
            flattened_state = self._flatten_state(current_state)
            return self.agent_prompt_processor.process_agent_prompt(step, flattened_state)

        elif step.type == "parallel_foreach":
            return self._process_parallel_foreach(instance, step, processed_definition)

        elif step.type == "wait_step":
            return WaitStepProcessor.process(processed_definition, instance.id, self.state_manager)

        # Default: return basic client step format
        return {"id": step.id, "type": step.type, "definition": processed_definition, "execution_context": "client"}

    def process_agent_response_result(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        agent_response: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process an agent response step result from the client."""
        current_state = self.state_manager.read(instance.id)
        flattened_state = self._flatten_state(current_state)

        # Process the agent response
        result = self.agent_response_processor.process_agent_response(step, agent_response, flattened_state)

        # Apply state updates if successful
        if result.get("executed") and "state_updates" in result:
            state_updates = result["state_updates"]
            if state_updates:
                self.state_manager.update(instance.id, state_updates, context)

        return result

    def _process_embedded_state_updates(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        processed_definition: dict[str, Any],
        step_result: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> None:
        """Process embedded state updates for a step."""
        updates_to_apply = []

        # Check for single state_update
        state_update = processed_definition.get("state_update")
        if state_update:
            updates_to_apply.append(state_update)

        # Check for multiple state_updates
        state_updates = processed_definition.get("state_updates", [])
        if state_updates:
            updates_to_apply.extend(state_updates)

        # Apply all updates
        if updates_to_apply:
            # Validate each update has required fields
            validated_updates = []
            for update in updates_to_apply:
                if not isinstance(update, dict):
                    continue

                path = update.get("path")
                if not path:
                    continue

                # Get value from update spec
                value = update.get("value")
                operation = update.get("operation", "set")

                # Handle backward compatibility: map "raw" paths to "inputs" paths
                if path.startswith("raw."):
                    path = path.replace("raw.", "inputs.", 1)

                # Re-evaluate template expressions with current state (including loop variables)
                # This is critical for foreach loops where loop_item/loop_index change
                current_state = self.state_manager.read(instance.id)
                eval_context = current_state.copy()
                if instance and instance.inputs:
                    # Add workflow inputs at top level for template evaluation
                    eval_context.update(instance.inputs)

                # If path contains template expressions, evaluate them first
                # This handles dynamic paths like "state.results['large_batch_' + {{ batch_index }}]"
                original_path = path
                if isinstance(path, str) and "{{" in path and "}}" in path:
                    path = self._replace_variables(path, current_state, False, instance, False, context)
                    # Convert bracket notation to dot notation for state manager compatibility
                    path = self._convert_bracket_notation_to_dot_notation(path)

                # ALSO handle JavaScript expressions in paths (like state.items[loop.idx].quantity)
                # This is needed for loop variables in paths
                elif isinstance(path, str) and "loop." in path and "[" in path and "]" in path:
                    try:
                        # Extract the bracket expression and evaluate it
                        import re

                        # Find all [expression] patterns
                        bracket_matches = re.findall(r"\[([^\]]+)\]", path)
                        for bracket_expr in bracket_matches:
                            if "loop." in bracket_expr:
                                # Evaluate the expression to get the actual index
                                evaluated_index = self._evaluate_javascript_expression(
                                    bracket_expr, current_state, context, instance.id
                                )
                                # Replace in the path
                                path = path.replace(f"[{bracket_expr}]", f"[{evaluated_index}]")
                        # Convert bracket notation to dot notation
                        path = self._convert_bracket_notation_to_dot_notation(path)
                    except Exception as e:
                        # If evaluation fails, keep original path
                        print(f"DEBUG: Path JavaScript evaluation failed: {e}")
                        pass

                # If value is a template expression, re-evaluate it with current state
                original_value = value
                if isinstance(value, str) and "{{" in value and "}}" in value:
                    value = self._replace_variables(value, current_state, False, instance, False, context)
                # If value is a JavaScript expression (not template), evaluate it
                elif isinstance(value, str) and (
                    # Arithmetic operations
                    any(op in value for op in ["+", "-", "*", "/"])
                    or
                    # Comparison operations
                    any(op in value for op in ["===", "!==", ">", "<", ">=", "<=", "&&", "||"])
                    or
                    # Property access
                    any(ref in value for ref in ["state.", "inputs.", "computed.", "loop."])
                    or
                    # Array/object operations
                    value.startswith("[")
                    or value.startswith("{")
                    or
                    # Template literals
                    "`" in value
                    or
                    # Special cases
                    "..." in value
                    or
                    # Numeric strings (treat as numbers in JavaScript context)
                    (
                        value.isdigit()
                        or (value.startswith("-") and value[1:].isdigit())
                        or ("." in value and value.replace(".", "").replace("-", "").isdigit())
                    )
                ):
                    try:
                        # Use PythonMonkey for full JavaScript expression evaluation
                        value = self._evaluate_javascript_expression(value, current_state, context, instance.id)
                    except Exception as e:
                        # If expression evaluation fails, keep the original value
                        # Log the error for debugging
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.warning(f"JavaScript expression evaluation failed: {e}")
                        pass

                # For shell commands, allow value to reference output fields
                if step.type == "shell_command" and isinstance(value, str):
                    # Check if shell result has the output directly or nested under 'result'
                    shell_output = None
                    if "output" in step_result:
                        shell_output = step_result["output"]
                    elif "result" in step_result and "output" in step_result["result"]:
                        shell_output = step_result["result"]["output"]

                    if shell_output:
                        if value == "stdout":
                            value = shell_output.get("stdout", "")
                        elif value == "stderr":
                            value = shell_output.get("stderr", "")
                        elif value == "returncode":
                            value = shell_output.get("exit_code", 0)
                        elif value == "full_output":
                            value = shell_output

                validated_updates.append({"path": path, "value": value, "operation": operation})

            if validated_updates:
                self.state_manager.update(instance.id, validated_updates, context)
                # Add update info to step result
                if "result" not in step_result:
                    step_result["result"] = {}
                step_result["result"]["shell_command with state_updates_applied"] = len(validated_updates)

    def _convert_bracket_notation_to_dot_notation(self, path: str) -> str:
        """
        Convert bracket notation to dot notation for state manager compatibility.
        Example: "state.results['large_batch_0']" -> "state.results.large_batch_0"
        Example: "state.items[0].quantity" -> "state.items.0.quantity"
        """
        import re

        # Pattern to match quoted bracket notation like ['key'] or ["key"]
        quoted_pattern = r"\[(['\"])([^'\"]+)\1\]"

        # Pattern to match numeric bracket notation like [0] or [123]
        numeric_pattern = r"\[(\d+)\]"

        def replace_quoted_brackets(match):
            # Extract the key without quotes
            key = match.group(2)
            return f".{key}"

        def replace_numeric_brackets(match):
            # Extract the numeric index
            index = match.group(1)
            return f".{index}"

        # Replace all bracket notation with dot notation
        converted_path = re.sub(quoted_pattern, replace_quoted_brackets, path)
        converted_path = re.sub(numeric_pattern, replace_numeric_brackets, converted_path)
        return converted_path

    def _process_shell_command(
        self, instance: WorkflowInstance, step: WorkflowStep, processed_definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a shell command step."""
        result = self.shell_command_processor.process(processed_definition, instance.id, self.state_manager)

        return {
            "executed": True,
            "id": step.id,
            "type": "shell_command",
            "definition": processed_definition,
            "result": result,
        }

    def process_conditional(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        definition: dict[str, Any],
        queue: WorkflowQueue,
        state: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process a conditional step by adding branch steps to queue."""
        condition = definition.get("condition", "")
        if not condition:
            return create_workflow_error("Missing 'condition' in conditional step", instance.id, step.id)

        # Evaluate condition
        try:
            # Remove template braces if present
            if condition.startswith("{{") and condition.endswith("}}"):
                condition = condition[2:-2].strip()

            # Use nested state for condition evaluation (not flattened)
            # This allows expressions like "computed.has_files" to work
            eval_state = self.state_manager.read(instance.id)

            # Set up scoped context for 'this.' expressions
            scoped_context = {
                "this": eval_state.get("computed", {}),
                "inputs": eval_state.get("inputs", {}),
                "state": eval_state.get("state", {}),
                "global": eval_state.get("global", {}),
                "loop": self._get_current_loop_variables(context),
            }

            result = self.expression_evaluator.evaluate(condition, eval_state, scoped_context)
            condition_result = bool(result)

        except Exception as e:
            return create_workflow_error(
                f"Error evaluating condition: {enhance_exception_message(e)}", instance.id, step.id
            )

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

                # Extract execution_context if present
                execution_context = step_def.get("execution_context", "server")
                definition = {k: v for k, v in step_def.items() if k not in ["id", "type", "execution_context"]}

                workflow_step = WorkflowStep(
                    id=step_def["id"], type=step_def["type"], definition=definition, execution_context=execution_context
                )
                workflow_steps.append(workflow_step)

            queue.prepend_steps(workflow_steps)

        return {
            "executed": False,  # No result to show
            "condition_result": condition_result,
            "steps_added": len(branch_steps),
        }

    def process_while_loop(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        definition: dict[str, Any],
        queue: WorkflowQueue,
        state: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process a while loop by evaluating condition and adding body steps using scoped loop variables."""
        condition = definition.get("condition", "")
        body = definition.get("body", [])
        max_iterations = definition.get("max_iterations", 100)

        if not condition:
            return create_workflow_error("Missing 'condition' in while_loop step", instance.id, step.id)

        # Use execution context for proper loop management if available
        if context:
            # Check if there's already a current loop with this step ID
            current_loop = context.current_loop()

            if current_loop and current_loop.loop_id == step.id:
                # Continuing existing loop - advance to next iteration
                current_loop.advance_iteration()

                # Check if loop reached max iterations
                if current_loop.current_iteration >= max_iterations:
                    # Exit the loop
                    context.exit_loop()
                    return {"executed": False, "reason": "Max iterations reached"}
            else:
                # Create new while loop
                from .control_flow import LoopState

                loop_state = LoopState(loop_type="while", loop_id=step.id, max_iterations=max_iterations)
                # Prepare initial loop variables
                loop_state.prepare_for_iteration()
                context.enter_loop(loop_state)
        else:
            # Fallback to queue-based loop management
            loop_context = None
            for ctx in queue.loop_stack:
                if ctx["context"].get("loop_id") == step.id:
                    loop_context = ctx["context"]
                    break

            if not loop_context:
                # First iteration
                loop_context = {"loop_id": step.id, "iteration": 0, "max_iterations": max_iterations}
                queue.push_loop_context("while", loop_context)

        # Evaluate condition
        try:
            if condition.startswith("{{") and condition.endswith("}}"):
                condition = condition[2:-2].strip()

            # Use updated state for condition evaluation with scoped context
            eval_state = self.state_manager.read(instance.id)
            scoped_context = self._build_scoped_context(instance, eval_state, context)

            # Debug: show state during condition evaluation
            # category_index = eval_state.get('state', {}).get('category_index', 'unknown')
            # has_more_categories = eval_state.get('computed', {}).get('has_more_categories', 'unknown')
            # print(f"DEBUG: Condition evaluation - category_index={category_index}, has_more_categories={has_more_categories}")

            result = self.expression_evaluator.evaluate(condition, eval_state, scoped_context)
            condition_result = bool(result)
        except Exception as e:
            # Clean up on error
            if context:
                context.exit_loop()
            else:
                queue.pop_loop_context()
                # Modern scoped loop variables are automatically cleaned up
            return create_workflow_error(
                f"Error evaluating while condition: {enhance_exception_message(e)}", instance.id, step.id
            )

        # Get current loop state
        current_loop = context.current_loop() if context else None

        # Check for break/continue signals first
        if current_loop and current_loop.control_signal:
            from .context import LoopControl

            if current_loop.control_signal == LoopControl.BREAK:
                context.exit_loop()
                return {"executed": False, "reason": "Break signal"}
            elif current_loop.control_signal == LoopControl.CONTINUE:
                # Clear the continue signal and continue to next iteration
                current_loop.control_signal = None

        # print(f"DEBUG: While loop {step.id}: condition_result={condition_result}, body_length={len(body) if body else 0}")
        # if current_loop:
        #     print(f"DEBUG: While loop {step.id}: current_iteration={current_loop.current_iteration}, max_iterations={max_iterations}")
        if condition_result and body:
            # Check if we've reached max iterations before adding body steps
            if current_loop:
                # Modern context path - check if already at max iterations
                if current_loop.current_iteration >= max_iterations:
                    context.exit_loop()
                    return {"executed": False, "reason": "Max iterations reached"}
            else:
                # Legacy queue-based path - check max iterations
                loop_context = None
                for ctx in queue.loop_stack:
                    if ctx["context"].get("loop_id") == step.id:
                        loop_context = ctx["context"]
                        break

                if loop_context:
                    # Check if we've reached max iterations before adding more steps
                    if loop_context["iteration"] >= loop_context["max_iterations"]:
                        queue.pop_loop_context()
                        return {"executed": False, "reason": "Max iterations reached"}

            # Continue loop - add body steps and loop step again
            workflow_steps = []

            # Add body steps
            for i, step_def in enumerate(body):
                if "id" not in step_def:
                    step_def["id"] = f"{step.id}.body.{i}"
                # Extract execution_context if present
                execution_context = step_def.get("execution_context", "server")
                definition_copy = {k: v for k, v in step_def.items() if k not in ["id", "type", "execution_context"]}

                workflow_step = WorkflowStep(
                    id=step_def["id"],
                    type=step_def["type"],
                    definition=definition_copy,
                    execution_context=execution_context,
                )
                workflow_steps.append(workflow_step)

            # Add a continuation step that will check for break signals before re-queuing the loop
            continuation_step = WorkflowStep(
                id=f"{step.id}.continuation",
                type="while_loop_continuation",
                definition={
                    "original_loop_step_id": step.id,
                    "original_loop_step_type": step.type,
                    "original_loop_definition": step.definition,
                },
                execution_context="server",
            )
            workflow_steps.append(continuation_step)

            queue.prepend_steps(workflow_steps)

            if current_loop:
                return {"executed": False, "iteration": current_loop.current_iteration}
            else:
                # Fallback to queue-based management - increment after adding steps
                if loop_context:
                    loop_context["iteration"] += 1
                    return {"executed": False, "iteration": loop_context["iteration"]}

                return {"executed": False, "iteration": 1}
        else:
            # Loop complete - condition is false or no body
            if context:
                context.exit_loop()
            else:
                # Fallback cleanup
                queue.pop_loop_context()
                # Modern scoped loop variables are automatically cleaned up

            return {"executed": False, "reason": "Condition false"}

    def process_while_loop_continuation(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        definition: dict[str, Any],
        queue: WorkflowQueue,
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process a while loop continuation step by checking for break signals and re-queuing the loop."""
        if not context:
            return create_workflow_error("while_loop_continuation requires execution context", instance.id, step.id)

        # Get current loop state
        current_loop = context.current_loop()
        if not current_loop:
            return create_workflow_error("while_loop_continuation used outside of loop", instance.id, step.id)

        original_step_id = definition.get("original_loop_step_id", "unknown")
        # print(f"DEBUG: Processing continuation for loop {original_step_id}, current_loop.loop_id={current_loop.loop_id}, control_signal={current_loop.control_signal}")

        # Check for break/continue signals
        from .context import LoopControl

        if current_loop.control_signal == LoopControl.BREAK:
            # Break signal received - exit the loop
            context.exit_loop()
            return {"executed": False, "reason": "Break signal"}
        elif current_loop.control_signal == LoopControl.CONTINUE:
            # Continue signal received - clear it and re-queue the loop
            current_loop.control_signal = None

        # No break signal - re-queue the original while loop step
        # Note: iteration will be incremented by advance_iteration() in process_while_loop

        # Recreate the original loop step from the definition
        original_step_id = definition.get("original_loop_step_id")
        original_step_type = definition.get("original_loop_step_type")
        original_definition = definition.get("original_loop_definition")

        if original_step_id and original_step_type and original_definition:
            original_step = WorkflowStep(
                id=original_step_id, type=original_step_type, definition=original_definition, execution_context="server"
            )
            queue.prepend_steps([original_step])
            return {"executed": False, "reason": "Loop continuation"}
        else:
            return create_workflow_error("Missing original loop step information in continuation", instance.id, step.id)

    def process_foreach(
        self,
        instance: WorkflowInstance,
        step: WorkflowStep,
        definition: dict[str, Any],
        queue: WorkflowQueue,
        state: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> dict[str, Any]:
        """Process a foreach loop by iterating over items using scoped loop variables."""
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

        # Use execution context for proper loop management if available
        if context:
            # Check if there's already a current loop with this step ID
            current_loop = context.current_loop()

            if current_loop and current_loop.loop_id == step.id:
                # Check for break/continue signals FIRST (before advancing iteration)
                if current_loop.control_signal:
                    from .context import LoopControl

                    if current_loop.control_signal == LoopControl.BREAK:
                        context.exit_loop()
                        return {"executed": False, "reason": "Break signal"}
                    elif current_loop.control_signal == LoopControl.CONTINUE:
                        # Clear the continue signal and advance to next iteration
                        current_loop.control_signal = None

                # Continuing existing loop - advance to next iteration
                current_loop.advance_iteration()

                # Check if loop is complete
                if current_loop.is_complete():
                    # Exit the loop
                    context.exit_loop()
                    return {"executed": False, "reason": "All items processed"}
            else:
                # Create new foreach loop
                from .control_flow import LoopState

                variable_name = definition.get("variable_name", "item")
                index_name = definition.get("index_name", "index")

                loop_state = LoopState(
                    loop_type="foreach",
                    loop_id=step.id,
                    items=items,
                    max_iterations=len(items),
                    variable_name=variable_name,
                    index_name=index_name,
                )
                # Prepare initial loop variables
                loop_state.prepare_for_iteration()
                context.enter_loop(loop_state)
        else:
            # Fallback to queue-based loop management
            # Use a stable loop ID that won't change across iterations
            stable_loop_id = getattr(step, "_original_id", step.id)

            loop_context = None
            for ctx in queue.loop_stack:
                if ctx["context"].get("loop_id") == stable_loop_id:
                    loop_context = ctx["context"]
                    break

            if not loop_context:
                # First iteration - create new loop context
                loop_context = {"loop_id": stable_loop_id, "items": items, "index": 0}
                queue.push_loop_context("foreach", loop_context)

                # Store the original step ID for consistency across iterations
                if not hasattr(step, "_original_id"):
                    step._original_id = step.id

        # Get current loop state
        current_loop = context.current_loop() if context else None

        if current_loop and not current_loop.is_complete():
            # Add body steps for current iteration
            workflow_steps = []
            for i, step_def in enumerate(body):
                if "id" not in step_def:
                    step_def["id"] = f"{step.id}.body.{i}"
                # Extract execution_context if present
                execution_context = step_def.get("execution_context", "server")
                definition_copy = {k: v for k, v in step_def.items() if k not in ["id", "type", "execution_context"]}

                workflow_step = WorkflowStep(
                    id=step_def["id"],
                    type=step_def["type"],
                    definition=definition_copy,
                    execution_context=execution_context,
                )
                # Store the original step ID and loop information for break/continue logic
                workflow_step._loop_id = step.id
                workflow_step._loop_body_index = i
                workflow_steps.append(workflow_step)

            # Add the foreach step again for next iteration
            workflow_steps.append(step)

            queue.prepend_steps(workflow_steps)

            return {"executed": False, "index": current_loop.current_item_index}
        else:
            # Handle queue-based processing (legacy or when no execution context)
            # Use a stable loop ID that won't change across iterations
            stable_loop_id = getattr(step, "_original_id", step.id)

            loop_context = None
            for ctx in queue.loop_stack:
                if ctx["context"].get("loop_id") == stable_loop_id:
                    loop_context = ctx["context"]
                    break

            if loop_context and loop_context["index"] < len(loop_context["items"]):
                # Set legacy loop variables in state for backward compatibility
                # TODO: Remove this legacy behavior in future version
                import warnings

                warnings.warn(
                    "Legacy loop variable management (state.loop_item, state.loop_index) is deprecated. "
                    "Use scoped loop variables ({{loop.item}}, {{loop.index}}) instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                item = loop_context["items"][loop_context["index"]]

                # Set legacy loop variables for backward compatibility
                state_updates = [
                    {"path": "state.loop_item", "value": item},
                    {"path": "state.loop_index", "value": loop_context["index"]},
                ]

                # Also set custom variable names if specified
                variable_name = definition.get("variable_name", "item")
                index_name = definition.get("index_name", "index")
                if variable_name:
                    state_updates.append({"path": f"state.{variable_name}", "value": item})
                if index_name:
                    state_updates.append({"path": f"state.{index_name}", "value": loop_context["index"]})

                self.state_manager.update(instance.id, state_updates, context)

                # Add body steps
                workflow_steps = []
                for i, step_def in enumerate(body):
                    if "id" not in step_def:
                        step_def["id"] = f"{step.id}.body.{i}"
                    # Extract execution_context if present
                    execution_context = step_def.get("execution_context", "server")
                    definition_copy = {
                        k: v for k, v in step_def.items() if k not in ["id", "type", "execution_context"]
                    }

                    # Pre-evaluate templates in state updates to capture current loop variable values
                    if "state_update" in definition_copy:
                        current_state = self.state_manager.read(instance.id)
                        definition_copy["state_update"] = self._replace_variables(
                            definition_copy["state_update"], current_state, False, instance, False, context
                        )
                    if "state_updates" in definition_copy:
                        current_state = self.state_manager.read(instance.id)
                        definition_copy["state_updates"] = self._replace_variables(
                            definition_copy["state_updates"], current_state, False, instance, False, context
                        )

                    workflow_step = WorkflowStep(
                        id=step_def["id"],
                        type=step_def["type"],
                        definition=definition_copy,
                        execution_context=execution_context,
                    )
                    # Store the original step ID and loop information for break/continue logic
                    workflow_step._loop_id = step.id
                    workflow_step._loop_body_index = i
                    workflow_steps.append(workflow_step)

                # Add the foreach step again for next iteration
                workflow_steps.append(step)

                queue.prepend_steps(workflow_steps)
                loop_context["index"] += 1

                return {"executed": False, "index": loop_context["index"] - 1}
            elif loop_context:
                # Loop complete - clean up loop variables
                queue.pop_loop_context()
                # Clean up legacy loop variables
                # TODO: Remove this legacy cleanup in future version
                self.state_manager.update(
                    instance.id,
                    [{"path": "state.loop_item", "value": None}, {"path": "state.loop_index", "value": None}],
                    context,
                )
                return {"executed": False, "reason": "All items processed"}

        return {"executed": False, "reason": "Loop completed"}

    def process_break(self, queue: WorkflowQueue, context: ExecutionContext | None = None) -> dict[str, Any]:
        """Process a break statement by exiting the current loop."""
        # Try modern context system first
        if context:
            current_loop = context.current_loop()
            if not current_loop:
                return create_workflow_error("break used outside of loop", "", "")

            from .context import LoopControl

            context.signal_loop_control(LoopControl.BREAK)

            # Remove remaining steps from queue that belong to the current loop only
            # This ensures break only affects the innermost loop, not outer loops
            loop_id = current_loop.loop_id
            steps_removed = 0

            # Remove steps that belong to the current loop, using both ID prefix and loop metadata
            steps_to_remove = []
            for step in queue.main_queue:
                if step.id == loop_id:
                    # Found the loop step itself - include it and stop
                    steps_to_remove.append(step)
                    break
                elif step.id.startswith(f"{loop_id}."):
                    # This step belongs to the current loop body (auto-generated ID)
                    steps_to_remove.append(step)
                elif hasattr(step, "_loop_id") and step._loop_id == loop_id:
                    # This step belongs to the current loop body (custom ID with metadata)
                    steps_to_remove.append(step)
                else:
                    # This step doesn't belong to the current loop - stop removing
                    break

            # Remove the identified steps
            for step_to_remove in steps_to_remove:
                if queue.main_queue and queue.main_queue[0].id == step_to_remove.id:
                    queue.pop_next()
                    steps_removed += 1
                else:
                    # Step not at front of queue - this shouldn't happen in normal execution
                    break

            return {"executed": False, "signal": "break", "steps_removed": steps_removed}

        # Fall back to legacy queue-based system
        current_loop = queue.get_current_loop()
        if not current_loop:
            return create_workflow_error("break used outside of loop", "", "")

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

    def process_continue(self, queue: WorkflowQueue, context: ExecutionContext | None = None) -> dict[str, Any]:
        """Process a continue statement by skipping to next iteration."""
        # Try modern context system first
        if context:
            current_loop = context.current_loop()
            if not current_loop:
                return create_workflow_error("continue used outside of loop", "", "")

            from .context import LoopControl

            context.signal_loop_control(LoopControl.CONTINUE)

            # Remove remaining body steps from queue that belong to the current loop only
            # This ensures continue only affects the innermost loop, not outer loops
            loop_id = current_loop.loop_id
            steps_removed = 0

            # Remove steps that belong to the current loop, using both ID prefix and loop metadata
            steps_to_remove = []
            for step in queue.main_queue:
                if step.id == loop_id:
                    # Found the loop step itself - keep it for next iteration
                    break
                elif step.id.startswith(f"{loop_id}."):
                    # This step belongs to the current loop body (auto-generated ID)
                    steps_to_remove.append(step)
                elif hasattr(step, "_loop_id") and step._loop_id == loop_id:
                    # This step belongs to the current loop body (custom ID with metadata)
                    steps_to_remove.append(step)
                else:
                    # This step doesn't belong to the current loop - stop removing
                    break

            # Remove the identified steps
            for step_to_remove in steps_to_remove:
                if queue.main_queue and queue.main_queue[0].id == step_to_remove.id:
                    queue.pop_next()
                    steps_removed += 1
                else:
                    # Step not at front of queue - this shouldn't happen in normal execution
                    break

            return {"executed": False, "signal": "continue", "steps_removed": steps_removed}

        # Fall back to legacy queue-based system
        current_loop = queue.get_current_loop()
        if not current_loop:
            return create_workflow_error("continue used outside of loop", "", "")

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

    def process_debug_task_completion(
        self, instance: WorkflowInstance, step: WorkflowStep, definition: dict[str, Any], queue: WorkflowQueue
    ) -> dict[str, Any]:
        """Process debug task completion marker by re-triggering parallel_foreach if more tasks remain."""
        task_id = definition.get("task_id", "")
        total_tasks = definition.get("total_tasks", 0)
        completed_task_index = definition.get("completed_task_index", 0)

        print(f"🐛 DEBUG: Completed task {completed_task_index + 1}/{total_tasks}: {task_id}")

        # Check if there are more tasks to process
        if completed_task_index + 1 < total_tasks:
            print("🐛 DEBUG: More tasks remaining, re-triggering parallel_foreach")

            # Find the original parallel_foreach step in the workflow definition
            # and re-add it to the queue so it can process the next task

            # Look for parallel_foreach step that needs to continue processing
            # We need to find it by scanning the instance's workflow definition
            workflow_def = instance.definition
            if workflow_def and hasattr(workflow_def, "steps"):
                for wf_step in workflow_def.steps:
                    if wf_step.type == "parallel_foreach":
                        # Re-add this step to continue processing
                        print(f"🐛 DEBUG: Re-adding parallel_foreach step: {wf_step.id}")
                        queue.main_queue.insert(0, wf_step)
                        break
        else:
            print("🐛 DEBUG: All tasks completed!")

        return {"executed": True, "task_completion": True}

    def process_debug_step_advance(
        self, instance: WorkflowInstance, step: WorkflowStep, definition: dict[str, Any], queue: WorkflowQueue
    ) -> dict[str, Any]:
        """Process debug step advancement marker by re-triggering parallel_foreach to get next step."""
        task_id = definition.get("task_id", "")
        current_step_index = definition.get("current_step_index", 0)
        total_steps = definition.get("total_steps", 0)
        current_task_index = definition.get("current_task_index", 0)
        total_tasks = definition.get("total_tasks", 0)

        print(f"🐛 DEBUG: Advancing task {current_task_index + 1}/{total_tasks}: {task_id}")
        print(f"🐛 DEBUG: Completed step {current_step_index + 1}/{total_steps}")

        # Re-trigger parallel_foreach to get the next step in the sequence
        workflow_def = instance.definition
        if workflow_def and hasattr(workflow_def, "steps"):
            for wf_step in workflow_def.steps:
                if wf_step.type == "parallel_foreach":
                    print(f"🐛 DEBUG: Re-adding parallel_foreach step for next step: {wf_step.id}")
                    queue.main_queue.insert(0, wf_step)
                    break

        return {"executed": True, "step_advance": True}

    def _build_scoped_context(
        self, instance: WorkflowInstance, state: dict[str, Any], execution_context: ExecutionContext | None = None
    ) -> dict[str, dict[str, Any]]:
        """Build scoped context structure for template resolution.

        Args:
            instance: WorkflowInstance with workflow inputs
            state: Current workflow state (from state manager)
            execution_context: Optional execution context for loop and global variables

        Returns:
            Scoped context dictionary with keys: 'inputs', 'global', 'this', 'loop'
        """
        scoped_context = {
            "inputs": instance.inputs.copy() if instance and instance.inputs else {},
            "global": execution_context.global_variables.copy() if execution_context else {},
            "this": {**state.get("state", {}), **state.get("computed", {})},
            "loop": self._get_current_loop_variables(execution_context),
        }
        return scoped_context

    def _get_current_loop_variables(self, execution_context: ExecutionContext | None) -> dict[str, Any]:
        """Extract current loop variables from execution context with nested loop support.

        Args:
            execution_context: Execution context containing loop state

        Returns:
            Dictionary containing loop variables from nested loops (innermost takes precedence)
        """
        if not execution_context:
            return {}

        # Get nested loop variables with proper isolation
        return execution_context.get_nested_loop_variables()

    def _replace_variables(
        self,
        obj: Any,
        state: dict[str, Any],
        preserve_conditions: bool = False,
        instance: WorkflowInstance | None = None,
        preserve_templates: bool = False,
        execution_context: ExecutionContext | None = None,
    ) -> Any:
        """Replace template variables in an object using scoped contexts.

        Args:
            obj: Object to process for template variables
            state: Legacy state context for backward compatibility
            preserve_conditions: Whether to preserve condition strings
            instance: WorkflowInstance containing workflow inputs
            preserve_templates: Whether to preserve template expressions
            execution_context: Execution context for scoped variable resolution
        """
        # Build scoped context for enhanced expression evaluator
        scoped_context = None
        if instance or execution_context:
            scoped_context = self._build_scoped_context(instance, state, execution_context)

        # Create legacy evaluation context for backward compatibility
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
                        result[k] = self._replace_variables(
                            v, state, preserve_conditions, instance, preserve_templates, execution_context
                        )
                return result
            # Special handling for control flow steps - preserve items/condition fields
            elif preserve_templates and ("items" in obj or "condition" in obj):
                result = {}
                for k, v in obj.items():
                    if k in ["items", "condition"]:
                        result[k] = v  # Keep template expression as-is
                    else:
                        result[k] = self._replace_variables(
                            v, state, preserve_conditions, instance, preserve_templates, execution_context
                        )
                return result
            else:
                return {
                    k: self._replace_variables(
                        v, state, preserve_conditions, instance, preserve_templates, execution_context
                    )
                    for k, v in obj.items()
                }
        elif isinstance(obj, list):
            return [
                self._replace_variables(
                    item, state, preserve_conditions, instance, preserve_templates, execution_context
                )
                for item in obj
            ]
        elif isinstance(obj, str):
            # Handle template strings with multiple variables
            if "{{" in obj and "}}" in obj:
                # Check if the entire string is a single template expression
                import re

                single_expr_match = re.match(r"^\{\{([^}]+)\}\}$", obj)
                if single_expr_match:
                    # For single expressions, return the actual value (not stringified)
                    expr = single_expr_match.group(1).strip()
                    try:
                        # Use enhanced expression evaluator with scoped context
                        result = self.expression_evaluator.evaluate(expr, eval_context, scoped_context)
                        # For single expressions, return the actual value
                        if result is not None:
                            return result
                        # Handle None/undefined with smart fallbacks
                        fallback = self._get_fallback_value(expr, eval_context)
                        # Try to convert to appropriate type for single expressions
                        if "attempt" in expr and "number" in expr:
                            try:
                                return int(fallback) if fallback.isdigit() else 0
                            except:
                                return 0
                        if "max_attempts" in expr:
                            try:
                                return int(fallback) if fallback.isdigit() else 10
                            except:
                                return 10
                        return fallback
                    except Exception:
                        # For evaluation errors, provide fallbacks
                        fallback = self._get_fallback_value(expr, eval_context)
                        # Try to convert to appropriate type for single expressions
                        if "attempt" in expr and "number" in expr:
                            try:
                                return int(fallback) if fallback.isdigit() else 0
                            except:
                                return 0
                        if "max_attempts" in expr:
                            try:
                                return int(fallback) if fallback.isdigit() else 10
                            except:
                                return 10
                        return fallback
                else:
                    # Multiple expressions or embedded in text - stringify results
                    def replace_template(match):
                        expr = match.group(1).strip()
                        try:
                            # Use enhanced expression evaluator with scoped context
                            result = self.expression_evaluator.evaluate(expr, eval_context, scoped_context)
                            # Handle None/undefined values with smart fallbacks
                            if result is None:
                                return self._get_fallback_value(expr, eval_context)
                            return str(result)
                        except Exception:
                            # For evaluation errors, provide fallbacks
                            return self._get_fallback_value(expr, eval_context)

                    # Replace all {{expr}} patterns
                    result = re.sub(r"\{\{([^}]+)\}\}", replace_template, obj)
                    return result
            return obj
        else:
            return obj

    def _get_fallback_value(self, expr: str, state: dict[str, Any]) -> str:
        """Provide intelligent fallback values for undefined template variables."""
        # Common fallback patterns for better error messages
        # Note: state here is nested state structure {inputs: {...}, computed: {...}, state: {...}}
        state_section = state.get("state", {})
        inputs_section = state.get("inputs", {})

        fallback_map = {
            "inputs.file_path": inputs_section.get("file_path", state_section.get("item", "unknown_file")),
            "file_path": inputs_section.get("file_path", state_section.get("item", "unknown_file")),
            # Legacy attempt_number variables removed - use loop.iteration instead
            "inputs.max_attempts": str(inputs_section.get("max_attempts", "10")),
            "max_attempts": str(inputs_section.get("max_attempts", "10")),
            "loop.iteration": str(state_section.get("loop_iteration", "0")),  # For debug mode
            "item": state_section.get("item", inputs_section.get("item", "unknown_item")),
            "state.loop_item": state_section.get("loop_item", "unknown_item"),  # Legacy - deprecated
            "state.loop_index": str(state_section.get("loop_index", "0")),  # Legacy - deprecated
            "task_id": state_section.get("task_id", inputs_section.get("task_id", "unknown_task")),
        }

        # Check for direct matches first
        if expr in fallback_map:
            return str(fallback_map[expr])

        # Check for nested property access patterns (e.g., inputs.step_results.hints.success)
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
        return f"<{expr}>"

    def _flatten_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested state structure for compatibility with existing processors."""
        flattened = {}

        def flatten_dict(d: dict[str, Any], prefix: str = "") -> None:
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    flatten_dict(value, full_key)
                else:
                    flattened[full_key] = value

        flatten_dict(state)
        return flattened

    def _process_user_message(
        self, instance: WorkflowInstance, step: WorkflowStep, processed_definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a user message step using the UserMessageProcessor."""
        result = UserMessageProcessor.process(processed_definition, instance.id, self.state_manager)

        # Add step identification to the result
        if "agent_action" in result:
            result["agent_action"]["step_id"] = step.id

        return {
            "id": step.id,
            "type": step.type,
            "definition": processed_definition,
            "agent_action": result.get("agent_action", {}),
            "execution_context": "client",
        }

    def _process_user_input(
        self, instance: WorkflowInstance, step: WorkflowStep, processed_definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a user input step using the UserInputProcessor from user_message.py."""
        # Import the correct UserInputProcessor from user_message.py
        from .steps.user_message import UserInputProcessor as UserInputProcessorStatic

        result = UserInputProcessorStatic.process(processed_definition, instance.id, self.state_manager)

        # Add step identification to the result
        if "agent_action" in result:
            result["agent_action"]["step_id"] = step.id

        return {
            "id": step.id,
            "type": step.type,
            "definition": processed_definition,
            "agent_action": result.get("agent_action", {}),
            "execution_context": "client",
        }

    def _process_mcp_call(
        self, instance: WorkflowInstance, step: WorkflowStep, processed_definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Process an MCP call step using the MCPCallProcessor."""
        result = MCPCallProcessor.process(processed_definition, instance.id, self.state_manager)

        # Add step identification to the result
        if "agent_action" in result:
            result["agent_action"]["step_id"] = step.id

        return {
            "id": step.id,
            "type": step.type,
            "definition": processed_definition,
            "agent_action": result.get("agent_action", {}),
            "execution_context": "client",
        }

    def _process_parallel_foreach(
        self, instance: WorkflowInstance, step: WorkflowStep, processed_definition: dict[str, Any]
    ) -> dict[str, Any]:
        """Process a parallel_foreach step using the ParallelForEachProcessor."""
        # Create ParallelForEachStep from definition
        try:
            parallel_step = ParallelForEachStep(
                items=processed_definition.get("items", ""),
                sub_agent_task=processed_definition.get("sub_agent_task", "default"),
                max_parallel=processed_definition.get("max_parallel", 10),
                wait_for_all=processed_definition.get("wait_for_all", True),
                sub_agent_prompt_override=processed_definition.get("sub_agent_prompt_override"),
                timeout_seconds=processed_definition.get("timeout_seconds"),
            )

            # Get current state for expression evaluation
            current_state = self.state_manager.read(instance.id)

            # Process the parallel foreach step
            result = self.parallel_foreach_processor.process_parallel_foreach(
                parallel_step, current_state, step.id, instance.id
            )

            # Check for errors
            if "error" in result:
                return {
                    "id": step.id,
                    "type": step.type,
                    "definition": processed_definition,
                    "execution_context": "client",
                    "error": result["error"],
                }

            # Return the processed parallel step
            parallel_step_result = result.get("step", {})
            return {
                "id": step.id,
                "type": step.type,
                "definition": parallel_step_result.get("definition", processed_definition),
                "instructions": parallel_step_result.get("instructions", ""),
                "execution_context": "client",
                "requires_sub_agents": True,
            }

        except Exception as e:
            return {
                "id": step.id,
                "type": step.type,
                "definition": processed_definition,
                "execution_context": "client",
                "error": f"Failed to process parallel_foreach: {str(e)}",
            }

    def _evaluate_javascript_expression(
        self,
        expression: str,
        state: dict[str, Any],
        context: ExecutionContext | None = None,
        workflow_id: str | None = None,
    ) -> Any:
        """
        Evaluate a JavaScript expression using PythonMonkey with full state context.

        Args:
            expression: JavaScript expression to evaluate
            state: Full workflow state
            context: Execution context for scoped variables

        Returns:
            Evaluated result
        """
        try:
            import pythonmonkey as pm

            # Get fresh state if workflow_id is provided to ensure we have the latest updates
            if workflow_id and hasattr(self, "state_manager"):
                fresh_state = self.state_manager.read(workflow_id)
                pm.globalThis.state = fresh_state.get("state", {})
                pm.globalThis.inputs = fresh_state.get("inputs", {})
                pm.globalThis.computed = fresh_state.get("computed", {})
            else:
                # Fallback to provided state
                pm.globalThis.state = state.get("state", {})
                pm.globalThis.inputs = state.get("inputs", {})
                pm.globalThis.computed = state.get("computed", {})

            # Add loop variables if available
            if context:
                loop_vars = context.get_nested_loop_variables()
                pm.globalThis.loop = loop_vars
            else:
                # Check if loop variables are in state (fallback for legacy support)
                state_data = state.get("state", {})
                loop_vars = {}
                # Check for common loop variable names
                for key in ["idx", "qty", "item", "index", "loop_item", "loop_index"]:
                    if key in state_data:
                        loop_vars[key] = state_data[key]
                pm.globalThis.loop = loop_vars

            # Evaluate the expression
            js_code = f"({expression})"
            result = pm.eval(js_code)

            # Convert PythonMonkey proxy objects to native Python objects
            result = self._convert_pythonmonkey_to_native(result)

            # Convert numeric strings to numbers for consistency
            if isinstance(result, str) and result.isdigit():
                result = int(result)
            elif isinstance(result, str):
                try:
                    # Try to convert to float if it's a decimal number
                    if "." in result and result.replace(".", "").replace("-", "").isdigit():
                        result = float(result)
                except ValueError:
                    pass

            # Convert JavaScript floats to integers if they are whole numbers
            if isinstance(result, float) and result.is_integer():
                result = int(result)

            # Cleanup global context
            for attr in ["state", "inputs", "computed", "loop"]:
                try:
                    delattr(pm.globalThis, attr)
                except:
                    pass

            return result

        except ImportError:
            # PythonMonkey not available, fallback to basic evaluation
            return expression
        except Exception:
            # Clean up on error
            try:
                import pythonmonkey as pm

                for attr in ["state", "inputs", "computed", "loop"]:
                    try:
                        delattr(pm.globalThis, attr)
                    except:
                        pass
            except:
                pass
            raise

    def _convert_pythonmonkey_to_native(self, obj: Any) -> Any:
        """
        Convert PythonMonkey proxy objects to native Python objects.

        Args:
            obj: Object that may contain PythonMonkey proxies

        Returns:
            Native Python object
        """
        # IMPORTANT: Check for arrays FIRST, before checking for objects with keys
        # JavaScript arrays have both length and keys(), but should be treated as arrays
        if hasattr(obj, "length") and hasattr(obj, "__getitem__"):
            try:
                # Convert length to integer as PythonMonkey may return float
                length = int(obj.length)
                result = [self._convert_pythonmonkey_to_native(obj[i]) for i in range(length)]
                return result
            except Exception:
                # If array conversion fails, fall through to other conversion methods
                pass

        # If it's a dict-like object (including PythonMonkey proxies), manually convert
        if hasattr(obj, "keys") and callable(obj.keys):
            try:
                # Manual dictionary conversion to handle PythonMonkey proxy dicts
                native_dict = {}
                for key in obj.keys():
                    value = obj[key]
                    # Recursively convert values
                    native_dict[str(key)] = self._convert_pythonmonkey_to_native(value)
                return native_dict
            except:
                pass

        # If it's a primitive value that might be a PythonMonkey proxy, convert to native type
        if isinstance(obj, (int, float, str, bool)) or obj is None:
            # Convert numeric strings to numbers for consistency with JavaScript behavior
            if isinstance(obj, str):
                # Check if it's a pure integer
                if obj.isdigit() or (obj.startswith("-") and obj[1:].isdigit()):
                    return int(obj)
                # Check if it's a float
                try:
                    if "." in obj and obj.replace(".", "").replace("-", "").isdigit():
                        return float(obj)
                except:
                    pass
            return obj

        # For other objects, try to convert to string as fallback
        if hasattr(obj, "toString"):
            try:
                return str(obj)
            except:
                pass

        # Return as-is if we can't convert it
        return obj
