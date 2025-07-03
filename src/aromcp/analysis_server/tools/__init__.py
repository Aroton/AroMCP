"""Analysis server tools implementations.

Provides production-ready code analysis tools for code quality analysis."""

from typing import Any

from ...utils.json_parameter_middleware import json_convert
from .._security import get_project_root
from .extract_api_endpoints import extract_api_endpoints_impl
from .find_dead_code import find_dead_code_impl
from .find_import_cycles import find_import_cycles_impl


def register_analysis_tools(mcp):
    """Register analysis tools with the MCP server."""

    # Code Quality Analysis Tools

    @mcp.tool
    @json_convert
    def find_dead_code(
        project_root: str | None = None,
        entry_points: str | list[str] | None = None,
        include_tests: bool = False,
        confidence_threshold: float = 0.8
    ) -> dict[str, Any]:
        """Find unused code that can potentially be removed.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            entry_points: List of entry point files (auto-detected if None)
            include_tests: Whether to include test files as entry points
            confidence_threshold: Minimum confidence score to report as dead code
        """
        if project_root is None:
            project_root = get_project_root()

        # Convert string to list if needed
        if isinstance(entry_points, str):
            entry_points = [entry_points]

        return find_dead_code_impl(
            project_root, entry_points, include_tests, confidence_threshold
        )

    @mcp.tool
    @json_convert
    def find_import_cycles(
        project_root: str | None = None,
        max_depth: int = 10,
        include_node_modules: bool = False
    ) -> dict[str, Any]:
        """Detect circular import dependencies in the codebase.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            max_depth: Maximum cycle depth to search for
            include_node_modules: Whether to include node_modules in analysis
        """
        if project_root is None:
            project_root = get_project_root()
        return find_import_cycles_impl(project_root, max_depth, include_node_modules)


    @mcp.tool
    @json_convert
    def extract_api_endpoints(
        project_root: str | None = None,
        route_patterns: str | list[str] | None = None,
        include_middleware: bool = True
    ) -> dict[str, Any]:
        """Extract and document API endpoints from route files.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            route_patterns: Glob patterns for route files (defaults to common patterns)
            include_middleware: Whether to include middleware information
        """
        if project_root is None:
            project_root = get_project_root()

        # Convert string to list if needed
        if isinstance(route_patterns, str):
            route_patterns = [route_patterns]

        return extract_api_endpoints_impl(
            project_root, route_patterns, include_middleware
        )




__all__ = [
    "register_analysis_tools"
]
