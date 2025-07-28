# AroMCP FileSystem Server

File operations and code analysis tools for AI-driven development.

## Overview

The FileSystem server provides essential file management and code analysis capabilities:
- File listing with glob patterns
- Multi-file reading with pagination
- Multi-file writing with automatic directory creation
- Code signature extraction
- Import dependency analysis

## Installation

```bash
cd servers/filesystem
uv sync
```

## Running the Server

```bash
uv run python main.py
```

## Tools Available

### File Operations
- `list_files` - List files matching glob patterns
- `read_files` - Read multiple files with pagination support
- `write_files` - Write multiple files with automatic directory creation

### Code Analysis
- `extract_method_signatures` - Extract function/method signatures from code
- `find_who_imports` - Find which files import a given module

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
    "aromcp-filesystem": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/usr/mcp/AroMCP",
        "run",
        "--extra", "all-servers",
        "python",
        "servers/filesystem/main.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project",
        "MCP_SECURITY_LEVEL": "standard"
      }
    }
  }
}
```

Replace `/path/to/your/project` with the project you want to work with.

## Key Configuration Changes

1. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
2. **Run from root directory**: `--directory` points to AroMCP root instead of individual server directory
3. **Use --extra all-servers**: Ensures all dependencies are available
4. **Relative paths to servers**: `servers/filesystem/main.py` instead of just `main.py`

## Setup Requirements

First, create the AroMCP symlink as described in the main README:

```bash
# Create system-wide symlink (run from your AroMCP directory)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

## Verification

Test the server manually before adding to Claude:

```bash
cd /usr/mcp/AroMCP
MCP_FILE_ROOT=/path/to/your/project uv run --extra all-servers python servers/filesystem/main.py
```

## Environment Variables

- `MCP_FILE_ROOT` - Root directory for file operations (required)
- `MCP_SECURITY_LEVEL` - Security level: "strict" or "standard" (default: "standard")
- `MCP_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## Security

The FileSystem server includes security features to prevent:
- Directory traversal attacks
- Access outside the project root
- Reading/writing system files

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "List all Python files in the project"
- "Read the main.py and config.py files"
- "Find all files that import the utils module"
- "Extract all function signatures from api.py"

## Standalone Usage

You can also run the server standalone for testing:

```bash
# With custom file root
MCP_FILE_ROOT=/my/project uv run python main.py

# With debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework
- `chardet>=5.0.0` - Character encoding detection