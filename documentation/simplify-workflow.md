# MCP Server Suite Technical Design Prompt

## Project Overview

I need you to implement a suite of MCP (Model Context Protocol) servers that will serve as reusable utilities for AI-driven code operations across multiple projects. These servers should be "dumb" utilities - they perform deterministic, programmatic operations without any AI/LLM logic. The AI agent (Claude) will handle all intelligent decision-making.

## Core Design Principles

1. **Separation of Concerns**: Each MCP server has a single, well-defined responsibility
2. **Token Efficiency**: Servers handle operations that would be token-expensive in an AI context
3. **Project Agnostic**: Servers work with any project structure without hardcoded paths
4. **Stateless Operations**: Most operations should be stateless except for the dedicated state server
5. **Error Resilience**: Graceful error handling with structured error responses
6. **Batch Operations**: Support batch operations where applicable to reduce round trips
7. **Security**: Validate inputs, use whitelists for commands, prevent directory traversal

## Server Specifications

### 1. FileSystem MCP Server (`filesystem-server`)

**Purpose**: Handle all file I/O operations, git operations, and code parsing tasks that would consume tokens if done in the AI agent.

**Key Tools**:
- `get_target_files`: List files based on git status (working/branch/commit) or path patterns
- `read_files_batch`: Read multiple files in one operation, return as path->content dict
- `write_files_batch`: Write multiple files atomically with automatic directory creation
- `extract_method_signatures`: Parse code files to extract function/method signatures programmatically
- `find_imports_for_files`: Identify which files import the given files (dependency analysis)
- `scan_project_structure`: Analyze project layout and return structured information
- `load_documents_by_pattern`: Load multiple documents matching glob patterns (for standards, configs)

**Design Considerations**:
- Support multiple file encodings (UTF-8 default, with fallbacks)
- Handle large files gracefully (streaming for files >1MB)
- Implement smart path resolution (relative to git root)
- Return structured data, not raw strings where possible
- Include file metadata (size, last modified) when relevant

### 2. Process State MCP Server (`state-server`)

**Purpose**: Manage persistent state for long-running processes, enabling resumability and progress tracking.

**Key Tools**:
- `initialize_process`: Create a new process state with unique ID
- `get_process_state`: Retrieve current state by process ID
- `update_process_state`: Update arbitrary fields in process state
- `get_next_work_item`: Get next item from a queue (supports batching)
- `complete_work_item`: Mark items as complete, update progress
- `add_process_metadata`: Add arbitrary metadata to process
- `cleanup_process`: Archive or delete completed process state

**Design Considerations**:
- Support multiple storage backends (file, Redis, PostgreSQL) via adapter pattern
- Implement state versioning for compatibility
- Include automatic state backup/recovery
- Support concurrent process tracking
- Provide progress calculation utilities
- Enable state querying (e.g., "get all processes of type X")

### 3. Build Tools MCP Server (`build-server`)

**Purpose**: Execute build, lint, test, and validation commands with structured output parsing.

**Key Tools**:
- `run_command`: Execute whitelisted commands with structured output
- `parse_typescript_errors`: Run tsc and return structured error data
- `parse_lint_results`: Run linters and return categorized issues
- `run_test_suite`: Execute tests with parsed results
- `check_dependencies`: Analyze package.json and installed deps
- `get_build_config`: Extract build configuration from various sources

**Design Considerations**:
- Command whitelisting with configurable allowed lists
- Structured parsing of common output formats (TypeScript, ESLint, Jest)
- Resource limits (timeout, memory) for command execution
- Support for different package managers (npm, yarn, pnpm)
- Caching of command results where appropriate
- Incremental execution support

### 4. Code Analysis MCP Server (`analysis-server`)

**Purpose**: Perform deterministic code analysis operations that would be token-heavy.

**Key Tools**:
- `find_duplicates`: Identify duplicate code patterns across files
- `analyze_complexity`: Calculate cyclomatic complexity and other metrics
- `extract_dependencies`: Build dependency graphs between modules
- `find_unused_exports`: Identify dead code
- `analyze_naming_patterns`: Extract naming conventions used in project
- `generate_file_map`: Create a structured map of the codebase

**Design Considerations**:
- Use AST parsing for accurate analysis
- Support multiple languages (TypeScript, JavaScript, Python)
- Provide configurable thresholds for various metrics
- Return actionable data (not just metrics)
- Support incremental analysis for large codebases

## Configuration Standards

### Environment Variables
```
MCP_STATE_BACKEND=file|redis|postgres
MCP_STATE_PATH=/path/to/state/storage
MCP_FILE_ROOT=/path/to/project/root
MCP_SECURITY_LEVEL=strict|standard|permissive
MCP_LOG_LEVEL=debug|info|warn|error
```

### Server Response Format
All tools should return consistent response structures:
```
{
  "status": "success|error|partial",
  "data": { ... },  // Tool-specific data
  "metadata": {
    "duration_ms": 123,
    "timestamp": "ISO-8601",
    "warnings": []
  },
  "error": {  // Only if status is error
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": { ... }
  }
}
```

### Error Codes Convention
- `INVALID_INPUT`: Validation failed
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Security check failed
- `OPERATION_FAILED`: Command/operation failed
- `TIMEOUT`: Operation timed out
- `UNSUPPORTED`: Feature not supported

## Implementation Guidelines

1. **Language**: Python 3.10+ using the `mcp` SDK
2. **Dependencies**: Minimal external dependencies, prefer stdlib
3. **Testing**: Each tool should have unit tests with mocked filesystem/commands
4. **Documentation**: Each tool must have comprehensive docstrings
5. **Logging**: Structured logging with appropriate levels
6. **Performance**: Async operations where beneficial, connection pooling for state backends

## Security Requirements

1. **Input Validation**: Validate all inputs against schemas
2. **Path Security**: Prevent directory traversal attacks
3. **Command Security**: Whitelist approach for all command execution
4. **Resource Limits**: Implement timeouts and memory limits
5. **Secrets**: Never log sensitive information

## Deployment Considerations

1. **Packaging**: Each server should be independently deployable
2. **Versioning**: Semantic versioning with clear upgrade paths
3. **Compatibility**: Maintain backwards compatibility within major versions
4. **Discovery**: Servers should provide capability discovery endpoints
5. **Health Checks**: Include health/readiness endpoints

## Example Usage Patterns

The servers should support these common patterns:

1. **Batch Processing**: Process multiple files in parallel
2. **Incremental Updates**: Only process changed items
3. **Progress Tracking**: Long operations report progress
4. **Resumability**: Processes can be paused and resumed
5. **Audit Trail**: State changes are tracked with metadata

Remember: These servers are utilities that provide efficient, deterministic operations. They do not make decisions - they execute operations requested by the AI agent and return structured data for the AI to analyze and act upon.