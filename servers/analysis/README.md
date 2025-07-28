# AroMCP Analysis Server

Code quality and dependency analysis tools for maintaining clean codebases.

## Overview

The Analysis server provides advanced code analysis capabilities:
- Dead code detection
- Circular import detection
- API endpoint extraction and documentation
- Multi-language support (Python, JavaScript, TypeScript)

## Installation

```bash
cd servers/analysis
uv sync
```

## Running the Server

```bash
uv run python main.py
```

## Tools Available

- `find_dead_code` - Identify unused functions, classes, and variables
- `find_import_cycles` - Detect circular import dependencies
- `extract_api_endpoints` - Document API routes and endpoints

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
    "aromcp-analysis": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/usr/mcp/AroMCP",
        "run",
        "--extra", "all-servers",
        "python",
        "servers/analysis/main.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

Replace `/path/to/your/project` with the project you want to analyze.

## Key Configuration Changes

1. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
2. **Run from root directory**: `--directory` points to AroMCP root instead of individual server directory
3. **Use --extra all-servers**: Ensures all dependencies are available
4. **Relative paths to servers**: `servers/analysis/main.py` instead of just `main.py`

## Setup Requirements

First, create the AroMCP symlink as described in the main README:

```bash
# Create system-wide symlink (run from your AroMCP directory)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

## Environment Variables

- `MCP_FILE_ROOT` - Root directory for analysis (required)
- `MCP_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## Analysis Features

### Dead Code Detection
- Identifies unused functions, classes, and variables
- Respects exports and public APIs
- Ignores test files by default
- Supports Python, JavaScript, and TypeScript

### Import Cycle Detection
- Finds circular dependencies between modules
- Shows complete import chains
- Configurable search depth
- Helps maintain clean architecture

### API Endpoint Extraction
- Automatically detects framework (Express, FastAPI, Flask, Django)
- Extracts route definitions with HTTP methods
- Documents request/response schemas when available
- Generates markdown documentation

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "Find all dead code in the project"
- "Check for circular imports"
- "Document all API endpoints"
- "Find unused functions in the utils module"

## Configuration

Analysis behavior can be customized through:
- Ignore patterns in tool parameters
- Framework-specific detection rules
- Language-specific parsing strategies

## Standalone Usage

You can also run the server standalone for testing:

```bash
# With custom project root
MCP_FILE_ROOT=/my/project uv run python main.py

# With debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Use Cases

1. **Pre-release Cleanup**: Find and remove dead code before releases
2. **Architecture Review**: Detect and fix circular dependencies
3. **API Documentation**: Keep API docs in sync with implementation
4. **Code Quality**: Maintain a clean, well-structured codebase

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework