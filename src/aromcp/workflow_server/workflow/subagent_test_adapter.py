"""Test adapter for SubAgentManager to support Phase 2 tests."""

import logging
import threading
import time
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SubAgentManager:
    """Test-compatible SubAgentManager for resource management tests."""
    
    def __init__(self, workflow_id: str, state_manager: Any):
        """Initialize sub-agent manager for testing."""
        self.workflow_id = workflow_id
        self.state_manager = state_manager
        
        # Resource tracking
        self._lock = threading.RLock()
        self._active_contexts = {}
        self._status_callback = None
        self._resource_tracking_enabled = False
        self._memory_monitoring_enabled = False
        
        # Execution tracking
        self._execution_results = {}
        self._monitoring_data = {
            "total_subagents": 0,
            "completed_subagents": 0,
            "failed_subagents": 0,
            "contexts_created": 0,
            "contexts_cleaned_up": 0
        }
    
    def execute_subagent(self, item: dict[str, Any], task_def: dict[str, Any]) -> dict[str, Any]:
        """Execute a sub-agent task (mocked for testing)."""
        # This will be mocked in tests
        raise NotImplementedError("Should be mocked in tests")
    
    def execute_parallel_tasks(self, work_items: list[dict[str, Any]], task_definitions: dict[str, Any],
                             timeout_seconds: float = None, max_parallel: int = 10,
                             error_isolation: bool = False) -> dict[str, Any]:
        """Execute tasks in parallel with resource management."""
        with self._lock:
            self._monitoring_data["total_subagents"] = len(work_items)
            results = {}
            
            # Track active contexts
            for item in work_items:
                item_id = item.get("id", item.get("task", "unknown"))
                self._active_contexts[item_id] = {
                    "status": "active",
                    "start_time": time.time()
                }
                self._monitoring_data["contexts_created"] += 1
            
            # Execute tasks (simplified for testing)
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
                futures = {}
                
                for item in work_items:
                    item_id = item.get("id", item.get("task", "unknown"))
                    task_name = item.get("task", "default")
                    
                    # Get task definition
                    if isinstance(task_definitions, dict) and task_name in task_definitions:
                        task_def = task_definitions[task_name]
                    else:
                        task_def = task_definitions
                    
                    # Submit task
                    future = executor.submit(self._execute_with_timeout, item, task_def, timeout_seconds, error_isolation)
                    futures[future] = item_id
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    item_id = futures[future]
                    try:
                        result = future.result()
                        results[item_id] = result
                        
                        if result.get("status") == "completed":
                            self._monitoring_data["completed_subagents"] += 1
                        else:
                            self._monitoring_data["failed_subagents"] += 1
                            
                    except Exception as e:
                        results[item_id] = {"status": "failed", "error": str(e)}
                        self._monitoring_data["failed_subagents"] += 1
                    
                    # Clean up context
                    self._cleanup_context(item_id)
            
            return results
    
    def _execute_with_timeout(self, item: dict[str, Any], task_def: dict[str, Any],
                            timeout_seconds: Optional[float], error_isolation: bool) -> dict[str, Any]:
        """Execute a task with timeout handling."""
        item_id = item.get("id", item.get("task", "unknown"))
        
        try:
            # Update status
            if self._status_callback:
                self._status_callback(item_id, "starting")
            
            # Execute with timeout if specified
            if timeout_seconds:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self.execute_subagent, item, task_def)
                    try:
                        result = future.result(timeout=timeout_seconds)
                        return result
                    except concurrent.futures.TimeoutError:
                        if error_isolation:
                            return {"status": "timeout", "error": f"Task {item_id} timed out after {timeout_seconds}s"}
                        raise TimeoutError(f"Sub-agent {item_id} timed out")
            else:
                return self.execute_subagent(item, task_def)
                
        except Exception as e:
            if error_isolation:
                return {"status": "failed", "error": str(e)}
            raise
    
    def _cleanup_context(self, item_id: str):
        """Clean up context for an item."""
        with self._lock:
            if item_id in self._active_contexts:
                del self._active_contexts[item_id]
                self._monitoring_data["contexts_cleaned_up"] += 1
    
    def set_status_callback(self, callback: Callable):
        """Set status update callback."""
        self._status_callback = callback
    
    def enable_resource_tracking(self, enabled: bool):
        """Enable resource tracking."""
        self._resource_tracking_enabled = enabled
    
    def enable_memory_monitoring(self, enabled: bool):
        """Enable memory monitoring."""
        self._memory_monitoring_enabled = enabled
    
    def get_active_contexts(self) -> list[str]:
        """Get list of active contexts."""
        with self._lock:
            return list(self._active_contexts.keys())
    
    def get_monitoring_summary(self) -> dict[str, Any]:
        """Get monitoring summary."""
        with self._lock:
            data = self._monitoring_data.copy()
            if data["total_subagents"] > 0:
                data["success_rate"] = data["completed_subagents"] / data["total_subagents"]
            else:
                data["success_rate"] = 0.0
            
            # Add average execution time (mock value for tests)
            data["average_execution_time"] = 0.2  # Mock average
            
            return data
    
    def get_resource_summary(self) -> dict[str, Any]:
        """Get resource usage summary."""
        with self._lock:
            return {
                "contexts_created": self._monitoring_data["contexts_created"],
                "contexts_cleaned_up": self._monitoring_data["contexts_cleaned_up"],
                "cleanup_success_rate": self._monitoring_data["contexts_cleaned_up"] / self._monitoring_data["contexts_created"] if self._monitoring_data["contexts_created"] > 0 else 0.0
            }
    
    def get_memory_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        import psutil
        process = psutil.Process()
        
        return {
            "peak_memory_usage": process.memory_info().rss,
            "contexts_created": self._monitoring_data["contexts_created"],
            "average_memory_per_context": process.memory_info().rss / self._monitoring_data["contexts_created"] if self._monitoring_data["contexts_created"] > 0 else 0
        }