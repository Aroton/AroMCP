"""Lint project tool implementation."""

import json
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root
from ...utils.pagination import auto_paginate_cursor_response
from ..models.build_models import LintIssue, LintProjectResponse


def lint_project_impl(
    use_standards: bool = True,
    target_files: str | list[str] | None = None,
    debug: bool = False,
    cursor: str | None = None,
    max_tokens: int = 20000,
) -> LintProjectResponse:
    """Run ESLint to find code style issues and bugs.

    Args:
        use_standards: Whether to use standards server generated ESLint config
        target_files: Specific files to lint (optional)
        debug: Enable detailed debug output for troubleshooting
        cursor: Cursor for pagination (None for first page)
        max_tokens: Maximum tokens per response

    Returns:
        LintProjectResponse with issues and pagination info
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)
        project_path = Path(project_root)

        debug_info = []
        if debug:
            debug_info.append(f"🔍 DEBUG: Project root: {project_root}")
            debug_info.append(f"🔍 DEBUG: Target files: {target_files}")
            debug_info.append(f"🔍 DEBUG: Use standards: {use_standards}")

            # Check what npm run build actually does
            package_json = project_path / "package.json"
            if package_json.exists():
                try:
                    config = json.loads(package_json.read_text())
                    scripts = config.get("scripts", {})
                    build_script = scripts.get("build", "Not found")
                    lint_script = scripts.get("lint", "Not found")
                    debug_info.append(f"🔍 DEBUG: npm run build script: {build_script}")
                    debug_info.append(f"🔍 DEBUG: npm run lint script: {lint_script}")

                    # Special note about build vs lint
                    if "test" in build_script.lower():
                        debug_info.append(
                            "🔍 DEBUG: ⚠️  npm run build includes tests - errors might be from tests, not linting!"
                        )
                    if build_script != lint_script:
                        debug_info.append(
                            f"🔍 DEBUG: ⚠️  npm run build ({build_script}) differs from npm run lint ({lint_script})"
                        )
                except (json.JSONDecodeError, KeyError) as e:
                    debug_info.append(f"🔍 DEBUG: package.json read error: {str(e)}")
            else:
                debug_info.append("🔍 DEBUG: No package.json found")

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

        if debug:
            debug_info.append(f"🔍 DEBUG: Is Next.js project: {is_nextjs}")

        # Try Next.js lint command first if it's a Next.js project
        # Always try Next.js lint for Next.js projects since it handles config better
        if is_nextjs:
            try:
                nextjs_cmd = ["npm", "run", "lint", "--", "--format", "json"]
                if target_files:
                    nextjs_cmd.extend(target_files)

                if debug:
                    debug_info.append(f"🔍 DEBUG: Running Next.js command: {' '.join(nextjs_cmd)}")

                result = subprocess.run(  # noqa: S603 # Intentional subprocess call for Next.js lint
                    nextjs_cmd, cwd=project_root, capture_output=True, text=True, timeout=120
                )

                if debug:
                    debug_info.append(f"🔍 DEBUG: Next.js exit code: {result.returncode}")
                    debug_info.append(f"🔍 DEBUG: Next.js stdout length: {len(result.stdout)} chars")
                    debug_info.append(f"🔍 DEBUG: Next.js stderr: {result.stderr[:500]}...")
                    if result.stdout:
                        debug_info.append(f"🔍 DEBUG: Next.js stdout preview: {result.stdout[:500]}...")

                issues = _parse_eslint_output_enhanced(result, project_root, "nextjs", debug, debug_info)
                all_issues.extend(issues)
                commands_run.append("nextjs")

                if debug:
                    debug_info.append(f"🔍 DEBUG: Next.js found {len(issues)} issues")

            except Exception as e:  # noqa: S110 # Intentional fallback on Next.js failure
                if debug:
                    debug_info.append(f"🔍 DEBUG: Next.js lint failed: {str(e)}")
                # Fall through to regular ESLint if Next.js lint fails
                pass

        # Try standards config if requested and Next.js didn't work
        if use_standards and not all_issues:
            standards_config = _get_standards_eslint_config(project_root)
            if debug:
                debug_info.append(f"🔍 DEBUG: Standards config path: {standards_config}")

            if standards_config:
                try:
                    eslint_cmd = [
                        "npx",
                        "eslint",
                        "--format",
                        "json",
                        "--config",
                        standards_config,
                        "--no-config-lookup",
                    ]
                    if target_files:
                        eslint_cmd.extend(target_files)
                    else:
                        eslint_cmd.append("src")

                    if debug:
                        debug_info.append(f"🔍 DEBUG: Running standards command: {' '.join(eslint_cmd)}")

                    result = subprocess.run(  # noqa: S603 # Intentional subprocess call for standards ESLint
                        eslint_cmd, cwd=project_root, capture_output=True, text=True, timeout=120
                    )

                    if debug:
                        debug_info.append(f"🔍 DEBUG: Standards exit code: {result.returncode}")
                        debug_info.append(f"🔍 DEBUG: Standards stdout length: {len(result.stdout)} chars")
                        debug_info.append(f"🔍 DEBUG: Standards stderr: {result.stderr[:500]}...")

                    issues = _parse_eslint_output_enhanced(result, project_root, "standards", debug, debug_info)
                    all_issues.extend(issues)
                    commands_run.append("standards")

                    if debug:
                        debug_info.append(f"🔍 DEBUG: Standards found {len(issues)} issues")

                except Exception as e:  # noqa: S110 # Intentional fallback on standards failure
                    if debug:
                        debug_info.append(f"🔍 DEBUG: Standards lint failed: {str(e)}")
                    # If the standards config has syntax errors, we should skip it entirely
                    if "Syntax error in selector" in str(result.stderr):
                        if debug:
                            debug_info.append(
                                "🔍 DEBUG: Standards config has selector syntax errors, skipping standards"
                            )
                    # Fall through to regular ESLint if standards fails
                    pass

        # Fall back to regular ESLint if no other method worked or if not Next.js
        if not all_issues:
            if debug:
                debug_info.append("🔍 DEBUG: Falling back to regular ESLint")

            # Check if regular ESLint config is available
            config_files = [".eslintrc.js", ".eslintrc.json", "eslint.config.js"]
            available_configs = [config for config in config_files if (project_path / config).exists()]

            if debug:
                debug_info.append(f"🔍 DEBUG: Available config files: {available_configs}")

            if not available_configs:
                # Try to find package.json with eslint config
                package_json = project_path / "package.json"
                if package_json.exists():
                    try:
                        config = json.loads(package_json.read_text())
                        has_eslint_config = "eslintConfig" in config
                        if debug:
                            debug_info.append(f"🔍 DEBUG: package.json has eslintConfig: {has_eslint_config}")
                        if not has_eslint_config:
                            raise ValueError("No ESLint configuration found")
                    except (json.JSONDecodeError, KeyError) as e:
                        if debug:
                            debug_info.append(f"🔍 DEBUG: package.json error: {str(e)}")
                        raise ValueError("No ESLint configuration found") from e
                else:
                    if debug:
                        debug_info.append("🔍 DEBUG: No package.json found")
                    raise ValueError("No ESLint configuration found")

            # Run regular ESLint
            try:
                eslint_cmd = ["npx", "eslint", "--format", "json"]
                if target_files:
                    eslint_cmd.extend(target_files)
                else:
                    eslint_cmd.extend(["src", "--ext", ".js,.jsx,.ts,.tsx"])

                if debug:
                    debug_info.append(f"🔍 DEBUG: Running regular ESLint command: {' '.join(eslint_cmd)}")

                result = subprocess.run(  # noqa: S603 # Intentional subprocess call for regular ESLint
                    eslint_cmd, cwd=project_root, capture_output=True, text=True, timeout=120
                )

                if debug:
                    debug_info.append(f"🔍 DEBUG: Regular ESLint exit code: {result.returncode}")
                    debug_info.append(f"🔍 DEBUG: Regular ESLint stdout length: {len(result.stdout)} chars")
                    debug_info.append(f"🔍 DEBUG: Regular ESLint stderr: {result.stderr[:500]}...")

                issues = _parse_eslint_output_enhanced(result, project_root, "eslint", debug, debug_info)
                all_issues.extend(issues)
                commands_run.append("eslint")

                if debug:
                    debug_info.append(f"🔍 DEBUG: Regular ESLint found {len(issues)} issues")

            except subprocess.TimeoutExpired as e:
                if debug:
                    debug_info.append(f"🔍 DEBUG: ESLint timed out: {str(e)}")
                raise ValueError("ESLint timed out") from e
            except FileNotFoundError as e:
                if debug:
                    debug_info.append(f"🔍 DEBUG: ESLint not found: {str(e)}")
                raise ValueError("ESLint not found (npx eslint)") from e

        # Calculate summary
        total_issues = len(all_issues)
        fixable_count = len([i for i in all_issues if i.get("fixable", False)])

        if debug:
            debug_info.append(f"🔍 DEBUG: Total issues found: {total_issues}")
            debug_info.append(f"🔍 DEBUG: Fixable issues: {fixable_count}")
            debug_info.append(f"🔍 DEBUG: Commands run: {commands_run}")

        # Estimate files checked first (before converting to dataclasses)
        files_checked = len({issue["file"] for issue in all_issues}) if all_issues else 1

        # Return all issues from all files
        issues_to_convert = all_issues

        if debug:
            debug_info.append(f"🔍 DEBUG: Converting all {len(issues_to_convert)} issues")

        # Convert issues to LintIssue dataclasses
        lint_issues = []
        for issue in issues_to_convert:
            lint_issues.append(
                LintIssue(
                    file=issue["file"],
                    line=issue["line"],
                    column=issue["column"],
                    rule=issue["rule"],
                    message=issue["message"],
                    severity=issue["severity"],
                    fixable=issue["fixable"],
                )
            )

        # Build the response using the dataclass
        response = LintProjectResponse(
            issues=lint_issues,
            total_issues=total_issues,
            fixable_issues=fixable_count,
            files_checked=files_checked,
            check_again=fixable_count > 0,  # Suggest checking again if issues are fixable
            success=total_issues == 0,
        )

        # Apply auto-pagination with proper sort key
        paginated_response = auto_paginate_cursor_response(
            response=response,
            items_field="issues",
            cursor=cursor,
            max_tokens=max_tokens,
            sort_key=lambda x: (
                x.file if hasattr(x, "file") else x["file"],
                x.line if hasattr(x, "line") else x["line"],
            ),  # Handle both dict and dataclass
        )

        # Add debug info if requested
        if debug:
            if isinstance(paginated_response, dict):
                paginated_response["debug_info"] = debug_info
            elif hasattr(paginated_response, "__dict__"):
                # If it's still a dataclass, convert to dict to add debug info
                from dataclasses import asdict

                result_dict = asdict(paginated_response)
                result_dict["debug_info"] = debug_info
                return result_dict

        return paginated_response

    except Exception as e:
        if debug:
            # Return error response with debug info
            error_response = LintProjectResponse(
                issues=[],
                total_issues=0,
                fixable_issues=0,
                files_checked=0,
                check_again=False,
                success=False,
            )
            # Convert to dict and add error info
            from dataclasses import asdict

            result_dict = asdict(error_response)
            result_dict["error"] = {"code": "LINT_FAILED", "message": str(e)}
            result_dict["debug_info"] = debug_info
            return result_dict
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
    source: str,
    debug: bool = False,
    debug_info: list | None = None,
) -> list[dict[str, Any]]:
    """Parse ESLint output and return list of issues."""
    issues = []

    if debug and debug_info is not None:
        debug_info.append(f"🔍 DEBUG: Parsing {source} output...")
        debug_info.append(f"🔍 DEBUG: Has stdout: {bool(result.stdout)}")
        debug_info.append(f"🔍 DEBUG: Has stderr: {bool(result.stderr)}")
        if result.stdout:
            debug_info.append(f"🔍 DEBUG: Stdout first 200 chars: {result.stdout[:200]}...")
        if result.stderr:
            debug_info.append(f"🔍 DEBUG: Stderr first 200 chars: {result.stderr[:200]}...")

    # Try to parse JSON from stdout first, then stderr (Next.js sometimes puts JSON in stderr)
    json_output = None
    json_source = None

    if result.stdout:
        try:
            json_output = json.loads(result.stdout)
            json_source = "stdout"
            if debug and debug_info is not None:
                debug_info.append(f"🔍 DEBUG: JSON parsed successfully from stdout, {len(json_output)} file results")
        except json.JSONDecodeError:
            if debug and debug_info is not None:
                debug_info.append("🔍 DEBUG: Stdout is not valid JSON, trying stderr...")

    # If stdout parsing failed, try stderr (common with Next.js lint errors)
    if json_output is None and result.stderr:
        try:
            # Extract JSON from stderr - sometimes it's mixed with other output
            stderr_lines = result.stderr.strip().split("\n")
            for line in stderr_lines:
                line = line.strip()
                if line.startswith("[") and line.endswith("]"):
                    json_output = json.loads(line)
                    json_source = "stderr"
                    if debug and debug_info is not None:
                        debug_info.append(
                            f"🔍 DEBUG: JSON parsed successfully from stderr line, {len(json_output)} file results"
                        )
                    break
        except json.JSONDecodeError:
            if debug and debug_info is not None:
                debug_info.append("🔍 DEBUG: Stderr also not valid JSON")

    if json_output:
        if debug and debug_info is not None:
            debug_info.append(f"🔍 DEBUG: Processing JSON from {json_source}")

        for file_result in json_output:
            file_path = file_result.get("filePath", "")
            # Make path relative to project root
            if file_path.startswith(project_root):
                file_path = file_path[len(project_root) :].lstrip("/")

            messages = file_result.get("messages", [])
            if debug and debug_info is not None and messages:
                debug_info.append(f"🔍 DEBUG: File {file_path} has {len(messages)} messages")

            for message in messages:
                severity = "error" if message.get("severity") == 2 else "warning"

                issues.append(
                    {
                        "file": file_path,
                        "line": message.get("line", 0),
                        "column": message.get("column", 0),
                        "severity": severity,
                        "rule": message.get("ruleId", ""),
                        "message": message.get("message", ""),
                        "fixable": message.get("fix") is not None,
                        "source": source,
                    }
                )
    else:
        if debug and debug_info is not None:
            debug_info.append("🔍 DEBUG: No valid JSON found in stdout or stderr")
            if result.stdout:
                debug_info.append(f"🔍 DEBUG: Raw stdout: {result.stdout[:500]}...")
            if result.stderr:
                debug_info.append(f"🔍 DEBUG: Raw stderr: {result.stderr[:500]}...")

    if debug and debug_info is not None:
        debug_info.append(f"🔍 DEBUG: Parsed {len(issues)} total issues from {source}")

    return issues
