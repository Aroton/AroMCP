"""AroMCP Unified Server - All MCP tools in a single server instance.

This server provides comprehensive development tools organized into categories:
- FileSystem: File operations, reading, writing, and analysis
- Build: Compilation, linting, testing, and dependency management  
- Analysis: Code quality, dead code detection, import analysis
- Standards: Coding guidelines, hints, and ESLint rule management

For best results, use the simplified tool versions:
- list_files, read_files, write_files (instead of *_batch versions)
- lint_project, check_typescript, run_tests (instead of parse_* versions)
- find_who_imports (instead of find_imports_for_files)
"""

from fastmcp import FastMCP

from aromcp.analysis_server.tools import register_analysis_tools
from aromcp.build_server.tools import register_build_tools
from aromcp.filesystem_server.tools import register_filesystem_tools
from aromcp.standards_server.tools import register_standards_tools

# Initialize the unified MCP server
mcp = FastMCP("AroMCP Development Tools Suite")

# Register all tools from different modules
# Filesystem tools now use @json_convert decorators for automatic parameter parsing
register_filesystem_tools(mcp)
# register_state_tools(mcp)
register_build_tools(mcp)
register_analysis_tools(mcp)
register_standards_tools(mcp)

if __name__ == "__main__":
    mcp.run()
