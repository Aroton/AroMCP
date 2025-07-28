"""Timeout management for the MCP Workflow System."""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeoutConfig:
    """Configuration for timeout handling."""
    
    timeout_seconds: float
    warning_threshold: float = 0.8  # Warn at 80% of timeout
    grace_period_seconds: float = 5.0  # Extra time before hard kill
    
    @property
    def warning_seconds(self) -> float:
        """Calculate when to issue warning."""
        return self.timeout_seconds * self.warning_threshold


@dataclass
class TimeoutContext:
    """Context for a timeout operation."""
    
    id: str
    timeout_config: TimeoutConfig
    start_time: datetime
    end_time: Optional[datetime] = None
    warned: bool = False
    timed_out: bool = False
    cancelled: bool = False
    parent_id: Optional[str] = None
    children: list[str] = field(default_factory=list)
    
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    def remaining_seconds(self) -> float:
        """Get remaining time before timeout."""
        elapsed = self.elapsed_seconds()
        return max(0, self.timeout_config.timeout_seconds - elapsed)
    
    def should_warn(self) -> bool:
        """Check if warning should be issued."""
        if self.warned or self.timed_out:
            return False
        return self.elapsed_seconds() >= self.timeout_config.warning_seconds
    
    def is_timed_out(self) -> bool:
        """Check if operation has timed out."""
        if self.timed_out or self.cancelled:
            return self.timed_out
        return self.elapsed_seconds() >= self.timeout_config.timeout_seconds


class TimeoutManager:
    """Manages hierarchical timeouts for workflow execution."""
    
    def __init__(self):
        """Initialize timeout manager."""
        self._lock = threading.RLock()
        self._contexts: dict[str, TimeoutContext] = {}
        self._callbacks: dict[str, Callable] = {}
        self._warning_callbacks: dict[str, Callable] = {}
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_active = False
        self._start_monitoring()
    
    def create_timeout(self, 
                      id: str,
                      timeout_seconds: float,
                      parent_id: Optional[str] = None,
                      warning_callback: Optional[Callable] = None,
                      timeout_callback: Optional[Callable] = None) -> TimeoutContext:
        """Create a new timeout context."""
        with self._lock:
            # Create timeout config
            config = TimeoutConfig(timeout_seconds=timeout_seconds)
            
            # Create context
            context = TimeoutContext(
                id=id,
                timeout_config=config,
                start_time=datetime.now(),
                parent_id=parent_id
            )
            
            # Register context
            self._contexts[id] = context
            
            # Register callbacks
            if warning_callback:
                self._warning_callbacks[id] = warning_callback
            if timeout_callback:
                self._callbacks[id] = timeout_callback
            
            # Update parent-child relationships
            if parent_id and parent_id in self._contexts:
                self._contexts[parent_id].children.append(id)
            
            return context
    
    def complete_timeout(self, id: str) -> Optional[TimeoutContext]:
        """Mark a timeout as completed."""
        with self._lock:
            if id not in self._contexts:
                return None
            
            context = self._contexts[id]
            context.end_time = datetime.now()
            
            # Clean up callbacks
            self._callbacks.pop(id, None)
            self._warning_callbacks.pop(id, None)
            
            return context
    
    def cancel_timeout(self, id: str, cascade: bool = True) -> list[str]:
        """Cancel a timeout and optionally its children."""
        with self._lock:
            cancelled = []
            
            if id not in self._contexts:
                return cancelled
            
            context = self._contexts[id]
            context.cancelled = True
            context.end_time = datetime.now()
            cancelled.append(id)
            
            # Clean up callbacks
            self._callbacks.pop(id, None)
            self._warning_callbacks.pop(id, None)
            
            # Cascade cancellation to children
            if cascade:
                for child_id in context.children:
                    cancelled.extend(self.cancel_timeout(child_id, cascade=True))
            
            return cancelled
    
    def extend_timeout(self, id: str, additional_seconds: float) -> bool:
        """Extend an existing timeout."""
        with self._lock:
            if id not in self._contexts:
                return False
            
            context = self._contexts[id]
            if context.timed_out or context.cancelled:
                return False
            
            # Update timeout config
            context.timeout_config.timeout_seconds += additional_seconds
            return True
    
    def get_timeout_status(self, id: str) -> Optional[dict[str, Any]]:
        """Get status of a timeout."""
        with self._lock:
            if id not in self._contexts:
                return None
            
            context = self._contexts[id]
            # Use real-time timeout check for current status
            current_timed_out = context.is_timed_out()
            return {
                "id": id,
                "elapsed_seconds": context.elapsed_seconds(),
                "remaining_seconds": context.remaining_seconds(),
                "timeout_seconds": context.timeout_config.timeout_seconds,
                "warned": context.warned,
                "timed_out": current_timed_out,
                "exceeded": current_timed_out,  # Alias for timed_out for backward compatibility
                "cancelled": context.cancelled,
                "parent_id": context.parent_id,
                "children": context.children.copy()
            }
    
    def get_hierarchical_timeouts(self, root_id: str) -> dict[str, Any]:
        """Get hierarchical timeout tree."""
        with self._lock:
            if root_id not in self._contexts:
                return {}
            
            def build_tree(id: str) -> dict[str, Any]:
                context = self._contexts[id]
                status = self.get_timeout_status(id)
                status["children"] = [build_tree(child_id) for child_id in context.children]
                return status
            
            return build_tree(root_id)
    
    def coordinate_hierarchical_timeouts(self, parent_id: str, child_timeouts: dict[str, float]) -> dict[str, TimeoutContext]:
        """Coordinate timeouts in a hierarchy."""
        with self._lock:
            if parent_id not in self._contexts:
                raise ValueError(f"Parent timeout {parent_id} not found")
            
            parent_context = self._contexts[parent_id]
            parent_remaining = parent_context.remaining_seconds()
            
            created_contexts = {}
            
            for child_id, child_timeout in child_timeouts.items():
                # Ensure child timeout doesn't exceed parent
                adjusted_timeout = min(child_timeout, parent_remaining)
                
                # Create child timeout
                context = self.create_timeout(
                    id=child_id,
                    timeout_seconds=adjusted_timeout,
                    parent_id=parent_id
                )
                
                created_contexts[child_id] = context
            
            return created_contexts
    
    def _start_monitoring(self):
        """Start the timeout monitoring thread."""
        self._monitor_active = True
        
        def monitor_timeouts():
            while self._monitor_active:
                try:
                    self._check_timeouts()
                    time.sleep(0.5)  # Check every 500ms
                except Exception as e:
                    logger.error(f"Error in timeout monitoring: {e}")
        
        self._monitor_thread = threading.Thread(target=monitor_timeouts, daemon=True)
        self._monitor_thread.start()
    
    def _check_timeouts(self):
        """Check for warnings and timeouts."""
        with self._lock:
            for id, context in list(self._contexts.items()):
                if context.cancelled or context.end_time:
                    continue
                
                # Check for warning
                if context.should_warn() and id in self._warning_callbacks:
                    try:
                        self._warning_callbacks[id](id, context.remaining_seconds())
                        context.warned = True
                    except Exception as e:
                        logger.error(f"Error in warning callback for {id}: {e}")
                
                # Check for timeout
                if context.is_timed_out() and not context.timed_out:
                    context.timed_out = True
                    context.end_time = datetime.now()
                    
                    if id in self._callbacks:
                        try:
                            self._callbacks[id](id)
                        except Exception as e:
                            logger.error(f"Error in timeout callback for {id}: {e}")
                    
                    # Cascade timeout to children
                    for child_id in context.children:
                        self._trigger_timeout(child_id)
    
    def _trigger_timeout(self, id: str):
        """Trigger timeout for a context."""
        if id not in self._contexts:
            return
        
        context = self._contexts[id]
        if not context.timed_out:
            context.timed_out = True
            context.end_time = datetime.now()
            
            if id in self._callbacks:
                try:
                    self._callbacks[id](id)
                except Exception as e:
                    logger.error(f"Error in cascaded timeout callback for {id}: {e}")
            
            # Cascade to children
            for child_id in context.children:
                self._trigger_timeout(child_id)
    
    def stop(self):
        """Stop the timeout manager."""
        self._monitor_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
    
    def clear_completed_timeouts(self):
        """Clean up completed timeout contexts."""
        with self._lock:
            completed_ids = [
                id for id, context in self._contexts.items()
                if context.end_time and (datetime.now() - context.end_time).total_seconds() > 300  # 5 minutes
            ]
            
            for id in completed_ids:
                del self._contexts[id]
                self._callbacks.pop(id, None)
                self._warning_callbacks.pop(id, None)
    
    def set_step_timeout(self, step_id: str, timeout_seconds: float) -> None:
        """Set timeout for a specific step."""
        with self._lock:
            # If timeout already exists, update it
            if step_id in self._contexts:
                self._contexts[step_id].timeout_config.timeout_seconds = timeout_seconds
            else:
                self.create_timeout(step_id, timeout_seconds)
    
    def set_workflow_timeout(self, workflow_id: str, timeout_seconds: float, cleanup_callback: Optional[Callable] = None) -> None:
        """Set timeout for a specific workflow."""
        self.create_timeout(workflow_id, timeout_seconds, timeout_callback=cleanup_callback)
    
    def get_remaining_time(self, operation_id: str) -> float:
        """Get remaining time for an operation."""
        with self._lock:
            if operation_id not in self._contexts:
                return 0.0
            return self._contexts[operation_id].remaining_seconds()
    
    def send_warning(self, operation_id: str, warning_threshold: float) -> None:
        """Send warning for timeout approaching."""
        with self._lock:
            if operation_id in self._contexts:
                context = self._contexts[operation_id]
                if context.elapsed_seconds() >= warning_threshold:
                    context.warned = True
                    logger.warning(f"Timeout warning for {operation_id}: {context.remaining_seconds():.1f}s remaining")
    
    def coordinate_nested_timeouts(self, parent_id: str, child_id: str) -> None:
        """Coordinate nested timeouts to ensure child doesn't exceed parent."""
        with self._lock:
            if parent_id in self._contexts and child_id in self._contexts:
                parent_context = self._contexts[parent_id]
                child_context = self._contexts[child_id]
                
                # Ensure child timeout doesn't exceed parent remaining time
                parent_remaining = parent_context.remaining_seconds()
                if child_context.timeout_config.timeout_seconds > parent_remaining:
                    child_context.timeout_config.timeout_seconds = parent_remaining
                
                # Update parent-child relationship
                if child_id not in parent_context.children:
                    parent_context.children.append(child_id)
                child_context.parent_id = parent_id
    
    def start_step(self, step_id: str, parent_step: str | None = None, workflow_id: str | None = None) -> None:
        """Start monitoring a step (alias for create_timeout with default timeout)."""
        with self._lock:
            # Use workflow_id as parent if specified and no explicit parent
            parent_id = parent_step or workflow_id
            
            if step_id not in self._contexts:
                self.create_timeout(step_id, 30.0, parent_id=parent_id)  # Default 30 second timeout
            else:
                # Reset the start time to begin timeout monitoring from now, but preserve existing timeout config
                context = self._contexts[step_id]
                context.start_time = datetime.now()
                context.end_time = None
                context.warned = False
                context.timed_out = False
                context.cancelled = False
                
                # Update parent relationship if specified
                if parent_id and parent_id in self._contexts:
                    context.parent_id = parent_id
                    if step_id not in self._contexts[parent_id].children:
                        self._contexts[parent_id].children.append(step_id)
            
            # Coordinate nested timeouts if parent is specified
            if parent_id and parent_id in self._contexts:
                self.coordinate_nested_timeouts(parent_id, step_id)
    
    def check_timeout(self, operation_id: str) -> bool:
        """Check if an operation has timed out."""
        with self._lock:
            if operation_id not in self._contexts:
                return False
            return self._contexts[operation_id].is_timed_out()
    
    def start_workflow(self, workflow_id: str) -> None:
        """Start monitoring a workflow."""
        with self._lock:
            if workflow_id not in self._contexts:
                # Create default workflow timeout if not set
                self.create_timeout(workflow_id, 300.0)  # Default 5 minute timeout
            else:
                # Reset the start time to begin timeout monitoring from now
                context = self._contexts[workflow_id]
                context.start_time = datetime.now()
                context.end_time = None
                context.warned = False
                context.timed_out = False
                context.cancelled = False
    
    def end_step(self, step_id: str) -> None:
        """End monitoring a step."""
        self.complete_timeout(step_id)
    
    def check_workflow_timeout(self, workflow_id: str) -> bool:
        """Check if a workflow has timed out."""
        return self.check_timeout(workflow_id)
    
    def get_cascade_info(self, operation_id: str) -> dict[str, Any]:
        """Get cascade information for an operation."""
        with self._lock:
            if operation_id not in self._contexts:
                return {"child_timeouts": []}
            
            context = self._contexts[operation_id]
            child_info = {}
            for child_id in context.children:
                if child_id in self._contexts:
                    child_context = self._contexts[child_id]
                    child_info[child_id] = {
                        "timeout_seconds": child_context.timeout_config.timeout_seconds,
                        "elapsed_seconds": child_context.elapsed_seconds(),
                        "remaining_seconds": child_context.remaining_seconds(),
                        "timed_out": child_context.is_timed_out()
                    }
            
            return {
                "child_timeouts": list(context.children),
                "child_info": child_info,
                "parent_id": context.parent_id
            }
    
    def handle_timeout(self, operation_id: str) -> None:
        """Handle timeout for an operation by triggering cleanup callbacks."""
        with self._lock:
            if operation_id in self._callbacks:
                try:
                    callback = self._callbacks[operation_id]
                    # Try calling with no arguments first, then with operation_id
                    try:
                        callback()
                    except TypeError:
                        callback(operation_id)
                    logger.info(f"Timeout cleanup callback executed for {operation_id}")
                except Exception as e:
                    logger.error(f"Error in timeout cleanup callback for {operation_id}: {e}")
            
            # Complete the timeout to clean up
            self.complete_timeout(operation_id)


class AsyncTimeoutManager(TimeoutManager):
    """Async version of timeout manager for async workflows."""
    
    def __init__(self):
        """Initialize async timeout manager."""
        super().__init__()
        self._async_tasks: dict[str, asyncio.Task] = {}
    
    async def create_async_timeout(self,
                                  id: str,
                                  timeout_seconds: float,
                                  parent_id: Optional[str] = None,
                                  warning_callback: Optional[Callable] = None,
                                  timeout_callback: Optional[Callable] = None) -> TimeoutContext:
        """Create an async timeout with automatic monitoring."""
        # Create the timeout context
        context = self.create_timeout(id, timeout_seconds, parent_id, warning_callback, timeout_callback)
        
        # Create async monitoring task
        async def monitor_async():
            try:
                # Wait for warning threshold
                warning_time = timeout_seconds * 0.8
                await asyncio.sleep(warning_time)
                
                if not context.cancelled and not context.timed_out and warning_callback:
                    await warning_callback(id, context.remaining_seconds())
                    context.warned = True
                
                # Wait for remaining time
                remaining = context.remaining_seconds()
                if remaining > 0:
                    await asyncio.sleep(remaining)
                
                # Trigger timeout
                if not context.cancelled and not context.timed_out:
                    context.timed_out = True
                    context.end_time = datetime.now()
                    if timeout_callback:
                        await timeout_callback(id)
                        
            except asyncio.CancelledError:
                pass
            finally:
                self._async_tasks.pop(id, None)
        
        # Start monitoring task
        task = asyncio.create_task(monitor_async())
        self._async_tasks[id] = task
        
        return context
    
    async def complete_async_timeout(self, id: str) -> Optional[TimeoutContext]:
        """Complete an async timeout and cancel monitoring."""
        # Cancel monitoring task
        if id in self._async_tasks:
            self._async_tasks[id].cancel()
            try:
                await self._async_tasks[id]
            except asyncio.CancelledError:
                pass
            del self._async_tasks[id]
        
        # Complete the timeout
        return self.complete_timeout(id)
    
    async def cancel_async_timeout(self, id: str, cascade: bool = True) -> list[str]:
        """Cancel an async timeout and its monitoring."""
        # Cancel monitoring tasks
        to_cancel = [id]
        if cascade and id in self._contexts:
            to_cancel.extend(self._contexts[id].children)
        
        for cancel_id in to_cancel:
            if cancel_id in self._async_tasks:
                self._async_tasks[cancel_id].cancel()
                try:
                    await self._async_tasks[cancel_id]
                except asyncio.CancelledError:
                    pass
                del self._async_tasks[cancel_id]
        
        # Cancel the timeouts
        return self.cancel_timeout(id, cascade)