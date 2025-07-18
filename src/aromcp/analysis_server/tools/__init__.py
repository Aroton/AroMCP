"""Analysis server tools implementations.

Provides production-ready code analysis tools for code quality analysis."""

from ...utils.json_parameter_middleware import json_convert
from .._security import get_project_root
from ..models.analysis_models import (
    ExtractApiEndpointsResponse,
    FindDeadCodeResponse,
    FindImportCyclesResponse,
)
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
        confidence_threshold: float = 0.8,
    ) -> FindDeadCodeResponse:
        """Identify potentially unused code that can be safely removed.

        Use this tool when:
        - Cleaning up legacy codebases to reduce maintenance burden
        - Optimizing bundle size by removing unused exports
        - Performing code quality audits
        - Before major refactoring to simplify scope

        This tool traces code usage from entry points (main files, exports,
        tests) to identify functions, variables, and classes that appear
        to be unused with a confidence score.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            entry_points: List of entry point files (auto-detected if None)
            include_tests: Whether to include test files as entry points
            confidence_threshold: Minimum confidence score to report as dead code

        Example:
            find_dead_code(confidence_threshold=0.9)
            → {"data": {
                "unused_items": [
                  {"file": "src/utils/helpers.js",
                   "item": "oldFormatDate",
                   "type": "function",
                   "line": 45,
                   "confidence": 0.95,
                   "reason": "No imports or calls found"}
                ],
                "summary": {"total_unused": 12, "estimated_lines": 340}
              }}

        Note: Review results carefully - dynamic imports and string-based
        access patterns may not be detected. Higher confidence = safer to remove.
        Use find_who_imports to verify specific files before deletion.
        """
        from ..models.analysis_models import UnusedCodeItem

        project_root = get_project_root(project_root)

        # Convert string to list if needed
        if isinstance(entry_points, str):
            entry_points = [entry_points]

        result = find_dead_code_impl(project_root, entry_points, include_tests, confidence_threshold)

        # Convert dict items to UnusedCodeItem dataclasses
        unused_items = []
        for item in result.get("unused_items", []):
            unused_items.append(
                UnusedCodeItem(
                    file=item.get("file", ""),
                    item=item.get("item", ""),
                    type=item.get("type", ""),
                    line=item.get("line", 0),
                    confidence=item.get("confidence", 0.0),
                    reason=item.get("reason", ""),
                    estimated_lines=item.get("estimated_lines", 1),
                )
            )

        return FindDeadCodeResponse(
            unused_items=unused_items,
            total_unused=result.get("total_unused", 0),
            estimated_lines=result.get("estimated_lines", 0),
            confidence_threshold=result.get("confidence_threshold", confidence_threshold),
            entry_points_used=result.get("entry_points_used", []),
            summary=result.get("summary", {}),
        )

    @mcp.tool
    @json_convert
    def find_import_cycles(
        project_root: str | None = None, max_depth: int = 10, include_node_modules: bool = False
    ) -> FindImportCyclesResponse:
        """Detect circular import dependencies that can cause runtime errors.

        Use this tool when:
        - Debugging "Cannot access X before initialization" errors
        - Improving code architecture and module organization
        - Refactoring to reduce coupling between modules
        - Setting up import linting rules to prevent cycles

        This tool analyzes import statements to find circular dependencies
        where module A imports B, and B imports A (directly or indirectly),
        which can cause initialization issues and make code harder to maintain.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            max_depth: Maximum cycle depth to search for
            include_node_modules: Whether to include node_modules in analysis

        Example:
            find_import_cycles()
            → {"data": {
                "cycles": [
                  {"cycle": ["src/auth/user.js", "src/api/auth.js", "src/auth/user.js"],
                   "type": "direct",
                   "severity": "high"}
                ],
                "summary": {"total_cycles": 3, "files_affected": 8}
              }}

        Note: To understand specific import relationships, use find_who_imports.
        Consider using dependency injection or lazy imports to break cycles.
        """
        from ..models.analysis_models import ImportCycle

        project_root = get_project_root(project_root)
        result = find_import_cycles_impl(project_root, max_depth, include_node_modules)

        # Convert dict cycles to ImportCycle dataclasses
        cycles = []
        for cycle in result.get("cycles", []):
            cycles.append(
                ImportCycle(
                    cycle=cycle.get("cycle", []),
                    type=cycle.get("type", "unknown"),
                    severity=cycle.get("severity", "medium"),
                    length=cycle.get("length", len(cycle.get("cycle", []))),
                )
            )

        return FindImportCyclesResponse(
            cycles=cycles,
            total_cycles=result.get("total_cycles", 0),
            files_affected=result.get("files_affected", 0),
            max_depth_searched=result.get("max_depth_searched", max_depth),
            summary=result.get("summary", {}),
        )

    @mcp.tool
    @json_convert
    def extract_api_endpoints(
        project_root: str | None = None, route_patterns: str | list[str] | None = None, include_middleware: bool = True
    ) -> ExtractApiEndpointsResponse:
        """Extract and document all API endpoints from route definitions.

        Use this tool when:
        - Generating API documentation automatically
        - Auditing API surface area for security review
        - Understanding available endpoints in an unfamiliar project
        - Checking for consistent REST conventions

        This tool parses Express, Next.js, FastAPI and similar route
        files to extract HTTP methods, paths, middleware, and parameters,
        providing a complete map of your API surface.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            route_patterns: Glob patterns for route files (defaults to common patterns)
            include_middleware: Whether to include middleware information

        Example:
            extract_api_endpoints()
            → {"data": {
                "endpoints": [
                  {"method": "POST", "path": "/api/users",
                   "file": "src/routes/users.js",
                   "line": 25,
                   "middleware": ["authenticate", "validateUser"],
                   "description": "Create new user"}
                ],
                "summary": {"total": 24, "by_method": {"GET": 15, "POST": 6, "PUT": 2, "DELETE": 1}}
              }}

        Note: Supports Express, Next.js API routes, FastAPI, and similar frameworks.
        For detailed function analysis, use extract_method_signatures.
        """
        from ..models.analysis_models import ApiEndpoint

        project_root = get_project_root(project_root)

        # Convert string to list if needed
        if isinstance(route_patterns, str):
            route_patterns = [route_patterns]

        result = extract_api_endpoints_impl(project_root, route_patterns, include_middleware)

        # Convert dict endpoints to ApiEndpoint dataclasses
        endpoints = []
        for endpoint in result.get("endpoints", []):
            endpoints.append(
                ApiEndpoint(
                    method=endpoint.get("method", ""),
                    path=endpoint.get("path", ""),
                    file=endpoint.get("file_path", ""),
                    line=endpoint.get("line_number", 0),
                    middleware=endpoint.get("middleware", []),
                    description=endpoint.get("description"),
                    parameters=endpoint.get("parameters", []),
                    framework=endpoint.get("framework", "unknown"),
                )
            )

        return ExtractApiEndpointsResponse(
            endpoints=endpoints,
            total_endpoints=result.get("total_endpoints", 0),
            by_method=result.get("by_method", {}),
            by_framework=result.get("by_framework", {}),
            files_processed=result.get("files_processed", 0),
            summary=result.get("summary", {}),
        )


__all__ = ["register_analysis_tools"]
