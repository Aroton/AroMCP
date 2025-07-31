"""Performance monitoring for the MCP Workflow System."""

import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceBottleneck:
    """Represents a detected performance bottleneck."""

    step_id: str
    type: str  # duration, cpu, memory, io
    severity: str  # low, medium, high, critical
    value: float
    threshold: float
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StepPerformanceData:
    """Performance data for a single step."""

    step_id: str
    step_type: str
    duration: float
    cpu_usage: float
    memory_usage: float
    timestamp: datetime = field(default_factory=datetime.now)
    io_operations: int = 0
    network_bytes: int = 0


@dataclass
class ResourceSnapshot:
    """Snapshot of resource usage at a point in time."""

    timestamp: datetime
    memory_mb: float
    cpu_percent: float
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionModeData:
    """Data for an execution mode (serial/parallel)."""

    mode: str
    total_duration: float
    step_durations: list[float]
    peak_memory_mb: float
    average_cpu_percent: float
    concurrent_steps: int
    parallelizable_steps: int
    serial_steps: int
    resource_efficiency: float = 0.0


class PerformanceMonitor:
    """Monitor and analyze workflow performance."""

    def __init__(self):
        """Initialize performance monitor."""
        self._lock = threading.RLock()

        # Step performance tracking
        self._step_data: deque = deque(maxlen=1000)
        self._step_type_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0,
                "total_cpu": 0,
                "total_memory": 0,
                "success_count": 0,
                "failure_count": 0,
            }
        )

        # Resource usage tracking
        self._resource_timeline: deque = deque(maxlen=1000)
        self._resource_monitoring_enabled = False

        # Bottleneck detection thresholds
        self._thresholds = {
            "duration": {"low": 5.0, "medium": 10.0, "high": 20.0, "critical": 30.0},
            "cpu": {"low": 50, "medium": 70, "high": 85, "critical": 95},
            "memory": {"low": 200, "medium": 500, "high": 800, "critical": 1000},
        }

        # Execution mode comparison
        self._execution_modes: dict[str, ExecutionModeData] = {}

        # Process info
        self._process = psutil.Process()

    def record_step_performance(
        self, step_id: str, step_type: str, duration: float, cpu_usage: float, memory_usage: float
    ):
        """Record performance data for a step."""
        with self._lock:
            data = StepPerformanceData(
                step_id=step_id, step_type=step_type, duration=duration, cpu_usage=cpu_usage, memory_usage=memory_usage
            )

            self._step_data.append(data)

            # Update type statistics
            stats = self._step_type_stats[step_type]
            stats["count"] += 1
            stats["total_duration"] += duration
            stats["total_cpu"] += cpu_usage
            stats["total_memory"] += memory_usage
            stats["success_count"] += 1  # Assuming success if recording

    def record_resource_usage(self, timestamp: datetime, memory_mb: float, cpu_percent: float, context: dict[str, Any]):
        """Record resource usage snapshot."""
        with self._lock:
            snapshot = ResourceSnapshot(
                timestamp=timestamp, memory_mb=memory_mb, cpu_percent=cpu_percent, context=context.copy()
            )
            self._resource_timeline.append(snapshot)

    def identify_bottlenecks(self) -> list[PerformanceBottleneck]:
        """Identify performance bottlenecks."""
        with self._lock:
            bottlenecks = []

            # Analyze recent step data
            recent_steps = list(self._step_data)

            for step in recent_steps:
                # Check duration bottlenecks
                for severity, threshold in self._thresholds["duration"].items():
                    if step.duration >= threshold:
                        bottlenecks.append(
                            PerformanceBottleneck(
                                step_id=step.step_id,
                                type="duration",
                                severity=severity,
                                value=step.duration,
                                threshold=threshold,
                                recommendation=f"Step {step.step_id} took {step.duration:.1f}s. Consider optimizing or parallelizing.",
                            )
                        )
                        break

                # Check CPU bottlenecks
                for severity, threshold in self._thresholds["cpu"].items():
                    if step.cpu_usage >= threshold:
                        bottlenecks.append(
                            PerformanceBottleneck(
                                step_id=step.step_id,
                                type="cpu",
                                severity=severity,
                                value=step.cpu_usage,
                                threshold=threshold,
                                recommendation=f"Step {step.step_id} used {step.cpu_usage:.0f}% CPU. Consider resource optimization.",
                            )
                        )
                        break

                # Check memory bottlenecks
                for severity, threshold in self._thresholds["memory"].items():
                    if step.memory_usage >= threshold:
                        bottlenecks.append(
                            PerformanceBottleneck(
                                step_id=step.step_id,
                                type="memory",
                                severity=severity,
                                value=step.memory_usage,
                                threshold=threshold,
                                recommendation=f"Step {step.step_id} used {step.memory_usage:.0f}MB memory. Consider memory optimization.",
                            )
                        )
                        break

            return bottlenecks

    def get_resource_analysis(self) -> dict[str, Any]:
        """Analyze resource usage patterns."""
        with self._lock:
            if not self._resource_timeline:
                return {"memory": {}, "cpu": {}, "patterns": [], "optimization_suggestions": []}

            snapshots = list(self._resource_timeline)

            # Memory analysis
            memory_values = [s.memory_mb for s in snapshots]
            memory_stats = {
                "peak_usage_mb": max(memory_values),
                "average_usage_mb": sum(memory_values) / len(memory_values),
                "min_usage_mb": min(memory_values),
                "memory_growth_rate": self._calculate_growth_rate(memory_values),
            }

            # CPU analysis
            cpu_values = [s.cpu_percent for s in snapshots]
            cpu_stats = {
                "peak_cpu_percent": max(cpu_values),
                "average_cpu_percent": sum(cpu_values) / len(cpu_values),
                "min_cpu_percent": min(cpu_values),
                "cpu_volatility": self._calculate_volatility(cpu_values),
            }

            # Pattern identification
            patterns = []

            # Check for memory spikes
            if memory_stats["peak_usage_mb"] > memory_stats["average_usage_mb"] * 2:
                patterns.append("memory_spike")

            # Check for CPU intensive periods
            high_cpu_count = sum(1 for cpu in cpu_values if cpu > 70)
            if high_cpu_count / len(cpu_values) > 0.3:
                patterns.append("cpu_intensive_period")

            # Optimization suggestions
            suggestions = []

            if memory_stats["memory_growth_rate"] > 0.1:
                suggestions.append(
                    {
                        "type": "memory",
                        "issue": "Memory continuously growing",
                        "suggestion": "Check for memory leaks or implement periodic cleanup",
                    }
                )

            if cpu_stats["average_cpu_percent"] > 60:
                suggestions.append(
                    {
                        "type": "cpu",
                        "issue": "High average CPU usage",
                        "suggestion": "Consider distributing work across multiple processes",
                    }
                )

            return {
                "memory": memory_stats,
                "cpu": cpu_stats,
                "patterns": patterns,
                "optimization_suggestions": suggestions,
            }

    def enable_resource_monitoring(self, enabled: bool):
        """Enable or disable resource monitoring."""
        self._resource_monitoring_enabled = enabled

    def record_execution_mode(self, mode: str, data: dict[str, Any]):
        """Record execution mode data for comparison."""
        with self._lock:
            mode_data = ExecutionModeData(
                mode=mode,
                total_duration=data["total_duration"],
                step_durations=data["step_durations"],
                peak_memory_mb=data["peak_memory_mb"],
                average_cpu_percent=data["average_cpu_percent"],
                concurrent_steps=data["concurrent_steps"],
                parallelizable_steps=data["parallelizable_steps"],
                serial_steps=data["serial_steps"],
            )

            # Calculate resource efficiency
            if mode == "parallel":
                # Efficiency based on speedup vs resource usage
                ideal_speedup = mode_data.parallelizable_steps
                actual_speedup = 1.0  # Will be calculated in comparison
                memory_overhead = mode_data.peak_memory_mb / 100  # Normalized
                mode_data.resource_efficiency = actual_speedup / (1 + memory_overhead)

            self._execution_modes[mode] = mode_data

    def compare_execution_modes(self, mode1: str, mode2: str) -> dict[str, Any]:
        """Compare performance between two execution modes."""
        with self._lock:
            if mode1 not in self._execution_modes or mode2 not in self._execution_modes:
                return {"error": "Execution mode data not found"}

            data1 = self._execution_modes[mode1]
            data2 = self._execution_modes[mode2]

            # Timing comparison
            timing = {
                f"{mode1}_duration": data1.total_duration,
                f"{mode2}_duration": data2.total_duration,
                "speedup_factor": data2.total_duration / data1.total_duration if data1.total_duration > 0 else 0,
                "time_saved_seconds": data2.total_duration - data1.total_duration,
            }

            # Resource comparison
            resources = {
                f"{mode1}_peak_memory": data1.peak_memory_mb,
                f"{mode2}_peak_memory": data2.peak_memory_mb,
                "memory_overhead_factor": (
                    data1.peak_memory_mb / data2.peak_memory_mb if data2.peak_memory_mb > 0 else 0
                ),
                f"{mode1}_avg_cpu": data1.average_cpu_percent,
                f"{mode2}_avg_cpu": data2.average_cpu_percent,
            }

            # Efficiency analysis
            efficiency = {
                "parallel_efficiency": (
                    min(1.0, timing["speedup_factor"] / data1.concurrent_steps) if mode1 == "parallel" else 0
                ),
                "resource_efficiency_score": data1.resource_efficiency,
                "cpu_utilization_improvement": (
                    (data1.average_cpu_percent - data2.average_cpu_percent) / data2.average_cpu_percent
                    if data2.average_cpu_percent > 0
                    else 0
                ),
                "memory_cost_analysis": (
                    (data1.peak_memory_mb - data2.peak_memory_mb) / timing.get("time_saved_seconds", 1)
                    if timing.get("time_saved_seconds", 0) != 0
                    else 0
                ),
            }

            # Recommendations
            recommendations = []

            if timing["speedup_factor"] > 1.2 and resources["memory_overhead_factor"] < 3:
                recommendations.append(
                    {
                        "recommended_mode": mode1,
                        "reasoning": f"Significant speedup ({timing['speedup_factor']:.1f}x) with acceptable memory overhead",
                    }
                )
            elif resources["memory_overhead_factor"] > 5:
                recommendations.append(
                    {
                        "recommended_mode": mode2,
                        "reasoning": f"Memory overhead too high ({resources['memory_overhead_factor']:.1f}x)",
                    }
                )
            else:
                recommendations.append(
                    {
                        "recommended_mode": mode1 if timing["speedup_factor"] > 1 else mode2,
                        "reasoning": "Marginal performance difference, choose based on resource availability",
                    }
                )

            return {
                "timing": timing,
                "resources": resources,
                "efficiency": efficiency,
                "recommendations": recommendations,
            }

    def get_performance_analysis(self) -> dict[str, Any]:
        """Get comprehensive performance analysis."""
        with self._lock:
            # Calculate step type breakdown
            step_type_breakdown = {}
            for step_type, stats in self._step_type_stats.items():
                if stats["count"] > 0:
                    step_type_breakdown[step_type] = {
                        "count": stats["count"],
                        "average_duration": stats["total_duration"] / stats["count"],
                        "average_cpu": stats["total_cpu"] / stats["count"],
                        "average_memory": stats["total_memory"] / stats["count"],
                        "success_rate": stats["success_count"] / stats["count"],
                    }

            # Total workflow duration
            if self._step_data:
                total_duration = sum(step.duration for step in self._step_data)
            else:
                total_duration = 0

            return {
                "total_workflow_duration": total_duration,
                "step_performance_breakdown": step_type_breakdown,
                "bottlenecks": [b.__dict__ for b in self.identify_bottlenecks()],
                "resource_analysis": self.get_resource_analysis(),
            }

    def _calculate_growth_rate(self, values: list[float]) -> float:
        """Calculate growth rate of values."""
        if len(values) < 2:
            return 0.0

        # Simple linear regression slope
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator / y_mean if y_mean != 0 else 0

    def _calculate_volatility(self, values: list[float]) -> float:
        """Calculate volatility (standard deviation) of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return variance**0.5

    def start_operation(self, operation_id: str, metadata: dict = None) -> str:
        """Start monitoring an operation."""
        with self._lock:
            if metadata is None:
                metadata = {}

            start_time = datetime.now()
            operation_data = {"operation_id": operation_id, "start_time": start_time, "metadata": metadata}

            # Store in step data temporarily
            self._step_data.append(
                type(
                    "Operation",
                    (),
                    {
                        "step_id": operation_id,
                        "step_type": "operation",
                        "duration": 0,
                        "cpu_usage": 0,
                        "memory_usage": 0,
                        "start_time": start_time,
                        "metadata": metadata,
                    },
                )()
            )

            return operation_id

    def end_operation(self, operation_id: str) -> float:
        """End monitoring an operation and return duration."""
        with self._lock:
            end_time = datetime.now()

            # Find the operation in recent data
            for i, step in enumerate(reversed(self._step_data)):
                if hasattr(step, "step_id") and step.step_id == operation_id and hasattr(step, "start_time"):
                    duration = (end_time - step.start_time).total_seconds()
                    # Update the operation with final duration
                    step.duration = duration
                    return duration

            return 0.0

    def record_metric(self, metric_name: str, value: float, tags: dict = None) -> None:
        """Record a custom metric value."""
        with self._lock:
            if tags is None:
                tags = {}

            # Store metric in resource timeline with context
            self.record_resource_usage(
                timestamp=datetime.now(),
                memory_mb=0,  # Placeholder
                cpu_percent=0,  # Placeholder
                context={"metric_name": metric_name, "metric_value": value, "tags": tags},
            )

    def get_metrics_summary(self, metric_name: str) -> dict[str, Any]:
        """Get summary statistics for a specific metric."""
        with self._lock:
            metric_values = []

            for snapshot in self._resource_timeline:
                if snapshot.context.get("metric_name") == metric_name:
                    metric_values.append(snapshot.context.get("metric_value", 0))

            if not metric_values:
                return {"error": f"No data found for metric: {metric_name}"}

            return {
                "metric_name": metric_name,
                "count": len(metric_values),
                "min": min(metric_values),
                "max": max(metric_values),
                "avg": sum(metric_values) / len(metric_values),  # Use "avg" for test compatibility
                "average": sum(metric_values) / len(metric_values),
                "total": sum(metric_values),
            }

    def get_bottleneck_analysis(self) -> dict[str, Any]:
        """Get comprehensive bottleneck analysis."""
        bottlenecks = self.identify_bottlenecks()

        # Group by type and severity
        analysis = {"total_bottlenecks": len(bottlenecks), "by_type": {}, "by_severity": {}, "top_issues": []}

        for bottleneck in bottlenecks:
            # Group by type
            if bottleneck.type not in analysis["by_type"]:
                analysis["by_type"][bottleneck.type] = 0
            analysis["by_type"][bottleneck.type] += 1

            # Group by severity
            if bottleneck.severity not in analysis["by_severity"]:
                analysis["by_severity"][bottleneck.severity] = 0
            analysis["by_severity"][bottleneck.severity] += 1

        # Get top 5 most severe issues
        severity_order = ["critical", "high", "medium", "low"]
        sorted_bottlenecks = sorted(
            bottlenecks, key=lambda x: (severity_order.index(x.severity), x.value), reverse=True
        )
        analysis["top_issues"] = [b.__dict__ for b in sorted_bottlenecks[:5]]

        return analysis

    def track_step_execution_time(self, step_id: str, execution_time: float) -> None:
        """Track execution time for a specific step."""
        self.record_step_performance(
            step_id=step_id,
            step_type="tracked_step",
            duration=execution_time,
            cpu_usage=0,  # Will be populated by system monitoring
            memory_usage=0,  # Will be populated by system monitoring
        )

    def record_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Record an event with associated data."""
        with self._lock:
            # Store event as a resource snapshot with special context
            snapshot = ResourceSnapshot(
                timestamp=datetime.now(),
                memory_mb=0,  # Not relevant for events
                cpu_percent=0,  # Not relevant for events
                context={"event_type": event_type, "event_data": data, "is_event": True},
            )
            self._resource_timeline.append(snapshot)

    def get_events(self, event_type: str) -> list[dict[str, Any]]:
        """Get all events of a specific type."""
        with self._lock:
            events = []
            for snapshot in self._resource_timeline:
                if snapshot.context.get("is_event") and snapshot.context.get("event_type") == event_type:
                    events.append(
                        {
                            "timestamp": snapshot.timestamp,
                            "data": snapshot.context.get("event_data", {}),
                            "type": event_type,
                        }
                    )
            return events
