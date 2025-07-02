# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AroMCP is a suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. The project aims to create "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making.

## Current State

The project has a functional MCP server architecture with **Phase 1: FileSystem Tools** fully implemented. The main server (`src/aromcp/main_server.py`) unifies all MCP servers into a single FastMCP instance. FileSystem tools are production-ready with comprehensive functionality.

**Implementation Status:**
- ✅ Server architecture and tool signatures complete
- ✅ FastMCP integration working with JSON parameter middleware
- ✅ **Phase 1: FileSystem Tools - FULLY IMPLEMENTED**
  - ✅ All 9 filesystem tools implemented with full functionality
  - ✅ Comprehensive input validation, error handling, and security measures
  - ✅ Path traversal protection and encoding safety
  - ✅ Batch operations and atomic file writing with backup support
  - ✅ Diff operations (apply, preview, validate) with rollback support
  - ✅ JSON parameter middleware for automatic type conversion
- ✅ **Phase 2: Build Tools - FULLY IMPLEMENTED**
  - ✅ All 7 build tools implemented with full functionality
  - ✅ Command whitelisting and security validation
  - ✅ Structured output parsing for TypeScript, ESLint, tests
  - ✅ Multi-package manager support (npm, yarn, pnpm)
  - ✅ Specialized Next.js build handling with categorized error reporting
- ✅ **Phase 4: Code Analysis Tools - FULLY IMPLEMENTED**
  - ✅ All 8 analysis tools implemented with full functionality
  - ✅ Standards management and pattern-based matching
  - ✅ Context-aware standard loading based on file patterns
  - ✅ Security vulnerability detection (SQL injection, hardcoded secrets, etc.)
  - ✅ Code quality analysis (dead code, import cycles, component usage)
  - ✅ Standards parsing for AI-driven ESLint rule generation
- ⚠️ Phases 3, 5-6: Other tool categories are stub implementations (return empty/placeholder data)

## Planned Architecture

The project consists of six main tool categories:

1. **FileSystem Tools** - File I/O operations, git operations, code parsing, diff validation
2. **Build Tools** - Build, lint, test, and validation commands (COMPLETED)
3. **State Management Tools** - Persistent state management for long-running processes
4. **Code Analysis Tools** - Deterministic code analysis operations
5. **Context Window Management Tools** - Token usage tracking and optimization
6. **Interactive Debugging Tools** - Debugging utilities and error investigation

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
- **Run single test**: `uv run pytest tests/filesystem_server/test_get_target_files.py::TestGetTargetFiles::test_basic_functionality`
- **Code formatting**: `uv run black src/ tests/`
- **Linting**: `uv run ruff check src/ tests/`
- **Fix linting**: `uv run ruff check --fix src/ tests/`

**Note**: Always use `uv run` prefix for all Python commands to ensure proper virtual environment and dependency resolution.

## Project Structure

- `src/aromcp/main_server.py` - Unified FastMCP server that combines all tools
- `src/aromcp/filesystem_server/tools/` - FileSystem tools with registration and implementations:
  - `__init__.py` - FastMCP tool registration for filesystem operations
  - `get_target_files.py` - File listing with git integration and pattern matching
  - `read_files_batch.py` - Multi-file reading with encoding detection
  - `write_files_batch.py` - Atomic multi-file writing with backup support
  - `extract_method_signatures.py` - AST-based code signature extraction
  - `find_imports_for_files.py` - Import dependency analysis
  - `load_documents_by_pattern.py` - Pattern-based document loading with type classification
  - `apply_file_diffs.py` - Apply unified diffs with validation and rollback
  - `preview_file_changes.py` - Preview diff changes before applying
  - `validate_diffs.py` - Pre-validate diffs for conflicts and syntax
- `src/aromcp/state_server/tools.py` - Persistent state management tools (planned)
- `src/aromcp/build_server/tools.py` - Build, lint, test execution tools (planned)
- `src/aromcp/analysis_server/tools/` - Code analysis tools with registration and implementations
- `main.py` - Entry point that imports and runs the main server
- `tests/filesystem_server/` - Modular test suite with separate files per test class:
  - `test_get_target_files.py` - Tests for file listing and pattern matching
  - `test_read_files_batch.py` - Tests for multi-file reading operations
  - `test_write_files_batch.py` - Tests for atomic file writing operations
  - `test_extract_method_signatures.py` - Tests for code signature extraction
  - `test_find_imports_for_files.py` - Tests for import dependency analysis
  - `test_load_documents_by_pattern.py` - Tests for document loading and classification
  - `test_security_validation.py` - Tests for security measures across all tools
  - `test_diff_operations.py` - Tests for diff operations (apply, preview, validate)

## Core Design Principles

1. **Separation of Concerns** - Each server has a single responsibility
2. **Token Efficiency** - Handle operations that would be expensive in AI context
3. **Project Agnostic** - Work with any project structure
4. **Stateless Operations** - Most operations stateless except state server
5. **Batch Operations** - Support batch operations to reduce round trips
6. **Unified Server Architecture** - Single FastMCP server hosts all tools for simplified deployment
7. **Parameter Flexibility** - JSON parameter middleware handles type conversion automatically

## Environment Variables

```
MCP_STATE_BACKEND=file|redis|postgres
MCP_STATE_PATH=/path/to/state/storage
MCP_FILE_ROOT=/path/to/project/root
MCP_SECURITY_LEVEL=strict|standard|permissive
MCP_LOG_LEVEL=debug|info|warn|error
```

## Documentation Structure

The project follows a structured documentation approach with the main README.md serving as an index to detailed documentation:

### Main Documentation Files
- `README.md` - Project overview, installation, quick start, and index to detailed documentation
- `CLAUDE.md` - Development guidelines and instructions for Claude Code (this file)
- `documentation/simplify-workflow.md` - Main technical design and architecture specifications

### Usage Documentation
- `documentation/usage/filesystem_tools.md` - Comprehensive usage guide for all FileSystem tools with examples
- `documentation/usage/analysis_tools.md` - Comprehensive usage guide for all Code Analysis tools with examples
- `documentation/commands/` - Claude Code command documentation for AI-driven features
- Additional usage guides will be added as new tool categories are implemented

### Documentation Standards
- **README.md**: Keep concise with overview and links to detailed documentation
- **Usage Guides**: Detailed examples, parameters, and practical usage patterns for each tool category
- **Technical Documentation**: Architecture, design decisions, and implementation specifications
- **Cross-References**: All documentation should link to related files to create a connected knowledge base

## Claude Code Commands

Some advanced features are implemented as Claude Code commands rather than MCP tools:

- **ESLint Rule Generation**: Use the command at `documentation/commands/generate-eslint-rules.md` 
  for AI-driven rule generation from your coding standards. This provides more intelligent 
  rule creation than deterministic pattern matching.

Commands offer several advantages:
- AI understanding of standards intent and context
- Complex semantic rule generation beyond pattern matching
- Better handling of edge cases and nuanced requirements
- Dynamic adaptation to project-specific patterns

## Server Configuration

- We use FastMCP server for this project. Always load the documentation index: https://gofastmcp.com/llms.txt - Only load documentation through *.md files located in llms.txt. DO NOT LOAD HTML PAGES.

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
- `get_project_root()` - Environment-based project root resolution from `MCP_FILE_ROOT`

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
**All FileSystem tools follow this pattern**:
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
) -> dict[str, Any]:
    if project_root is None:
        project_root = get_project_root()
    # Implementation...
```

**Key patterns**:
- Always default `project_root` to `None` and resolve using `get_project_root()`
- Support both single strings and lists for file paths where appropriate
- Use `expand_patterns=True` for glob pattern support
- Apply `@json_convert` decorator for all tools accepting lists/dicts

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

### Type Annotations
- **Modern Python Types**: Use `dict[str, Any]` instead of `Dict[str, Any]`
- **Optional Parameters**: Use `list[str] | None` instead of `Optional[List[str]]`
- **Comprehensive Typing**: All function parameters and return types should be annotated

### Documentation Standards
- **Docstrings**: All public functions must have comprehensive docstrings with Args and Returns sections
- **Parameter Documentation**: FastMCP tool decorators should include parameter descriptions
- **Usage Examples**: README.md should contain practical examples for each tool
- **Implementation Notes**: Complex logic should include inline comments explaining the approach

## FileSystem Tools (Phase 1) - Production Ready

The FileSystem tools are fully implemented and provide comprehensive file operations optimized for AI-driven workflows. All tools include:

### Available Tools
1. **get_target_files** - File listing with git integration and glob pattern matching
2. **read_files_batch** - Multi-file reading with automatic encoding detection
3. **write_files_batch** - Atomic multi-file writing with backup support and directory creation
4. **extract_method_signatures** - AST-based code parsing for Python and regex for JavaScript/TypeScript
5. **find_imports_for_files** - Import dependency analysis across multiple languages
6. **load_documents_by_pattern** - Pattern-based document loading with automatic type classification
7. **apply_file_diffs** - Apply unified diffs with validation and rollback support
8. **preview_file_changes** - Preview diff changes before applying with impact analysis
9. **validate_diffs** - Pre-validate diffs for conflicts, syntax, and applicability

### Key Features
- **Security**: Path traversal protection, input validation, file size limits
- **Performance**: Batch operations, atomic transactions, efficient encoding detection
- **Multi-language**: Python AST parsing, JavaScript/TypeScript regex parsing, generic text analysis
- **Error Resilience**: Structured error responses, graceful failure handling
- **Automation**: Automatic directory creation, backup management, encoding detection
- **Metadata**: Rich file metadata (size, modification time, line/word counts, file types)
- **Diff Operations**: Unified diff format support with validation, preview, and rollback capabilities

### Usage Patterns
```python
# Common workflow: Find, Read, Analyze, Write
files = get_target_files(status="pattern", patterns=["**/*.py"])
content = read_files_batch(file_paths=[f["path"] for f in files["data"]["files"]])

# Multi-file signature extraction with pattern support
signatures = extract_method_signatures(file_paths=["src/**/*.py"])

# Batch operations for efficiency
write_files_batch(files={
    "output/analysis.json": json.dumps(signatures),
    "output/files.json": json.dumps(files)
})

# Diff workflow with validation
diffs = [{"file_path": "src/main.py", "diff_content": "..."}]
validation = validate_diffs(diffs)  # Pre-validate
if validation["data"]["valid"]:
    preview = preview_file_changes(diffs)  # Preview changes
    result = apply_file_diffs(diffs, create_backup=True)  # Apply with backup
```

**Modern tool capabilities**:
- All tools support glob patterns (e.g., `**/*.py`, `src/**/test_*.py`)
- Multi-file operations are batch-optimized
- Tools auto-resolve project root from environment
- JSON parameters are automatically converted from strings

See `documentation/usage/filesystem_tools.md` for detailed usage examples and parameter documentation.

## Code Analysis Tools (Phase 4) - Production Ready

The Code Analysis Tools are fully implemented and provide comprehensive code analysis operations with a focus on standards-driven development. All tools include:

### Available Tools
1. **load_coding_standards** - Load all coding standards from the project with metadata
2. **get_relevant_standards** - Get coding standards relevant to a specific file based on patterns
3. **parse_standard_to_rules** - Parse markdown standards to extract enforceable rules
4. **detect_security_patterns** - Detect security vulnerabilities (SQL injection, hardcoded secrets)
5. **find_dead_code** - Find unused exports, functions, and orphaned files
6. **find_import_cycles** - Detect circular import dependencies
7. **analyze_component_usage** - Track component/function usage across codebase
8. **extract_api_endpoints** - Extract and document API endpoints from route files

### Key Features
- **Standards Management**: Load and organize coding standards with metadata
- **Context-Aware**: Automatically load relevant standards based on file patterns
- **Security Analysis**: Detect common vulnerabilities with severity levels
- **Code Quality**: Find dead code, circular dependencies, and usage patterns
- **Rule Parsing**: Structure standards for AI-driven ESLint generation
- **Performance**: Caching, batch operations, incremental processing

### Usage Patterns
```python
# Common workflow: Load standards, parse for structure
standards = load_coding_standards()
rules = parse_standard_to_rules(standard_content, standard_id)
# ESLint rule generation now uses Claude Code commands (see documentation/commands/)

# Security and quality analysis
detect_security_patterns(file_paths=["src/**/*.ts"], severity_threshold="medium")
find_dead_code(confidence_threshold=0.9)
find_import_cycles()

# Get relevant standards for a file before editing
relevant = get_relevant_standards("src/api/routes/user.ts")
```

### MCP Server Usage Guidelines

When using the Code Analysis Tools in other projects with Claude Code:

```markdown
## Code Analysis Tools Usage

The AroMCP server includes Code Analysis Tools for standards-driven development:

### When to use:
- **Before editing files**: Use `get_relevant_standards(file_path)` to load applicable coding standards
- **After making changes**: Run `run_eslint` from Build Tools to validate against standards
- **For security checks**: Use `detect_security_patterns` on modified files
- **For cleanup**: Use `find_dead_code` and `find_import_cycles` periodically

### Workflow pattern:
1. When starting work on a file, get its standards: `get_relevant_standards("path/to/file.ts")`
2. Cache the standards for the session to avoid repeated lookups
3. For ESLint rule generation: Use Claude Code command (see documentation/commands/generate-eslint-rules.md)
4. After completing changes, run linting: `run_eslint(file_paths=["path/to/file.ts"])`
5. For new features, check security: `detect_security_patterns(file_paths=["path/to/file.ts"])`

### Standards location:
- Standards should be in `.aromcp/standards/` as markdown files with YAML frontmatter
- Standards are matched to files using glob patterns in the frontmatter
- More specific patterns take precedence over general ones
- For ESLint rule generation, use the AI-driven Claude Code command approach
```

See `documentation/usage/analysis_tools.md` for detailed usage examples and parameter documentation.

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

## Development Memories

- Always use `uv run` prefix for all Python commands to ensure proper virtual environment
- Apply `@json_convert` decorator to all tools that accept list/dict parameters
- Default `project_root` parameters to `None` and resolve using `get_project_root()`
- Use `validate_file_path_legacy()` for consistent path security validation
- Implement comprehensive error handling with structured error responses
- ESLint rule generation is now handled via Claude Code commands for better AI-driven rule creation
- The command documentation is at `documentation/commands/generate-eslint-rules.md`