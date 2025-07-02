"""Analysis server tools implementations.

Provides 8 production-ready code analysis tools for standards management
and security/quality analysis."""

from typing import Any

from ...utils.json_parameter_middleware import json_convert
from .._security import get_project_root
from .load_coding_standards import load_coding_standards_impl
from .get_relevant_standards import get_relevant_standards_impl
from .parse_standard_to_rules import parse_standard_to_rules_impl
from .detect_security_patterns import detect_security_patterns_impl
from .find_dead_code import find_dead_code_impl
from .find_import_cycles import find_import_cycles_impl
from .analyze_component_usage import analyze_component_usage_impl
from .extract_api_endpoints import extract_api_endpoints_impl


def register_analysis_tools(mcp):
    """Register analysis tools with the MCP server."""

    # Standards Management Tools
    @mcp.tool
    @json_convert
    def load_coding_standards(
        project_root: str | None = None,
        standards_dir: str = ".aromcp/standards",
        include_metadata: bool = True
    ) -> dict[str, Any]:
        """Load all coding standards from the project with metadata.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            standards_dir: Directory containing standards files (relative to project_root)
            include_metadata: Whether to parse and include YAML frontmatter metadata
        """
        if project_root is None:
            project_root = get_project_root()
        return load_coding_standards_impl(project_root, standards_dir, include_metadata)

    @mcp.tool
    @json_convert
    def get_relevant_standards(
        file_path: str,
        project_root: str | None = None,
        include_general: bool = True
    ) -> dict[str, Any]:
        """Get coding standards relevant to a specific file.

        Args:
            file_path: File path to analyze for relevant standards
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            include_general: Whether to include general/default standards
        """
        if project_root is None:
            project_root = get_project_root()
        return get_relevant_standards_impl(file_path, project_root, include_general)

    @mcp.tool
    @json_convert
    def parse_standard_to_rules(
        standard_content: str,
        standard_id: str,
        extract_examples: bool = True
    ) -> dict[str, Any]:
        """Parse a coding standard to extract enforceable rules.

        Args:
            standard_content: Markdown content of the coding standard
            standard_id: Unique identifier for the standard
            extract_examples: Whether to extract good/bad code examples
        """
        return parse_standard_to_rules_impl(standard_content, standard_id, extract_examples)


    # Security & Quality Analysis Tools
    @mcp.tool
    @json_convert
    def detect_security_patterns(
        file_paths: str | list[str],
        project_root: str | None = None,
        patterns: list[str] | None = None,
        severity_threshold: str = "low"
    ) -> dict[str, Any]:
        """Detect security vulnerability patterns in code files.

        Args:
            file_paths: File path(s) or glob patterns to analyze
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            patterns: Security patterns to check (uses defaults if None)
            severity_threshold: Minimum severity to report (low|medium|high|critical)
        """
        if project_root is None:
            project_root = get_project_root()
        return detect_security_patterns_impl(file_paths, project_root, patterns, severity_threshold)

    @mcp.tool
    @json_convert
    def find_dead_code(
        project_root: str | None = None,
        entry_points: list[str] | None = None,
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
        return find_dead_code_impl(project_root, entry_points, include_tests, confidence_threshold)

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
    def analyze_component_usage(
        project_root: str | None = None,
        component_patterns: list[str] | None = None,
        include_imports: bool = True
    ) -> dict[str, Any]:
        """Analyze component/function usage patterns across the codebase.

        Args:
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            component_patterns: Glob patterns for component files (defaults to common patterns)
            include_imports: Whether to track import usage in addition to direct calls
        """
        if project_root is None:
            project_root = get_project_root()
        return analyze_component_usage_impl(project_root, component_patterns, include_imports)

    @mcp.tool
    @json_convert
    def extract_api_endpoints(
        project_root: str | None = None,
        route_patterns: list[str] | None = None,
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
        return extract_api_endpoints_impl(project_root, route_patterns, include_middleware)


__all__ = [
    "register_analysis_tools"
]