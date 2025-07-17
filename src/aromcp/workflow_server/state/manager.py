"""
State manager for MCP Workflow System

Manages workflow state with flattened views, path validation, and atomic updates.
Handles cascading transformations when dependencies change.
"""

import copy
import threading
from typing import Any

from .models import ComputedFieldError, InvalidPathError, StateSchema, WorkflowState
from .transformer import CascadingUpdateCalculator, DependencyResolver, TransformationEngine


class StateManager:
    """
    Manages workflow state with reactive transformations

    Provides:
    - Flattened view generation for reading
    - Path validation for writing
    - Atomic state updates
    - Cascading transformations
    """

    def __init__(self, schema: dict[str, Any] | StateSchema | None = None):
        """
        Initialize state manager

        Args:
            schema: Optional schema defining computed fields and validation rules
        """
        self._states: dict[str, WorkflowState] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

        # Set up schema and transformation components
        if isinstance(schema, dict):
            self._schema = StateSchema(**schema)
        elif isinstance(schema, StateSchema):
            self._schema = schema
        else:
            self._schema = StateSchema()

        self._transformer = TransformationEngine()
        self._dependency_resolver = None
        self._cascade_calculator = None

        # Initialize transformation components if schema has computed fields
        if self._schema.computed:
            self._setup_transformations()

    def _setup_transformations(self) -> None:
        """Initialize transformation and dependency resolution components"""
        schema_dict = {
            "computed": self._schema.computed,
            "raw": self._schema.raw,
            "state": self._schema.state
        }

        self._dependency_resolver = DependencyResolver(schema_dict)
        resolved_deps = self._dependency_resolver.resolve()
        self._cascade_calculator = CascadingUpdateCalculator(resolved_deps)

    def _get_workflow_lock(self, workflow_id: str) -> threading.Lock:
        """Get or create a lock for a specific workflow"""
        with self._global_lock:
            if workflow_id not in self._locks:
                self._locks[workflow_id] = threading.Lock()
            return self._locks[workflow_id]

    def _get_or_create_state(self, workflow_id: str) -> WorkflowState:
        """Get existing state or create new one with defaults"""
        if workflow_id not in self._states:
            self._states[workflow_id] = WorkflowState()
        return self._states[workflow_id]

    def get_flattened_view(self, state: WorkflowState, paths: list[str] | None = None) -> dict[str, Any]:
        """
        Generate flattened view of state for reading

        Precedence order: computed > raw > state

        Args:
            state: WorkflowState to flatten
            paths: Optional list of specific paths to include

        Returns:
            Flattened dictionary with computed values taking precedence
        """
        flattened = {}

        # Start with state tier (lowest precedence)
        flattened.update(self._flatten_dict(state.state))

        # Add raw tier (middle precedence)
        flattened.update(self._flatten_dict(state.raw))

        # Add computed tier (highest precedence)
        flattened.update(self._flatten_dict(state.computed))

        # Filter to specific paths if requested
        if paths is not None:
            filtered = {}
            for path in paths:
                if path in flattened:
                    filtered[path] = flattened[path]
                else:
                    filtered[path] = None
            return filtered

        return flattened

    def _flatten_dict(self, d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        """
        Flatten nested dictionary while preserving object structure

        This preserves the original object hierarchy rather than creating
        dot-separated keys, which maintains JavaScript-like property access.
        """
        # For now, just return the dictionary as-is to maintain object structure
        # This allows access like state["user"]["name"] rather than state["user.name"]
        return d.copy()

    def validate_update_path(self, path: str) -> bool:
        """
        Validate that a path can be written to

        Only paths starting with "raw." or "state." are writable.
        Computed paths are read-only.

        Args:
            path: Path to validate (e.g., "raw.counter", "state.version")

        Returns:
            True if path is writable, False otherwise
        """
        if not path or not isinstance(path, str):
            return False

        # Path must contain at least one dot
        if "." not in path:
            return False

        parts = path.split(".", 1)
        if len(parts) != 2:
            return False

        tier, field = parts

        # Check tier is valid and field is not empty
        if tier not in ("raw", "state") or not field or field.startswith("."):
            return False

        # Check for invalid patterns like double dots
        if ".." in path or path.endswith("."):
            return False

        return True

    def read(self, workflow_id: str, paths: list[str] | None = None) -> dict[str, Any]:
        """
        Read workflow state with flattened view

        Args:
            workflow_id: Unique workflow identifier
            paths: Optional list of specific paths to read

        Returns:
            Flattened state dictionary

        Raises:
            KeyError: If workflow doesn't exist
        """
        lock = self._get_workflow_lock(workflow_id)

        with lock:
            if workflow_id not in self._states:
                raise KeyError(f"Workflow '{workflow_id}' not found")

            state = self._states[workflow_id]
            return self.get_flattened_view(state, paths)

    def update(self, workflow_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Apply atomic updates to workflow state

        Updates are applied atomically - either all succeed or none are applied.
        After successful updates, cascading transformations are triggered.

        Args:
            workflow_id: Unique workflow identifier
            updates: List of update operations, each containing:
                - path: State path to update (e.g., "raw.counter")
                - value: New value to set
                - operation: Optional operation ("set", "append", "increment", "merge")

        Returns:
            Updated flattened state

        Raises:
            InvalidPathError: If any path is invalid
            ValueError: If update operation fails
        """
        lock = self._get_workflow_lock(workflow_id)

        with lock:
            # Get or create state
            state = self._get_or_create_state(workflow_id)

            # Validate all updates first (fail fast)
            for update in updates:
                path = update.get("path", "")
                if not self.validate_update_path(path):
                    raise InvalidPathError(f"Invalid update path: '{path}'")

            # Create backup for atomic operation
            original_state = copy.deepcopy(state)

            try:
                # Apply all updates
                changed_paths = []
                for update in updates:
                    path = update["path"]
                    value = update["value"]
                    operation = update.get("operation", "set")

                    self._apply_single_update(state, path, value, operation)
                    changed_paths.append(path)

                # Trigger cascading transformations if schema is defined
                if self._cascade_calculator:
                    self._update_computed_fields(state, changed_paths)

                # Store updated state
                self._states[workflow_id] = state

                # Return flattened view
                return self.get_flattened_view(state)

            except Exception as e:
                # Restore original state on any failure
                self._states[workflow_id] = original_state
                raise e

    def _apply_single_update(self, state: WorkflowState, path: str, value: Any, operation: str) -> None:
        """
        Apply a single update operation to state

        Args:
            state: WorkflowState to modify
            path: Path to update (e.g., "raw.counter")
            value: Value to apply
            operation: Operation type ("set", "append", "increment", "merge")
        """
        tier, field_path = path.split(".", 1)

        # Get the appropriate tier
        if tier == "raw":
            target_dict = state.raw
        elif tier == "state":
            target_dict = state.state
        else:
            raise InvalidPathError(f"Cannot write to tier: {tier}")

        # Handle nested paths
        if "." in field_path:
            # Navigate to parent object
            path_parts = field_path.split(".")
            current = target_dict

            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    raise ValueError(f"Cannot set nested property on non-object: {part}")
                current = current[part]

            final_key = path_parts[-1]
        else:
            current = target_dict
            final_key = field_path

        # Apply operation
        if operation == "set":
            current[final_key] = value
        elif operation == "append":
            if final_key not in current:
                current[final_key] = []
            if not isinstance(current[final_key], list):
                raise ValueError(f"Cannot append to non-list: {final_key}")
            current[final_key].append(value)
        elif operation == "increment":
            if final_key not in current:
                current[final_key] = 0
            if not isinstance(current[final_key], int | float):
                raise ValueError(f"Cannot increment non-number: {final_key}")
            current[final_key] += value
        elif operation == "merge":
            if final_key not in current:
                current[final_key] = {}
            if not isinstance(current[final_key], dict) or not isinstance(value, dict):
                raise ValueError(f"Cannot merge non-objects: {final_key}")
            current[final_key].update(value)
        else:
            raise ValueError(f"Unknown operation: {operation}")

    def _update_computed_fields(self, state: WorkflowState, changed_paths: list[str]) -> None:
        """
        Update computed fields affected by changed paths

        Args:
            state: WorkflowState to update
            changed_paths: List of paths that changed
        """
        if not self._cascade_calculator:
            return

        affected_fields = self._cascade_calculator.get_affected_fields(changed_paths)

        for field_name in affected_fields:
            try:
                self._compute_field(state, field_name)
            except Exception as e:
                # Handle errors based on field configuration
                field_info = self._cascade_calculator.dependencies[field_name]
                # print(f"DEBUG: Computation error for {field_name}: {e}")
                self._handle_computation_error(state, field_name, field_info, e)

    def _compute_field(self, state: WorkflowState, field_name: str) -> None:
        """
        Compute value for a single computed field

        Args:
            state: WorkflowState containing input values
            field_name: Name of computed field to update
        """
        field_info = self._cascade_calculator.dependencies[field_name]
        dependencies = field_info["dependencies"]
        transform = field_info["transform"]

        # Gather input values
        inputs = []
        for dep_path in dependencies:
            value = self._get_value_from_path(state, dep_path)
            inputs.append(value)

        # Execute transformation
        if len(inputs) == 1:
            result = self._transformer.execute(transform, inputs[0])
        else:
            result = self._transformer.execute(transform, inputs)

        # Store result
        state.computed[field_name] = result

    def _get_value_from_path(self, state: WorkflowState, path: str) -> Any:
        """
        Get value from state using a path like "raw.counter" or "computed.double"

        Args:
            state: WorkflowState to read from
            path: Path to value

        Returns:
            Value at path, or None if not found
        """
        if "." not in path:
            return None

        tier, field_path = path.split(".", 1)

        if tier == "raw":
            source = state.raw
        elif tier == "computed":
            source = state.computed
        elif tier == "state":
            source = state.state
        else:
            return None

        # Navigate nested path
        current = source
        for part in field_path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def _handle_computation_error(
        self, state: WorkflowState, field_name: str, field_info: dict[str, Any], error: Exception
    ) -> None:
        """
        Handle computation errors based on field configuration

        Args:
            state: WorkflowState to potentially update
            field_name: Name of field that failed
            field_info: Field configuration including error handling
            error: Exception that occurred
        """
        on_error = field_info.get("on_error", "use_fallback")

        if on_error == "use_fallback":
            fallback = field_info.get("fallback", None)
            state.computed[field_name] = fallback
        elif on_error == "propagate":
            raise ComputedFieldError(f"Computation failed for {field_name}") from error
        elif on_error == "ignore":
            # Remove field from computed state if it exists
            state.computed.pop(field_name, None)
        else:
            # Default to fallback behavior
            fallback = field_info.get("fallback", None)
            state.computed[field_name] = fallback
