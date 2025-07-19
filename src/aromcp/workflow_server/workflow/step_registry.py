"""Declarative configuration for workflow step types.

This registry defines all available step types, their execution context,
queuing behavior, and validation requirements.
"""

from typing import Any, Literal, TypedDict


class StepConfig(TypedDict):
    """Configuration for a workflow step type."""
    
    execution: Literal["client", "server"]
    queuing: Literal["batch", "blocking", "immediate", "expand"]
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
        "optional_fields": ["parameters", "state_update", "timeout"]
    },
    
    "user_input": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Collect user input",
        "supports_state_update": True,
        "required_fields": ["prompt"],
        "optional_fields": ["instructions", "type", "choices", "validation", "state_update", "default", "max_retries"]
    },
    
    "parallel_foreach": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Execute sub-agents in parallel",
        "supports_state_update": False,
        "required_fields": ["items", "sub_agent_task"],
        "optional_fields": ["max_parallel"]
    },
    
    "agent_shell_command": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Shell command executed by agent",
        "supports_state_update": True,
        "required_fields": ["command"],
        "optional_fields": ["reason", "working_directory", "state_update"]
    },
    
    "internal_mcp_call": {
        "execution": "client",
        "queuing": "blocking",
        "description": "Internal MCP tool call",
        "supports_state_update": True,
        "required_fields": ["tool"],
        "optional_fields": ["parameters", "state_update"]
    },
    
    "conditional_message": {
        "execution": "client",
        "queuing": "batch",
        "description": "Conditional user message",
        "supports_state_update": False,
        "required_fields": ["condition", "message"],
        "optional_fields": ["message_type", "format"]
    },
    
    # Server-executed steps (processed internally)
    "shell_command": {
        "execution": "server",
        "queuing": "immediate",  # Execute immediately server-side
        "description": "Execute shell command on server",
        "supports_state_update": True,  # Via state_update field
        "required_fields": ["command"],
        "optional_fields": ["working_directory", "timeout", "state_update"]
    },
    
    "state_update": {
        "execution": "server",
        "queuing": "immediate",
        "description": "Update workflow state",
        "supports_state_update": False,  # IS the state update
        "required_fields": ["path", "value"],
        "optional_fields": ["operation"]
    },
    
    "batch_state_update": {
        "execution": "server",
        "queuing": "immediate",
        "description": "Multiple state updates at once",
        "supports_state_update": False,
        "required_fields": ["updates"],
        "optional_fields": []
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
        "optional_fields": []
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
    }
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
        
        config = self.get(step_type)
        if not config:
            return False, f"Unknown step type: {step_type}"
        
        # Check required fields
        for field in config["required_fields"]:
            if field not in step:
                return False, f"Step type '{step_type}' missing required field: {field}"
        
        # Check for unknown fields
        allowed_fields = {"id", "type"} | set(config["required_fields"]) | set(config["optional_fields"])
        for field in step:
            if field not in allowed_fields:
                return False, f"Step type '{step_type}' has unknown field: {field}"
        
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