# TypeScript Analysis MCP Server - Test Suite

This directory contains comprehensive failing tests for Phase 1 of the TypeScript Analysis MCP Server implementation. The tests follow TDD principles and define the expected behavior before implementation.

## Test Structure

### Test Files

1. **`test_typescript_parser.py`** - Core parser functionality tests
   - TypeScript/TSX file parsing
   - AST cache management (LRU)
   - Performance requirements (<2ms per 1000 LOC)
   - Error handling and graceful degradation
   - Resolution depth levels (syntactic/semantic/full-type)

2. **`test_typescript_tools.py`** - Tool implementation tests
   - `find_references` - Symbol reference discovery
   - `get_function_details` - Function signature and type analysis
   - `analyze_call_graph` - Static call graph analysis
   - Tool integration and consistency

3. **`test_performance_requirements.py`** - Performance and memory tests
   - Parsing speed requirements validation
   - Memory usage under 200MB for medium projects
   - Cache performance characteristics
   - Concurrent parsing safety

4. **`test_fastmcp_integration.py`** - FastMCP compliance tests
   - `@json_convert` decorator functionality
   - Union type parameters (str | list[str])
   - Typed response models
   - MCP protocol compliance

### Test Fixtures

The `fixtures/` directory contains TypeScript files for testing:

- **`valid_typescript.ts`** - Basic TypeScript with interfaces, classes, functions
- **`valid_tsx.tsx`** - TSX with React components and JSX syntax
- **`malformed.ts`** - File with various syntax errors for error handling tests
- **`large_file.ts`** - Large file (~2000 LOC) for performance testing
- **`with_imports.ts`** - Complex import statements for dependency analysis
- **`with_generics.ts`** - Advanced generic types for deep type analysis

## Phase 1 Requirements Tested

### Core Parser Requirements
- ✅ Parse TypeScript/TSX files using tree-sitter
- ✅ 3-tier lazy resolution (syntactic/semantic/full-type)
- ✅ Basic LRU AST cache with file modification tracking
- ✅ Handle malformed TypeScript gracefully
- ✅ Performance: <2ms per 1000 LOC
- ✅ Memory usage: <200MB for medium projects (~1000 files)
- ✅ Exclude node_modules, .git, dist directories by default

### Tool Interface Requirements
- ✅ FastMCP standards: `@json_convert`, typed responses, union parameters
- ✅ Tool stubs return empty results with proper structure
- ✅ Consistent error handling across tools
- ✅ Pagination support for large result sets

### Expected Components

#### TypeScriptParser Class
```python
class TypeScriptParser:
    def __init__(self, cache_size_mb=100, max_file_size_mb=5)
    def parse_file(self, file_path: str, resolution_depth: ResolutionDepth) -> ParseResult
    def get_cached_tree(self, file_path: str) -> Tree | None
    def invalidate_cache(self, file_path: str) -> None
    def get_parser_stats(self) -> ParserStats
```

#### ResolutionDepth Enum
```python
class ResolutionDepth:
    SYNTACTIC = "syntactic"    # AST-only, no cross-file analysis
    SEMANTIC = "semantic"      # Import tracking, cross-file symbols
    FULL_TYPE = "full_type"    # Deep generic analysis, type inference
```

#### Tool Functions
```python
def find_references_impl(symbol: str, file_paths: str | list[str], ...) -> FindReferencesResponse
def get_function_details_impl(functions: str | list[str], ...) -> FunctionDetailsResponse
def get_call_trace_impl(entry_point: str, ...) -> CallTraceResponse  # Implementation function name unchanged
```

## Running Tests

```bash
# Run all analysis server tests
uv run pytest tests/analysis_server/ -v

# Run specific test categories
uv run pytest tests/analysis_server/test_typescript_parser.py -v
uv run pytest tests/analysis_server/test_typescript_tools.py -v
uv run pytest tests/analysis_server/test_performance_requirements.py -v
uv run pytest tests/analysis_server/test_fastmcp_integration.py -v

# Run single test
uv run pytest tests/analysis_server/test_typescript_parser.py::TestTypeScriptParser::test_parser_initialization -v
```

## Expected Initial State (RED Phase)

All tests should initially **FAIL** with ImportError or NotImplementedError because:

1. `aromcp.analysis_server.tools.typescript_parser` module doesn't exist
2. `TypeScriptParser` class not implemented
3. Tool implementation functions not created
4. Models may exist but implementations are missing

This is the correct TDD RED phase - tests define the expected behavior before implementation.

## Implementation Guidelines

When implementing to pass these tests:

1. **Start with the parser core** - `TypeScriptParser` class
2. **Use tree-sitter-typescript** for parsing
3. **Implement LRU cache** for AST storage
4. **Follow FastMCP standards** for tool registration
5. **Use existing AroMCP patterns** from filesystem/build servers
6. **Implement tool stubs first** (empty results), then add functionality

## Performance Benchmarks

Tests validate these specific requirements:
- Parse speed: <2ms per 1000 lines of code
- Memory usage: <200MB for projects with ~1000 files
- Cache hit ratio: >90% for typical workloads
- Concurrent parsing safety

## Integration Points

Tests verify integration with:
- FastMCP server registration
- AroMCP shared utilities (pagination, security, JSON conversion)
- Main server tool namespace
- Existing filesystem/build server tools