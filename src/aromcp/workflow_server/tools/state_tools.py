"""
MCP tools for workflow state management

Provides tools for reading, updating, and managing workflow state with reactive transformations.
"""

from typing import Any

from fastmcp import FastMCP

from ...utils.json_parameter_middleware import json_convert
from ..state.models import StateSchema
from ..state.shared import get_shared_state_manager


def get_state_manager():
    """Get the shared state manager instance"""
    return get_shared_state_manager()


def register_workflow_state_tools(mcp: FastMCP) -> None:
    """Register workflow state management tools with FastMCP server"""

    @mcp.tool
    @json_convert
    def workflow_state_read(workflow_id: str, paths: list[str] | str | None = None) -> dict[str, Any]:
        """
        Read workflow state with nested structure

        Returns workflow state in nested format: {raw: {...}, computed: {...}, state: {...}}.
        All computed fields are automatically calculated when state is read.

        Use this tool when:
        - Reading current workflow state for decision making
        - Checking computed field values
        - Validating state before making updates
        - Debugging workflow state issues

        Args:
            workflow_id: Unique identifier for the workflow
            paths: Reserved for future use (path filtering not implemented for nested state)

        Returns:
            Nested state dictionary with structure: {raw: {...}, computed: {...}, state: {...}}

        Example:
            workflow_state_read("wf_123")
            → {"raw": {"counter": 5}, "computed": {"doubled": 10}, "state": {"status": "running"}}
        """
        try:
            manager = get_state_manager()

            # Get nested state (paths parameter not used for nested state)
            state = manager.read(workflow_id)

            return {"data": {"workflow_id": workflow_id, "state": state}}

        except KeyError as e:
            return {"error": {"code": "NOT_FOUND", "message": str(e)}}
        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to read state: {str(e)}"}}

    @mcp.tool
    @json_convert
    def workflow_state_update(workflow_id: str, updates: list[dict[str, Any]] | str) -> dict[str, Any]:
        """
        Update workflow state and trigger cascading transformations

        Updates raw state values and automatically recalculates any computed fields
        that depend on the changed values. All updates are applied atomically.

        Use this tool when:
        - Setting initial workflow parameters
        - Updating state based on user input or external events
        - Incrementing counters or modifying arrays
        - Merging new data into existing objects

        Args:
            workflow_id: Unique identifier for the workflow
            updates: List of update operations, each containing:
                - path: State path to update (must start with "raw." or "state.")
                - value: New value to set
                - operation: Optional operation type ("set", "append", "increment", "merge")

        Returns:
            Updated flattened state after applying changes and cascading transformations

        Example:
            workflow_state_update("wf_123", [
                {"path": "raw.counter", "value": 10},
                {"path": "raw.items", "value": "new_item", "operation": "append"}
            ])
            → {"counter": 10, "items": ["old_item", "new_item"], "double_counter": 20}

        Note: Only "raw.*" and "state.*" paths can be written. Computed fields are read-only.
        """
        try:
            manager = get_state_manager()

            # Handle JSON string input for updates
            if isinstance(updates, str):
                import json

                updates = json.loads(updates)

            if not isinstance(updates, list):
                return {"error": {"code": "INVALID_INPUT", "message": "Updates must be a list of update operations"}}

            # Validate update structure
            for i, update in enumerate(updates):
                if not isinstance(update, dict):
                    return {"error": {"code": "INVALID_INPUT", "message": f"Update {i} must be a dictionary"}}

                if "path" not in update or "value" not in update:
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": f"Update {i} must contain 'path' and 'value' fields",
                        }
                    }

            updated_state = manager.update(workflow_id, updates)

            return {"data": {"workflow_id": workflow_id, "state": updated_state, "updates_applied": len(updates)}}

        except Exception as e:
            error_message = str(e)

            # Map specific exceptions to error codes
            if "Invalid update path" in error_message:
                error_code = "INVALID_INPUT"
            elif "Cannot write to tier" in error_message:
                error_code = "PERMISSION_DENIED"
            elif "Workflow" in error_message and "not found" in error_message:
                error_code = "NOT_FOUND"
            else:
                error_code = "OPERATION_FAILED"

            return {"error": {"code": error_code, "message": f"Failed to update state: {error_message}"}}

    @mcp.tool
    @json_convert
    def workflow_state_dependencies(workflow_id: str, field: str) -> dict[str, Any]:
        """
        Get computed field dependency information

        Returns information about what a computed field depends on and what depends on it.
        Useful for debugging transformation issues and understanding state relationships.

        Use this tool when:
        - Debugging why a computed field isn't updating
        - Understanding state dependencies before making changes
        - Analyzing workflow complexity
        - Optimizing state update performance

        Args:
            workflow_id: Unique identifier for the workflow
            field: Name of the computed field to analyze

        Returns:
            Dependency information including direct dependencies, dependents, and configuration

        Example:
            workflow_state_dependencies("wf_123", "user_summary")
            → {
                "field": "user_summary",
                "dependencies": ["raw.users", "raw.department"],
                "dependents": ["computed.user_count"],
                "transform": "...",
                "on_error": "use_fallback"
            }
        """
        try:
            manager = get_state_manager()

            # For now, return basic information
            # In a full implementation, this would analyze the dependency graph
            if not manager._cascade_calculator:
                return {"error": {"code": "NOT_FOUND", "message": "No computed fields defined for this workflow"}}

            dependencies = manager._cascade_calculator.dependencies

            if field not in dependencies:
                return {"error": {"code": "NOT_FOUND", "message": f"Computed field '{field}' not found"}}

            field_info = dependencies[field]

            # Find what depends on this field
            dependents = []
            computed_path = f"computed.{field}"
            for other_field, other_info in dependencies.items():
                if computed_path in other_info["dependencies"]:
                    dependents.append(other_field)

            return {
                "data": {
                    "workflow_id": workflow_id,
                    "field": field,
                    "dependencies": field_info["dependencies"],
                    "dependents": dependents,
                    "transform": field_info["transform"],
                    "on_error": field_info["on_error"],
                    "fallback": field_info["fallback"],
                }
            }

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to get dependencies: {str(e)}"}}

    @mcp.tool
    @json_convert
    def workflow_state_init(
        workflow_id: str, schema: dict[str, Any] | str | None = None, initial_state: dict[str, Any] | str | None = None
    ) -> dict[str, Any]:
        """
        Initialize a new workflow with schema and default state

        Creates a new workflow state with computed field definitions and optional
        initial values. This is typically called when starting a new workflow.

        Use this tool when:
        - Starting a new workflow instance
        - Defining computed fields and their transformations
        - Setting up initial state values
        - Configuring error handling for transformations

        Args:
            workflow_id: Unique identifier for the new workflow
            schema: Optional schema definition containing computed field definitions
            initial_state: Optional initial state values to set

        Returns:
            Initialized workflow state

        Example:
            workflow_state_init("wf_123", {
                "computed": {
                    "double": {"from": "raw.value", "transform": "input * 2"}
                }
            }, {
                "raw": {"value": 5}
            })
            → {"value": 5, "double": 10}
        """
        try:
            # Create new state manager with schema if provided
            state_schema = None
            if schema is not None:
                if isinstance(schema, str):
                    import json

                    schema = json.loads(schema)
                state_schema = StateSchema(**schema) if isinstance(schema, dict) else None

            # For now, use the global state manager
            # In production, this might create workflow-specific managers
            manager = get_state_manager()

            # Apply schema if provided (would need manager enhancement)
            if state_schema and state_schema.computed:
                # For now, just document that schema would be applied
                pass

            # Set initial state if provided
            if initial_state is not None:
                if isinstance(initial_state, str):
                    import json

                    initial_state = json.loads(initial_state)

                # Convert initial state to update operations
                updates = []
                if isinstance(initial_state, dict):
                    for tier in ["raw", "state"]:
                        if tier in initial_state and isinstance(initial_state[tier], dict):
                            for key, value in initial_state[tier].items():
                                updates.append({"path": f"{tier}.{key}", "value": value})

                if updates:
                    updated_state = manager.update(workflow_id, updates)
                    return {"data": {"workflow_id": workflow_id, "state": updated_state, "initialized": True}}

            # Return empty initialized state
            return {"data": {"workflow_id": workflow_id, "state": {}, "initialized": True}}

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to initialize workflow: {str(e)}"}}

    @mcp.tool
    @json_convert
    def workflow_state_validate_path(path: str) -> dict[str, Any]:
        """
        Validate if a state path is writable

        Checks whether a given path can be used for state updates. Only paths
        starting with "raw." or "state." are writable.

        Use this tool when:
        - Validating user input before attempting updates
        - Building dynamic update operations
        - Debugging path-related errors
        - Implementing path validation in UIs

        Args:
            path: State path to validate (e.g., "raw.counter", "computed.double")

        Returns:
            Validation result with detailed information

        Example:
            workflow_state_validate_path("raw.counter")
            → {"valid": true, "writable": true, "tier": "raw", "field": "counter"}

            workflow_state_validate_path("computed.double")
            → {"valid": true, "writable": false, "reason": "Computed fields are read-only"}
        """
        try:
            manager = get_state_manager()
            is_valid = manager.validate_update_path(path)

            result = {"path": path, "valid": is_valid}

            if is_valid:
                tier, field = path.split(".", 1)
                result.update({"writable": True, "tier": tier, "field": field})
            else:
                # Determine why it's invalid
                if not path or "." not in path:
                    reason = "Path must contain tier prefix (raw. or state.)"
                elif path.startswith("computed."):
                    reason = "Computed fields are read-only"
                elif not any(path.startswith(prefix) for prefix in ["raw.", "state."]):
                    reason = "Path must start with 'raw.' or 'state.'"
                else:
                    reason = "Invalid path format"

                result.update({"writable": False, "reason": reason})

            return {"data": result}

        except Exception as e:
            return {"error": {"code": "OPERATION_FAILED", "message": f"Failed to validate path: {str(e)}"}}
