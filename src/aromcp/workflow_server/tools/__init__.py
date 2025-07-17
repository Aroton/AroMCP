"""
MCP tools for workflow state management
"""

from fastmcp import FastMCP

from .state_tools import register_workflow_state_tools
from .workflow_tools import register_workflow_tools as register_workflow_management_tools


def register_workflow_tools(mcp: FastMCP) -> None:
    """
    Register all workflow server tools with FastMCP

    Args:
        mcp: FastMCP server instance
    """
    register_workflow_state_tools(mcp)
    register_workflow_management_tools(mcp)
