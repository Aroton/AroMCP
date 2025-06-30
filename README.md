# AroMCP

A comprehensive suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. AroMCP provides "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making while handling token-intensive operations efficiently.

## Features

- **FileSystem Tools** - File I/O operations, git integration, code parsing, and document loading
- **State Management Tools** - Persistent state management for long-running processes (planned)
- **Build Tools** - Build, lint, test, and validation commands (planned)
- **Code Analysis Tools** - Deterministic code analysis operations (planned)
- **Context Window Management Tools** - Token usage tracking and optimization (planned)
- **Interactive Debugging Tools** - Debugging utilities and error investigation (planned)

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd AroMCP

# Install dependencies using uv
uv sync --dev

# Run the server
uv run python main.py
```

### Development Commands

```bash
# Run tests
uv run pytest

# Code formatting
uv run black src/ tests/

# Linting
uv run ruff check src/ tests/

# Auto-fix linting issues
uv run ruff check --fix src/ tests/
```

## Integration

### Claude Code Integration

AroMCP integrates seamlessly with Claude Code to provide enhanced filesystem operations and code analysis capabilities during AI-driven development sessions.

**[Complete Claude Code Integration Guide →](documentation/claude_code.md)**

Quick setup:
```bash
# Start AroMCP server
uv run python main.py

# Configure in Claude Code MCP settings
# Set MCP_FILE_ROOT to your project directory
# Available tools: file operations, code analysis, diff management
```

## Documentation

### Integration Guides
- [Claude Code Integration](documentation/claude_code.md) - Complete setup guide for Claude Code integration

### Usage Guides
- [FileSystem Tools Usage](documentation/usage/filesystem_tools.md) - Comprehensive guide for all filesystem operations

### Technical Documentation
- [Simplify Workflow](documentation/simplify-workflow.md) - Detailed technical design and architecture

## FileSystem Tools Usage (Moved)

**This section has been moved to [documentation/usage/filesystem_tools.md](documentation/usage/filesystem_tools.md) for better organization.**

## Project Structure

```
src/aromcp/
├── main_server.py                     # Unified FastMCP server
├── filesystem_server/
│   ├── tools.py                       # FastMCP tool registration
│   └── tools/                         # Individual tool implementations
│       ├── get_target_files.py
│       ├── read_files_batch.py
│       ├── write_files_batch.py
│       ├── extract_method_signatures.py
│       ├── find_imports_for_files.py
│       └── load_documents_by_pattern.py
├── state_server/                      # Planned: State management tools
├── build_server/                      # Planned: Build and test tools
└── analysis_server/                   # Planned: Code analysis tools
```

## Contributing

1. Follow the existing code structure with separate implementation files
2. All tools must include comprehensive input validation and security checks
3. Use structured error responses with appropriate error codes
4. Write comprehensive tests for all functionality
5. Update documentation for any new tools or features

## License

[License information]
