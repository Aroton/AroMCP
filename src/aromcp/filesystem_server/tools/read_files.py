"""Read files implementation."""

from pathlib import Path
from typing import Any

import chardet

from ...utils.pagination import simplify_cursor_pagination
from .._security import get_project_root, validate_file_path_legacy


def read_files_impl(files: str | list[str], cursor: str | None = None, max_tokens: int = 20000) -> dict[str, Any]:
    """Read multiple files and return their contents.

    Args:
        files: File paths to read
        cursor: Cursor for pagination (None for first page)
        max_tokens: Maximum tokens per response

    Returns:
        Dictionary with paginated file contents and metadata
    """
    try:
        # Use MCP_FILE_ROOT
        project_root = get_project_root(None)
        project_path = Path(project_root)

        # Normalize files to list
        if isinstance(files, str):
            files = [files]

        file_contents = []
        for file_path in files:
            # Validate file path for security
            try:
                validated_path = validate_file_path_legacy(file_path, project_path)
                full_path = validated_path
            except ValueError as e:
                raise ValueError(f"Invalid file path: {str(e)}") from e

            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            if not full_path.is_file():
                raise ValueError(f"Path is not a file: {file_path}")

            # Detect encoding
            raw_content = full_path.read_bytes()
            detected_encoding = chardet.detect(raw_content)
            encoding = detected_encoding.get("encoding", "utf-8")

            if encoding is None:
                encoding = "utf-8"

            try:
                content = raw_content.decode(encoding)
            except UnicodeDecodeError:
                # Fallback to utf-8 with error handling
                content = raw_content.decode("utf-8", errors="replace")

            file_contents.append({"file": file_path, "content": content, "encoding": encoding, "size": len(content)})

        # Apply pagination
        metadata = {"total_files": len(file_contents), "files_requested": len(files)}

        # Use cursor-based pagination
        return simplify_cursor_pagination(
            items=file_contents, cursor=cursor, max_tokens=max_tokens, sort_key=lambda x: x["file"], metadata=metadata
        )

    except Exception as e:
        raise ValueError(f"Failed to read files: {str(e)}") from e
