"""Workflow loader with name-based resolution and YAML parsing."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from ..state.models import StateSchema
from .models import (
    InputDefinition,
    SubAgentTask,
    WorkflowDefinition,
    WorkflowNotFoundError,
    WorkflowStep,
    WorkflowValidationError,
)
from .validator import WorkflowValidator

logger = logging.getLogger(__name__)


class WorkflowLoader:
    """Loads workflows from YAML files with name-based resolution."""

    def __init__(self, project_root: str | None = None):
        """Initialize the workflow loader.

        Args:
            project_root: Override project root for testing
        """
        self.project_root = project_root or os.getcwd()
        self.user_home = os.path.expanduser("~")

    def load(self, workflow_name: str) -> WorkflowDefinition:
        """Load a workflow by name with fallback resolution.

        Args:
            workflow_name: Name of workflow (e.g., "test:simple")

        Returns:
            Parsed workflow definition

        Raises:
            WorkflowNotFoundError: If workflow file not found
            WorkflowValidationError: If workflow fails validation
        """
        # Try project directory first
        project_path = Path(self.project_root) / ".aromcp" / "workflows" / f"{workflow_name}.yaml"
        if project_path.exists():
            return self._load_from_file(project_path, "project")

        # Fall back to user directory
        user_path = Path(self.user_home) / ".aromcp" / "workflows" / f"{workflow_name}.yaml"
        if user_path.exists():
            return self._load_from_file(user_path, "global")

        # Not found in either location
        raise WorkflowNotFoundError(
            f"Workflow '{workflow_name}' not found. Searched:\n  - {project_path}\n  - {user_path}"
        )

    def _load_from_file(self, file_path: Path, source: str) -> WorkflowDefinition:
        """Load and parse a workflow file.

        Args:
            file_path: Path to workflow YAML file
            source: "project" or "global"

        Returns:
            Parsed workflow definition
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            return self._parse_yaml(content, str(file_path), source)

        except FileNotFoundError as e:
            raise WorkflowNotFoundError(f"Workflow file not found: {file_path}") from e
        except yaml.YAMLError as e:
            raise WorkflowValidationError(f"YAML parsing error in {file_path}: {e}") from e
        except Exception as e:
            raise WorkflowValidationError(f"Error loading workflow from {file_path}: {e}") from e

    def _parse_yaml(self, content: str, file_path: str, source: str) -> WorkflowDefinition:
        """Parse YAML content into a workflow definition.

        Args:
            content: YAML content
            file_path: Path where content was loaded from
            source: "project" or "global"

        Returns:
            Parsed workflow definition
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise WorkflowValidationError(f"Invalid YAML syntax: {e}") from e

        if not isinstance(data, dict):
            raise WorkflowValidationError("Workflow must be a YAML object")

        # Validate workflow structure using the validator
        validator = WorkflowValidator()
        if not validator.validate(data):
            raise WorkflowValidationError(validator.get_validation_error())

        # Parse components
        try:
            default_state = data.get("default_state", {})
            state_schema = self._parse_state_schema(data.get("state_schema", {}))
            inputs = self._parse_inputs(data.get("inputs", {}))
            steps = self._parse_steps(data.get("steps", []))
            sub_agent_tasks = self._parse_sub_agent_tasks(data.get("sub_agent_tasks", {}))

            return WorkflowDefinition(
                name=data["name"],
                description=data["description"],
                version=data["version"],
                default_state=default_state,
                state_schema=state_schema,
                inputs=inputs,
                steps=steps,
                sub_agent_tasks=sub_agent_tasks,
                loaded_from=file_path,
                source=source,
            )

        except Exception as e:
            raise WorkflowValidationError(f"Error parsing workflow definition: {e}") from e

    def _parse_state_schema(self, schema_data: dict[str, Any]) -> StateSchema:
        """Parse state schema from YAML data."""
        raw = schema_data.get("raw", {})
        state = schema_data.get("state", {})
        computed_data = schema_data.get("computed", {})

        # Parse computed field definitions (keep as raw dictionaries for compatibility)
        computed = {}
        for field_name, field_def in computed_data.items():
            if isinstance(field_def, dict):
                computed[field_name] = field_def
            else:
                # Simple type definition
                computed[field_name] = {"from": [], "transform": "input"}

        return StateSchema(raw=raw, computed=computed, state=state)

    def _parse_inputs(self, inputs_data: dict[str, Any]) -> dict[str, InputDefinition]:
        """Parse input definitions from YAML data."""
        inputs = {}
        for name, input_def in inputs_data.items():
            if isinstance(input_def, dict):
                inputs[name] = InputDefinition(
                    type=input_def.get("type", "string"),
                    description=input_def.get("description", ""),
                    required=input_def.get("required", True),
                    default=input_def.get("default"),
                    validation=input_def.get("validation"),
                )
            else:
                # Simple type string
                inputs[name] = InputDefinition(type=str(input_def), description=f"Input parameter {name}")

        return inputs

    def _parse_steps(self, steps_data: list[Any]) -> list[WorkflowStep]:
        """Parse workflow steps from YAML data."""
        steps = []
        for i, step_data in enumerate(steps_data):
            if not isinstance(step_data, dict):
                raise WorkflowValidationError(f"Step {i} must be an object")

            step_type = step_data.get("type")
            if not step_type:
                raise WorkflowValidationError(f"Step {i} missing required 'type' field")

            # Generate ID if not provided
            step_id = step_data.get("id", f"step_{i}")

            # Extract definition (everything except id and type)
            definition = {k: v for k, v in step_data.items() if k not in ["id", "type"]}

            steps.append(WorkflowStep(id=step_id, type=step_type, definition=definition))

        return steps

    def _parse_sub_agent_tasks(self, tasks_data: dict[str, Any]) -> dict[str, SubAgentTask]:
        """Parse sub-agent task definitions from YAML data."""
        tasks = {}
        for name, task_data in tasks_data.items():
            if not isinstance(task_data, dict):
                raise WorkflowValidationError(f"Sub-agent task '{name}' must be an object")

            inputs = self._parse_inputs(task_data.get("inputs", {}))

            tasks[name] = SubAgentTask(
                name=name,
                description=task_data.get("description", ""),
                inputs=inputs,
                context_template=task_data.get("context_template", {}),
                prompt_template=task_data.get("prompt_template", ""),
            )

        return tasks

    def list_available_workflows(self, include_global: bool = True) -> list[dict[str, Any]]:
        """List all available workflows.

        Args:
            include_global: Whether to include global workflows

        Returns:
            List of workflow metadata
        """
        workflows = []

        # Project workflows
        project_dir = Path(self.project_root) / ".aromcp" / "workflows"
        if project_dir.exists():
            for file_path in project_dir.glob("*.yaml"):
                try:
                    workflow = self._load_from_file(file_path, "project")
                    workflows.append(
                        {
                            "name": workflow.name,
                            "description": workflow.description,
                            "version": workflow.version,
                            "source": "project",
                            "path": str(file_path),
                        }
                    )
                except Exception as e:
                    # Skip invalid workflows
                    logger.debug(f"Skipping invalid workflow file {file_path}: {e}")

        # Global workflows
        if include_global:
            user_dir = Path(self.user_home) / ".aromcp" / "workflows"
            if user_dir.exists():
                for file_path in user_dir.glob("*.yaml"):
                    try:
                        workflow = self._load_from_file(file_path, "global")
                        # Skip if already have project version
                        if not any(w["name"] == workflow.name for w in workflows):
                            workflows.append(
                                {
                                    "name": workflow.name,
                                    "description": workflow.description,
                                    "version": workflow.version,
                                    "source": "global",
                                    "path": str(file_path),
                                }
                            )
                    except Exception as e:
                        # Skip invalid workflows
                        logger.debug(f"Skipping invalid workflow file {file_path}: {e}")

        return workflows


class WorkflowParser:
    """Static parser for workflow YAML content."""

    @staticmethod
    def parse(yaml_content: str) -> WorkflowDefinition:
        """Parse YAML content into a workflow definition.

        Args:
            yaml_content: YAML content string

        Returns:
            Parsed workflow definition
        """
        loader = WorkflowLoader()
        return loader._parse_yaml(yaml_content, "<string>", "unknown")
