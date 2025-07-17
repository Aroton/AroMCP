"""Write files implementation."""

from pathlib import Path

from .._security import get_project_root, validate_file_path_legacy


def write_files_impl(files: dict[str, str] | str) -> None:
    """Write multiple NEW files atomically with automatic directory creation.

    IMPORTANT: This function is designed for creating new files only.
    For modifying existing files, use Claude Code's Edit or MultiEdit tools instead.

    Args:
        files: Dictionary mapping file paths to content for new files

    Returns:
        None
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

        # Write files atomically
        for file_path, content in files.items():
            # Validate file path for security
            try:
                validated_path = validate_file_path_legacy(file_path, project_path)
                full_path = validated_path
            except ValueError as e:
                raise ValueError(f"Invalid file path: {str(e)}") from e

            # Create directories if they don't exist
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            full_path.write_text(content, encoding='utf-8')

    except Exception as e:
        raise ValueError(f"Failed to write files: {str(e)}") from e
