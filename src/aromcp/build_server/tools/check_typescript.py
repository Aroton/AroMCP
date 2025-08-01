"""Check TypeScript errors tool implementation."""

import re
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root
from ..models.build_models import CheckTypescriptResponse, TypescriptError


def check_typescript_impl(files: str | list[str] | None = None) -> CheckTypescriptResponse:
    """Run TypeScript compiler to find type errors.

    Args:
        files: Specific files to check (optional, defaults to comprehensive project check)

    Returns:
        Dictionary with errors and success status
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)
        project_path = Path(project_root)

        # Check if TypeScript is available
        if not (project_path / "tsconfig.json").exists():
            raise ValueError("No tsconfig.json found in project root")

        # Build TypeScript command - use more comprehensive checking by default
        if not files:
            # When no files specified, use the most comprehensive TypeScript check
            # This mirrors what build processes typically do
            cmd = ["npx", "tsc", "--noEmit", "--skipLibCheck"]

            # Try to detect if there are multiple tsconfig files or project references
            if (project_path / "tsconfig.build.json").exists():
                cmd = ["npx", "tsc", "--noEmit", "--project", "tsconfig.build.json"]
            elif (project_path / "tsconfig.json").exists():
                # Check if tsconfig.json has project references
                try:
                    import json

                    with open(project_path / "tsconfig.json") as f:
                        tsconfig = json.load(f)
                        if tsconfig.get("references"):
                            cmd = ["npx", "tsc", "--build", "--dry", "--force"]
                        else:
                            cmd = ["npx", "tsc", "--noEmit", "--project", "."]
                except (json.JSONDecodeError, FileNotFoundError):
                    # Fall back to basic command
                    cmd = ["npx", "tsc", "--noEmit"]
        else:
            # When checking specific files, still use project configuration
            # This ensures path mappings and other project settings are available
            cmd = ["npx", "tsc", "--noEmit", "--project", "."]

        if files:
            # Handle JSON string conversion
            if isinstance(files, str):
                try:
                    import json

                    files = json.loads(files)
                except json.JSONDecodeError:
                    files = [files]  # Treat as single file

            # Handle files/directories/glob patterns
            expanded_files = []
            for file_path in files if files else []:
                # Check if it's a glob pattern (contains * or **)
                if "*" in file_path:
                    # Pass glob patterns directly to TypeScript compiler
                    expanded_files.append(file_path)
                else:
                    # Handle regular files and directories
                    full_path = project_path / file_path
                    if full_path.is_dir():
                        # If it's a directory, append /* to glob all files in it
                        expanded_files.append(f"{file_path}/*")
                    elif full_path.exists():
                        expanded_files.append(file_path)
                    else:
                        raise ValueError(f"File or directory not found: {file_path}")

            # Add expanded files to command
            cmd.extend(expanded_files)

        # Run TypeScript compiler
        try:
            result = subprocess.run(  # noqa: S603 # Intentional subprocess call for TypeScript compiler
                cmd, cwd=project_root, capture_output=True, text=True, timeout=120
            )
        except subprocess.TimeoutExpired as e:
            raise ValueError("TypeScript check timed out") from e
        except FileNotFoundError as e:
            raise ValueError("TypeScript compiler not found (npx tsc)") from e

        # Parse errors from output - TypeScript can write to both stdout and stderr
        errors = []
        if result.stderr:
            errors.extend(_parse_tsc_output(result.stderr))
        if result.stdout:
            errors.extend(_parse_tsc_output(result.stdout))

        # Count files checked (estimate based on command)
        files_checked = 1 if files else 100  # Rough estimate for project-wide check

        # Convert dict errors to TypescriptError dataclasses
        typed_errors = []
        for error in errors:
            typed_errors.append(
                TypescriptError(
                    file=error["file"],
                    line=error["line"],
                    column=error["column"],
                    message=error["message"],
                    code=error["code"],
                    severity=error["severity"],
                )
            )

        # Build result - only show errors if there are any
        if len(typed_errors) == 0:
            return CheckTypescriptResponse(
                errors=[],
                total_errors=0,
                files_checked=files_checked,
                check_again=False,
                success=True,
            )
        else:
            # Return all errors from all files
            return CheckTypescriptResponse(
                errors=typed_errors,
                total_errors=len(typed_errors),
                files_checked=files_checked,
                check_again=True,  # Always suggest checking again after fixing TypeScript errors
                success=False,
            )

    except Exception as e:
        raise ValueError(f"TypeScript check failed: {str(e)}") from e


def _parse_tsc_output(output: str) -> list[dict[str, Any]]:
    """Parse TypeScript compiler output into structured errors."""
    errors = []

    # TypeScript error pattern: file(line,col): error TSxxxx: message
    pattern = r"^(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+TS(\d+):\s+(.+)$"

    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line)
        if match:
            file_path, line_num, col_num, severity, error_code, message = match.groups()

            errors.append(
                {
                    "file": file_path,
                    "line": int(line_num),
                    "column": int(col_num),
                    "severity": severity,
                    "code": f"TS{error_code}",
                    "message": message.strip(),
                }
            )

    return errors
