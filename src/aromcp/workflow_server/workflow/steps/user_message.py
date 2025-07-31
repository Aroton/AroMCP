"""User message step processor for workflow execution."""

from typing import Any


class UserMessageProcessor:
    """Processes user message steps for display."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Format a user message step.

        Args:
            step_definition: Step definition with message and optional formatting
            workflow_id: ID of the workflow instance
            state_manager: State manager (not used for formatting)

        Returns:
            Formatted message for display
        """
        message = step_definition.get("message")
        if not message:
            return {"status": "failed", "error": "Missing 'message' in user_message step"}

        # Note: Variable replacement happens in the executor before this processor
        # So the message should already have variables replaced

        message_type = step_definition.get("type", "info")  # info, warning, error, success
        title = step_definition.get("title")
        format_as = step_definition.get("format", "text")  # text, markdown, code

        result = {
            "status": "success",
            "agent_action": {
                "type": "user_message",
                "message": message,
                "message_type": message_type,
                "format": format_as,
            },
            "execution_type": "agent",
        }

        if title:
            result["agent_action"]["title"] = title

        return result


class UserInputProcessor:
    """Processes user input request steps."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Format a user input request step.

        Args:
            step_definition: Step definition with prompt and input specifications
            workflow_id: ID of the workflow instance
            state_manager: State manager (not used for formatting)

        Returns:
            Formatted input request for agent
        """
        prompt = step_definition.get("prompt")
        if not prompt:
            return {"status": "failed", "error": "Missing 'prompt' in user_input step"}

        input_type = step_definition.get("input_type", "text")  # text, number, boolean, choice
        choices = step_definition.get("choices")  # For choice type
        default_value = step_definition.get("default")
        required = step_definition.get("required", True)
        state_update = step_definition.get("state_update")

        input_request = {"type": "user_input", "prompt": prompt, "input_type": input_type, "required": required}

        if choices:
            input_request["choices"] = choices

        if default_value is not None:
            input_request["default"] = default_value

        if state_update:
            input_request["state_update"] = state_update

        return {"status": "success", "agent_action": input_request, "execution_type": "agent"}


class ConditionalMessageProcessor:
    """Processes conditional message steps."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Process a conditional message that may or may not be shown.

        Args:
            step_definition: Step definition with condition and message
            workflow_id: ID of the workflow instance
            state_manager: State manager for reading state

        Returns:
            Conditional message result
        """
        condition = step_definition.get("condition")
        message = step_definition.get("message")

        if not condition:
            return {"status": "failed", "error": "Missing 'condition' in conditional_message step"}

        if not message:
            return {"status": "failed", "error": "Missing 'message' in conditional_message step"}

        try:
            # Get current state
            current_state = state_manager.read(workflow_id)

            # Evaluate condition (simple implementation for Phase 2)
            # In Phase 3, this would use the expression evaluator
            condition_result = ConditionalMessageProcessor._evaluate_simple_condition(condition, current_state)

            if condition_result:
                # Show the message
                return UserMessageProcessor.process(
                    {
                        "message": message,
                        "type": step_definition.get("type", "info"),
                        "title": step_definition.get("title"),
                        "format": step_definition.get("format", "text"),
                    },
                    workflow_id,
                    state_manager,
                )
            else:
                # Skip the message
                return {"status": "success", "skipped": True, "reason": f"Condition '{condition}' evaluated to false"}

        except Exception as e:
            return {"status": "failed", "error": f"Failed to evaluate condition: {e}"}

    @staticmethod
    def _evaluate_simple_condition(condition: str, state: dict[str, Any]) -> bool:
        """Simple condition evaluation for Phase 2.

        Supports basic comparisons like:
        - field_name == "value"
        - field_name > 5
        - field_name != null
        """
        # Remove surrounding whitespace
        condition = condition.strip()

        # Simple pattern matching for basic conditions
        # This is a minimal implementation for Phase 2

        # Handle equality
        if " == " in condition:
            left, right = condition.split(" == ", 1)
            left_val = state.get(left.strip())
            right_val = right.strip().strip("\"'")
            try:
                # Try to convert to number if possible
                right_val = float(right_val) if "." in right_val else int(right_val)
            except ValueError:
                pass
            return left_val == right_val

        # Handle inequality
        if " != " in condition:
            left, right = condition.split(" != ", 1)
            left_val = state.get(left.strip())
            right_val = right.strip().strip("\"'")
            if right_val == "null":
                return left_val is not None
            try:
                right_val = float(right_val) if "." in right_val else int(right_val)
            except ValueError:
                pass
            return left_val != right_val

        # Handle greater than
        if " > " in condition:
            left, right = condition.split(" > ", 1)
            left_val = state.get(left.strip(), 0)
            right_val = float(right.strip())
            return float(left_val) > right_val

        # Handle less than
        if " < " in condition:
            left, right = condition.split(" < ", 1)
            left_val = state.get(left.strip(), 0)
            right_val = float(right.strip())
            return float(left_val) < right_val

        # Default: check if field exists and is truthy
        return bool(state.get(condition.strip()))
