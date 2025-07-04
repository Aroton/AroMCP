"""Validate diffs tool implementation."""

import re
from pathlib import Path
from typing import Any

from .._security import get_project_root, validate_file_path


def validate_diffs_impl(
    diffs: list[dict[str, Any]],
    project_root: str | None = None,
    check_conflicts: bool = True,
    check_syntax: bool = True
) -> dict[str, Any]:
    """Pre-validate diffs for conflicts and applicability.

    Args:
        diffs: List of diff objects with 'file_path' and 'diff_content' keys
        project_root: Root directory of the project
        check_conflicts: Whether to check for conflicts between diffs
        check_syntax: Whether to validate diff syntax

    Returns:
        Dictionary with validation results for each diff and overall status
    """
    try:
        # Resolve project root
        project_root = get_project_root(project_root)

        project_path = Path(project_root).resolve()
        validation_results = []
        overall_valid = True
        global_conflicts = []

        # Validate each diff individually
        for i, diff_obj in enumerate(diffs):
            result = _validate_single_diff(diff_obj, project_path, check_syntax)
            result["index"] = i
            validation_results.append(result)

            if not result["valid"]:
                overall_valid = False

        # Check for conflicts between diffs if requested
        if check_conflicts and len(diffs) > 1:
            conflict_results = _check_diff_conflicts(diffs, project_path)
            global_conflicts = conflict_results["conflicts"]
            if global_conflicts:
                overall_valid = False

        return {
            "data": {
                "overall_valid": overall_valid,
                "total_diffs": len(diffs),
                "valid_diffs": len([r for r in validation_results if r["valid"]]),
                "invalid_diffs": len([r for r in validation_results if not r["valid"]]),
                "global_conflicts": global_conflicts,
                "individual_results": validation_results
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to validate diffs: {str(e)}"
            }
        }


def _validate_single_diff(
    diff_obj: dict[str, Any],
    project_path: Path,
    check_syntax: bool
) -> dict[str, Any]:
    """Validate a single diff."""
    file_path = diff_obj.get("file_path")
    diff_content = diff_obj.get("diff_content")

    result = {
        "file_path": file_path,
        "valid": True,
        "errors": [],
        "warnings": [],
        "metadata": {}
    }

    # Check required fields
    if not file_path:
        result["valid"] = False
        result["errors"].append("Missing file_path")
        return result

    if not diff_content:
        result["valid"] = False
        result["errors"].append("Missing diff_content")
        return result

    # Validate file path
    path_validation = validate_file_path(file_path, str(project_path))
    if not path_validation["valid"]:
        result["valid"] = False
        result["errors"].append(f"Invalid file path: {path_validation['error']}")
        return result

    # Check if file exists
    full_path = project_path / file_path
    file_exists = full_path.exists()
    result["metadata"]["file_exists"] = file_exists

    if check_syntax:
        syntax_result = _validate_diff_syntax(diff_content, file_path, full_path)
        if not syntax_result["valid"]:
            result["valid"] = False
            result["errors"].extend(syntax_result["errors"])
        else:
            result["metadata"].update(syntax_result["metadata"])
            result["warnings"].extend(syntax_result.get("warnings", []))

    return result


def _validate_diff_syntax(diff_content: str, file_path: str, full_path: Path) -> dict[str, Any]:
    """Validate the syntax and structure of a diff."""
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "metadata": {}
    }

    lines = diff_content.strip().split('\n')

    if not lines:
        result["valid"] = False
        result["errors"].append("Empty diff content")
        return result

    # Check for unified diff format
    has_file_header = False
    has_hunk_header = False
    hunk_count = 0
    line_changes = {"additions": 0, "deletions": 0, "context": 0}

    current_hunk_old_seen = 0
    current_hunk_new_seen = 0
    in_hunk = False

    for i, line in enumerate(lines):
        # Check for file headers
        if line.startswith('---') or line.startswith('+++'):
            has_file_header = True
            continue

        # Check for hunk headers
        if line.startswith('@@'):
            has_hunk_header = True
            hunk_count += 1
            in_hunk = True

            # Parse hunk header
            hunk_match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if hunk_match:
                int(hunk_match.group(2)) if hunk_match.group(2) else 1
                int(hunk_match.group(4)) if hunk_match.group(4) else 1
                current_hunk_old_seen = 0
                current_hunk_new_seen = 0
            else:
                result["errors"].append(f"Invalid hunk header at line {i+1}: {line}")
                result["valid"] = False
            continue

        # Process hunk content
        if in_hunk and line:
            if line.startswith('-'):
                line_changes["deletions"] += 1
                current_hunk_old_seen += 1
            elif line.startswith('+'):
                line_changes["additions"] += 1
                current_hunk_new_seen += 1
            elif line.startswith(' '):
                line_changes["context"] += 1
                current_hunk_old_seen += 1
                current_hunk_new_seen += 1
            else:
                # Check if it's a context line without the space prefix (common variation)
                if not line.startswith('\\'):  # Ignore "\ No newline at end of file"
                    result["warnings"].append(f"Unusual line format at line {i+1}: {line[:50]}...")

    # Validate basic diff structure
    if not has_file_header:
        result["valid"] = False
        result["errors"].append("No file headers found - not a valid unified diff (missing --- and +++ lines)")

    if not has_hunk_header:
        result["valid"] = False
        result["errors"].append("No hunk headers found - not a valid unified diff")

    # Check if source file exists and content matches (if file exists)
    if full_path.exists():
        try:
            with open(full_path, encoding='utf-8') as f:
                current_content = f.read()

            # Basic check: ensure the diff seems applicable
            original_lines = current_content.splitlines()
            result["metadata"]["source_lines"] = len(original_lines)

            # Check if any context lines from the diff exist in the source
            context_lines_found = 0
            context_lines_total = 0

            for line in lines:
                if line.startswith(' '):  # Context line
                    context_lines_total += 1
                    context_line = line[1:]
                    if context_line in original_lines:
                        context_lines_found += 1

            if context_lines_total > 0:
                context_match_ratio = context_lines_found / context_lines_total
                result["metadata"]["context_match_ratio"] = context_match_ratio

                if context_match_ratio < 0.5:
                    result["warnings"].append(
                        f"Low context match ratio ({context_match_ratio:.2f}) - diff may not apply cleanly"
                    )

        except Exception as e:
            result["warnings"].append(f"Could not read source file for validation: {str(e)}")
    else:
        # File doesn't exist - check if this is a new file creation
        if line_changes["deletions"] > 0:
            result["errors"].append("Diff contains deletions but target file doesn't exist")
            result["valid"] = False
        else:
            result["metadata"]["new_file"] = True

    # Store metadata
    result["metadata"].update({
        "hunk_count": hunk_count,
        "additions": line_changes["additions"],
        "deletions": line_changes["deletions"],
        "context_lines": line_changes["context"],
        "net_change": line_changes["additions"] - line_changes["deletions"]
    })

    return result


def _check_diff_conflicts(diffs: list[dict[str, Any]], project_path: Path) -> dict[str, Any]:
    """Check for conflicts between multiple diffs."""
    conflicts = []

    # Group diffs by file
    files_to_diffs = {}
    for i, diff_obj in enumerate(diffs):
        file_path = diff_obj.get("file_path")
        if file_path:
            if file_path not in files_to_diffs:
                files_to_diffs[file_path] = []
            files_to_diffs[file_path].append((i, diff_obj))

    # Check for multiple diffs affecting the same file
    for file_path, file_diffs in files_to_diffs.items():
        if len(file_diffs) > 1:
            conflicts.append({
                "type": "multiple_diffs_same_file",
                "file_path": file_path,
                "diff_indices": [idx for idx, _ in file_diffs],
                "description": f"Multiple diffs target the same file: {file_path}"
            })

    # Additional conflict checks could be added here:
    # - Line overlap detection
    # - Dependency conflicts
    # - Semantic conflicts

    return {"conflicts": conflicts}
