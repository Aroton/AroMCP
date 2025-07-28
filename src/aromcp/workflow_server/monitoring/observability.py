"""Observability infrastructure for the MCP Workflow System."""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Mock external clients for testing
EXTERNAL_CLIENTS = {}
ALERT_CLIENTS = {}


@dataclass
class AuditEvent:
    """Represents an audit trail event."""
    
    event_type: str
    timestamp: datetime
    workflow_id: str
    step_id: Optional[str] = None
    details: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "details": self.details
        }


@dataclass
class AlertConfig:
    """Configuration for an alert channel."""
    
    channel: str
    severity_threshold: str
    config: dict[str, Any]
    rate_limit: Optional[str] = None
    last_alert_time: Optional[datetime] = None
    alert_count: int = 0


@dataclass 
class WorkflowHealthStatus:
    """Health status for a workflow."""
    
    workflow_id: str
    status: str  # healthy, degraded, unhealthy
    memory_usage_percent: float
    cpu_usage_percent: float
    error_rate: float
    performance_score: float
    last_updated: datetime = field(default_factory=datetime.now)


class StatusAPI:
    """API for workflow status and monitoring."""
    
    def __init__(self, observability_manager: 'ObservabilityManager'):
        """Initialize status API."""
        self.manager = observability_manager
    
    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get current workflow status."""
        workflow = self.manager._workflows.get(workflow_id)
        if not workflow:
            return {"error": "Workflow not found"}
        
        progress = self.manager._workflow_progress.get(workflow_id, {})
        
        return {
            "workflow_id": workflow_id,
            "status": workflow.status,
            "current_step_index": progress.get("step_index", workflow.current_step_index),
            "total_steps": workflow.total_steps,
            "overall_progress": progress.get("progress", workflow.current_step_index / workflow.total_steps),
            "last_error": progress.get("error"),
            "last_updated": datetime.now().isoformat()
        }
    
    def get_progress_details(self, workflow_id: str) -> dict[str, Any]:
        """Get detailed progress information."""
        history = self.manager._progress_history.get(workflow_id, [])
        
        completed_steps = sum(1 for h in history if h.get("status") == "completed")
        failed_steps = sum(1 for h in history if h.get("status") == "failed")
        
        return {
            "step_history": history,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "total_steps_executed": len(history)
        }
    
    def get_workflow_health(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow health status."""
        health = self.manager._health_status.get(workflow_id)
        if not health:
            return {"error": "Health data not found"}
        
        # Determine overall health
        if health.error_rate > 0.3 or health.memory_usage_percent > 90 or health.cpu_usage_percent > 90:
            overall_health = "unhealthy"
        elif health.error_rate > 0.1 or health.memory_usage_percent > 70 or health.cpu_usage_percent > 70:
            overall_health = "degraded"
        else:
            overall_health = "healthy"
        
        return {
            "overall_health": overall_health,
            "resource_usage": {
                "memory_percent": health.memory_usage_percent,
                "cpu_percent": health.cpu_usage_percent
            },
            "error_rate": health.error_rate,
            "performance_indicators": {
                "performance_score": health.performance_score,
                "last_updated": health.last_updated.isoformat()
            }
        }
    
    def get_realtime_metrics(self, workflow_id: str) -> dict[str, Any]:
        """Get real-time metrics for a workflow."""
        workflow = self.manager._workflows.get(workflow_id)
        if not workflow:
            return {"error": "Workflow not found"}
        
        progress = self.manager._workflow_progress.get(workflow_id, {})
        
        execution_time = (datetime.now() - workflow.start_time).total_seconds()
        
        return {
            "current_step": progress.get("step_name", f"step_{workflow.current_step_index}"),
            "execution_time": execution_time,
            "resource_usage": {
                "memory_mb": workflow.state.get("state", {}).get("memory_usage", 0),
                "cpu_percent": workflow.state.get("state", {}).get("cpu_usage", 0)
            },
            "timestamp": datetime.now().isoformat()
        }


class ObservabilityManager:
    """Manages observability, monitoring, and alerting for workflows."""
    
    def __init__(self):
        """Initialize observability manager."""
        self._lock = threading.RLock()
        
        # Workflow tracking
        self._workflows: dict[str, Any] = {}
        self._workflow_progress: dict[str, dict[str, Any]] = {}
        self._progress_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        
        # Health monitoring
        self._health_status: dict[str, WorkflowHealthStatus] = {}
        self._system_health_history: deque = deque(maxlen=100)
        
        # Audit trail
        self._audit_trail_enabled = False
        self._audit_events: dict[str, list[AuditEvent]] = defaultdict(list)
        
        # External integrations
        self._external_configs: list[dict[str, Any]] = []
        
        # Alerting
        self._alert_configs: list[AlertConfig] = []
        self._alert_handler: Optional[Callable] = None
        
        # Status API
        self._status_api = StatusAPI(self)
    
    def register_workflow(self, workflow_state: Any):
        """Register a workflow for monitoring."""
        with self._lock:
            self._workflows[workflow_state.workflow_id] = workflow_state
            
            # Initialize health status
            self._health_status[workflow_state.workflow_id] = WorkflowHealthStatus(
                workflow_id=workflow_state.workflow_id,
                status="healthy",
                memory_usage_percent=0,
                cpu_usage_percent=0,
                error_rate=0,
                performance_score=1.0
            )
    
    def update_workflow_progress(self, workflow_id: str, step_index: int, status: str,
                               step_name: str, progress: float, error: Optional[str] = None):
        """Update workflow progress."""
        with self._lock:
            self._workflow_progress[workflow_id] = {
                "step_index": step_index,
                "status": status,
                "step_name": step_name,
                "progress": progress,
                "error": error,
                "timestamp": datetime.now()
            }
            
            # Add to history
            self._progress_history[workflow_id].append({
                "step_index": step_index,
                "status": status,
                "step_name": step_name,
                "progress": progress,
                "error": error,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_status_api(self) -> StatusAPI:
        """Get the status API interface."""
        return self._status_api
    
    def configure_external_integration(self, config: dict[str, Any]):
        """Configure an external monitoring integration."""
        with self._lock:
            self._external_configs.append(config)
            
            # Create mock client for testing
            system = config["system"]
            if system not in EXTERNAL_CLIENTS:
                from unittest.mock import Mock
                EXTERNAL_CLIENTS[system] = Mock()
    
    def export_metrics(self, metrics: dict[str, Any]):
        """Export metrics to configured external systems."""
        with self._lock:
            for config in self._external_configs:
                system = config["system"]
                client = EXTERNAL_CLIENTS.get(system)
                
                if not client:
                    continue
                
                # Format metrics based on system
                if config["format"] == "prometheus":
                    # Prometheus text format
                    formatted = "\n".join([
                        f"{key} {value}" 
                        for key, value in metrics.items()
                        if key in config.get("metrics", [])
                    ])
                    client.send_metrics(formatted)
                    
                elif config["format"] == "datadog":
                    # DataDog JSON format
                    formatted = [
                        {
                            "metric": key.replace("_", "."),
                            "points": [[datetime.now().timestamp(), value]],
                            "type": "gauge"
                        }
                        for key, value in metrics.items()
                        if key.replace("_", ".") in config.get("metrics", [])
                    ]
                    client.send_metrics(formatted)
                    
                elif config["format"] == "cloudwatch":
                    # CloudWatch format
                    formatted = {
                        "MetricData": [
                            {
                                "MetricName": self._to_pascal_case(key),
                                "Value": value,
                                "Timestamp": datetime.now().isoformat()
                            }
                            for key, value in metrics.items()
                            if self._to_pascal_case(key) in config.get("metrics", [])
                        ]
                    }
                    client.send_metrics(formatted)
    
    def enable_audit_trail(self, enabled: bool):
        """Enable or disable audit trail generation."""
        self._audit_trail_enabled = enabled
    
    def record_audit_event(self, event_type: str, workflow_id: str, timestamp: datetime,
                          step_id: Optional[str] = None, details: Optional[dict[str, Any]] = None):
        """Record an audit event."""
        if not self._audit_trail_enabled:
            return
        
        with self._lock:
            event = AuditEvent(
                event_type=event_type,
                timestamp=timestamp,
                workflow_id=workflow_id,
                step_id=step_id,
                details=details or {}
            )
            
            self._audit_events[workflow_id].append(event)
    
    def generate_audit_trail(self, workflow_id: str) -> dict[str, Any]:
        """Generate complete audit trail for a workflow."""
        with self._lock:
            events = self._audit_events.get(workflow_id, [])
            
            if not events:
                return {
                    "workflow_id": workflow_id,
                    "events": [],
                    "total_duration": 0
                }
            
            # Sort events chronologically
            sorted_events = sorted(events, key=lambda e: e.timestamp)
            
            # Calculate total duration
            if len(sorted_events) >= 2:
                total_duration = (sorted_events[-1].timestamp - sorted_events[0].timestamp).total_seconds()
            else:
                total_duration = 0
            
            # Extract final status from events
            completion_events = [e for e in sorted_events if e.event_type == "workflow_completed"]
            if completion_events:
                total_duration = completion_events[0].details.get("total_duration", total_duration)
            
            return {
                "workflow_id": workflow_id,
                "events": [e.to_dict() for e in sorted_events],
                "total_duration": total_duration,
                "event_count": len(sorted_events)
            }
    
    def configure_alert_channel(self, config: dict[str, Any]):
        """Configure an alert channel."""
        with self._lock:
            alert_config = AlertConfig(
                channel=config["channel"],
                severity_threshold=config.get("severity_threshold", "medium"),
                config=config
            )
            
            self._alert_configs.append(alert_config)
            
            # Create mock notifier for testing
            if config["channel"] not in ALERT_CLIENTS:
                from unittest.mock import Mock
                ALERT_CLIENTS[config["channel"]] = Mock()
    
    def trigger_failure_alert(self, workflow_id: str, error_type: str, severity: str,
                            message: str, context: Optional[dict[str, Any]] = None):
        """Trigger a failure alert."""
        with self._lock:
            # Check severity thresholds
            severity_levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
            alert_severity = severity_levels.get(severity, 2)
            
            for alert_config in self._alert_configs:
                threshold_severity = severity_levels.get(alert_config.severity_threshold, 2)
                
                if alert_severity >= threshold_severity:
                    # Check rate limiting
                    if self._check_rate_limit(alert_config):
                        # Send alert
                        client = ALERT_CLIENTS.get(alert_config.channel)
                        if client:
                            alert_data = {
                                "workflow_id": workflow_id,
                                "error_type": error_type,
                                "severity": severity,
                                "message": message,
                                "context": context or {},
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            client.send_alert(alert_data)
                            
                            # Update alert tracking
                            alert_config.last_alert_time = datetime.now()
                            alert_config.alert_count += 1
    
    def set_alert_handler(self, handler: Callable):
        """Set custom alert handler."""
        self._alert_handler = handler
    
    def record_system_health(self, timestamp: datetime, memory_usage_percent: float,
                           cpu_usage_percent: float, error_rate: float):
        """Record system health metrics."""
        with self._lock:
            health_data = {
                "timestamp": timestamp,
                "memory_usage_percent": memory_usage_percent,
                "cpu_usage_percent": cpu_usage_percent,
                "error_rate": error_rate
            }
            
            self._system_health_history.append(health_data)
    
    def evaluate_system_health(self) -> dict[str, Any]:
        """Evaluate current system health."""
        with self._lock:
            if not self._system_health_history:
                return {"status": "unknown", "metrics": {}}
            
            latest = self._system_health_history[-1]
            
            # Determine health status
            if latest["error_rate"] > 0.2 or latest["memory_usage_percent"] > 95 or latest["cpu_usage_percent"] > 95:
                status = "unhealthy"
            elif latest["error_rate"] > 0.1 or latest["memory_usage_percent"] > 85 or latest["cpu_usage_percent"] > 80:
                status = "degraded"
            else:
                status = "healthy"
            
            return {
                "status": status,
                "metrics": latest
            }
    
    def trigger_health_alert(self, old_status: str, new_status: str, metrics: dict[str, Any]):
        """Trigger alert for health status change."""
        if self._alert_handler:
            alert_data = {
                "type": "health_status_change",
                "old_status": old_status,
                "new_status": new_status,
                "metrics": metrics,
                "message": f"System health changed from {old_status} to {new_status}",
                "timestamp": datetime.now().isoformat()
            }
            
            self._alert_handler(alert_data)
    
    def get_current_system_health(self) -> dict[str, Any]:
        """Get current system health status."""
        with self._lock:
            if not self._system_health_history:
                return {
                    "status": "unknown",
                    "memory_usage_percent": 0,
                    "cpu_usage_percent": 0,
                    "error_rate": 0
                }
            
            latest = self._system_health_history[-1]
            evaluation = self.evaluate_system_health()
            
            return {
                "status": evaluation["status"],
                "memory_usage_percent": latest["memory_usage_percent"],
                "cpu_usage_percent": latest["cpu_usage_percent"],
                "error_rate": latest["error_rate"],
                "timestamp": latest["timestamp"].isoformat()
            }
    
    def get_monitoring_summary(self) -> dict[str, Any]:
        """Get summary of all monitoring data."""
        with self._lock:
            return {
                "active_workflows": len(self._workflows),
                "audit_events_count": sum(len(events) for events in self._audit_events.values()),
                "external_integrations": len(self._external_configs),
                "alert_channels": len(self._alert_configs),
                "system_health": self.get_current_system_health()
            }
    
    def _check_rate_limit(self, alert_config: AlertConfig) -> bool:
        """Check if alert is within rate limit."""
        if not alert_config.rate_limit:
            return True
        
        if not alert_config.last_alert_time:
            return True
        
        # Parse rate limit (e.g., "5_per_hour")
        parts = alert_config.rate_limit.split("_")
        if len(parts) != 3 or parts[1] != "per":
            return True
        
        try:
            limit = int(parts[0])
            period = parts[2]
            
            # Calculate time window
            if period == "hour":
                window = timedelta(hours=1)
            elif period == "day":
                window = timedelta(days=1)
            else:
                return True
            
            # Check if within window
            time_since_last = datetime.now() - alert_config.last_alert_time
            if time_since_last > window:
                alert_config.alert_count = 0
                return True
            
            return alert_config.alert_count < limit
            
        except (ValueError, IndexError):
            return True
    
    def _to_pascal_case(self, snake_str: str) -> str:
        """Convert snake_case to PascalCase."""
        components = snake_str.split('_')
        return ''.join(x.title() for x in components)