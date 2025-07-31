"""Variable replacement utilities for workflow steps."""

import re
from typing import Any


class VariableReplacer:
    """Handles variable interpolation in workflow step definitions."""

    @staticmethod
    def replace(step_definition: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Replace variables in step definition with state values.

        Args:
            step_definition: Step definition with potential variables
            state: Flattened state to use for replacement

        Returns:
            Step definition with variables replaced
        """
        # Deep copy to avoid modifying original
        import copy

        result = copy.deepcopy(step_definition)

        # Replace variables recursively
        return VariableReplacer._replace_recursive(result, state)

    @staticmethod
    def _replace_recursive(obj: Any, state: dict[str, Any]) -> Any:
        """Recursively replace variables in nested objects."""
        if isinstance(obj, dict):
            return {k: VariableReplacer._replace_recursive(v, state) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [VariableReplacer._replace_recursive(item, state) for item in obj]
        elif isinstance(obj, str):
            return VariableReplacer._replace_string(obj, state)
        else:
            return obj

    @staticmethod
    def _replace_string(text: str, state: dict[str, Any]) -> str:
        """Replace variables in a string using {{ variable }} syntax."""
        # Find all {{ variable }} patterns
        pattern = r"\{\{\s*([^}]+)\s*\}\}"

        # Import ExpressionEvaluator for complex expressions
        from .expressions import ExpressionEvaluator

        evaluator = ExpressionEvaluator()

        def replace_match(match):
            var_expr = match.group(1).strip()

            # First try simple variable lookup
            if var_expr in state:
                return str(state[var_expr])

            # For dot notation expressions, always use the expression evaluator
            if "." in var_expr:
                try:
                    result = evaluator.evaluate(var_expr, state)
                    return str(result)
                except Exception:
                    # If evaluation fails, keep original
                    return f"{{{{ {var_expr} }}}}"

            # If it contains operators or is more complex, evaluate as expression
            if any(op in var_expr for op in ["||", "&&", "==", "!=", ">", "<", "+", "-", "*", "/", "?", ":"]):
                try:
                    result = evaluator.evaluate(var_expr, state)
                    return str(result)
                except Exception:
                    # If evaluation fails, keep original
                    return f"{{{{ {var_expr} }}}}"

            # Simple variable lookup with fallback
            return str(state.get(var_expr, f"{{{{ {var_expr} }}}}"))

        return re.sub(pattern, replace_match, text)
