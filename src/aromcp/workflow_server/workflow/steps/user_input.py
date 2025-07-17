"""User input step processor for MCP Workflow System.

Handles user input with validation, retry logic, and type conversion.
"""

import re
from typing import Any

from ..context import ExecutionContext
from ..control_flow import ControlFlowError
from ..models import WorkflowStep


class UserInputProcessor:
    """Processes user input workflow steps."""

    def process_user_input(
        self, step: WorkflowStep, context: ExecutionContext, state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Process a user input step.

        Args:
            step: The user input step to process
            context: Current execution context
            state: Current workflow state (flattened view)

        Returns:
            Dictionary containing user input step instructions for the agent
        """
        definition = step.definition
        prompt = definition.get("prompt", "Please enter a value:")
        variable_name = definition.get("variable_name", "user_input")
        validation_pattern = definition.get("validation_pattern")
        validation_message = definition.get("validation_message", "Invalid input format")
        input_type = definition.get("input_type", "string")
        required = definition.get("required", True)
        max_attempts = definition.get("max_attempts", 3)

        # Get current attempt count from context
        attempt_key = f"{step.id}_attempts"
        current_attempts = context.get_variable(attempt_key) or 0

        if current_attempts >= max_attempts:
            raise ControlFlowError(f"Maximum input attempts ({max_attempts}) exceeded for step {step.id}")

        # Increment attempt count
        context.set_variable(attempt_key, current_attempts + 1)

        return {
            "type": "user_input_required",
            "step_id": step.id,
            "prompt": prompt,
            "variable_name": variable_name,
            "input_type": input_type,
            "required": required,
            "validation_pattern": validation_pattern,
            "validation_message": validation_message,
            "current_attempt": current_attempts + 1,
            "max_attempts": max_attempts,
            "instructions": self._generate_input_instructions(prompt, input_type, validation_pattern, required),
        }

    def validate_and_store_input(
        self, step: WorkflowStep, user_input: str, context: ExecutionContext
    ) -> dict[str, Any]:
        """
        Validate user input and store it in the workflow state.

        Args:
            step: The user input step
            user_input: The input provided by the user
            context: Current execution context

        Returns:
            Dictionary containing validation result
        """
        definition = step.definition
        variable_name = definition.get("variable_name", "user_input")
        validation_pattern = definition.get("validation_pattern")
        validation_message = definition.get("validation_message", "Invalid input format")
        input_type = definition.get("input_type", "string")
        required = definition.get("required", True)

        try:
            # Check if input is required and empty
            if required and not user_input.strip():
                return {"valid": False, "error": "Input is required but was empty", "retry": True}

            # Validate pattern if provided
            if validation_pattern and user_input.strip():
                if not re.match(validation_pattern, user_input):
                    return {"valid": False, "error": validation_message, "retry": True}

            # Convert to appropriate type
            converted_value = self._convert_input_type(user_input, input_type)

            # Store in context
            context.set_variable(variable_name, converted_value)

            # Clear attempt counter
            attempt_key = f"{step.id}_attempts"
            context.set_variable(attempt_key, 0)

            return {"valid": True, "value": converted_value, "variable_name": variable_name, "stored": True}

        except ValueError as e:
            return {"valid": False, "error": f"Type conversion error: {str(e)}", "retry": True}
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}", "retry": True}

    def _convert_input_type(self, user_input: str, input_type: str) -> Any:
        """
        Convert user input to the specified type.

        Args:
            user_input: Raw user input string
            input_type: Target type ("string", "number", "boolean", "json")

        Returns:
            Converted value
        """
        if input_type == "string":
            return user_input

        elif input_type == "number":
            # Try integer first, then float
            try:
                if "." in user_input:
                    return float(user_input)
                else:
                    return int(user_input)
            except ValueError:
                raise ValueError(f"'{user_input}' is not a valid number") from None

        elif input_type == "boolean":
            # Accept various boolean representations
            lower_input = user_input.lower().strip()
            if lower_input in ("true", "yes", "y", "1", "on"):
                return True
            elif lower_input in ("false", "no", "n", "0", "off"):
                return False
            else:
                raise ValueError(f"'{user_input}' is not a valid boolean (use true/false, yes/no, 1/0)")

        elif input_type == "json":
            import json

            try:
                return json.loads(user_input)
            except json.JSONDecodeError:
                raise ValueError(f"'{user_input}' is not valid JSON") from None

        else:
            # Default to string for unknown types
            return user_input

    def _generate_input_instructions(
        self, prompt: str, input_type: str, validation_pattern: str | None, required: bool
    ) -> str:
        """
        Generate detailed instructions for the agent to present to the user.

        Args:
            prompt: The input prompt
            input_type: Expected input type
            validation_pattern: Validation regex pattern if any
            required: Whether input is required

        Returns:
            Formatted instructions string
        """
        instructions = [prompt]

        # Add type information
        if input_type == "number":
            instructions.append("(Enter a number)")
        elif input_type == "boolean":
            instructions.append("(Enter true/false, yes/no, or 1/0)")
        elif input_type == "json":
            instructions.append("(Enter valid JSON)")

        # Add pattern information
        if validation_pattern:
            instructions.append(f"Format: {validation_pattern}")

        # Add required information
        if not required:
            instructions.append("(Optional - press Enter to skip)")

        return " ".join(instructions)

    def create_input_validation_examples(self, input_type: str, validation_pattern: str | None) -> list[str]:
        """
        Create example inputs for the given type and pattern.

        Args:
            input_type: The expected input type
            validation_pattern: Validation regex pattern if any

        Returns:
            List of example valid inputs
        """
        examples = []

        if input_type == "string":
            if validation_pattern:
                # Pattern-specific examples would require pattern analysis
                examples.append("Example: (depends on pattern)")
            else:
                examples.extend(["Example: Hello World", "Example: Any text"])

        elif input_type == "number":
            examples.extend(["Example: 42", "Example: 3.14", "Example: -10"])

        elif input_type == "boolean":
            examples.extend(["Example: true", "Example: false", "Example: yes", "Example: no"])

        elif input_type == "json":
            examples.extend(['Example: {"key": "value"}', "Example: [1, 2, 3]", 'Example: "simple string"'])

        return examples

    def get_input_help_text(self, step: WorkflowStep) -> str:
        """
        Generate help text for a user input step.

        Args:
            step: The user input step

        Returns:
            Help text explaining the input requirements
        """
        definition = step.definition
        input_type = definition.get("input_type", "string")
        validation_pattern = definition.get("validation_pattern")
        required = definition.get("required", True)

        help_lines = []

        if input_type == "number":
            help_lines.append("Enter a numeric value (integer or decimal)")
        elif input_type == "boolean":
            help_lines.append("Enter a boolean value:")
            help_lines.append("  - True: true, yes, y, 1, on")
            help_lines.append("  - False: false, no, n, 0, off")
        elif input_type == "json":
            help_lines.append("Enter valid JSON data")
            help_lines.append('Examples: {"key": "value"}, [1,2,3], "text"')
        else:
            help_lines.append("Enter text")

        if validation_pattern:
            help_lines.append(f"Must match pattern: {validation_pattern}")

        if not required:
            help_lines.append("This input is optional - press Enter to skip")

        examples = self.create_input_validation_examples(input_type, validation_pattern)
        if examples:
            help_lines.append("Examples:")
            help_lines.extend(f"  {example}" for example in examples)

        return "\n".join(help_lines)
