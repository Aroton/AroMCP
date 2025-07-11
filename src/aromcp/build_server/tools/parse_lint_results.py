"""Parse lint results tool implementation for Build Tools."""

import json
import os
import subprocess
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path
from ...utils.pagination import simplify_pagination


def parse_lint_results_impl(
    linter: str = "eslint",
    project_root: str | None = None,
    target_files: list[str] | None = None,
    config_file: str | None = None,
    include_warnings: bool = True,
    use_standards_eslint: bool = False,
    timeout: int = 120,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Run linters and return categorized issues.

    Args:
        linter: Linter to use ("eslint", "prettier", "stylelint")
        project_root: Directory to run linter in (defaults to MCP_FILE_ROOT)
        target_files: Specific files to lint (defaults to linter defaults)
        config_file: Path to linter config file
        include_warnings: Whether to include warnings
        use_standards_eslint: Whether to include generated ESLint rules from standards server
        timeout: Maximum execution time in seconds
        page: Page number for pagination (1-based, default: 1)
        max_tokens: Maximum tokens per page (default: 20000)

    Returns:
        Dictionary with paginated categorized lint issues
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

        # Build linter command based on type
        if linter == "eslint":
            result = _run_eslint(
                project_root, target_files, config_file, include_warnings,
                use_standards_eslint, timeout, page, max_tokens
            )
        elif linter == "prettier":
            result = _run_prettier(project_root, target_files, config_file, timeout, page, max_tokens)
        elif linter == "stylelint":
            result = _run_stylelint(
                project_root, target_files, config_file, include_warnings, timeout, page, max_tokens
            )
        else:
            return {
                "error": {
                    "code": "UNSUPPORTED",
                    "message": f"Unsupported linter: {linter}. Supported: eslint, prettier, stylelint"
                }
            }

        return result

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to parse lint results: {str(e)}"
            }
        }


def _run_eslint(
    project_root: str,
    target_files: list[str] | None,
    config_file: str | None,
    include_warnings: bool,
    use_standards_eslint: bool,
    timeout: int,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Run ESLint and parse results."""
    is_nextjs = _is_nextjs_project(project_root)

    # Step 1: Generate commands to run
    commands = []

    # Generate Next.js command if applicable
    if is_nextjs:
        nextjs_cmd = ["npm", "run", "lint", "--", "--format", "json"]
        if target_files:
            nextjs_cmd.extend(target_files if isinstance(target_files, list) else [target_files])
        commands.append(("nextjs", nextjs_cmd))

    # Generate ESLint command for standards (if requested) or regular ESLint
    if use_standards_eslint:
        standards_config = _get_standards_eslint_config(project_root)
        if standards_config:
            eslint_cmd = ["npx", "eslint", "--format", "json", "--config", standards_config, "--no-config-lookup"]
            if target_files:
                eslint_cmd.extend(target_files if isinstance(target_files, list) else [target_files])
            else:
                eslint_cmd.append("src")
            commands.append(("standards", eslint_cmd))
    elif not is_nextjs:
        # Regular ESLint for non-Next.js projects
        eslint_cmd = ["npx", "eslint", "--format", "json"]
        if config_file:
            eslint_cmd.extend(["--config", config_file])
        if target_files:
            eslint_cmd.extend(target_files if isinstance(target_files, list) else [target_files])
        else:
            eslint_cmd.extend(["src", "--ext", ".js,.jsx,.ts,.tsx"])
        commands.append(("eslint", eslint_cmd))

    # Step 2: Run all commands and collect issues
    all_issues = []
    command_names = []

    for cmd_name, cmd in commands:
        command_names.append(cmd_name)
        try:
            result = subprocess.run(  # noqa: S603
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # Handle configuration errors
            if result.returncode == 2 and result.stderr:
                return {
                    "error": {
                        "code": "OPERATION_FAILED",
                        "message": f"ESLint configuration error: {result.stderr}"
                    }
                }

            # Parse output
            issues = _parse_eslint_output(result, project_root, include_warnings, cmd_name)
            all_issues.extend(issues)

        except subprocess.TimeoutExpired:
            return {
                "error": {
                    "code": "TIMEOUT",
                    "message": f"ESLint timed out after {timeout} seconds"
                }
            }
        except subprocess.SubprocessError as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to run ESLint: {str(e)}"
                }
            }

    # Step 3: Process and return results
    categories = _categorize_lint_issues(all_issues)
    summary = {
        "total_errors": len([i for i in all_issues if i["severity"] == "error"]),
        "total_warnings": len([i for i in all_issues if i["severity"] == "warning"]),
        "total_issues": len(all_issues),
        "files_with_issues": len({i["file"] for i in all_issues}),
        "fixable_issues": len([i for i in all_issues if i["fixable"]]),
        "exit_code": 0 if not all_issues else 1
    }

    metadata = {
        "linter": "eslint",
        "summary": summary,
        "categories": categories,
        "command": (
            " + ".join(command_names) if len(command_names) > 1
            else " ".join(commands[0][1]) if commands
            else "none"
        )
    }

    # Apply simplified pagination with token-based sizing
    result = simplify_pagination(
        items=all_issues,
        page=page,
        max_tokens=max_tokens,
        sort_key=lambda x: (x.get("file", ""), x.get("line", 0), x.get("column", 0)),
        metadata=metadata
    )
    
    return {"data": result}


def _parse_eslint_output(
    result: subprocess.CompletedProcess,
    project_root: str,
    include_warnings: bool,
    source: str
) -> list[dict[str, Any]]:
    """Parse ESLint output and return list of issues."""
    issues = []

    if result.stdout:
        try:
            eslint_results = json.loads(result.stdout)

            for file_result in eslint_results:
                file_path = file_result.get("filePath", "")
                # Make path relative to project root
                if file_path.startswith(project_root):
                    file_path = file_path[len(project_root):].lstrip("/")

                for message in file_result.get("messages", []):
                    severity = "error" if message.get("severity") == 2 else "warning"

                    # Skip warnings if not requested
                    if severity == "warning" and not include_warnings:
                        continue

                    issues.append({
                        "file": file_path,
                        "line": message.get("line", 0),
                        "column": message.get("column", 0),
                        "severity": severity,
                        "rule": message.get("ruleId", ""),
                        "message": message.get("message", ""),
                        "fixable": message.get("fix") is not None,
                        "source": source
                    })
        except json.JSONDecodeError:
            # For Next.js, check if there's a success message with no errors
            if source == "nextjs" and result.stdout and "✔ No ESLint warnings or errors" in result.stdout:
                # Next.js outputs success message when no errors
                pass
            # Otherwise, silently ignore JSON parsing errors and return empty list

    return issues



def _run_prettier(
    project_root: str,
    target_files: list[str] | None,
    config_file: str | None,
    timeout: int,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Run Prettier and parse results."""
    cmd = ["npx", "prettier", "--check", "--list-different"]

    if config_file:
        cmd.extend(["--config", config_file])

    if target_files:
        cmd.extend(target_files)
    else:
        # Default Prettier patterns
        cmd.extend(["**/*.{js,jsx,ts,tsx,json,css,scss,md}"])

    try:
        result = subprocess.run(  # noqa: S603 # Safe: cmd built from predetermined Prettier commands
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        issues = []

        # Prettier lists files that need formatting
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    file_path = line.strip()
                    # Make path relative to project root
                    if file_path.startswith(project_root):
                        file_path = file_path[len(project_root):].lstrip("/")

                    issues.append({
                        "file": file_path,
                        "line": 0,
                        "column": 0,
                        "severity": "warning",
                        "rule": "formatting",
                        "message": "File is not formatted according to Prettier rules",
                        "fixable": True
                    })

        summary = {
            "total_errors": 0,
            "total_warnings": len(issues),
            "total_issues": len(issues),
            "files_with_issues": len(issues),
            "fixable_issues": len(issues),
            "exit_code": result.returncode
        }

        categories = {"formatting": {"count": len(issues), "fixable": len(issues)}}

        # Create metadata for pagination
        metadata = {
            "linter": "prettier",
            "summary": summary,
            "categories": categories,
            "command": " ".join(cmd)
        }

        # Apply simplified pagination with token-based sizing
        result = simplify_pagination(
            items=issues,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: x.get("file", ""),
            metadata=metadata
        )
        
        return {"data": result}

    except subprocess.TimeoutExpired:
        return {
            "error": {
                "code": "TIMEOUT",
                "message": f"Prettier timed out after {timeout} seconds"
            }
        }
    except subprocess.SubprocessError as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to run Prettier: {str(e)}"
            }
        }


def _run_stylelint(
    project_root: str,
    target_files: list[str] | None,
    config_file: str | None,
    include_warnings: bool,
    timeout: int,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Run Stylelint and parse results."""
    cmd = ["npx", "stylelint", "--formatter", "json"]

    if config_file:
        cmd.extend(["--config", config_file])

    if target_files:
        cmd.extend(target_files)
    else:
        # Default Stylelint patterns
        cmd.extend(["**/*.{css,scss,sass,less}"])

    try:
        result = subprocess.run(  # noqa: S603 # Safe: cmd built from predetermined Stylelint commands
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        issues = []

        if result.stdout:
            try:
                stylelint_results = json.loads(result.stdout)

                for file_result in stylelint_results:
                    file_path = file_result.get("source", "")
                    # Make path relative to project root
                    if file_path.startswith(project_root):
                        file_path = file_path[len(project_root):].lstrip("/")

                    for warning in file_result.get("warnings", []):
                        severity = warning.get("severity", "warning")

                        # Skip warnings if not requested
                        if severity == "warning" and not include_warnings:
                            continue

                        issues.append({
                            "file": file_path,
                            "line": warning.get("line", 0),
                            "column": warning.get("column", 0),
                            "severity": severity,
                            "rule": warning.get("rule", ""),
                            "message": warning.get("text", ""),
                            "fixable": False  # Stylelint doesn't provide fix info in JSON
                        })

            except json.JSONDecodeError:
                return {
                    "error": {
                        "code": "OPERATION_FAILED",
                        "message": f"Failed to parse Stylelint output: {result.stderr}"
                    }
                }

        # Categorize issues
        categories = _categorize_lint_issues(issues)

        # Generate summary
        summary = {
            "total_errors": len([i for i in issues if i["severity"] == "error"]),
            "total_warnings": len([i for i in issues if i["severity"] == "warning"]),
            "total_issues": len(issues),
            "files_with_issues": len({i["file"] for i in issues}),
            "fixable_issues": len([i for i in issues if i["fixable"]]),
            "exit_code": result.returncode
        }

        # Create metadata for pagination
        metadata = {
            "linter": "stylelint",
            "summary": summary,
            "categories": categories,
            "command": " ".join(cmd)
        }

        # Apply simplified pagination with token-based sizing
        result = simplify_pagination(
            items=issues,
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
                "message": f"Stylelint timed out after {timeout} seconds"
            }
        }
    except subprocess.SubprocessError as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to run Stylelint: {str(e)}"
            }
        }


def _is_nextjs_project(project_root: str) -> bool:
    """Check if the project is a Next.js project."""
    # Check for next.config.js or next.config.mjs
    next_config_files = ["next.config.js", "next.config.mjs", "next.config.ts"]
    for config_file in next_config_files:
        if os.path.exists(os.path.join(project_root, config_file)):
            return True

    # Check package.json for next dependency
    package_json_path = os.path.join(project_root, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, encoding="utf-8") as f:
                package_data = json.load(f)

            # Check dependencies and devDependencies for next
            dependencies = package_data.get("dependencies", {})
            dev_dependencies = package_data.get("devDependencies", {})

            if "next" in dependencies or "next" in dev_dependencies:
                return True

        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return False


def _get_standards_eslint_config(project_root: str) -> str | None:
    """Get the path to standards ESLint config if available."""
    standards_config_path = os.path.join(project_root, ".aromcp", "eslint", "standards-config.js")
    if os.path.exists(standards_config_path):
        # Check if the aromcp plugin file exists
        aromcp_plugin_path = os.path.join(project_root, ".aromcp", "eslint", "eslint-plugin-aromcp.js")
        if os.path.exists(aromcp_plugin_path):
            # For ESLint v9 flat configs, we need to use absolute path
            return os.path.abspath(standards_config_path)
        # If config exists but plugin doesn't, skip standards config
        return None
    return None




def _categorize_lint_issues(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """Categorize lint issues by rule type."""
    categories = {}

    for issue in issues:
        rule = issue.get("rule", "unknown")
        if not rule:
            rule = "unknown"

        if rule not in categories:
            categories[rule] = {
                "count": 0,
                "errors": 0,
                "warnings": 0,
                "fixable": 0,
                "files": set(),
                "sources": set()  # Track which linters found this rule
            }

        categories[rule]["count"] += 1
        categories[rule][issue["severity"] + "s"] += 1

        if issue.get("fixable", False):
            categories[rule]["fixable"] += 1

        if issue["file"]:
            categories[rule]["files"].add(issue["file"])

        # Track source if available
        if issue.get("source"):
            categories[rule]["sources"].add(issue["source"])

    # Convert sets to lists and sort by count
    for rule_data in categories.values():
        rule_data["files"] = list(rule_data["files"])
        rule_data["sources"] = list(rule_data["sources"])

    # Sort categories by count (most common first)
    return dict(
        sorted(
            categories.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
    )
