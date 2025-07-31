"""Serial execution mode for debugging workflows."""

import asyncio
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SerialExecutionStep:
    """Represents a step to be executed serially."""

    step_id: str
    step_type: str
    step_config: dict[str, Any]
    dependencies: list[str]
    is_parallel_group: bool = False
    parallel_steps: list["SerialExecutionStep"] = None

    def __post_init__(self):
        if self.parallel_steps is None:
            self.parallel_steps = []


class SerialDebugMode:
    """Manages serial execution mode for debugging parallel workflows."""

    def __init__(self):
        """Initialize serial debug mode."""
        self._lock = threading.RLock()

        # Execution state
        self._serial_mode_active = False
        self._current_workflow_id: str | None = None
        self._execution_queue: list[SerialExecutionStep] = []
        self._executed_steps: set[str] = set()

        # Step control
        self._pause_between_steps = False
        self._step_delay_seconds = 0.0
        self._continue_event = threading.Event()
        self._continue_event.set()  # Start in running state

        # Callbacks
        self._before_step_callback: Callable | None = None
        self._after_step_callback: Callable | None = None

    def enable_serial_mode(self, workflow_id: str):
        """Enable serial mode for a workflow."""
        with self._lock:
            self._serial_mode_active = True
            self._current_workflow_id = workflow_id
            self._execution_queue.clear()
            self._executed_steps.clear()
            logger.info(f"Serial debug mode enabled for workflow {workflow_id}")

    def disable_serial_mode(self):
        """Disable serial mode."""
        with self._lock:
            self._serial_mode_active = False
            self._current_workflow_id = None
            self._continue_event.set()  # Release any waiting steps
            logger.info("Serial debug mode disabled")

    def is_active(self) -> bool:
        """Check if serial mode is active."""
        return self._serial_mode_active

    def convert_parallel_to_serial(self, parallel_steps: list[dict[str, Any]]) -> list[SerialExecutionStep]:
        """Convert parallel steps to serial execution order."""
        with self._lock:
            if not self._serial_mode_active:
                return []

            serial_steps = []

            for step in parallel_steps:
                serial_step = SerialExecutionStep(
                    step_id=step.get("id", f"step_{len(serial_steps)}"),
                    step_type=step.get("type", "unknown"),
                    step_config=step,
                    dependencies=step.get("depends_on", []),
                )

                # Check if this step contains parallel sub-steps
                if "parallel_steps" in step:
                    serial_step.is_parallel_group = True
                    serial_step.parallel_steps = self.convert_parallel_to_serial(step["parallel_steps"])

                serial_steps.append(serial_step)

            # Sort by dependencies
            sorted_steps = self._topological_sort(serial_steps)

            return sorted_steps

    def queue_step(self, step: SerialExecutionStep):
        """Queue a step for serial execution."""
        with self._lock:
            if self._serial_mode_active:
                self._execution_queue.append(step)
                logger.debug(f"Queued step {step.step_id} for serial execution")

    def get_next_step(self) -> SerialExecutionStep | None:
        """Get the next step to execute."""
        with self._lock:
            if not self._execution_queue:
                return None

            # Find next step with satisfied dependencies
            for i, step in enumerate(self._execution_queue):
                if all(dep in self._executed_steps for dep in step.dependencies):
                    return self._execution_queue.pop(i)

            # No step with satisfied dependencies
            return None

    def mark_step_executed(self, step_id: str):
        """Mark a step as executed."""
        with self._lock:
            self._executed_steps.add(step_id)
            logger.debug(f"Marked step {step_id} as executed")

    def wait_before_step(self, step: SerialExecutionStep) -> bool:
        """Wait before executing a step (for debugging)."""
        if not self._serial_mode_active:
            return True

        # Call before-step callback
        if self._before_step_callback:
            try:
                self._before_step_callback(step)
            except Exception as e:
                logger.error(f"Error in before-step callback: {e}")

        # Apply step delay
        if self._step_delay_seconds > 0:
            time.sleep(self._step_delay_seconds)

        # Wait for continue if paused
        if self._pause_between_steps:
            logger.info(f"Paused before step {step.step_id}. Waiting for continue...")
            self._continue_event.wait()

            # Reset for next step
            if self._pause_between_steps:
                self._continue_event.clear()

        return True

    def complete_step(self, step: SerialExecutionStep, result: Any, error: Exception | None = None):
        """Complete a step execution."""
        if not self._serial_mode_active:
            return

        # Mark as executed
        self.mark_step_executed(step.step_id)

        # Call after-step callback
        if self._after_step_callback:
            try:
                self._after_step_callback(step, result, error)
            except Exception as e:
                logger.error(f"Error in after-step callback: {e}")

    def set_pause_between_steps(self, pause: bool):
        """Enable or disable pausing between steps."""
        with self._lock:
            self._pause_between_steps = pause
            if not pause:
                self._continue_event.set()

    def continue_execution(self):
        """Continue execution from a pause."""
        self._continue_event.set()

    def set_step_delay(self, delay_seconds: float):
        """Set delay between steps."""
        with self._lock:
            self._step_delay_seconds = max(0, delay_seconds)

    def set_before_step_callback(self, callback: Callable):
        """Set callback to be called before each step."""
        self._before_step_callback = callback

    def set_after_step_callback(self, callback: Callable):
        """Set callback to be called after each step."""
        self._after_step_callback = callback

    def get_execution_state(self) -> dict[str, Any]:
        """Get current execution state."""
        with self._lock:
            return {
                "active": self._serial_mode_active,
                "workflow_id": self._current_workflow_id,
                "queued_steps": len(self._execution_queue),
                "executed_steps": len(self._executed_steps),
                "paused": self._pause_between_steps and not self._continue_event.is_set(),
                "step_delay": self._step_delay_seconds,
            }

    def get_queue_info(self) -> list[dict[str, Any]]:
        """Get information about queued steps."""
        with self._lock:
            return [
                {
                    "step_id": step.step_id,
                    "step_type": step.step_type,
                    "dependencies": step.dependencies,
                    "ready": all(dep in self._executed_steps for dep in step.dependencies),
                }
                for step in self._execution_queue
            ]

    def _topological_sort(self, steps: list[SerialExecutionStep]) -> list[SerialExecutionStep]:
        """Sort steps topologically based on dependencies."""
        # Build dependency graph
        graph = {step.step_id: step.dependencies for step in steps}
        step_map = {step.step_id: step for step in steps}

        # Find steps with no dependencies
        no_deps = [step for step in steps if not step.dependencies]
        sorted_steps = []

        while no_deps:
            # Take a step with no dependencies
            current = no_deps.pop(0)
            sorted_steps.append(current)

            # Remove this step from other dependencies
            current_id = current.step_id
            for step_id, deps in graph.items():
                if current_id in deps:
                    deps.remove(current_id)
                    if not deps and step_id != current_id:
                        step = step_map[step_id]
                        if step not in sorted_steps and step not in no_deps:
                            no_deps.append(step)

        # Add any remaining steps (might have circular dependencies)
        for step in steps:
            if step not in sorted_steps:
                sorted_steps.append(step)

        return sorted_steps


class AsyncSerialDebugMode(SerialDebugMode):
    """Async version of serial debug mode."""

    def __init__(self):
        """Initialize async serial debug mode."""
        super().__init__()
        self._async_continue_event = asyncio.Event()
        self._async_continue_event.set()

    async def wait_before_step_async(self, step: SerialExecutionStep) -> bool:
        """Async wait before executing a step."""
        if not self._serial_mode_active:
            return True

        # Call before-step callback
        if self._before_step_callback:
            try:
                if asyncio.iscoroutinefunction(self._before_step_callback):
                    await self._before_step_callback(step)
                else:
                    self._before_step_callback(step)
            except Exception as e:
                logger.error(f"Error in before-step callback: {e}")

        # Apply step delay
        if self._step_delay_seconds > 0:
            await asyncio.sleep(self._step_delay_seconds)

        # Wait for continue if paused
        if self._pause_between_steps:
            logger.info(f"Paused before step {step.step_id}. Waiting for continue...")
            await self._async_continue_event.wait()

            # Reset for next step
            if self._pause_between_steps:
                self._async_continue_event.clear()

        return True

    async def complete_step_async(self, step: SerialExecutionStep, result: Any, error: Exception | None = None):
        """Complete a step execution asynchronously."""
        if not self._serial_mode_active:
            return

        # Mark as executed
        self.mark_step_executed(step.step_id)

        # Call after-step callback
        if self._after_step_callback:
            try:
                if asyncio.iscoroutinefunction(self._after_step_callback):
                    await self._after_step_callback(step, result, error)
                else:
                    self._after_step_callback(step, result, error)
            except Exception as e:
                logger.error(f"Error in after-step callback: {e}")

    def continue_execution_async(self):
        """Continue async execution from a pause."""
        self._async_continue_event.set()
        self._continue_event.set()

    def set_pause_between_steps(self, pause: bool):
        """Enable or disable pausing between steps."""
        super().set_pause_between_steps(pause)
        if not pause:
            self._async_continue_event.set()
