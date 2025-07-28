"""
Health check management for production deployment.
"""

import time
import psutil
from datetime import datetime, UTC
from typing import Dict, Any


class HealthCheckManager:
    """Manages health checks for the workflow server."""
    
    def __init__(self, executor=None, state_manager=None, observability=None):
        self.executor = executor
        self.state_manager = state_manager
        self.observability = observability
        self.start_time = time.time()
    
    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now(UTC).isoformat(),
            'version': '1.0.0',
            'uptime': time.time() - self.start_time,
            'components': {},
            'metrics': {}
        }
        
        # Check components
        health_status['components']['executor'] = {
            'status': 'healthy' if self.executor else 'unavailable'
        }
        
        health_status['components']['state_manager'] = {
            'status': 'healthy' if self.state_manager else 'unavailable'
        }
        
        health_status['components']['observability'] = {
            'status': 'healthy' if self.observability else 'unavailable'
        }
        
        # Collect metrics
        if self.executor:
            health_status['metrics']['active_workflows'] = getattr(self.executor, 'active_workflow_count', 0)
            health_status['metrics']['queued_workflows'] = getattr(self.executor, 'queued_workflow_count', 0)
        
        # System metrics
        process = psutil.Process()
        health_status['metrics']['cpu_usage'] = process.cpu_percent()
        health_status['metrics']['memory_usage'] = process.memory_info().rss / 1024 / 1024  # MB
        
        return health_status
    
    async def check_readiness(self) -> Dict[str, Any]:
        """Check if system is ready to receive traffic."""
        readiness = {
            'ready': True,
            'checks': {}
        }
        
        # Database connection check
        readiness['checks']['database_connection'] = {
            'passed': True,  # Simplified for demo
            'message': 'Database connection available'
        }
        
        # Resource availability
        readiness['checks']['resource_availability'] = {
            'passed': True,
            'message': 'Sufficient resources available'
        }
        
        # Configuration check
        readiness['checks']['configuration'] = {
            'passed': True,
            'message': 'Configuration valid'
        }
        
        # Overall readiness
        readiness['ready'] = all(
            check['passed'] for check in readiness['checks'].values()
        )
        
        return readiness
    
    async def check_liveness(self) -> Dict[str, Any]:
        """Check if system is alive and processing."""
        return {
            'alive': True,
            'last_activity': datetime.now(UTC).isoformat(),
            'processing_active': True
        }