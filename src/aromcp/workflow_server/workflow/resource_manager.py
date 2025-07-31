"""Resource management for the MCP Workflow System."""

import gc
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import psutil

logger = logging.getLogger(__name__)


class ResourceExhaustionError(Exception):
    """Raised when resource limits are exceeded."""

    pass


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class OperationFailureError(Exception):
    """Raised when an operation fails."""

    pass


@dataclass
class ResourceUsage:
    """Track resource usage for a workflow."""

    workflow_id: str
    memory_mb: float
    cpu_percent: float
    allocated_at: datetime
    last_updated: datetime
    thread_count: int = 1
    file_handles: int = 0

    def is_stale(self, timeout_minutes: int = 30) -> bool:
        """Check if resource allocation is stale."""
        return (datetime.now() - self.last_updated).total_seconds() > timeout_minutes * 60


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting operations."""

    operation: str
    failure_threshold: int
    timeout_seconds: int
    recovery_time_seconds: int
    failure_count: int = 0
    last_failure_time: datetime | None = None
    state: str = "closed"  # closed, open, half-open

    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.state == "open":
            # Check if recovery time has passed
            if self.last_failure_time:
                time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
                if time_since_failure >= self.recovery_time_seconds:
                    self.state = "half-open"
                    return False
            return True
        return False

    def record_success(self):
        """Record successful operation."""
        if self.state == "half-open":
            self.state = "closed"
            self.failure_count = 0

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"


@dataclass
class WorkflowCheckpoint:
    """Checkpoint data for workflow recovery."""

    workflow_id: str
    status: str
    current_step_index: int
    total_steps: int
    state: dict[str, Any]
    execution_context: dict[str, Any]
    checkpoint_time: datetime
    completed_steps: list[str] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)


class WorkflowResourceManager:
    """Manages resources for workflow execution."""

    def __init__(
        self,
        max_memory_mb: float = 1000,
        max_cpu_percent: float = 80,
        max_workflows: int = 10,
        gc_interval_seconds: int = 60,
    ):
        """Initialize resource manager with limits."""
        self.max_memory_mb = max_memory_mb
        self.max_cpu_percent = max_cpu_percent
        self.max_workflows = max_workflows
        self.gc_interval_seconds = gc_interval_seconds

        # Resource tracking
        self._lock = threading.RLock()
        self._resource_usage: dict[str, ResourceUsage] = {}
        self._total_memory_mb = 0.0
        self._total_cpu_percent = 0.0

        # Circuit breakers
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

        # Recovery data
        self._checkpoints: dict[str, WorkflowCheckpoint] = {}
        self._recovery_enabled = False

        # Callbacks
        self._degradation_callback: Callable | None = None
        self._status_callback: Callable | None = None

        # Garbage collection
        self._gc_thread = None
        self._gc_active = False
        self._start_garbage_collection()

        # Process info
        self._process = psutil.Process(os.getpid())

    def allocate_resources(
        self,
        workflow_id: str,
        memory_mb: float = None,
        cpu_percent: float = None,
        requested_memory_mb: float = None,
        requested_cpu_percent: float = None,
    ) -> dict[str, Any]:
        """Allocate resources for a workflow."""
        with self._lock:
            # Support both parameter names for backward compatibility
            if requested_memory_mb is not None:
                memory_mb = requested_memory_mb
            if requested_cpu_percent is not None:
                cpu_percent = requested_cpu_percent

            # Default values if not provided
            if memory_mb is None:
                memory_mb = 100.0  # Default 100MB
            if cpu_percent is None:
                cpu_percent = 10.0  # Default 10% CPU

            # Check if we can allocate
            new_total_memory = self._total_memory_mb + memory_mb
            new_total_cpu = self._total_cpu_percent + cpu_percent

            if new_total_memory > self.max_memory_mb:
                error_msg = f"Cannot allocate {memory_mb}MB memory. Would exceed memory limit of {self.max_memory_mb}MB"
                self._trigger_degradation("resource_limit_approached", {"type": "memory", "requested": memory_mb})
                raise ResourceExhaustionError(error_msg)

            if new_total_cpu > self.max_cpu_percent:
                error_msg = f"Cannot allocate {cpu_percent}% CPU. Would exceed CPU limit of {self.max_cpu_percent}%"
                self._trigger_degradation("resource_limit_approached", {"type": "cpu", "requested": cpu_percent})
                raise ResourceExhaustionError(error_msg)

            if len(self._resource_usage) >= self.max_workflows:
                error_msg = f"Cannot allocate resources. Maximum workflow limit of {self.max_workflows} reached"
                self._trigger_degradation(
                    "resource_limit_approached", {"type": "workflows", "current": len(self._resource_usage)}
                )
                raise ResourceExhaustionError(error_msg)

            # Allocate resources
            usage = ResourceUsage(
                workflow_id=workflow_id,
                memory_mb=memory_mb,
                cpu_percent=cpu_percent,
                allocated_at=datetime.now(),
                last_updated=datetime.now(),
            )

            self._resource_usage[workflow_id] = usage
            self._total_memory_mb = new_total_memory
            self._total_cpu_percent = new_total_cpu

            return {
                "allocated": True,
                "workflow_id": workflow_id,
                "memory_mb": memory_mb,
                "cpu_percent": cpu_percent,
                "available_memory_mb": self.max_memory_mb - new_total_memory,
                "available_cpu_percent": self.max_cpu_percent - new_total_cpu,
            }

    def release_resources(self, workflow_id: str):
        """Release resources for a workflow."""
        with self._lock:
            if workflow_id in self._resource_usage:
                usage = self._resource_usage[workflow_id]
                self._total_memory_mb -= usage.memory_mb
                self._total_cpu_percent -= usage.cpu_percent
                del self._resource_usage[workflow_id]

                # Trigger garbage collection if significant resources freed
                if usage.memory_mb > 100:
                    gc.collect()

    def get_resource_usage(self, workflow_id: str) -> ResourceUsage | None:
        """Get resource usage for a workflow."""
        with self._lock:
            return self._resource_usage.get(workflow_id)

    def get_total_resource_usage(self) -> dict[str, Any]:
        """Get total resource usage across all workflows."""
        with self._lock:
            return {
                "total_memory_mb": self._total_memory_mb,
                "total_cpu_percent": self._total_cpu_percent,
                "active_workflows": len(self._resource_usage),
                "max_memory_mb": self.max_memory_mb,
                "max_cpu_percent": self.max_cpu_percent,
                "max_workflows": self.max_workflows,
            }

    def configure_circuit_breaker(
        self, operation_type: str, failure_threshold: int, timeout_seconds: int, recovery_time_seconds: int
    ):
        """Configure a circuit breaker for an operation type."""
        with self._lock:
            self._circuit_breakers[operation_type] = CircuitBreaker(
                operation=operation_type,
                failure_threshold=failure_threshold,
                timeout_seconds=timeout_seconds,
                recovery_time_seconds=recovery_time_seconds,
            )

    def execute_protected_operation(
        self, operation_type: str, operation_params: dict[str, Any], simulate_failure: bool = False
    ) -> Any:
        """Execute an operation protected by circuit breaker."""
        with self._lock:
            if operation_type not in self._circuit_breakers:
                raise ValueError(f"No circuit breaker configured for operation: {operation_type}")

            breaker = self._circuit_breakers[operation_type]

            # Check if circuit breaker is open
            if breaker.is_open():
                raise CircuitBreakerOpenError(f"Circuit breaker open for operation: {operation_type}")

            # Simulate operation
            if simulate_failure:
                breaker.record_failure()
                raise OperationFailureError(f"Operation failed: {operation_type}")
            else:
                breaker.record_success()
                return {"success": True, "operation": operation_type}

    def store_recovery_checkpoint(self, workflow_state: Any):
        """Store a recovery checkpoint for a workflow."""
        with self._lock:
            checkpoint = WorkflowCheckpoint(
                workflow_id=workflow_state.workflow_id,
                status=workflow_state.status,
                current_step_index=workflow_state.current_step_index,
                total_steps=workflow_state.total_steps,
                state=workflow_state.state.copy(),
                execution_context=workflow_state.execution_context.copy(),
                checkpoint_time=datetime.now(),
                completed_steps=workflow_state.execution_context.get("checkpoint_data", {}).get("completed_steps", []),
                pending_steps=workflow_state.execution_context.get("checkpoint_data", {}).get("pending_steps", []),
            )
            self._checkpoints[workflow_state.workflow_id] = checkpoint

    def recover_interrupted_workflows(self) -> list[Any]:
        """Recover workflows from checkpoints."""
        with self._lock:
            recovered = []
            for checkpoint in self._checkpoints.values():
                # Create recovered workflow state
                from .workflow_state import WorkflowState

                recovered_state = WorkflowState(
                    workflow_id=checkpoint.workflow_id,
                    status="recovering",
                    current_step_index=checkpoint.current_step_index,
                    total_steps=checkpoint.total_steps,
                    state=checkpoint.state.copy(),
                    execution_context=checkpoint.execution_context.copy(),
                )
                recovered.append(recovered_state)

            return recovered

    def resume_workflow_execution(self, workflow_state: Any) -> dict[str, Any]:
        """Resume workflow execution from checkpoint."""
        checkpoint_data = workflow_state.execution_context.get("checkpoint_data", {})
        completed_steps = checkpoint_data.get("completed_steps", [])
        pending_steps = checkpoint_data.get("pending_steps", [])

        if pending_steps:
            resume_point = pending_steps[0]
        else:
            resume_point = f"step{workflow_state.current_step_index + 1}"

        return {
            "success": True,
            "workflow_id": workflow_state.workflow_id,
            "resume_point": resume_point,
            "completed_steps": len(completed_steps),
            "pending_steps": len(pending_steps),
        }

    def enable_failure_recovery(self, enabled: bool):
        """Enable or disable failure recovery."""
        self._recovery_enabled = enabled

    def set_degradation_callback(self, callback: Callable):
        """Set callback for degradation events."""
        self._degradation_callback = callback

    def set_status_callback(self, callback: Callable):
        """Set callback for status updates."""
        self._status_callback = callback

    def get_active_contexts(self) -> list[str]:
        """Get list of active workflow contexts."""
        with self._lock:
            return list(self._resource_usage.keys())

    def get_resource_summary(self) -> dict[str, Any]:
        """Get summary of resource usage."""
        with self._lock:
            return {
                "contexts_created": len(self._resource_usage),
                "contexts_cleaned_up": 0,  # Track in real implementation
                "cleanup_success_rate": 1.0,
                "total_memory_allocated_mb": self._total_memory_mb,
                "total_cpu_allocated_percent": self._total_cpu_percent,
                "memory_utilization": self._total_memory_mb / self.max_memory_mb if self.max_memory_mb > 0 else 0,
                "cpu_utilization": self._total_cpu_percent / self.max_cpu_percent if self.max_cpu_percent > 0 else 0,
            }

    def _trigger_degradation(self, action: str, details: dict[str, Any]):
        """Trigger degradation callback."""
        if self._degradation_callback:
            self._degradation_callback(action, details)

    def _start_garbage_collection(self):
        """Start periodic garbage collection."""
        self._gc_active = True

        def gc_worker():
            while self._gc_active:
                try:
                    time.sleep(self.gc_interval_seconds)
                    self._cleanup_stale_resources()
                except Exception as e:
                    logger.error(f"Error in garbage collection: {e}")

        self._gc_thread = threading.Thread(target=gc_worker, daemon=True)
        self._gc_thread.start()

    def _cleanup_stale_resources(self):
        """Clean up stale resource allocations."""
        with self._lock:
            stale_workflows = []
            for workflow_id, usage in self._resource_usage.items():
                if usage.is_stale():
                    stale_workflows.append(workflow_id)

            for workflow_id in stale_workflows:
                logger.warning(f"Cleaning up stale resources for workflow: {workflow_id}")
                self.release_resources(workflow_id)

    def stop(self):
        """Stop the resource manager."""
        self._gc_active = False
        if self._gc_thread:
            self._gc_thread.join(timeout=5.0)

    def set_workflow_limits(self, workflow_id: str, **limits) -> None:
        """Set resource limits for a specific workflow."""
        with self._lock:
            if workflow_id in self._resource_usage:
                usage = self._resource_usage[workflow_id]
                # Apply any memory or CPU limit changes
                if "memory_mb" in limits:
                    usage.memory_mb = limits["memory_mb"]
                if "cpu_percent" in limits:
                    usage.cpu_percent = limits["cpu_percent"]
                usage.last_updated = datetime.now()

    def get_workflow_usage(self, workflow_id: str) -> dict[str, Any]:
        """Get usage information for a specific workflow."""
        with self._lock:
            usage = self._resource_usage.get(workflow_id)
            if not usage:
                return {"error": "Workflow not found"}

            return {
                "workflow_id": workflow_id,
                "memory_mb": usage.memory_mb,
                "cpu_percent": usage.cpu_percent,
                "thread_count": usage.thread_count,
                "file_handles": usage.file_handles,
                "allocated_at": usage.allocated_at.isoformat(),
                "last_updated": usage.last_updated.isoformat(),
            }

    def enforce_resource_limits(self, workflow_id: str) -> bool:
        """Enforce resource limits for a workflow."""
        with self._lock:
            usage = self._resource_usage.get(workflow_id)
            if not usage:
                return False

            # Check if workflow is exceeding limits
            if usage.memory_mb > self.max_memory_mb * 0.8:  # 80% threshold
                logger.warning(f"Workflow {workflow_id} approaching memory limit")
                return False

            if usage.cpu_percent > self.max_cpu_percent * 0.8:  # 80% threshold
                logger.warning(f"Workflow {workflow_id} approaching CPU limit")
                return False

            return True

    def cleanup_workflow_resources(self, workflow_id: str) -> None:
        """Clean up all resources for a workflow."""
        with self._lock:
            self.release_resources(workflow_id)
            # Remove checkpoint
            self._checkpoints.pop(workflow_id, None)

    def get_system_resource_status(self) -> dict[str, Any]:
        """Get current system resource status."""
        try:
            memory_info = self._process.memory_info()
            cpu_percent = self._process.cpu_percent()

            return {
                "process_memory_mb": memory_info.rss / 1024 / 1024,
                "process_cpu_percent": cpu_percent,
                "system_memory_available": psutil.virtual_memory().available / 1024 / 1024,
                "system_cpu_count": psutil.cpu_count(),
                "allocated_memory_mb": self._total_memory_mb,
                "allocated_cpu_percent": self._total_cpu_percent,
                "active_workflows": len(self._resource_usage),
            }
        except Exception as e:
            logger.error(f"Error getting system resource status: {e}")
            return {"error": str(e)}

    def create_circuit_breaker(
        self,
        operation_type: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 30,
        recovery_time_seconds: int = 60,
    ) -> CircuitBreaker:
        """Create a circuit breaker for an operation type."""
        self.configure_circuit_breaker(operation_type, failure_threshold, timeout_seconds, recovery_time_seconds)
        return self._circuit_breakers[operation_type]

    def check_resource_availability(
        self, requested_memory_mb: float, requested_cpu_percent: float, workflow_id: str = None
    ) -> bool:
        """Check if resources are available for allocation."""
        with self._lock:
            new_total_memory = self._total_memory_mb + requested_memory_mb
            new_total_cpu = self._total_cpu_percent + requested_cpu_percent

            return (
                new_total_memory <= self.max_memory_mb
                and new_total_cpu <= self.max_cpu_percent
                and len(self._resource_usage) < self.max_workflows
            )

    def circuit_breaker_context(self, operation_type: str):
        """Context manager for circuit breaker protected operations."""

        class CircuitBreakerContext:
            def __init__(self, manager, op_type):
                self.manager = manager
                self.op_type = op_type

            def __enter__(self):
                # Check if circuit breaker exists and is open
                if self.op_type in self.manager._circuit_breakers:
                    breaker = self.manager._circuit_breakers[self.op_type]
                    if breaker.is_open():
                        raise CircuitBreakerOpenError(f"Circuit breaker is open for operation: {self.op_type}")
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                # Record success or failure
                if self.op_type in self.manager._circuit_breakers:
                    breaker = self.manager._circuit_breakers[self.op_type]
                    if exc_type is None:
                        breaker.record_success()
                    else:
                        breaker.record_failure()
                return False  # Don't suppress exceptions

        return CircuitBreakerContext(self, operation_type)


# Alias for backward compatibility
ResourceManager = WorkflowResourceManager
