"""ForEach step processor for MCP Workflow System.

Handles iteration over arrays with item and index variable binding.
"""

from typing import Any

from ..context import ExecutionContext
from ..control_flow import ControlFlowError, LoopControl, LoopState
from ..expressions import ExpressionError, ExpressionEvaluator
from ..models import WorkflowStep


class ForEachProcessor:
    """Processes foreach workflow steps."""

    def __init__(self):
        self.expression_evaluator = ExpressionEvaluator()

    def process_foreach(
        self,
        step: WorkflowStep,
        context: ExecutionContext,
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a foreach step.

        Args:
            step: The foreach step to process
            context: Current execution context
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing foreach initialization result
        """
        definition = step.definition
        items_expression = definition.get("items", "")
        variable_name = definition.get("variable_name", "item")
        index_name = definition.get("index_name", "index")
        body_steps = definition.get("body", [])

        if not items_expression:
            raise ControlFlowError("ForEach step missing 'items' field")

        try:
            # Evaluate the items expression to get the array
            items = self._evaluate_items_expression(items_expression, state, context)

            if not isinstance(items, list):
                raise ControlFlowError(f"ForEach items expression must evaluate to an array, got {type(items)}")

            if len(items) == 0:
                return {
                    "type": "foreach_skipped",
                    "step_id": step.id,
                    "reason": "Empty array",
                    "items_expression": items_expression
                }

            # Create loop state
            loop_state = LoopState(
                loop_type="foreach",
                loop_id=step.id,
                max_iterations=len(items),
                items=items,
                current_item_index=0
            )

            # Store variable names for later use
            loop_state.variable_name = variable_name
            loop_state.index_name = index_name

            # Set initial loop variables
            loop_state.variable_bindings[variable_name] = items[0]
            loop_state.variable_bindings[index_name] = 0

            # Convert body step definitions to WorkflowStep objects
            workflow_steps = []
            for i, step_def in enumerate(body_steps):
                step_id = f"{step.id}.body.{i}"
                workflow_steps.append(WorkflowStep(
                    id=step_id,
                    type=step_def.get("type", "unknown"),
                    definition=step_def
                ))

            # Enter the loop
            context.enter_loop(loop_state)

            # Create loop frame
            loop_frame = context.create_loop_frame(
                steps=workflow_steps,
                loop_state=loop_state
            )
            context.push_frame(loop_frame)

            return {
                "type": "foreach_started",
                "step_id": step.id,
                "loop_id": loop_state.loop_id,
                "items_count": len(items),
                "variable_name": variable_name,
                "index_name": index_name,
                "body_steps": len(workflow_steps),
                "current_item": items[0],
                "current_index": 0
            }

        except ExpressionError as e:
            raise ControlFlowError(f"Failed to evaluate foreach items expression '{items_expression}': {str(e)}") from e
        except Exception as e:
            raise ControlFlowError(f"Error processing foreach step: {str(e)}") from e

    def check_foreach_continuation(
        self,
        context: ExecutionContext,
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Check if a foreach loop should continue to the next iteration.

        Args:
            context: Current execution context
            state: Current workflow state

        Returns:
            Dictionary containing foreach continuation decision
        """
        current_loop = context.current_loop()
        if not current_loop or current_loop.loop_type != "foreach":
            raise ControlFlowError("Not currently in a foreach loop")

        # Check for control signals
        if current_loop.control_signal == LoopControl.BREAK:
            return self._exit_foreach(context, "break_signal")

        # Check if we've processed all items
        if current_loop.is_complete():
            return self._exit_foreach(context, "all_items_processed")

        # Advance to next item
        current_loop.advance_iteration()

        if current_loop.current_item_index < len(current_loop.items):
            # Set up variables for next iteration
            current_item = current_loop.get_current_item()
            current_index = current_loop.current_item_index

            # Get variable names from loop state
            variable_name = getattr(current_loop, 'variable_name', 'item')
            index_name = getattr(current_loop, 'index_name', 'index')

            current_loop.variable_bindings[variable_name] = current_item
            current_loop.variable_bindings[index_name] = current_index

            # Reset frame to beginning of body
            current_frame = context.current_frame()
            if current_frame:
                current_frame.current_step_index = 0

            return {
                "type": "foreach_continue",
                "loop_id": current_loop.loop_id,
                "current_item": current_item,
                "current_index": current_index,
                "iteration": current_loop.current_iteration
            }
        else:
            return self._exit_foreach(context, "items_exhausted")

    def _evaluate_items_expression(
        self,
        items_expression: str,
        state: dict[str, Any],
        context: ExecutionContext
    ) -> list[Any]:
        """
        Evaluate the items expression to get the array to iterate over.

        Args:
            items_expression: The expression that should return an array
            state: Current workflow state
            context: Current execution context

        Returns:
            List of items to iterate over
        """
        # Clean the expression
        cleaned_expression = items_expression.strip()
        if cleaned_expression.startswith("{{") and cleaned_expression.endswith("}}"):
            cleaned_expression = cleaned_expression[2:-2].strip()

        # Merge state with context variables for evaluation
        evaluation_context = dict(state)
        evaluation_context.update(context.get_all_variables())

        # Evaluate the expression
        result = self.expression_evaluator.evaluate(cleaned_expression, evaluation_context)

        # Ensure we have a list
        if result is None:
            return []
        elif isinstance(result, list):
            return result
        elif isinstance(result, str):
            # Split strings into character array
            return list(result)
        elif hasattr(result, '__iter__') and not isinstance(result, dict):
            # Convert other iterables to list
            return list(result)
        else:
            # Wrap single items in a list
            return [result]

    def _exit_foreach(self, context: ExecutionContext, reason: str) -> dict[str, Any]:
        """
        Exit the current foreach loop.

        Args:
            context: Current execution context
            reason: Reason for exiting the loop

        Returns:
            Dictionary containing foreach exit information
        """
        current_loop = context.current_loop()
        loop_id = current_loop.loop_id if current_loop else "unknown"
        iteration = current_loop.current_iteration if current_loop else 0
        items_count = len(current_loop.items) if current_loop and current_loop.items else 0

        # Exit the loop
        context.exit_loop()

        # Pop the loop frame
        context.pop_frame()

        return {
            "type": "foreach_exited",
            "loop_id": loop_id,
            "reason": reason,
            "total_iterations": iteration,
            "items_processed": iteration,
            "total_items": items_count
        }

    def expand_foreach_steps(
        self,
        step: WorkflowStep,
        context: ExecutionContext,
        state: dict[str, Any]
    ) -> list[WorkflowStep]:
        """
        Expand a foreach loop into individual steps for each item.
        This is an alternative to the iterative approach for simpler execution.

        Args:
            step: The foreach step to expand
            context: Current execution context
            state: Current workflow state

        Returns:
            List of expanded workflow steps
        """
        definition = step.definition
        items_expression = definition.get("items", "")
        variable_name = definition.get("variable_name", "item")
        index_name = definition.get("index_name", "index")
        body_steps = definition.get("body", [])

        try:
            # Evaluate the items expression
            items = self._evaluate_items_expression(items_expression, state, context)

            if not isinstance(items, list):
                raise ControlFlowError(f"ForEach items expression must evaluate to an array, got {type(items)}")

            expanded_steps = []

            for index, item in enumerate(items):
                # Create variable bindings for this iteration
                iteration_variables = {
                    variable_name: item,
                    index_name: index
                }

                # Expand each body step with variable substitution
                for i, step_def in enumerate(body_steps):
                    step_id = f"{step.id}.{index}.{i}"

                    # Substitute variables in step definition
                    substituted_def = self._substitute_variables(step_def, iteration_variables)

                    expanded_steps.append(WorkflowStep(
                        id=step_id,
                        type=step_def.get("type", "unknown"),
                        definition=substituted_def
                    ))

            return expanded_steps

        except ExpressionError as e:
            raise ControlFlowError(f"Failed to expand foreach step '{step.id}': {str(e)}") from e
        except Exception as e:
            raise ControlFlowError(f"Error expanding foreach step: {str(e)}") from e

    def _substitute_variables(self, step_def: dict[str, Any], variables: dict[str, Any]) -> dict[str, Any]:
        """
        Substitute foreach variables in a step definition.

        Args:
            step_def: Original step definition
            variables: Variables to substitute

        Returns:
            Step definition with variables substituted
        """
        import json
        import re

        # Convert to JSON string for substitution
        step_json = json.dumps(step_def)

        # Substitute variables
        for var_name, var_value in variables.items():
            # Replace {{variable_name}} patterns
            pattern = r'\{\{\s*' + re.escape(var_name) + r'\s*\}\}'
            replacement = json.dumps(var_value) if not isinstance(var_value, str) else var_value
            step_json = re.sub(pattern, replacement, step_json)

        # Convert back to dictionary
        return json.loads(step_json)
