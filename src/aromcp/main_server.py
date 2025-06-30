"""AroMCP Unified Server - All MCP tools in a single server instance."""

from fastmcp import FastMCP
from aromcp.filesystem_server.tools import register_filesystem_tools
from aromcp.state_server.tools import register_state_tools
from aromcp.build_server.tools import register_build_tools
from aromcp.analysis_server.tools import register_analysis_tools

# Initialize the unified MCP server
mcp = FastMCP("AroMCP Server Suite")

# Register all tools from different modules
register_filesystem_tools(mcp)
register_state_tools(mcp)
register_build_tools(mcp)
register_analysis_tools(mcp)

if __name__ == "__main__":
    mcp.run()