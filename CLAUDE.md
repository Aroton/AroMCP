# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AroMCP is a suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. The project aims to create "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making.

## Current State

**Implementation Status:**
- ✅ **Phase 1: FileSystem Tools** - 6 simplified tools with file I/O, diff operations, code analysis
- ✅ **Phase 2: Build Tools** - 3 simplified tools with linting, TypeScript checking, test execution
- ✅ **Phase 4: Code Analysis Tools** - 3 tools implemented (find_dead_code, find_import_cycles, extract_api_endpoints)
- ⚠️ Phases 3, 5-6: Other tool categories are stub implementations

## Architecture

Six main tool categories:
1. **FileSystem Tools** - Simplified file operations, code parsing, diff validation
2. **Build Tools** - Simplified lint, TypeScript, and test execution
4. **Code Analysis Tools** - Standards-driven analysis, security detection, quality checks
5. **Context Window Management Tools** - Token optimization (planned)
6. **Interactive Debugging Tools** - Debugging utilities (planned)

## Development Guidelines

- **Language**: Python 3.12+ using the `fastmcp` SDK (not `mcp`)
- **Dependencies**: Minimal external dependencies, prefer stdlib
- **Security**: Implement input validation, path security, command whitelisting
- **Error Handling**: Use structured error responses with consistent format
- **Testing**: Each tool should have comprehensive unit tests

## Development Commands

- **Install dependencies**: `uv sync --dev` (uses uv package manager)
- **Run server**: `uv run python main.py` or `uv run python -m src.aromcp.main_server`
- **Run tests**: `uv run pytest`
- **Run single test**: `uv run pytest tests/filesystem_server/test_list_files.py::TestListFiles::test_basic_functionality`
- **Code formatting**: `uv run black src/ tests/`
- **Linting**: `uv run ruff check src/ tests/`
- **Fix linting**: `uv run ruff check --fix src/ tests/`

**Note**: Always use `uv run` prefix for all Python commands to ensure proper virtual environment and dependency resolution.

## Project Structure

- `src/aromcp/main_server.py` - Unified FastMCP server that combines all tools
- `src/aromcp/filesystem_server/tools/` - FileSystem tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for filesystem operations
  - `list_files.py` - File listing with glob pattern matching
  - `read_files.py` - Multi-file reading with encoding detection and pagination
  - `write_files.py` - Multi-file writing with automatic directory creation
  - `extract_method_signatures.py` - AST-based code signature extraction
  - `find_who_imports.py` - Import dependency analysis
- `src/aromcp/build_server/tools/` - Build tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for build operations
  - `lint_project.py` - ESLint integration for code style checking
  - `check_typescript.py` - TypeScript compiler error checking
  - `run_test_suite.py` - Execute test suites with result parsing
- `src/aromcp/analysis_server/tools/` - Code analysis tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for analysis operations
  - `find_dead_code.py` - Identify unused code that can be removed
  - `find_import_cycles.py` - Detect circular import dependencies
  - `extract_api_endpoints.py` - Document API endpoints from route files
- `main.py` - Entry point that imports and runs the main server
- `tests/filesystem_server/` - Modular test suite with separate files per test class:
  - `test_list_files.py` - Tests for file listing and pattern matching
  - `test_read_files.py` - Tests for multi-file reading operations with pagination
  - `test_write_files.py` - Tests for multi-file writing operations
  - `test_extract_method_signatures.py` - Tests for code signature extraction
  - `test_find_who_imports.py` - Tests for import dependency analysis
  - `test_security_validation.py` - Tests for security measures across all tools
- `tests/analysis_server/` - Analysis server test suite with modular structure

## Core Design Principles

1. **Separation of Concerns** - Each server has a single responsibility
2. **Token Efficiency** - Handle operations that would be expensive in AI context
3. **Project Agnostic** - Work with any project structure
4. **Stateless Operations** - Most operations stateless except state server
5. **Batch Operations** - Support batch operations to reduce round trips
6. **Unified Server Architecture** - Single FastMCP server hosts all tools for simplified deployment
7. **Parameter Flexibility** - JSON parameter middleware handles type conversion automatically

## Server Configuration

- Uses FastMCP server for this project
- ESLint rule generation handled via Claude Code commands at `documentation/commands/generate-eslint-rules.md`

## Key Architectural Components

### JSON Parameter Middleware (`src/aromcp/utils/json_parameter_middleware.py`)

**Critical for MCP integration**: This middleware automatically converts JSON string parameters from MCP clients (like Claude Code) to proper Python types. This solves the common issue where list/dict parameters are passed as JSON strings instead of native types.

**Usage in tools**:
```python
from ...utils.json_parameter_middleware import json_convert

@mcp.tool
@json_convert  # Automatically converts JSON strings to Python types
def my_tool(patterns: list[str]) -> dict[str, Any]:
    # patterns will be a proper list, even if passed as JSON string
    return {"result": patterns}
```

**Key benefits**:
- Automatic type conversion based on function signatures
- Handles Union types (e.g., `str | list[str]`, `list[str] | None`)
- Structured error responses for invalid JSON
- Debug mode available for troubleshooting

### Security Module (`src/aromcp/filesystem_server/_security.py`)

**Path validation and project root management**:
- `validate_file_path()` - Modern validation with structured error responses
- `validate_file_path_legacy()` - Backward-compatible validation for existing tools
- `get_project_root(project_root: str | None = None)` - Environment-based project root resolution from `MCP_FILE_ROOT`

**Security features**:
- Directory traversal protection
- Path resolution validation
- Project root boundary enforcement

## Implementation Conventions

### Code Organization
- **Modular Architecture**: Each tool category has its own directory under `src/aromcp/`
- **Unified Structure**: Each tool category has a `tools/` directory containing both registration and implementations
- **Individual Tool Files**: Each tool has its own implementation file (e.g., `get_target_files.py`)
- **Registration in __init__.py**: Tool implementations are imported and registered in `tools/__init__.py`

### Function Naming Convention
- **Registration Functions**: `register_[category]_tools(mcp)` in `tools/__init__.py` files
- **Implementation Functions**: `[tool_name]_impl(...)` for actual implementation
- **Helper Functions**: Private functions prefixed with `_` (e.g., `_validate_file_path()`)

### Parameter Handling Patterns
**All tools that return lists follow this pattern**:
```python
@mcp.tool
@json_convert  # Always use for list/dict parameters
def tool_name(
    # Core parameters first
    file_paths: str | list[str],  # Support both single and multiple
    project_root: str | None = None,  # Auto-resolve to MCP_FILE_ROOT if None
    # Feature flags
    expand_patterns: bool = True,  # Enable glob pattern expansion
    # Tool-specific parameters
    ...
    # Pagination parameters (for tools returning lists)
    page: int = 1,  # Page number (1-based)
    max_tokens: int = 20000  # Maximum tokens per page
) -> dict[str, Any]:
    # Resolve project root using new pattern
    project_root = get_project_root(project_root)

    # Implementation that collects items...
    items = collect_items()

    # For list-returning tools, use pagination
    from ...utils.pagination import paginate_list
    metadata = {"summary": summary_data}
    return paginate_list(
        items=items,
        page=page,
        max_tokens=max_tokens,
        sort_key=lambda x: x.get("sort_field"),  # Deterministic sorting
        metadata=metadata
    )
```

**Key patterns**:
- **ALWAYS use MCP_FILE_ROOT** - Do not include `project_root` parameters in new tools
- Support both single strings and lists for file paths where appropriate
- Use `expand_patterns=True` for glob pattern support
- Apply `@json_convert` decorator for all tools accepting lists/dicts
- **Add pagination parameters** (`page`, `max_tokens`) for tools returning lists
- **Use `paginate_list()`** with appropriate sort key for deterministic ordering
- **Preserve metadata** in pagination response

### FastMCP Parameter Type Requirements
**Critical for FastMCP compatibility**: All `@mcp.tool` parameters that accept complex types (lists, dicts) must be declared with union types to support both native types and JSON strings from MCP clients.

**Required parameter patterns**:
```python
@mcp.tool
@json_convert  # Required for all tools with complex type parameters
def my_tool(
    # For list parameters - MUST include str option for FastMCP validation
    file_paths: str | list[str],  # NOT just list[str]
    patterns: list[str] | None = None,  # Optional lists need str support too

    # For dict parameters - MUST include str option for FastMCP validation
    metadata: dict[str, Any] | str,  # NOT just dict[str, Any]
    updates: dict[str, Any] | str | None = None,  # Optional dicts need str support too

    # For complex nested types - MUST include str option
    diffs: list[dict[str, Any]] | str,  # NOT just list[dict[str, Any]]

    # Simple types don't need union types
    project_root: str | None = None,  # str types are fine as-is
    count: int = 1,  # primitive types don't need str unions
) -> dict[str, Any]:
```

**Why this is required**:
- FastMCP validates parameter types before passing to tools
- MCP clients (like Claude Code) pass complex parameters as JSON strings
- `@json_convert` middleware converts JSON strings to native types after FastMCP validation
- Without `str` in the union type, FastMCP rejects the JSON string before conversion

**Key rules**:
- **ALWAYS** use `str | list[str]` instead of `list[str]` for list parameters
- **ALWAYS** use `dict[str, Any] | str` instead of `dict[str, Any]` for dict parameters
- **ALWAYS** use `list[dict[...]] | str` instead of `list[dict[...]]` for complex list parameters
- **ALWAYS** apply `@json_convert` decorator when using union types with complex types
- Simple types (`str`, `int`, `bool`) don't need `str` unions

### Project Root Resolution Pattern
The updated `get_project_root()` function now accepts an optional parameter:
```python
def get_project_root(project_root: str | None = None) -> str:
```

**Usage pattern**: Replace old pattern `if project_root is None: project_root = get_project_root()` with:
```python
project_root = get_project_root(project_root)
```

### Error Handling Standards
All tools must follow consistent error response format:
```python
# Success Response
{
    "data": {
        # Tool-specific data structure
    }
}

# Error Response
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Detailed error message"
    }
}
```

**Standard Error Codes:**
- `INVALID_INPUT`: Parameter validation failed
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Security check failed
- `OPERATION_FAILED`: Operation failed to complete
- `TIMEOUT`: Operation timed out
- `UNSUPPORTED`: Feature not supported

### Security Requirements
- **Path Validation**: All file operations must validate paths to prevent directory traversal
- **Input Sanitization**: Validate all input parameters with appropriate type checking
- **Resource Limits**: Implement reasonable limits (file size, operation timeouts)
- **Error Information**: Never expose sensitive system information in error messages

### Testing Standards
- **Modular Test Structure**: Each test class has its own file (e.g., `test_get_target_files.py` for `TestGetTargetFiles`)
- **Comprehensive Coverage**: Each tool should have multiple test scenarios covering:
  - Happy path functionality
  - Parameter variations (optional parameters, different values)
  - Error conditions and edge cases
  - Security validation (path traversal protection)
  - Performance considerations (large files, empty inputs)
- **Test Organization**: Tests organized by tool in classes like `TestToolName`, with one class per file
- **Descriptive Test Names**: Test method names should clearly describe what is being tested
- **Isolated Tests**: Each test should be independent and use temporary directories
- **Security Testing**: Dedicated `test_security_validation.py` file for cross-tool security validation
- **IMPORTANT**: When adding new tools, **ALWAYS update `tests/test_main_server.py`** to include the new tool names in the expected tools lists. This ensures the unified server test validates all tools are properly registered.

### Type Annotations
- **Modern Python Types**: Use `dict[str, Any]` instead of `Dict[str, Any]`
- **Optional Parameters**: Use `list[str] | None` instead of `Optional[List[str]]`
- **Comprehensive Typing**: All function parameters and return types should be annotated

### Documentation Standards
- **Docstrings**: All public functions must have comprehensive docstrings with Args and Returns sections
- **Parameter Documentation**: FastMCP tool decorators should include parameter descriptions
- **Usage Examples**: README.md should contain practical examples for each tool
- **Implementation Notes**: Complex logic should include inline comments explaining the approach

### Tool Description Standards (Added 2025-07-09)
All tool descriptions must follow this enhanced template to improve AI agent discovery:

```python
@mcp.tool
def tool_name(...) -> dict[str, Any]:
    """
    [One-line summary of what the tool does]

    Use this tool when:
    - [Specific scenario when this tool is appropriate]
    - [Another specific use case]
    - [Third scenario differentiating from similar tools]
    - [Fourth scenario if applicable]

    Replaces bash commands: [command1, command2, command3]

    Args:
        param1: [Clear description with example values]
        param2: [Description with valid options listed]

    Example:
        tool_name("example_input")
        → ["result1", "result2", "result3"]

    Note: [Cross-references to related tools or important caveats]
    """
```

**Key requirements for tool descriptions**:
- **"Use this tool when" section is mandatory** - 3-5 specific scenarios
- **Examples must show realistic input/output** - Not abstract placeholders
- **Note section should reference related tools** - Help agents choose correctly
- **Differentiate from similar tools** - e.g., read_files vs load_project_documents

### Simplified Tool Aliases
The project uses simplified tool aliases as the primary interface for AI agents:
- **Prefer simplified names**: `lint_project` over `parse_lint_results`
- **Use 2-3 parameters**: Simplified tools have sensible defaults
- **Include "Perfect for..." phrases**: Quick understanding of use cases
- **Keep original tools**: For backward compatibility and advanced use


## Testing Architecture

**Modular test structure** - Each tool has its own test file matching the pattern `test_[tool_name].py`:
- Tests organized in classes like `TestGetTargetFiles`
- One test class per file for better organization
- Comprehensive coverage including happy path, edge cases, and security validation
- Isolated tests using temporary directories and cleanup

**Key test utilities**:
- `pytest` fixtures for temporary directories and sample files
- Security validation tests in dedicated `test_security_validation.py`
- Cross-tool integration tests for workflows
- Performance tests for large file operations

**Running tests**:
```bash
# All tests
uv run pytest

# Specific test file
uv run pytest tests/filesystem_server/test_get_target_files.py

# Specific test method
uv run pytest tests/filesystem_server/test_get_target_files.py::TestGetTargetFiles::test_basic_functionality

# With verbose output
uv run pytest -v

# With coverage
uv run pytest --cov=src/aromcp
```

## Pagination Support

All list-returning tools support pagination to stay under 20k token limits:

**Implementation (`src/aromcp/utils/pagination.py`)**:
- Token-based sizing (1 token ≈ 4 characters)
- Deterministic ordering via sort keys
- Binary search optimization for page size

**Parameters**: All paginated tools accept `page` (default: 1) and `max_tokens` (default: 20000)

## Development Memories

- Always use `uv run` prefix for all Python commands to ensure proper virtual environment
- Apply `@json_convert` decorator to all tools that accept list/dict parameters
- **ALWAYS use MCP_FILE_ROOT** - Do not include `project_root` parameters in new tools
- Use `validate_file_path_legacy()` for consistent path security validation
- Implement comprehensive error handling with structured error responses
- ESLint rule generation is now handled via Claude Code commands for better AI-driven rule creation
- The command documentation is at `documentation/commands/generate-eslint-rules.md`
- **All list-returning tools now support pagination** - Use `page` and `max_tokens` parameters for large result sets
- Pagination maintains deterministic ordering and includes comprehensive metadata
- Token estimation uses conservative 4:1 character ratio to stay under 20k token limit
- **Line length is 120 characters**
- **Ignore linting errors that are intentional**

## Workflow System

### Workflow Schema Update Locations
When updating the MCP workflow schema, ensure all of the following locations are updated:

1. **Command Documentation**: `.claude/commands/workflow:generate.md`
   - Update the "Workflow YAML Schema Reference" section
   - Add new step types or modify existing ones
   - Update examples and patterns

2. **Validation Script**: `scripts/validate_workflow.py`
   - Add new step types to `VALID_STEP_TYPES`
   - Add validation methods for new step types (e.g., `_validate_new_step_type()`)
   - Update any validation logic for schema changes

3. **Validation Tests**: `tests/test_workflow_validation.py`
   - Add tests for new step types
   - Update existing tests if schema changes affect them
   - Add edge cases for new features

4. **Example Workflows**: `.aromcp/workflows/*.yaml`
   - Update existing workflows to use new features if beneficial
   - Create example workflows demonstrating new capabilities

5. **Workflow Documentation**: `.aromcp/workflows/*.README.md`
   - Update documentation for workflows using new features
   - Add examples of new step types or parameters

### Workflow Validation
- **Validate workflows**: `uv run python scripts/validate_workflow.py <workflow.yaml>`
- **Run validation tests**: `uv run pytest tests/test_workflow_validation.py -v`
- Always validate generated workflows before committing

## Tool Discovery and Agent Guidance (Added 2025-07-09)

### Primary Tool Recommendations
When implementing AI agent features, prefer these simplified tools:
- **File Operations**: `list_files`, `read_files`, `write_files`
- **Quality Checks**: `lint_project`, `check_typescript`, `run_tests`
- **Code Analysis**: `find_who_imports`, `find_dead_code`, `find_import_cycles`
- **Commands**: `execute_command` (instead of `run_command`)
- **Composite**: `quality_check` (runs lint + TypeScript + tests)

### Common Workflows
Implement these patterns for common tasks:

```python
# Pre-commit validation
1. lint_project()      # Check code style
2. check_typescript()  # Verify types
3. run_tests()        # Ensure tests pass

# Safe file modification
1. read_files(target)  # Always read first
2. write_files(...)    # Make changes
3. lint_project()      # Verify quality

# Dependency analysis before deletion
1. find_who_imports(file)  # Check dependencies
2. if no imports: safe to delete
```

### Tool Naming Patterns
- **Action-Target format**: `find_dead_code`, `check_dependencies`, `run_tests`
- **Avoid generic names**: Not "analyze" or "process"
- **Clear differentiation**: `read_files` for code, `load_project_documents` for docs

### Documentation Locations
- **Tool Selection Guide**: See `TOOL_GUIDE.md` for decision trees and workflows
- **Agent Guidance**: `src/aromcp/utils/agent_guidance.py` (for reference only)
- **Tool Categories**: Defined in `pyproject.toml` under `[tool.aromcp]`