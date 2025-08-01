# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AroMCP is a suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. The project aims to create "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making.

## Current State

**Implementation Status:**
- ✅ **Filesystem Server** - 3 tools: `list_files`, `read_files`, `write_files` with pagination and glob patterns
- ✅ **Build Server** - 3 tools: `check_typescript`, `lint_project`, `run_test_suite` with comprehensive automation
- ✅ **Analysis Server** - 3 tools: `find_references`, `get_function_details`, `analyze_call_graph` for TypeScript analysis
- ✅ **Standards Server** - 10 tools for intelligent coding standards management with 70-80% token reduction
- ✅ **Workflow Server** - 12 tools for workflow execution and persistent state management

## Architecture

Five implemented MCP servers:
1. **Filesystem Server** - File operations with glob patterns and pagination (3 tools)
2. **Build Server** - Build automation, linting, and testing (3 tools)
3. **Analysis Server** - TypeScript symbol resolution and call graph analysis (3 tools)
4. **Standards Server** - Intelligent coding standards with session management (10 tools)
5. **Workflow Server** - State management and workflow orchestration (12 tools)

## Development Guidelines

- **Language**: Python 3.12+ using the `fastmcp` SDK (not `mcp`)
- **Dependencies**: Minimal external dependencies, prefer stdlib
- **Security**: Implement input validation, path security, command whitelisting
- **Error Handling**: Use structured error responses with consistent format
- **Testing**: Each tool should have comprehensive unit tests
- **Code Formatting**: Always use `black` for consistent Python code formatting

## Development Commands

- **Install dependencies**: `uv sync --dev` (uses uv package manager)
- **Run individual servers**: `uv run python servers/{name}/main.py` (filesystem, build, analysis, standards, workflow)
- **Run tests**: `uv run pytest`
- **Run single test**: `uv run pytest tests/filesystem_server/test_list_files.py::TestListFiles::test_basic_functionality`
- **Code formatting**: `uv run black src/ tests/`
- **Linting**: `uv run ruff check src/ tests/`
- **Fix linting**: `uv run ruff check --fix src/ tests/`

**Note**: Always use `uv run` prefix for all Python commands to ensure proper virtual environment and dependency resolution.

## JavaScript Engine

The project uses **PythonMonkey** as the JavaScript engine for workflow transformations. PythonMonkey provides:
- Full ES6+ support including arrow functions, const/let, template literals, destructuring
- Modern JavaScript array methods (filter, map, reduce, etc.)
- Native Python-JavaScript interoperability
- Better performance than legacy engines

Falls back to Python-based evaluation for basic expressions when PythonMonkey is not available.

## Project Structure
- `src/aromcp/filesystem_server/tools/` - FileSystem tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for filesystem operations
  - `list_files.py` - File listing with glob pattern matching and pagination
  - `read_files.py` - Multi-file reading with encoding detection and pagination
  - `write_files.py` - Multi-file writing with automatic directory creation
- `src/aromcp/build_server/tools/` - Build tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for build operations
  - `lint_project.py` - ESLint integration for code style checking with pagination
  - `check_typescript.py` - TypeScript compiler error checking
  - `run_test_suite.py` - Execute test suites with result parsing and pagination
- `src/aromcp/analysis_server/tools/` - TypeScript analysis tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for analysis operations
  - `find_references.py` - Find TypeScript symbol references across projects
  - `get_function_details.py` - Extract detailed TypeScript function information
  - `analyze_call_graph.py` - Generate static call graphs for TypeScript code
- `src/aromcp/standards_server/` - Standards management with session-based optimization:
  - `tools/` - 10 tools for hints, rules, and session management
  - `models/` - Enhanced rule structures and compression models
  - `services/` - Session management and context-aware compression
  - `utils/` - Token optimization and example generation utilities
- `src/aromcp/workflow_server/` - Workflow execution and state management:
  - `tools/` - 12 tools for workflow orchestration and state persistence
  - `models/` - Workflow state and execution models
  - `services/` - Workflow execution engine and state management
- `servers/{name}/main.py` - Individual server entry points for each specialized server
- `tests/` - Comprehensive test suite organized by server:
  - `filesystem_server/` - Tests for file operations and pagination
  - `build_server/` - Tests for build automation and linting
  - `analysis_server/` - Tests for TypeScript analysis tools
  - `standards_server/` - Tests for standards management and session handling
  - `workflow_server/` - Tests for workflow execution and state management
  - `test_main_server.py` - Integration tests for server registration and tool validation

## Core Design Principles

1. **Separation of Concerns** - Each server has a single responsibility
2. **Token Efficiency** - Handle operations that would be expensive in AI context
3. **Project Agnostic** - Work with any project structure
4. **Stateless Operations** - Most operations stateless except state server
5. **Batch Operations** - Support batch operations to reduce round trips
6. **Individual Server Architecture** - Specialized servers for focused functionality and independent scaling
7. **Parameter Flexibility** - JSON parameter middleware handles type conversion automatically

## Server Configuration

- Uses FastMCP server for this project
- ESLint rule generation handled via Claude Code commands at `documentation/commands/generate-eslint-rules.md`

## Key Architectural Components

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
**All tools follow the FastMCP Standards above** and use this pattern for list-returning tools:

```python
@mcp.tool
@json_convert  # Required per FastMCP Standards
def tool_name(
    # Core parameters with union types per FastMCP Standards
    file_paths: str | list[str],  # Support both single and multiple
    project_root: str | None = None,  # Auto-resolve to MCP_FILE_ROOT if None
    # Feature flags
    expand_patterns: bool = True,  # Enable glob pattern expansion
    # Pagination parameters (for tools returning lists)
    page: int = 1,  # Page number (1-based)
    max_tokens: int = 20000  # Maximum tokens per page
) -> MyToolResponseModel:  # Use typed dataclass per FastMCP Standards
    # Resolve project root using new pattern
    project_root = get_project_root(project_root)

    # Implementation that collects items...
    items = collect_items()

    # For list-returning tools, use pagination
    from ...utils.pagination import paginate_list
    metadata = {"summary": summary_data}
    paginated_result = paginate_list(
        items=items,
        page=page,
        max_tokens=max_tokens,
        sort_key=lambda x: x.get("sort_field"),  # Deterministic sorting
        metadata=metadata
    )

    # Return typed response
    return MyToolResponseModel(**paginated_result)
```

**Key patterns**:
- **Follow FastMCP Standards** - Use `@json_convert`, union types, and typed responses
- **ALWAYS use MCP_FILE_ROOT** - Do not include `project_root` parameters in new tools
- Support both single strings and lists for file paths where appropriate
- Use `expand_patterns=True` for glob pattern support
- **Add pagination parameters** (`page`, `max_tokens`) for tools returning lists
- **Use `paginate_list()`** with appropriate sort key for deterministic ordering
- **Return typed dataclass models** instead of raw dictionaries


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
- **IMPORTANT**: When adding new tools, **ALWAYS update `tests/test_main_server.py`** to include the new tool names in the expected tools lists. This ensures the server registration tests validate all tools are properly implemented.

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

## FastMCP Standards (Updated 2025-07-18)

FastMCP 2.10+ requires adherence to these four critical standards for proper MCP integration:

### 1. Use @json_convert for Complex Parameters
**Always apply `@json_convert` decorator** for tools accepting lists or dictionaries:

```python
from ...utils.json_parameter_middleware import json_convert

@mcp.tool
@json_convert  # Required for all tools with complex type parameters
def my_tool(patterns: str | list[str]) -> dict[str, Any]:
    # patterns will be proper list, even if passed as JSON string
    return {"result": patterns}
```

### 2. Use str Union Types for Complex Inputs
**All complex parameters must include `str` in union types** for FastMCP validation:

```python
@mcp.tool
@json_convert
def my_tool(
    # For list parameters - MUST include str option
    file_paths: str | list[str],  # NOT just list[str]

    # For dict parameters - MUST include str option
    metadata: dict[str, Any] | str,  # NOT just dict[str, Any]

    # For complex nested types - MUST include str option
    diffs: list[dict[str, Any]] | str,  # NOT just list[dict[str, Any]]

    # Simple types don't need str unions
    project_root: str | None = None,  # str types are fine as-is
) -> dict[str, Any]:
```

**Why this is required**:
- FastMCP validates parameter types before passing to tools
- MCP clients pass complex parameters as JSON strings
- `@json_convert` converts JSON strings to native types after FastMCP validation
- Without `str` in union type, FastMCP rejects JSON strings before conversion

### 3. Use Type Casting Instead of Manual Parsing
**Use simple type casting instead of manual serialize_for_json() calls**:

```python
# PREFERRED: Simple type casting
@mcp.tool
def workflow_start(workflow: str, inputs: dict[str, Any] | str | None = None) -> WorkflowStartResponse:
    result = executor.start(workflow_def, inputs)

    # Simple type casting - let FastMCP handle serialization
    return WorkflowStartResponse(
        workflow_id=str(result.workflow_id),
        status=result.status,
        state=dict(result.state),
        total_steps=int(result.total_steps),
        execution_context=dict(result.execution_context)
    )

# AVOID: Manual serialization complexity
def old_pattern():
    serialized_result = serialize_for_json(result)  # Don't do this
    return WorkflowStartResponse(**serialized_result)
```

### 4. Use Typed Responses from Model Files
**Define output schemas using dataclasses** in `models/` directories:

```python
# In src/aromcp/workflow_server/models/workflow_models.py
@dataclass
class WorkflowStartResponse:
    workflow_id: str
    status: str
    state: dict[str, Any]
    total_steps: int
    execution_context: dict[str, Any]

# In tool files - import and use typed responses
from ..models.workflow_models import WorkflowStartResponse

@mcp.tool
def workflow_start(...) -> WorkflowStartResponse:
    # Implementation returns typed dataclass
    return WorkflowStartResponse(...)
```

### Directory Structure for Output Models
```
src/aromcp/
├── filesystem_server/
│   ├── models/
│   │   ├── __init__.py
│   │   └── filesystem_models.py
│   └── tools/
├── workflow_server/
│   ├── models/
│   │   ├── __init__.py
│   │   └── workflow_models.py
│   └── tools/
└── build_server/
    ├── models/
    │   ├── __init__.py
    │   └── build_models.py
    └── tools/
```

### Quick Type Conversion Reference
- **DateTime objects**: Use `.isoformat()` → strings
- **DataClass objects**: Use `asdict()` → dictionaries
- **Enum objects**: Use `.value` → underlying values
- **Complex objects**: Convert to basic types (str, int, dict, list)

## Development Memories

- Always use `uv run` prefix for all Python commands to ensure proper virtual environment
- **Follow FastMCP Standards** - Use `@json_convert`, union types with `str`, type casting, and typed responses (see FastMCP Standards section above)
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
- **Remember fastmcp LLM friendly documentation can be found here: https://gofastmcp.com/llms.txt This is a sitemap of places to get docs. Always load this into memory if you are working on fastmcp specific logic. It will require reading and then loading as neccessary. Always prioritize loading fastmcp documentation when working on fastmcp**


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

# Specialized Development Agents

This project benefits from specialized agents that provide battle-tested patterns for TDD, code analysis, and systematic refactoring.

## Available Agents

### Implementation Agents
- **@tdd-code-writer**: Implements code to satisfy tests following TDD principles. Analyzes failing tests, writes minimal code to pass, then refactors for clarity.
- **@technology-specialist**: Researches proven patterns from industry leaders. Discovers production-ready solutions and documents them for future reference.
- **@codebase-specialist**: Maps architecture and traces code flows. Provides deep understanding of code relationships and dependencies.

### Testing & Quality Agents
- **@tdd-test-writer**: Creates comprehensive test suites from requirements. Translates acceptance criteria into failing tests that drive development.
- **@acceptance-criteria-agent**: Generates testable acceptance criteria from code or requirements. Maintains living documentation synchronized with implementation.
- **@automated-code-reviewer**: Performs security and quality analysis. Reviews code against best practices, identifies vulnerabilities, and suggests improvements.

## TDD Workflow

These agents work together in a structured Test-Driven Development flow:

1. **Requirements Analysis**: The @acceptance-criteria-agent analyzes requirements or existing code to generate clear, testable acceptance criteria.

2. **Test Creation**: The @tdd-test-writer takes these criteria and creates comprehensive failing tests that cover:
   - Happy path scenarios
   - Edge cases and error conditions
   - Performance requirements
   - Integration behaviors

3. **Implementation**: The @tdd-code-writer analyzes the failing tests and implements the minimal code needed to make them pass, focusing on:
   - Understanding test expectations
   - Writing clean, maintainable solutions
   - Handling all tested scenarios

4. **Refactoring**: Once tests pass, the code writer refactors for:
   - Better structure and organization
   - Performance optimization
   - Code reusability
   - Consistent patterns

5. **Validation**: The test writer validates the implementation against acceptance criteria and provides feedback if gaps exist.

6. **Review**: The @automated-code-reviewer performs final quality checks for security, performance, and maintainability.

## Agent Philosophy

- **Test Readability > DRY**: One clear test per behavior, prioritizing clarity over abstraction
- **Phased Implementation**: Complex work broken into validated phases
- **Research First**: Analyze multiple approaches before recommending solutions
- **Aggressive Deletion**: Remove obsolete code when backwards compatibility isn't needed
- **Continuous Validation**: Every phase must pass tests before proceeding
- **Living Documentation**: Acceptance criteria stay synchronized with code

## Best Practices

1. **Clear Acceptance Criteria**: Start with well-defined, testable requirements
2. **Test-First Development**: Always write tests before implementation
3. **Small Iterations**: Work in small, verifiable increments
4. **Continuous Integration**: Validate changes frequently
5. **Documentation as Code**: Keep acceptance criteria in version control

The agents excel at systematic, thorough work. They follow a disciplined approach that ensures quality through comprehensive testing and validation at every step.