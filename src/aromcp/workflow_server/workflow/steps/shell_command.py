"""Shell command step processor for workflow execution."""

import subprocess
from typing import Any


class ShellCommandProcessor:
    """Processes shell command steps internally."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Execute a shell command step.

        Args:
            step_definition: Step definition with command and optional state_update
            workflow_id: ID of the workflow instance
            state_manager: State manager for updates

        Returns:
            Execution result with output and any state updates
        """
        command = step_definition.get("command")
        if not command:
            return {"status": "failed", "error": "Missing 'command' in shell_command step"}

        try:
            # Execute command (shell=True is intentional for workflow step execution)
            result = subprocess.run(  # noqa: S602
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": command,
            }

            # Update state if specified
            state_update = step_definition.get("state_update")
            if state_update:
                path = state_update.get("path")
                value_source = state_update.get("value", "stdout")

                if path:
                    # Determine value to store
                    if value_source == "stdout":
                        value = result.stdout.strip()
                    elif value_source == "stderr":
                        value = result.stderr.strip()
                    elif value_source == "returncode":
                        value = result.returncode
                    elif value_source == "full_output":
                        value = output
                    else:
                        value = value_source  # Literal value

                    # Apply state update
                    updates = [{"path": path, "value": value}]
                    state_manager.update(workflow_id, updates)

            return {"status": "success", "output": output, "execution_type": "internal"}

        except subprocess.TimeoutExpired:
            return {"status": "failed", "error": f"Command timed out after 30 seconds: {command}"}
        except Exception as e:
            return {"status": "failed", "error": f"Command execution failed: {e}"}


class AgentShellCommandProcessor:
    """Formats shell commands to be executed by agents."""

    @staticmethod
    def process(step_definition: dict[str, Any], workflow_id: str, state_manager) -> dict[str, Any]:
        """Format a shell command for agent execution.

        Args:
            step_definition: Step definition with command and reason
            workflow_id: ID of the workflow instance
            state_manager: State manager (not used for formatting)

        Returns:
            Formatted step for agent execution
        """
        command = step_definition.get("command")
        if not command:
            return {"status": "failed", "error": "Missing 'command' in agent_shell_command step"}

        return {
            "status": "success",
            "agent_action": {
                "type": "shell_command",
                "command": command,
                "reason": step_definition.get("reason", "Custom command execution"),
                "capture_output": step_definition.get("capture_output", True),
                "state_update": step_definition.get("state_update"),
            },
            "execution_type": "agent",
        }
