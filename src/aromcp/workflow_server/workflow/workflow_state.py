"""Workflow state model for the MCP Workflow System."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowState:
    """
    State for a workflow execution instance.
    
    This is different from the three-tier state model (inputs/state/computed).
    This represents the overall workflow execution state.
    """
    
    workflow_id: str
    status: str  # running, completed, failed, paused, recovering
    current_step_index: int
    total_steps: int
    state: dict[str, Any]  # The three-tier state (inputs/state/computed)
    execution_context: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Ensure state is properly initialized."""
        if not isinstance(self.state, dict):
            self.state = {"inputs": {}, "state": {}, "computed": {}}
        
        # Ensure three-tier structure exists in state
        if "inputs" not in self.state:
            self.state["inputs"] = {}
        if "state" not in self.state:
            self.state["state"] = {}
        if "computed" not in self.state:
            self.state["computed"] = {}
            
        if not isinstance(self.execution_context, dict):
            self.execution_context = {}