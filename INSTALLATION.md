# AroMCP Installation Guide

Complete installation and setup guide for all AroMCP servers and configurations.

## Quick Start

```bash
# 1. Clone and install
git clone <repository-url>
cd AroMCP
uv sync --dev

# 2. Create system-wide symlink (recommended)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP

# 3. Verify installation
ls -la /usr/mcp/AroMCP  # Should point to your AroMCP directory
```

## Individual Server Architecture

AroMCP uses an individual server architecture where each server provides specialized functionality. Run only the servers you need for optimal performance and minimal resource usage.

---

## Prerequisites

### Required
- **Python 3.12+** - AroMCP requires modern Python features
- **uv package manager** - Used for dependency management and virtual environments
- **Git** - For cloning the repository

### Recommended  
- **System symlink** - For consistent paths across environments
- **TypeScript/Node.js** - For TypeScript analysis features
- **ESLint** - For code quality features

---

## System-Wide Symlink Setup

### Why Use a Symlink?

Creating a symlink at `/usr/mcp/AroMCP` provides several benefits:

- **🔗 Consistent Path**: All Claude Desktop configurations use the same path regardless of where you clone AroMCP
- **📝 Simplified Config**: No need to update configurations when moving the repository
- **🔄 Easy Updates**: Pull updates to your local directory, symlink automatically points to latest code
- **👥 Team Consistency**: All team members can use identical Claude Desktop configurations

### Creating the Symlink

```bash
# Navigate to your AroMCP directory
cd /path/to/your/AroMCP

# Create the symlink (requires sudo)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP

# Verify the symlink
ls -la /usr/mcp/AroMCP  # Should show: /usr/mcp/AroMCP -> /path/to/your/AroMCP
```

### Alternative Without Symlink

If you prefer not to use a symlink, replace `/usr/mcp/AroMCP` with your actual AroMCP directory path in all configurations below.

---

## Individual Server Setup

### Server Overview

| Server | Purpose | Tools | Config Name |
|--------|---------|-------|-------------|
| [Filesystem](#filesystem-server) | File operations | 3 | `aromcp-filesystem` |
| [Build](#build-server) | Development automation | 3 | `aromcp-build` |
| [Analysis](#analysis-server) | TypeScript analysis | 3 | `aromcp-analysis` |
| [Standards](#standards-server) | Coding standards | 10 | `aromcp-standards` |
| [Workflow](#workflow-server) | State management | 14 | ⚠️ **IN DEVELOPMENT** |

### Filesystem Server
**Purpose**: Advanced file operations with glob patterns and pagination  
**Tools**: `list_files`, `read_files`, `write_files`

```bash
# Run standalone
uv run python servers/filesystem/main.py
```

**Claude Desktop Configuration**:
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
        "MCP_FILE_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

### Build Server
**Purpose**: Build automation, linting, and testing  
**Tools**: `check_typescript`, `lint_project`, `run_test_suite`

```bash
# Run standalone
uv run python servers/build/main.py
```

**Claude Desktop Configuration**:
```json
{
  "mcpServers": {
    "aromcp-build": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/usr/mcp/AroMCP",
        "run",
        "--extra", "all-servers",
        "python",
        "servers/build/main.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

### Analysis Server
**Purpose**: TypeScript code analysis and symbol resolution  
**Tools**: `find_references`, `get_function_details`, `analyze_call_graph`

```bash
# Run standalone
uv run python servers/analysis/main.py
```

**Claude Desktop Configuration**:
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

### Standards Server
**Purpose**: Intelligent coding standards with 70-80% token reduction  
**Tools**: 10 tools including `hints_for_file`, `register`, `add_rule`, `get_session_stats`

```bash
# Run standalone
uv run python servers/standards/main.py
```

**Claude Desktop Configuration**:
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

### Workflow Server ⚠️ **IN DEVELOPMENT - NOT FUNCTIONAL**

**⚠️ WARNING**: This server is under active development and is **NOT YET FUNCTIONAL**.

**Purpose**: Workflow execution and persistent state management (when complete)  
**Tools**: 14 planned tools for workflow orchestration and state management  
**Status**: 🚧 **DO NOT USE** - Implementation in progress

```bash
# ⚠️ NOT FUNCTIONAL - FOR DEVELOPMENT ONLY
# uv run python servers/workflow/main.py
```

**Claude Desktop Configuration**: ⚠️ **DO NOT ADD TO CONFIGURATION**
```json
<!-- DO NOT USE - SERVER NOT FUNCTIONAL
{
  "mcpServers": {
    "aromcp-workflow": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory", "/usr/mcp/AroMCP",
        "run",
        "--extra", "all-servers",
        "python",
        "servers/workflow/main.py"
      ],
      "env": {
        "MCP_FILE_ROOT": "/path/to/your/project"
      }
    }
  }
}
-->
```

---

## Multi-Server Configuration

### All Servers Configuration
Add multiple servers to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "aromcp-filesystem": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/usr/mcp/AroMCP", "run", "--extra", "all-servers", "python", "servers/filesystem/main.py"],
      "env": {"MCP_FILE_ROOT": "/path/to/your/project"}
    },
    "aromcp-build": {
      "type": "stdio", 
      "command": "uv",
      "args": ["--directory", "/usr/mcp/AroMCP", "run", "--extra", "all-servers", "python", "servers/build/main.py"],
      "env": {"MCP_FILE_ROOT": "/path/to/your/project"}
    },
    "aromcp-analysis": {
      "type": "stdio",
      "command": "uv", 
      "args": ["--directory", "/usr/mcp/AroMCP", "run", "--extra", "all-servers", "python", "servers/analysis/main.py"],
      "env": {"MCP_FILE_ROOT": "/path/to/your/project"}
    },
    "aromcp-standards": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/usr/mcp/AroMCP", "run", "--extra", "all-servers", "python", "servers/standards/main.py"],
      "env": {"MCP_FILE_ROOT": "/path/to/your/project", "AROMCP_STANDARDS_PATH": "/path/to/standards/storage"}
    },
    "aromcp-workflow": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/usr/mcp/AroMCP", "run", "--extra", "all-servers", "python", "servers/workflow/main.py"],
      "env": {"MCP_FILE_ROOT": "/path/to/your/project"}
    }
  }
}
```

### Selective Server Configuration
Choose only the servers you need:

**For File Operations Only:**
```json
{
  "mcpServers": {
    "aromcp-filesystem": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "/usr/mcp/AroMCP", "run", "--extra", "all-servers", "python", "servers/filesystem/main.py"],
      "env": {"MCP_FILE_ROOT": "/path/to/your/project"}
    }
  }
}
```

**For Code Quality Pipeline:**
```json
{
  "mcpServers": {
    "aromcp-filesystem": { /* filesystem config */ },
    "aromcp-build": { /* build config */ },
    "aromcp-standards": { /* standards config */ }
  }
}
```

---

## Claude Desktop Configuration Files

### Configuration File Locations

**macOS**:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows**:
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux**:
```
~/.config/Claude/claude_desktop_config.json
```

### Creating Configuration File
If the configuration file doesn't exist, create it:

```bash
# macOS
mkdir -p ~/Library/Application\ Support/Claude
touch ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Linux  
mkdir -p ~/.config/Claude
touch ~/.config/Claude/claude_desktop_config.json

# Windows (PowerShell)
New-Item -Path $env:APPDATA\Claude\claude_desktop_config.json -ItemType File -Force
```

---

## Environment Variables

### Required Variables

**`MCP_FILE_ROOT`** - Project root directory for all file operations
```bash
export MCP_FILE_ROOT="/path/to/your/project"
```

### Optional Variables

**`AROMCP_STANDARDS_PATH`** - Standards server storage location
```bash
export AROMCP_STANDARDS_PATH="/path/to/standards/storage"
```

**`MCP_LOG_LEVEL`** - Logging level (DEBUG, INFO, WARNING, ERROR)
```bash
export MCP_LOG_LEVEL="INFO"
```

**`MCP_SECURITY_LEVEL`** - Security validation level
```bash
export MCP_SECURITY_LEVEL="standard"
```

---

## Server Management Scripts

### Automated Server Management
AroMCP includes scripts for managing multiple servers:

```bash
# Start all servers in background
./scripts/run-all-servers.sh

# Check server health
./scripts/health-check.py

# Stop all servers
./scripts/stop-all-servers.sh
```

### Manual Server Management
```bash
# Start specific server
uv run python servers/filesystem/main.py &

# Check if server is running
ps aux | grep "servers/filesystem/main.py"

# Stop server (find PID and kill)
pkill -f "servers/filesystem/main.py"
```

---

## Project Dependencies (Target Projects)

For projects using AroMCP's build and standards features, ensure these dependencies are installed:

### Required for TypeScript Analysis
```bash
npm install --save-dev eslint @typescript-eslint/parser
```

### Next.js Projects
```bash
npm install --save-dev eslint eslint-config-next @typescript-eslint/parser
```

### Dependencies Explained
- **`eslint`** (v9.0+) - Required for linting with flat config format
- **`@typescript-eslint/parser`** - Required for parsing TypeScript files
- **`eslint-config-next`** - Next.js ESLint configuration (Next.js projects only)

---

## Verification and Testing

### Installation Verification
```bash
# Test individual servers
uv run python servers/filesystem/main.py --help
uv run python servers/build/main.py --help
uv run python servers/analysis/main.py --help
uv run python servers/standards/main.py --help
uv run python servers/workflow/main.py --help

# Run tests
uv run pytest
uv run pytest tests/test_main_server.py  # Test all 33 tools
```

### Claude Desktop Connection Test
1. Start your chosen server configuration
2. Open Claude Desktop
3. Check that MCP connection is established
4. Test a simple command like listing files

---

## Troubleshooting

### Common Issues

**1. Command not found: `uv`**
```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Permission denied for symlink**
```bash
# Use sudo for system-wide symlink
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

**3. ModuleNotFoundError**
```bash
# Ensure dependencies are installed
uv sync --dev

# Use --extra all-servers flag
uv run --extra all-servers python main.py
```

**4. MCP_FILE_ROOT not set**
```bash
# Set environment variable
export MCP_FILE_ROOT="/path/to/your/project"

# Or add to your shell profile
echo 'export MCP_FILE_ROOT="/path/to/your/project"' >> ~/.bashrc
```

**5. Claude Desktop not connecting**
- Verify configuration file syntax (use JSON validator)
- Check that server process starts without errors
- Ensure `MCP_FILE_ROOT` path exists and is accessible
- Restart Claude Desktop after configuration changes

### Getting Help

- **[TOOL_INVENTORY.md](TOOL_INVENTORY.md)** - Complete tool reference
- **[TOOL_GUIDE.md](TOOL_GUIDE.md)** - Usage patterns and workflows  
- **[servers/*/README.md](servers/)** - Server-specific documentation
- **[CLAUDE.md](CLAUDE.md)** - Development guidelines

### Debug Mode
```bash
# Run with debug logging
MCP_LOG_LEVEL=DEBUG uv run python main.py

# Run with verbose output
uv run --verbose python main.py
```

---

## Next Steps

1. **Choose your servers**: Select the individual servers you need
2. **Configure Claude Desktop**: Add server configurations to config file
3. **Set environment variables**: Especially `MCP_FILE_ROOT`
4. **Test connection**: Verify servers start and Claude Desktop connects
5. **Explore tools**: Use [TOOL_GUIDE.md](TOOL_GUIDE.md) to understand available functionality

**Success**: You now have access to **19 production-ready development tools** across **4 functional servers** (plus 1 workflow server in development)!