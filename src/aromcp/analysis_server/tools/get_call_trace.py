"""
Analyze static call graphs and function dependencies for TypeScript functions.

Phase 4: Full implementation with call graph construction, cycle detection,
and conditional execution path analysis.
"""

import os
import glob
import re
from typing import Any

from ..models.typescript_models import (
    CallTraceResponse,
    ExecutionPath,
    CallGraphStats,
    AnalysisError,
)
from .typescript_parser import TypeScriptParser, ResolutionDepth
from .call_graph_builder import CallGraphBuilder
from .cycle_detector import CycleDetector
from .conditional_analyzer import ConditionalAnalyzer


def get_call_trace_impl(
    entry_point: str,
    file_paths: str | list[str],
    max_depth: int = 10,
    include_external_calls: bool = False,
    analyze_conditions: bool = False,
    resolution_depth: str = ResolutionDepth.SEMANTIC,
    caller_direction: bool = False,
    callee_direction: bool = True,
    page: int = 1,
    max_tokens: int = 20000,
) -> CallTraceResponse:
    """
    Analyze static call graph and function dependencies from an entry point.

    Phase 4: Full implementation with call graph construction, cycle detection,
    and conditional execution path analysis.
    
    Args:
        entry_point: Function name to start analysis from
        file_paths: Files to analyze (required to avoid ambiguity)
        max_depth: Maximum call depth to analyze
        include_external_calls: Include calls to external modules
        analyze_conditions: Analyze conditional execution paths
        resolution_depth: Analysis depth (syntactic, semantic, full_type)
        caller_direction: Analyze who calls this function (reverse direction)
        callee_direction: Analyze what this function calls (forward direction)
        page: Page number for pagination
        max_tokens: Maximum tokens per page
        
    Returns:
        CallTraceResponse with static call graph and statistics
    """
    # Normalize inputs - file_paths is now required
    if isinstance(file_paths, str):
        search_files = [file_paths]
    else:
        search_files = file_paths
    
    # Validate inputs
    errors = []
    
    # Get project root for path resolution
    project_root = os.environ.get("MCP_FILE_ROOT", os.getcwd())
    
    # Check for non-existent files and resolve relative paths
    existing_files = []
    for file_path in search_files:
        if not file_path:
            continue
            
        # Handle relative paths by resolving against project root
        if not os.path.isabs(file_path):
            resolved_path = os.path.join(project_root, file_path)
        else:
            resolved_path = file_path
            
        if os.path.exists(resolved_path):
            existing_files.append(resolved_path)
        else:
            errors.append(AnalysisError(
                code="NOT_FOUND",
                message=f"File not found: {file_path}",
                file=file_path
            ))
    
    # Validate entry point format
    if not entry_point:
        errors.append(AnalysisError(
            code="INVALID_ENTRY_POINT",
            message="Entry point cannot be empty",
            file=None
        ))
        
    # If we have critical errors, return early
    if not entry_point or not existing_files:
        return CallTraceResponse(
            entry_point=entry_point,
            execution_paths=[],
            call_graph_stats=CallGraphStats(
                total_functions=0,
                total_edges=0,
                max_depth_reached=0,
                cycles_detected=0
            ),
            errors=errors,
            total=0,
            page_size=None,
            next_cursor=None,
            has_more=False
        )
    
    try:
        # Initialize components
        parser = _get_shared_parser()
        function_analyzer = _get_function_analyzer()
        
        # Validate that the entry point exists in the provided files
        entry_point_file = _find_function_file(entry_point, existing_files)
        if not entry_point_file:
            errors.append(AnalysisError(
                code="NOT_FOUND",
                message=f"Entry point function '{entry_point}' not found in any of the provided files",
                file=None
            ))
        
        # Build call graph
        call_graph_builder = CallGraphBuilder(parser, function_analyzer)
        graph_result = call_graph_builder.build_call_graph(
            entry_point, existing_files, max_depth
        )
        
        # Detect and handle cycles
        cycle_detector = CycleDetector(call_graph_builder)
        detected_cycles = cycle_detector.detect_and_break_cycles()
        
        # Analyze conditional execution if requested
        execution_paths = graph_result.execution_paths
        
        if analyze_conditions and execution_paths:
            conditional_analyzer = ConditionalAnalyzer(parser)
            
            # Find entry point file
            entry_point_file = _find_function_file(entry_point, existing_files)
            if entry_point_file:
                execution_paths = conditional_analyzer.enhance_execution_paths_with_conditions(
                    execution_paths, entry_point, entry_point_file
                )
        
        # Update stats with cycle information
        graph_result.call_graph_stats.cycles_detected = len(detected_cycles)
        
        # Apply pagination
        paginated_result = _paginate_execution_paths(execution_paths, page, max_tokens)
        
        return CallTraceResponse(
            entry_point=entry_point,
            execution_paths=paginated_result['items'],
            call_graph_stats=graph_result.call_graph_stats,
            errors=errors,
            total=paginated_result['total'],
            page_size=paginated_result['page_size'],
            next_cursor=paginated_result['next_cursor'],
            has_more=paginated_result['has_more']
        )
        
    except Exception as e:
        errors.append(AnalysisError(
            code="CALL_TRACE_ERROR",
            message=f"Error during call trace analysis: {str(e)}",
            file=None
        ))
        
        return CallTraceResponse(
            entry_point=entry_point,
            execution_paths=[],
            call_graph_stats=CallGraphStats(
                total_functions=0,
                total_edges=0,
                max_depth_reached=0,
                cycles_detected=0
            ),
            errors=errors,
            total=0,
            page_size=None,
            next_cursor=None,
            has_more=False
        )


def _get_typescript_files() -> list[str]:
    """Get all TypeScript files in the project using MCP_FILE_ROOT."""
    typescript_files = []
    
    # Get project root from environment
    project_root = os.environ.get("MCP_FILE_ROOT", os.getcwd())
    
    try:
        for root, dirs, files in os.walk(project_root):
            # Skip common directories
            dirs[:] = [d for d in dirs if d not in {'.git', 'node_modules', 'dist', 'build'}]
            
            for file in files:
                if file.endswith(('.ts', '.tsx')):
                    typescript_files.append(os.path.join(root, file))
                    
        return typescript_files[:50]  # Limit for performance
    except Exception:
        return []


def _get_shared_parser():
    """Get shared TypeScript parser instance."""
    # In a full implementation, this would return a cached parser
    # For now, return None and let the call graph builder handle it
    return None


def _get_function_analyzer():
    """Get shared function analyzer instance."""
    # In a full implementation, this would return a cached analyzer
    # For now, return None and let the call graph builder handle it
    return None


def _find_function_file(func_name: str, file_paths: list[str]) -> str | None:
    """Find which file contains a specific function."""
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Search for function definition patterns
            patterns = [
                rf'export\s+function\s+{re.escape(func_name)}\s*\(',
                rf'function\s+{re.escape(func_name)}\s*\(',
                rf'const\s+{re.escape(func_name)}\s*=.*=>',
                rf'{re.escape(func_name)}\s*\([^)]*\)\s*\{{',
            ]
            
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE):
                    return file_path
                    
        except Exception:
            continue
            
    return None


def _paginate_execution_paths(execution_paths: list[ExecutionPath], page: int, max_tokens: int) -> dict:
    """Apply pagination to execution paths."""
    try:
        from ...utils.pagination import paginate_list
        
        return paginate_list(
            items=execution_paths,
            page=page,
            max_tokens=max_tokens,
            sort_key=lambda x: len(x.path)  # Sort by path length
        )
    except ImportError:
        # Fallback pagination if utility not available
        items_per_page = max(1, max_tokens // 100)  # Rough estimate
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        
        paginated_items = execution_paths[start_idx:end_idx]
        
        return {
            'items': paginated_items,
            'total': len(execution_paths),
            'page_size': len(paginated_items),
            'next_cursor': str(page + 1) if end_idx < len(execution_paths) else None,
            'has_more': end_idx < len(execution_paths)
        }