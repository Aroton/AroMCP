# TypeScript Analysis MCP Server Implementation Plan

**Plan Date**: July 28, 2025  
**Research Sources**: Microsoft TypeScript Language Server, GitHub CodeQL, ESLint TypeScript, SonarQube, Academic research  
**Implementation Framework**: AroMCP with FastMCP 2.10+ standards

## Executive Summary

Implementation of a comprehensive TypeScript code analysis MCP server providing three core APIs: `find_references`, `get_function_details`, and `get_call_trace`. The solution combines proven production patterns from industry leaders with AroMCP architecture for efficient analysis at scale.

## Solution Architecture

**Core Approach**: Lazy Resolution Pattern with Multi-Level Caching
- **3-Tier Resolution**: Syntactic (90% queries) → Semantic (10% queries) → Full Type (1% queries)
- **Multi-Level Caching**: Memory AST cache → Symbol cache → Filesystem cache
- **Incremental Processing**: File modification tracking with batch processing
- **Tree-sitter Integration**: Performance-optimized TypeScript/TSX parsing
- **FastMCP Standards**: `@json_convert`, typed responses, union parameters

**Performance Targets**:
- Parse Speed: 2ms per 1000 LOC
- Large Codebase: <30 seconds for 10k+ files
- Memory Usage: <500MB for medium projects
- Cache Hit Rate: >80% on repeated operations

## Backwards Compatibility Decision

**Not Required** - This is a completely new TypeScript analysis capability. The implementation will:
- Integrate cleanly with existing build tools (`check_typescript`)
- Complement existing filesystem tools (`list_files`)
- Follow established AroMCP patterns without breaking existing functionality
- Use unified server architecture in `main_server.py`

## Implementation Phases

### Phase 1: Core TypeScript Parser with Basic Caching
**Duration**: 3-5 days  
**Objective**: Establish foundation with tree-sitter TypeScript parsing and basic AST caching

#### Code Organization
```
src/aromcp/analysis_server/
├── models/
│   └── typescript_models.py  # Response dataclasses for all APIs
├── tools/
│   ├── __init__.py           # Register all 3 tools with FastMCP
│   ├── find_references.py    # Reference finding implementation  
│   ├── get_function_details.py  # Function detail extraction
│   ├── get_call_trace.py     # Call graph construction
│   └── _typescript_parser.py # Core parsing and caching logic
└── _security.py              # Path validation (existing)
```

#### Key Tasks
1. **Tree-sitter Integration Setup**
   - Install tree-sitter-typescript with binary wheels
   - Configure separate parsers for TS/TSX dialects
   - Implement excluded directories (node_modules, .git, dist)

2. **3-Tier Lazy Resolution Architecture**
   - Syntactic resolution: AST-only, no cross-file analysis
   - Semantic resolution: Import tracking, cross-file symbols
   - Full type resolution: Deep generic analysis, type inference

3. **Basic AST Caching**
   - LRU cache for parsed ASTs (100MB default)
   - File modification time tracking
   - Cache invalidation on file changes

4. **Error Handling Framework**
   - Graceful malformed TypeScript handling
   - Structured error responses with standard codes
   - Partial parsing for syntax errors

#### Acceptance Criteria
- ✅ Parse TypeScript/TSX files with <2ms per 1000 LOC performance
- ✅ Implement 3-tier lazy resolution with configurable depth
- ✅ Basic LRU AST cache with file modification tracking
- ✅ Handle malformed TypeScript gracefully (skip unparseable sections)
- ✅ Follow FastMCP standards: `@json_convert`, typed responses, union parameters
- ✅ Memory usage stays under 200MB for medium projects (~1000 files)
- ✅ Exclude node_modules, .git, dist directories by default

#### Existing Test Analysis
- **Test Structure**: Create `tests/analysis_server/test_typescript_parser.py` with `TestTypeScriptParser` class
- **Test Patterns**: Follow existing analysis server test patterns from filesystem server
- **Performance Tests**: Add synthetic TypeScript fixtures for parsing benchmarks
- **Security Tests**: Validate path traversal protection using existing security patterns

#### Dependencies to Add
```toml
# Add to pyproject.toml [project.optional-dependencies.all-servers]
"tree-sitter>=0.20.0",
"tree-sitter-typescript>=0.20.0", 
"tree-sitter-javascript>=0.20.0"
```

---

### Phase 2: Symbol Resolution and Reference Finding
**Duration**: 4-6 days  
**Objective**: Implement `find_references` with cross-file symbol resolution

#### Code Organization
- Extend `_typescript_parser.py` with symbol resolution capabilities
- Implement `find_references.py` with multi-pass reference analysis
- Add import/export dependency tracking

#### Key Tasks
1. **Multi-Pass Reference Analysis**
   - Pass 1: Syntactic references (fast, local to each file)
   - Pass 2: Semantic references (cross-file, moderate cost)
   - Pass 3: Dynamic references (expensive, opt-in)

2. **Symbol Resolution System**
   - Import dependency graph construction
   - Cross-file symbol tracking
   - Inheritance chain resolution for method calls

3. **Reference Classification**
   - Distinguish declarations, definitions, and usages
   - Handle method calls vs function calls vs property access
   - Support "ClassName#methodName" syntax

4. **Performance Optimization**
   - Batch file processing for large codebases
   - Pagination with 20k token limits
   - Deterministic sorting for consistent results

#### Acceptance Criteria
- ✅ Find all references to functions and class methods across project
- ✅ Distinguish between declarations, definitions, and usages with confidence scores
- ✅ Support "ClassName#methodName" syntax for method references
- ✅ Handle inheritance chains and method overrides correctly
- ✅ Return paginated results with 20k token limit using AroMCP pagination utilities
- ✅ Complete analysis in <30 seconds for 10k+ file projects
- ✅ Exclude tests by default, include with `include_tests=true` parameter
- ✅ Memory usage stays under 300MB during large codebase analysis

#### Existing Test Analysis
- **Reuse Patterns**: Extend test patterns from `tests/filesystem_server/test_find_who_imports.py`
- **New Test Cases**: Add inheritance chain tests, method resolution tests
- **Performance Tests**: Validate large codebase performance with synthetic projects
- **Update Required**: MUST update `tests/test_main_server.py` to include `find_references` in expected tools list

#### Tree-sitter Query Patterns
```python
# Reference finding queries
IDENTIFIER_QUERY = """
(identifier) @ref
(#eq? @ref "{symbol}")
"""

CALL_EXPRESSION_QUERY = """
(call_expression
    function: [
        (identifier) @function_name
        (member_expression 
            object: (identifier) @object
            property: (property_identifier) @method)
    ]
    arguments: (arguments) @args)
"""

METHOD_DEFINITION_QUERY = """
(method_definition
    name: (property_identifier) @method_name
    parameters: (formal_parameters) @params
    body: (statement_block) @body)
"""
```

---

### Phase 3: Function Details and Type Extraction  
**Duration**: 5-7 days  
**Objective**: Implement `get_function_details` with progressive type resolution

#### Code Organization
- Add type extraction logic to `_typescript_parser.py`
- Implement batch processing in `get_function_details.py`
- Create comprehensive type resolution system

#### Key Tasks
1. **Progressive Type Resolution**
   - Basic: Explicitly declared types only
   - Generics: Generic constraints and instantiations
   - Full Inference: Deep type analysis with TypeScript compiler integration

2. **Batch Processing System**
   - Efficient batch requests for 100+ functions
   - Shared type context across batch
   - Memory management for large batches

3. **Type Definition Extraction**
   - Extract imported types and interfaces
   - Resolve generic type parameters
   - Handle complex types (unions, intersections)

4. **Function Analysis**
   - Complete signature extraction with parameters/return types
   - Function body inclusion (optional)
   - Call analysis (functions called by each analyzed function)

#### Acceptance Criteria
- ✅ Extract complete function signatures with parameter and return types
- ✅ Support batch requests for 100+ functions within 10 seconds
- ✅ Resolve imported types and interfaces (basic level resolution)
- ✅ Include complete function code when `include_code=true`
- ✅ Identify functions called by each analyzed function (call dependencies)
- ✅ Handle generic types with constraint resolution up to 5 levels deep
- ✅ Progressive type resolution: basic → generics → full inference
- ✅ Memory usage stays under 400MB during batch processing

#### Existing Test Analysis
- **Extend Patterns**: Build on `tests/filesystem_server/test_extract_method_signatures.py`
- **TypeScript Features**: Add comprehensive tests for generics, interfaces, complex types
- **Batch Performance**: Validate batch request performance with timing tests
- **Type Resolution**: Test progressive resolution depths and accuracy

#### Type Extraction Queries
```python
FUNCTION_SIGNATURE_QUERY = """
(function_declaration
    name: (identifier) @func_name
    parameters: (formal_parameters) @params
    return_type: (type_annotation 
        type: (_) @return_type)?)
"""

GENERIC_TYPE_QUERY = """
(type_parameters
    (type_parameter 
        name: (type_identifier) @generic_name
        constraint: (constraint
            type: (_) @constraint_type)?))
"""

INTERFACE_QUERY = """
(interface_declaration
    name: (type_identifier) @interface_name
    body: (object_type) @interface_body)
"""
```

---

### Phase 4: Call Graph Construction and Tracing
**Duration**: 6-8 days  
**Objective**: Implement `get_call_trace` with cycle detection and conditional analysis

#### Code Organization
- Add call graph builder to `_typescript_parser.py`
- Implement trace algorithms in `get_call_trace.py`
- Create conditional execution path analysis

#### Key Tasks
1. **Scalable Call Graph Construction**
   - Field-based flow analysis for precision
   - Static and dynamic call resolution
   - Memory-efficient graph storage using NetworkX

2. **Cycle Detection and Handling**
   - Detect circular call patterns
   - Break cycles with placeholder references
   - Prevent infinite recursion in deep traces

3. **Conditional Execution Analysis**
   - Analyze if/else branches in call paths
   - Estimate execution probabilities
   - Track conditional call dependencies

4. **Trace Direction Support**
   - Caller analysis (who calls this function)
   - Callee analysis (what does this function call)
   - Bidirectional tracing support

#### Acceptance Criteria
- ✅ Build complete call graphs from entry points with 99% edge coverage
- ✅ Detect and break circular call patterns without infinite loops
- ✅ Analyze conditional execution paths with branch detection
- ✅ Support both caller and callee direction tracing
- ✅ Complete deep traces (10+ levels) within 15 seconds
- ✅ Return execution paths without code (lean responses for performance)
- ✅ Handle dynamic property access and method calls with reasonable accuracy
- ✅ Memory usage stays under 500MB for complex call graphs

#### Existing Test Analysis
- **New Test Suite**: No existing call tracing tests - need comprehensive new test suite
- **Test Fixtures**: Create complex call chains, recursive functions, conditional calls
- **Cycle Detection**: Add specific tests for circular call patterns
- **Performance**: Validate deep recursion performance and memory usage

#### Call Graph Queries
```python
CALL_SITE_QUERY = """
(call_expression
    function: [
        (identifier) @direct_call
        (member_expression
            object: (_) @object
            property: (property_identifier) @method)
        (subscript_expression
            object: (_) @dynamic_object
            index: (_) @dynamic_property)
    ]
    arguments: (arguments) @args) @call_site
"""

CONDITIONAL_CALL_QUERY = """
(if_statement
    condition: (_) @condition
    consequence: (_) @then_block
    alternative: (_)? @else_block)
"""
```

---

### Phase 5: Performance Optimization and Monorepo Support
**Duration**: 4-6 days  
**Objective**: Optimize for large codebases and add monorepo workspace support

#### Code Organization
- Add workspace analysis to `_typescript_parser.py`
- Implement memory optimization patterns
- Create incremental analysis system

#### Key Tasks
1. **Monorepo Workspace Support**
   - Multiple tsconfig.json file discovery
   - Project dependency graph construction
   - Cross-project symbol resolution

2. **Large-Scale Performance Optimization**
   - Incremental analysis based on file modifications
   - Batch processing with memory management
   - Compressed AST storage with string interning

3. **Advanced Caching Strategy**
   - Multi-level cache with dependency invalidation
   - Persistent filesystem cache
   - Memory usage optimization with garbage collection

4. **Scalability Improvements**
   - File size limits (5MB default)
   - Memory limits with adaptive batch sizing
   - Priority-based analysis ordering

#### Acceptance Criteria
- ✅ Support multiple tsconfig.json files in monorepos with workspace-aware analysis
- ✅ Maintain <500MB memory usage for 50k+ file projects
- ✅ Achieve >80% cache hit rates on repeated operations
- ✅ Process large codebases with batching and memory management
- ✅ Cross-project symbol resolution in workspaces
- ✅ Incremental analysis based on file modification tracking reduces analysis time by 70%
- ✅ Compressed AST storage reduces memory usage by 50%

#### Existing Test Analysis
- **Performance Tests**: Add large-scale performance tests with synthetic 5k+ file projects
- **Monorepo Fixtures**: Create monorepo test fixtures with multiple tsconfig.json files
- **Memory Validation**: Test memory usage patterns and cache effectiveness
- **Incremental Tests**: Validate incremental analysis accuracy and performance

#### Dependencies to Add
```toml
# Additional dependency for call graph construction
"networkx>=3.0"  # For call graph construction and analysis
```

---

## Tool API Specifications

### find_references
```python
@mcp.tool
@json_convert
def find_references(
    symbol: str,                     # "functionName" or "ClassName#methodName"
    include_tests: bool = False,     # Include test files in search
    cursor: str | None = None,       # Pagination cursor
    max_tokens: int = 20000          # Token limit per response
) -> FindReferencesResponse

@dataclass
class FindReferencesResponse:
    references: list[ReferenceInfo]
    total_references: int
    searched_files: int
    errors: list[AnalysisError]
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None

@dataclass  
class ReferenceInfo:
    file: str
    line: int
    column: int
    context: str                     # Line of code containing reference
    reference_type: str              # "declaration", "definition", "usage", "call"
    confidence: float                # 0.0-1.0 confidence score
```

### get_function_details
```python
@mcp.tool
@json_convert  
def get_function_details(
    functions: str | list[str],      # Function names to analyze
    include_code: bool = False,      # Include full function code
    include_types: bool = True,      # Include type definitions
    cursor: str | None = None,       # Pagination cursor
    max_tokens: int = 20000          # Token limit per response
) -> FunctionDetailsResponse

@dataclass
class FunctionDetailsResponse:
    functions: dict[str, FunctionDetail]
    errors: list[AnalysisError]
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None

@dataclass
class FunctionDetail:
    signature: str                   # Full function signature with params and return type
    location: str                    # "path/to/file.ts:lineNumber"
    code: str | None = None         # Complete function implementation (if requested)
    types: dict[str, TypeDefinition] | None = None  # Types used in this function
    calls: list[str] = field(default_factory=list)  # Functions this one calls

@dataclass
class TypeDefinition:
    kind: str                        # "interface", "type", "class", "enum"
    definition: str                  # Full type definition
    location: str                    # "path/to/file.ts:lineNumber"
```

### get_call_trace
```python
@mcp.tool
@json_convert
def get_call_trace(
    entry_point: str,                # Function to trace from
    max_depth: int = 10,             # Maximum trace depth
    include_external: bool = False,  # Include node_modules
    cursor: str | None = None,       # Pagination cursor  
    max_tokens: int = 20000          # Token limit per response
) -> CallTraceResponse

@dataclass
class CallTraceResponse:
    entry_point: str
    execution_paths: list[ExecutionPath]
    call_graph_stats: CallGraphStats
    errors: list[AnalysisError]
    # Standard pagination fields
    total: int = 0
    page_size: int | None = None
    next_cursor: str | None = None
    has_more: bool | None = None

@dataclass
class ExecutionPath:
    path: list[str]                  # ["login", "validate", "UserService#find", ...]
    condition: str | None = None     # "if (user.isActive)" - for conditional branches
    execution_probability: float    # 0.0-1.0 estimated execution likelihood

@dataclass
class CallGraphStats:
    total_functions: int
    total_edges: int
    max_depth_reached: int
    cycles_detected: int
```

## Testing Strategy

### Test Structure
Following AroMCP modular test patterns:
```
tests/analysis_server/
├── test_find_references.py          # TestFindReferences class
├── test_get_function_details.py     # TestGetFunctionDetails class  
├── test_get_call_trace.py           # TestGetCallTrace class
├── test_typescript_parser.py        # TestTypeScriptParser class
├── test_performance.py              # Performance benchmarks
├── test_security_validation.py      # Cross-tool security validation
├── fixtures/
│   ├── small_project/               # <100 files for basic functionality
│   ├── medium_project/              # 500-1000 files for performance testing
│   ├── large_project/               # 5000+ files for scalability testing
│   ├── monorepo_workspace/          # Multiple tsconfig.json files
│   ├── complex_types/               # Generic/interface test cases
│   ├── inheritance_chains/          # Class hierarchy test cases
│   └── call_graph_examples/         # Complex call patterns
```

### Critical Test Requirements
1. **MUST update `tests/test_main_server.py`** to include new tool names in expected tools lists:
   - `find_references`
   - `get_function_details` 
   - `get_call_trace`

2. **Performance Benchmarks** for each acceptance criterion:
   - Parse speed: 2ms per 1000 LOC
   - Large codebase analysis: <30 seconds for 10k+ files
   - Memory usage: <500MB maximum
   - Cache hit rates: >80% on repeated operations

3. **Security Validation** using existing patterns:
   - Path traversal protection
   - File size limits enforcement
   - Memory usage bounds
   - Input sanitization

### Test Data Requirements
- **Real-world TypeScript samples** from popular open-source projects
- **Synthetic large codebases** for performance testing
- **Edge case collections**: malformed TypeScript, complex generics, deep inheritance
- **Monorepo examples**: Multiple TypeScript projects with cross-references

## Risk Assessment and Mitigation

### Phase 1 Risks
**Risk**: Tree-sitter integration complexity and performance issues  
**Mitigation**: Use proven binary wheel pattern from research, implement excluded directories early  
**Fallback**: Start with basic regex parsing if tree-sitter integration fails

### Phase 2 Risks  
**Risk**: Symbol resolution performance degrades with large codebases  
**Mitigation**: Implement 3-tier lazy pattern early, comprehensive performance testing  
**Fallback**: Reduce resolution depth or implement file-based batching

### Phase 3 Risks
**Risk**: Type resolution complexity overwhelms system  
**Mitigation**: Progressive resolution with strict depth limits, memory monitoring  
**Fallback**: Basic type extraction only, defer complex inference

### Phase 4 Risks
**Risk**: Call graph construction consumes excessive memory  
**Mitigation**: Batch processing with GC, NetworkX for efficient graph storage  
**Fallback**: Shallow call tracing with reduced depth limits

### Phase 5 Risks
**Risk**: Monorepo complexity breaks existing functionality  
**Mitigation**: Start with workspace discovery, add cross-project features gradually  
**Fallback**: Single-project analysis with manual project boundaries

## Success Metrics

### Performance Metrics
- **Parse Speed**: <2ms per 1000 LOC consistently
- **Large Scale**: Analysis of 10k+ files completes in <30 seconds
- **Memory Efficiency**: <500MB usage for medium projects
- **Cache Performance**: >80% hit rates on repeated operations
- **Response Time**: Individual API calls complete in <500ms when cached

### Functionality Metrics
- **Reference Accuracy**: >95% precision for reference finding
- **Type Resolution**: >90% success rate for imported type resolution
- **Call Graph Coverage**: >99% edge coverage for static analysis
- **Error Handling**: Graceful degradation for 100% of malformed inputs

### Integration Metrics
- **FastMCP Compliance**: 100% compatibility with FastMCP 2.10+ standards
- **AroMCP Patterns**: Consistent with existing filesystem and build server patterns
- **Security**: Zero path traversal vulnerabilities in security testing
- **Backwards Compatibility**: Zero regressions in existing AroMCP functionality

## Conclusion

This implementation plan synthesizes proven production patterns from Microsoft TypeScript Language Server, GitHub CodeQL, and other industry leaders with AroMCP architecture requirements. The phased approach ensures each component is thoroughly tested and optimized before building upon it, resulting in a production-ready TypeScript analysis server that scales efficiently to large codebases while maintaining the performance and security standards expected in professional development environments.

The plan prioritizes the 90/10 rule observed in production systems: 90% of queries need only syntactic analysis, 10% require semantic analysis, and <1% need full type inference. This focus on lazy resolution and intelligent caching ensures optimal performance across all use cases while providing comprehensive analysis capabilities when needed.