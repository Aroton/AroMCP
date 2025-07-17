"""Workflow execution engine with sequential step processing."""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from ..state.manager import StateManager
from .models import StepExecution, WorkflowDefinition, WorkflowExecutionError, WorkflowInstance


class VariableReplacer:
    """Handles variable interpolation in workflow step definitions."""

    @staticmethod
    def replace(step_definition: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
        """Replace variables in step definition with state values.

        Args:
            step_definition: Step definition with potential variables
            state: Flattened state to use for replacement

        Returns:
            Step definition with variables replaced
        """
        # Deep copy to avoid modifying original
        import copy
        result = copy.deepcopy(step_definition)

        # Replace variables recursively
        return VariableReplacer._replace_recursive(result, state)

    @staticmethod
    def _replace_recursive(obj: Any, state: dict[str, Any]) -> Any:
        """Recursively replace variables in nested objects."""
        if isinstance(obj, dict):
            return {k: VariableReplacer._replace_recursive(v, state) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [VariableReplacer._replace_recursive(item, state) for item in obj]
        elif isinstance(obj, str):
            return VariableReplacer._replace_string(obj, state)
        else:
            return obj

    @staticmethod
    def _replace_string(text: str, state: dict[str, Any]) -> str:
        """Replace variables in a string using {{ variable }} syntax."""
        # Find all {{ variable }} patterns
        pattern = r'\{\{\s*([^}]+)\s*\}\}'

        def replace_match(match):
            var_name = match.group(1).strip()
            return str(state.get(var_name, f"{{{{ {var_name} }}}}"))  # Keep original if not found

        return re.sub(pattern, replace_match, text)


class WorkflowExecutor:
    """Manages workflow instances and executes steps sequentially."""

    def __init__(self, state_manager: StateManager | None = None):
        """Initialize the workflow executor.

        Args:
            state_manager: State manager instance (creates new if None)
        """
        self.state_manager = state_manager or StateManager()
        self.workflows: dict[str, WorkflowInstance] = {}
        self.step_executions: dict[str, list[StepExecution]] = {}

    def start(self, workflow_def: WorkflowDefinition, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        """Initialize and start a workflow instance.

        Args:
            workflow_def: Workflow definition to execute
            inputs: Input values for the workflow

        Returns:
            Dictionary with workflow_id and initial state

        Raises:
            WorkflowExecutionError: If workflow initialization fails
        """
        try:
            # Generate unique workflow ID
            workflow_id = f"wf_{uuid.uuid4().hex[:8]}"

            # Create workflow instance
            instance = WorkflowInstance(
                id=workflow_id,
                workflow_name=workflow_def.name,
                definition=workflow_def,
                current_step_index=0,
                status="running",
                created_at=datetime.now(UTC).isoformat()
            )

            # Initialize state with defaults
            initial_state = workflow_def.default_state.copy()

            # Apply inputs to state
            if inputs:
                if 'raw' not in initial_state:
                    initial_state['raw'] = {}
                initial_state['raw'].update(inputs)

            # Initialize state manager with schema
            if not hasattr(self.state_manager, '_schema') or self.state_manager._schema != workflow_def.state_schema:
                self.state_manager._schema = workflow_def.state_schema
                self.state_manager._setup_transformations()

            # Set initial state by applying updates
            if initial_state:
                updates = []
                for tier_name, tier_data in initial_state.items():
                    if tier_name in ['raw', 'state'] and isinstance(tier_data, dict):
                        for key, value in tier_data.items():
                            updates.append({"path": f"{tier_name}.{key}", "value": value})

                if updates:
                    self.state_manager.update(workflow_id, updates)

            # Store workflow instance
            self.workflows[workflow_id] = instance
            self.step_executions[workflow_id] = []

            # Get current flattened state
            try:
                current_state = self.state_manager.read(workflow_id)
            except Exception:
                # If reading fails (e.g., no state exists), return empty state
                current_state = {}

            return {
                "workflow_id": workflow_id,
                "state": current_state,
                "status": "running",
                "total_steps": len(workflow_def.steps)
            }

        except Exception as e:
            raise WorkflowExecutionError(f"Failed to start workflow: {e}") from e

    def get_next_step(self, workflow_id: str) -> dict[str, Any] | None:
        """Get the next step to execute for a workflow.

        Args:
            workflow_id: ID of the workflow instance

        Returns:
            Next step to execute or None if workflow complete

        Raises:
            WorkflowExecutionError: If workflow not found or in invalid state
        """
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        instance = self.workflows[workflow_id]

        if instance.status != "running":
            return None

        # Check if we have more steps
        if instance.current_step_index >= len(instance.definition.steps):
            # Mark workflow as complete
            instance.status = "completed"
            instance.completed_at = datetime.now(UTC).isoformat()
            return None

        # Get the next step
        step = instance.definition.steps[instance.current_step_index]

        # Get current state for variable replacement
        current_state = self.state_manager.read(workflow_id)

        # Replace variables in step definition
        processed_definition = VariableReplacer.replace(step.definition, current_state)

        # Create step execution record
        step_execution = StepExecution(
            workflow_id=workflow_id,
            step_id=step.id,
            step_index=instance.current_step_index,
            status="pending",
            started_at=datetime.now(UTC).isoformat()
        )

        self.step_executions[workflow_id].append(step_execution)

        return {
            "step": {
                "id": step.id,
                "type": step.type,
                "definition": processed_definition
            },
            "workflow_id": workflow_id,
            "step_index": instance.current_step_index,
            "total_steps": len(instance.definition.steps)
        }

    def step_complete(self, workflow_id: str, step_id: str, status: str = "success",
                     result: dict[str, Any] | None = None,
                     error_message: str | None = None) -> dict[str, Any]:
        """Mark a step as complete and advance workflow.

        Args:
            workflow_id: ID of the workflow instance
            step_id: ID of the completed step
            status: "success" or "failed"
            result: Optional result data from step execution
            error_message: Error message if step failed

        Returns:
            Updated workflow status

        Raises:
            WorkflowExecutionError: If workflow or step not found
        """
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        instance = self.workflows[workflow_id]

        # Find the step execution record
        step_executions = self.step_executions[workflow_id]
        step_execution = None
        for exec_record in reversed(step_executions):  # Get most recent matching step
            if exec_record.step_id == step_id:
                step_execution = exec_record
                break

        if not step_execution:
            raise WorkflowExecutionError(f"Step execution record not found for step {step_id}")

        # Update step execution
        step_execution.status = "completed" if status == "success" else "failed"
        step_execution.completed_at = datetime.now(UTC).isoformat()
        step_execution.result = result
        step_execution.error_message = error_message

        if status == "failed":
            # Mark workflow as failed
            instance.status = "failed"
            instance.completed_at = datetime.now(UTC).isoformat()
            instance.error_message = error_message or "Step execution failed"

            return {
                "status": "failed",
                "error": error_message,
                "completed_at": instance.completed_at
            }

        # Advance to next step
        instance.current_step_index += 1

        # Check if workflow is complete
        if instance.current_step_index >= len(instance.definition.steps):
            instance.status = "completed"
            instance.completed_at = datetime.now(UTC).isoformat()

        return {
            "status": instance.status,
            "current_step_index": instance.current_step_index,
            "total_steps": len(instance.definition.steps),
            "completed_at": instance.completed_at if instance.status == "completed" else None
        }

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get current status of a workflow.

        Args:
            workflow_id: ID of the workflow instance

        Returns:
            Current workflow status and progress

        Raises:
            WorkflowExecutionError: If workflow not found
        """
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        instance = self.workflows[workflow_id]
        current_state = self.state_manager.read(workflow_id)

        return {
            "workflow_id": workflow_id,
            "workflow_name": instance.workflow_name,
            "status": instance.status,
            "current_step_index": instance.current_step_index,
            "total_steps": len(instance.definition.steps),
            "created_at": instance.created_at,
            "completed_at": instance.completed_at,
            "error_message": instance.error_message,
            "state": current_state
        }

    def update_workflow_state(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """Update workflow state.

        Args:
            workflow_id: ID of the workflow instance
            updates: List of state updates

        Returns:
            Updated state

        Raises:
            WorkflowExecutionError: If workflow not found
        """
        if workflow_id not in self.workflows:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found")

        try:
            # Apply updates through state manager
            self.state_manager.update(workflow_id, updates)

            # Return updated state
            return self.state_manager.read(workflow_id)

        except Exception as e:
            raise WorkflowExecutionError(f"Failed to update workflow state: {e}") from e

    def list_active_workflows(self) -> list[dict[str, Any]]:
        """List all active workflow instances.

        Returns:
            List of workflow summaries
        """
        result = []
        for workflow_id, instance in self.workflows.items():
            result.append({
                "workflow_id": workflow_id,
                "workflow_name": instance.workflow_name,
                "status": instance.status,
                "current_step_index": instance.current_step_index,
                "total_steps": len(instance.definition.steps),
                "created_at": instance.created_at,
                "completed_at": instance.completed_at
            })

        return result
