"""FileSystem MCP Server - File operations and code analysis tools."""

from fastmcp import FastMCP

from .tools import register_filesystem_tools

__version__ = "0.1.0"

# Initialize the FileSystem MCP server
mcp = FastMCP(
    name="AroMCP FileSystem Server",
    version=__version__,
    instructions="""
        FileSystem server provides file operations and code analysis tools:
        
        Core Tools:
        - list_files: List files matching glob patterns
        - read_files: Read multiple files with pagination support
        - write_files: Write multiple files with automatic directory creation
        - extract_method_signatures: Extract function/method signatures from code
        - find_who_imports: Find which files import a given module
        
        All tools support:
        - Path security validation (no directory traversal)
        - Glob pattern expansion
        - Token-based pagination for large results
        - Automatic encoding detection for file reading
        
        Best Practices:
        - Use list_files instead of find/ls commands
        - Use read_files for batch file reading
        - Always read files before modifying them
        - Use find_who_imports before deleting/moving files
    """,
)

# Register all filesystem tools
register_filesystem_tools(mcp)

if __name__ == "__main__":
    mcp.run()
