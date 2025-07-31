"""Analysis server tools implementations.

TypeScript analysis tools for Phase 1 implementation.
"""

from ...utils.json_parameter_middleware import json_convert
from ..models.typescript_models import (
    FindReferencesResponse,
    FunctionDetailsResponse,
    CallTraceResponse,
)
from .find_references import find_references_impl
from .get_function_details import get_function_details_impl
from .get_call_trace import get_call_trace_impl


def register_analysis_tools(mcp):
    """Register TypeScript analysis tools with the MCP server."""
    
    @mcp.tool
    @json_convert
    def find_references(
        symbol: str,
        file_paths: str | list[str] | None = None,
        include_declarations: bool = True,
        include_usages: bool = True,
        include_tests: bool = False,
        resolution_depth: str = "semantic",
        page: int = 1,
        max_tokens: int = 20000,
    ) -> FindReferencesResponse:
        """
        Find all references to a TypeScript symbol across files.
        
        Use this tool when:
        - Tracking where a function, class, or variable is used
        - Analyzing symbol dependencies before refactoring
        - Understanding code impact of changes
        - Finding all usages of an interface or type
        
        Replaces bash commands: grep -r "symbolName", ag "symbolName"
        
        Args:
            symbol: Symbol name to find references for (e.g., "getUserById", "User")
            file_paths: Specific files to search, or None for project-wide search
            include_declarations: Include where symbol is declared/defined
            include_usages: Include where symbol is used/called
            include_tests: Include references found in test files
            resolution_depth: Analysis level - "syntactic", "semantic", or "full_type"
            page: Page number for pagination (default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
            
        Example:
            find_references("User")
            → FindReferencesResponse with all User interface references
            
        Note: Cross-references with get_function_details for detailed analysis
        """
        return find_references_impl(
            symbol=symbol,
            file_paths=file_paths,
            include_declarations=include_declarations,
            include_usages=include_usages,
            include_tests=include_tests,
            resolution_depth=resolution_depth,
            page=page,
            max_tokens=max_tokens,
        )
    
    @mcp.tool
    @json_convert
    def get_function_details(
        functions: str | list[str],
        file_paths: str | list[str] | None = None,
        include_code: bool = True,
        include_types: bool = True,
        include_calls: bool = False,
        resolution_depth: str = "semantic",
        page: int = 1,
        max_tokens: int = 20000,
    ) -> FunctionDetailsResponse:
        """
        Get detailed information about TypeScript functions and methods.
        
        Use this tool when:
        - Understanding function signatures and parameters
        - Analyzing type definitions used in functions
        - Documenting function behavior and interfaces
        - Preparing for function refactoring or optimization
        
        Replaces bash commands: grep -A 20 "function name", manual code inspection
        
        Args:
            functions: Function names to analyze (single string or list)
            file_paths: Files to search, or None for project-wide search
            include_code: Include complete function implementation
            include_types: Include detailed type definitions used
            include_calls: Include functions called within this function
            resolution_depth: Analysis level - "syntactic", "semantic", or "full_type"
            page: Page number for pagination (default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
            
        Example:
            get_function_details(["getUserById", "createUser"])
            → FunctionDetailsResponse with signatures and implementations
            
        Note: Pairs well with find_references to understand complete function usage
        """
        return get_function_details_impl(
            functions=functions,
            file_paths=file_paths,
            include_code=include_code,
            include_types=include_types,
            include_calls=include_calls,
            resolution_depth=resolution_depth,
            page=page,
            max_tokens=max_tokens,
        )
    
    @mcp.tool
    @json_convert
    def analyze_call_graph(
        entry_point: str,
        file_paths: str | list[str],
        max_depth: int = 10,
        include_external_calls: bool = False,
        analyze_conditions: bool = False,
        resolution_depth: str = "semantic",
        page: int = 1,
        max_tokens: int = 20000,
    ) -> CallTraceResponse:
        """
        Analyze static call graph and function dependencies from an entry point.
        
        Use this tool when:
        - Mapping function dependencies before refactoring
        - Understanding which functions a method can potentially call
        - Detecting circular dependencies in function calls
        - Planning code organization and module boundaries
        
        Replaces bash commands: manual dependency mapping, grep -r for function calls
        
        Args:
            entry_point: Function name to analyze dependencies for (e.g., "main", "UserService.process")
            file_paths: Files to analyze (required to avoid ambiguity with multiple definitions)
            max_depth: Maximum call depth to analyze (prevents infinite recursion)
            include_external_calls: Include calls to external modules/libraries
            analyze_conditions: Analyze conditional execution branches
            resolution_depth: Analysis level - "syntactic", "semantic", or "full_type"
            page: Page number for pagination (default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
            
        Example:
            analyze_call_graph("authenticate", "src/auth/auth.ts", max_depth=5)
            → CallTraceResponse with static call graph from authenticate function
            
        Note: Shows potential calls, not runtime execution. Use with get_function_details for implementation details.
        """
        return get_call_trace_impl(
            entry_point=entry_point,
            file_paths=file_paths,
            max_depth=max_depth,
            include_external_calls=include_external_calls,
            analyze_conditions=analyze_conditions,
            resolution_depth=resolution_depth,
            page=page,
            max_tokens=max_tokens,
        )


__all__ = ["register_analysis_tools"]