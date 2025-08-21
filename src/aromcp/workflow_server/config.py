"""Configuration management for workflow server."""

import os
from dataclasses import dataclass


@dataclass
class WorkflowServerConfig:
    """Configuration class for the workflow server."""

    # Temporal Configuration (for Phase 4)
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "mcp-workflows"

    # MCP Server Configuration
    server_name: str = "temporal-workflow"
    transport: str = "stdio"
    max_message_size: int = 10_000_000  # 10MB
    timeout: int = 30  # seconds

    # Workflow Configuration
    workflow_definitions_path: str = "./.aromcp/workflows/"
    max_pending_actions: int = 50
    yaml_cache_ttl: int = 300  # seconds
    worker_threads: int = 10

    # Runtime Configuration
    debug_mode: bool = False
    log_level: str = "INFO"

    # Phase 1 specific configuration (mock mode)
    mock_mode: bool = True  # Run without Temporal for Phase 1
    mock_step_delay: float = 0.1  # Delay between mock steps in seconds

    @classmethod
    def from_environment(cls) -> "WorkflowServerConfig":
        """Create configuration from environment variables."""
        return cls(
            # Temporal Configuration
            temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            temporal_task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "mcp-workflows"),

            # Server Configuration
            server_name=os.getenv("WORKFLOW_SERVER_NAME", "temporal-workflow"),
            max_message_size=int(os.getenv("MAX_MESSAGE_SIZE", "10000000")),
            timeout=int(os.getenv("MCP_TIMEOUT", "30")),

            # Workflow Configuration
            workflow_definitions_path=os.getenv("WORKFLOW_DEFINITIONS_PATH", "./.aromcp/workflows/"),
            max_pending_actions=int(os.getenv("MAX_PENDING_ACTIONS", "50")),
            yaml_cache_ttl=int(os.getenv("YAML_CACHE_TTL", "300")),
            worker_threads=int(os.getenv("WORKER_THREADS", "10")),

            # Runtime Configuration
            debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),

            # Phase 1 Configuration
            mock_mode=os.getenv("WORKFLOW_MOCK_MODE", "true").lower() == "true",
            mock_step_delay=float(os.getenv("MOCK_STEP_DELAY", "0.1")),
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration settings."""
        errors = []

        # Validate timeouts
        if self.timeout <= 0:
            errors.append("timeout must be positive")

        if self.yaml_cache_ttl <= 0:
            errors.append("yaml_cache_ttl must be positive")

        if self.max_pending_actions <= 0:
            errors.append("max_pending_actions must be positive")

        if self.worker_threads <= 0:
            errors.append("worker_threads must be positive")

        # Validate paths
        if not self.workflow_definitions_path:
            errors.append("workflow_definitions_path cannot be empty")

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            errors.append(f"log_level must be one of {valid_log_levels}")

        return len(errors) == 0, errors

    def __post_init__(self):
        """Post-initialization validation."""
        is_valid, errors = self.validate()
        if not is_valid:
            raise ValueError(f"Invalid configuration: {', '.join(errors)}")


# Global configuration instance
_config: WorkflowServerConfig | None = None


def get_config() -> WorkflowServerConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = WorkflowServerConfig.from_environment()
    return _config


def set_config(config: WorkflowServerConfig) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config


def reset_config() -> None:
    """Reset the global configuration instance."""
    global _config
    _config = None
