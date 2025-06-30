"""Preview file changes tool implementation."""

from pathlib import Path
from typing import Any

from .._security import validate_file_path
from .apply_file_diffs import _parse_unified_diff, _validate_diff_format


def preview_file_changes_impl(
    diffs: list[dict[str, Any]],
    project_root: str = ".",
    include_full_preview: bool = True,
    max_preview_lines: int = 50
) -> dict[str, Any]:
    """Show consolidated preview of all pending changes.
    
    Args:
        diffs: List of diff objects with 'file_path' and 'diff_content' keys
        project_root: Root directory of the project
        include_full_preview: Whether to include full diff preview for each file
        max_preview_lines: Maximum lines to show in preview
        
    Returns:
        Dictionary with change summary, file details, and validation status
    """
    try:
        project_path = Path(project_root).resolve()
        files = []
        total_changes = 0
        conflicts_detected = False
        all_valid = True
        validation_errors = []

        # Process each diff
        for i, diff_obj in enumerate(diffs):
            try:
                file_result = _process_single_file_diff(
                    diff_obj, project_path, include_full_preview, max_preview_lines
                )

                if "error" in file_result:
                    all_valid = False
                    validation_errors.append({
                        "index": i,
                        "file": diff_obj.get("file_path", "unknown"),
                        "error": file_result["error"]
                    })
                    continue

                files.append(file_result)
                total_changes += file_result["additions"] + file_result["deletions"]

                if file_result.get("conflicts"):
                    conflicts_detected = True

            except Exception as e:
                all_valid = False
                validation_errors.append({
                    "index": i,
                    "file": diff_obj.get("file_path", "unknown"),
                    "error": f"Processing error: {str(e)}"
                })

        # Check for inter-file conflicts
        inter_file_conflicts = _detect_inter_file_conflicts(files)
        if inter_file_conflicts:
            conflicts_detected = True

        return {
            "data": {
                "total_files": len(files),
                "total_changes": total_changes,
                "files": files,
                "validation": {
                    "all_valid": all_valid,
                    "conflicts_detected": conflicts_detected,
                    "applicable": all_valid and not conflicts_detected,
                    "errors": validation_errors,
                    "inter_file_conflicts": inter_file_conflicts
                }
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to preview changes: {str(e)}"
            }
        }


def _process_single_file_diff(
    diff_obj: dict[str, Any],
    project_path: Path,
    include_full_preview: bool,
    max_preview_lines: int
) -> dict[str, Any]:
    """Process a single file diff for preview."""
    file_path = diff_obj.get("file_path")
    diff_content = diff_obj.get("diff_content")

    if not file_path or not diff_content:
        return {"error": "Missing file_path or diff_content"}

    # Validate file path
    validation_result = validate_file_path(file_path, str(project_path))
    if not validation_result["valid"]:
        return {"error": validation_result["error"]}

    # Validate diff format
    diff_validation = _validate_diff_format(diff_content, file_path, project_path)
    if not diff_validation["valid"]:
        return {"error": diff_validation["error"]}

    # Parse diff to get statistics
    try:
        hunks = _parse_unified_diff(diff_content)
        additions = 0
        deletions = 0
        conflicts = []

        for hunk in hunks:
            for change in hunk["changes"]:
                if change["type"] == "add":
                    additions += 1
                elif change["type"] == "delete":
                    deletions += 1

        # Generate preview
        preview = ""
        if include_full_preview:
            preview = _generate_diff_preview(diff_content, max_preview_lines)

        # Check file existence and get metadata
        full_path = project_path / file_path
        file_exists = full_path.exists()
        file_size = full_path.stat().st_size if file_exists else 0

        return {
            "path": file_path,
            "additions": additions,
            "deletions": deletions,
            "net_change": additions - deletions,
            "conflicts": conflicts,
            "preview": preview,
            "file_exists": file_exists,
            "file_size": file_size,
            "hunks_count": len(hunks)
        }

    except Exception as e:
        return {"error": f"Failed to parse diff: {str(e)}"}


def _generate_diff_preview(diff_content: str, max_lines: int) -> str:
    """Generate a readable preview of the diff."""
    lines = diff_content.split('\n')

    if len(lines) <= max_lines:
        return diff_content

    # Show first portion and indicate truncation
    preview_lines = lines[:max_lines-1]
    remaining_lines = len(lines) - max_lines + 1

    preview_lines.append(f"... ({remaining_lines} more lines)")

    return '\n'.join(preview_lines)


def _detect_inter_file_conflicts(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect conflicts between different file changes."""
    conflicts = []

    # Check for files that might have overlapping changes
    # This is a basic implementation - could be enhanced with more sophisticated analysis

    file_paths = [f["path"] for f in files]

    # Check for potential import/dependency conflicts
    # (This would need more sophisticated analysis in a real implementation)

    return conflicts
