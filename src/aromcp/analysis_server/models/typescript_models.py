"""
TypeScript analysis response models for FastMCP integration.

These dataclasses define the response structure for all TypeScript analysis tools,
following FastMCP standards with typed responses.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AnalysisError:
    """Standard error information for analysis operations."""

    code: str  # Error code like "PARSE_ERROR", "NOT_FOUND", etc.
    message: str  # Human-readable error message
    file: str | None = None  # File path where error occurred
    line: int | None = None  # Line number where error occurred


@dataclass
class ReferenceInfo:
    """Information about a symbol reference location."""

    file_path: str  # File path containing the reference
    line: int  # Line number (1-based)
    column: int  # Column number (0-based)
    context: str  # Line of code containing the reference
    reference_type: str  # "declaration", "definition", "usage", "call"
    confidence: float  # 0.0-1.0 confidence score
    symbol_type: str | None = None  # Type of symbol being referenced
    symbol_name: str | None = None  # Name of the symbol being referenced
    # Phase 2 additions for class method support
    class_name: str | None = None  # For class methods, the containing class
    method_name: str | None = None  # For methods, the method name
    method_signature: str | None = None  # Full method signature
    import_path: str | None = None  # For import references, the imported module path
    import_type: str | None = None  # For import references, type of import

    @property
    def confidence_score(self) -> float:
        """Alias for confidence to maintain compatibility."""
        return self.confidence


@dataclass
class FindReferencesResponse:
    """Response for find_references tool."""

    references: list[ReferenceInfo]
    total_references: int
    searched_files: int
    errors: list[AnalysisError]
    success: bool = True  # Phase 2 addition for test compatibility
    inheritance_info: "SymbolResolutionResult | None" = None  # Phase 2 inheritance support
    analysis_stats: "AnalysisStats | None" = None  # Performance statistics
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class ParameterType:
    """Type information for function parameters."""

    name: str  # Parameter name
    type: str  # Type annotation (e.g., "string", "number", "MyInterface")
    optional: bool = False  # Whether parameter is optional
    default_value: str | None = None  # Default value if any
    is_rest_parameter: bool = False  # Whether this is a rest parameter (...args)


@dataclass
class TypeDefinition:
    """Definition of a custom type used in function signatures."""

    kind: str  # "interface", "type", "class", "enum"
    definition: str  # Full type definition source code
    location: str  # "path/to/file.ts:lineNumber"


@dataclass
class FunctionDetail:
    """Detailed information about a function or method."""

    signature: str  # Full function signature with params and return type
    location: str  # "path/to/file.ts:lineNumber"
    code: str | None = None  # Complete function implementation (if requested)
    types: dict[str, TypeDefinition] | None = None  # Types used in this function
    calls: list[str] = field(default_factory=list)  # Functions this one calls
    parameters: list[ParameterType] = field(default_factory=list)  # Detailed parameter info
    # Advanced Phase 3 fields
    type_guard_info: "TypeGuardInfo | None" = None  # Type guard information


@dataclass
class FunctionDetailsResponse:
    """Response for get_function_details tool."""

    functions: dict[str, list[FunctionDetail]]
    errors: list[AnalysisError]
    success: bool = True  # Phase 3 addition for test compatibility
    # Advanced Phase 3 fields
    resolution_metadata: "TypeResolutionMetadata | None" = None
    type_instantiations: dict[str, list["TypeInstantiation"]] | None = None
    import_graph: dict[str, list[str]] | None = None
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


@dataclass
class ExecutionPath:
    """A single execution path in a call trace."""

    path: list[str]  # ["login", "validate", "UserService#find", ...]
    condition: str | None = None  # "if (user.isActive)" - for conditional branches
    execution_probability: float = 1.0  # 0.0-1.0 estimated execution likelihood


@dataclass
class CallGraphStats:
    """Statistics about the call graph analysis."""

    total_functions: int
    total_edges: int
    max_depth_reached: int
    cycles_detected: int


@dataclass
class CallTraceResponse:
    """Response for get_call_trace tool."""

    entry_point: str
    execution_paths: list[ExecutionPath]
    call_graph_stats: CallGraphStats
    errors: list[AnalysisError]
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


# Parser-specific models for internal use


@dataclass
class ParseResult:
    """Result of parsing a TypeScript file."""

    success: bool
    tree: Any | None = None  # tree_sitter.Tree object
    errors: list[AnalysisError] = field(default_factory=list)
    parse_time_ms: float = 0.0


@dataclass
class CacheEntry:
    """Entry in the AST cache."""

    tree: Any  # tree_sitter.Tree object
    file_hash: str  # Hash of file content for validation
    modification_time: float  # File modification timestamp
    parse_time_ms: float  # Time taken to parse
    access_count: int = 0  # For LRU eviction


@dataclass
class ParserStats:
    """Statistics about parser performance."""

    files_parsed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_parse_time_ms: float = 0.0
    average_parse_time_ms: float = 0.0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as percentage."""
        total_requests = self.cache_hits + self.cache_misses
        return (self.cache_hits / total_requests * 100.0) if total_requests > 0 else 0.0


# Phase 2 Symbol Resolution Models


@dataclass
class SymbolInfo:
    """Information about a symbol (class, function, variable, etc)."""

    name: str  # Symbol name
    symbol_type: str  # "function", "class", "interface", "variable", "method", "property"
    file_path: str  # File containing the symbol
    line: int  # Line number where symbol is defined
    column: int  # Column number where symbol starts
    confidence_score: float = 1.0  # 0.0-1.0 confidence of resolution
    is_exported: bool = False  # Whether symbol is exported
    class_name: str | None = None  # For methods, the containing class
    method_name: str | None = None  # For class methods
    parameters: list[ParameterType] = field(default_factory=list)  # For functions/methods
    return_type: str | None = None  # Return type annotation
    is_type_guard: bool = False  # For TypeScript type guard functions


@dataclass
class InheritanceChain:
    """Information about class inheritance relationships."""

    base_class: str  # Name of the base class
    derived_classes: list[str]  # Names of classes that inherit from base
    file_path: str  # File containing the inheritance relationship
    inheritance_depth: int = 1  # How deep the inheritance chain is


@dataclass
class AnalysisStats:
    """Statistics about symbol resolution analysis."""

    total_files_processed: int = 0
    total_symbols_resolved: int = 0
    analysis_time_ms: float = 0.0
    files_with_errors: int = 0
    # Compatibility aliases for tests
    files_analyzed: int = 0
    references_found: int = 0


@dataclass
class MemoryStats:
    """Memory usage statistics during analysis."""

    peak_memory_mb: float = 0.0
    final_memory_mb: float = 0.0
    cache_memory_mb: float = 0.0


@dataclass
class SymbolResolutionResult:
    """Results of multi-pass symbol resolution."""

    success: bool
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)  # symbol_name -> SymbolInfo
    references: list[ReferenceInfo] = field(default_factory=list)  # All found references
    inheritance_chains: list[InheritanceChain] = field(default_factory=list)
    errors: list[AnalysisError] = field(default_factory=list)
    analysis_stats: AnalysisStats = field(default_factory=AnalysisStats)
    memory_stats: MemoryStats = field(default_factory=MemoryStats)
    # Pagination support
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool = False

    @property
    def chains(self) -> list[InheritanceChain]:
        """Alias for inheritance_chains for backward compatibility."""
        return self.inheritance_chains


# Import/Export Tracking Models


@dataclass
class ImportInfo:
    """Information about an import statement."""

    source_file: str  # File containing the import
    module_path: str  # Path/name of the imported module
    imported_names: list[str] = field(default_factory=list)  # Named imports
    default_import: str | None = None  # Default import name
    namespace_import: str | None = None  # Namespace import (import * as foo)
    import_type: str = "named"  # "named", "default", "namespace", "side_effect", "dynamic"
    is_type_only: bool = False  # TypeScript type-only import
    is_external: bool = False  # Whether it's an external module (node_modules)
    is_async: bool = False  # For dynamic imports
    line: int = 0  # Line number of import statement
    column: int = 0  # Column number of import statement


@dataclass
class ExportInfo:
    """Information about an export statement."""

    source_file: str  # File containing the export
    exported_names: list[str] = field(default_factory=list)  # Named exports
    default_export: str | None = None  # Default export name
    export_type: str = "named"  # "named", "default", "namespace", "re_export"
    re_export_from: str | None = None  # For re-exports, the source module
    line: int = 0  # Line number of export statement
    column: int = 0  # Column number of export statement


@dataclass
class ModuleInfo:
    """Detailed information about a single module."""

    file_path: str  # Path to the module file
    imports: list[ImportInfo] = field(default_factory=list)
    exports: list[ExportInfo] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # Files this module depends on
    dependents: list[str] = field(default_factory=list)  # Files that depend on this module


@dataclass
class DependencyEdge:
    """An edge in the dependency graph."""

    source: str  # Source module ID
    target: str  # Target module ID
    import_type: str  # Type of dependency
    line: int = 0  # Line where dependency is created


@dataclass
class DependencyNode:
    """A node in the dependency graph."""

    module_id: str  # Unique identifier for the module
    file_path: str  # Full path to the module file
    exports: list[str] = field(default_factory=list)  # What this module exports
    imports: list[str] = field(default_factory=list)  # What this module imports


@dataclass
class DependencyGraph:
    """Complete dependency graph for a project."""

    nodes: list[DependencyNode] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)
    analysis_stats: AnalysisStats = field(default_factory=AnalysisStats)


@dataclass
class CircularDependency:
    """Information about a circular dependency."""

    cycle_path: list[DependencyNode] = field(default_factory=list)  # Nodes forming the cycle
    cycle_length: int = 0  # Number of modules in the cycle
    severity: str = "warning"  # "warning", "error"


@dataclass
class ImportAnalysisResult:
    """Result of import/export analysis."""

    success: bool
    imports: list[ImportInfo] = field(default_factory=list)
    exports: list[ExportInfo] = field(default_factory=list)
    dependency_graph: DependencyGraph | None = None
    circular_dependencies: list[CircularDependency] = field(default_factory=list)
    errors: list[AnalysisError] = field(default_factory=list)
    # Pagination support
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool = False


# Phase 3 Models for Function Details and Type Extraction


@dataclass
class TypeInstantiation:
    """Information about a generic type instantiation."""

    type_name: str  # Base generic type name (e.g., "Repository")
    type_args: list[str]  # Type arguments (e.g., ["User", "string"])
    location: str  # Where this instantiation occurs
    context: str  # Context of the instantiation


@dataclass
class TypeResolutionMetadata:
    """Metadata about type resolution process."""

    resolution_depth_used: str  # "basic", "generics", "full_inference"
    max_constraint_depth_reached: int  # Deepest constraint level reached
    fallbacks_used: int  # Number of times fallback resolution was used
    total_types_resolved: int  # Total types successfully resolved
    resolution_time_ms: float  # Time spent on type resolution


@dataclass
class BatchProcessingStats:
    """Statistics about batch processing performance."""

    total_requested: int  # Number of functions requested for processing
    total_processed: int  # Number of functions successfully processed
    processing_time_seconds: float  # Total processing time
    average_time_per_function_ms: float  # Average time per function
    functions_per_second: float  # Processing throughput
    cache_hit_rate: float  # Percentage of cache hits
    memory_peak_mb: float  # Peak memory usage during processing


@dataclass
class MemoryUsageStats:
    """Memory usage statistics during analysis."""

    initial_memory_mb: float  # Memory at start of analysis
    peak_memory_mb: float  # Peak memory during analysis
    final_memory_mb: float  # Memory at end of analysis
    memory_increase_mb: float  # Total memory increase
    cache_memory_mb: float  # Memory used by caches
    gc_collections: int  # Number of garbage collections triggered


@dataclass
class CallDependencyInfo:
    """Information about a function call dependency."""

    function_name: str  # Name of the called function
    source_file: str  # File where the function is defined
    is_imported: bool  # Whether this is an imported function
    is_external: bool  # Whether this is an external/built-in function
    call_type: str  # "direct", "method", "dynamic", "callback"
    line_number: int  # Line where the call occurs
    confidence: float  # 0.0-1.0 confidence in call identification


@dataclass
class VariableDeclaration:
    """Information about a variable declaration within a function."""

    name: str  # Variable name
    declaration_type: str  # "const", "let", "var", "parameter", "destructured"
    type_annotation: str | None  # Type annotation if present
    initial_value: str | None  # Initial value if present
    line_number: int  # Line where declared
    scope: str  # "function", "block", "parameter"


@dataclass
class ControlFlowInfo:
    """Information about control flow patterns in a function."""

    has_conditionals: bool  # Contains if/else statements
    has_loops: bool  # Contains for/while loops
    has_switch: bool  # Contains switch statements
    has_try_catch: bool  # Contains try/catch blocks
    has_async_await: bool  # Contains async/await patterns
    has_multiple_returns: bool  # Multiple return statements
    has_break_continue: bool  # Contains break/continue statements
    cyclomatic_complexity: int  # Estimated cyclomatic complexity


@dataclass
class AsyncCallInfo:
    """Information about async function calls and patterns."""

    has_async_calls: bool  # Function makes async calls
    returns_promise: bool  # Function returns a Promise
    uses_await: bool  # Function uses await keyword
    promise_patterns: list[str]  # Promise patterns used (e.g., "Promise.all", "Promise.race")
    callback_patterns: list[str]  # Callback patterns identified


@dataclass
class TypeGuardInfo:
    """Information about TypeScript type guard functions."""

    is_type_guard: bool  # Whether function is a type guard
    narrows_to: str | None  # Type that the guard narrows to
    from_type: str | None  # Type that the guard narrows from
    guard_expression: str | None  # The actual guard expression


@dataclass
class FunctionOverload:
    """Information about a function overload signature."""

    signature: str  # The overload signature
    is_implementation: bool  # Whether this is the implementation signature
    parameters: list[ParameterType]  # Parameter details for this overload
    return_type: str  # Return type for this overload


@dataclass
class NestedFunctionInfo:
    """Information about nested functions within a function."""

    name: str  # Name of the nested function
    signature: str  # Signature of the nested function
    line_number: int  # Line where defined
    function_type: str  # "function", "arrow", "method", "closure"
    captures_variables: list[str]  # Variables captured from outer scope


@dataclass
class GenericConstraintInfo:
    """Information about generic type constraints."""

    type_parameter: str  # Type parameter name (e.g., "T")
    constraint: str  # Constraint expression (e.g., "extends BaseEntity")
    constraint_depth: int  # Nesting depth of the constraint
    resolved_constraint_type: str | None  # Resolved constraint type if available


@dataclass
class ImportTypeInfo:
    """Information about imported types and their usage."""

    imported_type: str  # Name of the imported type
    source_module: str  # Module where type is imported from
    import_type: str  # "named", "default", "namespace", "type_only"
    usage_locations: list[int]  # Line numbers where type is used
    local_alias: str | None  # Local alias if renamed


@dataclass
class CacheStats:
    """Statistics about type and AST caching."""

    total_requests: int  # Total cache requests
    cache_hits: int  # Successful cache hits
    cache_misses: int  # Cache misses
    hit_rate: float  # Cache hit rate percentage
    cache_size_mb: float  # Current cache size in MB
    eviction_count: int  # Number of cache evictions

    # Compatibility properties for tests
    @property
    def hits(self):
        return self.cache_hits

    @property
    def misses(self):
        return self.cache_misses


@dataclass
class ContextSharingStats:
    """Statistics about shared type context optimization."""

    shared_types_count: int  # Number of types in shared context
    context_reuse_count: int  # How many times context was reused
    context_build_time_ms: float  # Time to build shared context
    context_memory_mb: float  # Memory used by shared context
    performance_improvement: float  # Performance improvement percentage


# Enhanced FunctionDetail for Phase 3
@dataclass
class EnhancedFunctionDetail:
    """Enhanced function detail with Phase 3 capabilities."""

    signature: str  # Full function signature with params and return type
    location: str  # "path/to/file.ts:lineNumber"
    code: str | None = None  # Complete function implementation (if requested)
    types: dict[str, TypeDefinition] | None = None  # Types used in this function
    calls: list[str] = field(default_factory=list)  # Functions this one calls

    # Phase 3 enhancements
    parameters: list[ParameterType] = field(default_factory=list)  # Detailed parameter info
    overloads: list[FunctionOverload] = field(default_factory=list)  # Function overloads
    nested_functions: dict[str, NestedFunctionInfo] = field(default_factory=dict)  # Nested functions
    call_info: list[CallDependencyInfo] = field(default_factory=list)  # Detailed call info
    variable_info: dict[str, list[VariableDeclaration]] | None = None  # Variable declarations
    control_flow_info: ControlFlowInfo | None = None  # Control flow analysis
    async_call_info: AsyncCallInfo | None = None  # Async pattern analysis
    type_guard_info: TypeGuardInfo | None = None  # Type guard information
    dynamic_call_info: list[dict[str, Any]] = field(default_factory=list)  # Dynamic calls
    generic_constraints: list[GenericConstraintInfo] = field(default_factory=list)  # Generic info
    import_types: list[ImportTypeInfo] = field(default_factory=list)  # Imported type usage


# Enhanced FunctionDetailsResponse for Phase 3
@dataclass
class EnhancedFunctionDetailsResponse:
    """Enhanced response for get_function_details tool with Phase 3 features."""

    functions: dict[str, EnhancedFunctionDetail]
    errors: list[AnalysisError]
    success: bool = True

    # Phase 3 enhancements
    resolution_metadata: TypeResolutionMetadata | None = None
    batch_stats: BatchProcessingStats | None = None
    memory_stats: MemoryUsageStats | None = None
    type_instantiations: dict[str, list[TypeInstantiation]] | None = None
    import_graph: dict[str, list[str]] | None = None  # Module dependency graph
    cache_stats: CacheStats | None = None
    context_stats: ContextSharingStats | None = None

    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None


# Progressive Type Resolution Models
@dataclass
class BasicTypeInfo:
    """Basic type information for Level 1 resolution."""

    type_name: str  # Type name as declared
    kind: str  # "primitive", "interface", "class", "type_alias", "enum"
    definition: str  # Type definition source
    location: str  # Where type is defined


@dataclass
class GenericTypeInfo:
    """Generic type information for Level 2 resolution."""

    type_name: str  # Generic type name
    type_parameters: list[str]  # Type parameter names
    constraints: list[GenericConstraintInfo]  # Type constraints
    instantiations: list[TypeInstantiation]  # Known instantiations
    variance: str | None = None  # "covariant", "contravariant", "invariant"


@dataclass
class InferredTypeInfo:
    """Inferred type information for Level 3 resolution."""

    type_name: str  # Inferred type name
    inference_source: str  # How type was inferred
    confidence: float  # 0.0-1.0 confidence in inference
    alternatives: list[str] = field(default_factory=list)  # Alternative inferences
    inference_path: list[str] = field(default_factory=list)  # Steps in inference


@dataclass
class TypeResolutionResult:
    """Result of progressive type resolution."""

    success: bool
    resolution_level: str  # "basic", "generics", "full_inference"
    basic_types: dict[str, BasicTypeInfo] = field(default_factory=dict)
    generic_types: dict[str, GenericTypeInfo] = field(default_factory=dict)
    inferred_types: dict[str, InferredTypeInfo] = field(default_factory=dict)
    resolution_metadata: TypeResolutionMetadata | None = None
    errors: list[AnalysisError] = field(default_factory=list)


# Batch Processing Models
@dataclass
class BatchFunctionRequest:
    """Request for batch function processing."""

    function_names: list[str]  # Functions to analyze
    file_paths: list[str]  # Files to search in
    include_code: bool = False
    include_types: bool = True
    include_calls: bool = False
    resolution_depth: str = "basic"
    batch_size: int = 50  # Functions per batch
    max_memory_mb: float = 400.0  # Memory limit
    timeout_seconds: float = 10.0  # Timeout per batch


@dataclass
class BatchFunctionResult:
    """Result of batch function processing."""

    success: bool
    functions: dict[str, EnhancedFunctionDetail]
    batch_stats: BatchProcessingStats
    memory_stats: MemoryUsageStats
    errors: list[AnalysisError] = field(default_factory=list)
    partial_results: bool = False  # Whether some functions failed


# Phase 4 Call Graph Models


@dataclass
class ConditionalPath:
    """A conditional execution path with probability."""

    condition: str  # The condition expression
    execution_probability: float  # 0.0-1.0 estimated probability
    function_calls: list[str]  # Functions called in this path
    path_type: str  # "if_then", "if_else", "switch_case", "try_catch", etc.


@dataclass
class CallGraphResult:
    """Result of call graph construction."""

    entry_point: str
    execution_paths: list[ExecutionPath]
    call_graph_stats: CallGraphStats
    processing_time_ms: float


@dataclass
class FunctionDefinition:
    """Information about a function definition location."""

    name: str
    file: str
    line: int
    signature: str | None = None


@dataclass
class CallSite:
    """Information about a function call site."""

    function_name: str
    file: str
    line: int
    context: str  # Line of code containing the call
    call_type: str = "direct"  # "direct", "method", "dynamic"
