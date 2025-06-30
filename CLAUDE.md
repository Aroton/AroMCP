# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AroMCP is a suite of MCP (Model Context Protocol) servers designed as utilities for AI-driven development workflows. The project aims to create "dumb" utilities that perform deterministic operations without AI logic, allowing AI agents to focus on decision-making.

## Current State

The project has a functional MCP server architecture with all tool signatures implemented as stubs. The main server (`src/aromcp/main_server.py`) unifies all four MCP servers into a single FastMCP instance. All core tools are defined but currently return placeholder responses - actual implementations are needed.

**Implementation Status:**
- ✅ Server architecture and tool signatures complete
- ✅ FastMCP integration working
- ⚠️ All tools are stub implementations (return empty/placeholder data)
- ❌ No input validation, error handling, or security measures implemented

## Planned Architecture

The project will consist of four main MCP servers:

1. **FileSystem Server** (`filesystem-server`) - File I/O operations, git operations, code parsing
2. **Process State Server** (`state-server`) - Persistent state management for long-running processes
3. **Build Tools Server** (`build-server`) - Build, lint, test, and validation commands
4. **Code Analysis Server** (`analysis-server`) - Deterministic code analysis operations

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
- `src/aromcp/filesystem_server/tools.py` - File I/O, git operations, code parsing tools
- `src/aromcp/state_server/tools.py` - Persistent state management tools  
- `src/aromcp/build_server/tools.py` - Build, lint, test execution tools
- `src/aromcp/analysis_server/tools.py` - Code analysis and metrics tools
- `main.py` - Entry point that imports and runs the main server

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

## Documentation

- Main technical design: `documentation/simplify-workflow.md`
- Contains detailed specifications for each planned MCP server
- Includes security requirements and deployment considerations

## Server Configuration

- We use FastMCP server for this project. Always load the documentation index: https://gofastmcp.com/llms.txt - Only load documentation through *.md files located in llms.txt. DO NOT LOAD HTML PAGES.