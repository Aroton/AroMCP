"""Check for standards that need updating."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path_legacy
from .._storage import find_markdown_files, load_manifest


def _has_valid_yaml_header(file_path: str) -> bool:
    """
    Check if a markdown file has a valid YAML header with at least an 'id' field.

    Args:
        file_path: Path to the markdown file

    Returns:
        True if the file has a valid YAML header with an id field
    """
    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        # Check for YAML frontmatter (starts with --- and ends with ---)
        yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(yaml_pattern, content, re.DOTALL)

        if not match:
            return False

        yaml_content = match.group(1)

        # Check for id field (simple regex to find id: followed by any value)
        id_pattern = r'^\s*id\s*:\s*.+$'
        has_id = bool(re.search(id_pattern, yaml_content, re.MULTILINE))

        return has_id

    except (OSError, UnicodeDecodeError):
        return False


def check_updates_impl(
    standards_path: str, project_root: str | None = None
) -> dict[str, Any]:
    """
    Scans for new or modified standard files.

    Args:
        standards_path: Root folder containing .md files
        project_root: Project root directory

    Returns:
        Dict with needsUpdate list and upToDate count
    """
    try:
        if project_root is None:
            project_root = get_project_root()

        # Validate standards path
        from pathlib import Path
        validate_file_path_legacy(standards_path, Path(project_root))

        # Find all markdown files
        md_files = find_markdown_files(standards_path, project_root)

        # Filter files to only include those with valid YAML headers
        valid_md_files = []
        for md_file in md_files:
            if _has_valid_yaml_header(md_file["absolutePath"]):
                valid_md_files.append(md_file)

        # Load existing manifest
        manifest = load_manifest(project_root)
        tracked_standards = manifest.get("standards", {})

        needs_update = []
        up_to_date_count = 0

        # Check each valid markdown file
        for md_file in valid_md_files:
            file_path = md_file["path"]
            last_modified = md_file["lastModified"]

            # Generate standard ID from relative path
            standard_id = _generate_standard_id(file_path, standards_path)

            # Check if this is new or modified
            if standard_id not in tracked_standards:
                needs_update.append({
                    "standardId": standard_id,
                    "sourcePath": file_path,
                    "reason": "new",
                    "lastModified": last_modified
                })
            else:
                tracked_modified = tracked_standards[standard_id].get(
                    "lastModified", ""
                )
                if last_modified > tracked_modified:
                    needs_update.append({
                        "standardId": standard_id,
                        "sourcePath": file_path,
                        "reason": "modified",
                        "lastModified": last_modified
                    })
                else:
                    up_to_date_count += 1

        # Check for deleted files
        current_files_set = {
            _generate_standard_id(f["path"], standards_path)
            for f in valid_md_files
        }
        for standard_id in tracked_standards:
            if standard_id not in current_files_set:
                needs_update.append({
                    "standardId": standard_id,
                    "sourcePath": tracked_standards[standard_id].get("sourcePath", ""),
                    "reason": "deleted",
                    "lastModified": datetime.now().isoformat()
                })

        return {
            "data": {
                "needsUpdate": needs_update,
                "upToDate": up_to_date_count
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to check for updates: {str(e)}"
            }
        }


def _generate_standard_id(file_path: str, standards_path: str) -> str:
    """Generate a standard ID from file path."""
    # Remove standards_path prefix and .md extension
    relative_path = Path(file_path)
    if standards_path in str(relative_path):
        # Remove the standards path part
        parts = relative_path.parts
        standards_parts = Path(standards_path).parts
        if len(parts) > len(standards_parts):
            relative_parts = parts[len(standards_parts):]
            relative_path = Path(*relative_parts)

    # Remove .md extension and convert to ID
    stem = relative_path.with_suffix("")
    return str(stem).replace("/", "-").replace("\\", "-").lower()
