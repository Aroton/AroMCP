"""
Reusable pagination utilities for MCP tools that return lists.

Provides deterministic pagination based on token estimation to keep responses
under 20k tokens while maintaining consistent ordering across identical inputs.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class PaginationInfo:
    """Information about pagination state."""

    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool
    estimated_tokens: int
    max_tokens: int


class TokenEstimator:
    """Estimates token count for JSON responses."""

    # Rough approximation: 1 token ≈ 4 characters for JSON content
    # This accounts for structure overhead and is conservative
    CHARS_PER_TOKEN = 4

    @classmethod
    def estimate_tokens(cls, data: Any) -> int:
        """
        Estimate token count for arbitrary data structures.

        Args:
            data: The data to estimate tokens for

        Returns:
            Estimated token count
        """
        try:
            # Convert to JSON string to get serialized size
            json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            char_count = len(json_str)
            return max(1, char_count // cls.CHARS_PER_TOKEN)
        except (TypeError, ValueError):
            # Fallback for non-serializable data
            return len(str(data)) // cls.CHARS_PER_TOKEN


class PaginatedResponse[T]:
    """Generic paginated response container."""

    def __init__(self, items: list[T], pagination: PaginationInfo, metadata: dict[str, Any] | None = None):
        self.items = items
        self.pagination = pagination
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for MCP responses."""
        return {
            "data": {
                "items": self.items,
                "pagination": {
                    "page": self.pagination.page,
                    "page_size": self.pagination.page_size,
                    "total_items": self.pagination.total_items,
                    "total_pages": self.pagination.total_pages,
                    "has_next": self.pagination.has_next,
                    "has_previous": self.pagination.has_previous,
                    "estimated_tokens": self.pagination.estimated_tokens,
                    "max_tokens": self.pagination.max_tokens,
                },
                **self.metadata,
            }
        }


class ListPaginator[T]:
    """
    Deterministic paginator for lists with token-based sizing.

    Ensures consistent ordering and pagination based on token estimation
    to keep responses under the specified token limit.
    """

    def __init__(
        self, max_tokens: int = 20000, min_items_per_page: int = 1, sort_key: Callable[[T], Any] | None = None
    ):
        """
        Initialize paginator.

        Args:
            max_tokens: Maximum tokens per page (default 20k)
            min_items_per_page: Minimum items per page regardless of token count
            sort_key: Function to extract sort key for deterministic ordering
        """
        self.max_tokens = max_tokens
        self.min_items_per_page = min_items_per_page
        self.sort_key = sort_key
        self.estimator = TokenEstimator()

    def paginate(self, items: list[T], page: int = 1, metadata: dict[str, Any] | None = None) -> PaginatedResponse[T]:
        """
        Paginate a list of items with token-based sizing.

        Args:
            items: List of items to paginate
            page: Page number (1-based)
            metadata: Additional metadata to include in response

        Returns:
            PaginatedResponse with paginated items and metadata
        """
        if not items:
            return self._empty_response(metadata)

        # Ensure deterministic ordering
        sorted_items = self._sort_items(items)

        # Calculate dynamic page sizes based on token estimation
        page_boundaries = self._calculate_page_boundaries(sorted_items)
        total_pages = len(page_boundaries)

        # Validate page number
        page = max(1, min(page, total_pages))

        # Get items for the requested page
        start_idx, end_idx = page_boundaries[page - 1]
        page_items = sorted_items[start_idx:end_idx]

        # Calculate token estimate for this page
        estimated_tokens = self.estimator.estimate_tokens(
            {"items": page_items, "pagination": {"page": page, "total_pages": total_pages}, **(metadata or {})}
        )

        pagination_info = PaginationInfo(
            page=page,
            page_size=len(page_items),
            total_items=len(sorted_items),
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
            estimated_tokens=estimated_tokens,
            max_tokens=self.max_tokens,
        )

        return PaginatedResponse(page_items, pagination_info, metadata)

    def _sort_items(self, items: list[T]) -> list[T]:
        """Sort items deterministically."""
        if self.sort_key:
            return sorted(items, key=self.sort_key)

        # Default sorting based on string representation for deterministic order
        try:
            return sorted(items, key=lambda x: str(x))
        except TypeError:
            # If items aren't comparable, use their string representation
            return sorted(items, key=lambda x: repr(x))

    def _calculate_page_boundaries(self, items: list[T]) -> list[tuple[int, int]]:
        """
        Calculate page boundaries based on token estimation.

        Returns list of (start_idx, end_idx) tuples for each page.
        """
        if not items:
            return [(0, 0)]

        boundaries = []
        current_start = 0

        while current_start < len(items):
            # Find the optimal end index for this page
            end_idx = self._find_page_end(items, current_start)
            boundaries.append((current_start, end_idx))
            current_start = end_idx

        return boundaries

    def _find_page_end(self, items: list[T], start_idx: int) -> int:
        """
        Find the optimal end index for a page starting at start_idx.

        Uses binary search to find the largest subset that fits within token limit.
        """
        total_items = len(items)

        # Ensure minimum items per page
        min_end = min(start_idx + self.min_items_per_page, total_items)

        # Binary search for optimal page size
        left, right = min_end, total_items
        best_end = min_end

        while left <= right:
            mid = (left + right) // 2
            page_items = items[start_idx:mid]

            # Estimate tokens for this page subset
            estimated_tokens = self.estimator.estimate_tokens({"items": page_items, "pagination": {"estimated": True}})

            if estimated_tokens <= self.max_tokens:
                best_end = mid
                left = mid + 1
            else:
                right = mid - 1

        return best_end

    def _empty_response(self, metadata: dict[str, Any] | None) -> PaginatedResponse[T]:
        """Create response for empty lists."""
        pagination_info = PaginationInfo(
            page=1,
            page_size=0,
            total_items=0,
            total_pages=1,
            has_next=False,
            has_previous=False,
            estimated_tokens=self.estimator.estimate_tokens({"items": [], "pagination": {}}),
            max_tokens=self.max_tokens,
        )

        return PaginatedResponse([], pagination_info, metadata)


def create_paginator(
    max_tokens: int = 20000, sort_key: Callable[[Any], Any] | None = None, min_items_per_page: int = 1
) -> ListPaginator:
    """
    Convenience function to create a paginator with common defaults.

    Args:
        max_tokens: Maximum tokens per page
        sort_key: Function to extract sort key for deterministic ordering
        min_items_per_page: Minimum items per page

    Returns:
        Configured ListPaginator instance
    """
    return ListPaginator(max_tokens=max_tokens, min_items_per_page=min_items_per_page, sort_key=sort_key)


def simplify_pagination(
    items: list[Any],
    page: int,
    max_tokens: int,
    sort_key: Callable[[Any], Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Simplified pagination pattern that uses token-based pagination but cleaner output.

    Uses the existing token-based pagination logic but returns simplified metadata.
    For small results, skips pagination entirely.
    For larger results, uses minimal pagination metadata.

    Args:
        items: All items to paginate (not pre-paginated)
        page: Current page number
        max_tokens: Maximum tokens per page
        sort_key: Function to extract sort key for deterministic ordering
        metadata: Additional metadata to include

    Returns:
        Simplified response format with token-based pagination
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
        result = {"items": items}
        if metadata:
            result.update(metadata)
        return result

    # For larger results, use token-based pagination with simplified output
    paginator = create_paginator(max_tokens=max_tokens, sort_key=sort_key)
    response = paginator.paginate(items, page=page, metadata=metadata)
    full_result = response.to_dict()["data"]

    # Simplify the pagination metadata
    pagination_info = full_result["pagination"]
    simplified_result = {
        "items": full_result["items"],
        "page": pagination_info["page"],
        "has_more": pagination_info["has_next"],
        "total": pagination_info["total_items"] if pagination_info["total_items"] < 100 else "100+",
    }

    # Add any additional metadata
    if metadata:
        simplified_result.update(metadata)

    return simplified_result


def paginate_list(
    items: list[Any],
    page: int = 1,
    max_tokens: int = 20000,
    sort_key: Callable[[Any], Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Quick utility function to paginate a list and return MCP-formatted response.

    Args:
        items: List of items to paginate
        page: Page number (1-based)
        max_tokens: Maximum tokens per page
        sort_key: Function to extract sort key for deterministic ordering
        metadata: Additional metadata to include in response

    Returns:
        MCP-formatted response dictionary
    """
    paginator = create_paginator(max_tokens=max_tokens, sort_key=sort_key)
    response = paginator.paginate(items, page=page, metadata=metadata)
    return response.to_dict()
