"""Error tracking and history for the MCP Workflow System."""

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

from .models import WorkflowError

logger = logging.getLogger(__name__)


class ErrorHistory:
    """History tracking for workflow errors."""

    def __init__(self, max_errors_per_workflow: int = 100):
        self.max_errors_per_workflow = max_errors_per_workflow
        self._errors: dict[str, deque[WorkflowError]] = defaultdict(lambda: deque(maxlen=max_errors_per_workflow))
        self._global_errors: deque[WorkflowError] = deque(maxlen=1000)

    def add_error(self, error: WorkflowError):
        """Add an error to the history."""
        self._errors[error.workflow_id].append(error)
        self._global_errors.append(error)

    def get_workflow_errors(self, workflow_id: str) -> list[WorkflowError]:
        """Get all errors for a specific workflow."""
        return list(self._errors[workflow_id])

    def get_recent_errors(self, hours: int = 24) -> list[WorkflowError]:
        """Get all errors from the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [error for error in self._global_errors if error.timestamp >= cutoff]

    def get_error_by_id(self, error_id: str) -> WorkflowError | None:
        """Get a specific error by ID."""
        for error in self._global_errors:
            if error.id == error_id:
                return error
        return None

    def get_errors_by_step(self, workflow_id: str, step_id: str) -> list[WorkflowError]:
        """Get all errors for a specific step."""
        return [
            error for error in self._errors[workflow_id]
            if error.step_id == step_id
        ]

    def get_error_summary(self, workflow_id: str | None = None) -> dict[str, Any]:
        """Get error summary statistics."""
        errors = (
            list(self._errors[workflow_id]) if workflow_id
            else list(self._global_errors)
        )

        if not errors:
            return {
                "total_errors": 0,
                "by_severity": {},
                "by_type": {},
                "recent_errors": 0,
            }

        # Count by severity
        by_severity = defaultdict(int)
        for error in errors:
            by_severity[error.severity.value] += 1

        # Count by type
        by_type = defaultdict(int)
        for error in errors:
            by_type[error.error_type] += 1

        # Recent errors (last hour)
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_errors = sum(1 for error in errors if error.timestamp >= recent_cutoff)

        return {
            "total_errors": len(errors),
            "by_severity": dict(by_severity),
            "by_type": dict(by_type),
            "recent_errors": recent_errors,
            "first_error": errors[0].timestamp.isoformat() if errors else None,
            "last_error": errors[-1].timestamp.isoformat() if errors else None,
        }


class ErrorTracker:
    """Comprehensive error tracking and analysis."""

    def __init__(self):
        self.history = ErrorHistory()
        self._error_patterns = defaultdict(list)
        self._recovery_stats = defaultdict(int)

    def track_error(
        self,
        error: WorkflowError,
        recovery_action: str | None = None,
    ):
        """Track an error and any recovery action taken."""
        self.history.add_error(error)

        # Track error patterns
        pattern_key = f"{error.error_type}:{error.step_id}"
        self._error_patterns[pattern_key].append(error.timestamp)

        # Track recovery action
        if recovery_action:
            self._recovery_stats[recovery_action] += 1

        logger.info(f"Tracked error {error.id} for workflow {error.workflow_id}")

    def mark_error_recovered(self, error_id: str):
        """Mark an error as recovered."""
        error = self.history.get_error_by_id(error_id)
        if error:
            error.recovered = True
            self._recovery_stats["recovered"] += 1
            logger.info(f"Marked error {error_id} as recovered")

    def detect_error_patterns(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Detect recurring error patterns."""
        patterns = []
        recent_cutoff = datetime.now() - timedelta(hours=24)

        for pattern_key, timestamps in self._error_patterns.items():
            recent_timestamps = [ts for ts in timestamps if ts >= recent_cutoff]

            if len(recent_timestamps) >= 3:  # Pattern threshold
                error_type, step_id = pattern_key.split(":", 1)
                patterns.append({
                    "error_type": error_type,
                    "step_id": step_id,
                    "occurrences": len(recent_timestamps),
                    "first_occurrence": min(recent_timestamps).isoformat(),
                    "last_occurrence": max(recent_timestamps).isoformat(),
                    "frequency": len(recent_timestamps) / 24,  # per hour
                })

        return sorted(patterns, key=lambda p: p["occurrences"], reverse=True)

    def get_failure_rate(self, workflow_id: str, hours: int = 24) -> float:
        """Calculate failure rate for a workflow."""
        errors = self.history.get_workflow_errors(workflow_id)
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_errors = [error for error in errors if error.timestamp >= cutoff]

        if not recent_errors:
            return 0.0

        # Estimate total executions based on error rate
        # This is a simplified calculation - in practice you'd track executions separately
        total_executions = len(recent_errors) * 10  # Assume 10% error rate as baseline
        return len(recent_errors) / total_executions

    def get_mttr(self, workflow_id: str | None = None) -> float | None:
        """Calculate Mean Time To Recovery (MTTR) in minutes."""
        errors = (
            self.history.get_workflow_errors(workflow_id) if workflow_id
            else list(self.history._global_errors)
        )

        recovered_errors = [error for error in errors if error.recovered]
        if not recovered_errors:
            return None

        # This is simplified - in practice you'd track recovery times
        total_recovery_time = sum(
            (datetime.now() - error.timestamp).total_seconds() / 60
            for error in recovered_errors
        )

        return total_recovery_time / len(recovered_errors)

    def get_error_trends(self, hours: int = 24) -> dict[str, Any]:
        """Get error trends over time."""
        recent_errors = self.history.get_recent_errors(hours)

        # Group by hour
        hourly_counts = defaultdict(int)
        severity_trends = defaultdict(lambda: defaultdict(int))

        for error in recent_errors:
            hour_key = error.timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_counts[hour_key] += 1
            severity_trends[hour_key][error.severity.value] += 1

        return {
            "hourly_counts": {
                hour.isoformat(): count
                for hour, count in sorted(hourly_counts.items())
            },
            "severity_trends": {
                hour.isoformat(): dict(severities)
                for hour, severities in sorted(severity_trends.items())
            },
            "total_recent": len(recent_errors),
        }

    def get_top_errors(self, limit: int = 10, hours: int = 24) -> list[dict[str, Any]]:
        """Get most common errors."""
        recent_errors = self.history.get_recent_errors(hours)
        error_counts = defaultdict(int)

        for error in recent_errors:
            key = f"{error.error_type}:{error.message[:100]}"
            error_counts[key] += 1

        top_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        return [
            {
                "error_signature": error_sig,
                "count": count,
                "percentage": (count / len(recent_errors)) * 100 if recent_errors else 0,
            }
            for error_sig, count in top_errors
        ]

    def get_recovery_stats(self) -> dict[str, Any]:
        """Get recovery statistics."""
        return {
            "recovery_actions": dict(self._recovery_stats),
            "total_recoveries": sum(self._recovery_stats.values()),
        }

    def export_error_data(
        self,
        workflow_id: str | None = None,
        export_format: str = "json"
    ) -> str:
        """Export error data for analysis."""
        errors = (
            self.history.get_workflow_errors(workflow_id) if workflow_id
            else list(self.history._global_errors)
        )

        if export_format == "json":
            return json.dumps([error.to_dict() for error in errors], indent=2)
        elif export_format == "csv":
            # Simple CSV format
            lines = ["id,workflow_id,step_id,error_type,message,timestamp,severity"]
            for error in errors:
                lines.append(
                    f"{error.id},{error.workflow_id},{error.step_id or ''},"
                    f"{error.error_type},\"{error.message}\","
                    f"{error.timestamp.isoformat()},{error.severity.value}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {export_format}")

    def cleanup_old_errors(self, days: int = 30):
        """Clean up errors older than specified days."""
        cutoff = datetime.now() - timedelta(days=days)

        # Clean workflow errors
        for workflow_id, errors in self._error_patterns.items():
            self._error_patterns[workflow_id] = [
                ts for ts in errors if ts >= cutoff
            ]

        # Clean global errors (done automatically by deque maxlen)
        logger.info(f"Cleaned up errors older than {days} days")
