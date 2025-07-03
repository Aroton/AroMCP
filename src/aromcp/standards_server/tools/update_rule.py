"""Store AI hints and ESLint rules for a standard."""

from typing import Any

from ...filesystem_server._security import get_project_root
from .._storage import (
    build_index,
    clear_ai_hints,
    load_standard_metadata,
    save_ai_hints,
    save_eslint_rules,
)
from .hints_for_file import invalidate_index_cache


def update_rule_impl(
    standard_id: str,
    clear_existing: bool = False,
    ai_hints: list[dict[str, Any]] | None = None,
    eslint_rules: dict[str, Any] | None = None,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    Stores AI hints and ESLint rules for a standard.
    
    Args:
        standard_id: ID of the standard to update
        clear_existing: Whether to clear existing hints before adding new ones
        ai_hints: List of AI hints to store
        eslint_rules: ESLint rules configuration to store
        project_root: Project root directory
        
    Returns:
        Dict with operation results
    """
    try:
        if project_root is None:
            project_root = get_project_root()

        # Validate standard ID
        if not standard_id or not isinstance(standard_id, str):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "standardId must be a non-empty string"
                }
            }

        # Check if standard exists
        metadata = load_standard_metadata(standard_id, project_root)
        if not metadata:
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Standard '{standard_id}' not found. Register it first."
                }
            }

        results = {
            "hintsUpdated": 0,
            "eslintUpdated": False,
            "clearedExisting": False
        }

        # Clear existing hints if requested
        if clear_existing:
            cleared_count = clear_ai_hints(standard_id, project_root)
            results["clearedExisting"] = True
            results["clearedCount"] = cleared_count

        # Save AI hints
        if ai_hints:
            # Validate hint structure
            for i, hint in enumerate(ai_hints):
                required_hint_fields = ["rule", "context", "correctExample", "incorrectExample"]
                for field in required_hint_fields:
                    if field not in hint:
                        return {
                            "error": {
                                "code": "INVALID_INPUT",
                                "message": f"Hint {i+1} missing required field: {field}"
                            }
                        }

                # Set default hasEslintRule if not provided
                if "hasEslintRule" not in hint:
                    hint["hasEslintRule"] = False

            # Save hints
            hint_count = save_ai_hints(standard_id, ai_hints, project_root)
            results["hintsUpdated"] = hint_count

        # Save ESLint rules
        if eslint_rules:
            # Validate ESLint rules structure
            if not isinstance(eslint_rules, dict):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "eslintRules must be an object"
                    }
                }

            # Ensure rules key exists
            if "rules" not in eslint_rules:
                eslint_rules = {"rules": eslint_rules}

            save_eslint_rules(standard_id, eslint_rules, project_root)
            results["eslintUpdated"] = True

        # Rebuild index to reflect changes and invalidate cache
        build_index(project_root)
        invalidate_index_cache()

        return {
            "data": results
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to update rules: {str(e)}"
            }
        }
