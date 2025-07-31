"""Standards MCP Server - Coding guidelines and ESLint rule management."""

from fastmcp import FastMCP

from .tools import register_standards_tools

__version__ = "0.1.0"

# Initialize the Standards MCP server
mcp = FastMCP(
    name="AroMCP Standards Server",
    version=__version__,
    instructions="""
        Standards server provides coding guidelines and ESLint rule management:
        
        Core Tools:
        - register_standard: Register a new coding standard
        - add_rule: Add ESLint rules with context awareness
        - add_hint: Add coding hints and best practices
        - hints_for_file: Get relevant hints for a specific file
        - update_rule: Modify existing rules
        - delete_standard/delete_rule/delete_hint: Remove items
        - check_updates: Check for standard updates
        
        Features:
        - Context-aware rule suggestions
        - Automatic rule grouping and organization
        - Token-efficient rule compression
        - Session-based rule management
        - Multi-project standard support
        
        Best Practices:
        - Register project-specific standards first
        - Use hints_for_file to get contextual guidance
        - Group related rules together
        - Use check_updates to keep standards current
    """,
)

# Register all standards tools
register_standards_tools(mcp)

if __name__ == "__main__":
    mcp.run()
