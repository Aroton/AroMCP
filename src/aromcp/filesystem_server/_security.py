"""Security validation utilities for filesystem operations."""

import os
from pathlib import Path
from typing import Any


def get_project_root(project_root: str | None = None) -> str:
    """Get project root from environment or default.

    Args:
        project_root: Provided project root, if None or "." will use environment

    Returns:
        Project root directory path from MCP_FILE_ROOT environment variable,
        or current directory as fallback
    """
    if project_root is None or project_root == ".":
        return os.getenv('MCP_FILE_ROOT', '.')
    return project_root


def validate_file_path(file_path: str, project_root: str) -> dict[str, Any]:
    """Validate file path to prevent directory traversal attacks.

    Args:
        file_path: File path to validate
        project_root: Root directory of the project

    Returns:
        Dictionary with validation result and error message if invalid
    """
    try:
        project_path = Path(project_root).resolve()
        # Expand user home directory (~) if present
        path = Path(file_path).expanduser()

        # If it's absolute, it should be within project_root
        if path.is_absolute():
            abs_path = path.resolve()
        else:
            abs_path = (project_path / path).resolve()

        # Special case: Allow access to ~/.claude directory for Claude configuration
        claude_config_path = Path.home() / ".claude"
        try:
            abs_path.relative_to(claude_config_path)
            # Path is within ~/.claude, allow access
            return {
                "valid": True,
                "abs_path": abs_path
            }
        except ValueError:
            # Not in ~/.claude, continue with normal validation
            pass

        # Security check: ensure the resolved path is within project_root
        try:
            abs_path.relative_to(project_path)
        except ValueError:
            return {
                "valid": False,
                "error": f"File path outside project root: {file_path}"
            }

        return {
            "valid": True,
            "abs_path": abs_path
        }

    except Exception as e:
        return {
            "valid": False,
            "error": f"Invalid file path: {str(e)}"
        }


def validate_file_path_legacy(file_path: str, project_root: Path) -> Path:
    """Legacy validation function for backward compatibility with existing tools.

    Args:
        file_path: File path to validate
        project_root: Root directory of the project as Path object

    Returns:
        Validated absolute path

    Raises:
        ValueError: If path is invalid or outside project root
    """
    # Convert to Path and resolve, expanding user home directory (~) if present
    path = Path(file_path).expanduser()

    # If it's absolute, it should be within project_root
    if path.is_absolute():
        abs_path = path.resolve()
    else:
        abs_path = (project_root / path).resolve()

    # Special case: Allow access to ~/.claude directory for Claude configuration
    claude_config_path = Path.home() / ".claude"
    try:
        abs_path.relative_to(claude_config_path)
        # Path is within ~/.claude, allow access
        return abs_path
    except ValueError:
        # Not in ~/.claude, continue with normal validation
        pass

    # Security check: ensure the resolved path is within project_root
    try:
        abs_path.relative_to(project_root)
    except ValueError:
        raise ValueError(f"File path outside project root: {file_path}") from None

    return abs_path
