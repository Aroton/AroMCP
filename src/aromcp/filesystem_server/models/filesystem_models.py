"""Dataclass models for filesystem server MCP tool output schemas."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ListFilesResponse:
    """Response schema for list_files tool."""

    files: list[str]
    pattern_used: str | list[str]
    total_files: int


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
    page: int
    total_pages: int
    total_files: int
    has_more: bool


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
