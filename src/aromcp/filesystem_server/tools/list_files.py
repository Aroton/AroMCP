"""List files implementation."""

import json
import re
from pathlib import Path

from ...utils.pagination import auto_paginate_cursor_response
from .._security import get_project_root
from ..models.filesystem_models import ListFilesResponse


def list_files_impl(patterns: str | list[str], cursor: str | None = None, max_tokens: int = 20000) -> ListFilesResponse:
    """List files matching glob patterns.

    Args:
        patterns: File patterns to match (glob patterns like "**/*.py", "src/**/*.js")
        cursor: Cursor for pagination (None for first page)
        max_tokens: Maximum tokens per response

    Returns:
        ListFilesResponse with file list and optional pagination

    Note:
        Automatically excludes common folders like node_modules, .git, __pycache__, dist, etc.
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

        files = _get_file_paths_by_pattern(processed_patterns, project_path)

        # Build response using dataclass
        response = ListFilesResponse(files=files, pattern_used=patterns, total=len(files))

        # Use cursor-based pagination
        return auto_paginate_cursor_response(
            response=response,
            items_field="files",
            cursor=cursor,
            max_tokens=max_tokens,
            sort_key=lambda x: x,  # Sort alphabetically
        )

    except Exception as e:
        raise ValueError(f"Failed to list files: {str(e)}") from e


# Default folders to exclude
DEFAULT_EXCLUDE_DIRS = {
    "node_modules",
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".cache",
    ".parcel-cache",
    "coverage",
    ".nyc_output",
    ".venv",
    "venv",
    "env",
    ".env",
    "virtualenv",
    ".idea",
    ".vscode",
    ".DS_Store",
    "thumbs.db",
    ".terraform",
    "vendor",
    "target",  # Rust/Java
    "out",  # Various build systems
    ".gradle",
    ".settings",
    "bower_components",
}


def _expand_brace_patterns(pattern: str) -> list[str]:
    """Expand brace patterns like {js,jsx,ts,tsx} into multiple patterns.

    Args:
        pattern: A glob pattern that may contain brace expansions

    Returns:
        List of expanded glob patterns

    Examples:
        "src/**/*.{js,jsx}" -> ["src/**/*.js", "src/**/*.jsx"]
        "src/{components,utils}/**/*.ts" -> ["src/components/**/*.ts", "src/utils/**/*.ts"]
        "src/**/*.py" -> ["src/**/*.py"]  # No braces, return as-is
    """
    # Validate basic pattern structure
    if not pattern or not isinstance(pattern, str):
        return [pattern] if pattern else []

    # If no braces, return the pattern as-is
    if "{" not in pattern or "}" not in pattern:
        return [pattern]

    # Check for mismatched braces
    if pattern.count("{") != pattern.count("}"):
        # Malformed braces - treat as literal pattern
        return [pattern]

    # Find all brace patterns using regex
    brace_pattern = re.compile(r"\{([^{}]+)\}")

    def expand_single_brace(text: str) -> list[str]:
        """Expand a single brace pattern."""
        match = brace_pattern.search(text)
        if not match:
            return [text]

        # Extract the content inside braces
        brace_content = match.group(1)
        if not brace_content.strip():
            # Empty braces - treat as literal
            return [text]

        options = [opt.strip() for opt in brace_content.split(",")]
        # Filter out empty options
        options = [opt for opt in options if opt]

        if not options:
            # No valid options - treat as literal
            return [text]

        # Replace the brace pattern with each option
        results = []
        for option in options:
            expanded = text[: match.start()] + option + text[match.end() :]
            results.extend(expand_single_brace(expanded))  # Recursively handle nested braces

        return results

    try:
        return expand_single_brace(pattern)
    except Exception:
        # Any error in expansion - return original pattern as fallback
        return [pattern]


def _should_exclude_path(path: Path, exclude_dirs: set[str]) -> bool:
    """Check if a path should be excluded based on exclude patterns."""
    parts = path.parts
    for part in parts:
        if part in exclude_dirs:
            return True
        # Check glob patterns in exclude dirs
        for exclude_pattern in exclude_dirs:
            if "*" in exclude_pattern and Path(part).match(exclude_pattern):
                return True
    return False


def _get_file_paths_by_pattern(patterns: list[str], project_path: Path) -> list[str]:
    """Get file paths matching glob patterns, excluding common build/dependency folders."""
    files = []

    for pattern in patterns:
        # Expand brace patterns first
        expanded_patterns = _expand_brace_patterns(pattern)

        for expanded_pattern in expanded_patterns:
            # Use pathlib's glob for pattern matching
            if expanded_pattern.startswith("/"):
                # Absolute pattern within project
                matches = list(project_path.glob(expanded_pattern[1:]))
            else:
                # Relative pattern
                matches = list(project_path.rglob(expanded_pattern))

            for match in matches:
                if match.is_file():
                    # Check if the file should be excluded
                    if not _should_exclude_path(match.relative_to(project_path), DEFAULT_EXCLUDE_DIRS):
                        rel_path = str(match.relative_to(project_path))
                        files.append(rel_path)

    # Remove duplicates and sort
    return sorted(set(files))
