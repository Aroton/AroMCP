# AroMCP Analysis Server

Advanced TypeScript code analysis and symbol resolution for maintaining clean codebases.

## Overview

The Analysis server provides TypeScript-focused code analysis capabilities:
- Symbol reference tracking across projects
- Function signature and parameter analysis
- Static call graph generation
- Type-aware code navigation and analysis

## Installation

Dependencies are automatically installed when using the run script:

```bash
./scripts/run-server.sh analysis
```

## Running the Server

### Recommended (with automatic dependency management):
```bash
# From AroMCP project root
./scripts/run-server.sh analysis

# Background mode
./scripts/run-server.sh analysis --background
```

### Manual (requires separate dependency installation):
```bash
cd servers/analysis
uv sync  # Install dependencies first
uv run python main.py
```

## Tools Available

- `find_references` - Find all references to TypeScript symbols (functions, classes, variables)
- `get_function_details` - Extract detailed information about TypeScript functions including parameters, return types, and documentation
- `analyze_call_graph` - Generate static call graphs showing function dependencies and relationships

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
      "command": "/usr/mcp/AroMCP/scripts/run-server.sh",
      "args": [
        "analysis"
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

1. **Uses run-server.sh script**: Provides automatic dependency management and consistent startup
2. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
3. **Simple server specification**: Just specify `analysis` as the server name
4. **Automatic dependency installation**: Script handles `uv sync` before starting server

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

### Symbol Reference Tracking
- Finds all references to TypeScript symbols across the codebase
- Tracks usage in functions, classes, interfaces, and types
- Supports cross-file and cross-module analysis
- Respects TypeScript module resolution

### Function Analysis
- Extracts complete function signatures with parameter types
- Analyzes return types and JSDoc documentation
- Identifies function complexity and dependencies
- Supports both regular functions and arrow functions

### Call Graph Generation
- Creates static call graphs showing function relationships
- Identifies direct and indirect dependencies
- Helps understand code architecture and data flow
- Supports filtering by depth and complexity

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "Find all references to the calculateTotal function"
- "Get detailed information about the UserService class methods"
- "Generate a call graph for the authentication module"
- "Show me all functions that call the validateInput function"

## Configuration

Analysis behavior can be customized through:
- TypeScript project configuration (tsconfig.json)
- Symbol search depth and scope parameters
- Call graph complexity filtering options

## Standalone Usage

You can also run the server standalone for testing:

```bash
# With custom project root
MCP_FILE_ROOT=/my/project uv run python main.py

# With debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Use Cases

1. **Code Navigation**: Quickly find all usages of functions and classes
2. **Refactoring**: Understand impact of changes before modification
3. **Architecture Analysis**: Visualize function dependencies and call patterns
4. **Code Documentation**: Generate documentation from TypeScript symbols

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework
- `tree-sitter>=0.20.0` - Syntax tree parsing
- `tree-sitter-typescript>=0.20.0` - TypeScript language parser
- `tree-sitter-javascript>=0.20.0` - JavaScript language parser
- `networkx>=3.0` - Graph algorithms for call graph analysis
- `psutil>=5.9.0` - System and process monitoring