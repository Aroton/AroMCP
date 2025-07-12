"""Apply file diffs tool implementation."""

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .._security import get_project_root, validate_file_path


def apply_file_diffs_impl(
    diffs: list[dict[str, Any]],
    project_root: str | None = None,
    create_backup: bool = True,
    validate_before_apply: bool = True
) -> dict[str, Any]:
    """Apply multiple diffs to files with validation and rollback support.

    Args:
        diffs: List of diff objects with 'file_path' and 'diff_content' keys
        project_root: Root directory of the project
        create_backup: Whether to create backups before applying diffs
        validate_before_apply: Whether to validate all diffs before applying any

    Returns:
        Dictionary with success status, applied files, and any errors
    """
    try:
        # Resolve project root
        project_root = get_project_root(project_root)

        project_path = Path(project_root).resolve()
        applied_files = []
        backup_info = {}
        errors = []

        # First pass: validate all diffs if requested
        if validate_before_apply:
            validation_result = _validate_all_diffs(diffs, project_path)
            if not validation_result["all_valid"]:
                return {
                    "error": {
                        "code": "VALIDATION_FAILED",
                        "message": "Diff validation failed",
                        "details": validation_result["errors"]
                    }
                }

        # Create temporary backup directory if needed
        backup_dir = None
        if create_backup:
            backup_dir = tempfile.mkdtemp(prefix="aromcp_backup_")

        try:
            # Apply diffs one by one
            for diff_obj in diffs:
                result = _apply_single_diff(
                    diff_obj, project_path, backup_dir, backup_info
                )

                if "error" in result:
                    errors.append({
                        "file": diff_obj.get("file_path", "unknown"),
                        "error": result["error"]
                    })
                    # If any diff fails, rollback all changes
                    if create_backup:
                        _rollback_changes(backup_info)
                    return {
                        "error": {
                            "code": "APPLY_FAILED",
                            "message": "Failed to apply diff, changes rolled back",
                            "details": errors
                        }
                    }
                else:
                    applied_files.append(result["file_path"])

            # Success - clean up backup if everything worked
            if backup_dir and os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)

            return {
                "data": {
                    "applied_files": applied_files,
                    "total_applied": len(applied_files),
                    "backup_created": create_backup,
                    "validation_performed": validate_before_apply
                }
            }

        except Exception as e:
            # Rollback on any unexpected error
            if create_backup:
                _rollback_changes(backup_info)
            raise e

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to apply diffs: {str(e)}"
            }
        }


def _validate_all_diffs(diffs: list[dict[str, Any]], project_path: Path) -> dict[str, Any]:
    """Validate all diffs before applying any."""
    errors = []

    for i, diff_obj in enumerate(diffs):
        try:
            file_path = diff_obj.get("file_path")
            diff_content = diff_obj.get("diff_content")

            if not file_path or not diff_content:
                errors.append({
                    "index": i,
                    "error": "Missing file_path or diff_content"
                })
                continue

            # Validate file path
            validation_result = validate_file_path(file_path, str(project_path))
            if not validation_result["valid"]:
                errors.append({
                    "index": i,
                    "file": file_path,
                    "error": validation_result["error"]
                })
                continue

            # Parse and validate diff format
            validation_result = _validate_diff_format(diff_content, file_path, project_path)
            if not validation_result["valid"]:
                errors.append({
                    "index": i,
                    "file": file_path,
                    "error": validation_result["error"]
                })

        except Exception as e:
            errors.append({
                "index": i,
                "error": f"Validation error: {str(e)}"
            })

    return {
        "all_valid": len(errors) == 0,
        "errors": errors
    }


def _validate_diff_format(diff_content: str, file_path: str, project_path: Path) -> dict[str, Any]:
    """Validate that diff format is correct and applicable."""
    try:
        # Check if it's a unified diff format
        lines = diff_content.strip().split('\n')

        if not lines:
            return {"valid": False, "error": "Empty diff content"}

        # Basic unified diff format check
        has_diff_header = any(line.startswith('---') or line.startswith('+++') for line in lines[:10])
        has_hunk_header = any(line.startswith('@@') for line in lines)

        if not (has_diff_header and has_hunk_header):
            return {"valid": False, "error": "Invalid unified diff format"}

        # Check if source file exists and content matches
        full_path = project_path / file_path
        if full_path.exists():
            try:
                with open(full_path, encoding='utf-8') as f:
                    current_content = f.read()

                # Try to apply diff to verify it's applicable
                current_content.splitlines(keepends=True)

                # Parse the diff and check if it can be applied
                try:
                    _parse_unified_diff(diff_content)
                except Exception as e:
                    return {"valid": False, "error": f"Cannot parse diff: {str(e)}"}

            except Exception as e:
                return {"valid": False, "error": f"Cannot read source file: {str(e)}"}

        return {"valid": True}

    except Exception as e:
        return {"valid": False, "error": f"Diff validation failed: {str(e)}"}


def _apply_single_diff(
    diff_obj: dict[str, Any],
    project_path: Path,
    backup_dir: str | None,
    backup_info: dict[str, str]
) -> dict[str, Any]:
    """Apply a single diff to a file."""
    try:
        file_path = diff_obj["file_path"]
        diff_content = diff_obj["diff_content"]

        # Validate file path
        validation_result = validate_file_path(file_path, str(project_path))
        if not validation_result["valid"]:
            return {"error": validation_result["error"]}

        full_path = project_path / file_path

        # Create backup if requested
        if backup_dir and full_path.exists():
            backup_path = os.path.join(backup_dir, file_path.replace('/', '_'))
            shutil.copy2(full_path, backup_path)
            backup_info[str(full_path)] = backup_path

        # Read current content
        current_content = ""
        if full_path.exists():
            with open(full_path, encoding='utf-8') as f:
                current_content = f.read()

        # Apply diff
        new_content = _apply_unified_diff(current_content, diff_content)

        # Ensure directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Write new content
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return {"file_path": file_path}

    except Exception as e:
        return {"error": f"Failed to apply diff: {str(e)}"}


def _apply_unified_diff(original_content: str, diff_content: str) -> str:
    """Apply a unified diff to content."""
    original_lines = original_content.splitlines(keepends=True)

    # Parse the unified diff
    hunks = _parse_unified_diff(diff_content)

    # Apply hunks in reverse order to maintain line numbers
    result_lines = original_lines.copy()

    for hunk in reversed(hunks):
        start_line = hunk["old_start"] - 1  # Convert to 0-based

        # Remove deleted lines and add new lines
        lines_to_remove = []
        lines_to_add = []

        for change in hunk["changes"]:
            if change["type"] == "delete":
                lines_to_remove.append(change["line"])
            elif change["type"] == "add":
                lines_to_add.append(change["line"])

        # Apply changes
        end_line = start_line + len([c for c in hunk["changes"] if c["type"] in ["delete", "context"]])

        # Replace the section
        new_section = []

        for change in hunk["changes"]:
            if change["type"] == "add":
                new_section.append(change["line"])
            elif change["type"] == "context":
                new_section.append(change["line"])
            # Skip deleted lines

        result_lines[start_line:end_line] = new_section

    return ''.join(result_lines)


def _parse_unified_diff(diff_content: str) -> list[dict[str, Any]]:
    """Parse unified diff format into structured data."""
    lines = diff_content.split('\n')
    hunks = []
    current_hunk = None

    for line in lines:
        if line.startswith('@@'):
            # Hunk header: @@ -old_start,old_count +new_start,new_count @@
            if current_hunk:
                hunks.append(current_hunk)

            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if match:
                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1

                current_hunk = {
                    "old_start": old_start,
                    "old_count": old_count,
                    "new_start": new_start,
                    "new_count": new_count,
                    "changes": []
                }
        elif current_hunk and line:
            if line.startswith('-'):
                current_hunk["changes"].append({
                    "type": "delete",
                    "line": line[1:] + '\n'
                })
            elif line.startswith('+'):
                current_hunk["changes"].append({
                    "type": "add",
                    "line": line[1:] + '\n'
                })
            elif line.startswith(' '):
                current_hunk["changes"].append({
                    "type": "context",
                    "line": line[1:] + '\n'
                })

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def _rollback_changes(backup_info: dict[str, str]) -> None:
    """Rollback changes using backup files."""
    for original_path, backup_path in backup_info.items():
        try:
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, original_path)
        except Exception:  # noqa: S110 # Intentionally ignoring errors during rollback
            # Log error but continue with other files
            pass
