"""Write files batch implementation."""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .._security import validate_file_path_legacy


def write_files_batch_impl(
    files: dict[str, str],
    project_root: str = ".",
    encoding: str = "utf-8",
    create_backup: bool = True
) -> dict[str, Any]:
    """Write multiple files atomically with automatic directory creation.
    
    Args:
        files: Dictionary mapping file paths to content
        project_root: Root directory of the project
        encoding: File encoding to use
        create_backup: Whether to create backups of existing files
        
    Returns:
        Dictionary with write results and metadata
    """
    start_time = time.time()
    backup_dir = None
    temp_files = {}

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

        if not files:
            return {
                "data": {
                    "written": [],
                    "created_directories": [],
                    "backup_location": None
                }
            }

        # Validate all file paths first
        validated_files = {}
        for file_path, content in files.items():
            abs_file_path = validate_file_path_legacy(file_path, project_path)
            validated_files[file_path] = {
                "abs_path": abs_file_path,
                "content": content,
                "exists": abs_file_path.exists()
            }

        # Create backup if requested and files exist
        if create_backup and any(info["exists"] for info in validated_files.values()):
            backup_dir = _create_backup(validated_files, project_path)

        # Create temporary files first (atomic operation preparation)
        for file_path, info in validated_files.items():
            abs_path = info["abs_path"]
            content = info["content"]

            # Create parent directories if they don't exist
            abs_path.parent.mkdir(parents=True, exist_ok=True)

            # Create temporary file in same directory (for atomic move)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=abs_path.parent,
                prefix=f".tmp_{abs_path.name}_"
            )

            try:
                # Write content to temporary file
                with os.fdopen(temp_fd, 'w', encoding=encoding) as f:
                    f.write(content)

                temp_files[file_path] = temp_path

            except Exception:
                # Clean up file descriptor if write failed
                os.close(temp_fd)
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        # Atomic move all temporary files to final locations
        written_files = []
        created_directories = set()

        for file_path, temp_path in temp_files.items():
            abs_path = validated_files[file_path]["abs_path"]

            # Track created directories
            current_dir = abs_path.parent
            while current_dir != project_path and not current_dir.exists():
                created_directories.add(str(current_dir.relative_to(project_path)))
                current_dir = current_dir.parent

            # Atomic move
            shutil.move(temp_path, abs_path)

            # Get file stats after write
            stat = abs_path.stat()
            written_files.append({
                "path": file_path,
                "size": stat.st_size,
                "lines": len(validated_files[file_path]["content"].splitlines()),
                "created": not validated_files[file_path]["exists"]
            })

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "data": {
                "written": written_files,
                "created_directories": sorted(list(created_directories)),
                "backup_location": str(backup_dir.relative_to(project_path)) if backup_dir else None,
                "summary": {
                    "total_files": len(files),
                    "new_files": sum(1 for f in written_files if f["created"]),
                    "updated_files": sum(1 for f in written_files if not f["created"]),
                    "total_size": sum(f["size"] for f in written_files)
                }
            }
        }

    except Exception as e:
        # Cleanup temporary files on error
        for temp_path in temp_files.values():
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass

        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to write files: {str(e)}"
            }
        }




def _create_backup(validated_files: dict[str, dict[str, Any]], project_path: Path) -> Path:
    """Create backup of existing files."""

    # Create backup directory with timestamp
    timestamp = int(time.time())
    backup_dir = project_path / ".mcp" / "backups" / f"batch_write_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create backup manifest
    manifest = {
        "timestamp": timestamp,
        "operation": "write_files_batch",
        "files": []
    }

    for file_path, info in validated_files.items():
        if info["exists"]:
            abs_path = info["abs_path"]

            # Create backup file path maintaining directory structure
            rel_path = abs_path.relative_to(project_path)
            backup_file_path = backup_dir / rel_path

            # Create parent directories in backup
            backup_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file to backup
            shutil.copy2(abs_path, backup_file_path)

            manifest["files"].append({
                "original_path": file_path,
                "backup_path": str(rel_path),
                "size": abs_path.stat().st_size
            })

    # Write backup manifest
    manifest_path = backup_dir / "manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    return backup_dir
