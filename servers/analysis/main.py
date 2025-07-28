"""Entry point for AroMCP Analysis Server."""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.aromcp.analysis_server.server import mcp

if __name__ == "__main__":
    mcp.run()