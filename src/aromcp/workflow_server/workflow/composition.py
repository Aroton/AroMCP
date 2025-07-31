"""Workflow composition and inclusion system.

This module provides functionality for including and composing workflows,
enabling reusable workflow components and modular design.
"""

import copy
from dataclasses import dataclass, field
from typing import Any

from .loader import WorkflowLoader
from .models import WorkflowDefinition


@dataclass
class IncludeWorkflowStep:
    """Configuration for include_workflow step type."""

    workflow: str  # Name of workflow to include
    input_mapping: dict[str, str] = field(default_factory=dict)  # parent_var -> child_var
    output_mapping: dict[str, str] = field(default_factory=dict)  # child_var -> parent_var
    state_namespace: str | None = None  # Isolate included workflow state
    wait_for_completion: bool = True
    timeout_seconds: int | None = None


@dataclass
class IncludedWorkflowContext:
    """Context for an included workflow instance."""

    include_id: str
    parent_workflow_id: str
    child_workflow_id: str
    workflow_name: str
    namespace: str | None
    input_mapping: dict[str, str]
    output_mapping: dict[str, str]
    status: str = "pending"  # pending, running, completed, failed
    created_at: float = field(default_factory=lambda: __import__("time").time())
    completed_at: float | None = None
    error: str | None = None


class WorkflowComposer:
    """Manages workflow composition and inclusion."""

    def __init__(self, workflow_loader: WorkflowLoader | None = None):
        self.workflow_loader = workflow_loader or WorkflowLoader()
        self._included_workflows: dict[str, IncludedWorkflowContext] = {}
        self._inclusion_graph: dict[str, set[str]] = {}  # parent -> children
        self._max_inclusion_depth = 10

    def process_include_workflow(
        self, step_def: IncludeWorkflowStep, parent_workflow_id: str, parent_state: dict[str, Any], step_id: str
    ) -> dict[str, Any]:
        """Process an include_workflow step.

        Args:
            step_def: Include workflow configuration
            parent_workflow_id: ID of parent workflow
            parent_state: Current state of parent workflow
            step_id: ID of the include step

        Returns:
            Atomic step for agent or error
        """
        try:
            # Check for circular inclusion
            if self._would_create_cycle(parent_workflow_id, step_def.workflow):
                return {"error": f"Circular inclusion detected: {step_def.workflow} would create cycle"}

            # Load included workflow
            included_workflow = self.workflow_loader.load(step_def.workflow)

            # Generate unique include ID
            include_id = f"inc_{step_id}_{int(__import__('time').time())}"

            # Prepare input mapping
            mapped_inputs = self._map_inputs(parent_state, step_def.input_mapping, included_workflow)

            # Create included workflow context
            context = IncludedWorkflowContext(
                include_id=include_id,
                parent_workflow_id=parent_workflow_id,
                child_workflow_id="",  # Will be set when workflow starts
                workflow_name=step_def.workflow,
                namespace=step_def.state_namespace,
                input_mapping=step_def.input_mapping,
                output_mapping=step_def.output_mapping,
            )

            self._included_workflows[include_id] = context

            # Add to inclusion graph
            if parent_workflow_id not in self._inclusion_graph:
                self._inclusion_graph[parent_workflow_id] = set()
            self._inclusion_graph[parent_workflow_id].add(include_id)

            # Return atomic step for agent
            return {
                "step": {
                    "id": step_id,
                    "type": "include_workflow",
                    "instructions": f"Start included workflow '{step_def.workflow}' with mapped inputs",
                    "definition": {
                        "include_id": include_id,
                        "workflow": step_def.workflow,
                        "mapped_inputs": mapped_inputs,
                        "namespace": step_def.state_namespace,
                        "wait_for_completion": step_def.wait_for_completion,
                        "timeout_seconds": step_def.timeout_seconds,
                    },
                }
            }

        except Exception as e:
            return {"error": f"Failed to process include_workflow: {str(e)}"}

    def _map_inputs(
        self, parent_state: dict[str, Any], input_mapping: dict[str, str], included_workflow: WorkflowDefinition
    ) -> dict[str, Any]:
        """Map parent state to included workflow inputs."""
        mapped_inputs = {}

        # Apply explicit mapping
        for parent_var, child_var in input_mapping.items():
            if parent_var in parent_state:
                mapped_inputs[child_var] = parent_state[parent_var]

        # Auto-map inputs with same names if not explicitly mapped
        for input_name in included_workflow.inputs.keys():
            if input_name not in mapped_inputs and input_name in parent_state:
                mapped_inputs[input_name] = parent_state[input_name]

        return mapped_inputs

    def _map_outputs(self, child_state: dict[str, Any], output_mapping: dict[str, str]) -> dict[str, Any]:
        """Map included workflow outputs to parent state."""
        mapped_outputs = {}

        for child_var, parent_var in output_mapping.items():
            if child_var in child_state:
                mapped_outputs[parent_var] = child_state[child_var]

        return mapped_outputs

    def _would_create_cycle(self, parent_id: str, included_workflow: str) -> bool:
        """Check if including a workflow would create a circular dependency."""
        # Simple implementation - could be enhanced for complex scenarios
        visited = set()

        def has_cycle(workflow_id: str) -> bool:
            if workflow_id in visited:
                return True

            visited.add(workflow_id)

            # Check children
            children = self._inclusion_graph.get(workflow_id, set())
            for child_id in children:
                context = self._included_workflows.get(child_id)
                if context and context.workflow_name == included_workflow:
                    return True
                if has_cycle(child_id):
                    return True

            visited.remove(workflow_id)
            return False

        return has_cycle(parent_id)

    def complete_included_workflow(
        self,
        include_id: str,
        child_workflow_id: str,
        final_state: dict[str, Any],
        status: str = "completed",
        error: str | None = None,
    ) -> dict[str, Any]:
        """Complete an included workflow and map outputs back.

        Args:
            include_id: Include operation ID
            child_workflow_id: Child workflow instance ID
            final_state: Final state of child workflow
            status: Completion status
            error: Error message if failed

        Returns:
            Mapped outputs or error
        """
        try:
            context = self._included_workflows.get(include_id)
            if not context:
                return {"error": f"Include context not found: {include_id}"}

            # Update context
            context.child_workflow_id = child_workflow_id
            context.status = status
            context.completed_at = __import__("time").time()
            if error:
                context.error = error

            if status == "completed":
                # Map outputs back to parent
                mapped_outputs = self._map_outputs(final_state, context.output_mapping)

                return {
                    "success": True,
                    "include_id": include_id,
                    "mapped_outputs": mapped_outputs,
                    "namespace": context.namespace,
                }
            else:
                return {"success": False, "include_id": include_id, "error": error or "Included workflow failed"}

        except Exception as e:
            return {"error": f"Failed to complete included workflow: {str(e)}"}

    def get_included_workflow_context(self, include_id: str) -> IncludedWorkflowContext | None:
        """Get context for an included workflow."""
        return self._included_workflows.get(include_id)

    def list_included_workflows(self, parent_workflow_id: str) -> list[IncludedWorkflowContext]:
        """List all included workflows for a parent."""
        included_ids = self._inclusion_graph.get(parent_workflow_id, set())
        return [self._included_workflows[inc_id] for inc_id in included_ids if inc_id in self._included_workflows]

    def create_namespaced_state(
        self, parent_state: dict[str, Any], namespace: str, child_state: dict[str, Any]
    ) -> dict[str, Any]:
        """Create state with namespace isolation.

        Args:
            parent_state: Parent workflow state
            namespace: Namespace for child state
            child_state: Child workflow state

        Returns:
            Combined state with namespace isolation
        """
        # Create deep copy of parent state
        combined_state = copy.deepcopy(parent_state)

        # Add child state under namespace
        if namespace:
            combined_state[namespace] = child_state
        else:
            # Merge child state directly (may override parent values)
            combined_state.update(child_state)

        return combined_state

    def extract_namespaced_state(self, combined_state: dict[str, Any], namespace: str | None) -> dict[str, Any]:
        """Extract child state from namespaced combined state."""
        if namespace and namespace in combined_state:
            return combined_state[namespace]
        else:
            # Return full state if no namespace
            return combined_state

    def cleanup_completed_inclusions(self, max_age_seconds: int = 3600) -> int:
        """Clean up old completed inclusion contexts."""
        current_time = __import__("time").time()
        cleanup_count = 0

        completed_ids = []
        for include_id, context in self._included_workflows.items():
            if (
                context.status in ("completed", "failed")
                and context.completed_at
                and current_time - context.completed_at > max_age_seconds
            ):
                completed_ids.append(include_id)

        for include_id in completed_ids:
            context = self._included_workflows.pop(include_id, None)
            if context:
                # Remove from inclusion graph
                parent_children = self._inclusion_graph.get(context.parent_workflow_id, set())
                parent_children.discard(include_id)
                cleanup_count += 1

        return cleanup_count

    def get_inclusion_stats(self) -> dict[str, Any]:
        """Get statistics about workflow inclusions."""
        total_inclusions = len(self._included_workflows)
        status_counts = {}

        for context in self._included_workflows.values():
            status_counts[context.status] = status_counts.get(context.status, 0) + 1

        return {
            "total_inclusions": total_inclusions,
            "by_status": status_counts,
            "active_parent_workflows": len(self._inclusion_graph),
            "max_inclusion_depth": self._max_inclusion_depth,
        }


class IncludeWorkflowProcessor:
    """Processor for include_workflow steps."""

    def __init__(self, composer: WorkflowComposer | None = None):
        self.composer = composer or WorkflowComposer()

    def process_include_step(
        self, step_def: dict[str, Any], workflow_id: str, state: dict[str, Any], step_id: str
    ) -> dict[str, Any]:
        """Process an include_workflow step definition."""
        try:
            # Parse step definition
            include_config = IncludeWorkflowStep(
                workflow=step_def["workflow"],
                input_mapping=step_def.get("input_mapping", {}),
                output_mapping=step_def.get("output_mapping", {}),
                state_namespace=step_def.get("state_namespace"),
                wait_for_completion=step_def.get("wait_for_completion", True),
                timeout_seconds=step_def.get("timeout_seconds"),
            )

            return self.composer.process_include_workflow(include_config, workflow_id, state, step_id)

        except Exception as e:
            return {"error": f"Failed to process include step: {str(e)}"}
