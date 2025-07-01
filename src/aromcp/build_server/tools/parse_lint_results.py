"""Parse lint results tool implementation for Build Tools."""

import json
import subprocess
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path


def parse_lint_results_impl(
    linter: str = "eslint",
    project_root: str | None = None,
    target_files: list[str] | None = None,
    config_file: str | None = None,
    include_warnings: bool = True,
    timeout: int = 120
) -> dict[str, Any]:
    """Run linters and return categorized issues.
    
    Args:
        linter: Linter to use ("eslint", "prettier", "stylelint")
        project_root: Directory to run linter in (defaults to MCP_FILE_ROOT)
        target_files: Specific files to lint (defaults to linter defaults)
        config_file: Path to linter config file
        include_warnings: Whether to include warnings
        timeout: Maximum execution time in seconds
        
    Returns:
        Dictionary with categorized lint issues
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
            
        # Build linter command based on type
        if linter == "eslint":
            result = _run_eslint(project_root, target_files, config_file, include_warnings, timeout)
        elif linter == "prettier":
            result = _run_prettier(project_root, target_files, config_file, timeout)
        elif linter == "stylelint":
            result = _run_stylelint(project_root, target_files, config_file, include_warnings, timeout)
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
    timeout: int
) -> dict[str, Any]:
    """Run ESLint and parse results."""
    cmd = ["npx", "eslint", "--format", "json"]
    
    if config_file:
        cmd.extend(["--config", config_file])
        
    if target_files:
        cmd.extend(target_files)
    else:
        # Default ESLint patterns
        cmd.extend([".", "--ext", ".js,.jsx,.ts,.tsx"])
        
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        # ESLint returns exit code 1 when issues are found, which is expected
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
                            "fixable": message.get("fix") is not None
                        })
                        
            except json.JSONDecodeError:
                # Fallback to stderr if JSON parsing fails
                return {
                    "error": {
                        "code": "OPERATION_FAILED",
                        "message": f"Failed to parse ESLint output: {result.stderr}"
                    }
                }
                
        # Categorize issues
        categories = _categorize_lint_issues(issues)
        
        # Generate summary
        summary = {
            "total_errors": len([i for i in issues if i["severity"] == "error"]),
            "total_warnings": len([i for i in issues if i["severity"] == "warning"]),
            "total_issues": len(issues),
            "files_with_issues": len(set(i["file"] for i in issues)),
            "fixable_issues": len([i for i in issues if i["fixable"]]),
            "exit_code": result.returncode
        }
        
        return {
            "data": {
                "linter": "eslint",
                "issues": issues,
                "summary": summary,
                "categories": categories,
                "command": " ".join(cmd)
            }
        }
        
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


def _run_prettier(
    project_root: str,
    target_files: list[str] | None,
    config_file: str | None,
    timeout: int
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
        result = subprocess.run(
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
        
        return {
            "data": {
                "linter": "prettier",
                "issues": issues,
                "summary": summary,
                "categories": categories,
                "command": " ".join(cmd)
            }
        }
        
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
    timeout: int
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
        result = subprocess.run(
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
            "files_with_issues": len(set(i["file"] for i in issues)),
            "fixable_issues": len([i for i in issues if i["fixable"]]),
            "exit_code": result.returncode
        }
        
        return {
            "data": {
                "linter": "stylelint",
                "issues": issues,
                "summary": summary,
                "categories": categories,
                "command": " ".join(cmd)
            }
        }
        
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
                "files": set()
            }
            
        categories[rule]["count"] += 1
        categories[rule][issue["severity"] + "s"] += 1
        
        if issue.get("fixable", False):
            categories[rule]["fixable"] += 1
            
        if issue["file"]:
            categories[rule]["files"].add(issue["file"])
            
    # Convert sets to lists and sort by count
    for rule_data in categories.values():
        rule_data["files"] = list(rule_data["files"])
        
    # Sort categories by count (most common first)
    return dict(
        sorted(
            categories.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
    )