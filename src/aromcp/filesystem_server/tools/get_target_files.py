"""Get target files implementation."""

import json
import time
from pathlib import Path
from typing import Any

from ...utils.pagination import simplify_pagination
from .._security import get_project_root


def get_target_files_impl(
    patterns: str | list[str],
    project_root: str | None = None,
    details: bool = False,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """List files based on path patterns.

    Args:
        patterns: File patterns to match (glob patterns like "**/*.py", "src/**/*.js")
        project_root: Root directory of the project
        details: Include size, modified, absolute_path (default: False)
        page: Page number for pagination (1-based, default: 1)
        max_tokens: Maximum tokens per page (default: 20000)

    Returns:
        Dictionary with paginated file list and metadata
    """
    start_time = time.time()

    try:
        # Resolve project root
        project_root = get_project_root(project_root)

        # Validate and normalize project root
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root does not exist: {project_root}"
                }
            }

        if not patterns:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Patterns required"
                }
            }

        # Handle case where patterns is still a JSON string (fallback)
        processed_patterns: list[str]
        if isinstance(patterns, str):
            try:
                parsed_patterns = json.loads(patterns)
                if not isinstance(parsed_patterns, list):
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": "Patterns must be a list of strings"
                        }
                    }
                processed_patterns = parsed_patterns
            except json.JSONDecodeError:
                # Treat as single pattern
                processed_patterns = [patterns]
        else:
            # patterns is already a list[str]
            processed_patterns = patterns

        files = _get_files_by_pattern(processed_patterns, project_path, details)

        duration_ms = int((time.time() - start_time) * 1000)

        # Create metadata
        metadata = {
            "patterns": processed_patterns,
            "duration_ms": duration_ms
        }

        # Apply simplified pagination with token-based sizing
        result = simplify_pagination(
            items=files,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: x["path"],
            metadata=metadata
        )
        
        return {"data": result}

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to get target files: {str(e)}"
            }
        }


def _get_files_by_pattern(
    patterns: list[str], project_path: Path, details: bool
) -> list[dict[str, Any]]:
    """Get files matching glob patterns."""
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
                rel_path = match.relative_to(project_path)
                
                # Create compact output by default
                file_info = {
                    "path": str(rel_path),
                    "matched_pattern": pattern
                }
                
                # Add details only if requested
                if details:
                    stat = match.stat()
                    file_info.update({
                        "absolute_path": str(match),
                        "size": stat.st_size,
                        "modified": stat.st_mtime
                    })
                
                files.append(file_info)

    # Remove duplicates based on path
    seen_paths = set()
    unique_files = []
    for file_info in files:
        if file_info["path"] not in seen_paths:
            seen_paths.add(file_info["path"])
            unique_files.append(file_info)

    return sorted(unique_files, key=lambda x: x["path"])


