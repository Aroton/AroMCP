"""Shell command step processor for workflow execution."""

import os
import subprocess
from typing import Any

from ....filesystem_server._security import get_project_root


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

        # Get timeout and error handling configuration
        timeout = step_definition.get("timeout", 30)  # Default 30 seconds
        error_handling = step_definition.get("error_handling", {"strategy": "fail"})
        working_directory = step_definition.get("working_directory")

        try:
            # Determine working directory
            if working_directory:
                # Use specified working directory
                work_dir = working_directory
                if not os.path.isabs(work_dir):
                    # Make relative paths relative to project root
                    project_root = get_project_root()
                    work_dir = os.path.join(project_root, work_dir)
            else:
                # Use project root as default
                work_dir = get_project_root()

            # Ensure the working directory exists, fallback to current directory if not
            if not os.path.exists(work_dir) or not os.path.isdir(work_dir):
                work_dir = os.getcwd()

            # Execute command in the working directory (shell=True is intentional for workflow step execution)
            result = subprocess.run(  # noqa: S602
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
            )

            output = {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": command,
            }

            # Check if command failed and handle according to error_handling strategy
            if result.returncode != 0:
                strategy = error_handling.get("strategy", "fail")
                
                if strategy == "fail":
                    # Fail immediately
                    return {
                        "status": "failed", 
                        "error": f"Command failed with exit code {result.returncode}: {result.stderr}",
                        "output": output
                    }
                elif strategy == "continue":
                    # Continue execution despite failure
                    output["warning"] = f"Command failed with exit code {result.returncode} but continuing due to error_handling strategy"
                elif strategy == "fallback":
                    # Use fallback value
                    fallback_value = error_handling.get("fallback_value", "")
                    output["stdout"] = str(fallback_value)
                    output["stderr"] = ""
                    output["returncode"] = 0

            # State updates are now handled by the embedded state update processor
            # in step_processors.py, so we don't need to handle them here.
            # The embedded processor will examine state_update and state_updates fields
            # and apply them after the shell command completes.

            return {"status": "success", "output": output, "execution_type": "internal"}

        except subprocess.TimeoutExpired:
            strategy = error_handling.get("strategy", "fail")
            
            if strategy == "fail":
                return {"status": "failed", "error": f"Command timed out after {timeout} seconds: {command}"}
            elif strategy == "continue":
                return {"status": "success", "output": {"warning": f"Command timed out after {timeout} seconds but continuing"}}
            elif strategy == "fallback":
                fallback_value = error_handling.get("fallback_value", "")
                return {"status": "success", "output": {"stdout": str(fallback_value), "stderr": "", "returncode": 0}}
            else:
                return {"status": "failed", "error": f"Command timed out after {timeout} seconds: {command}"}
        except Exception as e:
            strategy = error_handling.get("strategy", "fail")
            
            if strategy == "fail":
                return {"status": "failed", "error": f"Command execution failed: {e}"}
            elif strategy == "continue":
                return {"status": "success", "output": {"warning": f"Command execution failed but continuing: {e}"}}
            elif strategy == "fallback":
                fallback_value = error_handling.get("fallback_value", "")
                return {"status": "success", "output": {"stdout": str(fallback_value), "stderr": "", "returncode": 0}}
            else:
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
