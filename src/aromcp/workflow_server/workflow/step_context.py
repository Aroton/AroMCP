"""Step execution context for the MCP Workflow System."""

from dataclasses import dataclass
from typing import Any


@dataclass
class StepContext:
    """Context for step execution."""
    
    workflow_id: str
    step_id: str
    state_manager: Any  # StateManager instance
    workflow_config: dict[str, Any]
    
    def __post_init__(self):
        """Ensure proper initialization."""
        if not isinstance(self.workflow_config, dict):
            self.workflow_config = {}