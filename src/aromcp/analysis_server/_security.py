"""Security validation utilities for code analysis operations."""

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


def validate_pattern_safe(pattern: str) -> dict[str, Any]:
    """Validate that a glob pattern is safe to use.
    
    Args:
        pattern: Glob pattern to validate
        
    Returns:
        Dictionary with validation result and error message if invalid
    """
    # Check for potentially dangerous patterns
    dangerous_patterns = [
        '../',  # Directory traversal
        '/..',  # Directory traversal  
        '//',   # Double slashes
        '\\',   # Windows path separators that could cause issues
    ]
    
    for dangerous in dangerous_patterns:
        if dangerous in pattern:
            return {
                "valid": False,
                "error": f"Potentially unsafe pattern: {pattern}"
            }
    
    # Check for reasonable length
    if len(pattern) > 1000:
        return {
            "valid": False,
            "error": "Pattern too long"
        }
    
    return {"valid": True}


def validate_standards_directory(standards_dir: str, project_root: str) -> dict[str, Any]:
    """Validate that a standards directory path is safe and accessible.
    
    Args:
        standards_dir: Directory path to validate (relative to project_root)
        project_root: Project root directory
        
    Returns:
        Dictionary with validation result and resolved path
    """
    if not standards_dir:
        return {
            "valid": False,
            "error": "Standards directory cannot be empty"
        }
    
    # Validate the path using existing validation
    full_path = str(Path(project_root) / standards_dir)
    validation = validate_file_path(full_path, project_root)
    
    if not validation["valid"]:
        return validation
    
    return {
        "valid": True,
        "abs_path": validation["abs_path"]
    }