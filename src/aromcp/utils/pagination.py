"""
Reusable cursor-based pagination utilities for MCP tools that return lists.

Provides deterministic pagination based on token estimation to keep responses
under 20k tokens while maintaining consistent ordering across identical inputs.
"""

import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from typing import Any, TypeVar

T = TypeVar("T")


class TokenEstimator:
    """Estimates token count for JSON responses."""

    # More accurate approximation: 1 token ≈ 3.5 characters for JSON content
    # Adding 10% safety margin as requested
    CHARS_PER_TOKEN = 3.5
    SAFETY_MARGIN = 1.1  # 10% safety margin

    @classmethod
    def estimate_tokens(cls, data: Any) -> int:
        """
        Estimate token count for arbitrary data structures.

        Args:
            data: The data to estimate tokens for

        Returns:
            Estimated token count with safety margin
        """
        try:
            # Convert to JSON string to get serialized size
            json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            char_count = len(json_str)
            base_estimate = char_count / cls.CHARS_PER_TOKEN
            # Apply safety margin
            return max(1, int(base_estimate * cls.SAFETY_MARGIN))
        except (TypeError, ValueError):
            # Fallback for non-serializable data
            base_estimate = len(str(data)) / cls.CHARS_PER_TOKEN
            return max(1, int(base_estimate * cls.SAFETY_MARGIN))


def _serialize_for_json(obj: Any) -> Any:
    """Convert objects to JSON-serializable format."""
    if is_dataclass(obj):
        return asdict(obj)
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    else:
        return obj


class CursorPaginator[T]:
    """
    Cursor-based paginator for lists with token-based sizing.

    Provides consistent, reliable pagination using cursors instead of page numbers.
    Builds actual response to determine exact cutoff point and avoids inconsistent
    metadata like has_more=True with total_pages=1.
    """

    def __init__(
        self, max_tokens: int = 20000, min_items_per_page: int = 1, sort_key: Callable[[T], Any] | None = None
    ):
        """
        Initialize cursor paginator.

        Args:
            max_tokens: Maximum tokens per page (default 20k)
            min_items_per_page: Minimum items per page regardless of token count
            sort_key: Function to extract sort key for deterministic ordering
        """
        self.max_tokens = max_tokens
        self.min_items_per_page = min_items_per_page
        self.sort_key = sort_key
        self.estimator = TokenEstimator()

    def paginate(
        self, items: list[T], cursor: str | None = None, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Paginate a list of items using cursor-based pagination.

        Args:
            items: List of items to paginate
            cursor: Start after this item (None for first page)
            metadata: Additional metadata to include in response

        Returns:
            Dict with items, has_more, next_cursor, total, and metadata
        """
        if not items:
            return self._empty_cursor_response(metadata)

        # Ensure deterministic ordering
        sorted_items = self._sort_items(items)

        # Find starting position based on cursor
        start_idx = self._find_cursor_position(sorted_items, cursor)

        if start_idx >= len(sorted_items):
            # Cursor is beyond end of data
            return self._empty_cursor_response(metadata)

        # Find optimal end position using binary search
        end_idx = self._find_optimal_end(sorted_items, start_idx, metadata)

        # Extract page items
        page_items = sorted_items[start_idx:end_idx]

        # Determine next cursor
        next_cursor = None
        has_more = end_idx < len(sorted_items)
        if has_more:
            next_cursor = self._generate_cursor(sorted_items[end_idx - 1])

        # Build response with standardized pagination fields
        response = {
            "items": page_items,
            "total": len(sorted_items),
            "page_size": len(page_items),
            "next_cursor": next_cursor,
            "has_more": has_more,
        }

        # Add metadata
        if metadata:
            response.update(metadata)

        return response

    def _sort_items(self, items: list[T]) -> list[T]:
        """Sort items using the configured sort key."""
        if self.sort_key:
            return sorted(items, key=self.sort_key)
        return items[:]  # Return a copy to avoid modifying the original

    def _empty_cursor_response(self, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create an empty cursor response."""
        response = {"items": [], "total": 0, "page_size": 0, "next_cursor": None, "has_more": False}
        if metadata:
            response.update(metadata)
        return response

    def _find_cursor_position(self, sorted_items: list[T], cursor: str | None) -> int:
        """Find the starting position based on cursor."""
        if cursor is None:
            return 0

        # For simplicity, cursor is the string representation of the last item
        # In a real implementation, you might use a more sophisticated cursor
        for i, item in enumerate(sorted_items):
            if self._generate_cursor(item) == cursor:
                return i + 1  # Start after the cursor item

        # If cursor not found, start from beginning
        return 0

    def _generate_cursor(self, item: T) -> str:
        """Generate a cursor string for an item."""
        if self.sort_key:
            sort_value = self.sort_key(item)
            return str(sort_value)
        return str(item)

    def _find_optimal_end(self, sorted_items: list[T], start_idx: int, metadata: dict[str, Any] | None = None) -> int:
        """Find optimal end index using binary search."""
        total_items = len(sorted_items)

        # Ensure minimum items per page
        min_end = min(start_idx + self.min_items_per_page, total_items)

        # If we're already at or past the end, return the end
        if start_idx >= total_items:
            return total_items

        # Start with a reasonable upper bound
        max_end = total_items

        # Binary search for the optimal end point
        while min_end < max_end:
            mid = (min_end + max_end + 1) // 2
            test_items = sorted_items[start_idx:mid]

            # Build a test response to estimate tokens
            test_response = {"items": test_items}
            if metadata:
                test_response.update(metadata)

            estimated_tokens = self.estimator.estimate_tokens(test_response)

            if estimated_tokens <= self.max_tokens:
                min_end = mid
            else:
                max_end = mid - 1

        return max(min_end, start_idx + 1)  # Ensure at least one item


def simplify_cursor_pagination(
    items: list[Any],
    cursor: str | None = None,
    max_tokens: int = 20000,
    sort_key: Callable[[Any], Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Simplified cursor-based pagination with cleaner output.

    For small results, skips pagination entirely.
    For larger results, uses cursor-based pagination.

    Args:
        items: All items to paginate (not pre-paginated)
        cursor: Start after this cursor (None for first page)
        max_tokens: Maximum tokens per page
        sort_key: Function to extract sort key for deterministic ordering
        metadata: Additional metadata to include

    Returns:
        Simplified response format with cursor-based pagination
    """
    if not items:
        result = {"items": []}
        if metadata:
            result.update(metadata)
        return result

    # For small results, skip pagination entirely
    if len(items) <= 10:
        # Still sort for consistency
        if sort_key:
            items = sorted(items, key=sort_key)
        result = {"items": items, "total": len(items), "page_size": len(items), "next_cursor": None, "has_more": False}
        if metadata:
            result.update(metadata)
        return result

    # For larger results, use cursor-based pagination
    paginator = CursorPaginator(max_tokens=max_tokens, sort_key=sort_key)
    return paginator.paginate(items, cursor=cursor, metadata=metadata)


def auto_paginate_cursor_response(
    response: Any,
    items_field: str,
    cursor: str | None = None,
    max_tokens: int = 20000,
    sort_key: Callable[[Any], Any] | None = None,
) -> Any:
    """
    Apply cursor-based auto-pagination to any response with an items field.

    Args:
        response: Response object (dataclass or dict) containing items
        items_field: Name of the field containing the list of items
        cursor: Cursor for pagination (None for first page)
        max_tokens: Maximum tokens per response
        sort_key: Function to extract sort key for deterministic ordering

    Returns:
        Response object with cursor-based pagination applied
    """
    # Convert response to dict if it's a dataclass
    if is_dataclass(response):
        response_dict = asdict(response)
    else:
        response_dict = dict(response)

    # Extract items
    items = response_dict.get(items_field, [])

    # Build metadata from all fields except items and pagination fields
    pagination_fields = {"total", "page_size", "next_cursor", "has_more"}
    metadata = {k: v for k, v in response_dict.items() if k != items_field and k not in pagination_fields}

    # Apply cursor pagination
    paginated_result = simplify_cursor_pagination(
        items=items, cursor=cursor, max_tokens=max_tokens, sort_key=sort_key, metadata=metadata
    )

    # Update the items field with paginated items
    response_dict[items_field] = paginated_result["items"]

    # Always set standardized cursor pagination fields
    response_dict["total"] = paginated_result.get("total", 0)
    response_dict["page_size"] = paginated_result.get("page_size", None)
    response_dict["next_cursor"] = paginated_result.get("next_cursor", None)
    response_dict["has_more"] = paginated_result.get("has_more", False)

    # Return original type if it was a dataclass
    if is_dataclass(response):
        return type(response)(**response_dict)
    else:
        return response_dict
