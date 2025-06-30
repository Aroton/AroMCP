# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AroMCP is a suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. The project aims to create "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making.

## Current State

The project has a functional MCP server architecture with **Phase 1: FileSystem Tools** fully implemented. The main server (`src/aromcp/main_server.py`) unifies all MCP servers into a single FastMCP instance. FileSystem tools are production-ready with comprehensive functionality.

**Implementation Status:**
- ✅ Server architecture and tool signatures complete
- ✅ FastMCP integration working
- ✅ **Phase 1: FileSystem Tools - FULLY IMPLEMENTED**
  - ✅ All 6 filesystem tools implemented with full functionality
  - ✅ Comprehensive input validation, error handling, and security measures
  - ✅ 46 comprehensive tests with 100% pass rate
  - ✅ Path traversal protection and encoding safety
  - ✅ Batch operations and atomic file writing with backup support
- ⚠️ Phases 2-6: Other tool categories are stub implementations (return empty/placeholder data)

## Planned Architecture

The project consists of six main tool categories:

1. **FileSystem Tools** - File I/O operations, git operations, code parsing, diff validation
2. **State Management Tools** - Persistent state management for long-running processes
3. **Build Tools** - Build, lint, test, and validation commands
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
- **Run server**: `python main.py` or `python -m src.aromcp.main_server`
- **Run tests**: `pytest` 
- **Code formatting**: `black src/ tests/`
- **Linting**: `ruff check src/ tests/`
- **Fix linting**: `ruff check --fix src/ tests/`

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
- `src/aromcp/analysis_server/tools.py` - Code analysis and metrics tools (planned)
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
- Additional usage guides will be added as new tool categories are implemented

### Documentation Standards
- **README.md**: Keep concise with overview and links to detailed documentation
- **Usage Guides**: Detailed examples, parameters, and practical usage patterns for each tool category
- **Technical Documentation**: Architecture, design decisions, and implementation specifications
- **Cross-References**: All documentation should link to related files to create a connected knowledge base

## Server Configuration

- We use FastMCP server for this project. Always load the documentation index: https://gofastmcp.com/llms.txt - Only load documentation through *.md files located in llms.txt. DO NOT LOAD HTML PAGES.

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
signatures = extract_method_signatures(file_path="src/main.py")
write_files_batch(files={"output/analysis.json": json.dumps(signatures)})
```

See `documentation/usage/filesystem_tools.md` for detailed usage examples and parameter documentation.

## Development Memories

- Always use `uv` to run python commands