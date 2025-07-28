# Individual MCP Servers Guide

This guide explains how to use AroMCP's individual MCP servers, which allow you to enable/disable specific functionality as needed.

## Overview

AroMCP has been split into 5 independent MCP servers:

1. **FileSystem Server** - File operations and code analysis
2. **Build Server** - Compilation, linting, and testing
3. **Analysis Server** - Code quality and dependency analysis
4. **Standards Server** - ESLint rules and coding guidelines
5. **Workflow Server** - Workflow execution and state management

## Running Individual Servers

### Method 1: Direct Python Execution

```bash
# FileSystem Server
uv run python filesystem_server.py

# Build Server
uv run python build_server.py

# Analysis Server
uv run python analysis_server.py

# Standards Server
uv run python standards_server.py

# Workflow Server
uv run python workflow_server.py
```

### Method 2: Module Execution

```bash
# FileSystem Server
uv run python -m src.aromcp.filesystem_server.server

# Build Server
uv run python -m src.aromcp.build_server.server

# Analysis Server
uv run python -m src.aromcp.analysis_server.server

# Standards Server
uv run python -m src.aromcp.standards_server.server

# Workflow Server
uv run python -m src.aromcp.workflow_server.server
```

### Method 3: Using the Unified Server (Legacy)

The original unified server is still available for backward compatibility:

```bash
uv run python main.py
```

## Installing Server-Specific Dependencies

Each server has its own minimal dependencies. Install only what you need:

```bash
# Install base dependencies + filesystem server
uv sync --extra filesystem

# Install base dependencies + build server
uv sync --extra build

# Install base dependencies + analysis server
uv sync --extra analysis

# Install base dependencies + standards server
uv sync --extra standards

# Install base dependencies + workflow server
uv sync --extra workflow

# Install all servers (equivalent to original setup)
uv sync
```

## Server Configurations

Each server has its own configuration file in `.aromcp/servers/`:

- `filesystem.yaml` - FileSystem server settings
- `build.yaml` - Build server settings
- `analysis.yaml` - Analysis server settings
- `standards.yaml` - Standards server settings
- `workflow.yaml` - Workflow server settings

## Server-Specific Tools

### FileSystem Server Tools
- `list_files` - List files matching patterns
- `read_files` - Read multiple files
- `write_files` - Write multiple files
- `extract_method_signatures` - Extract code signatures
- `find_who_imports` - Find import dependencies

### Build Server Tools
- `lint_project` - Run ESLint checks
- `check_typescript` - Check TypeScript errors
- `run_test_suite` - Execute tests
- `run_tests` - Simplified test execution
- `quality_check` - Run all quality checks

### Analysis Server Tools
- `find_dead_code` - Find unused code
- `find_import_cycles` - Detect circular imports
- `extract_api_endpoints` - Document API routes

### Standards Server Tools
- `register_standard` - Register coding standard
- `add_rule` - Add ESLint rule
- `add_hint` - Add coding hint
- `hints_for_file` - Get file-specific hints
- `update_rule` - Update existing rule
- `delete_*` - Remove standards/rules/hints
- `check_updates` - Check for updates

### Workflow Server Tools
- `workflow_start` - Start workflow
- `workflow_step` - Execute next step
- `workflow_status` - Get status
- `workflow_stop` - Stop workflow
- `workflow_list` - List workflows
- `state_*` - State management tools

## Use Cases

### Minimal File Operations
If you only need file operations:
```bash
uv sync --extra filesystem
uv run python filesystem_server.py
```

### Code Quality Checks
For linting and testing:
```bash
uv sync --extra build
uv run python build_server.py
```

### Full Development Suite
For complete functionality:
```bash
uv sync  # Installs all dependencies
# Run servers as needed
```

## Environment Variables

All servers respect the same environment variables:
- `MCP_FILE_ROOT` - Project root directory
- `MCP_LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

## Migration from Unified Server

If you're currently using the unified server:

1. The unified server (`main.py`) continues to work as before
2. Individual servers provide the same tools with focused functionality
3. You can gradually migrate to individual servers
4. Configuration remains backward compatible

## Testing Individual Servers

Run tests for individual server functionality:

```bash
# Test all individual servers
uv run pytest tests/test_individual_servers.py

# Test specific server
uv run pytest tests/filesystem_server/
uv run pytest tests/build_server/
uv run pytest tests/analysis_server/
uv run pytest tests/standards_server/
uv run pytest tests/workflow_server/
```

## Benefits of Individual Servers

1. **Reduced Dependencies** - Only install what you need
2. **Independent Versioning** - Each server can be versioned separately
3. **Better Performance** - Smaller memory footprint
4. **Easier Development** - Work on one server without affecting others
5. **Flexible Deployment** - Deploy only required functionality

## Troubleshooting

### Server Won't Start
- Check dependencies: `uv sync --extra [server_name]`
- Verify Python version: `python --version` (requires 3.12+)
- Check for port conflicts if running multiple servers

### Tools Not Found
- Ensure you're running the correct server for the tools you need
- Check server configuration files in `.aromcp/servers/`

### Import Errors
- Individual servers have focused dependencies
- Install server-specific extras: `uv sync --extra [server_name]`

## Future Enhancements

- Docker images for each server
- Server orchestration tools
- Inter-server communication
- Server health monitoring
- Auto-discovery in MCP clients