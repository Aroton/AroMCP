"""Tests for pagination utility functionality."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aromcp.utils.pagination import (
    CursorPaginator,
    TokenEstimator,
    simplify_cursor_pagination,
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
                {"id": 2, "name": "test2", "data": {"nested": "value2"}},
            ],
            "metadata": {"total": 2, "page": 1},
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
            {"file": "a.py", "line": 2},
        ]

        paginator = ListPaginator(max_tokens=20000, sort_key=lambda x: (x["file"], x["line"]))

        result = paginator.paginate(items)

        # Should be sorted by file, then line
        expected_order = [
            {"file": "a.py", "line": 1},
            {"file": "a.py", "line": 2},
            {"file": "b.py", "line": 1},
            {"file": "b.py", "line": 2},
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
            items=items, page=1, max_tokens=1000, sort_key=lambda x: x["id"], metadata={"source": "test"}
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
        metadata = {"summary": {"total": 3, "processed": 3}, "extra_info": "test data"}

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

        paginator = create_paginator(max_tokens=10000, sort_key=sort_key, min_items_per_page=5)

        assert paginator.max_tokens == 10000
        assert paginator.min_items_per_page == 5
        assert paginator.sort_key == sort_key


class TestSimplifyPagination:
    """Test the simplify_pagination function for consistency bugs."""

    def test_pagination_consistency_bug(self):
        """Test that reproduces the has_more=true but total_pages=1 inconsistency bug.
        
        This test reproduces the exact scenario from the bug report:
        - Response shows: "page": 1, "total_pages": 1, "total_files": 21, "has_more": true
        - This is logically inconsistent - if has_more=true, total_pages should be > 1
        """
        # Create 21 items with enough content to trigger pagination
        items = [{"file": f"file_{i:02d}.py", "content": f"{'x' * 50}"} for i in range(21)]
        
        # Use a small max_tokens to force pagination
        result = simplify_pagination(
            items=items,
            page=1,
            max_tokens=1000,  # Small enough to require multiple pages
            sort_key=lambda x: x["file"],
            metadata={"total_files": 21}
        )
        
        # Bug reproduction: The current implementation returns inconsistent values
        # If we're on page 1 and has_more=True, then total_pages MUST be > 1
        if result.get("has_more") is True:
            # This assertion should pass but currently fails due to the bug
            # The simplify_pagination function doesn't include total_pages in output
            # but if it did, it should be consistent with has_more
            
            # For now, let's verify we have the bug:
            # has_more=True means there are more pages, so we should have more than 10 total items
            # and we should be on page 1
            assert result["page"] == 1
            assert result["has_more"] is True
            assert result["total_files"] == 21  # From metadata
            
            # The bug: simplify_pagination doesn't return total_pages at all
            # but the underlying logic calculates it correctly
            assert "total_pages" not in result  # This exposes the bug - missing field
            
            # Let's also verify the bug by calling the underlying paginator directly
            from aromcp.utils.pagination import create_paginator
            paginator = create_paginator(max_tokens=1000, sort_key=lambda x: x["file"])
            full_response = paginator.paginate(items, page=1, metadata={"total_files": 21})
            
            # The full response should have consistent values
            assert full_response.pagination.has_next is True
            assert full_response.pagination.total_pages > 1  # This should be true
            
            # But the simplified version loses this information, creating inconsistency
            # This is the root cause of the bug
    
    def test_pagination_consistency_fix(self):
        """Test that verifies the fixed behavior - has_more and total_pages should be consistent.
        
        This test should FAIL before the fix and PASS after the fix.
        """
        # Create 21 items with enough content to trigger pagination
        items = [{"file": f"file_{i:02d}.py", "content": f"{'x' * 500}"} for i in range(21)]
        
        # Use a small max_tokens to force pagination
        result = simplify_pagination(
            items=items,
            page=1,
            max_tokens=1000,  # Small enough to require multiple pages
            sort_key=lambda x: x["file"],
            metadata={"total_files": 21}
        )
        
        # After the fix, these should be consistent:
        if result.get("has_more") is True:
            # If has_more is True, we should have total_pages information
            # and it should be > 1 (indicating multiple pages exist)
            assert "total_pages" in result, "total_pages should be included when has_more=True"
            assert result["total_pages"] > 1, f"total_pages should be > 1 when has_more=True, got {result.get('total_pages')}"
            assert result["page"] == 1, "Should be on page 1"
        
        # Test consistency from the other direction
        if result.get("total_pages", 1) > 1:
            # If there are multiple pages and we're on page 1, has_more should be True
            if result["page"] == 1:
                assert result.get("has_more") is True, "has_more should be True when on page 1 of multiple pages"


if __name__ == "__main__":
    pytest.main([__file__])
