"""Metrics exporters for the MCP Workflow System."""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from .metrics import MetricsCollector, PerformanceMetrics, ResourceMetrics, WorkflowMetrics

logger = logging.getLogger(__name__)


class MetricsExporter:
    """Factory class for metrics exporters."""

    def __init__(self, format: str = "json", **kwargs):
        """Initialize exporter with specified format."""
        if format == "json":
            self._exporter = JSONExporter(**kwargs)
        elif format == "prometheus":
            self._exporter = PrometheusExporter(**kwargs)
        elif format == "csv":
            self._exporter = CSVExporter(**kwargs)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        self.format = format

    def export_workflow_metrics(self, metrics: dict[str, WorkflowMetrics]) -> str:
        """Export workflow metrics to string format."""
        return self._exporter.export_workflow_metrics(metrics)

    def export_performance_metrics(self, metrics: list[PerformanceMetrics]) -> str:
        """Export performance metrics to string format."""
        return self._exporter.export_performance_metrics(metrics)

    def export_resource_metrics(self, metrics: list[ResourceMetrics]) -> str:
        """Export resource metrics to string format."""
        return self._exporter.export_resource_metrics(metrics)

    def export_summary(self, summary: dict[str, Any]) -> str:
        """Export summary statistics to string format."""
        return self._exporter.export_summary(summary)


class BaseMetricsExporter(ABC):
    """Abstract base class for metrics exporters."""

    @abstractmethod
    def export_workflow_metrics(self, metrics: dict[str, WorkflowMetrics]) -> str:
        """Export workflow metrics to string format."""
        pass

    @abstractmethod
    def export_performance_metrics(self, metrics: list[PerformanceMetrics]) -> str:
        """Export performance metrics to string format."""
        pass

    @abstractmethod
    def export_resource_metrics(self, metrics: list[ResourceMetrics]) -> str:
        """Export resource metrics to string format."""
        pass

    @abstractmethod
    def export_summary(self, summary: dict[str, Any]) -> str:
        """Export summary statistics to string format."""
        pass


class JSONExporter(BaseMetricsExporter):
    """Exports metrics in JSON format."""

    def __init__(self, indent: int | None = 2):
        self.indent = indent

    def export_workflow_metrics(self, metrics: dict[str, WorkflowMetrics]) -> str:
        """Export workflow metrics as JSON."""
        data = {
            "type": "workflow_metrics",
            "timestamp": datetime.now().isoformat(),
            "workflows": {workflow_id: metric.to_dict() for workflow_id, metric in metrics.items()},
        }
        return json.dumps(data, indent=self.indent)

    def export_performance_metrics(self, metrics: list[PerformanceMetrics]) -> str:
        """Export performance metrics as JSON."""
        data = {
            "type": "performance_metrics",
            "timestamp": datetime.now().isoformat(),
            "metrics": [metric.to_dict() for metric in metrics],
        }
        return json.dumps(data, indent=self.indent)

    def export_resource_metrics(self, metrics: list[ResourceMetrics]) -> str:
        """Export resource metrics as JSON."""
        data = {
            "type": "resource_metrics",
            "timestamp": datetime.now().isoformat(),
            "metrics": [metric.to_dict() for metric in metrics],
        }
        return json.dumps(data, indent=self.indent)

    def export_summary(self, summary: dict[str, Any]) -> str:
        """Export summary statistics as JSON."""
        data = {"type": "summary_statistics", "data": summary}
        return json.dumps(data, indent=self.indent)

    def export_all_metrics(self, metrics_collector: MetricsCollector) -> str:
        """Export all metrics from a collector as JSON."""
        data = {
            "type": "complete_metrics_export",
            "timestamp": datetime.now().isoformat(),
            "workflow_metrics": {
                wf_id: metrics.to_dict() for wf_id, metrics in metrics_collector.get_all_workflow_metrics().items()
            },
            "performance_metrics": [metric.to_dict() for metric in metrics_collector.get_performance_metrics()],
            "resource_metrics": [metric.to_dict() for metric in metrics_collector.get_resource_metrics()],
            "summary": metrics_collector.get_summary_statistics(),
        }
        return json.dumps(data, indent=self.indent)


class PrometheusExporter(BaseMetricsExporter):
    """Exports metrics in Prometheus format."""

    def __init__(self, namespace: str = "workflow_system"):
        self.namespace = namespace

    def export_workflow_metrics(self, metrics: dict[str, WorkflowMetrics]) -> str:
        """Export workflow metrics in Prometheus format."""
        lines = []

        # Workflow status counters
        status_counts = {"running": 0, "completed": 0, "failed": 0, "paused": 0}
        for metric in metrics.values():
            status_counts[metric.status] = status_counts.get(metric.status, 0) + 1

        lines.append(f"# HELP {self.namespace}_workflows_total Total number of workflows by status")
        lines.append(f"# TYPE {self.namespace}_workflows_total counter")
        for status, count in status_counts.items():
            lines.append(f'{self.namespace}_workflows_total{{status="{status}"}} {count}')

        # Workflow durations
        lines.append(f"# HELP {self.namespace}_workflow_duration_ms Workflow execution duration in milliseconds")
        lines.append(f"# TYPE {self.namespace}_workflow_duration_ms gauge")
        for workflow_id, metric in metrics.items():
            if metric.total_duration_ms is not None:
                lines.append(
                    f"{self.namespace}_workflow_duration_ms{{"
                    f'workflow_id="{workflow_id}",workflow_name="{metric.workflow_name}"}} '
                    f"{metric.total_duration_ms}"
                )

        # Step statistics
        lines.append(f"# HELP {self.namespace}_workflow_steps_total Total steps by workflow")
        lines.append(f"# TYPE {self.namespace}_workflow_steps_total gauge")
        lines.append(f"# HELP {self.namespace}_workflow_steps_completed Completed steps by workflow")
        lines.append(f"# TYPE {self.namespace}_workflow_steps_completed gauge")
        lines.append(f"# HELP {self.namespace}_workflow_steps_failed Failed steps by workflow")
        lines.append(f"# TYPE {self.namespace}_workflow_steps_failed gauge")

        for workflow_id, metric in metrics.items():
            lines.append(f'{self.namespace}_workflow_steps_total{{workflow_id="{workflow_id}"}} {metric.total_steps}')
            lines.append(
                f'{self.namespace}_workflow_steps_completed{{workflow_id="{workflow_id}"}} ' f"{metric.completed_steps}"
            )
            lines.append(f'{self.namespace}_workflow_steps_failed{{workflow_id="{workflow_id}"}} {metric.failed_steps}')

        return "\n".join(lines)

    def export_performance_metrics(self, metrics: list[PerformanceMetrics]) -> str:
        """Export performance metrics in Prometheus format."""
        lines = []

        # Operation duration histogram
        lines.append(f"# HELP {self.namespace}_operation_duration_ms Operation duration in milliseconds")
        lines.append(f"# TYPE {self.namespace}_operation_duration_ms histogram")

        # Group by operation name and calculate histograms
        operations = {}
        for metric in metrics:
            if metric.operation_name not in operations:
                operations[metric.operation_name] = []
            operations[metric.operation_name].append(metric.duration_ms)

        # Simple histogram buckets
        buckets = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, float("inf")]

        for operation, durations in operations.items():
            durations.sort()

            # Calculate histogram buckets
            for bucket in buckets:
                count = sum(1 for d in durations if d <= bucket)
                bucket_label = "+Inf" if bucket == float("inf") else str(bucket)
                lines.append(
                    f"{self.namespace}_operation_duration_ms_bucket{{"
                    f'operation="{operation}",le="{bucket_label}"}} {count}'
                )

            lines.append(f'{self.namespace}_operation_duration_ms_count{{operation="{operation}"}} {len(durations)}')
            lines.append(f'{self.namespace}_operation_duration_ms_sum{{operation="{operation}"}} {sum(durations)}')

        # Success rate
        lines.append(f"# HELP {self.namespace}_operation_success_rate Success rate by operation")
        lines.append(f"# TYPE {self.namespace}_operation_success_rate gauge")

        for operation in operations:
            operation_metrics = [m for m in metrics if m.operation_name == operation]
            successful = sum(1 for m in operation_metrics if m.success)
            total = len(operation_metrics)
            success_rate = successful / total if total > 0 else 0
            lines.append(f'{self.namespace}_operation_success_rate{{operation="{operation}"}} {success_rate}')

        return "\n".join(lines)

    def export_resource_metrics(self, metrics: list[ResourceMetrics]) -> str:
        """Export resource metrics in Prometheus format."""
        lines = []

        if not metrics:
            return ""

        # Use latest metrics
        latest = metrics[-1]

        # Memory metrics
        lines.append(f"# HELP {self.namespace}_memory_total_bytes Total system memory in bytes")
        lines.append(f"# TYPE {self.namespace}_memory_total_bytes gauge")
        lines.append(f"{self.namespace}_memory_total_bytes {latest.memory_total_mb * 1024 * 1024}")

        lines.append(f"# HELP {self.namespace}_memory_used_bytes Used system memory in bytes")
        lines.append(f"# TYPE {self.namespace}_memory_used_bytes gauge")
        lines.append(f"{self.namespace}_memory_used_bytes {latest.memory_used_mb * 1024 * 1024}")

        lines.append(f"# HELP {self.namespace}_memory_usage_percent Memory usage percentage")
        lines.append(f"# TYPE {self.namespace}_memory_usage_percent gauge")
        lines.append(f"{self.namespace}_memory_usage_percent {latest.memory_percent}")

        # CPU metrics
        lines.append(f"# HELP {self.namespace}_cpu_usage_percent CPU usage percentage")
        lines.append(f"# TYPE {self.namespace}_cpu_usage_percent gauge")
        lines.append(f"{self.namespace}_cpu_usage_percent {latest.cpu_percent}")

        lines.append(f"# HELP {self.namespace}_cpu_cores Total CPU cores")
        lines.append(f"# TYPE {self.namespace}_cpu_cores gauge")
        lines.append(f"{self.namespace}_cpu_cores {latest.cpu_count}")

        # Process metrics
        lines.append(f"# HELP {self.namespace}_process_memory_bytes Process memory usage in bytes")
        lines.append(f"# TYPE {self.namespace}_process_memory_bytes gauge")
        lines.append(f"{self.namespace}_process_memory_bytes {latest.process_memory_mb * 1024 * 1024}")

        lines.append(f"# HELP {self.namespace}_process_cpu_percent Process CPU usage percentage")
        lines.append(f"# TYPE {self.namespace}_process_cpu_percent gauge")
        lines.append(f"{self.namespace}_process_cpu_percent {latest.process_cpu_percent}")

        lines.append(f"# HELP {self.namespace}_process_threads Process thread count")
        lines.append(f"# TYPE {self.namespace}_process_threads gauge")
        lines.append(f"{self.namespace}_process_threads {latest.process_threads}")

        # Workflow metrics
        lines.append(f"# HELP {self.namespace}_active_workflows Active workflow count")
        lines.append(f"# TYPE {self.namespace}_active_workflows gauge")
        lines.append(f"{self.namespace}_active_workflows {latest.active_workflows}")

        lines.append(f"# HELP {self.namespace}_total_workflows Total workflow count")
        lines.append(f"# TYPE {self.namespace}_total_workflows gauge")
        lines.append(f"{self.namespace}_total_workflows {latest.total_workflows}")

        return "\n".join(lines)

    def export_summary(self, summary: dict[str, Any]) -> str:
        """Export summary statistics in Prometheus format."""
        lines = []

        # System uptime
        if "uptime_seconds" in summary:
            lines.append(f"# HELP {self.namespace}_uptime_seconds System uptime in seconds")
            lines.append(f"# TYPE {self.namespace}_uptime_seconds counter")
            lines.append(f"{self.namespace}_uptime_seconds {summary['uptime_seconds']}")

        # Workflow statistics
        if "workflows" in summary:
            wf_stats = summary["workflows"]
            for key, value in wf_stats.items():
                lines.append(f"# HELP {self.namespace}_workflows_{key} Workflow {key.replace('_', ' ')}")
                lines.append(f"# TYPE {self.namespace}_workflows_{key} gauge")
                lines.append(f"{self.namespace}_workflows_{key} {value}")

        # Performance statistics
        if "performance" in summary:
            perf_stats = summary["performance"]
            for key, value in perf_stats.items():
                if isinstance(value, int | float):
                    lines.append(f"# HELP {self.namespace}_performance_{key} Performance {key.replace('_', ' ')}")
                    lines.append(f"# TYPE {self.namespace}_performance_{key} gauge")
                    lines.append(f"{self.namespace}_performance_{key} {value}")

        return "\n".join(lines)


class CSVExporter(BaseMetricsExporter):
    """Exports metrics in CSV format."""

    def export_workflow_metrics(self, metrics: dict[str, WorkflowMetrics]) -> str:
        """Export workflow metrics as CSV."""
        lines = [
            "workflow_id,workflow_name,start_time,end_time,status,total_steps,completed_steps,failed_steps,duration_ms,state_size_kb,error_count"
        ]

        for workflow_id, metric in metrics.items():
            lines.append(
                f"{workflow_id},{metric.workflow_name},{metric.start_time.isoformat()},"
                f"{metric.end_time.isoformat() if metric.end_time else ''},"
                f"{metric.status},{metric.total_steps},{metric.completed_steps},"
                f"{metric.failed_steps},{metric.calculate_duration() or ''},"
                f"{metric.state_size_kb},{metric.error_count}"
            )

        return "\n".join(lines)

    def export_performance_metrics(self, metrics: list[PerformanceMetrics]) -> str:
        """Export performance metrics as CSV."""
        lines = ["timestamp,operation_name,duration_ms,success,workflow_id,step_id,operation_type"]

        for metric in metrics:
            lines.append(
                f"{metric.timestamp.isoformat()},{metric.operation_name},"
                f"{metric.duration_ms},{metric.success},{metric.workflow_id or ''},"
                f"{metric.step_id or ''},{metric.operation_type or ''}"
            )

        return "\n".join(lines)

    def export_resource_metrics(self, metrics: list[ResourceMetrics]) -> str:
        """Export resource metrics as CSV."""
        lines = [
            "timestamp,memory_total_mb,memory_used_mb,memory_percent,cpu_percent,process_memory_mb,process_cpu_percent,active_workflows"
        ]

        for metric in metrics:
            lines.append(
                f"{metric.timestamp.isoformat()},{metric.memory_total_mb},"
                f"{metric.memory_used_mb},{metric.memory_percent},{metric.cpu_percent},"
                f"{metric.process_memory_mb},{metric.process_cpu_percent},"
                f"{metric.active_workflows}"
            )

        return "\n".join(lines)

    def export_summary(self, summary: dict[str, Any]) -> str:
        """Export summary statistics as CSV."""
        lines = ["metric,value"]

        def flatten_dict(d: dict[str, Any], prefix: str = ""):
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    lines.extend(flatten_dict(value, full_key))
                elif isinstance(value, int | float | str):
                    lines.append(f"{full_key},{value}")

        flatten_dict(summary)
        return "\n".join(lines)


class FileMetricsExporter:
    """Exports metrics to files using various formats."""

    def __init__(self, base_path: str = "/var/log/workflow_metrics"):
        self.base_path = base_path
        self.exporters = {
            "json": JSONExporter(),
            "prometheus": PrometheusExporter(),
            "csv": CSVExporter(),
        }

    def export_to_file(
        self,
        metrics_collector: MetricsCollector,
        export_format: str = "json",
        filename_prefix: str = "workflow_metrics",
    ) -> str:
        """Export metrics to file."""
        if export_format not in self.exporters:
            raise ValueError(f"Unsupported format: {export_format}")

        exporter = self.exporters[export_format]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.base_path}/{filename_prefix}_{timestamp}.{export_format}"

        try:
            with open(filename, "w") as f:
                if export_format == "json":
                    content = exporter.export_all_metrics(metrics_collector)
                else:
                    # For other formats, export individual sections
                    content = exporter.export_summary(metrics_collector.get_summary_statistics())
                    content += "\n\n" + exporter.export_workflow_metrics(metrics_collector.get_all_workflow_metrics())
                    content += "\n\n" + exporter.export_performance_metrics(metrics_collector.get_performance_metrics())
                    content += "\n\n" + exporter.export_resource_metrics(metrics_collector.get_resource_metrics())

                f.write(content)

            logger.info(f"Exported metrics to {filename}")
            return filename

        except Exception as e:
            logger.error(f"Failed to export metrics to {filename}: {e}")
            raise
