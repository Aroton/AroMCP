"""Lint project tool implementation."""

import json
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root


def lint_project_impl(use_standards: bool = True, target_files: str | list[str] | None = None) -> dict[str, Any]:
    """Run ESLint to find code style issues and bugs.

    Args:
        use_standards: Whether to use standards server generated ESLint config
        target_files: Specific files to lint (optional)

    Returns:
        Dictionary with issues and fixable count
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)
        project_path = Path(project_root)

        # Handle string input for target_files
        if isinstance(target_files, str):
            target_files = [target_files]

        # Auto-glob directories: if a path is a directory, append /* to glob all files in it
        if target_files:
            expanded_files = []
            for file_path in target_files:
                full_path = project_path / file_path
                if full_path.is_dir():
                    # If it's a directory, append /* to glob all files in it
                    expanded_files.append(f"{file_path}/*")
                else:
                    expanded_files.append(file_path)
            target_files = expanded_files

        is_nextjs = _is_nextjs_project(project_root)
        all_issues = []
        commands_run = []

        # Try Next.js lint command first if it's a Next.js project
        if is_nextjs and not use_standards:
            try:
                nextjs_cmd = ["npm", "run", "lint", "--", "--format", "json"]
                if target_files:
                    nextjs_cmd.extend(target_files)

                result = subprocess.run(  # noqa: S603 # Intentional subprocess call for Next.js lint
                    nextjs_cmd,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                issues = _parse_eslint_output_enhanced(result, project_root, "nextjs")
                all_issues.extend(issues)
                commands_run.append("nextjs")

            except Exception:  # noqa: S110 # Intentional fallback on Next.js failure
                # Fall through to regular ESLint if Next.js lint fails
                pass

        # Try standards config if requested
        if use_standards:
            standards_config = _get_standards_eslint_config(project_root)
            if standards_config:
                try:
                    eslint_cmd = [
                        "npx", "eslint", "--format", "json",
                        "--config", standards_config, "--no-config-lookup"
                    ]
                    if target_files:
                        eslint_cmd.extend(target_files)
                    else:
                        eslint_cmd.append("src")

                    result = subprocess.run(  # noqa: S603 # Intentional subprocess call for standards ESLint
                        eslint_cmd,
                        cwd=project_root,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )

                    issues = _parse_eslint_output_enhanced(result, project_root, "standards")
                    all_issues.extend(issues)
                    commands_run.append("standards")

                except Exception:  # noqa: S110 # Intentional fallback on standards failure
                    # Fall through to regular ESLint if standards fails
                    pass

        # Fall back to regular ESLint if no other method worked or if not Next.js
        if not all_issues:
            # Check if regular ESLint config is available
            config_files = [".eslintrc.js", ".eslintrc.json", "eslint.config.js"]
            if not any((project_path / config_file).exists() for config_file in config_files):
                # Try to find package.json with eslint config
                package_json = project_path / "package.json"
                if package_json.exists():
                    try:
                        config = json.loads(package_json.read_text())
                        if "eslintConfig" not in config:
                            raise ValueError("No ESLint configuration found")
                    except (json.JSONDecodeError, KeyError) as e:
                        raise ValueError("No ESLint configuration found") from e
                else:
                    raise ValueError("No ESLint configuration found")

            # Run regular ESLint
            try:
                eslint_cmd = ["npx", "eslint", "--format", "json"]
                if target_files:
                    eslint_cmd.extend(target_files)
                else:
                    eslint_cmd.extend(["src", "--ext", ".js,.jsx,.ts,.tsx"])

                result = subprocess.run(  # noqa: S603 # Intentional subprocess call for regular ESLint
                    eslint_cmd,
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                issues = _parse_eslint_output_enhanced(result, project_root, "eslint")
                all_issues.extend(issues)
                commands_run.append("eslint")

            except subprocess.TimeoutExpired as e:
                raise ValueError("ESLint timed out") from e
            except FileNotFoundError as e:
                raise ValueError("ESLint not found (npx eslint)") from e

        # Calculate summary
        total_issues = len(all_issues)
        fixable_count = len([i for i in all_issues if i.get("fixable", False)])

        # Cap issues to first file only (like check_typescript)
        first_file_issues = []
        if all_issues:
            first_file = all_issues[0]["file"]
            first_file_issues = [issue for issue in all_issues if issue["file"] == first_file]

        # Build result - always show issues array, add total if there are issues
        if total_issues == 0:
            return {
                "issues": [],
                "check_again": False
            }
        else:
            result = {
                "issues": first_file_issues,
                "total": total_issues,
                "check_again": fixable_count > 0  # Suggest checking again if issues are fixable
            }
            
            # Only include fixable count if > 0
            if fixable_count > 0:
                result["fixable"] = fixable_count
                
            return result

    except Exception as e:
        raise ValueError(f"Lint failed: {str(e)}") from e


def _is_nextjs_project(project_root: str) -> bool:
    """Check if the project is a Next.js project."""
    project_path = Path(project_root)

    # Check for Next.js specific files/directories
    if (project_path / "next.config.js").exists() or (project_path / "next.config.ts").exists():
        return True

    # Check package.json for Next.js dependency
    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            config = json.loads(package_json.read_text())
            deps = {**config.get("dependencies", {}), **config.get("devDependencies", {})}
            return "next" in deps
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    return False


def _get_standards_eslint_config(project_root: str) -> str | None:
    """Get path to standards-generated ESLint config if it exists."""
    aromcp_dir = Path(project_root) / ".aromcp"
    eslint_config = aromcp_dir / "eslint" / "standards-config.js"

    if eslint_config.exists():
        return str(eslint_config)
    return None


def _parse_eslint_output_enhanced(
    result: subprocess.CompletedProcess,
    project_root: str,
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
            # Otherwise, silently ignore JSON parsing errors and return empty list
            pass

    return issues


