"""Core metrics models for the MCP Workflow System."""

import logging
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class WorkflowMetrics:
    """Metrics for workflow execution."""

    workflow_id: str
    workflow_name: str
    start_time: datetime
    end_time: datetime | None = None
    status: str = "running"  # running, completed, failed, paused

    # Step metrics
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0

    # Timing metrics
    total_duration_ms: float | None = None
    avg_step_duration_ms: float | None = None
    max_step_duration_ms: float | None = None

    # Resource metrics
    peak_memory_mb: float = 0.0
    avg_cpu_percent: float = 0.0

    # Error metrics
    error_count: int = 0
    retry_count: int = 0

    # State metrics
    state_size_kb: float = 0.0
    transformation_count: int = 0

    def calculate_duration(self) -> float | None:
        """Calculate total duration in milliseconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    def calculate_completion_rate(self) -> float:
        """Calculate completion rate as percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "total_duration_ms": self.calculate_duration(),
            "avg_step_duration_ms": self.avg_step_duration_ms,
            "max_step_duration_ms": self.max_step_duration_ms,
            "peak_memory_mb": self.peak_memory_mb,
            "avg_cpu_percent": self.avg_cpu_percent,
            "error_count": self.error_count,
            "retry_count": self.retry_count,
            "state_size_kb": self.state_size_kb,
            "transformation_count": self.transformation_count,
            "completion_rate": self.calculate_completion_rate(),
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""

    operation_name: str
    timestamp: datetime
    duration_ms: float
    success: bool

    # Context information
    workflow_id: str | None = None
    step_id: str | None = None
    operation_type: str | None = None

    # Resource usage
    memory_delta_mb: float | None = None
    cpu_percent: float | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation_name": self.operation_name,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "success": self.success,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "operation_type": self.operation_type,
            "memory_delta_mb": self.memory_delta_mb,
            "cpu_percent": self.cpu_percent,
            "metadata": self.metadata,
        }


@dataclass
class ResourceMetrics:
    """System resource usage metrics."""

    timestamp: datetime

    # Memory metrics
    memory_total_mb: float
    memory_used_mb: float
    memory_available_mb: float
    memory_percent: float

    # CPU metrics
    cpu_percent: float
    cpu_count: int

    # Process-specific metrics
    process_memory_mb: float
    process_cpu_percent: float
    process_threads: int

    # Workflow-specific metrics
    active_workflows: int = 0
    total_workflows: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "memory_total_mb": self.memory_total_mb,
            "memory_used_mb": self.memory_used_mb,
            "memory_available_mb": self.memory_available_mb,
            "memory_percent": self.memory_percent,
            "cpu_percent": self.cpu_percent,
            "cpu_count": self.cpu_count,
            "process_memory_mb": self.process_memory_mb,
            "process_cpu_percent": self.process_cpu_percent,
            "process_threads": self.process_threads,
            "active_workflows": self.active_workflows,
            "total_workflows": self.total_workflows,
        }


class MetricsCollector:
    """Central collector for all workflow metrics."""

    def __init__(self, max_metrics_per_type: int = 1000):
        self.max_metrics_per_type = max_metrics_per_type
        self._lock = threading.RLock()

        # Metric storage
        self._workflow_metrics: dict[str, WorkflowMetrics] = {}
        self._performance_metrics: deque = deque(maxlen=max_metrics_per_type)
        self._resource_metrics: deque = deque(maxlen=max_metrics_per_type)

        # Aggregated metrics
        self._hourly_aggregates: dict[str, dict[str, Any]] = defaultdict(dict)
        self._daily_aggregates: dict[str, dict[str, Any]] = defaultdict(dict)

        # Process information
        self._process = psutil.Process(os.getpid())
        self._start_time = datetime.now()

        # Resource monitoring
        self._resource_monitor_active = False
        self._resource_monitor_thread = None

    def start_workflow_metrics(self, workflow_id: str, workflow_name: str) -> WorkflowMetrics:
        """Start tracking metrics for a workflow."""
        with self._lock:
            metrics = WorkflowMetrics(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                start_time=datetime.now(),
            )
            self._workflow_metrics[workflow_id] = metrics
            return metrics

    def update_workflow_metrics(self, workflow_id: str, **updates):
        """Update workflow metrics."""
        with self._lock:
            if workflow_id in self._workflow_metrics:
                metrics = self._workflow_metrics[workflow_id]
                for key, value in updates.items():
                    if hasattr(metrics, key):
                        setattr(metrics, key, value)

    def complete_workflow_metrics(self, workflow_id: str, status: str = "completed"):
        """Complete workflow metrics tracking."""
        with self._lock:
            if workflow_id in self._workflow_metrics:
                metrics = self._workflow_metrics[workflow_id]
                metrics.end_time = datetime.now()
                metrics.status = status
                metrics.total_duration_ms = metrics.calculate_duration()

    def record_performance_metric(self, metric: PerformanceMetrics):
        """Record a performance metric."""
        with self._lock:
            self._performance_metrics.append(metric)
            self._update_aggregates(metric)

    def record_resource_metrics(self, metric: ResourceMetrics):
        """Record resource usage metrics."""
        with self._lock:
            self._resource_metrics.append(metric)

    def get_workflow_metrics(self, workflow_id: str) -> WorkflowMetrics | None:
        """Get metrics for a specific workflow."""
        with self._lock:
            return self._workflow_metrics.get(workflow_id)

    def get_all_workflow_metrics(self) -> dict[str, WorkflowMetrics]:
        """Get all workflow metrics."""
        with self._lock:
            return self._workflow_metrics.copy()

    def get_performance_metrics(self, limit: int | None = None) -> list[PerformanceMetrics]:
        """Get performance metrics."""
        with self._lock:
            metrics = list(self._performance_metrics)
            if limit:
                return metrics[-limit:]
            return metrics

    def get_resource_metrics(self, limit: int | None = None) -> list[ResourceMetrics]:
        """Get resource metrics."""
        with self._lock:
            metrics = list(self._resource_metrics)
            if limit:
                return metrics[-limit:]
            return metrics

    def get_current_resource_usage(self) -> ResourceMetrics:
        """Get current system resource usage."""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent()

        process_memory = self._process.memory_info().rss / 1024 / 1024  # MB
        process_cpu = self._process.cpu_percent()
        process_threads = self._process.num_threads()

        return ResourceMetrics(
            timestamp=datetime.now(),
            memory_total_mb=memory.total / 1024 / 1024,
            memory_used_mb=memory.used / 1024 / 1024,
            memory_available_mb=memory.available / 1024 / 1024,
            memory_percent=memory.percent,
            cpu_percent=cpu_percent,
            cpu_count=psutil.cpu_count(),
            process_memory_mb=process_memory,
            process_cpu_percent=process_cpu,
            process_threads=process_threads,
            active_workflows=len([m for m in self._workflow_metrics.values() if m.status == "running"]),
            total_workflows=len(self._workflow_metrics),
        )

    def start_resource_monitoring(self, interval_seconds: int = 30):
        """Start continuous resource monitoring."""
        if self._resource_monitor_active:
            return

        self._resource_monitor_active = True

        def monitor_resources():
            while self._resource_monitor_active:
                try:
                    resource_metrics = self.get_current_resource_usage()
                    self.record_resource_metrics(resource_metrics)
                    time.sleep(interval_seconds)
                except Exception as e:
                    logger.error(f"Error in resource monitoring: {e}")
                    time.sleep(interval_seconds)

        self._resource_monitor_thread = threading.Thread(
            target=monitor_resources,
            daemon=True
        )
        self._resource_monitor_thread.start()

    def stop_resource_monitoring(self):
        """Stop continuous resource monitoring."""
        self._resource_monitor_active = False
        if self._resource_monitor_thread:
            self._resource_monitor_thread.join(timeout=5.0)

    def _update_aggregates(self, metric: PerformanceMetrics):
        """Update hourly and daily aggregates."""
        hour_key = metric.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
        day_key = metric.timestamp.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        # Update hourly aggregates
        if hour_key not in self._hourly_aggregates:
            self._hourly_aggregates[hour_key] = {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "total_duration_ms": 0,
                "max_duration_ms": 0,
                "min_duration_ms": float('inf'),
            }

        hourly = self._hourly_aggregates[hour_key]
        hourly["total_operations"] += 1
        if metric.success:
            hourly["successful_operations"] += 1
        else:
            hourly["failed_operations"] += 1

        hourly["total_duration_ms"] += metric.duration_ms
        hourly["max_duration_ms"] = max(hourly["max_duration_ms"], metric.duration_ms)
        hourly["min_duration_ms"] = min(hourly["min_duration_ms"], metric.duration_ms)

        # Update daily aggregates similarly
        if day_key not in self._daily_aggregates:
            self._daily_aggregates[day_key] = {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "total_duration_ms": 0,
                "max_duration_ms": 0,
                "min_duration_ms": float('inf'),
            }

        daily = self._daily_aggregates[day_key]
        daily["total_operations"] += 1
        if metric.success:
            daily["successful_operations"] += 1
        else:
            daily["failed_operations"] += 1

        daily["total_duration_ms"] += metric.duration_ms
        daily["max_duration_ms"] = max(daily["max_duration_ms"], metric.duration_ms)
        daily["min_duration_ms"] = min(daily["min_duration_ms"], metric.duration_ms)

    def get_summary_statistics(self) -> dict[str, Any]:
        """Get summary statistics across all metrics."""
        with self._lock:
            now = datetime.now()

            # Workflow statistics
            workflow_stats = {
                "total_workflows": len(self._workflow_metrics),
                "active_workflows": len([m for m in self._workflow_metrics.values() if m.status == "running"]),
                "completed_workflows": len([m for m in self._workflow_metrics.values() if m.status == "completed"]),
                "failed_workflows": len([m for m in self._workflow_metrics.values() if m.status == "failed"]),
            }

            # Performance statistics
            recent_performance = [
                m for m in self._performance_metrics
                if (now - m.timestamp).total_seconds() < 3600  # Last hour
            ]

            perf_stats = {
                "total_operations_hour": len(recent_performance),
                "successful_operations_hour": len([m for m in recent_performance if m.success]),
                "failed_operations_hour": len([m for m in recent_performance if not m.success]),
            }

            if recent_performance:
                durations = [m.duration_ms for m in recent_performance]
                perf_stats.update({
                    "avg_duration_ms": sum(durations) / len(durations),
                    "max_duration_ms": max(durations),
                    "min_duration_ms": min(durations),
                })

            # Current resource usage
            current_resources = self.get_current_resource_usage()

            return {
                "timestamp": now.isoformat(),
                "uptime_seconds": (now - self._start_time).total_seconds(),
                "workflows": workflow_stats,
                "performance": perf_stats,
                "resources": current_resources.to_dict(),
                "aggregates": {
                    "hourly_periods": len(self._hourly_aggregates),
                    "daily_periods": len(self._daily_aggregates),
                },
            }

    def cleanup_old_metrics(self, days: int = 7):
        """Clean up metrics older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)

        with self._lock:
            # Clean workflow metrics
            old_workflows = [
                wf_id for wf_id, metrics in self._workflow_metrics.items()
                if metrics.end_time and metrics.end_time < cutoff
            ]
            for wf_id in old_workflows:
                del self._workflow_metrics[wf_id]

            # Clean aggregates
            old_hours = [
                hour for hour in self._hourly_aggregates.keys()
                if datetime.fromisoformat(hour) < cutoff
            ]
            for hour in old_hours:
                del self._hourly_aggregates[hour]

            old_days = [
                day for day in self._daily_aggregates.keys()
                if datetime.fromisoformat(day) < cutoff
            ]
            for day in old_days:
                del self._daily_aggregates[day]
