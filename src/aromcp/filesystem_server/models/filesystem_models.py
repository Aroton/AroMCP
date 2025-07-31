"""Dataclass models for filesystem server MCP tool output schemas."""

from dataclasses import dataclass

# Standard cursor pagination fields for all paginated responses:
# - total: int - Total number of items across all pages
# - page_size: int | None - Number of items in current page
# - next_cursor: str | None - Cursor for next page (None if no more pages)
# - has_more: bool | None - Whether there are more pages


@dataclass
class ListFilesResponse:
    """Response schema for list_files tool."""

    files: list[str]
    pattern_used: str | list[str]
    # Standard cursor pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class ReadFileItem:
    """Individual file content item."""

    file: str
    content: str
    encoding: str
    size: int
    exists: bool
    error: str | None = None


@dataclass
class ReadFilesResponse:
    """Response schema for read_files tool."""

    items: list[ReadFileItem]
    # Standard cursor pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class WriteFilesResponse:
    """Response schema for write_files tool."""

    files_written: list[str]
    total_files: int
    directories_created: list[str]
    success: bool
