"""Tests for cursor-based pagination functionality."""

from aromcp.utils.pagination import CursorPaginator, simplify_cursor_pagination


class TestCursorPaginator:
    """Test the CursorPaginator class."""

    def test_empty_list(self):
        """Test pagination with empty list."""
        paginator = CursorPaginator(max_tokens=1000)
        result = paginator.paginate([])

        assert result["items"] == []
        assert result["has_more"] is False
        assert result["next_cursor"] is None
        assert result["total"] == 0

    def test_small_list_fits_in_one_page(self):
        """Test pagination when all items fit in one page."""
        items = ["a.py", "b.py", "c.py"]
        paginator = CursorPaginator(max_tokens=10000)
        result = paginator.paginate(items)

        assert result["items"] == ["a.py", "b.py", "c.py"]
        assert result["has_more"] is False
        assert result["next_cursor"] is None
        assert result["total"] == 3

    def test_cursor_pagination_consistency(self):
        """Test that cursor pagination provides consistent results."""
        items = [f"file_{i:03d}_with_much_longer_filename_to_force_pagination.py" for i in range(50)]  # 50 files
        paginator = CursorPaginator(max_tokens=500, sort_key=lambda x: x)

        # Get first page
        page1 = paginator.paginate(items)
        assert page1["has_more"] is True
        assert page1["next_cursor"] is not None
        assert len(page1["items"]) > 0

        # Get second page using cursor
        page2 = paginator.paginate(items, cursor=page1["next_cursor"])

        # Verify no overlap
        page1_files = set(page1["items"])
        page2_files = set(page2["items"])
        assert len(page1_files.intersection(page2_files)) == 0

        # Verify continuation
        last_item_page1 = page1["items"][-1]
        first_item_page2 = page2["items"][0]
        assert last_item_page1 < first_item_page2  # Should be in order

    def test_cursor_navigation_through_all_pages(self):
        """Test navigating through all pages using cursors."""
        items = [f"file_with_very_long_filename_to_ensure_pagination_{i:03d}.py" for i in range(20)]
        paginator = CursorPaginator(max_tokens=300, sort_key=lambda x: x)

        all_paginated_items = []
        cursor = None
        pages_count = 0

        while True:
            result = paginator.paginate(items, cursor=cursor)
            all_paginated_items.extend(result["items"])
            pages_count += 1

            if not result["has_more"]:
                assert result["next_cursor"] is None
                break
            else:
                assert result["next_cursor"] is not None
                cursor = result["next_cursor"]

        # Verify we got all items
        assert len(all_paginated_items) == len(items)
        assert sorted(all_paginated_items) == sorted(items)
        assert pages_count > 1  # Should require multiple pages

    def test_invalid_cursor_starts_from_beginning(self):
        """Test that invalid cursor gracefully starts from beginning."""
        items = ["a.py", "b.py", "c.py"]
        paginator = CursorPaginator(max_tokens=10000)

        # Use invalid cursor
        result = paginator.paginate(items, cursor="invalid_cursor")

        # Should start from beginning
        assert result["items"] == ["a.py", "b.py", "c.py"]
        assert result["has_more"] is False

    def test_custom_sort_key(self):
        """Test cursor pagination with custom sort key."""
        items = [{"name": "zebra.py", "size": 100}, {"name": "alpha.py", "size": 200}]

        # Sort by size (descending)
        paginator = CursorPaginator(max_tokens=10000, sort_key=lambda x: -x["size"])
        result = paginator.paginate(items)

        # Should be sorted by size descending
        assert result["items"][0]["name"] == "alpha.py"
        assert result["items"][1]["name"] == "zebra.py"

    def test_deterministic_sorting(self):
        """Test that pagination sorting is deterministic across calls."""
        items = ["zebra.py", "alpha.py", "beta.py", "gamma.py"]
        paginator = CursorPaginator(max_tokens=10000)

        result1 = paginator.paginate(items)
        result2 = paginator.paginate(items)

        # Should be identical
        assert result1["items"] == result2["items"]
        assert result1["items"] == ["alpha.py", "beta.py", "gamma.py", "zebra.py"]

    def test_minimum_items_per_page(self):
        """Test that minimum items per page is respected."""
        items = [f"very_long_filename_that_takes_many_tokens_{i}.py" for i in range(10)]

        # Set very low token limit but min_items_per_page=3
        paginator = CursorPaginator(max_tokens=50, min_items_per_page=3)
        result = paginator.paginate(items)

        # Should have at least 3 items despite token limit
        assert len(result["items"]) >= 3

    def test_cursor_with_metadata(self):
        """Test cursor pagination with additional metadata."""
        items = ["a.py", "b.py", "c.py"]
        metadata = {"pattern_used": "**/*.py", "total_files": 3}

        paginator = CursorPaginator(max_tokens=10000)
        result = paginator.paginate(items, metadata=metadata)

        assert result["pattern_used"] == "**/*.py"
        assert result["total_files"] == 3
        assert "items" in result
        assert "has_more" in result


class TestSimplifyCursorPagination:
    """Test the simplify_cursor_pagination function."""

    def test_small_list_no_pagination(self):
        """Test that small lists skip pagination entirely."""
        items = ["a.py", "b.py", "c.py"]  # <= 10 items
        result = simplify_cursor_pagination(items, max_tokens=1000)

        assert result["items"] == ["a.py", "b.py", "c.py"]
        assert "has_more" not in result
        assert "next_cursor" not in result

    def test_large_list_uses_pagination(self):
        """Test that large lists use cursor pagination."""
        items = [f"file_with_much_longer_filename_for_forcing_pagination_{i:03d}.py" for i in range(50)]  # > 10 items
        result = simplify_cursor_pagination(items, max_tokens=500)

        assert len(result["items"]) < len(items)  # Should be paginated
        assert "has_more" in result
        assert "next_cursor" in result

    def test_empty_list(self):
        """Test cursor pagination with empty list."""
        result = simplify_cursor_pagination([], max_tokens=1000)

        assert result["items"] == []
        assert "has_more" not in result
        assert "next_cursor" not in result

    def test_with_metadata(self):
        """Test cursor pagination preserves metadata."""
        items = ["a.py", "b.py"]
        metadata = {"pattern_used": "**/*.py"}
        result = simplify_cursor_pagination(items, metadata=metadata)

        assert result["pattern_used"] == "**/*.py"
        assert result["items"] == ["a.py", "b.py"]


class TestCursorPaginationEdgeCases:
    """Test edge cases for cursor pagination."""

    def test_cursor_at_last_item(self):
        """Test cursor pointing to the last item."""
        items = ["a.py", "b.py", "c.py"]
        paginator = CursorPaginator(max_tokens=10000)

        # Use cursor pointing to last item
        result = paginator.paginate(items, cursor="c.py")

        # Should return empty result
        assert result["items"] == []
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    def test_cursor_in_middle(self):
        """Test cursor pointing to middle item."""
        items = ["a.py", "b.py", "c.py", "d.py"]
        paginator = CursorPaginator(max_tokens=10000)

        # Use cursor pointing to middle item
        result = paginator.paginate(items, cursor="b.py")

        # Should return items after b.py
        assert result["items"] == ["c.py", "d.py"]
        assert result["has_more"] is False

    def test_very_long_items_exceed_token_limit(self):
        """Test handling of items that individually exceed token limits."""
        # Create items with very long content
        long_content = "x" * 10000  # Very long string
        items = [f"{long_content}_{i}.py" for i in range(3)]

        paginator = CursorPaginator(max_tokens=100, min_items_per_page=1)
        result = paginator.paginate(items)

        # Should still return at least minimum items
        assert len(result["items"]) >= 1

    def test_token_estimation_accuracy(self):
        """Test that token estimation works reasonably well."""
        # Create items of known approximate size with long content to force pagination
        items = [
            f"file_with_very_long_filename_and_much_content_to_ensure_proper_token_estimation_{i:05d}.py"
            for i in range(100)
        ]

        paginator = CursorPaginator(max_tokens=1000)
        result = paginator.paginate(items)

        # Should paginate appropriately (not all items, but not just 1)
        assert 1 < len(result["items"]) < len(items)
        assert result["has_more"] is True


class TestBackwardCompatibility:
    """Test that cursor pagination maintains backward compatibility."""

    def test_page_based_still_works(self):
        """Test that existing page-based pagination still works."""
        from aromcp.utils.pagination import simplify_pagination

        items = [f"file_{i:03d}.py" for i in range(20)]
        result = simplify_pagination(items, page=1, max_tokens=500)

        # Should work as before
        assert "items" in result
        assert "page" in result
        assert "has_more" in result
        assert "total_pages" in result

    def test_auto_paginate_response_still_works(self):
        """Test that auto_paginate_response maintains existing behavior."""
        from aromcp.filesystem_server.models.filesystem_models import ListFilesResponse
        from aromcp.utils.pagination import auto_paginate_response

        files = [f"file_{i:03d}.py" for i in range(20)]
        response = ListFilesResponse(files=files, pattern_used="**/*.py", total_files=len(files))

        result = auto_paginate_response(
            response=response, items_field="files", page=1, max_tokens=500, sort_key=lambda x: x
        )

        # Should return ListFilesResponse with pagination
        assert hasattr(result, "files")
        assert hasattr(result, "page")
        assert hasattr(result, "has_more")
