# AroMCP Build Server

Build automation, linting, and testing tools for AI-driven development workflows.

## Overview

The Build server provides essential development automation capabilities:
- ESLint integration for code style checking with pagination
- TypeScript compiler error checking
- Test suite execution with result parsing and pagination

## Installation

Dependencies are automatically installed when using the run script:

```bash
./scripts/run-server.sh build
```

## Running the Server

### Recommended (with automatic dependency management):
```bash
# From AroMCP project root
./scripts/run-server.sh build

# Background mode
./scripts/run-server.sh build --background
```

### Manual (requires separate dependency installation):
```bash
cd servers/build
uv sync  # Install dependencies first
uv run python main.py
```

## Tools Available

- `lint_project` - ESLint integration for code style checking with pagination
- `check_typescript` - TypeScript compiler error checking  
- `run_test_suite` - Execute test suites with result parsing and pagination

## Claude Desktop Configuration

Add this to your Claude Desktop configuration file:

### macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`

### Windows
`%APPDATA%\Claude\claude_desktop_config.json`

### Linux
`~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "aromcp-build": {
      "type": "stdio",
      "command": "/usr/mcp/AroMCP/scripts/run-server.sh",
      "args": [
        "build"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

Replace `/path/to/your/project` with the project you want to work with.

## Key Configuration Changes

1. **Uses run-server.sh script**: Provides automatic dependency management and consistent startup
2. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
3. **Simple server specification**: Just specify `build` as the server name
4. **Automatic dependency installation**: Script handles `uv sync` before starting server

## Setup Requirements

First, create the AroMCP symlink as described in the main README:

```bash
# Create system-wide symlink (run from your AroMCP directory)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

## Environment Variables

- `MCP_FILE_ROOT` - Root directory for build operations (required)
- `MCP_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## Build Features

### ESLint Integration
- Supports both project ESLint and standards-based ESLint configurations
- Handles flat config (eslint.config.js) and legacy (.eslintrc.js) formats
- Provides detailed error reporting with file paths and line numbers
- Includes pagination for large result sets

### TypeScript Checking
- Uses TypeScript compiler API for accurate error detection
- Reports syntax errors, type errors, and configuration issues
- Supports complex project structures and path mapping
- Handles both compilation errors and warnings

### Test Suite Execution
- Supports multiple test runners (Jest, Vitest, etc.)
- Parses test results with pass/fail statistics
- Provides detailed error reporting for failed tests
- Includes pagination for large test suites

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "Lint the entire project and show any errors"
- "Check TypeScript compilation errors in the src directory"
- "Run all tests and show me the results"
- "Fix linting issues in the authentication module"

## Standalone Usage

You can also run the server standalone for testing:

```bash
# With custom project root
MCP_FILE_ROOT=/my/project uv run python main.py

# With debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework