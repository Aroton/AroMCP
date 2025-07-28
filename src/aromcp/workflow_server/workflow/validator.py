"""Workflow validation logic shared between runtime and static validation."""

import json
import re
from pathlib import Path
from typing import Any

try:
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
        "mcp_call",
        "user_message",
        "user_input",
        "agent_prompt",
        "agent_response",
        "shell_command",
        "conditional",
        "while_loop",
        "foreach",
        "parallel_foreach",
        "break",
        "continue",
        "wait_step",
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
        self.computed_fields: set[str] = set()
        self.referenced_variables: set[str] = set()
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
        self.computed_fields = set()
        self.referenced_variables = set()
        
        # Store current workflow for context-aware validation
        self._current_workflow = workflow

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
                self.errors.append(f"JSON Schema violation at {error_path}: {e.message}")
                # Continue with traditional validation to provide more specific errors
            except Exception as e:
                # If schema validation fails for any reason, note the issue
                self.warnings.append(f"JSON schema validation failed due to error: {str(e)}")
        elif not self.schema:
            self.warnings.append("JSON schema not loaded - using traditional validation only")
        elif not HAS_JSONSCHEMA:
            self.warnings.append("jsonschema library not available - using traditional validation only")

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
        # Collect input parameters from both locations for compatibility
        if "inputs" in workflow and isinstance(workflow["inputs"], dict):
            self.input_params = set(workflow["inputs"].keys())
        
        # Also collect inputs from default_state.inputs (three-tier state model)
        if "default_state" in workflow and isinstance(workflow["default_state"], dict):
            default_state = workflow["default_state"]
            if "inputs" in default_state and isinstance(default_state["inputs"], dict):
                self.input_params.update(default_state["inputs"].keys())

        # Collect state paths from default_state (supports both old and new formats)
        if "default_state" in workflow and isinstance(workflow["default_state"], dict):
            default_state = workflow["default_state"]
            
            # New three-tier model: default_state.state contains state variables
            if "state" in default_state and isinstance(default_state["state"], dict):
                self._collect_state_paths(default_state["state"], "")
            else:
                # Legacy format: default_state directly contains state variables
                # Filter out known tier names to avoid collecting them as state paths
                legacy_state = {k: v for k, v in default_state.items() 
                               if k not in ["inputs", "computed", "raw"]}
                if legacy_state:
                    self._collect_state_paths(legacy_state, "")

        # Collect computed fields from state_schema
        if "state_schema" in workflow and isinstance(workflow["state_schema"], dict):
            computed = workflow["state_schema"].get("computed", {})
            if isinstance(computed, dict):
                self.computed_fields = set(computed.keys())

            # Also collect state paths from state_schema definitions
            for section in ["state", "inputs"]:
                if section in workflow["state_schema"]:
                    schema_section = workflow["state_schema"][section]
                    if isinstance(schema_section, dict):
                        for key in schema_section.keys():
                            if section == "state":
                                self.state_paths.add(key)

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
            # Store computed field definitions for circular dependency checking
            self._current_computed_definitions = computed
            for field_name, field_def in computed.items():
                self._validate_computed_field(field_name, field_def)
            # Clean up after validation
            if hasattr(self, '_current_computed_definitions'):
                delattr(self, '_current_computed_definitions')

    def _validate_computed_field(self, name: str, field: Any, context: dict[str, Any] | None = None):
        """Validate a computed field definition."""
        if not isinstance(field, dict):
            self.errors.append(f"Computed field '{name}' must be an object")
            return

        if "from" not in field:
            self.errors.append(f"Computed field '{name}' missing 'from' property")
        else:
            # Extract references from the 'from' field
            from_value = field["from"]
            if isinstance(from_value, str):
                refs = self._extract_variable_references(from_value, f"computed.{name}.from")
                # If context is provided, validate references immediately
                if context:
                    for ref in refs:
                        if not self._validate_variable_reference(ref, context):
                            suggestions = self._get_similar_variables(ref)
                            error_msg = f"Undefined variable reference in computed field '{name}.from': '{ref}'"
                            if suggestions:
                                error_msg += f". Did you mean: {', '.join(suggestions)}?"
                            self.errors.append(error_msg)
                else:
                    self.referenced_variables.update(refs)
                # Check for circular dependencies
                if self._has_circular_dependency(name, from_value):
                    self.errors.append(f"Circular dependency detected in computed field '{name}'")
            elif isinstance(from_value, list):
                for i, item in enumerate(from_value):
                    refs = self._extract_variable_references(item, f"computed.{name}.from[{i}]")
                    self.referenced_variables.update(refs)
                    # Check for circular dependencies in array dependencies
                    if self._has_circular_dependency(name, item):
                        self.errors.append(f"Circular dependency detected in computed field '{name}.from[{i}]'")

        if "transform" not in field:
            self.errors.append(f"Computed field '{name}' missing 'transform' property")
        else:
            # Extract references from transform expressions
            refs = self._extract_variable_references(field["transform"], f"computed.{name}.transform")
            # If context is provided, validate references immediately
            if context:
                for ref in refs:
                    if not self._validate_variable_reference(ref, context):
                        suggestions = self._get_similar_variables(ref)
                        error_msg = f"Undefined variable reference in computed field '{name}.transform': '{ref}'"
                        if suggestions:
                            error_msg += f". Did you mean: {', '.join(suggestions)}?"
                        self.errors.append(error_msg)
            else:
                self.referenced_variables.update(refs)

        # Validate error handling strategy
        if "on_error" in field:
            valid_error_handlers = {"use_fallback", "propagate", "ignore"}
            if field["on_error"] not in valid_error_handlers:
                valid_list = ", ".join(sorted(valid_error_handlers))
                self.errors.append(f"Computed field '{name}' has invalid on_error value '{field['on_error']}'. Valid values: {valid_list}")
            
            # Validate fallback value is provided when using 'use_fallback' strategy
            if field["on_error"] == "use_fallback" and "fallback" not in field:
                self.errors.append(f"Computed field '{name}' uses 'use_fallback' error strategy but no 'fallback' value is defined")
                
        # Validate JavaScript expressions in transform field
        if "transform" in field:
            transform = field["transform"]
            if isinstance(transform, str):
                # Basic validation of JavaScript syntax elements
                if transform.strip():
                    # Check for potentially dangerous patterns
                    dangerous_patterns = [
                        r'eval\s*\(',  # eval() calls
                        r'Function\s*\(',  # Function constructor
                        r'setTimeout\s*\(',  # setTimeout
                        r'setInterval\s*\(',  # setInterval
                        r'require\s*\(',  # require() calls
                        r'import\s+',  # import statements
                        r'__.*__',  # dunder attributes
                    ]
                    for pattern in dangerous_patterns:
                        if re.search(pattern, transform, re.IGNORECASE):
                            self.warnings.append(f"Computed field '{name}' transform contains potentially unsafe JavaScript pattern: {pattern}")
                            break

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

    def _validate_step(self, step: Any, path: str, context: dict[str, Any] | None = None):
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

        # For control flow steps, handle reference validation specially
        if step_type in ["foreach", "while_loop", "conditional", "parallel_foreach"]:
            # For while_loop, don't validate condition references here as they're handled in step-specific validation
            if step_type == "while_loop":
                # Only validate non-condition fields
                step_copy = {k: v for k, v in step.items()
                            if k not in ["body", "then_steps", "else_steps", "steps", "condition"]}
                self._validate_step_references(step_copy, path, context)
            elif step_type == "foreach":
                # For foreach, validate items with current context and body with foreach context
                # Only validate non-body fields here
                step_copy = {k: v for k, v in step.items()
                            if k not in ["body", "then_steps", "else_steps", "steps"]}
                self._validate_step_references(step_copy, path, context)
            else:
                # Create a copy without body/branches for reference validation
                step_copy = {k: v for k, v in step.items()
                            if k not in ["body", "then_steps", "else_steps", "steps"]}
                self._validate_step_references(step_copy, path, context)
        else:
            # Validate all references for non-control-flow steps
            self._validate_step_references(step, path, context)

        # Generic validation for state_updates (used by multiple step types)
        self._validate_step_state_updates(step, path)
        
        # Type-specific validation (which handles body/branches with proper context)
        validator_method = f"_validate_{step_type}_step"
        if hasattr(self, validator_method):
            getattr(self, validator_method)(step, path, context)
        
        # Validate break/continue steps only occur in loop contexts
        if step_type in ["break", "continue"]:
            if not context or not context.get("in_loop"):
                suggestions = ["foreach", "while_loop"]
                error_msg = f"At {path}: '{step_type}' steps can only be used inside loop contexts (foreach, while_loop)"
                if suggestions:
                    error_msg += f". Valid loop types: {', '.join(suggestions)}"
                self.errors.append(error_msg)

    def _validate_mcp_call_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate mcp_call step."""
        if "tool" not in step:
            self.errors.append(f"{path} missing 'tool' field")

        if "parameters" in step and not isinstance(step["parameters"], dict):
            self.errors.append(f"{path} parameters must be an object")

    def _validate_user_message_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
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

    def _validate_conditional_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate conditional step."""
        if "condition" not in step:
            self.errors.append(f"{path} missing 'condition' field")
        else:
            # Validate condition references
            condition_refs = self._extract_references_from_expression(step["condition"])
            for ref in condition_refs:
                if self._is_context_specific_variable(ref):
                    if not self._validate_variable_reference(ref, context):
                        suggestions = self._get_similar_variables(ref)
                        error_msg = self._get_scoped_variable_error_message(ref, f"{path}.condition", context)
                        if suggestions:
                            error_msg += f". Did you mean: {', '.join(suggestions)}?"
                        self.errors.append(error_msg)
                else:
                    # Regular variable, add to global references for validation
                    self.referenced_variables.add(ref)

        if "then_steps" in step:
            if isinstance(step["then_steps"], list):
                for i, s in enumerate(step["then_steps"]):
                    self._validate_step(s, f"{path}.then_steps[{i}]", context)
            else:
                self.errors.append(f"{path}.then_steps must be an array")

        if "else_steps" in step:
            if isinstance(step["else_steps"], list):
                for i, s in enumerate(step["else_steps"]):
                    self._validate_step(s, f"{path}.else_steps[{i}]", context)
            else:
                self.errors.append(f"{path}.else_steps must be an array")

    def _validate_while_loop_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate while_loop step."""
        if "condition" not in step:
            self.errors.append(f"{path} missing 'condition' field")
        else:
            # Validate condition with loop context (for loop.iteration)
            condition_refs = self._extract_variable_references(step["condition"], f"{path}.condition")
            loop_context = {"in_loop": True, "in_while_loop": True}
            for ref in condition_refs:
                if self._is_context_specific_variable(ref):
                    if not self._validate_variable_reference(ref, loop_context):
                        suggestions = self._get_similar_variables(ref)
                        if ref == "loop.iteration":
                            # These are valid in while loop conditions
                            continue
                        error_msg = self._get_scoped_variable_error_message(ref, f"{path}.condition", loop_context)
                        if suggestions:
                            error_msg += f". Did you mean: {', '.join(suggestions)}?"
                        self.errors.append(error_msg)
                else:
                    # Regular variable, add to global references for validation
                    self.referenced_variables.add(ref)

        if "body" in step:
            if isinstance(step["body"], list):
                # Pass while_loop context for body steps
                loop_context = {"in_loop": True, "in_while_loop": True}
                for i, s in enumerate(step["body"]):
                    self._validate_step(s, f"{path}.body[{i}]", loop_context)
            else:
                self.errors.append(f"{path}.body must be an array")

    def _validate_foreach_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate foreach step."""
        if "items" not in step:
            self.errors.append(f"{path} missing 'items' field")
        # Note: items field validation is handled in _validate_step with current context

        if "body" in step:
            if isinstance(step["body"], list):
                # Pass foreach context for body steps with loop variables
                foreach_context = {
                    "in_foreach": True, 
                    "in_loop": True, 
                    "in_while_loop": False,
                    "loop_variable_name": step.get("variable_name", "item"),
                    "loop_index_name": step.get("index_name", "index")
                }
                for i, s in enumerate(step["body"]):
                    self._validate_step(s, f"{path}.body[{i}]", foreach_context)
            else:
                self.errors.append(f"{path}.body must be an array")

    def _validate_parallel_foreach_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate parallel_foreach step."""
        if "items" not in step:
            self.errors.append(f"{path} missing 'items' field")

        if "sub_agent_task" not in step:
            self.errors.append(f"{path} missing 'sub_agent_task' field")
        else:
            # Validate that the referenced sub-agent task exists and is valid within the current context
            task_name = step["sub_agent_task"]
            if hasattr(self, '_current_workflow') and self._current_workflow:
                sub_agent_tasks = self._current_workflow.get("sub_agent_tasks", {})
                if task_name in sub_agent_tasks:
                    # Pass loop context to sub-agent task validation if we're in a loop
                    sub_agent_context = {"in_sub_agent": True, "sub_agent_name": task_name}
                    if context and context.get("in_loop"):
                        sub_agent_context.update(context)
                    self._validate_sub_agent_task(task_name, sub_agent_tasks[task_name], sub_agent_context)

    def _validate_agent_prompt_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate agent_prompt step."""
        if "prompt" not in step:
            self.errors.append(f"{path} missing 'prompt' field")

        # Optional validation of expected_response schema
        if "expected_response" in step:
            expected_response = step["expected_response"]
            if isinstance(expected_response, dict):
                if "type" in expected_response:
                    valid_types = {"string", "number", "boolean", "object", "array"}
                    if expected_response["type"] not in valid_types:
                        self.errors.append(f"{path} has invalid expected_response type")

    def _validate_agent_response_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate agent_response step."""
        # Optional validation of response_schema
        if "response_schema" in step:
            response_schema = step["response_schema"]
            if isinstance(response_schema, dict):
                if "type" in response_schema:
                    valid_types = {"string", "number", "boolean", "object", "array"}
                    if response_schema["type"] not in valid_types:
                        self.errors.append(f"{path} has invalid response_schema type")

        # state_updates validation is now handled generically in _validate_step()

        # Validate error_handling
        if "error_handling" in step:
            error_handling = step["error_handling"]
            if isinstance(error_handling, dict):
                if "strategy" in error_handling:
                    valid_strategies = {"retry", "continue", "fail", "fallback"}
                    if error_handling["strategy"] not in valid_strategies:
                        self.errors.append(f"{path} has invalid error_handling strategy")

    def _validate_break_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate break step."""
        # break steps are only valid inside loops - this is handled by step validation with context
        pass

    def _validate_continue_step(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate continue step."""
        # continue steps are only valid inside loops - this is handled by step validation with context
        pass

    def _validate_sub_agent_tasks(self, tasks: dict[str, Any] | None):
        """Validate sub-agent task definitions."""
        if not tasks:
            return

        if not isinstance(tasks, dict):
            self.errors.append("sub_agent_tasks must be an object")
            return

        for task_name, task_def in tasks.items():
            self._validate_sub_agent_task(task_name, task_def)

    def _validate_sub_agent_task(self, name: str, task: Any, parent_context: dict[str, Any] | None = None):
        """Validate a sub-agent task definition."""
        if not isinstance(task, dict):
            self.errors.append(f"Sub-agent task '{name}' must be an object")
            return

        if "description" not in task:
            self.warnings.append(f"Sub-agent task '{name}' should have a description")

        # prompt_template is optional - defaults to standard prompt if missing
        if "prompt_template" not in task and "steps" not in task:
            self.warnings.append(f"Sub-agent task '{name}' should have either prompt_template or steps defined")

        # Validate steps in sub-agent task if present
        if "steps" in task and isinstance(task["steps"], list):
            # Create a context for sub-agent task validation, inheriting from parent context
            sub_agent_context = {"in_sub_agent": True, "sub_agent_name": name}
            if parent_context:
                # Inherit loop context from parent (parallel_foreach, while_loop, etc.)
                for key in ["in_loop", "in_while_loop", "in_foreach"]:
                    if key in parent_context:
                        sub_agent_context[key] = parent_context[key]

            # Temporarily store parent definitions and clear them for sub-agent isolation
            parent_state_paths = self.state_paths.copy()
            parent_computed_fields = self.computed_fields.copy()
            parent_input_params = self.input_params.copy()
            parent_referenced_variables = self.referenced_variables.copy()

            # Clear parent state for sub-agent isolation
            self.state_paths = set()
            self.computed_fields = set()
            self.input_params = set()
            self.referenced_variables = set()

            # Collect sub-agent specific definitions
            if "default_state" in task:
                default_state = task["default_state"]
                if isinstance(default_state, dict):
                    # For sub-agents, collect from all top-level keys
                    for key, value in default_state.items():
                        if key == "state" and isinstance(value, dict):
                            # Special handling for 'state' section - don't add 'state.' prefix
                            self._collect_state_paths(value, "")
                        else:
                            # For other keys, collect normally
                            self._collect_state_paths({key: value}, "")

            if "state_schema" in task and isinstance(task["state_schema"], dict):
                # Collect state paths from state schema
                for section in ["state", "inputs"]:
                    if section in task["state_schema"]:
                        schema_section = task["state_schema"][section]
                        if isinstance(schema_section, dict):
                            for key in schema_section.keys():
                                if section == "state":
                                    self.state_paths.add(key)

            # Collect input parameters first (needed for computed field validation)
            if "inputs" in task and isinstance(task["inputs"], dict):
                self.input_params = set(task["inputs"].keys())

            # First pass: collect step types to understand available loop contexts
            step_context_analysis = self._analyze_step_contexts(task.get("steps", []))
            if step_context_analysis.get("has_while_loop"):
                sub_agent_context["in_while_loop"] = True
                sub_agent_context["in_loop"] = True
            if step_context_analysis.get("has_foreach"):
                sub_agent_context["in_foreach"] = True
                sub_agent_context["in_loop"] = True

            if "state_schema" in task and isinstance(task["state_schema"], dict):
                # Collect computed fields with loop context awareness
                computed = task["state_schema"].get("computed", {})
                if isinstance(computed, dict):
                    # Store computed field definitions for circular dependency checking
                    self._current_computed_definitions = computed
                    for field_name, field_def in computed.items():
                        self.computed_fields.add(field_name)
                        # Validate computed field with sub-agent context (including loop context)
                        self._validate_computed_field(field_name, field_def, sub_agent_context)
                    # Clean up after validation
                    if hasattr(self, '_current_computed_definitions'):
                        delattr(self, '_current_computed_definitions')

            # Validate steps with sub-agent context
            for i, step in enumerate(task["steps"]):
                self._validate_step(step, f"sub_agent_tasks.{name}.steps[{i}]", sub_agent_context)

            # Validate sub-agent's collected references
            for ref in self.referenced_variables:
                if not self._validate_variable_reference(ref, sub_agent_context):
                    suggestions = self._get_similar_variables(ref)
                    error_msg = f"Undefined variable reference in sub-agent '{name}': '{ref}'"
                    if suggestions:
                        error_msg += f". Did you mean: {', '.join(suggestions)}?"
                    self.errors.append(error_msg)

            # Restore parent definitions
            self.state_paths = parent_state_paths
            self.computed_fields = parent_computed_fields
            self.input_params = parent_input_params
            self.referenced_variables = parent_referenced_variables

    def _analyze_step_contexts(self, steps: list[dict[str, Any]]) -> dict[str, bool]:
        """Analyze steps to determine what loop contexts will be available.
        
        Returns:
            Dictionary with boolean flags for available contexts like has_while_loop, has_foreach
        """
        context_info = {
            "has_while_loop": False,
            "has_foreach": False
        }
        
        def analyze_step_list(step_list: list[dict[str, Any]]):
            for step in step_list:
                if not isinstance(step, dict) or "type" not in step:
                    continue
                    
                step_type = step["type"]
                if step_type == "while_loop":
                    context_info["has_while_loop"] = True
                elif step_type in ["foreach", "parallel_foreach"]:
                    context_info["has_foreach"] = True
                
                # Recursively analyze nested steps
                if step_type == "conditional":
                    if "then_steps" in step and isinstance(step["then_steps"], list):
                        analyze_step_list(step["then_steps"])
                    if "else_steps" in step and isinstance(step["else_steps"], list):
                        analyze_step_list(step["else_steps"])
                elif step_type in ["foreach", "while_loop"]:
                    if "body" in step and isinstance(step["body"], list):
                        analyze_step_list(step["body"])
        
        analyze_step_list(steps)
        return context_info

    def _extract_variable_references(self, value: Any, path: str = "") -> set[str]:
        """Extract all variable references from a value (handles templates and direct references)."""
        references = set()

        if isinstance(value, str):
            # Extract from template expressions {{ ... }}
            template_pattern = r'\{\{([^}]+)\}\}'
            for match in re.finditer(template_pattern, value):
                expr = match.group(1).strip()
                refs = self._extract_references_from_expression(expr)
                references.update(refs)

            # Also check if the entire string is a variable reference (for "from" fields)
            # Exclude state_update.path fields which are target paths, not references
            # Also exclude complex expressions with operators
            operators = ['>=', '<=', '==', '!=', '>', '<', '&&', '||', '+', '-', '*', '/', '?', ':', '(', ')']
            if (not value.startswith("{{") and "." in value and not path.endswith(".path") and
                not any(op in value for op in operators)):
                parts = value.split(".")
                if parts[0] in ["state", "computed", "inputs"]:
                    references.add(value)
            # For condition fields, treat as expressions and extract references from them
            elif path.endswith(".condition") and not value.startswith("{{"):
                refs = self._extract_references_from_expression(value)
                references.update(refs)

        elif isinstance(value, dict):
            for k, v in value.items():
                references.update(self._extract_variable_references(v, f"{path}.{k}" if path else k))

        elif isinstance(value, list):
            for i, item in enumerate(value):
                references.update(self._extract_variable_references(item, f"{path}[{i}]"))

        return references

    def _extract_references_from_expression(self, expr: str) -> set[str]:
        """Extract variable references from a JavaScript-like expression."""
        references = set()

        # For complex expressions with operators, break them down first
        # Handle comparison and arithmetic operators by splitting the expression
        # Include more operators and variations without spaces
        operators = [' >= ', ' <= ', ' == ', ' != ', ' > ', ' < ', ' && ', ' || ', ' + ', ' - ', ' * ', ' / ', 
                    '>=', '<=', '==', '!=', '>', '<', '&&', '||', '+', '-', '*', '/', '?', ':']
        if any(op in expr for op in operators):
            # Split on operators while keeping the parts
            parts = re.split(r'\s*(?:>=|<=|==|!=|>|<|&&|\|\||\+|-|\*|/|\?|:)\s*', expr)
            for part in parts:
                part = part.strip()
                if part:
                    # Recursively extract from each part
                    sub_refs = self._extract_references_from_expression(part)
                    references.update(sub_refs)
            return references

        # Match all property access patterns (scope.variable), then validate the scope later
        # This catches both valid and invalid scopes for proper error reporting
        property_pattern = r'\b[a-zA-Z_]\w*\.[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*'

        for match in re.finditer(property_pattern, expr):
            references.add(match.group(0))

        # Also match array access patterns like state.items[0] or this.data[1]
        array_pattern = r'\b[a-zA-Z_]\w*\.[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*(?:\[\d+\])?'

        for match in re.finditer(array_pattern, expr):
            ref = match.group(0)
            # Normalize array access to dot notation for validation
            ref = re.sub(r'\[(\d+)\]', r'.\1', ref)
            references.add(ref)

        # Handle dynamic property access like state.obj[computed.key]
        dynamic_access_pattern = r'\b([a-zA-Z_]\w*\.[a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)*)\[\{\{\s*([^}]+)\s*\}\}\]'
        for match in re.finditer(dynamic_access_pattern, expr):
            base_ref = match.group(1)
            dynamic_key = match.group(2).strip()
            references.add(base_ref)  # Add the base reference
            # Also extract references from the dynamic key
            key_refs = self._extract_references_from_expression(dynamic_key)
            references.update(key_refs)

        # Special handling for template variables without dots (e.g., {{ file_path }}, {{ item }})
        # These are often workflow inputs or loop variables
        # Only extract these if the expression is JUST the variable name
        if expr.strip() and '.' not in expr and not any(op in expr for op in ['+', '-', '*', '/', '(', ')', '[', ']', '>', '<', '=', '!', '&', '|']):
            var_name = expr.strip()
            # Skip JavaScript keywords and common functions
            if var_name not in ['true', 'false', 'null', 'undefined', 'if', 'else', 'return',
                               'function', 'const', 'let', 'var', 'input', 'output', 'Math',
                               'parseInt', 'parseFloat', 'toString', 'length'] and var_name.isidentifier():
                # Check if it's a known loop variable
                if var_name in ['item', 'loop']:
                    # These will be validated in context
                    references.add(var_name)
                else:
                    # Assume it's an input parameter
                    references.add(f"inputs.{var_name}")

        return references

    def _has_circular_dependency(self, field_name: str, dependency_path: str, visited: set[str] | None = None) -> bool:
        """Check if a computed field dependency creates a circular reference with recursive checking."""
        if visited is None:
            visited = set()
            
        if field_name in visited:
            return True
            
        # Extract variable references from the dependency path
        refs = self._extract_variable_references(dependency_path)
        
        for ref in refs:
            if ref.startswith("computed."):
                dep_field_parts = ref.split(".", 1)
                if len(dep_field_parts) > 1:
                    dep_field = dep_field_parts[1]
                    if dep_field == field_name:
                        return True
                    
                    # Recursive check: find the computed field definition and check its dependencies
                    if dep_field in self.computed_fields and hasattr(self, '_current_computed_definitions'):
                        if dep_field in visited:
                            return True  # Found a cycle
                            
                        new_visited = visited.copy()
                        new_visited.add(field_name)
                        
                        dep_field_def = self._current_computed_definitions.get(dep_field)
                        if dep_field_def and isinstance(dep_field_def, dict):
                            dep_from = dep_field_def.get("from")
                            if dep_from:
                                if isinstance(dep_from, str):
                                    if self._has_circular_dependency(dep_field, dep_from, new_visited):
                                        return True
                                elif isinstance(dep_from, list):
                                    for dep_item in dep_from:
                                        if self._has_circular_dependency(dep_field, str(dep_item), new_visited):
                                            return True
        
        return False

    def _validate_variable_reference(self, ref: str, context: dict[str, Any] | None = None) -> bool:
        """Check if a variable reference is defined in the workflow."""
        parts = ref.split(".")
        if not parts:
            return False

        root = parts[0]

        # Handle built-in JavaScript objects first
        if root in ["Math", "Object", "Array", "String", "Number", "Date", "JSON", "console"]:
            # Allow common JavaScript built-in objects and their methods
            return True

        # Handle foreach loop variables
        if context and context.get("in_foreach"):
            loop_variable_name = context.get("loop_variable_name", "item")
            loop_index_name = context.get("loop_index_name", "index")
            
            # Check if ref matches the loop variable or index names
            if ref == loop_variable_name or ref.startswith(f"{loop_variable_name}."):
                return True
            if ref == loop_index_name:
                return True
                
            # Also handle inputs.variable_name pattern for foreach variables
            if ref.startswith("inputs."):
                input_var = ref[7:]  # Remove "inputs." prefix
                if input_var == loop_variable_name or input_var == loop_index_name:
                    return True

        # Handle new scoped syntax
        if root == "this":
            # this.variable - validates against workflow state/computed fields
            if len(parts) < 2:
                return False
            field_name = parts[1]
            
            # Check if it exists in state paths
            state_path = ".".join(parts[1:])
            if state_path in self.state_paths:
                return True
                
            # Check if a parent path exists for nested references
            path_parts = parts[1:]
            for i in range(len(path_parts)):
                parent_path = ".".join(path_parts[:i+1])
                if parent_path in self.state_paths:
                    return True
                    
            # Check if it's a computed field
            return field_name in self.computed_fields

        elif root == "global":
            # global.variable - always valid (created dynamically)
            return len(parts) >= 2

        elif root == "loop":
            # loop.item, loop.index, loop.iteration - valid only in loop contexts
            # Also support custom variable names like loop.inner_val, loop.outer_val
            if not context or not context.get("in_loop"):
                return False
            if len(parts) < 2:
                return False
                
            loop_var = parts[1]
            if loop_var == "item":
                # loop.item only valid in foreach contexts
                return context.get("in_foreach", False)
            elif loop_var == "index":
                # loop.index valid in foreach contexts
                return context.get("in_foreach", False)
            elif loop_var == "iteration":
                # loop.iteration only valid in while loop contexts, not foreach
                return context.get("in_while_loop", False)
            else:
                # Custom variable names: check if we're in a foreach context and the variable name
                # could be a custom variable_name from the foreach step
                if context.get("in_foreach", False):
                    # For custom variable names, assume valid if we're in foreach context
                    # The actual validation will happen at runtime with proper loop context
                    return True
                return False

        elif root == "inputs":
            # inputs.parameter - validates against workflow inputs
            if len(parts) < 2:
                return False
            param_name = parts[1]
            return param_name in self.input_params

        # Legacy support for existing syntax
        elif root == "state":
            if len(parts) < 2:
                return False
            # Remove the root to get the path within state
            state_path = ".".join(parts[1:])

            # Check if the exact path exists
            if state_path in self.state_paths:
                return True

            # Check if a parent path exists (e.g., if state.lint_output is defined as an object,
            # then state.lint_output.data, state.lint_output.success, etc. are valid)
            path_parts = parts[1:]  # Remove 'state'
            for i in range(len(path_parts)):
                parent_path = ".".join(path_parts[:i+1])
                if parent_path in self.state_paths:
                    # Found a parent that exists, this nested reference is valid
                    return True

            return False

        elif root == "computed":
            if len(parts) < 2:
                return False
            field_name = parts[1]
            return field_name in self.computed_fields

        # Handle context-specific variables (legacy loop variables, etc.)
        if context:
            # Enhanced item validation - only valid in foreach contexts
            if root == "item":
                return context.get("in_foreach", False)
                
            # Legacy state.attempt_number removed - use loop.iteration instead

            # Handle state.loop_item and state.loop_index in loop contexts
            if root == "state" and len(parts) > 1:
                if parts[1] in ["loop_item", "loop_index"]:
                    return context.get("in_loop", False)
                # Legacy attempt_number no longer supported - use loop.iteration
        
        # Handle bare "item" variable in foreach contexts
        if ref == "item":
            return bool(context and context.get("in_foreach", False))

        # Handle direct workflow input references (e.g., {{ file_path }} becomes inputs.file_path)
        if root == "inputs" and len(parts) == 2:
            # For simple input references, also check if it's a workflow-level input
            param_name = parts[1]
            if param_name in self.input_params:
                return True
            # In sub-agent context, the parameter might be from the sub-agent's inputs
            if context and context.get("in_sub_agent"):
                # This is handled by the temporary input_params update in _validate_sub_agent_task
                return param_name in self.input_params

        # Check for invalid scope names - should catch unknown scopes
        valid_scopes = {"this", "global", "loop", "inputs", "state", "computed", "raw"}
        if "." in ref and root not in valid_scopes:
            # This is an invalid scope name, will be handled as undefined reference
            pass

        return False

    def _get_similar_variables(self, ref: str) -> list[str]:
        """Get similar defined variables for suggestions."""
        all_vars = set()

        # Collect all defined variables with both legacy and scoped syntax
        for param in self.input_params:
            all_vars.add(f"inputs.{param}")

        for path in self.state_paths:
            # Don't double-prefix if path already starts with a tier name
            if path.startswith(("state.", "inputs.", "computed.")):
                all_vars.add(path)
            else:
                all_vars.add(f"state.{path}")
                # Also suggest scoped 'this' syntax
                all_vars.add(f"this.{path}")

        for field in self.computed_fields:
            all_vars.add(f"computed.{field}")
            # Also suggest scoped 'this' syntax for computed fields
            all_vars.add(f"this.{field}")

        # Add dynamic global scope suggestions
        if ref.startswith("global."):
            all_vars.add("global.variable_name")

        # Calculate similarity based on common substrings and prefixes
        ref_lower = ref.lower()
        ref_parts = ref_lower.split('.')

        scored_suggestions = []
        for var in all_vars:
            var_lower = var.lower()
            var_parts = var_lower.split('.')

            score = 0
            # Same root (state, computed, this, etc)
            if ref_parts[0] == var_parts[0]:
                score += 10

            # Check for common parts
            for ref_part in ref_parts:
                for var_part in var_parts:
                    if len(ref_part) > 2 and len(var_part) > 2:
                        # Substring match
                        if ref_part in var_part or var_part in ref_part:
                            score += 5
                        # Prefix match
                        elif ref_part.startswith(var_part[:3]) or var_part.startswith(ref_part[:3]):
                            score += 3

            if score > 0:
                scored_suggestions.append((score, var))

        # Sort by score descending and return top 3
        scored_suggestions.sort(reverse=True, key=lambda x: x[0])
        return [var for _, var in scored_suggestions[:3]]

    def _validate_step_references(self, step: dict[str, Any], path: str, context: dict[str, Any] | None = None):
        """Validate all variable references in a step."""
        if context is None:
            context = {}

        # Extract references from the step
        refs = self._extract_variable_references(step, path)

        # Validate each reference immediately with context
        for ref in refs:
            if self._validate_variable_reference(ref, context):
                # Valid in this context, don't need to validate globally
                continue

            # Check if this is a context-specific variable that's valid in its context
            if self._is_context_specific_variable(ref):
                # Report error immediately for context-specific variables used in wrong context
                suggestions = self._get_similar_variables(ref)
                error_msg = self._get_scoped_variable_error_message(ref, path, context)
                if suggestions:
                    error_msg += f". Did you mean: {', '.join(suggestions)}?"
                self.errors.append(error_msg)
            else:
                # Regular variable, add to global references for validation
                self.referenced_variables.add(ref)

    def _validate_step_state_updates(self, step: dict[str, Any], path: str):
        """Validate state_updates field and track new state variables."""
        if "state_updates" not in step:
            return
            
        state_updates = step["state_updates"]
        if isinstance(state_updates, list):
            for i, update in enumerate(state_updates):
                if not isinstance(update, dict):
                    self.errors.append(f"{path}.state_updates[{i}] must be an object")
                elif "path" not in update or "value" not in update:
                    self.errors.append(f"{path}.state_updates[{i}] missing required fields")
                else:
                    # Track dynamically created state variables
                    update_path = update.get("path", "")
                    if update_path.startswith("state."):
                        # Add the new state variable to tracked paths
                        state_var = update_path[6:]  # Remove "state." prefix
                        self.state_paths.add(state_var)
        else:
            self.errors.append(f"{path}.state_updates must be an array")

    def _is_context_specific_variable(self, ref: str) -> bool:
        """Check if a variable is only valid in specific contexts."""
        # Legacy context-specific variables
        legacy_vars = ["state.loop_item", "state.loop_index", "loop.iteration", "loop.index", "loop", "item"]
        
        # New scoped context-specific variables
        scoped_vars = ["loop.item", "loop.index", "loop.iteration"]
        
        return ref in legacy_vars or ref in scoped_vars

    def _get_scoped_variable_error_message(self, ref: str, path: str, context: dict[str, Any] | None) -> str:
        """Generate helpful error messages for scoped variable validation failures."""
        # Handle new scoped syntax
        if ref.startswith("loop."):
            loop_var = ref.split(".", 1)[1]
            if loop_var == "item":
                return f"At {path}: Variable '{ref}' is only valid inside foreach loops"
            elif loop_var == "index":
                return f"At {path}: Variable '{ref}' is only valid inside foreach loops"
            elif loop_var == "iteration":
                return f"At {path}: Variable '{ref}' is only valid inside while_loop contexts"
            else:
                return f"At {path}: Variable '{ref}' is only valid inside loop contexts"
        
        # Handle legacy loop variables
        elif ref == "item":
            return f"At {path}: Variable '{ref}' is only valid inside foreach loops"
        elif ref == "loop.index":
            return f"At {path}: Variable '{ref}' is only valid inside loop contexts (while_loop, foreach)"
        elif ref == "loop.iteration":
            return f"At {path}: Variable '{ref}' is only valid inside loop contexts (while_loop, foreach)"
        elif "loop_" in ref:
            return f"At {path}: Variable '{ref}' is only valid inside loop contexts (while_loop, foreach)"
        
        # Handle invalid scope names
        elif ref.startswith(("this.", "global.")):
            scope = ref.split(".", 1)[0]
            return f"At {path}: Variable '{ref}' uses '{scope}' scope which is valid, but the field may not exist"
        
        # Generic context-specific error
        else:
            return f"At {path}: Variable '{ref}' is only valid inside specific contexts"

    def _validate_references(self):
        """Cross-validate references between components."""
        # Validate all collected references
        for ref in self.referenced_variables:
            # Skip loop variables with custom names as they are context-specific
            # These are already validated in their proper context during step validation
            if ref.startswith("loop.") and not ref.split(".")[1] in ["item", "index", "iteration"]:
                # This is a custom loop variable, skip global validation
                continue
                
            if not self._validate_variable_reference(ref):
                suggestions = self._get_similar_variables(ref)
                error_msg = f"Undefined variable reference: '{ref}'"
                
                # Special handling for scoped variables
                parts = ref.split(".")
                if len(parts) > 0:
                    root = parts[0]
                    
                    # Check for invalid scope names
                    valid_scopes = {"this", "global", "loop", "inputs", "state", "computed", "raw"}
                    if root not in valid_scopes:
                        error_msg += f". Invalid scope '{root}'. Valid scopes are: {', '.join(sorted(valid_scopes))}"
                    elif root == "this" and not self.state_paths and not self.computed_fields:
                        error_msg += ". No state variables or computed fields are defined for 'this' scope"
                    elif root == "inputs" and not self.input_params:
                        error_msg += ". No input parameters are defined"
                    elif root == "global":
                        error_msg += ". 'global' scope variables are created dynamically and should be valid"
                    elif root == "raw":
                        error_msg += ". The 'raw' namespace has been deprecated. Use 'state' instead"
                    
                if suggestions:
                    error_msg += f". Did you mean: {', '.join(suggestions)}?"
                else:
                    # Provide helpful context about available variables
                    if ref.startswith("state.") and not self.state_paths:
                        error_msg += ". No state variables are defined in default_state"
                    elif ref.startswith("computed.") and not self.computed_fields:
                        error_msg += ". No computed fields are defined"
                        
                self.errors.append(error_msg)

    def validate_strict_schema_only(self, workflow: dict[str, Any]) -> bool:
        """Validate workflow using ONLY JSON schema with strict enforcement.

        This method requires JSON schema validation to pass and doesn't fall back
        to traditional validation. Use this when schema compliance is mandatory.

        Args:
            workflow: Parsed workflow dictionary

        Returns:
            True if workflow is schema-compliant, False otherwise
        """
        if not self.schema or not HAS_JSONSCHEMA:
            self.errors.append("JSON schema validation required but not available")
            return False

        try:
            validate(instance=workflow, schema=self.schema)
            return True
        except ValidationError as e:
            # Collect all validation errors for better diagnostics
            validator = Draft7Validator(self.schema)
            schema_errors = []
            for error in validator.iter_errors(workflow):
                error_path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
                schema_errors.append(f"at {error_path}: {error.message}")

            self.errors.append(f"JSON Schema validation failed:")
            self.errors.extend([f"  - {err}" for err in schema_errors])
            return False
        except Exception as e:
            self.errors.append(f"JSON schema validation error: {str(e)}")
            return False

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
