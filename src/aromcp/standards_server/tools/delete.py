"""Delete a standard and all its associated data."""

from typing import Any

from ...filesystem_server._security import get_project_root
from .._storage import build_index, delete_standard
from .hints_for_file import invalidate_index_cache


def delete_impl(standard_id: str, project_root: str | None = None) -> dict[str, Any]:
    """
    Removes all rules and hints for a standard.

    Args:
        standard_id: ID of the standard to delete
        project_root: Project root directory

    Returns:
        Dict with deletion summary
    """
    try:
        project_root = get_project_root(project_root)

        # Validate standard ID
        if not standard_id or not isinstance(standard_id, str):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "standardId must be a non-empty string"
                }
            }

        # Delete the standard and get summary
        deletion_summary = delete_standard(standard_id, project_root)

        # Rebuild index and invalidate cache
        build_index(project_root)
        invalidate_index_cache()

        return {
            "data": {
                "deleted": deletion_summary
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to delete standard: {str(e)}"
            }
        }
