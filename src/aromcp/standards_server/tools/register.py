"""Register a standard with metadata."""

from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path_legacy
from .._storage import build_index, load_manifest, save_manifest, save_standard_metadata
from .hints_for_file import invalidate_index_cache


def register_impl(source_path: str, metadata: dict[str, Any] | str, project_root: str | None = None) -> dict[str, Any]:
    """
    Registers a standard with metadata after AI parsing.
    
    Args:
        source_path: Path to the source markdown file
        metadata: Standard metadata with required fields
        project_root: Project root directory
        
    Returns:
        Dict with standardId and isNew flag
    """
    try:
        if project_root is None:
            project_root = get_project_root()

        # Validate source path
        from pathlib import Path
        validate_file_path_legacy(source_path, Path(project_root))

        # Parse metadata if it's a string
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Invalid JSON in metadata: {str(e)}"
                    }
                }

        # Validate required metadata fields
        required_fields = ["id", "name", "category", "tags", "appliesTo", "severity", "priority"]
        for field in required_fields:
            if field not in metadata:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Missing required metadata field: {field}"
                    }
                }

        # Validate enum values
        valid_severities = ["error", "warning", "info"]
        valid_priorities = ["required", "important", "recommended"]

        if metadata["severity"] not in valid_severities:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Invalid severity. Must be one of: {valid_severities}"
                }
            }

        if metadata["priority"] not in valid_priorities:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"Invalid priority. Must be one of: {valid_priorities}"
                }
            }

        # Validate arrays
        if not isinstance(metadata["tags"], list):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "tags must be an array"
                }
            }

        if not isinstance(metadata["appliesTo"], list):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "appliesTo must be an array"
                }
            }

        standard_id = metadata["id"]

        # Check if this is a new standard
        manifest = load_manifest(project_root)
        is_new = standard_id not in manifest.get("standards", {})

        # Save standard metadata
        save_standard_metadata(standard_id, metadata, project_root)

        # Update manifest
        if "standards" not in manifest:
            manifest["standards"] = {}

        manifest["standards"][standard_id] = {
            "sourcePath": source_path,
            "lastModified": metadata.get("lastModified", ""),
            "registered": True
        }

        save_manifest(manifest, project_root)

        # Rebuild index and invalidate cache
        build_index(project_root)
        invalidate_index_cache()

        return {
            "data": {
                "standardId": standard_id,
                "isNew": is_new
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to register standard: {str(e)}"
            }
        }
