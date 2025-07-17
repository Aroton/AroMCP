"""
State models for MCP Workflow System

Defines the core data structures for the three-tier state model and computed field definitions.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowState:
    """
    Three-tier state model for workflow execution

    - raw: Agent-writable values (direct input from agents)
    - computed: MCP-computed values (derived from transformations)
    - state: Legacy/manual values (backward compatibility)
    """

    raw: dict[str, Any] = field(default_factory=dict)
    computed: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure all tiers are dictionaries"""
        if not isinstance(self.raw, dict):
            self.raw = {}
        if not isinstance(self.computed, dict):
            self.computed = {}
        if not isinstance(self.state, dict):
            self.state = {}


@dataclass
class ComputedFieldDefinition:
    """
    Definition for a computed field in the workflow state

    Computed fields are automatically updated when their dependencies change.
    They use JavaScript expressions for transformations.
    """

    from_paths: list[str]
    """List of dependency paths (e.g., ["raw.value", "state.multiplier"])"""

    transform: str
    """JavaScript expression for transformation (e.g., "input * 2" or "input[0] + input[1]")"""

    on_error: str = "use_fallback"
    """Error handling strategy: "use_fallback", "propagate", or "ignore" """

    fallback: Any = None
    """Default value to use when on_error is "use_fallback" and transformation fails"""

    def __post_init__(self):
        """Validate field definition"""
        if not self.from_paths:
            raise ValueError("from_paths cannot be empty")

        if not self.transform:
            raise ValueError("transform cannot be empty")

        valid_error_strategies = {"use_fallback", "propagate", "ignore"}
        if self.on_error not in valid_error_strategies:
            raise ValueError(f"on_error must be one of {valid_error_strategies}")


@dataclass
class StateSchema:
    """
    Schema defining the structure and computed fields for a workflow state
    """

    raw: dict[str, str] = field(default_factory=dict)
    """Raw field type definitions (for validation)"""

    computed: dict[str, dict[str, Any]] = field(default_factory=dict)
    """Computed field definitions"""

    state: dict[str, str] = field(default_factory=dict)
    """State field type definitions (for validation)"""

    def get_computed_field_definitions(self) -> dict[str, ComputedFieldDefinition]:
        """
        Convert computed field dict to ComputedFieldDefinition objects

        Returns:
            Dictionary mapping field names to ComputedFieldDefinition objects
        """
        definitions = {}
        for field_name, field_config in self.computed.items():
            # Handle both single string and list of strings for from_paths
            from_paths = field_config.get("from", [])
            if isinstance(from_paths, str):
                from_paths = [from_paths]

            definitions[field_name] = ComputedFieldDefinition(
                from_paths=from_paths,
                transform=field_config.get("transform", "input"),
                on_error=field_config.get("on_error", "use_fallback"),
                fallback=field_config.get("fallback", None),
            )

        return definitions


@dataclass
class StateUpdate:
    """Represents a single state update operation."""

    path: str
    """State path to update (e.g., "raw.counter", "state.version")"""

    value: Any
    """Value to set at the path"""

    operation: str = "set"
    """Update operation: "set", "increment", "append", "delete" """


# Exception classes for state management
class StateError(Exception):
    """Base exception for state management errors"""

    pass


class InvalidPathError(StateError):
    """Raised when an invalid state path is accessed"""

    pass


class ComputedFieldError(StateError):
    """Raised when computed field evaluation fails"""

    pass


class CircularDependencyError(StateError):
    """Raised when circular dependencies are detected in computed fields"""

    pass
