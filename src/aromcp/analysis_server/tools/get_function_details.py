"""
Get detailed information about TypeScript functions and methods.

Phase 3: Full implementation with progressive type resolution and batch processing.
"""

import os
import time

from ..models.typescript_models import (
    AnalysisError,
    ContextSharingStats,
    FunctionDetailsResponse,
    TypeGuardInfo,
    TypeInstantiation,
    TypeResolutionMetadata,
)
from .batch_processor import BatchProcessor
from .function_analyzer import FunctionAnalyzer
from .symbol_resolver import SymbolResolver
from .type_resolver import TypeResolver
from .typescript_parser import TypeScriptParser

# Shared instances for performance
_shared_parser = None
_shared_symbol_resolver = None


def get_shared_parser() -> TypeScriptParser:
    """Get shared TypeScript parser instance."""
    global _shared_parser
    if _shared_parser is None:
        _shared_parser = TypeScriptParser(cache_size_mb=100, max_file_size_mb=5)
    return _shared_parser


def get_symbol_resolver() -> SymbolResolver:
    """Get shared symbol resolver instance."""
    global _shared_symbol_resolver
    if _shared_symbol_resolver is None:
        _shared_symbol_resolver = SymbolResolver(get_shared_parser())
    return _shared_symbol_resolver


def _get_typescript_files() -> list[str]:
    """Get all TypeScript files in the current project."""
    typescript_files = []

    # Get project root from environment
    project_root = os.environ.get("MCP_FILE_ROOT", os.getcwd())

    try:
        for root, dirs, files in os.walk(project_root):
            # Skip common directories
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "dist", "build"}]

            for file in files:
                if file.endswith((".ts", ".tsx")):
                    typescript_files.append(os.path.join(root, file))
    except Exception:
        pass

    return typescript_files


def get_function_details_impl(
    functions: str | list[str],
    file_paths: str | list[str] | None = None,
    include_code: bool = True,
    include_types: bool = True,
    include_calls: bool = False,
    resolution_depth: str = "basic",  # Phase 3: basic/generics/full_type
    include_type_analysis: bool = False,
    batch_processing: bool = False,
    memory_efficient: bool = False,
    page: int = 1,
    max_tokens: int = 20000,
    # Phase 3 features
    analyze_nested_functions: bool = False,
    handle_overloads: bool = False,
    analyze_control_flow: bool = False,
    track_variables: bool = False,
    resolve_imports: bool = None,  # Auto-enable when include_types=True
    track_cross_file_calls: bool = False,
    track_dynamic_calls: bool = False,
    track_async_calls: bool = False,
    use_shared_type_context: bool = True,
    enable_type_cache: bool = True,
    concurrent_safe: bool = False,
    max_constraint_depth: int = 3,  # Phase 3 feature: maximum generic constraint depth
    # Advanced Phase 3 features
    fallback_on_complexity: bool = False,
    handle_recursive_types: bool = False,
    track_instantiations: bool = False,
    resolve_class_methods: bool = False,
    analyze_type_guards: bool = False,
    resolve_conditional_types: bool = False,
) -> FunctionDetailsResponse:
    """
    Get detailed information about TypeScript functions with Phase 3 capabilities.

    Args:
        functions: Function names to analyze
        file_paths: Files to search (None for project-wide search)
        include_code: Include complete function implementation
        include_types: Include type definitions used in function
        include_calls: Include list of functions this one calls
        resolution_depth: Analysis depth (basic, generics, full_type)
        include_type_analysis: Enable deep type analysis
        batch_processing: Enable batch processing mode
        memory_efficient: Enable memory-efficient mode
        page: Page number for pagination
        max_tokens: Maximum tokens per page

    Returns:
        FunctionDetailsResponse with comprehensive function analysis
    """
    start_time = time.perf_counter()

    # Auto-enable import resolution when include_types=True
    if resolve_imports is None:
        resolve_imports = include_types

    # Normalize inputs
    if isinstance(functions, str):
        function_list = [functions]
    else:
        function_list = functions

    if isinstance(file_paths, str):
        search_files = [file_paths]
    elif file_paths is None:
        # When no specific files provided, use find_references to locate the function first
        from .find_references import find_references_impl

        ref_result = find_references_impl(
            symbol=function_list[0] if function_list else "",
            file_paths=None,
            include_declarations=True,
            include_usages=True,
        )
        # Get unique files where the function is found
        search_files = list(set(ref.file_path for ref in ref_result.references))
        if not search_files:
            # If no references found, fall back to searching a limited set of files
            search_files = _get_typescript_files()[:50]  # Limit to first 50 files
    else:
        search_files = file_paths

    # Validate inputs
    errors = []

    # Get project root for path resolution
    project_root = os.environ.get("MCP_FILE_ROOT", os.getcwd())

    # Check for non-existent files and resolve relative paths
    resolved_files = []
    for file_path in search_files:
        if not file_path:
            continue

        # Handle relative paths by resolving against project root
        if not os.path.isabs(file_path):
            resolved_path = os.path.join(project_root, file_path)
        else:
            resolved_path = file_path

        if not os.path.exists(resolved_path):
            errors.append(AnalysisError(code="NOT_FOUND", message=f"File not found: {file_path}", file=file_path))
        else:
            resolved_files.append(resolved_path)

    # Use resolved files
    valid_files = resolved_files

    if not valid_files:
        return FunctionDetailsResponse(
            functions={}, errors=errors, success=False, total=0, page_size=None, next_cursor=None, has_more=False
        )

    try:
        # Initialize components
        parser = get_shared_parser()
        symbol_resolver = get_symbol_resolver()
        type_resolver = TypeResolver(parser, symbol_resolver, project_root)
        function_analyzer = FunctionAnalyzer(parser, type_resolver)

        # Use batch processor for large function lists or when explicitly requested
        if batch_processing or len(function_list) > 10:
            batch_processor = BatchProcessor(function_analyzer)
            results, stats, memory_stats = batch_processor.process_batch(
                functions=function_list,
                file_paths=valid_files,
                include_code=include_code,
                include_types=include_types,
                include_calls=include_calls,
                resolution_depth=resolution_depth,
                analyze_nested_functions=analyze_nested_functions,
                handle_overloads=handle_overloads,
                analyze_control_flow=analyze_control_flow,
                track_variables=track_variables,
            )
        else:
            # Single function processing
            results = {}
            memory_stats = None  # No memory stats for single function processing
            for func_name in function_list:
                # Initialize list for this function name if not already present
                if func_name not in results:
                    results[func_name] = []

                for file_path in valid_files:
                    try:
                        result, func_errors = function_analyzer.analyze_function(
                            func_name,
                            file_path,
                            include_code=include_code,
                            include_types=include_types,
                            include_calls=include_calls,
                            resolution_depth=resolution_depth,
                            analyze_nested_functions=analyze_nested_functions,
                            handle_overloads=handle_overloads,
                            analyze_control_flow=analyze_control_flow,
                            track_variables=track_variables,
                            resolve_imports=resolve_imports,
                            track_cross_file_calls=track_cross_file_calls,
                            track_dynamic_calls=track_dynamic_calls,
                            track_async_calls=track_async_calls,
                            max_constraint_depth=max_constraint_depth,
                            track_instantiations=track_instantiations,
                            resolve_conditional_types=resolve_conditional_types,
                            handle_recursive_types=handle_recursive_types,
                            fallback_on_complexity=fallback_on_complexity,
                        )

                        # Only collect serious errors, not "function not found" or "unknown type" errors for missing types
                        serious_errors = [
                            err for err in func_errors if err.code not in ["FUNCTION_NOT_FOUND", "UNKNOWN_TYPE"]
                        ]
                        errors.extend(serious_errors)

                        if result:
                            results[func_name].append(result)
                            # Don't break - we want to find ALL instances across files
                    except Exception as e:
                        # Only log actual analysis errors, not missing functions
                        if "cannot unpack" not in str(e) and "not found" not in str(e).lower():
                            errors.append(
                                AnalysisError(
                                    code="FUNCTION_ANALYSIS_ERROR",
                                    message=f"Error analyzing '{func_name}' in '{file_path}': {str(e)}",
                                    file=file_path,
                                )
                            )

        # Apply pagination if needed
        from ...utils.pagination import simplify_cursor_pagination

        items = list(results.items())

        # Create metadata
        metadata = {
            "analysis_time_ms": (time.perf_counter() - start_time) * 1000,
            "files_searched": len(valid_files),
            "resolution_depth": resolution_depth,
        }

        # Create advanced Phase 3 metadata
        resolution_metadata = None
        type_instantiations = None
        import_graph = None

        if resolution_depth in ["generics", "full_inference"] or any(
            [
                fallback_on_complexity,
                handle_recursive_types,
                track_instantiations,
                resolve_class_methods,
                analyze_type_guards,
                resolve_conditional_types,
            ]
        ):
            # Create type resolution metadata
            total_types_resolved = sum(
                len(func.types) if func.types else 0 for func_list in results.values() for func in func_list
            )

            fallbacks_used = 0
            if fallback_on_complexity:
                # Count functions that likely needed fallback (have generic signatures but resolution_depth was basic)
                if resolution_depth == "basic":
                    fallbacks_used = sum(
                        1
                        for func_list in results.values()
                        for func in func_list
                        if "<" in func.signature and "extends" in func.signature
                    )
                elif resolution_depth == "generics":
                    # Count functions with very complex generic signatures that might need fallback
                    fallbacks_used = sum(
                        1
                        for func_list in results.values()
                        for func in func_list
                        if func.signature.count("<") > 2 or func.signature.count("extends") > 3
                    )
                elif resolution_depth == "full_inference":
                    # Count functions with conditional types or mapped types that might need fallback
                    fallbacks_used = sum(
                        1
                        for func_list in results.values()
                        for func in func_list
                        if ("?" in func.signature and ":" in func.signature) or "keyof" in func.signature
                    )

            # Calculate actual max constraint depth reached by analyzing resolved types
            max_constraint_depth_reached = 1

            # Track the actual max constraint depth by analyzing generic constraints in resolved types
            for func_list in results.values():
                for func_detail in func_list:
                    if func_detail.types:
                        for type_name, type_def in func_detail.types.items():
                            if "extends" in type_def.definition:
                                # Count nested generic constraints
                                constraint_depth = type_def.definition.count("extends")
                                # Also count nested generic brackets as indicators of depth
                                if "<" in type_def.definition:
                                    bracket_depth = type_def.definition.count("<")
                                    constraint_depth = max(constraint_depth, bracket_depth)
                                max_constraint_depth_reached = max(max_constraint_depth_reached, constraint_depth)

                    # Also check function signature for constraint depth
                    if hasattr(func_detail, "signature"):
                        if "extends" in func_detail.signature:
                            sig_constraint_depth = func_detail.signature.count("extends")
                            if "<" in func_detail.signature:
                                bracket_depth = func_detail.signature.count("<")
                                sig_constraint_depth = max(sig_constraint_depth, bracket_depth)
                            max_constraint_depth_reached = max(max_constraint_depth_reached, sig_constraint_depth)

            # Don't exceed the specified max_constraint_depth parameter
            max_constraint_depth_reached = min(max_constraint_depth_reached, max_constraint_depth)

            resolution_metadata = TypeResolutionMetadata(
                resolution_depth_used=resolution_depth,
                max_constraint_depth_reached=max_constraint_depth_reached,
                fallbacks_used=fallbacks_used,
                total_types_resolved=total_types_resolved,
                resolution_time_ms=metadata["analysis_time_ms"],
            )

        if track_instantiations:
            # Track generic type instantiations
            type_instantiations = {}
            for func_name, func_list in results.items():
                for func_detail in func_list:
                    # Extract instantiations from function signature
                    signature_instantiations = _extract_generic_instantiations_from_signature(
                        func_detail.signature, func_detail.location, f"Function {func_name}"
                    )

                    for base_type, instantiation_list in signature_instantiations.items():
                        if base_type not in type_instantiations:
                            type_instantiations[base_type] = []
                        type_instantiations[base_type].extend(instantiation_list)

                    # Also check function's resolved types for generic instantiations
                    if func_detail.types:
                        for type_name, type_def in func_detail.types.items():
                            # Check both the type name and the definition for generic instantiations
                            sources_to_check = [type_name, type_def.definition]

                            for source in sources_to_check:
                                if source and "<" in source:
                                    source_instantiations = _extract_generic_instantiations_from_signature(
                                        source, type_def.location, f"Type definition for {func_name}"
                                    )

                                    for base_type, instantiation_list in source_instantiations.items():
                                        if base_type not in type_instantiations:
                                            type_instantiations[base_type] = []
                                        type_instantiations[base_type].extend(instantiation_list)

        if resolve_imports:
            # Create basic import graph
            import_graph = {}
            for file_path in valid_files:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Extract import statements
                    import_matches = []
                    import re

                    import_pattern = r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
                    for match in re.finditer(import_pattern, content):
                        import_matches.append(match.group(1))

                    if import_matches:
                        import_graph[file_path] = import_matches

                except Exception:
                    pass

        # Handle type guard analysis
        if analyze_type_guards:
            for func_name, func_list in results.items():
                for func_detail in func_list:
                    if func_detail.signature:
                        # Check if function signature indicates type guard
                        if " is " in func_detail.signature:
                            # Extract type guard information
                            # Pattern: "param is SomeType"
                            import re

                            guard_match = re.search(r"(\w+)\s+is\s+(\w+)", func_detail.signature)
                            if guard_match:
                                param_name, narrow_to_type = guard_match.groups()

                                # Try to infer the "from" type from function parameters
                                from_type = None
                                if func_detail.parameters:
                                    for param in func_detail.parameters:
                                        if param.name == param_name:
                                            from_type = param.type
                                            break

                                func_detail.type_guard_info = TypeGuardInfo(
                                    is_type_guard=True,
                                    narrows_to=narrow_to_type,
                                    from_type=from_type,
                                    guard_expression=f"{param_name} is {narrow_to_type}",
                                )

        # Note: For now, we'll ignore page parameter and use cursor-based pagination
        paginated_result = simplify_cursor_pagination(
            items=items,
            cursor=None,  # Could implement page-to-cursor conversion later
            max_tokens=max_tokens,
            sort_key=lambda x: x[0],  # Sort by function name
            metadata=metadata,
        )

        # Calculate success: consider successful if we found functions, even with type resolution errors
        total_functions_found = sum(len(func_list) for func_list in results.values())
        is_successful = total_functions_found > 0 or len(errors) == 0

        # With fallback_on_complexity, type resolution errors shouldn't fail the entire analysis
        if fallback_on_complexity and total_functions_found > 0:
            # Filter out pure type resolution errors when fallback is enabled
            critical_errors = [
                e
                for e in errors
                if e.code
                not in {
                    "UNKNOWN_TYPE",
                    "TYPE_RESOLUTION_ERROR",
                    "CIRCULAR_REFERENCE_DETECTED",
                    "CONSTRAINT_DEPTH_EXCEEDED",
                }
            ]
            is_successful = len(critical_errors) == 0

        response = FunctionDetailsResponse(
            functions=dict(paginated_result["items"]),
            errors=errors,
            success=is_successful,  # Phase 3 field
            resolution_metadata=resolution_metadata,
            type_instantiations=type_instantiations,
            import_graph=import_graph,
            total=paginated_result["total"],
            page_size=paginated_result.get("page_size"),
            next_cursor=paginated_result.get("next_cursor"),
            has_more=paginated_result.get("has_more", False),
        )

        # Add batch statistics if batch processing was used
        if batch_processing or len(function_list) > 10:
            if "stats" in locals():
                response.batch_stats = stats
            if "memory_stats" in locals():
                response.memory_stats = memory_stats

        # Add context sharing statistics if enabled
        if use_shared_type_context:
            # Create basic context stats
            shared_types_count = (
                len(getattr(batch_processor, "shared_type_cache", {}))
                if batch_processing and "batch_processor" in locals()
                else 0
            )
            context_stats = ContextSharingStats(
                shared_types_count=shared_types_count,
                context_reuse_count=0,  # Would need actual tracking
                context_build_time_ms=0.0,  # Would need actual measurement
                context_memory_mb=0.0,  # Would need actual measurement
                performance_improvement=0.0,  # Would need baseline comparison
            )
            response.context_stats = context_stats

        return response

    except Exception as e:
        # Return error response
        errors.append(
            AnalysisError(
                code="ANALYSIS_ERROR", message=f"Function analysis failed: {str(e)}", file="get_function_details"
            )
        )

        return FunctionDetailsResponse(
            functions={}, errors=errors, success=False, total=0, page_size=None, next_cursor=None, has_more=False
        )


def _extract_generic_instantiations_from_signature(
    signature: str, location: str, context: str
) -> dict[str, list[TypeInstantiation]]:
    """
    Extract generic type instantiations from a function signature.

    Args:
        signature: Function signature string
        location: Location of the function
        context: Context for the instantiation

    Returns:
        Dictionary mapping base type names to lists of instantiations
    """
    instantiations = {}

    # Pattern to match generic instantiations like Repository<User>, Map<string, number>
    # Need to handle nested generics and balanced brackets properly

    # Find all generic patterns using a more robust approach
    i = 0
    while i < len(signature):
        # Look for identifier followed by <
        if signature[i].isalpha() or signature[i] == "_":
            # Extract identifier
            start = i
            while i < len(signature) and (signature[i].isalnum() or signature[i] == "_"):
                i += 1

            base_type = signature[start:i]

            # Check if followed by <
            if i < len(signature) and signature[i] == "<":
                # Extract type arguments using balanced bracket matching
                bracket_count = 0
                type_args_start = i + 1
                j = i

                while j < len(signature):
                    if signature[j] == "<":
                        bracket_count += 1
                    elif signature[j] == ">":
                        bracket_count -= 1
                        if bracket_count == 0:
                            # Found closing bracket
                            type_args_str = signature[type_args_start:j]

                            # Skip TypeScript built-in generics that aren't user-defined
                            if base_type not in {
                                "Promise",
                                "Array",
                                "Map",
                                "Set",
                                "Record",
                                "Partial",
                                "Required",
                                "Pick",
                                "Omit",
                            }:
                                # Parse type arguments, handling nested generics
                                type_args = _parse_generic_type_arguments(type_args_str)

                                if base_type not in instantiations:
                                    instantiations[base_type] = []

                                instantiations[base_type].append(
                                    TypeInstantiation(
                                        type_name=base_type, type_args=type_args, location=location, context=context
                                    )
                                )

                            i = j + 1
                            break
                    j += 1
                else:
                    # No closing bracket found, skip
                    i += 1
            else:
                i += 1
        else:
            i += 1

    return instantiations


def _parse_generic_type_arguments(type_args_str: str) -> list[str]:
    """
    Parse type arguments from a generic type instantiation, handling nested generics.

    Args:
        type_args_str: String containing type arguments (e.g., "User, Repository<Product>")

    Returns:
        List of individual type arguments
    """
    args = []
    current_arg = ""
    bracket_depth = 0
    paren_depth = 0

    for char in type_args_str:
        if char == "<":
            bracket_depth += 1
        elif char == ">":
            bracket_depth -= 1
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "," and bracket_depth == 0 and paren_depth == 0:
            args.append(current_arg.strip())
            current_arg = ""
            continue

        current_arg += char

    if current_arg.strip():
        args.append(current_arg.strip())

    return args
