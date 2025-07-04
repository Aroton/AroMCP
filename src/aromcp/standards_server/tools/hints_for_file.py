"""Get relevant hints for a specific file with relevance scoring."""

import time
from typing import Any

from ...filesystem_server._security import get_project_root, validate_file_path_legacy
from .._scoring import score_relevance, select_hints_by_budget
from .._storage import load_ai_hints, load_index, load_standard_metadata

# Global cache for index data
_index_cache: dict[str, Any] | None = None
_cache_timestamp: float = 0
_cache_ttl: float = 300  # 5 minutes cache TTL


def _get_cached_index(project_root: str | None = None) -> dict[str, Any]:
    """Get index with caching for performance."""
    global _index_cache, _cache_timestamp

    current_time = time.time()

    # Check if cache is valid
    if _index_cache is not None and (current_time - _cache_timestamp) < _cache_ttl:
        return _index_cache

    # Cache miss or expired - reload index
    _index_cache = load_index(project_root)
    _cache_timestamp = current_time

    return _index_cache


def invalidate_index_cache() -> None:
    """Invalidate the index cache to force reload."""
    global _index_cache, _cache_timestamp
    _index_cache = None
    _cache_timestamp = 0


def hints_for_file_impl(
    file_path: str,
    max_tokens: int = 10000,
    project_root: str | None = None
) -> dict[str, Any]:
    """
    Gets relevant hints for a specific file with relevance scoring.

    Args:
        file_path: Path to the file to get hints for
        max_tokens: Maximum tokens to return in response
        project_root: Project root directory

    Returns:
        Dict with hints array and totalTokens
    """
    try:
        project_root = get_project_root(project_root)

        # Validate file path
        from pathlib import Path
        validate_file_path_legacy(file_path, Path(project_root))

        # Validate max_tokens
        if max_tokens <= 0:
            return {
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "maxTokens must be a positive integer"
                }
            }

        # Load the index for fast lookups (with caching)
        index = _get_cached_index(project_root)
        standards = index.get("standards", {})

        if not standards:
            return {
                "data": {
                    "hints": [],
                    "totalTokens": 0
                }
            }

        # Collect all hints with relevance scores
        hints_with_scores: list[tuple[dict[str, Any], float]] = []

        for standard_id in standards.keys():
            # Load metadata for scoring
            metadata = load_standard_metadata(standard_id, project_root)
            if not metadata:
                continue

            # Calculate relevance score
            relevance_score = score_relevance(metadata, file_path)

            # Skip if no relevance
            if relevance_score <= 0:
                continue

            # Load hints for this standard
            hints = load_ai_hints(standard_id, project_root)

            for hint in hints:
                # Add metadata reference for priority sorting and standard ID
                hint["metadata"] = metadata
                hint["standardId"] = standard_id
                hints_with_scores.append((hint, relevance_score))

        # Apply ESLint coverage deprioritization
        deprioritized_hints = []
        for hint, score in hints_with_scores:
            if hint.get("hasEslintRule", False):
                score *= 0.7  # Deprioritize ESLint-covered rules
            deprioritized_hints.append((hint, score))

        # Select hints within token budget
        selected_hints, total_tokens = select_hints_by_budget(
            deprioritized_hints, max_tokens
        )

        # Extract import maps and optimize token usage
        global_import_maps = {}  # Structure: { "module_name": [import_objects] }
        optimized_hints = []

        for _i, hint in enumerate(selected_hints):
            # Extract import map if present
            modules_used = []
            if "importMap" in hint:
                import_map = hint["importMap"]

                # Organize imports by module name
                if import_map:  # Check if import map has entries
                    for import_item in import_map:
                        module_name = import_item.get("module", "")
                        if module_name:
                            if module_name not in global_import_maps:
                                global_import_maps[module_name] = []

                            # Check if this exact import already exists for this module
                            existing_statements = [imp.get("statement", "") for imp in global_import_maps[module_name]]
                            if import_item.get("statement", "") not in existing_statements:
                                # Remove the "type" field before adding to global import maps
                                clean_import = {k: v for k, v in import_item.items() if k != "type"}
                                global_import_maps[module_name].append(clean_import)

                            if module_name not in modules_used:
                                modules_used.append(module_name)

            # Create optimized hint without import map, metadata, and standardId
            optimized_hint = {k: v for k, v in hint.items() if k not in ("importMap", "metadata", "standardId")}

            # Add modules array
            if modules_used:
                optimized_hint["modules"] = sorted(modules_used)  # Sort for consistency

            # Apply import stripping as fallback for existing hints
            from .._storage import _strip_imports_from_code
            if "correctExample" in optimized_hint:
                optimized_hint["correctExample"] = _strip_imports_from_code(optimized_hint["correctExample"])
            if "incorrectExample" in optimized_hint:
                optimized_hint["incorrectExample"] = _strip_imports_from_code(optimized_hint["incorrectExample"])

            optimized_hints.append(optimized_hint)

        return {
            "data": {
                "hints": optimized_hints,
                "totalTokens": total_tokens,
                "importMaps": global_import_maps if global_import_maps else None
            }
        }

    except Exception as e:
        return {
            "error": {
                "code": "OPERATION_FAILED",
                "message": f"Failed to get hints for file: {str(e)}"
            }
        }
