"""Test adapters for monitoring components to support Phase 2 tests."""

import time
from collections import defaultdict
from typing import Any, Optional


class MetricsCollectorTestAdapter:
    """Test-compatible MetricsCollector for production monitoring tests."""
    
    def __init__(self):
        """Initialize test adapter."""
        self._step_executions = []
        self._step_starts = {}
        self._step_type_metrics = defaultdict(lambda: {
            "count": 0,
            "total_duration": 0,
            "success_count": 0,
            "failure_count": 0,
            "timeout_count": 0
        })
    
    def record_step_execution(self, step_id: str, step_type: str, duration: float,
                            status: str, timestamp: float):
        """Record a step execution."""
        self._step_executions.append({
            "step_id": step_id,
            "step_type": step_type,
            "duration": duration,
            "status": status,
            "timestamp": timestamp
        })
        
        # Update step type metrics
        metrics = self._step_type_metrics[step_type]
        metrics["count"] += 1
        metrics["total_duration"] += duration
        
        if status == "completed":
            metrics["success_count"] += 1
        elif status == "failed":
            metrics["failure_count"] += 1
        elif status == "timeout":
            metrics["timeout_count"] += 1
    
    def record_step_start(self, step_id: str, step_type: str, timestamp: float):
        """Record step start."""
        self._step_starts[step_id] = {
            "step_type": step_type,
            "start_time": timestamp
        }
    
    def record_step_completion(self, step_id: str, duration: float, status: str, timestamp: float):
        """Record step completion."""
        if step_id in self._step_starts:
            step_info = self._step_starts[step_id]
            self.record_step_execution(
                step_id=step_id,
                step_type=step_info["step_type"],
                duration=duration,
                status=status,
                timestamp=timestamp
            )
    
    def get_comprehensive_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics."""
        total_steps = len(self._step_executions)
        completed_steps = sum(1 for s in self._step_executions if s["status"] == "completed")
        failed_steps = sum(1 for s in self._step_executions if s["status"] == "failed")
        timeout_steps = sum(1 for s in self._step_executions if s["status"] == "timeout")
        
        durations = [s["duration"] for s in self._step_executions]
        total_duration = sum(durations)
        
        # Step type breakdown
        step_type_breakdown = {}
        for step_type, metrics in self._step_type_metrics.items():
            if metrics["count"] > 0:
                step_type_breakdown[step_type] = {
                    "count": metrics["count"],
                    "success_rate": metrics["success_count"] / metrics["count"],
                    "average_duration": metrics["total_duration"] / metrics["count"]
                }
        
        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "timeout_steps": timeout_steps,
            "success_rate": completed_steps / total_steps if total_steps > 0 else 0,
            "total_duration": total_duration,
            "average_step_duration": total_duration / total_steps if total_steps > 0 else 0,
            "min_step_duration": min(durations) if durations else 0,
            "max_step_duration": max(durations) if durations else 0,
            "step_type_breakdown": step_type_breakdown,
            "error_patterns": {
                "timeout_rate": timeout_steps / total_steps if total_steps > 0 else 0,
                "failure_rate": failed_steps / total_steps if total_steps > 0 else 0
            }
        }


class HAManagerTestAdapter:
    """Test adapter for High Availability Manager."""
    
    def __init__(self, cluster_size: int = 3, failover_timeout: int = 30):
        """Initialize HA manager."""
        self.cluster_size = cluster_size
        self.failover_timeout = failover_timeout


class ScalingManagerTestAdapter:
    """Test adapter for Scaling Manager."""
    
    def __init__(self, min_instances: int = 2, max_instances: int = 10, scale_threshold: int = 75):
        """Initialize scaling manager."""
        self.min_instances = min_instances
        self.max_instances = max_instances
        self.scale_threshold = scale_threshold
        self._instances = {}
    
    def register_execution_instance(self, instance_id: str, capacity: int, current_load: int,
                                  health_status: str):
        """Register an execution instance."""
        self._instances[instance_id] = {
            "capacity": capacity,
            "current_load": current_load,
            "health_status": health_status
        }


class ConnectionManagerTestAdapter:
    """Test adapter for Connection Manager."""
    
    def __init__(self, database_url: str, pool_size: int = 5):
        """Initialize connection manager."""
        self.database_url = database_url
        self.pool_size = pool_size


class ProductionIntegrationTestAdapter:
    """Test adapter for Production Integration."""
    
    def __init__(self):
        """Initialize production integration."""
        pass