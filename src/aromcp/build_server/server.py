"""Build MCP Server - Compilation, linting, and testing tools."""

from fastmcp import FastMCP

from .tools import register_build_tools

__version__ = "0.1.0"

# Initialize the Build MCP server
mcp = FastMCP(
    name="AroMCP Build Server",
    version=__version__,
    instructions="""
        Build server provides compilation, linting, and testing tools:
        
        Core Tools:
        - lint_project: Run ESLint and get formatted results
        - check_typescript: Check TypeScript compilation errors
        - run_test_suite: Execute test suites with result parsing
        
        Simplified Aliases:
        - run_tests: Alias for run_test_suite with sensible defaults
        - quality_check: Run all quality checks (lint + TypeScript + tests)
        
        All tools support:
        - Automatic project type detection
        - Configurable severity filtering
        - Detailed error reporting with file locations
        - Summary statistics
        
        Best Practices:
        - Use lint_project instead of running ESLint directly
        - Use check_typescript for type validation
        - Run quality_check before commits
        - Configure tools via project config files (eslintrc, tsconfig, etc.)
    """,
)

# Register all build tools
register_build_tools(mcp)

if __name__ == "__main__":
    mcp.run()