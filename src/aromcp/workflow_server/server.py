"""Workflow MCP Server - Workflow execution and state management."""

from fastmcp import FastMCP

from .tools import register_workflow_tools

__version__ = "0.1.0"

# Initialize the Workflow MCP server
mcp = FastMCP(
    name="AroMCP Workflow Server",
    version=__version__,
    instructions="""
        Workflow server provides workflow execution and state management:
        
        Core Tools:
        - workflow_start: Start a new workflow execution
        - workflow_step: Execute the next step in a workflow
        - workflow_status: Get workflow execution status
        - workflow_stop: Stop a running workflow
        - workflow_list: List available workflows
        
        State Management:
        - state_get: Get values from workflow state
        - state_update: Update workflow state values
        - state_transform: Transform state with JavaScript
        - state_clear: Clear workflow state
        
        Features:
        - YAML-based workflow definitions
        - Control flow (if/else, while, for-each)
        - Parallel step execution
        - Sub-agent communication
        - Variable scoping and resolution
        - Error handling and retries
        - Performance monitoring
        
        Best Practices:
        - Define workflows in .aromcp/workflows/
        - Use state management for data passing
        - Implement error handling in workflows
        - Monitor workflow performance
    """,
)

# Register all workflow tools
register_workflow_tools(mcp)

if __name__ == "__main__":
    mcp.run()
