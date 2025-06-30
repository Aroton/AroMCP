"""Entry point for AroMCP - redirects to the main server."""

from src.aromcp.main_server import mcp

if __name__ == "__main__":
    mcp.run()
