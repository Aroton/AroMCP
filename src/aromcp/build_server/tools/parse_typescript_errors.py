"""Parse TypeScript errors tool implementation for Build Tools."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path
from ...utils.pagination import simplify_pagination


def parse_typescript_errors_impl(
    project_root: str | None = None,
    tsconfig_path: str = "tsconfig.json",
    files: list[str] | None = None,
    include_warnings: bool = True,
    timeout: int = 120,
    page: int = 1,
    max_tokens: int = 20000,
    use_build_command: bool = False
) -> dict[str, Any]:
    """Run tsc and return structured error data.

    Args:
        project_root: Directory containing TypeScript project (defaults to MCP_FILE_ROOT)
        tsconfig_path: Path to tsconfig.json relative to project_root
        files: Specific files to check (optional, defaults to all files in project)
        include_warnings: Whether to include TypeScript warnings
        timeout: Maximum execution time in seconds
        page: Page number for pagination (1-based, default: 1)
        max_tokens: Maximum tokens per page (default: 20000)
        use_build_command: Whether to use build command for type checking (e.g., "npm run build")

    Returns:
        Dictionary with paginated structured TypeScript error data
    """
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

        project_path = Path(project_root)
        tsconfig_full_path = project_path / tsconfig_path

        # Check if tsconfig.json exists
        if not tsconfig_full_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"TypeScript config not found: {tsconfig_path}"
                }
            }

        # Choose command based on use_build_command flag
        if use_build_command:
            # Try to use build command which often has better module resolution
            # First check if package.json exists to determine build command
            package_json_path = project_path / "package.json"
            if package_json_path.exists():
                try:
                    with open(package_json_path, encoding='utf-8') as f:
                        package_json = json.load(f)

                    scripts = package_json.get("scripts", {})
                    if "type-check" in scripts:
                        cmd = ["npm", "run", "type-check"]
                    elif "build" in scripts:
                        cmd = ["npm", "run", "build"]
                    else:
                        # Fallback to tsc if no suitable script found
                        cmd = ["npx", "tsc", "--noEmit", "--pretty", "false"]
                        cmd.extend(["--project", str(tsconfig_full_path)])
                except (json.JSONDecodeError, FileNotFoundError):
                    # Fallback to tsc if package.json can't be read
                    cmd = ["npx", "tsc", "--noEmit", "--pretty", "false"]
                    cmd.extend(["--project", str(tsconfig_full_path)])
            else:
                # Fallback to tsc if no package.json
                cmd = ["npx", "tsc", "--noEmit", "--pretty", "false"]
                cmd.extend(["--project", str(tsconfig_full_path)])
        else:
            # Use direct tsc command (original behavior)
            cmd = ["npx", "tsc", "--noEmit", "--pretty", "false"]

            # Always explicitly specify the tsconfig.json path for better path resolution
            cmd.extend(["--project", str(tsconfig_full_path)])

            # Try to read tsconfig.json to ensure proper module resolution
            try:
                with open(tsconfig_full_path, encoding='utf-8') as f:
                    tsconfig_content = json.load(f)

                # Check if baseUrl is set, if not, ensure TypeScript uses the project root
                compiler_options = tsconfig_content.get("compilerOptions", {})
                if "baseUrl" not in compiler_options and "paths" in compiler_options:
                    # Add explicit baseUrl parameter if paths are defined but baseUrl is not
                    cmd.extend(["--baseUrl", str(project_path)])
            except (json.JSONDecodeError, FileNotFoundError, KeyError):
                # If we can't read the tsconfig, continue with the default behavior
                pass

        # Add specific files if provided (only for tsc command, not build command)
        if files and not use_build_command:
            # Validate file paths
            for file_path in files:
                full_file_path = project_path / file_path
                if not full_file_path.exists():
                    return {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"File not found: {file_path}"
                        }
                    }
                # Validate file path is within project
                validation_result = validate_file_path(str(full_file_path), project_root)
                if not validation_result.get("valid", False):
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": f"Invalid file path: {file_path}"
                        }
                    }
            cmd.extend(files)
        elif files and use_build_command:
            # When using build command, we can't specify individual files
            # Log this limitation in the metadata
            pass

        try:
            result = subprocess.run(  # noqa: S603 # Safe: cmd built from predetermined TypeScript compiler commands
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse TypeScript output
            errors = _parse_tsc_output(result.stdout, result.stderr, include_warnings)

            # Categorize errors
            error_categories = _categorize_errors(errors)

            # Generate summary
            summary = {
                "total_errors": len([e for e in errors if e["severity"] == "error"]),
                "total_warnings": len([e for e in errors if e["severity"] == "warning"]),
                "total_issues": len(errors),
                "files_with_errors": len({e["file"] for e in errors if e["severity"] == "error"}),
                "files_with_warnings": len({e["file"] for e in errors if e["severity"] == "warning"}),
                "exit_code": result.returncode,
                "compilation_success": result.returncode == 0
            }

            # Create metadata for pagination
            metadata = {
                "summary": summary,
                "categories": error_categories,
                "tsconfig_path": str(tsconfig_full_path),
                "command": " ".join(cmd),
                "used_build_command": use_build_command
            }

            # Add note about file limitations when using build command
            if files and use_build_command:
                metadata["note"] = "Individual file checking not supported with build command; checked entire project"

            # Apply simplified pagination with token-based sizing
            result = simplify_pagination(
                items=errors,
                page=page,
                max_tokens=max_tokens,
                sort_key=lambda x: (x.get("file", ""), x.get("line", 0), x.get("column", 0)),
                metadata=metadata
            )
            
            return {"data": result}

        except subprocess.TimeoutExpired:
            return {
                "error": {
                    "code": "TIMEOUT",
                    "message": f"TypeScript compilation timed out after {timeout} seconds"
                }
            }

        except subprocess.SubprocessError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to run TypeScript compiler: {str(e)}"
                }
            }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to parse TypeScript errors: {str(e)}"
            }
        }


def _parse_tsc_output(stdout: str, stderr: str, include_warnings: bool) -> list[dict[str, Any]]:
    """Parse TypeScript compiler output into structured error data."""
    errors = []

    # Combine stdout and stderr
    output = stdout + "\n" + stderr

    # TypeScript error pattern: file(line,column): error/warning TSxxxx: message
    error_pattern = re.compile(
        r'^(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+TS(\d+):\s+(.+)$',
        re.MULTILINE
    )

    for match in error_pattern.finditer(output):
        file_path, line, column, severity, code, message = match.groups()

        # Skip warnings if not requested
        if severity == "warning" and not include_warnings:
            continue

        # Clean up file path (remove leading ./ if present)
        if file_path.startswith("./"):
            file_path = file_path[2:]

        errors.append({
            "file": file_path,
            "line": int(line),
            "column": int(column),
            "severity": severity,
            "code": f"TS{code}",
            "message": message.strip(),
            "category": _get_error_category(code)
        })

    # Also look for general compilation errors
    general_error_pattern = re.compile(
        r'^error\s+TS(\d+):\s+(.+)$',
        re.MULTILINE
    )

    for match in general_error_pattern.finditer(output):
        code, message = match.groups()

        errors.append({
            "file": "",
            "line": 0,
            "column": 0,
            "severity": "error",
            "code": f"TS{code}",
            "message": message.strip(),
            "category": _get_error_category(code)
        })

    return errors


def _get_error_category(code: str) -> str:
    """Categorize TypeScript error by code."""
    code_num = int(code)

    # Common TypeScript error categories
    if 1000 <= code_num <= 1999:
        return "syntax"
    elif 2000 <= code_num <= 2999:
        return "semantic"
    elif 4000 <= code_num <= 4999:
        return "declaration"
    elif 5000 <= code_num <= 5999:
        return "compiler_options"
    elif 6000 <= code_num <= 6999:
        return "command_line"
    elif 7000 <= code_num <= 7999:
        return "jsx"
    elif 8000 <= code_num <= 8999:
        return "module_resolution"
    else:
        return "other"


def _categorize_errors(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Categorize and summarize TypeScript errors."""
    categories = {}

    # Group by category
    for error in errors:
        category = error["category"]
        if category not in categories:
            categories[category] = {
                "count": 0,
                "errors": 0,
                "warnings": 0,
                "common_codes": {},
                "files": set()
            }

        categories[category]["count"] += 1
        categories[category][error["severity"] + "s"] += 1

        # Track common error codes
        code = error["code"]
        if code not in categories[category]["common_codes"]:
            categories[category]["common_codes"][code] = 0
        categories[category]["common_codes"][code] += 1

        # Track affected files
        if error["file"]:
            categories[category]["files"].add(error["file"])

    # Convert sets to lists for JSON serialization
    for category in categories.values():
        category["files"] = list(category["files"])

    # Sort common codes by frequency
    for category in categories.values():
        category["common_codes"] = dict(
            sorted(
                category["common_codes"].items(),
                key=lambda x: x[1],
                reverse=True
            )
        )

    return categories
