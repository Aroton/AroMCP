"""Run command tool implementation for Build Tools."""

import os
import subprocess
import time
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path

# Default whitelisted commands for security
DEFAULT_WHITELISTED_COMMANDS = [
    "npm", "yarn", "pnpm", "node", "npx",
    "tsc", "eslint", "jest", "vitest", "mocha",
    "python", "python3", "pip", "pip3",
    "cargo", "rustc", "go", "mvn", "gradle",
    "make", "cmake", "docker", "git"
]


def run_command_impl(
    command: str,
    args: list[str] | None = None,
    project_root: str | None = None,
    allowed_commands: list[str] | None = None,
    timeout: int = 300,
    capture_output: bool = True,
    env_vars: dict[str, str] | None = None
) -> dict[str, Any]:
    """Execute whitelisted commands with structured output.

    Args:
        command: Command to execute (must be in whitelist)
        args: Arguments to pass to the command
        project_root: Directory to execute command in (defaults to MCP_FILE_ROOT)
        allowed_commands: List of allowed commands (defaults to predefined whitelist)
        timeout: Maximum execution time in seconds (default: 300)
        capture_output: Whether to capture stdout/stderr (default: True)
        env_vars: Additional environment variables to set

    Returns:
        Dictionary with command results and metadata
    """
    start_time = time.time()

    try:
        # Resolve project root
        project_root = get_project_root(project_root)

        # Validate project root path
        validation_result = validate_file_path(project_root, project_root)
        if not validation_result.get("valid", False):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": validation_result.get("error", "Invalid project root path")
                }
            }

        # Validate command against whitelist
        if allowed_commands is None:
            allowed_commands = DEFAULT_WHITELISTED_COMMANDS

        if command not in allowed_commands:
            return {
                "error": {
                    "code": "PERMISSION_DENIED",
                    "message": f"Command '{command}' not in whitelist. Allowed: {', '.join(allowed_commands)}"
                }
            }

        # Build command list
        cmd_list = [command]
        if args:
            cmd_list.extend(args)

        # Set up environment
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        # Execute command
        try:
            result = subprocess.run(  # noqa: S603 # Safe: command validated against whitelist of predetermined commands
                cmd_list,
                cwd=project_root,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                env=env
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "data": {
                    "command": " ".join(cmd_list),
                    "exit_code": result.returncode,
                    "stdout": result.stdout if capture_output else "",
                    "stderr": result.stderr if capture_output else "",
                    "success": result.returncode == 0,
                    "working_directory": project_root
                },
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                    "duration_ms": duration_ms,
                    "timeout_seconds": timeout
                }
            }

        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "error": {
                    "code": "TIMEOUT",
                    "message": f"Command '{' '.join(cmd_list)}' timed out after {timeout} seconds"
                },
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                    "duration_ms": duration_ms,
                    "timeout_seconds": timeout
                }
            }

        except subprocess.SubprocessError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Command execution failed: {str(e)}"
                },
                "metadata": {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                    "duration_ms": duration_ms
                }
            }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Unexpected error: {str(e)}"
            },
            "metadata": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                "duration_ms": duration_ms
            }
        }
