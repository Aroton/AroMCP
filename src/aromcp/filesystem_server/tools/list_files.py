"""List files implementation."""

import json
from pathlib import Path

from .._security import get_project_root


def list_files_impl(patterns: str | list[str]) -> list[str]:
    """List files matching glob patterns.

    Args:
        patterns: File patterns to match (glob patterns like "**/*.py", "src/**/*.js")

    Returns:
        List of relative file paths
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)

        # Validate and normalize project root
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            raise FileNotFoundError(f"Project root does not exist: {project_root}")

        if not patterns:
            raise ValueError("Patterns required")

        # Handle case where patterns is still a JSON string (fallback)
        processed_patterns: list[str]
        if isinstance(patterns, str):
            try:
                parsed_patterns = json.loads(patterns)
                if not isinstance(parsed_patterns, list):
                    raise ValueError("Patterns must be a list of strings")
                processed_patterns = parsed_patterns
            except json.JSONDecodeError:
                # Treat as single pattern
                processed_patterns = [patterns]
        else:
            # patterns is already a list[str]
            processed_patterns = patterns

        return _get_file_paths_by_pattern(processed_patterns, project_path)

    except Exception as e:
        raise ValueError(f"Failed to list files: {str(e)}") from e


def _get_file_paths_by_pattern(
    patterns: list[str], project_path: Path
) -> list[str]:
    """Get file paths matching glob patterns."""
    files = []

    for pattern in patterns:
        # Use pathlib's glob for pattern matching
        if pattern.startswith('/'):
            # Absolute pattern within project
            matches = list(project_path.glob(pattern[1:]))
        else:
            # Relative pattern
            matches = list(project_path.rglob(pattern))

        for match in matches:
            if match.is_file():
                rel_path = str(match.relative_to(project_path))
                files.append(rel_path)

    # Remove duplicates and sort
    return sorted(set(files))


