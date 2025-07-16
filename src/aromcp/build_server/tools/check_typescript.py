"""Check TypeScript errors tool implementation."""

import re
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root


def check_typescript_impl(files: str | list[str] | None = None) -> dict[str, Any]:
    """Run TypeScript compiler to find type errors.

    Args:
        files: Specific files to check (optional, defaults to all files in project)

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

        # Build TypeScript command
        cmd = ["npx", "tsc", "--noEmit"]
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
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
        except subprocess.TimeoutExpired as e:
            raise ValueError("TypeScript check timed out") from e
        except FileNotFoundError as e:
            raise ValueError("TypeScript compiler not found (npx tsc)") from e

        # Parse errors from output
        errors = _parse_tsc_output(result.stderr)

        # Build result - only show errors if there are any
        if len(errors) == 0:
            return {
                "errors": [],
                "check_again": False
            }
        else:
            # Cap errors at first file's errors
            first_file_errors = []
            if errors:
                first_file = errors[0]["file"]
                first_file_errors = [err for err in errors if err["file"] == first_file]
            
            return {
                "errors": first_file_errors,
                "total": len(errors),
                "check_again": True  # Always suggest checking again after fixing TypeScript errors
            }

    except Exception as e:
        raise ValueError(f"TypeScript check failed: {str(e)}") from e


def _parse_tsc_output(output: str) -> list[dict[str, Any]]:
    """Parse TypeScript compiler output into structured errors."""
    errors = []

    # TypeScript error pattern: file(line,col): error TSxxxx: message
    pattern = r'^(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+TS(\d+):\s+(.+)$'

    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = re.match(pattern, line)
        if match:
            file_path, line_num, col_num, severity, error_code, message = match.groups()

            errors.append({
                "file": file_path,
                "line": int(line_num),
                "column": int(col_num),
                "severity": severity,
                "code": f"TS{error_code}",
                "message": message.strip()
            })

    return errors
