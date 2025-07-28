# AroMCP Workflow Server

Workflow execution and state management for complex AI-driven automation.

## Overview

The Workflow server provides advanced workflow orchestration:
- YAML-based workflow definitions
- Complex control flow (conditionals, loops, parallel execution)
- State management with variable scoping
- Sub-agent communication
- Performance monitoring and debugging

## Installation

```bash
cd servers/workflow
uv sync
```

## Running the Server

```bash
uv run python main.py
```

## Tools Available

### Workflow Execution
- `workflow_start` - Start a new workflow execution
- `workflow_step` - Execute the next step in a workflow
- `workflow_status` - Get workflow execution status
- `workflow_stop` - Stop a running workflow
- `workflow_list` - List available workflows

### State Management
- `state_get` - Get values from workflow state
- `state_update` - Update workflow state values
- `state_transform` - Transform state with JavaScript
- `state_clear` - Clear workflow state

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
        "MCP_FILE_ROOT": "/path/to/your/project",
        "AROMCP_WORKFLOWS_DIR": "/path/to/your/workflows"
      }
    }
  }
}
```

## Key Configuration Changes

1. **Uses symlink path**: `/usr/mcp/AroMCP` provides consistent path across environments
2. **Run from root directory**: `--directory` points to AroMCP root instead of individual server directory
3. **Use --extra all-servers**: Ensures all dependencies are available
4. **Relative paths to servers**: `servers/workflow/main.py` instead of just `main.py`

## Setup Requirements

First, create the AroMCP symlink as described in the main README:

```bash
# Create system-wide symlink (run from your AroMCP directory)
sudo mkdir -p /usr/mcp
sudo ln -sf $(pwd) /usr/mcp/AroMCP
```

## Environment Variables

- `MCP_FILE_ROOT` - Root directory for file operations (required)
- `AROMCP_WORKFLOWS_DIR` - Directory containing workflow YAML files (default: `.aromcp/workflows`)
- `MCP_LOG_LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `AROMCP_DEBUG_MODE` - Enable debug mode for workflows (default: false)

## Workflow Definition

Workflows are defined in YAML files in the workflows directory:

```yaml
name: example-workflow
description: Example workflow showing key features
version: "1.0"

inputs:
  - name: target_file
    type: string
    required: true

steps:
  - name: read_file
    type: mcp_call
    tool: read_files
    args:
      files: "{{ inputs.target_file }}"
    
  - name: process_content
    type: conditional
    condition: "{{ steps.read_file.output.files.length > 0 }}"
    then:
      - name: analyze
        type: mcp_call
        tool: find_dead_code
        args:
          files: "{{ inputs.target_file }}"
```

## Step Types

- `mcp_call` - Call MCP tools
- `conditional` - If/else branching
- `while_loop` - Repeat steps while condition is true
- `for_each` - Iterate over collections
- `parallel` - Execute steps concurrently
- `user_input` - Request user input
- `state_update` - Update workflow state
- `shell_command` - Execute shell commands
- `agent_prompt` - Communicate with sub-agents

## State Management

The workflow server provides sophisticated state management:
- Scoped variables (workflow, step, loop levels)
- JavaScript expressions for transformations
- Persistent state across workflow execution
- State isolation between workflows

## Example Usage

Once configured in Claude Desktop, you can use commands like:

- "Start the code-review workflow for main.py"
- "Check the status of running workflows"
- "Get the current state of the analysis workflow"
- "Stop the long-running migration workflow"

## Advanced Features

### Parallel Execution
Execute multiple steps concurrently with resource management:
```yaml
- name: parallel_analysis
  type: parallel
  steps:
    - name: lint
      type: mcp_call
      tool: lint_project
    - name: test
      type: mcp_call
      tool: run_tests
```

### Error Handling
Built-in retry logic and error recovery:
```yaml
- name: api_call
  type: mcp_call
  tool: fetch_data
  retry:
    max_attempts: 3
    delay: 1000
```

### Performance Monitoring
- Execution time tracking
- Resource usage monitoring
- Step-level performance metrics
- Debug mode for troubleshooting

## Standalone Usage

```bash
# With custom workflows directory
AROMCP_WORKFLOWS_DIR=/my/workflows uv run python main.py

# With debug mode
AROMCP_DEBUG_MODE=true uv run python main.py

# With verbose logging
MCP_LOG_LEVEL=DEBUG uv run python main.py
```

## Use Cases

1. **Automated Code Reviews**: Multi-step analysis workflows
2. **Deployment Pipelines**: Orchestrate build, test, deploy
3. **Data Processing**: Complex ETL workflows
4. **AI Agent Coordination**: Multi-agent task workflows

## Dependencies

- `fastmcp>=2.10.5` - MCP server framework
- `pyyaml>=6.0.0` - YAML workflow definitions
- `pythonmonkey>=1.1.1` - JavaScript expression evaluation
- `psutil>=5.9.0` - Resource monitoring
- `jsonschema>=4.0.0` - Workflow validation