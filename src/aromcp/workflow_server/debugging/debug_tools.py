"""Debug tools for the MCP Workflow System."""

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExecutionCheckpoint:
    """Checkpoint for debugging execution state."""
    
    workflow_id: str
    step_id: str
    checkpoint_id: str
    timestamp: datetime
    state_before: dict[str, Any]
    state_after: Optional[dict[str, Any]] = None
    step_config: dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None
    error: Optional[str] = None


@dataclass
class DebugBreakpoint:
    """Breakpoint configuration for debugging."""
    
    id: str
    workflow_id: Optional[str] = None
    step_id: Optional[str] = None
    step_type: Optional[str] = None
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0
    max_hits: Optional[int] = None


class DebugManager:
    """Manages debugging features for workflow execution."""
    
    def __init__(self):
        """Initialize debug manager."""
        self._lock = threading.RLock()
        
        # Debug mode settings
        self._debug_mode_enabled = False
        self._serial_mode_enabled = False
        self._step_through_enabled = False
        
        # Checkpoints
        self._checkpoints: dict[str, ExecutionCheckpoint] = {}
        self._checkpoint_history: deque = deque(maxlen=100)
        
        # Breakpoints
        self._breakpoints: dict[str, DebugBreakpoint] = {}
        self._breakpoint_hit_callback = None
        
        # State inspection
        self._state_snapshots: dict[str, dict[str, Any]] = {}
        self._state_diff_enabled = True
        
        # Execution trace
        self._execution_trace: deque = deque(maxlen=1000)
        self._trace_enabled = False
    
    def enable_debug_mode(self, enabled: bool):
        """Enable or disable debug mode."""
        with self._lock:
            self._debug_mode_enabled = enabled
            logger.info(f"Debug mode {'enabled' if enabled else 'disabled'}")
    
    def set_debug_mode(self, enabled: bool):
        """Set debug mode enabled/disabled (alias for enable_debug_mode)."""
        self.enable_debug_mode(enabled)
    
    def enable_serial_mode(self, enabled: bool):
        """Enable or disable serial execution mode."""
        with self._lock:
            self._serial_mode_enabled = enabled
            logger.info(f"Serial mode {'enabled' if enabled else 'disabled'}")
    
    def enable_step_through(self, enabled: bool):
        """Enable or disable step-through debugging."""
        with self._lock:
            self._step_through_enabled = enabled
            logger.info(f"Step-through mode {'enabled' if enabled else 'disabled'}")
    
    def is_debug_mode_enabled(self) -> bool:
        """Check if debug mode is enabled."""
        return self._debug_mode_enabled
    
    def is_serial_mode_enabled(self) -> bool:
        """Check if serial mode is enabled."""
        return self._serial_mode_enabled
    
    def create_checkpoint(self, workflow_id: str, step_id: str, state_before: dict[str, Any],
                         step_config: dict[str, Any]) -> str:
        """Create an execution checkpoint."""
        with self._lock:
            checkpoint_id = f"cp_{workflow_id}_{step_id}_{int(time.time() * 1000)}"
            
            checkpoint = ExecutionCheckpoint(
                workflow_id=workflow_id,
                step_id=step_id,
                checkpoint_id=checkpoint_id,
                timestamp=datetime.now(),
                state_before=self._deep_copy_state(state_before),
                step_config=step_config.copy()
            )
            
            self._checkpoints[checkpoint_id] = checkpoint
            self._checkpoint_history.append(checkpoint_id)
            
            if self._trace_enabled:
                self._add_trace_event("checkpoint_created", {
                    "checkpoint_id": checkpoint_id,
                    "workflow_id": workflow_id,
                    "step_id": step_id
                })
            
            return checkpoint_id
    
    def complete_checkpoint(self, checkpoint_id: str, state_after: dict[str, Any],
                          execution_time: float, error: Optional[str] = None):
        """Complete a checkpoint with final state."""
        with self._lock:
            if checkpoint_id not in self._checkpoints:
                return
            
            checkpoint = self._checkpoints[checkpoint_id]
            checkpoint.state_after = self._deep_copy_state(state_after)
            checkpoint.execution_time = execution_time
            checkpoint.error = error
            
            if self._trace_enabled:
                self._add_trace_event("checkpoint_completed", {
                    "checkpoint_id": checkpoint_id,
                    "execution_time": execution_time,
                    "error": error
                })
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[ExecutionCheckpoint]:
        """Get a specific checkpoint."""
        with self._lock:
            return self._checkpoints.get(checkpoint_id)
    
    def get_checkpoint_history(self, workflow_id: Optional[str] = None) -> list[ExecutionCheckpoint]:
        """Get checkpoint history, optionally filtered by workflow."""
        with self._lock:
            checkpoints = [self._checkpoints[cp_id] for cp_id in self._checkpoint_history 
                          if cp_id in self._checkpoints]
            
            if workflow_id:
                checkpoints = [cp for cp in checkpoints if cp.workflow_id == workflow_id]
            
            return checkpoints
    
    def create_breakpoint(self, id: str, workflow_id: Optional[str] = None,
                         step_id: Optional[str] = None, step_type: Optional[str] = None,
                         condition: Optional[str] = None, max_hits: Optional[int] = None) -> DebugBreakpoint:
        """Create a debug breakpoint."""
        with self._lock:
            breakpoint = DebugBreakpoint(
                id=id,
                workflow_id=workflow_id,
                step_id=step_id,
                step_type=step_type,
                condition=condition,
                max_hits=max_hits
            )
            
            self._breakpoints[id] = breakpoint
            
            if self._trace_enabled:
                self._add_trace_event("breakpoint_created", {
                    "breakpoint_id": id,
                    "workflow_id": workflow_id,
                    "step_id": step_id,
                    "step_type": step_type
                })
            
            return breakpoint
    
    def remove_breakpoint(self, id: str) -> bool:
        """Remove a breakpoint."""
        with self._lock:
            if id in self._breakpoints:
                del self._breakpoints[id]
                
                if self._trace_enabled:
                    self._add_trace_event("breakpoint_removed", {"breakpoint_id": id})
                
                return True
            return False
    
    def check_breakpoint(self, workflow_id: str, step_id: str, step_type: str,
                        state: dict[str, Any]) -> Optional[DebugBreakpoint]:
        """Check if execution should break at this point."""
        with self._lock:
            for breakpoint in self._breakpoints.values():
                if not breakpoint.enabled:
                    continue
                
                # Check if breakpoint matches
                if breakpoint.workflow_id and breakpoint.workflow_id != workflow_id:
                    continue
                if breakpoint.step_id and breakpoint.step_id != step_id:
                    continue
                if breakpoint.step_type and breakpoint.step_type != step_type:
                    continue
                
                # Check condition if specified
                if breakpoint.condition:
                    try:
                        # Simple condition evaluation (in real implementation, use safe eval)
                        if not self._evaluate_condition(breakpoint.condition, state):
                            continue
                    except Exception as e:
                        logger.warning(f"Failed to evaluate breakpoint condition: {e}")
                        continue
                
                # Check hit count
                breakpoint.hit_count += 1
                if breakpoint.max_hits and breakpoint.hit_count > breakpoint.max_hits:
                    breakpoint.enabled = False
                    continue
                
                # Breakpoint hit
                if self._breakpoint_hit_callback:
                    self._breakpoint_hit_callback(breakpoint, workflow_id, step_id, state)
                
                if self._trace_enabled:
                    self._add_trace_event("breakpoint_hit", {
                        "breakpoint_id": breakpoint.id,
                        "workflow_id": workflow_id,
                        "step_id": step_id,
                        "hit_count": breakpoint.hit_count
                    })
                
                return breakpoint
            
            return None
    
    def set_breakpoint_callback(self, callback):
        """Set callback for breakpoint hits."""
        self._breakpoint_hit_callback = callback
    
    def take_state_snapshot(self, snapshot_id: str, state: dict[str, Any]):
        """Take a snapshot of the current state."""
        with self._lock:
            self._state_snapshots[snapshot_id] = self._deep_copy_state(state)
            
            if self._trace_enabled:
                self._add_trace_event("state_snapshot", {"snapshot_id": snapshot_id})
    
    def get_state_snapshot(self, snapshot_id: str) -> Optional[dict[str, Any]]:
        """Get a state snapshot."""
        with self._lock:
            return self._state_snapshots.get(snapshot_id)
    
    def compare_states(self, state1_id: str, state2_id: str) -> dict[str, Any]:
        """Compare two state snapshots."""
        with self._lock:
            state1 = self._state_snapshots.get(state1_id)
            state2 = self._state_snapshots.get(state2_id)
            
            if not state1 or not state2:
                return {"error": "State snapshot not found"}
            
            return self._compute_state_diff(state1, state2)
    
    def inspect_state(self, workflow_id: str, path: Optional[str] = None) -> dict[str, Any]:
        """Inspect current workflow state."""
        # This would need access to the state manager in real implementation
        # For now, return a placeholder
        return {
            "workflow_id": workflow_id,
            "path": path,
            "value": "State inspection requires state manager integration"
        }
    
    def enable_execution_trace(self, enabled: bool):
        """Enable or disable execution tracing."""
        with self._lock:
            self._trace_enabled = enabled
    
    def get_execution_trace(self, limit: Optional[int] = None) -> list[dict[str, Any]]:
        """Get execution trace events."""
        with self._lock:
            trace = list(self._execution_trace)
            if limit:
                trace = trace[-limit:]
            return trace
    
    def clear_debug_data(self):
        """Clear all debug data."""
        with self._lock:
            self._checkpoints.clear()
            self._checkpoint_history.clear()
            self._breakpoints.clear()
            self._state_snapshots.clear()
            self._execution_trace.clear()
    
    def get_debug_summary(self) -> dict[str, Any]:
        """Get summary of debug information."""
        with self._lock:
            return {
                "debug_mode_enabled": self._debug_mode_enabled,
                "serial_mode_enabled": self._serial_mode_enabled,
                "step_through_enabled": self._step_through_enabled,
                "checkpoint_count": len(self._checkpoints),
                "breakpoint_count": len(self._breakpoints),
                "active_breakpoints": sum(1 for bp in self._breakpoints.values() if bp.enabled),
                "snapshot_count": len(self._state_snapshots),
                "trace_event_count": len(self._execution_trace),
                "trace_enabled": self._trace_enabled
            }
    
    def _deep_copy_state(self, state: dict[str, Any]) -> dict[str, Any]:
        """Create a deep copy of state for debugging."""
        try:
            return json.loads(json.dumps(state, default=str))
        except Exception:
            # Fallback to simple copy if JSON serialization fails
            return state.copy()
    
    def _evaluate_condition(self, condition: str, state: dict[str, Any]) -> bool:
        """Evaluate a simple condition against state."""
        # This is a simplified implementation
        # In production, use a safe expression evaluator
        
        # Support simple equality checks like "state.counter == 5"
        if "==" in condition:
            parts = condition.split("==")
            if len(parts) == 2:
                path = parts[0].strip()
                expected = parts[1].strip()
                
                # Extract value from state
                value = self._get_value_by_path(state, path)
                
                # Simple comparison
                try:
                    return str(value) == expected.strip('"\'')
                except Exception:
                    return False
        
        # Default to false for unsupported conditions
        return False
    
    def _get_value_by_path(self, data: dict[str, Any], path: str) -> Any:
        """Get value from nested dict by dot-separated path."""
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    
    def _compute_state_diff(self, state1: dict[str, Any], state2: dict[str, Any]) -> dict[str, Any]:
        """Compute difference between two states."""
        diff = {
            "added": {},
            "removed": {},
            "modified": {}
        }
        
        # Find added and modified keys
        for key, value in state2.items():
            if key not in state1:
                diff["added"][key] = value
            elif state1[key] != value:
                diff["modified"][key] = {
                    "old": state1[key],
                    "new": value
                }
        
        # Find removed keys
        for key in state1:
            if key not in state2:
                diff["removed"][key] = state1[key]
        
        return diff
    
    def add_checkpoint(self, workflow_id: str, step_id: str, state_before: dict[str, Any], step_config: dict[str, Any] = None) -> str:
        """Add checkpoint for workflow step (alias for create_checkpoint)."""
        if step_config is None:
            step_config = {}
        return self.create_checkpoint(workflow_id, step_id, state_before, step_config)
    
    def update_checkpoint(self, checkpoint_id: str, state_after: dict[str, Any]) -> None:
        """Update checkpoint with state after execution."""
        self.complete_checkpoint(checkpoint_id, state_after, 0.0)
    
    def get_workflow_checkpoints(self, workflow_id: str) -> list[ExecutionCheckpoint]:
        """Get checkpoints for specific workflow."""
        return self.get_checkpoint_history(workflow_id)
    
    def track_execution_flow(self, workflow_id: str, step_id: str, data: dict[str, Any]) -> None:
        """Track execution flow for debugging."""
        if self._trace_enabled:
            self._add_trace_event("execution_flow", {
                "workflow_id": workflow_id,
                "step_id": step_id,
                "data": data
            })
    
    def _add_trace_event(self, event_type: str, data: dict[str, Any]):
        """Add an event to the execution trace."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": data
        }
        self._execution_trace.append(event)