# Claude Code Integration

Integrate AroMCP with Claude Code via MCP to access powerful filesystem operations and code analysis tools.

> **Key Configuration Note**: This guide uses `uv --directory` to ensure proper project detection and dependency resolution, which is crucial for FastMCP-based servers.

## Quick Start

### 1. Setup AroMCP
```bash
git clone <repository-url>
cd AroMCP
uv sync --dev
uv run python main.py  # Test server starts, then Ctrl+C
```

### 2. Add to Claude Code

**Method 1: Direct Config File Edit (Recommended)**

Edit your Claude Code configuration file at `~/.claude.json`:

```json
{
  "mcpServers": {
    "aromcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/path/to/your/AroMCP",
        "run",
        "python",
        "src/aromcp/main_server.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project",
        "MCP_SECURITY_LEVEL": "standard"
      }
    }
  }
}
```

**Method 2: Using CLI Command**
```bash
claude mcp add aromcp -e MCP_FILE_ROOT=/path/to/your/project -e MCP_SECURITY_LEVEL=standard -- uv --directory /path/to/AroMCP run python src/aromcp/main_server.py
```

**Note**: The `--directory` flag ensures uv finds your project's virtual environment and dependencies correctly.

### 3. Restart Claude Code
After editing the config or adding via CLI, restart Claude Code for changes to take effect.

### 4. Verify
```bash
# Check server status
claude
/mcp
```

You should see:
```
⎿ MCP Server Status
⎿
⎿ • aromcp: connected
```

## Project-Specific Configuration

For team collaboration, create a `.mcp.json` file at your project root:

```json
{
  "mcpServers": {
    "aromcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "~/AroMCP",
        "run",
        "python",
        "src/aromcp/main_server.py"
      ],
      "env": {
        "MCP_FILE_ROOT": ".",
        "MCP_SECURITY_LEVEL": "standard"
      }
    }
  }
}
```

Claude Code will prompt for approval before using project-scoped servers from .mcp.json files.

## Available Tools

When properly configured, you can use these tools in Claude Code:

- **get_target_files** - List files with git integration and pattern matching
- **read_files_batch** - Read multiple files efficiently
- **write_files_batch** - Write multiple files atomically
- **extract_method_signatures** - Extract function/method signatures from code
- **find_imports_for_files** - Analyze import dependencies
- **load_documents_by_pattern** - Load and classify documents by pattern

## Usage in Claude Code

### Natural Language Requests
```
Can you show me all Python files in the src/ directory using aromcp?
Please read the contents of main.py and config.py
What are all the function signatures in the authentication module?
```

### Direct Tool Usage
Claude will automatically use the configured MCP tools when appropriate for your requests.

## Configuration Scopes

MCP servers can be configured at three different scope levels:

1. **Local (default)**: Private to current directory
   - Config stored in `~/.claude.json` under project-specific section

2. **Project**: Shared with team via `.mcp.json`
   - Checked into version control
   - Requires approval on first use

3. **User/Global**: Available across all projects
   - Config stored in `~/.claude.json` under global `mcpServers` section

## Environment Variables

Configure these in the `env` section:
- `MCP_FILE_ROOT`: Limit file access to specific directory
- `MCP_SECURITY_LEVEL`: Set security level (`standard`, `strict`, `permissive`)
- `MCP_LOG_LEVEL`: Set logging verbosity (`info`, `debug`)

## Debug Configuration

For troubleshooting, add debug logging:

```json
{
  "mcpServers": {
    "aromcp": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/path/to/AroMCP",
        "run",
        "python",
        "src/aromcp/main_server.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project",
        "MCP_SECURITY_LEVEL": "standard",
        "MCP_LOG_LEVEL": "debug"
      }
    }
  }
}
```

## Troubleshooting

### Check Server Status
```bash
# Inside Claude Code
/mcp
```

### View Available Tools
List all tools provided by your MCP server:
```bash
# This functionality may vary based on Claude Code version
# Check if server is connected first with /mcp
```

### Common Issues

1. **Server not connecting**:
   - Verify Python environment and dependencies with `uv sync`
   - Ensure the `--directory` path points to your AroMCP project root
   - Check that `src/aromcp/main_server.py` exists and has `mcp.run()` at the end

2. **Permission errors**:
   - Verify `MCP_FILE_ROOT` path exists and is accessible
   - Check file permissions

3. **Tools not available**:
   - Restart Claude Code after configuration changes
   - Verify server shows as "connected" in `/mcp` status

### Removing/Reconfiguring

To remove and reconfigure:
1. Edit `~/.claude.json` and remove the `aromcp` entry from `mcpServers`
2. Restart Claude Code
3. Add the configuration again with updated settings

## Best Practices

1. **Always set MCP_FILE_ROOT** to restrict file access to your project directory
2. **Use direct config editing** for complex configurations rather than CLI
3. **Test with `/mcp` command** to ensure server is connected before use
4. **Use project-scoped config** (`.mcp.json`) for team collaboration
5. **Keep sensitive API keys** out of project configs - use user/local scope instead

## Notes

- The precedence hierarchy prioritizes local-scoped servers first, followed by project-scoped servers, and finally user-scoped servers
- Unlike some MCP implementations, HTTP transport is not commonly used with Claude Code - stick with stdio
- The `claude mcp add-json` command format has been simplified in recent versions

For more details on MCP configuration, refer to the [official Claude Code MCP documentation](https://docs.anthropic.com/en/docs/claude-code/mcp).