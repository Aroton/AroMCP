"""Write files implementation."""

from pathlib import Path
from typing import Any

from .._security import get_project_root, validate_file_path_legacy


def write_files_impl(files: dict[str, str] | str) -> dict[str, Any]:
    """Write multiple NEW files atomically with automatic directory creation.

    IMPORTANT: This function is designed for creating new files only.
    For modifying existing files, use Claude Code's Edit or MultiEdit tools instead.

    Args:
        files: Dictionary mapping file paths to content for new files

    Returns:
        Dictionary with written files info
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)
        project_path = Path(project_root)

        # Handle JSON string conversion if needed
        if isinstance(files, str):
            import json

            try:
                files = json.loads(files)
            except json.JSONDecodeError as e:
                raise ValueError("Files parameter must be a valid JSON object") from e

        if not files:
            raise ValueError("Files dictionary cannot be empty")

        files_written = []
        directories_created = set()

        # Write files atomically
        for file_path, content in files.items():
            # Validate file path for security
            try:
                validated_path = validate_file_path_legacy(file_path, project_path)
                full_path = validated_path
            except ValueError as e:
                raise ValueError(f"Invalid file path: {str(e)}") from e

            # Create directories if they don't exist
            parent_dir = full_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
                directories_created.add(str(parent_dir.relative_to(project_path)))

            # Write content
            full_path.write_text(content, encoding="utf-8")
            files_written.append(file_path)

        return {
            "files_written": files_written,
            "total_files": len(files_written),
            "directories_created": sorted(directories_created),
            "success": True,
        }

    except Exception as e:
        raise ValueError(f"Failed to write files: {str(e)}") from e
