# AroMCP FileSystem Server

File operations with advanced pattern matching and pagination for AI-driven development.

## Overview

The FileSystem server provides essential file management capabilities:
- File listing with advanced glob patterns and pagination
- Multi-file reading with encoding detection and pagination
- Multi-file writing with automatic directory creation

## Installation

Dependencies are automatically installed when using the run script:

```bash
./scripts/run-server.sh filesystem
```

## Running the Server

### Recommended (with automatic dependency management):
```bash
# From AroMCP project root
./scripts/run-server.sh filesystem

# Background mode
./scripts/run-server.sh filesystem --background

# Using alias
./scripts/run-server.sh fs
```

### Manual (requires separate dependency installation):
```bash
cd servers/filesystem
uv sync  # Install dependencies first
uv run python main.py
```

## Tools Available

- `list_files` - List files matching glob patterns with cursor pagination
- `read_files` - Read multiple files with encoding detection and pagination support
- `write_files` - Write multiple files with automatic directory creation

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
      "command": "/usr/mcp/AroMCP/scripts/run-server.sh",
      "args": [
        "filesystem"
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

1. **Uses run-server.sh script**: Provides automatic dependency management and consistent startup
2. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
3. **Simple server specification**: Just specify `filesystem` as the server name
4. **Automatic dependency installation**: Script handles `uv sync` before starting server

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
MCP_FILE_ROOT=/path/to/your/project ./scripts/run-server.sh filesystem
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