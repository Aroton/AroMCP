"""Conditional step processor for MCP Workflow System.

Handles if/then/else conditional execution based on expression evaluation.
"""

from typing import Any

from ..context import ExecutionContext
from ..control_flow import ConditionalResult, ControlFlowError
from ..expressions import ExpressionError, ExpressionEvaluator
from ..models import WorkflowStep


class ConditionalProcessor:
    """Processes conditional workflow steps."""

    def __init__(self):
        self.expression_evaluator = ExpressionEvaluator()

    def process_conditional(
        self,
        step: WorkflowStep,
        context: ExecutionContext,
        state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a conditional step and determine which branch to execute.

        Args:
            step: The conditional step to process
            context: Current execution context
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing the conditional result and next steps
        """
        definition = step.definition
        condition = definition.get("condition", "")
        then_steps = definition.get("then_steps", [])
        else_steps = definition.get("else_steps", [])

        if not condition:
            raise ControlFlowError("Conditional step missing 'condition' field")

        try:
            # Evaluate the condition
            condition_result = self._evaluate_condition(condition, state)

            # Determine which branch to take
            branch_taken = "then" if condition_result.condition_result else "else"
            selected_steps = then_steps if condition_result.condition_result else else_steps

            # Convert step definitions back to WorkflowStep objects
            workflow_steps = []
            if selected_steps:
                for i, step_def in enumerate(selected_steps):
                    step_id = f"{step.id}.{branch_taken}.{i}"
                    workflow_steps.append(WorkflowStep(
                        id=step_id,
                        type=step_def.get("type", "unknown"),
                        definition=step_def
                    ))

            # Create conditional frame if there are steps to execute
            if workflow_steps:
                conditional_frame = context.create_conditional_frame(
                    steps=workflow_steps,
                    condition_id=step.id
                )
                context.push_frame(conditional_frame)

            # Record the condition evaluation in context
            condition_result.branch_taken = branch_taken

            return {
                "type": "conditional_evaluated",
                "step_id": step.id,
                "condition_result": condition_result.to_step_definition(),
                "steps_to_execute": len(workflow_steps),
                "branch_taken": branch_taken
            }

        except ExpressionError as e:
            raise ControlFlowError(f"Failed to evaluate condition '{condition}': {str(e)}") from e
        except Exception as e:
            raise ControlFlowError(f"Error processing conditional step: {str(e)}") from e

    def _evaluate_condition(self, condition: str, state: dict[str, Any]) -> ConditionalResult:
        """
        Evaluate a conditional expression against the current state.

        Args:
            condition: The condition expression to evaluate
            state: Current workflow state

        Returns:
            ConditionalResult with evaluation details
        """
        # Remove template braces if present
        cleaned_condition = condition.strip()
        if cleaned_condition.startswith("{{") and cleaned_condition.endswith("}}"):
            cleaned_condition = cleaned_condition[2:-2].strip()

        # Evaluate the expression
        result = self.expression_evaluator.evaluate(cleaned_condition, state)

        # Convert result to boolean
        condition_result = bool(result)

        # Capture evaluated values for debugging
        evaluated_values = self._extract_variable_values(cleaned_condition, state)

        return ConditionalResult(
            condition_result=condition_result,
            original_condition=condition,
            evaluated_values=evaluated_values
        )

    def _extract_variable_values(self, expression: str, state: dict[str, Any]) -> dict[str, Any]:
        """
        Extract variable values referenced in the expression for debugging.

        Args:
            expression: The expression to analyze
            state: Current workflow state

        Returns:
            Dictionary of variable names to their values
        """
        evaluated_values = {}

        # Simple extraction of variable names (could be improved with proper parsing)
        import re

        # Find simple variable references (alphanumeric + dot notation)
        variable_pattern = r'\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\b'
        variables = re.findall(variable_pattern, expression)

        for var in variables:
            # Skip keywords and operators
            if var in ['true', 'false', 'null', 'undefined', 'and', 'or', 'not', 'if', 'else', 'then']:
                continue

            # Get the variable value from state
            try:
                value = self._get_nested_value(state, var)
                evaluated_values[var] = value
            except (KeyError, AttributeError, TypeError):
                evaluated_values[var] = None

        return evaluated_values

    def _get_nested_value(self, data: dict[str, Any], path: str) -> Any:
        """
        Get a nested value from a dictionary using dot notation.

        Args:
            data: The dictionary to traverse
            path: Dot-separated path (e.g., "user.name")

        Returns:
            The value at the specified path
        """
        current = data
        parts = path.split('.')

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                index = int(part)
                current = current[index] if 0 <= index < len(current) else None
            else:
                return None

            if current is None:
                break

        return current
