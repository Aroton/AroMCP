"""Update ESLint rules for a standard."""

from typing import Any

from ...filesystem_server._security import get_project_root
from .._storage import (
    build_index,
    load_standard_metadata,
    update_eslint_config,
)
from .hints_for_file import invalidate_index_cache


def _validate_eslint_rule_content(content: str) -> bool:
    """
    Validate that content is a proper module.exports ESLint rule.

    Args:
        content: JavaScript content to validate

    Returns:
        True if content is a valid ESLint rule, False otherwise
    """
    import re

    # Remove comments and normalize whitespace for parsing
    content_normalized = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content_normalized = re.sub(r'/\*.*?\*/', '', content_normalized, flags=re.DOTALL)
    content_normalized = re.sub(r'\s+', ' ', content_normalized).strip()

    # Must start with module.exports
    if not re.search(r'module\.exports\s*=', content_normalized):
        return False

    # Must have meta property
    if not re.search(r'meta\s*:', content_normalized):
        return False

    # Must have create property (function) - handles both create: and create(context)
    if not re.search(r'create\s*[\(:]', content_normalized):
        return False

    # Must not contain any configuration objects (those are managed by API)
    forbidden_patterns = [
        r'plugins\s*:',
        r'extends\s*:',
        r'rules\s*:',
        r'env\s*:',
        r'globals\s*:',
        r'parser\s*:',
        r'parserOptions\s*:'
    ]

    for pattern in forbidden_patterns:
        if re.search(pattern, content_normalized):
            return False

    return True


def update_rule_impl(
    standard_id: str,
    eslint_files: dict[str, str] | str,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    Updates ESLint rule files for a standard.

    Args:
        standard_id: ID of the standard to update
        eslint_files: Dict of filename -> content for ESLint JavaScript files
        project_root: Project root directory

    Returns:
        Dict with operation results
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

        # Check if standard exists
        metadata = load_standard_metadata(standard_id, project_root)
        if not metadata:
            return {
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Standard '{standard_id}' not found. Register it first."
                }
            }

        # Validate eslint_files parameter
        if not eslint_files:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "eslint_files is required"
                }
            }

        # Parse eslint_files if it's a string
        if isinstance(eslint_files, str):
            import json
            try:
                eslint_files = json.loads(eslint_files)
            except json.JSONDecodeError as e:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Invalid JSON in eslint_files: {str(e)}"
                    }
                }

        # Validate ESLint files structure
        if not isinstance(eslint_files, dict):
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "eslintFiles must be an object with filename -> content mapping"
                }
            }

        from pathlib import Path

        # Write each ESLint file
        eslint_dir = Path(project_root) / ".aromcp" / "eslint"
        eslint_dir.mkdir(parents=True, exist_ok=True)

        files_written = 0
        for filename, content in eslint_files.items():
            if not isinstance(content, str):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Content for file '{filename}' must be a string"
                    }
                }

            # Enhanced filename validation
            if ".." in filename or filename.startswith("/"):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Invalid filename: {filename}"
                    }
                }

            # Validate filename restrictions
            filename_lower = filename.lower()
            if "config" in filename_lower:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": (
                            f"ESLint rule files cannot contain 'config' in filename: {filename}. "
                            "Configuration files are managed by the API."
                        )
                    }
                }

            # Check if the basename is index (e.g., rules/index.js)
            import os
            basename = os.path.basename(filename_lower)
            if basename.startswith("index"):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": (
                            f"ESLint rule files cannot be named 'index': {filename}. "
                            "Index files are managed by the API."
                        )
                    }
                }

            # Validate file must be in rules/ directory
            if not filename.startswith("rules/") or not filename.endswith(".js"):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"ESLint files must be in 'rules/' directory and end with '.js': {filename}"
                    }
                }

            # Validate content is a module.exports ESLint rule
            if not _validate_eslint_rule_content(content):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": (
                            f"File '{filename}' must contain a valid module.exports ESLint rule "
                            "with meta and create properties"
                        )
                    }
                }

            file_path = eslint_dir / filename
            # Create subdirectories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            files_written += 1

        # Update ESLint configuration files after writing rules
        update_eslint_config(project_root)

        # Rebuild index to reflect changes and invalidate cache
        build_index(project_root)
        invalidate_index_cache()

        return {
            "data": {
                "eslintFilesWritten": files_written,
                "eslintUpdated": True,
                "standard_id": standard_id
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to update ESLint rules: {str(e)}"
            }
        }
