"""Analysis MCP Server - Code quality and dependency analysis tools."""

from fastmcp import FastMCP

from .tools import register_analysis_tools

__version__ = "0.1.0"

# Initialize the Analysis MCP server
mcp = FastMCP(
    name="AroMCP Analysis Server",
    version=__version__,
    instructions="""
        Analysis server provides code quality and dependency analysis tools:
        
        Core Tools:
        - find_dead_code: Identify unused functions, classes, and variables
        - find_import_cycles: Detect circular import dependencies
        - extract_api_endpoints: Document API routes and endpoints
        
        All tools support:
        - Multiple programming languages (Python, JavaScript, TypeScript)
        - Configurable analysis depth
        - Detailed reporting with code locations
        - Export to various formats
        
        Best Practices:
        - Run find_dead_code before releases to clean up unused code
        - Use find_import_cycles to maintain clean architecture
        - Use extract_api_endpoints to keep API documentation current
        - Combine with build tools for comprehensive code quality checks
    """,
)

# Register all analysis tools
register_analysis_tools(mcp)

if __name__ == "__main__":
    mcp.run()