"""Health check implementation for workflow server."""

import logging

from ..models.workflow_models import HealthCheckResponse
from ..temporal_client import get_temporal_manager

logger = logging.getLogger(__name__)


def health_check_impl() -> HealthCheckResponse:
    """Check health of workflow server components.
    
    Returns:
        HealthCheckResponse with component health status
        
    Raises:
        RuntimeError: If critical components are unhealthy
    """
    logger.info("Performing health check")

    try:
        # Get Temporal manager
        logger.debug("Getting Temporal manager for health check")
        manager = get_temporal_manager()

        # Get health info
        logger.debug("Getting health info from Temporal manager")
        health_info = manager.get_health_info()

        # Determine overall status
        overall_status = "healthy" if health_info["connected"] or health_info["mock_mode"] else "unhealthy"
        logger.info(f"Overall health status: {overall_status} (connected: {health_info['connected']}, mock_mode: {health_info['mock_mode']})")

        response = HealthCheckResponse(
            status=overall_status,
            timestamp=health_info["health_check_time"],
            components={
                "temporal": {
                    "status": "healthy" if health_info["connected"] else "unhealthy",
                    "connected": health_info["connected"],
                    "mock_mode": health_info["mock_mode"],
                    "host": health_info["temporal_host"],
                    "namespace": health_info["temporal_namespace"],
                    "task_queue": health_info["task_queue"],
                },
                "workflows": {
                    "status": "healthy",
                    "active_count": health_info["active_workflows"],
                }
            },
            mock_mode=health_info["mock_mode"],
        )

        logger.info(f"Health check completed successfully: {response.status}")
        return response

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthCheckResponse(
            status="unhealthy",
            error=f"Health check failed: {str(e)}",
            components={},
            mock_mode=True,
        )
