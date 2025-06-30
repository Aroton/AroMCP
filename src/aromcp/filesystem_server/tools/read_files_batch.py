"""Read files batch implementation."""

import time
from pathlib import Path
from typing import Any

import chardet


def read_files_batch_impl(
    file_paths: list[str],
    project_root: str = ".",
    encoding: str = "auto"
) -> dict[str, Any]:
    """Read multiple files in one operation.
    
    Args:
        file_paths: List of file paths to read (relative to project_root)
        project_root: Root directory of the project
        encoding: File encoding ("auto", "utf-8", "ascii", etc.)
        
    Returns:
        Dictionary with file contents and metadata
    """
    start_time = time.time()

    try:
        # Validate and normalize project root
        project_path = Path(project_root).resolve()
        if not project_path.exists():
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Project root does not exist: {project_root}"
                }
            }

        files_data = {}
        errors = []
        total_size = 0

        for file_path in file_paths:
            try:
                # Security: Validate file path to prevent directory traversal
                abs_file_path = _validate_file_path(file_path, project_path)

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

                files_data[file_path] = {
                    "content": content,
                    "encoding": detected_encoding,
                    "size": file_size,
                    "modified": stat.st_mtime,
                    "lines": len(content.splitlines()) if content else 0
                }

            except Exception as e:
                errors.append({
                    "file": file_path,
                    "error": str(e)
                })

        duration_ms = int((time.time() - start_time) * 1000)

        result = {
            "data": {
                "files": files_data,
                "summary": {
                    "total_files": len(file_paths),
                    "successful": len(files_data),
                    "failed": len(errors),
                    "total_size": total_size
                }
            }
        }

        if errors:
            result["data"]["errors"] = errors

        return result

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to read files: {str(e)}"
            }
        }


def _validate_file_path(file_path: str, project_root: Path) -> Path:
    """Validate file path to prevent directory traversal attacks."""
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
        raise ValueError(f"File path outside project root: {file_path}")

    return abs_path


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
            content = raw_content.decode(detected_encoding)
            return content, detected_encoding
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
