"""Run Next.js build tool implementation for Build Tools."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path


def run_nextjs_build_impl(
    project_root: str | None = None,
    build_command: str = "npm run build",
    include_typescript_check: bool = True,
    include_lint_check: bool = True,
    timeout: int = 600
) -> dict[str, Any]:
    """Run Next.js build with categorized error reporting.
    
    Args:
        project_root: Directory containing Next.js project (defaults to MCP_FILE_ROOT)
        build_command: Command to run the build (default: "npm run build")
        include_typescript_check: Whether to include TypeScript type checking
        include_lint_check: Whether to include ESLint checking
        timeout: Maximum execution time in seconds
        
    Returns:
        Dictionary with categorized Next.js build results
    """
    try:
        # Resolve project root
        if project_root is None:
            project_root = get_project_root()

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

        # Verify it's a Next.js project
        if not _is_nextjs_project(project_path):
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Not a Next.js project. Missing next.config.js/mjs or Next.js dependency."
                }
            }

        # Run the build command
        cmd = build_command.split()

        try:
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Parse the build output
            build_results = _parse_nextjs_build_output(result.stdout, result.stderr)

            # Add additional checks if requested
            additional_results = {}

            if include_typescript_check:
                ts_result = _run_typescript_check(project_root)
                if ts_result:
                    additional_results["typescript"] = ts_result

            if include_lint_check:
                lint_result = _run_eslint_check(project_root)
                if lint_result:
                    additional_results["eslint"] = lint_result

            # Combine all results
            build_results.update({
                "command": " ".join(cmd),
                "exit_code": result.returncode,
                "success": result.returncode == 0,
                "project_root": project_root,
                "additional_checks": additional_results
            })

            return {"data": build_results}

        except subprocess.TimeoutExpired:
            return {
                "error": {
                    "code": "TIMEOUT",
                    "message": f"Next.js build timed out after {timeout} seconds"
                }
            }
        except subprocess.SubprocessError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to run Next.js build: {str(e)}"
                }
            }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to execute Next.js build: {str(e)}"
            }
        }


def _is_nextjs_project(project_path: Path) -> bool:
    """Check if the project is a Next.js project."""
    # Check for Next.js config files
    next_configs = [
        "next.config.js",
        "next.config.mjs",
        "next.config.ts"
    ]

    for config in next_configs:
        if (project_path / config).exists():
            return True

    # Check package.json for Next.js dependency
    package_json_path = project_path / "package.json"
    if package_json_path.exists():
        try:
            package_json = json.loads(package_json_path.read_text(encoding='utf-8'))
            dependencies = {
                **package_json.get("dependencies", {}),
                **package_json.get("devDependencies", {})
            }
            return "next" in dependencies
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    return False


def _parse_nextjs_build_output(stdout: str, stderr: str) -> dict[str, Any]:
    """Parse Next.js build output into structured data."""
    output = stdout + "\n" + stderr

    result = {
        "typescript_errors": [],
        "eslint_violations": [],
        "bundle_warnings": [],
        "build_errors": [],
        "performance_info": {},
        "summary": {
            "success": False,
            "total_errors": 0,
            "total_warnings": 0,
            "pages_count": 0,
            "static_pages": 0,
            "ssr_pages": 0
        }
    }

    # Parse TypeScript errors
    ts_error_pattern = re.compile(
        r'^(.+?)\((\d+),(\d+)\):\s+error\s+TS(\d+):\s+(.+)$',
        re.MULTILINE
    )

    for match in ts_error_pattern.finditer(output):
        file_path, line, column, code, message = match.groups()
        result["typescript_errors"].append({
            "file": file_path.replace("\\", "/"),
            "line": int(line),
            "column": int(column),
            "code": f"TS{code}",
            "message": message.strip(),
            "severity": "error"
        })

    # Parse ESLint violations
    eslint_pattern = re.compile(
        r'^(.+?):(\d+):(\d+):\s+(warning|error):\s+(.+?)\s+(.+)$',
        re.MULTILINE
    )

    for match in eslint_pattern.finditer(output):
        file_path, line, column, severity, message, rule = match.groups()
        result["eslint_violations"].append({
            "file": file_path.replace("\\", "/"),
            "line": int(line),
            "column": int(column),
            "severity": severity,
            "message": message.strip(),
            "rule": rule.strip()
        })

    # Parse bundle size warnings
    bundle_pattern = re.compile(
        r'(warn|warning).*?bundle.*?(\d+(?:\.\d+)?)\s*(kB|KB|MB)',
        re.IGNORECASE
    )

    for match in bundle_pattern.finditer(output):
        severity, size, unit = match.groups()
        result["bundle_warnings"].append({
            "type": "bundle_size",
            "size": f"{size}{unit}",
            "severity": "warning",
            "message": match.group(0).strip()
        })

    # Parse build errors (general)
    error_pattern = re.compile(
        r'(error|Error):\s*(.+)',
        re.IGNORECASE
    )

    for match in error_pattern.finditer(output):
        error_type, message = match.groups()
        # Skip TypeScript and ESLint errors already captured
        if not any(x in message.lower() for x in ["typescript", "eslint", "ts("]):
            result["build_errors"].append({
                "type": "build_error",
                "message": message.strip(),
                "severity": "error"
            })

    # Parse Next.js build summary
    if "✓ Production build completed" in output or "✓ Compiled successfully" in output:
        result["summary"]["success"] = True

    # Extract page information
    page_info_pattern = re.compile(
        r'Route\s+\(pages\)\s+Size\s+First Load JS.*?\n(.+?)(?=\n\n|\nRoute|\n├|\n└|$)',
        re.DOTALL
    )

    page_match = page_info_pattern.search(output)
    if page_match:
        page_section = page_match.group(1)

        # Count different page types
        static_count = len(re.findall(r'○', page_section))  # Static pages
        ssr_count = len(re.findall(r'●', page_section))     # SSR pages

        result["summary"]["static_pages"] = static_count
        result["summary"]["ssr_pages"] = ssr_count
        result["summary"]["pages_count"] = static_count + ssr_count

    # Extract performance information
    first_load_pattern = re.compile(r'First Load JS shared by all\s+(\d+(?:\.\d+)?)\s*(kB|KB)')
    first_load_match = first_load_pattern.search(output)
    if first_load_match:
        size, unit = first_load_match.groups()
        result["performance_info"]["shared_js_size"] = f"{size}{unit}"

    # Calculate totals
    result["summary"]["total_errors"] = (
        len(result["typescript_errors"]) +
        len([v for v in result["eslint_violations"] if v["severity"] == "error"]) +
        len(result["build_errors"])
    )

    result["summary"]["total_warnings"] = (
        len([v for v in result["eslint_violations"] if v["severity"] == "warning"]) +
        len(result["bundle_warnings"])
    )

    return result


def _run_typescript_check(project_root: str) -> dict[str, Any] | None:
    """Run TypeScript type checking separately."""
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )

        errors = []
        if result.stdout or result.stderr:
            output = result.stdout + "\n" + result.stderr

            # Parse TypeScript errors
            error_pattern = re.compile(
                r'^(.+?)\((\d+),(\d+)\):\s+error\s+TS(\d+):\s+(.+)$',
                re.MULTILINE
            )

            for match in error_pattern.finditer(output):
                file_path, line, column, code, message = match.groups()
                errors.append({
                    "file": file_path.replace("\\", "/"),
                    "line": int(line),
                    "column": int(column),
                    "code": f"TS{code}",
                    "message": message.strip()
                })

        return {
            "success": result.returncode == 0,
            "errors": errors,
            "error_count": len(errors)
        }

    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None


def _run_eslint_check(project_root: str) -> dict[str, Any] | None:
    """Run ESLint checking separately."""
    try:
        result = subprocess.run(
            ["npx", "eslint", ".", "--format", "json"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )

        violations = []
        if result.stdout:
            try:
                eslint_results = json.loads(result.stdout)

                for file_result in eslint_results:
                    file_path = file_result.get("filePath", "")
                    if file_path.startswith(project_root):
                        file_path = file_path[len(project_root):].lstrip("/")

                    for message in file_result.get("messages", []):
                        violations.append({
                            "file": file_path,
                            "line": message.get("line", 0),
                            "column": message.get("column", 0),
                            "severity": "error" if message.get("severity") == 2 else "warning",
                            "rule": message.get("ruleId", ""),
                            "message": message.get("message", "")
                        })

            except json.JSONDecodeError:
                pass

        return {
            "success": result.returncode == 0,
            "violations": violations,
            "error_count": len([v for v in violations if v["severity"] == "error"]),
            "warning_count": len([v for v in violations if v["severity"] == "warning"])
        }

    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None
