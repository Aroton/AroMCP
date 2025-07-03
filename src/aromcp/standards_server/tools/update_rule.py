"""Store AI hints and ESLint rules for a standard."""

from typing import Any

from ...filesystem_server._security import get_project_root
from .._storage import (
    build_index,
    clear_ai_hints,
    load_standard_metadata,
    save_ai_hints,
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
    
    # Must have create property (function)
    if not re.search(r'create\s*:', content_normalized):
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
    clear_existing: bool = False,
    ai_hints: list[dict[str, Any]] | str | None = None,
    eslint_files: dict[str, str] | str | None = None,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    Stores AI hints and ESLint files for a standard.
    
    Args:
        standard_id: ID of the standard to update
        clear_existing: Whether to clear existing hints before adding new ones
        ai_hints: List of AI hints to store
        eslint_files: Dict of filename -> content for ESLint JavaScript files
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

        # Parse ai_hints if it's a string
        if isinstance(ai_hints, str):
            import json
            try:
                ai_hints = json.loads(ai_hints)
            except json.JSONDecodeError as e:
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": f"Invalid JSON in ai_hints: {str(e)}"
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

        # Clear existing hints if requested
        if clear_existing:
            cleared_count = clear_ai_hints(standard_id, project_root)
            results["clearedExisting"] = True
            results["clearedCount"] = cleared_count

        # Save AI hints
        if ai_hints:
            # Ensure ai_hints is a list at this point
            if not isinstance(ai_hints, list):
                return {
                    "error": {
                        "code": "INVALID_INPUT",
                        "message": "ai_hints must be a list after JSON parsing"
                    }
                }
            
            # Validate hint structure
            for i, hint in enumerate(ai_hints):
                if not isinstance(hint, dict):
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": f"Hint {i+1} must be an object"
                        }
                    }
                    
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

        # Save ESLint files (JavaScript files)
        if eslint_files:
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
                            "message": f"ESLint rule files cannot contain 'config' in filename: {filename}. Configuration files are managed by the API."
                        }
                    }
                
                if filename_lower.startswith("index"):
                    return {
                        "error": {
                            "code": "INVALID_INPUT",
                            "message": f"ESLint rule files cannot be named 'index': {filename}. Index files are managed by the API."
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
                            "message": f"File '{filename}' must contain a valid module.exports ESLint rule with meta and create properties"
                        }
                    }
                
                file_path = eslint_dir / filename
                # Create subdirectories if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                files_written += 1
            
            results["eslintFilesWritten"] = files_written
            results["eslintUpdated"] = True
            
            # Update ESLint configuration files after writing rules
            update_eslint_config(project_root)

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
