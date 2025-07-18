"""Dataclass models for analysis server MCP tool output schemas."""

from dataclasses import dataclass
from typing import Any


@dataclass
class UnusedCodeItem:
    """Individual unused code item."""

    file: str
    item: str
    type: str  # "function", "variable", "class", etc.
    line: int
    confidence: float
    reason: str
    estimated_lines: int


@dataclass
class FindDeadCodeResponse:
    """Response schema for find_dead_code tool."""

    unused_items: list[UnusedCodeItem]
    total_unused: int
    estimated_lines: int
    confidence_threshold: float
    entry_points_used: list[str]
    summary: dict[str, Any]


@dataclass
class ImportCycle:
    """Individual import cycle item."""

    cycle: list[str]
    type: str  # "direct", "indirect"
    severity: str  # "high", "medium", "low"
    length: int


@dataclass
class FindImportCyclesResponse:
    """Response schema for find_import_cycles tool."""

    cycles: list[ImportCycle]
    total_cycles: int
    files_affected: int
    max_depth_searched: int
    summary: dict[str, Any]


@dataclass
class ApiEndpoint:
    """Individual API endpoint item."""

    method: str
    path: str
    file: str
    line: int
    middleware: list[str]
    description: str | None
    parameters: list[str]
    framework: str


@dataclass
class ExtractApiEndpointsResponse:
    """Response schema for extract_api_endpoints tool."""

    endpoints: list[ApiEndpoint]
    total_endpoints: int
    by_method: dict[str, int]
    by_framework: dict[str, int]
    files_processed: int
    summary: dict[str, Any]
