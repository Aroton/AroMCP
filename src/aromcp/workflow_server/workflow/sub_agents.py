"""Sub-agent management for parallel workflow execution.

This module handles the creation, tracking, and coordination of sub-agents
that execute workflow tasks in parallel.
"""

import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..prompts.standards import StandardPrompts
from .parallel import SubAgentContext


@dataclass
class SubAgentRegistration:
    """Registration information for a sub-agent."""

    agent_id: str
    task_id: str
    workflow_id: str
    context: SubAgentContext
    prompt: str
    status: str = "registered"  # registered, active, completed, failed
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    last_activity: float = field(default_factory=time.time)
    step_count: int = 0
    error: str | None = None


@dataclass
class SubAgentTask:
    """Definition of a task that can be executed by sub-agents."""

    task_name: str
    steps: list[dict[str, Any]]
    description: str | None = None
    timeout_seconds: int | None = None
    max_retries: int = 0


class SubAgentManager:
    """Manages sub-agent lifecycle and coordination."""

    def __init__(self):
        self._agents: dict[str, SubAgentRegistration] = {}
        self._task_definitions: dict[str, SubAgentTask] = {}
        self._workflow_agents: dict[str, set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        self._activity_timeout = 300  # 5 minutes

    def register_task_definition(
        self,
        task_name: str,
        steps: list[dict[str, Any]],
        description: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int = 0,
    ) -> bool:
        """Register a task definition that sub-agents can execute."""
        task = SubAgentTask(
            task_name=task_name,
            steps=steps,
            description=description,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        with self._lock:
            self._task_definitions[task_name] = task
        return True

    def create_sub_agent(
        self,
        workflow_id: str,
        task_id: str,
        task_name: str,
        context: dict[str, Any],
        parent_step_id: str,
        custom_prompt: str | None = None,
    ) -> SubAgentRegistration | None:
        """Create and register a new sub-agent.

        Args:
            workflow_id: Parent workflow ID
            task_id: Unique task identifier
            task_name: Name of task definition to execute
            context: Context data for the sub-agent
            parent_step_id: ID of parent step that created this sub-agent
            custom_prompt: Custom prompt override

        Returns:
            SubAgentRegistration if successful, None otherwise
        """
        # Validate task definition exists
        with self._lock:
            if task_name not in self._task_definitions:
                return None

        # Generate unique agent ID
        agent_id = f"agent_{uuid.uuid4().hex[:12]}"

        # Create sub-agent context
        sub_context = SubAgentContext(
            task_id=task_id, workflow_id=workflow_id, context=context, parent_step_id=parent_step_id
        )

        # Generate appropriate prompt
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt_context = {
                "task_id": task_id,
                "context": context,
                **context,  # Include context variables directly
            }
            prompt = StandardPrompts.create_sub_agent_prompt(
                task_id=task_id, task_type="sub_agent_base", context=prompt_context
            )

        # Create registration
        registration = SubAgentRegistration(
            agent_id=agent_id, task_id=task_id, workflow_id=workflow_id, context=sub_context, prompt=prompt
        )

        # Store registration
        with self._lock:
            self._agents[agent_id] = registration
            self._workflow_agents[workflow_id].add(agent_id)

        return registration

    def get_agent(self, agent_id: str) -> SubAgentRegistration | None:
        """Get sub-agent registration by ID."""
        with self._lock:
            return self._agents.get(agent_id)

    def get_agent_by_task_id(self, workflow_id: str, task_id: str) -> SubAgentRegistration | None:
        """Get sub-agent by workflow and task ID."""
        with self._lock:
            workflow_agents = self._workflow_agents.get(workflow_id, set())
            for agent_id in workflow_agents:
                agent = self._agents.get(agent_id)
                if agent and agent.task_id == task_id:
                    return agent
        return None

    def update_agent_status(self, agent_id: str, status: str, error: str | None = None) -> bool:
        """Update sub-agent status."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False

            old_status = agent.status
            agent.status = status
            agent.last_activity = time.time()

            if status == "active" and old_status == "registered":
                agent.started_at = time.time()
            elif status in ("completed", "failed"):
                agent.completed_at = time.time()
                if error:
                    agent.error = error

            return True

    def record_agent_activity(self, agent_id: str, step_completed: bool = False) -> bool:
        """Record activity for an agent."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False

            agent.last_activity = time.time()
            if step_completed:
                agent.step_count += 1

            return True

    def get_workflow_agents(self, workflow_id: str) -> list[SubAgentRegistration]:
        """Get all sub-agents for a workflow."""
        with self._lock:
            agent_ids = self._workflow_agents.get(workflow_id, set())
            return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_active_agents(self, workflow_id: str | None = None) -> list[SubAgentRegistration]:
        """Get all active sub-agents, optionally filtered by workflow."""
        with self._lock:
            if workflow_id:
                agents = self.get_workflow_agents(workflow_id)
                return [a for a in agents if a.status == "active"]
            else:
                return [a for a in self._agents.values() if a.status == "active"]

    def get_task_definition(self, task_name: str) -> SubAgentTask | None:
        """Get task definition by name."""
        with self._lock:
            return self._task_definitions.get(task_name)

    def get_filtered_steps_for_agent(self, agent_id: str, current_step_index: int = 0) -> list[dict[str, Any]]:
        """Get filtered workflow steps for a specific sub-agent.

        This filters the workflow steps to only include those relevant
        to the sub-agent's task.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return []

            # Get task definition
            context = agent.context
            task_def = self._task_definitions.get(context.context.get("task_type", "default"))
            if not task_def:
                return []

            # Filter steps based on sub-agent context
            filtered_steps = []
            for step in task_def.steps:
                # Replace variables in step with sub-agent context
                filtered_step = self._replace_step_variables(step, agent.context.context)
                filtered_steps.append(filtered_step)

            return filtered_steps[current_step_index:]

    def _replace_step_variables(self, step: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        """Replace variables in a step definition with context values."""
        import copy
        import re

        # Deep copy to avoid modifying original
        replaced_step = copy.deepcopy(step)

        def replace_in_value(value):
            if isinstance(value, str):
                # Replace {{ variable }} patterns
                pattern = r"\{\{\s*(\w+)\s*\}\}"

                def replacer(match):
                    var_name = match.group(1)
                    return str(context.get(var_name, match.group(0)))

                return re.sub(pattern, replacer, value)
            elif isinstance(value, dict):
                return {k: replace_in_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [replace_in_value(item) for item in value]
            else:
                return value

        return replace_in_value(replaced_step)

    def cleanup_inactive_agents(self, max_age_seconds: int = 3600) -> int:
        """Clean up inactive or old sub-agents.

        Returns:
            Number of agents cleaned up
        """
        current_time = time.time()
        cleanup_count = 0

        with self._lock:
            agents_to_remove = []

            for agent_id, agent in self._agents.items():
                # Clean up if completed/failed and old enough
                if agent.status in ("completed", "failed"):
                    if current_time - agent.last_activity > max_age_seconds:
                        agents_to_remove.append(agent_id)

                # Clean up if inactive for too long
                elif current_time - agent.last_activity > self._activity_timeout:
                    # Mark as failed due to timeout
                    agent.status = "failed"
                    agent.error = "Agent activity timeout"
                    agent.completed_at = current_time
                    agents_to_remove.append(agent_id)

            # Remove agents
            for agent_id in agents_to_remove:
                agent = self._agents.pop(agent_id, None)
                if agent:
                    self._workflow_agents[agent.workflow_id].discard(agent_id)
                    cleanup_count += 1

        return cleanup_count

    def get_agent_stats(self, workflow_id: str | None = None) -> dict[str, Any]:
        """Get statistics about sub-agents."""
        with self._lock:
            if workflow_id:
                agents = self.get_workflow_agents(workflow_id)
            else:
                agents = list(self._agents.values())

            stats = {
                "total_agents": len(agents),
                "by_status": defaultdict(int),
                "average_steps": 0,
                "active_duration": 0,
                "oldest_agent_age": 0,
            }

            if agents:
                current_time = time.time()
                total_steps = 0
                active_durations = []
                oldest_age = 0

                for agent in agents:
                    stats["by_status"][agent.status] += 1
                    total_steps += agent.step_count

                    age = current_time - agent.created_at
                    oldest_age = max(oldest_age, age)

                    if agent.status == "active" and agent.started_at:
                        active_durations.append(current_time - agent.started_at)
                    elif agent.completed_at and agent.started_at:
                        active_durations.append(agent.completed_at - agent.started_at)

                stats["average_steps"] = total_steps / len(agents)
                stats["average_active_duration"] = (
                    sum(active_durations) / len(active_durations) if active_durations else 0
                )
                stats["oldest_agent_age"] = oldest_age

            return dict(stats)

    def shutdown_workflow_agents(self, workflow_id: str) -> int:
        """Shutdown all agents for a workflow.

        Returns:
            Number of agents shut down
        """
        shutdown_count = 0

        with self._lock:
            agent_ids = list(self._workflow_agents.get(workflow_id, set()))

            for agent_id in agent_ids:
                agent = self._agents.get(agent_id)
                if agent and agent.status in ("registered", "active"):
                    agent.status = "completed"
                    agent.completed_at = time.time()
                    shutdown_count += 1

        return shutdown_count
