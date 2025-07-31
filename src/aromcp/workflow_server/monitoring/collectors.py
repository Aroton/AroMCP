"""Specialized metrics collectors for different workflow components."""

import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

from .metrics import MetricsCollector, PerformanceMetrics

logger = logging.getLogger(__name__)


class ExecutionMetricsCollector:
    """Collects metrics related to workflow and step execution."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._step_timings: dict[str, float] = {}
        self._step_counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def start_step_timing(self, workflow_id: str, step_id: str) -> str:
        """Start timing a step execution."""
        timing_key = f"{workflow_id}:{step_id}"
        self._step_timings[timing_key] = time.time()
        return timing_key

    def end_step_timing(
        self,
        timing_key: str,
        success: bool,
        step_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """End timing a step execution and record metrics."""
        if timing_key not in self._step_timings:
            logger.warning(f"No timing started for key: {timing_key}")
            return

        start_time = self._step_timings.pop(timing_key)
        duration_ms = (time.time() - start_time) * 1000

        # Extract workflow_id and step_id from timing_key
        workflow_id, step_id = timing_key.split(":", 1)

        # Record performance metric
        metric = PerformanceMetrics(
            operation_name=f"step_execution:{step_type or 'unknown'}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            success=success,
            workflow_id=workflow_id,
            step_id=step_id,
            operation_type="step_execution",
            metadata=metadata or {},
        )

        self.metrics_collector.record_performance_metric(metric)

        # Update step counters
        self._step_counters[workflow_id]["total"] += 1
        if success:
            self._step_counters[workflow_id]["completed"] += 1
        else:
            self._step_counters[workflow_id]["failed"] += 1

        # Update workflow metrics
        self.metrics_collector.update_workflow_metrics(
            workflow_id,
            completed_steps=self._step_counters[workflow_id]["completed"],
            failed_steps=self._step_counters[workflow_id]["failed"],
            total_steps=self._step_counters[workflow_id]["total"],
        )

    def record_workflow_start(self, workflow_id: str, workflow_name: str):
        """Record the start of a workflow."""
        self.metrics_collector.start_workflow_metrics(workflow_id, workflow_name)

        # Initialize step counters
        self._step_counters[workflow_id] = defaultdict(int)

    def record_workflow_completion(self, workflow_id: str, status: str = "completed"):
        """Record the completion of a workflow."""
        self.metrics_collector.complete_workflow_metrics(workflow_id, status)

        # Calculate and update timing statistics
        self._calculate_step_timing_stats(workflow_id)

    def _calculate_step_timing_stats(self, workflow_id: str):
        """Calculate timing statistics for completed workflow."""
        # Get all performance metrics for this workflow
        all_metrics = self.metrics_collector.get_performance_metrics()
        workflow_metrics = [
            m for m in all_metrics if m.workflow_id == workflow_id and m.operation_type == "step_execution"
        ]

        if workflow_metrics:
            durations = [m.duration_ms for m in workflow_metrics]
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)

            self.metrics_collector.update_workflow_metrics(
                workflow_id,
                avg_step_duration_ms=avg_duration,
                max_step_duration_ms=max_duration,
            )

    def get_execution_summary(self, workflow_id: str | None = None) -> dict[str, Any]:
        """Get execution metrics summary."""
        if workflow_id:
            counters = self._step_counters.get(workflow_id, {})
            return {
                "workflow_id": workflow_id,
                "total_steps": counters.get("total", 0),
                "completed_steps": counters.get("completed", 0),
                "failed_steps": counters.get("failed", 0),
                "success_rate": (
                    counters.get("completed", 0) / counters.get("total", 1) * 100 if counters.get("total", 0) > 0 else 0
                ),
            }
        else:
            # Aggregate across all workflows
            total_stats = defaultdict(int)
            for workflow_counters in self._step_counters.values():
                for key, value in workflow_counters.items():
                    total_stats[key] += value

            return {
                "total_steps": total_stats["total"],
                "completed_steps": total_stats["completed"],
                "failed_steps": total_stats["failed"],
                "success_rate": (
                    total_stats["completed"] / total_stats["total"] * 100 if total_stats["total"] > 0 else 0
                ),
                "active_workflows": len(self._step_counters),
            }


class StateMetricsCollector:
    """Collects metrics related to state size and management."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._state_sizes: dict[str, list[float]] = defaultdict(list)
        self._state_update_counts: dict[str, int] = defaultdict(int)

    def record_state_size(self, workflow_id: str, size_kb: float):
        """Record the current state size for a workflow."""
        self._state_sizes[workflow_id].append(size_kb)

        # Keep only last 100 measurements
        if len(self._state_sizes[workflow_id]) > 100:
            self._state_sizes[workflow_id] = self._state_sizes[workflow_id][-100:]

        # Update workflow metrics with current size
        self.metrics_collector.update_workflow_metrics(
            workflow_id,
            state_size_kb=size_kb,
        )

        # Check for size warnings
        if size_kb > 10000:  # 10MB warning threshold
            logger.warning(f"Large state size for workflow {workflow_id}: {size_kb:.1f} KB")

    def record_state_update(self, workflow_id: str, update_count: int = 1):
        """Record state update operations."""
        self._state_update_counts[workflow_id] += update_count

        # Record as performance metric
        metric = PerformanceMetrics(
            operation_name="state_update",
            timestamp=datetime.now(),
            duration_ms=0,  # Duration would be measured separately
            success=True,
            workflow_id=workflow_id,
            operation_type="state_management",
            metadata={"update_count": update_count},
        )

        self.metrics_collector.record_performance_metric(metric)

    def get_state_statistics(self, workflow_id: str) -> dict[str, Any]:
        """Get state statistics for a workflow."""
        sizes = self._state_sizes.get(workflow_id, [])

        if not sizes:
            return {
                "workflow_id": workflow_id,
                "measurements": 0,
                "current_size_kb": 0,
            }

        return {
            "workflow_id": workflow_id,
            "measurements": len(sizes),
            "current_size_kb": sizes[-1],
            "max_size_kb": max(sizes),
            "min_size_kb": min(sizes),
            "avg_size_kb": sum(sizes) / len(sizes),
            "update_count": self._state_update_counts.get(workflow_id, 0),
            "size_growth": sizes[-1] - sizes[0] if len(sizes) > 1 else 0,
        }

    def get_size_warnings(self, threshold_kb: float = 10000) -> list[dict[str, Any]]:
        """Get workflows with state sizes exceeding threshold."""
        warnings = []

        for workflow_id, sizes in self._state_sizes.items():
            if sizes and sizes[-1] > threshold_kb:
                warnings.append(
                    {
                        "workflow_id": workflow_id,
                        "current_size_kb": sizes[-1],
                        "threshold_kb": threshold_kb,
                        "exceeded_by_kb": sizes[-1] - threshold_kb,
                    }
                )

        return sorted(warnings, key=lambda w: w["exceeded_by_kb"], reverse=True)


class TransformationMetricsCollector:
    """Collects metrics related to computed field transformations."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._transformation_counts: dict[str, int] = defaultdict(int)
        self._transformation_timings: dict[str, list[float]] = defaultdict(list)
        self._transformation_errors: dict[str, int] = defaultdict(int)

    def record_transformation(
        self,
        workflow_id: str,
        field_name: str,
        duration_ms: float,
        success: bool,
        input_size: int | None = None,
        output_size: int | None = None,
    ):
        """Record a transformation execution."""
        transformation_key = f"{workflow_id}:{field_name}"

        self._transformation_counts[transformation_key] += 1
        self._transformation_timings[transformation_key].append(duration_ms)

        if not success:
            self._transformation_errors[transformation_key] += 1

        # Keep only last 100 timings
        if len(self._transformation_timings[transformation_key]) > 100:
            self._transformation_timings[transformation_key] = self._transformation_timings[transformation_key][-100:]

        # Record as performance metric
        metadata = {"field_name": field_name}
        if input_size is not None:
            metadata["input_size"] = input_size
        if output_size is not None:
            metadata["output_size"] = output_size

        metric = PerformanceMetrics(
            operation_name=f"transformation:{field_name}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            success=success,
            workflow_id=workflow_id,
            operation_type="transformation",
            metadata=metadata,
        )

        self.metrics_collector.record_performance_metric(metric)

        # Update workflow transformation count
        total_transformations = sum(
            count for key, count in self._transformation_counts.items() if key.startswith(f"{workflow_id}:")
        )

        self.metrics_collector.update_workflow_metrics(
            workflow_id,
            transformation_count=total_transformations,
        )

    def get_transformation_statistics(self, workflow_id: str) -> dict[str, Any]:
        """Get transformation statistics for a workflow."""
        workflow_keys = [key for key in self._transformation_counts.keys() if key.startswith(f"{workflow_id}:")]

        field_stats = {}
        total_count = 0
        total_errors = 0
        all_timings = []

        for key in workflow_keys:
            field_name = key.split(":", 1)[1]
            count = self._transformation_counts[key]
            errors = self._transformation_errors[key]
            timings = self._transformation_timings[key]

            total_count += count
            total_errors += errors
            all_timings.extend(timings)

            field_stats[field_name] = {
                "executions": count,
                "errors": errors,
                "success_rate": ((count - errors) / count * 100) if count > 0 else 0,
                "avg_duration_ms": sum(timings) / len(timings) if timings else 0,
                "max_duration_ms": max(timings) if timings else 0,
            }

        return {
            "workflow_id": workflow_id,
            "total_transformations": total_count,
            "total_errors": total_errors,
            "overall_success_rate": ((total_count - total_errors) / total_count * 100) if total_count > 0 else 0,
            "avg_duration_ms": sum(all_timings) / len(all_timings) if all_timings else 0,
            "field_statistics": field_stats,
        }

    def get_slowest_transformations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the slowest transformation operations."""
        all_timings = []

        for key, timings in self._transformation_timings.items():
            if timings:
                workflow_id, field_name = key.split(":", 1)
                max_timing = max(timings)
                avg_timing = sum(timings) / len(timings)

                all_timings.append(
                    {
                        "workflow_id": workflow_id,
                        "field_name": field_name,
                        "max_duration_ms": max_timing,
                        "avg_duration_ms": avg_timing,
                        "executions": len(timings),
                    }
                )

        return sorted(all_timings, key=lambda x: x["max_duration_ms"], reverse=True)[:limit]


class ErrorRateCollector:
    """Collects metrics related to error rates and patterns."""

    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self._error_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._error_rates: dict[str, list[float]] = defaultdict(list)
        self._last_calculation = datetime.now()

    def record_error(
        self,
        workflow_id: str,
        error_type: str,
        step_id: str | None = None,
        severity: str = "medium",
    ):
        """Record an error occurrence."""
        # Count by error type
        self._error_counts[workflow_id][error_type] += 1

        # Count by step if provided
        if step_id:
            step_key = f"step:{step_id}"
            self._error_counts[workflow_id][step_key] += 1

        # Count by severity
        severity_key = f"severity:{severity}"
        self._error_counts[workflow_id][severity_key] += 1

        # Record as performance metric (failed operation)
        metric = PerformanceMetrics(
            operation_name=f"error:{error_type}",
            timestamp=datetime.now(),
            duration_ms=0,
            success=False,
            workflow_id=workflow_id,
            step_id=step_id,
            operation_type="error",
            metadata={"error_type": error_type, "severity": severity},
        )

        self.metrics_collector.record_performance_metric(metric)

        # Update workflow error count
        total_errors = sum(
            count
            for key, count in self._error_counts[workflow_id].items()
            if not key.startswith(("step:", "severity:"))
        )

        self.metrics_collector.update_workflow_metrics(
            workflow_id,
            error_count=total_errors,
        )

    def calculate_error_rates(self):
        """Calculate current error rates for all workflows."""
        now = datetime.now()
        time_window = (now - self._last_calculation).total_seconds()

        if time_window < 60:  # Only calculate every minute
            return

        for workflow_id in self._error_counts:
            # Get recent performance metrics for this workflow
            all_metrics = self.metrics_collector.get_performance_metrics()
            recent_metrics = [
                m
                for m in all_metrics
                if (m.workflow_id == workflow_id and (now - m.timestamp).total_seconds() < 3600)  # Last hour
            ]

            if recent_metrics:
                error_count = len([m for m in recent_metrics if not m.success])
                total_count = len(recent_metrics)
                error_rate = (error_count / total_count) * 100 if total_count > 0 else 0

                self._error_rates[workflow_id].append(error_rate)

                # Keep only last 24 hours of hourly rates
                if len(self._error_rates[workflow_id]) > 24:
                    self._error_rates[workflow_id] = self._error_rates[workflow_id][-24:]

        self._last_calculation = now

    def get_error_statistics(self, workflow_id: str) -> dict[str, Any]:
        """Get error statistics for a workflow."""
        error_counts = self._error_counts.get(workflow_id, {})
        error_rates = self._error_rates.get(workflow_id, [])

        # Separate different types of counts
        error_types = {k: v for k, v in error_counts.items() if not k.startswith(("step:", "severity:"))}
        step_errors = {k[5:]: v for k, v in error_counts.items() if k.startswith("step:")}
        severity_counts = {k[9:]: v for k, v in error_counts.items() if k.startswith("severity:")}

        return {
            "workflow_id": workflow_id,
            "total_errors": sum(error_types.values()),
            "error_types": error_types,
            "step_errors": step_errors,
            "severity_distribution": severity_counts,
            "current_error_rate": error_rates[-1] if error_rates else 0,
            "avg_error_rate": sum(error_rates) / len(error_rates) if error_rates else 0,
            "error_rate_trend": error_rates[-5:] if error_rates else [],
        }

    def get_top_error_sources(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the top sources of errors across all workflows."""
        all_errors = []

        for workflow_id, error_counts in self._error_counts.items():
            for error_key, count in error_counts.items():
                if not error_key.startswith(("step:", "severity:")):
                    all_errors.append(
                        {
                            "workflow_id": workflow_id,
                            "error_type": error_key,
                            "count": count,
                        }
                    )

        return sorted(all_errors, key=lambda x: x["count"], reverse=True)[:limit]
