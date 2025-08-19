"""
Find unused code using Knip CLI integration.

Wraps the Knip tool to detect unused files, exports, and dependencies in TypeScript/JavaScript projects.
Handles Knip installation detection and provides structured responses.
"""

import json
import os
import subprocess
import time
from pathlib import Path

from ...filesystem_server._security import get_project_root
from ...utils.pagination import simplify_cursor_pagination
from ..models.typescript_models import (
    AnalysisError,
    FindUnusedCodeResponse,
    KnipConfiguration,
    KnipExecutionStats,
    UnusedCodeInfo,
)


def find_unused_code_impl(
    include_patterns: str | list[str] | None = None,
    exclude_patterns: str | list[str] | None = None,
    config_file: str | None = None,
    include_entry_files: bool = True,
    include_dependencies: bool = True,
    include_dev_dependencies: bool = False,
    workspace: str | None = None,
    page: int = 1,
    max_tokens: int = 20000,
) -> FindUnusedCodeResponse:
    """
    Find unused code using Knip CLI integration.

    Args:
        include_patterns: File patterns to include in analysis
        exclude_patterns: File patterns to exclude from analysis
        config_file: Path to Knip configuration file
        include_entry_files: Include entry point files in analysis
        include_dependencies: Include dependency analysis
        include_dev_dependencies: Include dev dependencies in analysis
        workspace: Workspace directory for monorepos
        framework: Framework preset to use (react, next, vue, etc.)
        page: Page number for pagination
        max_tokens: Maximum tokens per page

    Returns:
        FindUnusedCodeResponse with unused code information
    """
    start_time = time.time()
    project_root = get_project_root(None)
    errors = []

    # Detect Knip installation first (outside try-catch to avoid generic error)
    knip_command, installation_method = _detect_knip_installation(project_root)
    if not knip_command:
        return _create_error_response(
            "KNIP_NOT_FOUND",
            "Knip is not installed. Please install Knip first:\n\n"
            "• For global installation: npm install -g knip\n"
            "• For project installation: npm install --save-dev knip\n"
            "• For one-time use: npx knip\n\n"
            "Then try running the unused code detection again.",
            start_time,
        )

    try:

        # Get Knip version
        knip_version = _get_knip_version(knip_command)

        # Build Knip command
        command = _build_knip_command(
            knip_command,
            include_patterns,
            exclude_patterns,
            config_file,
            include_entry_files,
            include_dependencies,
            include_dev_dependencies,
            workspace,
            project_root,
        )

        # Execute Knip
        result = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        execution_time_ms = (time.time() - start_time) * 1000

        # Parse Knip output
        unused_items, knip_config, parse_errors = _parse_knip_output(
            result.stdout, result.stderr, result.returncode, project_root
        )
        errors.extend(parse_errors)

        # Create execution stats
        execution_stats = KnipExecutionStats(
            knip_version=knip_version,
            execution_time_ms=execution_time_ms,
            files_analyzed=_count_analyzed_files(result.stdout, project_root),
            total_issues=len(unused_items),
            exit_code=result.returncode,
            command_used=command,
            installation_method=installation_method,
        )

        # Apply pagination
        paginated_result = simplify_cursor_pagination(
            items=unused_items,
            cursor=None,  # For now, we'll use page 1 (cursor-based pagination will be enhanced later)
            max_tokens=max_tokens,
            sort_key=lambda x: (x.issue_type, x.file_path, x.symbol_name or ""),
            metadata={
                "total_issues": len(unused_items),
                "execution_stats": execution_stats,
                "knip_configuration": knip_config,
            },
        )
        
        return FindUnusedCodeResponse(
            unused_items=paginated_result["items"],
            total_issues=len(unused_items),
            knip_configuration=knip_config,
            execution_stats=execution_stats,
            errors=errors,
            success=len(errors) == 0,
            # Handle missing pagination fields with safe defaults
            total=paginated_result.get("total", len(unused_items)),
            page_size=paginated_result.get("page_size"),
            next_cursor=paginated_result.get("next_cursor"),
            has_more=paginated_result.get("has_more", False),
        )

    except subprocess.TimeoutExpired:
        return _create_error_response(
            "TIMEOUT", "Knip analysis timed out after 5 minutes", start_time
        )
    except subprocess.SubprocessError as e:
        return _create_error_response(
            "EXECUTION_ERROR", f"Failed to execute Knip: {str(e)}", start_time
        )
    except Exception as e:
        return _create_error_response(
            "UNEXPECTED_ERROR", f"Unexpected error during analysis: {str(e)}", start_time
        )


def _detect_knip_installation(project_root: str) -> tuple[list[str] | None, str]:
    """
    Detect Knip installation method and return command.

    Returns:
        Tuple of (command_list, installation_method) or (None, "") if not found
    """
    # Try local installation first
    local_knip = Path(project_root) / "node_modules" / ".bin" / "knip"
    if local_knip.exists():
        return ([str(local_knip)], "local")

    # Try npx (most common for CI/CD)
    try:
        result = subprocess.run(
            ["npx", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return (["npx", "knip"], "npx")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Try global installation
    try:
        result = subprocess.run(
            ["knip", "--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return (["knip"], "global")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return (None, "")


def _get_knip_version(knip_command: list[str]) -> str:
    """Get Knip version string."""
    try:
        result = subprocess.run(
            knip_command + ["--version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown"


def _build_knip_command(
    knip_command: list[str],
    include_patterns: str | list[str] | None,
    exclude_patterns: str | list[str] | None,
    config_file: str | None,
    include_entry_files: bool,
    include_dependencies: bool,
    include_dev_dependencies: bool,
    workspace: str | None,
    project_root: str,
) -> list[str]:
    """Build the complete Knip command with all options."""
    command = knip_command.copy()

    # Add JSON output flag for structured parsing
    command.append("--reporter=json")

    # Add config file if specified
    if config_file:
        config_path = Path(project_root) / config_file
        if config_path.exists():
            command.extend(["--config", str(config_path)])

    # Add workspace for monorepos
    if workspace:
        command.extend(["--workspace", workspace])

    # Framework detection is handled automatically by Knip
    # through package.json and project structure - no CLI flags needed

    # Handle include patterns
    if include_patterns:
        patterns = include_patterns if isinstance(include_patterns, list) else [include_patterns]
        for pattern in patterns:
            command.extend(["--include", pattern])

    # Handle exclude patterns  
    if exclude_patterns:
        patterns = exclude_patterns if isinstance(exclude_patterns, list) else [exclude_patterns]
        for pattern in patterns:
            command.extend(["--exclude", pattern])

    # Entry files option
    if not include_entry_files:
        command.append("--no-entry")

    # Dependencies options
    if not include_dependencies:
        command.append("--no-dependencies")

    if include_dev_dependencies:
        command.append("--include-dev-dependencies")

    return command


def _parse_knip_output(
    stdout: str, stderr: str, exit_code: int, project_root: str
) -> tuple[list[UnusedCodeInfo], KnipConfiguration, list[AnalysisError]]:
    """
    Parse Knip JSON output into structured unused code information.

    Returns:
        Tuple of (unused_items, knip_config, errors)
    """
    unused_items = []
    errors = []
    knip_config = KnipConfiguration()

    # Handle non-zero exit codes
    if exit_code != 0 and exit_code != 1:  # Exit code 1 is normal when unused code is found
        if stderr:
            errors.append(
                AnalysisError(
                    code="KNIP_ERROR",
                    message=f"Knip execution failed: {stderr}",
                )
            )
        return unused_items, knip_config, errors

    # Try to parse JSON output
    try:
        if stdout.strip():
            # Knip outputs NDJSON (newline-delimited JSON) or single JSON object
            output_lines = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
            
            for line in output_lines:
                if line.startswith('{'):
                    try:
                        data = json.loads(line)
                        items, config_info = _process_knip_json_entry(data, project_root)
                        unused_items.extend(items)
                        
                        # Update config information from first valid entry
                        if config_info and not knip_config.entry_points:
                            knip_config = config_info
                            
                    except json.JSONDecodeError:
                        continue

    except Exception as e:
        errors.append(
            AnalysisError(
                code="PARSE_ERROR",
                message=f"Failed to parse Knip output: {str(e)}",
            )
        )

    # Fallback to text parsing if JSON parsing fails
    if not unused_items and stdout.strip():
        unused_items, config_info = _parse_knip_text_output(stdout, project_root)
        if config_info:
            knip_config = config_info

    return unused_items, knip_config, errors


def _process_knip_json_entry(
    data: dict, project_root: str
) -> tuple[list[UnusedCodeInfo], KnipConfiguration | None]:
    """Process a single JSON entry from Knip output."""
    unused_items = []
    config_info = None

    # Handle different Knip output formats
    if "files" in data:
        # Unused files
        for file_info in data["files"]:
            file_path = str(Path(project_root) / file_info) if isinstance(file_info, str) else file_info.get("path", "")
            unused_items.append(
                UnusedCodeInfo(
                    file_path=file_path,
                    unused_files=[file_path],
                    issue_type="file",
                    severity="warning",
                    reason="File is not imported or used",
                )
            )

    if "exports" in data:
        # Unused exports
        for export_info in data["exports"]:
            if isinstance(export_info, dict):
                file_path = str(Path(project_root) / export_info.get("file", ""))
                symbol_name = export_info.get("symbol", "")
                unused_items.append(
                    UnusedCodeInfo(
                        file_path=file_path,
                        unused_exports=[symbol_name],
                        issue_type="export",
                        severity="warning",
                        symbol_name=symbol_name,
                        line_number=export_info.get("line"),
                        column_number=export_info.get("column"),
                        reason="Export is not used anywhere",
                    )
                )

    if "dependencies" in data:
        # Unused dependencies
        for dep_name in data["dependencies"]:
            package_json_path = str(Path(project_root) / "package.json")
            unused_items.append(
                UnusedCodeInfo(
                    file_path=package_json_path,
                    unused_dependencies=[dep_name],
                    issue_type="dependency",
                    severity="info",
                    symbol_name=dep_name,
                    reason="Dependency is not imported or used",
                )
            )

    # Extract configuration information
    if "config" in data:
        config_data = data["config"]
        config_info = KnipConfiguration(
            entry_points=config_data.get("entry", []),
            include_patterns=config_data.get("include", []),
            exclude_patterns=config_data.get("ignore", []),
            frameworks=config_data.get("frameworks", []),
        )

    return unused_items, config_info


def _parse_knip_text_output(stdout: str, project_root: str) -> tuple[list[UnusedCodeInfo], KnipConfiguration | None]:
    """Parse Knip text output as fallback when JSON parsing fails."""
    unused_items = []
    
    lines = stdout.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Detect sections
        if "Unused files" in line:
            current_section = "files"
            continue
        elif "Unused exports" in line:
            current_section = "exports"
            continue
        elif "Unused dependencies" in line:
            current_section = "dependencies"
            continue
            
        # Parse file paths and symbols
        if current_section == "files" and line.startswith("-"):
            file_path = line.lstrip("- ").strip()
            unused_items.append(
                UnusedCodeInfo(
                    file_path=str(Path(project_root) / file_path),
                    unused_files=[file_path],
                    issue_type="file",
                    severity="warning",
                    reason="File is not imported or used",
                )
            )
        elif current_section == "exports" and line.startswith("-"):
            # Format: "- symbol in path/to/file.ts"
            parts = line.lstrip("- ").split(" in ")
            if len(parts) == 2:
                symbol_name, file_path = parts
                unused_items.append(
                    UnusedCodeInfo(
                        file_path=str(Path(project_root) / file_path),
                        unused_exports=[symbol_name],
                        issue_type="export",
                        severity="warning",
                        symbol_name=symbol_name,
                        reason="Export is not used anywhere",
                    )
                )
        elif current_section == "dependencies" and line.startswith("-"):
            dep_name = line.lstrip("- ").strip()
            unused_items.append(
                UnusedCodeInfo(
                    file_path=str(Path(project_root) / "package.json"),
                    unused_dependencies=[dep_name],
                    issue_type="dependency",
                    severity="info",
                    symbol_name=dep_name,
                    reason="Dependency is not imported or used",
                )
            )
    
    return unused_items, None


def _count_analyzed_files(stdout: str, project_root: str) -> int:
    """Estimate number of files analyzed from Knip output."""
    # Try to extract file count from output
    try:
        # Count TypeScript/JavaScript files in project as estimate
        project_path = Path(project_root)
        file_count = 0
        patterns = ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"]
        exclude_dirs = {"node_modules", ".git", "dist", "build", ".next", "coverage"}
        
        for pattern in patterns:
            for file_path in project_path.glob(pattern):
                if not any(excluded in file_path.parts for excluded in exclude_dirs):
                    file_count += 1
                    
        return file_count
    except Exception:
        return 0


def _create_error_response(
    error_code: str, error_message: str, start_time: float
) -> FindUnusedCodeResponse:
    """Create error response for failed Knip execution."""
    execution_time_ms = (time.time() - start_time) * 1000
    
    return FindUnusedCodeResponse(
        unused_items=[],
        total_issues=0,
        knip_configuration=KnipConfiguration(),
        execution_stats=KnipExecutionStats(
            knip_version="unknown",
            execution_time_ms=execution_time_ms,
            files_analyzed=0,
            total_issues=0,
            exit_code=-1,
            command_used=[],
            installation_method="none",
        ),
        errors=[AnalysisError(code=error_code, message=error_message)],
        success=False,
        # Add missing pagination fields
        total=0,
        page_size=None,
        next_cursor=None,
        has_more=None,
    )