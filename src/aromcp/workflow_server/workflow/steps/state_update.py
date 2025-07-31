"""State update step processor for workflow execution."""

from typing import Any


class StateUpdateProcessor:
    """Processes state update steps."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Execute a state update step.

        Args:
            step_definition: Step definition with path and value/operation
            workflow_id: ID of the workflow instance
            state_manager: State manager for updates

        Returns:
            Execution result with updated state
        """
        try:
            # Extract update information
            path = step_definition.get("path")
            value = step_definition.get("value")
            operation = step_definition.get("operation")

            if not path:
                return {"status": "failed", "error": "Missing 'path' in state_update step"}

            # Handle different operation types
            if operation:
                current_state = state_manager.read(workflow_id)
                clean_path = path.replace("raw.", "").replace("state.", "")
                current_value = StateUpdateProcessor._get_nested_value(current_state, clean_path)

                if operation == "increment":
                    value = (current_value or 0) + (value or 1)
                elif operation == "decrement":
                    value = (current_value or 0) - (value or 1)
                elif operation == "append":
                    if isinstance(current_value, list):
                        value = current_value + [value]
                    else:
                        value = [current_value, value] if current_value is not None else [value]
                elif operation == "multiply":
                    value = (current_value or 0) * (value or 1)
                else:
                    return {"status": "failed", "error": f"Unknown operation: {operation}"}

            # Apply the update
            updates = [{"path": path, "value": value}]
            state_manager.update(workflow_id, updates)

            # Get updated state
            updated_state = state_manager.read(workflow_id)

            return {"status": "success", "updates_applied": updates, "updated_state": updated_state}

        except Exception as e:
            return {"status": "failed", "error": f"State update failed: {e}"}

    @staticmethod
    def _get_nested_value(obj: dict[str, Any], path: str) -> Any:
        """Get a nested value from an object using dot notation."""
        keys = path.split(".")
        current = obj

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current


class BatchStateUpdateProcessor:
    """Processes multiple state updates in a single step."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Execute multiple state updates atomically.

        Args:
            step_definition: Step definition with list of updates
            workflow_id: ID of the workflow instance
            state_manager: State manager for updates

        Returns:
            Execution result with all updates applied
        """
        try:
            updates = step_definition.get("updates")
            if not updates or not isinstance(updates, list):
                return {"status": "failed", "error": "Missing or invalid 'updates' list in batch_state_update step"}

            # Validate all updates first
            formatted_updates = []
            for i, update in enumerate(updates):
                if not isinstance(update, dict):
                    return {"status": "failed", "error": f"Update {i} must be an object with 'path' and 'value'"}

                path = update.get("path")
                value = update.get("value")

                if not path:
                    return {"status": "failed", "error": f"Update {i} missing required 'path' field"}

                formatted_updates.append({"path": path, "value": value})

            # Apply all updates atomically
            state_manager.update(workflow_id, formatted_updates)

            # Get updated state
            updated_state = state_manager.read(workflow_id)

            return {"status": "success", "updates_applied": formatted_updates, "updated_state": updated_state}

        except Exception as e:
            return {"status": "failed", "error": f"Batch state update failed: {e}"}
