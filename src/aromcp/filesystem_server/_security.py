"""Security validation utilities for filesystem operations."""

import os
from pathlib import Path
from typing import Any


def get_project_root() -> str:
    """Get project root from environment or default.

    Returns:
        Project root directory path from MCP_FILE_ROOT environment variable,
        or current directory as fallback
    """
    return os.getenv('MCP_FILE_ROOT', '.')


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
        path = Path(file_path)

        # If it's absolute, it should be within project_root
        if path.is_absolute():
            abs_path = path.resolve()
        else:
            abs_path = (project_path / path).resolve()

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
    # Convert to Path and resolve
    path = Path(file_path)

    # If it's absolute, it should be within project_root
    if path.is_absolute():
        abs_path = path.resolve()
    else:
        abs_path = (project_root / path).resolve()

    # Security check: ensure the resolved path is within project_root
    try:
        abs_path.relative_to(project_root)
    except ValueError:
        raise ValueError(f"File path outside project root: {file_path}") from None

    return abs_path
