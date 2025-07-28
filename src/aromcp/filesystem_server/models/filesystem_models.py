"""Dataclass models for filesystem server MCP tool output schemas."""

from dataclasses import dataclass
from typing import Any, Union


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


@dataclass
class MethodSignature:
    """Individual method signature item."""

    name: str
    file_path: str
    line: int
    signature: str
    params: list[str]
    returns: str | None
    decorators: list[str]
    docstring: str | None
    class_name: str | None
    is_method: bool
    is_async: bool


@dataclass
class ExtractMethodSignaturesResponse:
    """Response schema for extract_method_signatures tool."""

    signatures: list[MethodSignature]
    total_signatures: int
    files_processed: int
    patterns_used: str | list[str]
    # Optional fields
    errors: list[dict[str, Any]] | None = None
    # Standard cursor pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class ImportDependency:
    """Individual import dependency item."""

    file: str
    imports: list[str]
    line_numbers: list[int]
    import_type: str  # "from", "import", "require", etc.


@dataclass
class FindWhoImportsResponse:
    """Response schema for find_who_imports tool."""

    target_file: str
    dependents: list[ImportDependency]
    total_dependents: int
    safe_to_delete: bool
    impact_analysis: dict[str, Any]
    # Standard cursor pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None
