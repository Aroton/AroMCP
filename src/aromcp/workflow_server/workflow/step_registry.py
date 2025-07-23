"""Declarative configuration for workflow step types.

This registry defines all available step types, their execution context,
queuing behavior, and validation requirements.
"""

from typing import Any, Literal, TypedDict


class StepConfig(TypedDict):
    """Configuration for a workflow step type."""

    execution: Literal["client", "server"]
    queuing: Literal["batch", "blocking", "immediate", "expand", "wait"]
    description: str
    supports_state_update: bool
    required_fields: list[str]
    optional_fields: list[str]


# Registry of all workflow step types
STEP_TYPES: dict[str, StepConfig] = {
    # Client-executed steps (require agent/client interaction)
    "user_message": {
        "execution": "client",
        "queuing": "batch",  # Can be batched with other user_messages
        "description": "Display message to user",
        "supports_state_update": False,
        "required_fields": ["message"],
        "optional_fields": ["message_type", "format"]
    },

    "mcp_call": {
        "execution": "client",
        "queuing": "blocking",  # Blocks until completed
        "description": "Execute MCP tool call",
        "supports_state_update": True,  # Via state_update field
        "required_fields": ["tool"],
        "optional_fields": ["parameters", "state_update", "store_result", "timeout", "error_handling"]
    },

    "user_input": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Collect user input",
        "supports_state_update": True,
        "required_fields": ["prompt"],
        "optional_fields": ["instructions", "input_type", "choices", "validation", "state_update", "default", "max_retries", "error_handling"]
    },

    "wait_step": {
        "execution": "server",
        "queuing": "wait",  # Special queuing behavior - waits for client
        "description": "Wait for client to call get_next_step before continuing",
        "supports_state_update": False,
        "required_fields": [],
        "optional_fields": ["message", "timeout_seconds"]
    },

    "agent_prompt": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Task instruction for agent execution",
        "supports_state_update": False,
        "required_fields": ["prompt"],
        "optional_fields": ["context", "expected_response", "timeout", "max_retries"]
    },

    "agent_response": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Process and validate agent response",
        "supports_state_update": True,
        "required_fields": [],
        "optional_fields": ["response_schema", "state_updates", "store_response", "validation", "error_handling"]
    },

    "parallel_foreach": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Execute sub-agents in parallel",
        "supports_state_update": False,
        "required_fields": ["items", "sub_agent_task"],
        "optional_fields": ["max_parallel", "timeout_seconds"]
    },

    # Server-executed steps (processed internally)
    "shell_command": {
        "execution": "server",
        "queuing": "immediate",  # Execute immediately server-side
        "description": "Execute shell command on server",
        "supports_state_update": True,  # Via state_update and state_updates fields
        "required_fields": ["command"],
        "optional_fields": ["working_directory", "timeout", "state_update", "state_updates", "error_handling", "execution_context"]
    },

    # Control flow steps (server-side logic)
    "conditional": {
        "execution": "server",
        "queuing": "expand",  # Expands into branch steps
        "description": "Conditional branching",
        "supports_state_update": False,
        "required_fields": ["condition"],
        "optional_fields": ["then_steps", "else_steps"]
    },

    "while_loop": {
        "execution": "server",
        "queuing": "expand",
        "description": "Loop while condition is true",
        "supports_state_update": False,
        "required_fields": ["condition", "body"],
        "optional_fields": ["max_iterations"]
    },

    "foreach": {
        "execution": "server",
        "queuing": "expand",
        "description": "Iterate over items",
        "supports_state_update": False,
        "required_fields": ["items", "body"],
        "optional_fields": ["variable_name"]
    },

    "break": {
        "execution": "server",
        "queuing": "immediate",
        "description": "Exit current loop",
        "supports_state_update": False,
        "required_fields": [],
        "optional_fields": []
    },

    "continue": {
        "execution": "server",
        "queuing": "immediate",
        "description": "Skip to next loop iteration",
        "supports_state_update": False,
        "required_fields": [],
        "optional_fields": []
    },

    # Debug mode steps (for serial debugging)
    "debug_task_completion": {
        "execution": "server",
        "queuing": "immediate",
        "description": "Debug marker for task completion in serial mode",
        "supports_state_update": False,
        "required_fields": ["task_id", "total_tasks", "completed_task_index"],
        "optional_fields": []
    },

    "debug_step_advance": {
        "execution": "server",
        "queuing": "immediate",
        "description": "Debug marker for step advancement in serial mode",
        "supports_state_update": False,
        "required_fields": ["task_id", "current_step_index", "total_steps", "total_tasks", "current_task_index"],
        "optional_fields": []
    },
}


class StepRegistry:
    """Registry for workflow step types and their configurations."""

    def __init__(self):
        self.step_types = STEP_TYPES

    def get(self, step_type: str) -> StepConfig | None:
        """Get configuration for a step type."""
        return self.step_types.get(step_type)

    def validate_step(self, step: dict[str, Any]) -> tuple[bool, str | None]:
        """Validate a step against its configuration.

        Returns:
            Tuple of (is_valid, error_message)
        """
        step_type = step.get("type")
        if not step_type:
            return False, "Step missing 'type' field"

        # Check for deprecated step types
        if self.is_deprecated_step_type(step_type):
            suggestion = self.suggest_replacement_for_deprecated(step_type)
            return False, f"Step type '{step_type}' has been deprecated and removed. {suggestion}"

        config = self.get(step_type)
        if not config:
            return False, f"Unknown step type: {step_type}"

        # Check required fields
        for field in config["required_fields"]:
            if field not in step:
                return False, f"Step type '{step_type}' missing required field: {field}"

        # Special validation: execution_context only allowed on shell_command steps
        if "execution_context" in step and step_type != "shell_command":
            return False, f"Field 'execution_context' is only allowed on 'shell_command' steps, not '{step_type}'"

        # Check for unknown fields
        allowed_fields = {"id", "type"} | set(config["required_fields"]) | set(config["optional_fields"])
        for field in step:
            if field not in allowed_fields:
                return False, f"Step type '{step_type}' has unknown field: {field}"

        # Validate execution_context values if present
        if "execution_context" in step:
            valid_contexts = ["client", "server"]
            if step["execution_context"] not in valid_contexts:
                return False, f"Invalid execution_context '{step['execution_context']}'. Must be one of: {valid_contexts}"

        return True, None

    def is_client_step(self, step_type: str) -> bool:
        """Check if a step type is client-executed."""
        config = self.get(step_type)
        return config["execution"] == "client" if config else False

    def is_server_step(self, step_type: str) -> bool:
        """Check if a step type is server-executed."""
        config = self.get(step_type)
        return config["execution"] == "server" if config else False

    def is_batchable(self, step_type: str) -> bool:
        """Check if a step type can be batched with others."""
        config = self.get(step_type)
        return config["queuing"] == "batch" if config else False

    def is_control_flow(self, step_type: str) -> bool:
        """Check if a step type is a control flow step."""
        config = self.get(step_type)
        return config["queuing"] == "expand" if config else False

    def get_deprecated_step_types(self) -> list[str]:
        """Get list of deprecated step types that have been removed."""
        return ["state_update", "batch_state_update"]

    def is_deprecated_step_type(self, step_type: str) -> bool:
        """Check if a step type is deprecated and should not be used."""
        return step_type in self.get_deprecated_step_types()

    def get_all_valid_step_types(self) -> list[str]:
        """Get list of all valid step types."""
        return list(self.step_types.keys())

    def suggest_replacement_for_deprecated(self, step_type: str) -> str | None:
        """Suggest replacement for deprecated step types."""
        replacements = {
            "state_update": "Use 'state_update' field within other step types (mcp_call, user_input, shell_command, agent_response)",
            "batch_state_update": "Use 'state_updates' field within 'agent_response' step type"
        }
        return replacements.get(step_type)