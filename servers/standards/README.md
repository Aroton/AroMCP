# AroMCP Standards Server

Coding guidelines and ESLint rule management for consistent code quality.

## Overview

The Standards server provides intelligent coding standards management:
- Context-aware ESLint rule suggestions
- Project-specific coding hints
- Dynamic rule compression for efficiency
- Multi-project standard support
- Session-based rule management

## Installation

```bash
cd servers/standards
uv sync
```

## Running the Server

```bash
uv run python main.py
```

## Tools Available (10 Tools)

### Core Standards Management
- `hints_for_file` - Get context-aware coding hints with session management and 70-80% token reduction
- `register` - Register new coding standards with enhanced metadata
- `check_updates` - Check for updated or new standard files
- `delete` - Remove all rules and hints for a standard

### Rule & Hint Management
- `add_rule` - Add ESLint rules with context awareness
- `list_rules` - List ESLint rules for a standard
- `add_hint` - Add coding hints and best practices

### Session & Analytics
- `get_session_stats` - Get statistics for AI coding sessions
- `clear_session` - Clear session data for memory management
- `analyze_context` - Analyze context for specific files and sessions

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
    "aromcp-standards": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/usr/mcp/AroMCP",
        "run",
        "--extra", "all-servers",
        "python",
        "servers/standards/main.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project",
        "AROMCP_STANDARDS_PATH": "/path/to/standards/storage"
      }
    }
  }
}
```

Replace `/path/to/your/project` with your project root.

## Key Configuration Changes

1. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
2. **Run from root directory**: `--directory` points to AroMCP root instead of individual server directory  
3. **Use --extra all-servers**: Ensures all dependencies are available
4. **Relative paths to servers**: `servers/standards/main.py` instead of just `main.py`

## Setup Requirements

First, create the AroMCP symlink as described in the main README:

```bash
# Create system-wide symlink (run from your AroMCP directory)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

## Environment Variables

- `MCP_FILE_ROOT` - Root directory for file analysis (required)
- `AROMCP_STANDARDS_PATH` - Path to store standards data (optional)
- `MCP_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)

## Features

### Context-Aware Rules
- Suggests relevant ESLint rules based on file content
- Groups related rules automatically
- Adapts to project patterns and conventions

### Intelligent Hints
- Provides file-specific coding guidance
- Learns from project patterns
- Filters hints by relevance threshold

### Efficient Storage
- Compresses rules to save tokens
- Session-based caching
- Persistent storage across sessions

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "Register React coding standards for this project"
- "Add ESLint rule for consistent arrow functions"
- "What coding hints apply to this component?"
- "Update the no-console rule to allow warnings"

## Standard Templates

The server includes templates for common standards:
- React/Next.js best practices
- Node.js/Express conventions
- Python/Django guidelines
- TypeScript strict mode rules

## Session Management

- Sessions persist rule context during work
- Automatic session cleanup
- Multi-project session support

## Standalone Usage

You can also run the server standalone for testing:

```bash
# With custom project root
MCP_FILE_ROOT=/my/project uv run python main.py

# With custom standards storage
AROMCP_STANDARDS_PATH=/my/standards uv run python main.py

# With debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Use Cases

1. **Project Onboarding**: Register project-specific standards
2. **Code Reviews**: Get automated hints for improvements
3. **Team Consistency**: Share coding standards across team
4. **Rule Evolution**: Update rules as patterns emerge

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework
- `pyyaml>=6.0.0` - YAML configuration support