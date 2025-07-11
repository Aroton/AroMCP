"""Relevance scoring utilities for standards management."""

import fnmatch
from pathlib import Path
from typing import Any


def score_relevance(metadata: dict[str, Any], file_path: str) -> float:
    """
    Calculate relevance score for a standard against a file path.
    Based on the algorithm in the design document.
    """
    parts = Path(file_path).parts
    folders = parts[:-1] if len(parts) > 1 else []
    file_name = parts[-1] if parts else ""

    category = metadata.get("category", "").lower()
    tags = [tag.lower() for tag in metadata.get("tags", [])]
    applies_to = metadata.get("appliesTo", [])
    priority = metadata.get("priority", "recommended")

    score = 0.0

    # Exact folder match: 1.0
    if category and any(folder.lower() == category for folder in folders):
        score = 1.0
    elif tags and any(tag in [folder.lower() for folder in folders] for tag in tags):
        score = 1.0

    # Glob pattern match: 0.8
    elif applies_to and any(_matches_pattern(file_path, pattern) for pattern in applies_to):
        score = 0.8

    # Category in path: 0.6
    elif category and any(category in folder.lower() for folder in folders):
        score = 0.6

    # Tag in path: 0.4
    elif tags and any(
        tag in file_path.lower() or tag in file_name.lower()
        for tag in tags
    ):
        score = 0.4

    # Priority boost
    priority_multiplier = {
        "required": 1.2,
        "important": 1.1,
        "recommended": 1.0
    }

    return score * priority_multiplier.get(priority, 1.0)


def _matches_pattern(file_path: str, pattern: str) -> bool:
    """Check if file path matches a glob pattern."""
    try:
        return fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(Path(file_path).name, pattern)
    except (ValueError, TypeError):
        return False


def select_hints_by_budget(
    hints_with_scores: list[tuple[dict[str, Any], float]],
    max_tokens: int
) -> tuple[list[dict[str, Any]], int]:
    """
    Select hints that fit within the token budget.
    Returns (selected_hints, total_tokens_used).
    """
    # Sort by relevance score (descending), then by priority
    def sort_key(item):
        hint, score = item
        priority_value = {"required": 3, "important": 2, "recommended": 1}
        metadata_priority = hint.get("metadata", {}).get("priority", "recommended")
        return (-score, -priority_value.get(metadata_priority, 1))

    sorted_hints = sorted(hints_with_scores, key=sort_key)

    selected = []
    total_tokens = 0

    for hint, score in sorted_hints:
        tokens_data = hint.get("tokens", _estimate_tokens(hint))
        # Handle TokenCount dict structure
        if isinstance(tokens_data, dict):
            hint_tokens = tokens_data.get("standard", tokens_data.get("full", _estimate_tokens(hint)))
        else:
            hint_tokens = tokens_data

        if total_tokens + hint_tokens <= max_tokens:
            # Add score to response - handle both legacy and enhanced formats
            response_hint = {
                "rule": hint.get("rule", ""),
                "context": hint.get("context", ""),
                "relevanceScore": round(score, 2)
            }

            # Handle examples - support both legacy and enhanced formats
            if "examples" in hint and isinstance(hint["examples"], dict):
                # Enhanced format - extract examples from examples object
                examples = hint["examples"]
                if examples.get("standard"):
                    response_hint["correctExample"] = examples["standard"]
                elif examples.get("full"):
                    response_hint["correctExample"] = examples["full"]
                elif examples.get("minimal"):
                    response_hint["correctExample"] = examples["minimal"]
                else:
                    response_hint["correctExample"] = ""
                
                # Add other example formats if available
                if examples.get("minimal"):
                    response_hint["minimalExample"] = examples["minimal"]
                if examples.get("detailed"):
                    response_hint["detailedExample"] = examples["detailed"]
                
                response_hint["incorrectExample"] = hint.get("incorrectExample", "")
            else:
                # Legacy format - use existing fields
                response_hint["correctExample"] = hint.get("correctExample", "")
                response_hint["incorrectExample"] = hint.get("incorrectExample", "")

            # Include import map if present
            if "importMap" in hint:
                response_hint["importMap"] = hint["importMap"]
            elif "import_map" in hint:
                response_hint["importMap"] = hint["import_map"]

            # Include standard ID if present for reference
            if "standardId" in hint:
                response_hint["standardId"] = hint["standardId"]
            
            # Include other useful fields
            if "has_eslint_rule" in hint:
                response_hint["has_eslint_rule"] = hint["has_eslint_rule"]
            selected.append(response_hint)
            total_tokens += hint_tokens
        else:
            break

    return selected, total_tokens


def _estimate_tokens(hint: dict[str, Any]) -> int:
    """Estimate token count for a hint (4 characters per token)."""
    import json
    hint_json = json.dumps({
        "rule": hint.get("rule", ""),
        "context": hint.get("context", ""),
        "correctExample": hint.get("correctExample", ""),
        "incorrectExample": hint.get("incorrectExample", ""),
    })
    return len(hint_json) // 4


def filter_by_eslint_coverage(hints: list[dict[str, Any]], deprioritize_factor: float = 0.7) -> list[dict[str, Any]]:
    """
    Reduce relevance score for hints that have ESLint rule coverage.
    """
    filtered = []
    for hint in hints:
        if hint.get("has_eslint_rule", False):
            # Reduce relevance score for ESLint-covered rules
            if "relevanceScore" in hint:
                hint["relevanceScore"] *= deprioritize_factor
        filtered.append(hint)

    return filtered
