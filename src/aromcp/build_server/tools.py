"""Build Tools MCP Server tools - legacy import compatibility."""

# Import from the new tools module structure
from .tools import register_build_tools

__all__ = ["register_build_tools"]