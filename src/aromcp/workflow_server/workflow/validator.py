"""Workflow validation logic shared between runtime and static validation."""

import json
from pathlib import Path
from typing import Any

try:
    import jsonschema
    from jsonschema import validate, ValidationError, Draft7Validator
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class WorkflowValidator:
    """Validates MCP workflow definitions."""

    # Required top-level fields
    REQUIRED_FIELDS = {"name", "description", "version", "steps"}

    # Valid step types (matches step registry and schema)
    VALID_STEP_TYPES = {
        "state_update",
        "mcp_call",
        "user_message",
        "user_input",
        "shell_command",
        "conditional",
        "while_loop",
        "foreach",
        "parallel_foreach",
        "break",
        "continue",
        "batch_state_update",
        "agent_shell_command",
        "internal_mcp_call",
        "conditional_message",
        "agent_task",
        "debug_task_completion",
        "debug_step_advance",
    }

    # Valid message types
    VALID_MESSAGE_TYPES = {"info", "warning", "error", "success"}

    # Valid format types
    VALID_FORMAT_TYPES = {"text", "markdown", "code"}

    # Valid input types
    VALID_INPUT_TYPES = {"string", "number", "boolean", "object", "array"}

    # Valid state update operations
    VALID_OPERATIONS = {"set", "increment", "decrement", "append", "multiply"}

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.state_paths: set[str] = set()
        self.input_params: set[str] = set()
        self.sub_agent_tasks: set[str] = set()
        self.schema = None
        self._load_schema()
    
    def _load_schema(self):
        """Load the workflow JSON schema if available."""
        if not HAS_JSONSCHEMA:
            return
        
        # Try to find the schema file relative to this module
        schema_paths = [
            Path(__file__).parent.parent.parent.parent.parent / ".aromcp" / "workflows" / "schema.json",
            Path.cwd() / ".aromcp" / "workflows" / "schema.json",
        ]
        
        for schema_path in schema_paths:
            if schema_path.exists():
                try:
                    with open(schema_path, 'r') as f:
                        self.schema = json.load(f)
                    break
                except Exception:
                    # Silently ignore schema loading errors
                    pass

    def validate(self, workflow: dict[str, Any]) -> bool:
        """Validate a workflow definition.

        Args:
            workflow: Parsed workflow dictionary

        Returns:
            True if valid, False otherwise
        """
        self.errors = []
        self.warnings = []
        self.state_paths = set()
        self.input_params = set()
        self.sub_agent_tasks = set()

        if not isinstance(workflow, dict):
            self.errors.append("Workflow must be a dictionary/object")
            return False

        # Try JSON schema validation first if available
        if self.schema and HAS_JSONSCHEMA:
            try:
                validate(instance=workflow, schema=self.schema)
            except ValidationError as e:
                # Convert JSON schema error to user-friendly message
                error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
                self.errors.append(f"Schema validation error at {error_path}: {e.message}")
                # Continue with traditional validation to provide more specific errors
            except Exception:
                # If schema validation fails for any reason, fall back to traditional validation
                pass

        # Validate structure
        self._validate_structure(workflow)

        # Collect defined elements
        self._collect_definitions(workflow)

        # Validate components
        self._validate_metadata(workflow)
        self._validate_config(workflow.get("config"))
        self._validate_state(workflow.get("default_state"), workflow.get("state_schema"))
        self._validate_inputs(workflow.get("inputs"))
        self._validate_steps(workflow.get("steps", []))
        self._validate_sub_agent_tasks(workflow.get("sub_agent_tasks"))

        # Cross-validation
        self._validate_references()

        return len(self.errors) == 0

    def get_validation_error(self) -> str:
        """Get a formatted validation error message."""
        if not self.errors:
            return ""

        error_msg = "Workflow validation failed:\n"
        for error in self.errors:
            error_msg += f"  - {error}\n"

        if self.warnings:
            error_msg += "\nWarnings:\n"
            for warning in self.warnings:
                error_msg += f"  - {warning}\n"

        return error_msg.rstrip()

    def _validate_structure(self, workflow: dict[str, Any]):
        """Validate required fields exist."""
        missing = self.REQUIRED_FIELDS - set(workflow.keys())
        if missing:
            self.errors.append(f"Missing required fields: {', '.join(sorted(missing))}")

    def _collect_definitions(self, workflow: dict[str, Any]):
        """Collect all defined elements for reference validation."""
        # Collect input parameters
        if "inputs" in workflow and isinstance(workflow["inputs"], dict):
            self.input_params = set(workflow["inputs"].keys())

        # Collect state paths
        if "default_state" in workflow:
            self._collect_state_paths(workflow["default_state"], "")

        # Collect sub-agent tasks
        if "sub_agent_tasks" in workflow and isinstance(workflow["sub_agent_tasks"], dict):
            self.sub_agent_tasks = set(workflow["sub_agent_tasks"].keys())

    def _collect_state_paths(self, state: Any, prefix: str):
        """Recursively collect state paths."""
        if isinstance(state, dict):
            for key, value in state.items():
                path = f"{prefix}.{key}" if prefix else key
                self.state_paths.add(path)
                if isinstance(value, dict):
                    self._collect_state_paths(value, path)

    def _validate_metadata(self, workflow: dict[str, Any]):
        """Validate workflow metadata."""
        # Name validation
        name = workflow.get("name")
        if name:
            if ":" not in name:
                self.warnings.append("Workflow name should follow 'namespace:name' format")
            elif name.count(":") > 1:
                self.errors.append("Workflow name should have exactly one ':' separator")

        # Version validation
        version = workflow.get("version")
        if version:
            parts = version.split(".")
            if len(parts) != 3 or not all(p.isdigit() for p in parts):
                self.warnings.append("Version should follow semantic versioning (e.g., '1.0.0')")

    def _validate_config(self, config: dict[str, Any] | None):
        """Validate workflow configuration."""
        if not config:
            return

        if not isinstance(config, dict):
            self.errors.append("Config must be an object")
            return

        # Validate common config options
        if "timeout_seconds" in config:
            if not isinstance(config["timeout_seconds"], int | float) or config["timeout_seconds"] <= 0:
                self.errors.append("Config timeout_seconds must be a positive number")

        if "max_retries" in config:
            if not isinstance(config["max_retries"], int) or config["max_retries"] < 0:
                self.errors.append("Config max_retries must be a non-negative integer")

    def _validate_state(self, default_state: dict[str, Any] | None, state_schema: dict[str, Any] | None):
        """Validate state configuration."""
        if default_state and not isinstance(default_state, dict):
            self.errors.append("default_state must be an object")

        if not state_schema:
            return

        if not isinstance(state_schema, dict):
            self.errors.append("state_schema must be an object")
            return

        # Validate computed fields
        computed = state_schema.get("computed", {})
        if isinstance(computed, dict):
            for field_name, field_def in computed.items():
                self._validate_computed_field(field_name, field_def)

    def _validate_computed_field(self, name: str, field: Any):
        """Validate a computed field definition."""
        if not isinstance(field, dict):
            self.errors.append(f"Computed field '{name}' must be an object")
            return

        if "from" not in field:
            self.errors.append(f"Computed field '{name}' missing 'from' property")

        if "transform" not in field:
            self.errors.append(f"Computed field '{name}' missing 'transform' property")

        if "on_error" in field:
            valid_error_handlers = {"use_fallback", "propagate", "ignore"}
            if field["on_error"] not in valid_error_handlers:
                self.errors.append(f"Computed field '{name}' has invalid on_error value")

    def _validate_inputs(self, inputs: dict[str, Any] | None):
        """Validate input parameter definitions."""
        if not inputs:
            return

        if not isinstance(inputs, dict):
            self.errors.append("Inputs must be an object")
            return

        for param_name, param_def in inputs.items():
            self._validate_input_param(param_name, param_def)

    def _validate_input_param(self, name: str, param: Any):
        """Validate an input parameter definition."""
        if not isinstance(param, dict):
            self.errors.append(f"Input parameter '{name}' must be an object")
            return

        if "type" in param and param["type"] not in self.VALID_INPUT_TYPES:
            self.errors.append(f"Input parameter '{name}' has invalid type: {param['type']}")

        if "required" in param and not isinstance(param["required"], bool):
            self.errors.append(f"Input parameter '{name}' required field must be boolean")

    def _validate_steps(self, steps: list[Any]):
        """Validate workflow steps."""
        if not isinstance(steps, list):
            self.errors.append("Steps must be an array")
            return

        for i, step in enumerate(steps):
            self._validate_step(step, f"steps[{i}]")

    def _validate_step(self, step: Any, path: str):
        """Validate a single step."""
        if not isinstance(step, dict):
            self.errors.append(f"{path} must be an object")
            return

        step_type = step.get("type")
        if not step_type:
            self.errors.append(f"{path} missing 'type' field")
            return

        if step_type not in self.VALID_STEP_TYPES:
            self.errors.append(f"{path} has invalid type: {step_type}")
            return

        # Type-specific validation
        validator_method = f"_validate_{step_type}_step"
        if hasattr(self, validator_method):
            getattr(self, validator_method)(step, path)

    def _validate_state_update_step(self, step: dict[str, Any], path: str):
        """Validate state_update step."""
        if "path" not in step:
            self.errors.append(f"{path} missing 'path' field")

        if "value" not in step:
            self.errors.append(f"{path} missing 'value' field")

        if "operation" in step and step["operation"] not in self.VALID_OPERATIONS:
            self.errors.append(f"{path} has invalid operation: {step['operation']}")

    def _validate_mcp_call_step(self, step: dict[str, Any], path: str):
        """Validate mcp_call step."""
        if "tool" not in step:
            self.errors.append(f"{path} missing 'tool' field")

        if "parameters" in step and not isinstance(step["parameters"], dict):
            self.errors.append(f"{path} parameters must be an object")

    def _validate_user_message_step(self, step: dict[str, Any], path: str):
        """Validate user_message step."""
        if "message" not in step:
            self.errors.append(f"{path} missing 'message' field")

        # Note: 'type' field is overloaded - it's the step type, but user_message also has a message type
        # Check for message_type or type (when it's not "user_message")
        msg_type = step.get("message_type") or step.get("type")
        if msg_type and msg_type != "user_message" and msg_type not in self.VALID_MESSAGE_TYPES:
            self.errors.append(f"{path} has invalid message type: {msg_type}")

        if "format" in step and step["format"] not in self.VALID_FORMAT_TYPES:
            self.errors.append(f"{path} has invalid format: {step['format']}")

    def _validate_conditional_step(self, step: dict[str, Any], path: str):
        """Validate conditional step."""
        if "condition" not in step:
            self.errors.append(f"{path} missing 'condition' field")

        if "then_steps" in step:
            if isinstance(step["then_steps"], list):
                for i, s in enumerate(step["then_steps"]):
                    self._validate_step(s, f"{path}.then_steps[{i}]")
            else:
                self.errors.append(f"{path}.then_steps must be an array")

        if "else_steps" in step:
            if isinstance(step["else_steps"], list):
                for i, s in enumerate(step["else_steps"]):
                    self._validate_step(s, f"{path}.else_steps[{i}]")
            else:
                self.errors.append(f"{path}.else_steps must be an array")

    def _validate_while_loop_step(self, step: dict[str, Any], path: str):
        """Validate while_loop step."""
        if "condition" not in step:
            self.errors.append(f"{path} missing 'condition' field")

        if "body" in step:
            if isinstance(step["body"], list):
                for i, s in enumerate(step["body"]):
                    self._validate_step(s, f"{path}.body[{i}]")
            else:
                self.errors.append(f"{path}.body must be an array")

    def _validate_foreach_step(self, step: dict[str, Any], path: str):
        """Validate foreach step."""
        if "items" not in step:
            self.errors.append(f"{path} missing 'items' field")

        if "body" in step:
            if isinstance(step["body"], list):
                for i, s in enumerate(step["body"]):
                    self._validate_step(s, f"{path}.body[{i}]")
            else:
                self.errors.append(f"{path}.body must be an array")

    def _validate_parallel_foreach_step(self, step: dict[str, Any], path: str):
        """Validate parallel_foreach step."""
        if "items" not in step:
            self.errors.append(f"{path} missing 'items' field")

        if "sub_agent_task" not in step:
            self.errors.append(f"{path} missing 'sub_agent_task' field")

    def _validate_sub_agent_tasks(self, tasks: dict[str, Any] | None):
        """Validate sub-agent task definitions."""
        if not tasks:
            return

        if not isinstance(tasks, dict):
            self.errors.append("sub_agent_tasks must be an object")
            return

        for task_name, task_def in tasks.items():
            self._validate_sub_agent_task(task_name, task_def)

    def _validate_sub_agent_task(self, name: str, task: Any):
        """Validate a sub-agent task definition."""
        if not isinstance(task, dict):
            self.errors.append(f"Sub-agent task '{name}' must be an object")
            return

        if "description" not in task:
            self.warnings.append(f"Sub-agent task '{name}' should have a description")

        # prompt_template is optional - defaults to standard prompt if missing
        if "prompt_template" not in task and "steps" not in task:
            self.warnings.append(f"Sub-agent task '{name}' should have either prompt_template or steps defined")

    def _validate_references(self):
        """Cross-validate references between components."""
        # This is where we'd check that referenced sub_agent_tasks exist,
        # state paths are valid, etc. For now, basic implementation.
        pass
    
    def validate_with_schema(self, workflow: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a workflow using only the JSON schema.
        
        Args:
            workflow: Parsed workflow dictionary
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        if not self.schema or not HAS_JSONSCHEMA:
            return True, ["JSON schema validation not available"]
        
        try:
            validate(instance=workflow, schema=self.schema)
            return True, []
        except ValidationError as e:
            # Collect all validation errors
            validator = Draft7Validator(self.schema)
            errors = []
            for error in validator.iter_errors(workflow):
                error_path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                errors.append(f"Schema error at {error_path}: {error.message}")
            return False, errors
        except Exception as e:
            return False, [f"Schema validation error: {str(e)}"]
