"""Workflow MCP Server - Workflow execution and state management."""

import asyncio
import logging
import sys

from fastmcp import FastMCP

from .config import WorkflowServerConfig, get_config
from .pending_actions import PendingActionsManager, get_pending_actions_manager
from .temporal_client import TemporalManager, get_temporal_manager
from .tools import register_workflow_tools

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


class WorkflowServer:
    """Workflow server with proper lifecycle management as specified in Phase 1."""

    def __init__(self, config: WorkflowServerConfig | None = None):
        self.config = config or get_config()
        self.mcp = FastMCP(
            name="AroMCP Workflow Server",
            version=__version__,
            instructions="""
                Phase 1 Workflow server provides basic workflow execution and state management:
                
                Core Tools (Phase 1):
                - start_workflow: Start a new workflow execution from YAML definition
                - submit_result: Submit result for a pending workflow action 
                - get_workflow_status: Get current workflow execution status
                - health_check: Check server health and Temporal connection
                
                Features (Phase 1):
                - Basic YAML workflow loading
                - Temporal workflow integration (mock mode supported)
                - Pending action management for Claude interactions
                - Thread-safe state management
                
                Best Practices:
                - Define workflows in .aromcp/workflows/
                - Use mock mode for development without Temporal server
                - Check health_check before starting workflows
                - Monitor workflow status during execution
            """,
        )
        self.temporal: TemporalManager | None = None
        self.pending_actions: PendingActionsManager | None = None

    async def initialize(self):
        """Initialize server components as specified in Phase 1."""
        logger.info(f"Initializing workflow server: {self.config.server_name}")

        # Get global singletons
        self.temporal = get_temporal_manager()
        self.pending_actions = get_pending_actions_manager()

        # Connect to Temporal
        logger.info(f"Connecting to Temporal at {self.config.temporal_host}")
        connected = await self.temporal.connect()

        if not connected:
            if self.config.mock_mode:
                logger.warning("Temporal connection failed, but continuing in mock mode")
            else:
                raise RuntimeError("Failed to connect to Temporal server")

        # Verify connection with health check
        logger.info("Performing Temporal health check")
        healthy = await self.temporal.health_check()

        if not healthy:
            if self.config.mock_mode:
                logger.warning("Temporal health check failed, but continuing in mock mode")
            else:
                raise RuntimeError("Temporal health check failed")

        # Register MCP tools
        logger.info("Registering workflow tools")
        register_workflow_tools(
            self.mcp,
            self.temporal,
            self.pending_actions,
            self.config
        )

        logger.info(f"Workflow server initialized successfully: {self.config.server_name}")

    async def run(self):
        """Run the MCP server as specified in Phase 1."""
        await self.initialize()

        logger.info("Starting MCP server on stdio")
        # Start MCP server on stdio
        await self.mcp.run()

    async def shutdown(self):
        """Graceful shutdown of server components."""
        logger.info("Shutting down workflow server")

        if self.temporal:
            await self.temporal.close()

        logger.info("Workflow server shutdown complete")


def main():
    """Entry point for the workflow server as specified in Phase 1."""
    # Setup logging as specified in Phase 1
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration from environment
    config = get_config()

    # Apply log level from configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.log_level))

    logger.info(f"Starting workflow server with configuration: mock_mode={config.mock_mode}")

    # Create and run server
    server = WorkflowServer(config)

    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
