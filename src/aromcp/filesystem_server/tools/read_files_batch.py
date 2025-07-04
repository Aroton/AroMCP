"""Read files batch implementation."""

import time
from pathlib import Path
from typing import Any

import chardet

from ...utils.pagination import paginate_list
from .._security import get_project_root, validate_file_path_legacy


def read_files_batch_impl(
    file_paths: str | list[str],
    project_root: str | None = None,
    encoding: str = "auto",
    expand_patterns: bool = True,
    page: int = 1,
    max_tokens: int = 20000
) -> dict[str, Any]:
    """Read multiple files in one operation.

    Args:
        file_paths: List of file paths or glob patterns to read
            (relative to project_root)
        project_root: Root directory of the project
        encoding: File encoding ("auto", "utf-8", "ascii", etc.)
        expand_patterns: Whether to expand glob patterns in file_paths
            (default: True)
        page: Page number (1-based) for pagination
        max_tokens: Maximum tokens per page

    Returns:
        Paginated dictionary with file contents and metadata
    """
    start_time = time.time()

    try:
        # Normalize file_paths to list
        if isinstance(file_paths, str):
            file_paths = [file_paths]

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

        # Expand patterns if requested
        if expand_patterns:
            expanded_paths = []
            for file_path in file_paths:
                if any(char in file_path for char in ['*', '?', '[', ']']):
                    # This looks like a glob pattern
                    matches = list(project_path.glob(file_path))
                    if matches:
                        for match in matches:
                            if match.is_file():
                                try:
                                    rel_path = match.relative_to(project_path)
                                    expanded_paths.append(str(rel_path))
                                except ValueError:
                                    # Skip files outside project root
                                    continue
                    else:
                        # No matches found, keep original path for error reporting
                        expanded_paths.append(file_path)
                else:
                    # Not a pattern, use as-is
                    expanded_paths.append(file_path)

            # Remove duplicates while preserving order
            seen = set()
            unique_paths = []
            for path in expanded_paths:
                if path not in seen:
                    seen.add(path)
                    unique_paths.append(path)

            actual_file_paths = unique_paths
        else:
            actual_file_paths = file_paths

        files_list = []
        errors = []
        total_size = 0

        for file_path in actual_file_paths:
            try:
                # Security: Validate file path to prevent directory traversal
                abs_file_path = validate_file_path_legacy(file_path, project_path)

                if not abs_file_path.exists():
                    errors.append({
                        "file": file_path,
                        "error": "File not found"
                    })
                    continue

                if not abs_file_path.is_file():
                    errors.append({
                        "file": file_path,
                        "error": "Path is not a file"
                    })
                    continue

                # Get file stats
                stat = abs_file_path.stat()
                file_size = stat.st_size
                total_size += file_size

                # Check file size (warn for large files)
                if file_size > 1024 * 1024:  # 1MB
                    errors.append({
                        "file": file_path,
                        "error": "File too large (>1MB), consider streaming",
                        "size": file_size
                    })
                    continue

                # Read file content
                content, detected_encoding = _read_file_content(abs_file_path, encoding)

                files_list.append({
                    "file_path": file_path,
                    "content": content,
                    "encoding": detected_encoding,
                    "size": file_size,
                    "modified": stat.st_mtime,
                    "lines": len(content.splitlines()) if content else 0
                })

            except Exception as e:
                errors.append({
                    "file": file_path,
                    "error": str(e)
                })

        duration_ms = int((time.time() - start_time) * 1000)

        # Create metadata for pagination
        metadata: dict[str, Any] = {
            "summary": {
                "total_files": len(actual_file_paths),
                "input_patterns": len(file_paths),
                "successful": len(files_list),
                "failed": len(errors),
                "total_size": total_size,
                "patterns_expanded": expand_patterns,
                "duration_ms": duration_ms
            }
        }

        if errors:
            metadata["errors"] = errors

        # Return paginated list
        return paginate_list(
            items=files_list,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: x["file_path"],  # Sort by file path
            metadata=metadata
        )

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to read files: {str(e)}"
            }
        }




def _read_file_content(file_path: Path, encoding: str = "auto") -> tuple[str, str]:
    """Read file content with encoding detection."""

    # Read raw bytes first
    raw_content = file_path.read_bytes()

    if encoding == "auto":
        # Detect encoding
        if len(raw_content) == 0:
            return "", "utf-8"

        # Try UTF-8 first (most common)
        try:
            content = raw_content.decode('utf-8')
            return content, "utf-8"
        except UnicodeDecodeError:
            pass

        # Use chardet for detection
        detected = chardet.detect(raw_content)
        detected_encoding = detected.get('encoding', 'utf-8')
        confidence = detected.get('confidence', 0)

        # If confidence is low, try common encodings
        if confidence < 0.8:
            for fallback_encoding in ['iso-8859-1', 'windows-1252', 'ascii']:
                try:
                    content = raw_content.decode(fallback_encoding)
                    return content, fallback_encoding
                except UnicodeDecodeError:
                    continue

        # Use detected encoding
        try:
            content = raw_content.decode(detected_encoding or 'utf-8')
            return content, detected_encoding or 'utf-8'
        except (UnicodeDecodeError, TypeError):
            # Last resort: decode with errors='replace'
            content = raw_content.decode('utf-8', errors='replace')
            return content, "utf-8-with-errors"

    else:
        # Use specified encoding
        try:
            content = raw_content.decode(encoding)
            return content, encoding
        except UnicodeDecodeError:
            # Fallback with error replacement
            content = raw_content.decode(encoding, errors='replace')
            return content, f"{encoding}-with-errors"
