"""Tests for pagination utility functionality."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aromcp.utils.pagination import (
    ListPaginator,
    TokenEstimator,
    create_paginator,
    paginate_list,
)


class TestTokenEstimator:
    """Test token estimation functionality."""

    def test_estimate_simple_data(self):
        """Test token estimation for simple data structures."""
        estimator = TokenEstimator()

        # Simple string
        tokens = estimator.estimate_tokens("hello world")
        assert tokens > 0

        # List of strings
        data = ["item1", "item2", "item3"]
        tokens = estimator.estimate_tokens(data)
        assert tokens > len(data)  # Should account for JSON structure

        # Dictionary
        data = {"key1": "value1", "key2": "value2"}
        tokens = estimator.estimate_tokens(data)
        assert tokens > 0

    def test_estimate_complex_data(self):
        """Test token estimation for complex nested structures."""
        estimator = TokenEstimator()

        complex_data = {
            "items": [
                {"id": 1, "name": "test", "data": {"nested": "value"}},
                {"id": 2, "name": "test2", "data": {"nested": "value2"}}
            ],
            "metadata": {"total": 2, "page": 1}
        }

        tokens = estimator.estimate_tokens(complex_data)
        assert tokens > 20  # Should be reasonable for this structure


class TestListPaginator:
    """Test list pagination functionality."""

    def test_empty_list_pagination(self):
        """Test pagination with empty list."""
        paginator = ListPaginator(max_tokens=1000)
        result = paginator.paginate([])

        assert result.items == []
        assert result.pagination.total_items == 0
        assert result.pagination.total_pages == 1
        assert result.pagination.page == 1
        assert not result.pagination.has_next
        assert not result.pagination.has_previous

    def test_single_page_pagination(self):
        """Test pagination with data that fits in one page."""
        items = [f"item_{i}" for i in range(10)]
        paginator = ListPaginator(max_tokens=20000)  # Large enough for all items

        result = paginator.paginate(items)

        assert len(result.items) == 10
        assert result.pagination.total_items == 10
        assert result.pagination.total_pages == 1
        assert result.pagination.page == 1
        assert not result.pagination.has_next
        assert not result.pagination.has_previous

    def test_multi_page_pagination(self):
        """Test pagination with data that requires multiple pages."""
        # Create items with substantial content to trigger pagination
        items = [{"id": i, "data": f"{'x' * 100}"} for i in range(50)]
        paginator = ListPaginator(max_tokens=1000)  # Small limit to force pagination

        # Test first page
        result = paginator.paginate(items, page=1)

        assert len(result.items) < 50  # Should be paginated
        assert result.pagination.total_items == 50
        assert result.pagination.total_pages > 1
        assert result.pagination.page == 1
        assert result.pagination.has_next
        assert not result.pagination.has_previous

        # Test second page
        result = paginator.paginate(items, page=2)

        assert result.pagination.page == 2
        assert not result.pagination.has_next or result.pagination.total_pages > 2
        assert result.pagination.has_previous

    def test_deterministic_sorting(self):
        """Test that pagination returns items in deterministic order."""
        items = [{"name": f"item_{i}", "value": i} for i in [3, 1, 4, 1, 5, 9, 2, 6]]
        paginator = ListPaginator(max_tokens=20000, sort_key=lambda x: x["value"])

        result1 = paginator.paginate(items, page=1)
        result2 = paginator.paginate(items, page=1)

        # Results should be identical
        assert result1.items == result2.items

        # Should be sorted by value
        values = [item["value"] for item in result1.items]
        assert values == sorted(values)

    def test_custom_sort_key(self):
        """Test pagination with custom sort key."""
        items = [
            {"file": "b.py", "line": 2},
            {"file": "a.py", "line": 1},
            {"file": "b.py", "line": 1},
            {"file": "a.py", "line": 2}
        ]

        paginator = ListPaginator(
            max_tokens=20000,
            sort_key=lambda x: (x["file"], x["line"])
        )

        result = paginator.paginate(items)

        # Should be sorted by file, then line
        expected_order = [
            {"file": "a.py", "line": 1},
            {"file": "a.py", "line": 2},
            {"file": "b.py", "line": 1},
            {"file": "b.py", "line": 2}
        ]

        assert result.items == expected_order

    def test_page_bounds(self):
        """Test pagination with invalid page numbers."""
        items = [f"item_{i}" for i in range(10)]
        paginator = ListPaginator(max_tokens=20000)

        # Page 0 should be treated as page 1
        result = paginator.paginate(items, page=0)
        assert result.pagination.page == 1

        # Page beyond available should return last page
        result = paginator.paginate(items, page=999)
        assert result.pagination.page == result.pagination.total_pages


class TestPaginateListFunction:
    """Test the convenience paginate_list function."""

    def test_basic_pagination(self):
        """Test basic usage of paginate_list function."""
        items = [{"id": i, "name": f"item_{i}"} for i in range(20)]

        result = paginate_list(
            items=items,
            page=1,
            max_tokens=1000,
            sort_key=lambda x: x["id"],
            metadata={"source": "test"}
        )

        assert "data" in result
        assert "items" in result["data"]
        assert "pagination" in result["data"]
        assert result["data"]["source"] == "test"

        # Should have pagination info
        pagination = result["data"]["pagination"]
        assert "page" in pagination
        assert "total_items" in pagination
        assert "total_pages" in pagination
        assert "has_next" in pagination
        assert "has_previous" in pagination
        assert "estimated_tokens" in pagination
        assert "max_tokens" in pagination

    def test_metadata_inclusion(self):
        """Test that metadata is properly included in response."""
        items = ["item1", "item2", "item3"]
        metadata = {
            "summary": {"total": 3, "processed": 3},
            "extra_info": "test data"
        }

        result = paginate_list(items, metadata=metadata)

        assert result["data"]["summary"] == metadata["summary"]
        assert result["data"]["extra_info"] == metadata["extra_info"]


class TestCreatePaginator:
    """Test the paginator factory function."""

    def test_create_paginator_defaults(self):
        """Test creating paginator with default settings."""
        paginator = create_paginator()

        assert paginator.max_tokens == 20000
        assert paginator.min_items_per_page == 1
        assert paginator.sort_key is None

    def test_create_paginator_custom(self):
        """Test creating paginator with custom settings."""
        def sort_key(x):
            return x["name"]
        paginator = create_paginator(
            max_tokens=10000,
            sort_key=sort_key,
            min_items_per_page=5
        )

        assert paginator.max_tokens == 10000
        assert paginator.min_items_per_page == 5
        assert paginator.sort_key == sort_key


if __name__ == "__main__":
    pytest.main([__file__])
