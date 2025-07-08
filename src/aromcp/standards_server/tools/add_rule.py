"""Add a single ESLint rule to a standard."""

import logging
from typing import Any

from ...filesystem_server._security import get_project_root
from .._storage import build_index, get_eslint_dir, load_manifest
from .hints_for_file import invalidate_index_cache

logger = logging.getLogger(__name__)


def add_rule_impl(
    standard_id: str,
    rule_name: str,
    rule_content: str,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    Add a single ESLint rule to a standard.

    Args:
        standard_id: ID of the standard to add the rule to
        rule_name: Name of the ESLint rule (without .js extension)
        rule_content: JavaScript content of the ESLint rule
        project_root: Project root directory

    Returns:
        Dict with success status and rule info
    """
    try:
        project_root = get_project_root(project_root)

        # Validate that the standard exists
        manifest = load_manifest(project_root)
        if standard_id not in manifest.get("standards", {}):
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Standard {standard_id} not found"
                }
            }

        # Validate rule name
        if not rule_name or not rule_name.replace('-', '').replace('_', '').isalnum():
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Rule name must be alphanumeric with hyphens or underscores"
                }
            }

        # Validate rule content
        if not rule_content or not rule_content.strip():
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "Rule content cannot be empty"
                }
            }

        # Get the ESLint rules directory
        eslint_dir = get_eslint_dir(project_root)
        rules_dir = eslint_dir / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)

        # Create rule filename with standard_id prefix
        rule_filename = f"{standard_id}-{rule_name}.js"
        rule_file = rules_dir / rule_filename

        # Write the rule file
        with open(rule_file, 'w', encoding='utf-8') as f:
            f.write(rule_content)

        logger.info(f"Added ESLint rule {rule_name} to standard {standard_id}")

        # Rebuild index and invalidate cache
        build_index(project_root)
        invalidate_index_cache()

        return {
            "data": {
                "standardId": standard_id,
                "ruleName": rule_name,
                "ruleFile": str(rule_file),
                "ruleSize": len(rule_content)
            }
        }

    except Exception as e:
        logger.error(f"Error in add_rule_impl: {e}")
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to add rule: {str(e)}"
            }
        }


def list_rules_impl(
    standard_id: str,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    List ESLint rules for a standard.

    Args:
        standard_id: ID of the standard
        project_root: Project root directory

    Returns:
        Dict with list of rules
    """
    try:
        project_root = get_project_root(project_root)

        # Validate that the standard exists
        manifest = load_manifest(project_root)
        if standard_id not in manifest.get("standards", {}):
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Standard {standard_id} not found"
                }
            }

        # Get the ESLint rules directory
        eslint_dir = get_eslint_dir(project_root)
        rules_dir = eslint_dir / "rules"

        if not rules_dir.exists():
            return {
                "data": {
                    "standardId": standard_id,
                    "rules": []
                }
            }

        # Find rules for this standard
        rules = []
        for rule_file in rules_dir.glob(f"{standard_id}-*.js"):
            rule_name = rule_file.stem.replace(f"{standard_id}-", "")
            rules.append({
                "ruleName": rule_name,
                "ruleFile": str(rule_file),
                "ruleSize": rule_file.stat().st_size
            })

        return {
            "data": {
                "standardId": standard_id,
                "rules": rules
            }
        }

    except Exception as e:
        logger.error(f"Error in list_rules_impl: {e}")
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to list rules: {str(e)}"
            }
        }
