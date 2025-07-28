"""Entry point for AroMCP - DEPRECATED."""

import sys
import warnings

warnings.warn(
    "\n" + "="*70 + "\n" +
    "DEPRECATION WARNING: The unified AroMCP server is deprecated!\n\n" +
    "Please use individual servers instead:\n" +
    "  - FileSystem Server: uv run python servers/filesystem/main.py\n" +
    "  - Build Server: uv run python servers/build/main.py\n" +
    "  - Analysis Server: uv run python servers/analysis/main.py\n" +
    "  - Standards Server: uv run python servers/standards/main.py\n" +
    "  - Workflow Server: uv run python servers/workflow/main.py\n\n" +
    "See docs/INDIVIDUAL_SERVERS.md for more information.\n" +
    "="*70 + "\n",
    DeprecationWarning,
    stacklevel=2
)

# For backward compatibility, still run the unified server
try:
    from src.aromcp.main_server import mcp
    if __name__ == "__main__":
        print("\nStarting DEPRECATED unified server for backward compatibility...\n")
        mcp.run()
except ImportError:
    print("ERROR: Cannot run unified server. Dependencies not installed.")
    print("Install with: uv sync --extra all-servers")
    sys.exit(1)
