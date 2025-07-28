"""
Production readiness tests for workflow_server.

Tests production deployment requirements including health checks, graceful shutdown,
configuration validation, monitoring, and security.
"""

import pytest
import asyncio
import json
import os
import signal
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock
import tempfile
import yaml

from aromcp.workflow_server.workflow.models import (
    WorkflowDefinition, WorkflowStep, WorkflowInstance
)
from aromcp.workflow_server.models.workflow_models import WorkflowStatusResponse
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor
from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.monitoring.observability import ObservabilityManager
from aromcp.workflow_server.monitoring.metrics import MetricsCollector
from aromcp.workflow_server.monitoring.exporters import MetricsExporter
from aromcp.workflow_server.errors.handlers import ErrorHandler
from aromcp.workflow_server.workflow.loader import WorkflowLoader


class TestHealthCheckEndpoints:
    """Test health check and status endpoints."""
    
    @pytest.fixture
    def production_system(self):
        """Create production-ready system with all components."""
        state_manager = StateManager()
        observability = ObservabilityManager()
        metrics_collector = MetricsCollector()
        error_handler = ErrorHandler()
        
        executor = QueueBasedWorkflowExecutor(
            state_manager=state_manager,
            observability_manager=observability,
            error_handler=error_handler
        )
        
        # Create health check manager
        from aromcp.workflow_server.deployment.health import HealthCheckManager
        health_manager = HealthCheckManager(
            executor=executor,
            state_manager=state_manager,
            observability=observability
        )
        
        return {
            'executor': executor,
            'state_manager': state_manager,
            'observability': observability,
            'metrics_collector': metrics_collector,
            'error_handler': error_handler,
            'health_manager': health_manager
        }
    
    @pytest.mark.asyncio
    async def test_basic_health_check(self, production_system):
        """Test basic health check endpoint."""
        health_manager = production_system['health_manager']
        
        # Check health when system is idle
        health_status = await health_manager.check_health()
        
        assert health_status['status'] == 'healthy'
        assert 'timestamp' in health_status
        assert 'version' in health_status
        assert 'uptime' in health_status
        
        # Check component statuses
        assert 'components' in health_status
        components = health_status['components']
        
        assert 'executor' in components
        assert components['executor']['status'] == 'healthy'
        
        assert 'state_manager' in components
        assert components['state_manager']['status'] == 'healthy'
        
        assert 'observability' in components
        assert components['observability']['status'] == 'healthy'
    
    @pytest.mark.asyncio
    async def test_health_check_under_load(self, production_system):
        """Test health check when system is under load."""
        executor = production_system['executor']
        health_manager = production_system['health_manager']
        
        # Create load on the system
        simple_workflow = WorkflowDefinition(
            name="load_test",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="wait",
                    type="wait",
                    config={"duration": 1}
                )
            ]
        )
        
        # Start multiple workflows
        workflow_ids = []
        for i in range(10):
            result = await executor.start_workflow(simple_workflow, {"index": i})
            workflow_ids.append(result['workflow_id'])
        
        # Check health while under load
        health_status = await health_manager.check_health()
        
        assert health_status['status'] == 'healthy'
        assert 'metrics' in health_status
        
        metrics = health_status['metrics']
        assert metrics['active_workflows'] == 10
        assert metrics['queued_workflows'] >= 0
        assert 'cpu_usage' in metrics
        assert 'memory_usage' in metrics
    
    @pytest.mark.asyncio
    async def test_readiness_probe(self, production_system):
        """Test readiness probe for load balancer integration."""
        health_manager = production_system['health_manager']
        
        # Test readiness when system starts
        readiness = await health_manager.check_readiness()
        
        assert readiness['ready'] == True
        assert 'checks' in readiness
        
        checks = readiness['checks']
        assert 'database_connection' in checks
        assert 'resource_availability' in checks
        assert 'configuration' in checks
        
        # All checks should pass
        for check_name, check_result in checks.items():
            assert check_result['passed'] == True
    
    @pytest.mark.asyncio
    async def test_liveness_probe(self, production_system):
        """Test liveness probe for container orchestration."""
        health_manager = production_system['health_manager']
        executor = production_system['executor']
        
        # Start a workflow to ensure system is processing
        workflow_def = WorkflowDefinition(
            name="liveness_test",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="process",
                    type="state_update",
                    config={"updates": {"processed": True}}
                )
            ]
        )
        
        result = await executor.start_workflow(workflow_def, {})
        await executor.execute_next()
        
        # Check liveness
        liveness = await health_manager.check_liveness()
        
        assert liveness['alive'] == True
        assert 'last_activity' in liveness
        assert 'processing_active' in liveness
        
        # Verify recent activity
        last_activity = datetime.fromisoformat(liveness['last_activity'])
        assert (datetime.utcnow() - last_activity).total_seconds() < 5


class TestGracefulShutdown:
    """Test graceful shutdown scenarios."""
    
    @pytest.mark.asyncio
    async def test_shutdown_with_active_workflows(self):
        """Test graceful shutdown when workflows are active."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # Long-running workflow
        long_workflow = WorkflowDefinition(
            name="long_running",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="process",
                    type="foreach",
                    config={
                        "items": "{{ range(10) }}",
                        "steps": [
                            {
                                "id": "wait",
                                "type": "wait",
                                "config": {"duration": 0.5}
                            }
                        ]
                    }
                )
            ]
        )
        
        # Start workflows
        workflow_ids = []
        for i in range(3):
            result = await executor.start_workflow(long_workflow, {"index": i})
            workflow_ids.append(result['workflow_id'])
        
        # Start execution in background
        execution_task = asyncio.create_task(
            self._execute_workflows(executor)
        )
        
        # Wait a bit for execution to start
        await asyncio.sleep(0.5)
        
        # Initiate graceful shutdown
        shutdown_complete = False
        
        async def graceful_shutdown():
            nonlocal shutdown_complete
            print("Initiating graceful shutdown...")
            
            # Stop accepting new workflows
            executor.stop_accepting_workflows()
            
            # Wait for active workflows to complete
            timeout = 10  # 10 second timeout
            start_time = time.time()
            
            while executor.has_active_workflows() and time.time() - start_time < timeout:
                await asyncio.sleep(0.1)
            
            # Cancel remaining if timeout
            if executor.has_active_workflows():
                await executor.cancel_all_workflows()
            
            shutdown_complete = True
            print("Graceful shutdown complete")
        
        # Perform shutdown
        await graceful_shutdown()
        
        # Cancel execution task
        execution_task.cancel()
        try:
            await execution_task
        except asyncio.CancelledError:
            pass
        
        # Verify shutdown completed
        assert shutdown_complete
        assert not executor.is_accepting_workflows()
        
        # Check workflow states
        for workflow_id in workflow_ids:
            state = state_manager.get_workflow_state(workflow_id)
            # Workflows should be either completed or cancelled
            assert state['status'] in [WorkflowStatusResponse.COMPLETED.value, WorkflowStatusResponse.CANCELLED.value]
    
    async def _execute_workflows(self, executor):
        """Helper to execute workflows in background."""
        try:
            while True:
                if executor.has_pending_workflows():
                    await executor.execute_next()
                else:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_shutdown_signal_handling(self):
        """Test handling of shutdown signals (SIGTERM, SIGINT)."""
        state_manager = StateManager()
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        # Setup signal handlers
        shutdown_initiated = False
        
        def signal_handler(signum, frame):
            nonlocal shutdown_initiated
            shutdown_initiated = True
            print(f"Received signal {signum}")
        
        # Register handlers
        original_sigterm = signal.signal(signal.SIGTERM, signal_handler)
        original_sigint = signal.signal(signal.SIGINT, signal_handler)
        
        try:
            # Start a workflow
            workflow_def = WorkflowDefinition(
                name="signal_test",
                version="1.0",
                steps=[
                    WorkflowStep(
                        id="process",
                        type="wait",
                        config={"duration": 2}
                    )
                ]
            )
            
            await executor.start_workflow(workflow_def, {})
            
            # Simulate SIGTERM
            os.kill(os.getpid(), signal.SIGTERM)
            
            # Small delay for signal processing
            await asyncio.sleep(0.1)
            
            # Verify signal was handled
            assert shutdown_initiated
            
        finally:
            # Restore original handlers
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)


class TestConfigurationValidation:
    """Test configuration validation and management."""
    
    @pytest.mark.asyncio
    async def test_configuration_schema_validation(self):
        """Test validation of configuration files."""
        # Create test configuration
        config = {
            "workflow_server": {
                "max_concurrent_workflows": 10,
                "max_queued_workflows": 100,
                "default_timeout": 300,
                "enable_monitoring": True,
                "monitoring": {
                    "metrics_interval": 60,
                    "retention_days": 7,
                    "export_format": "prometheus"
                },
                "security": {
                    "enable_auth": True,
                    "auth_provider": "jwt",
                    "token_expiry": 3600
                },
                "database": {
                    "type": "postgresql",
                    "host": "localhost",
                    "port": 5432,
                    "name": "workflow_db"
                }
            }
        }
        
        # Validate configuration
        from aromcp.workflow_server.deployment.config import ConfigValidator
        validator = ConfigValidator()
        
        validation_result = validator.validate(config)
        assert validation_result['valid'] == True
        assert len(validation_result['errors']) == 0
        
        # Test invalid configuration
        invalid_config = {
            "workflow_server": {
                "max_concurrent_workflows": -1,  # Invalid: negative value
                "monitoring": {
                    "export_format": "invalid_format"  # Invalid format
                }
            }
        }
        
        validation_result = validator.validate(invalid_config)
        assert validation_result['valid'] == False
        assert len(validation_result['errors']) > 0
        assert any('max_concurrent_workflows' in error for error in validation_result['errors'])
    
    @pytest.mark.asyncio
    async def test_environment_variable_override(self):
        """Test configuration override via environment variables."""
        # Set environment variables
        os.environ['WORKFLOW_MAX_CONCURRENT'] = '20'
        os.environ['WORKFLOW_TIMEOUT'] = '600'
        os.environ['WORKFLOW_MONITORING_ENABLED'] = 'false'
        
        try:
            # Load configuration with env overrides
            from aromcp.workflow_server.deployment.config import ConfigLoader
            loader = ConfigLoader()
            
            base_config = {
                "workflow_server": {
                    "max_concurrent_workflows": 10,
                    "default_timeout": 300,
                    "enable_monitoring": True
                }
            }
            
            final_config = loader.load_with_overrides(base_config)
            
            # Verify overrides applied
            assert final_config['workflow_server']['max_concurrent_workflows'] == 20
            assert final_config['workflow_server']['default_timeout'] == 600
            assert final_config['workflow_server']['enable_monitoring'] == False
            
        finally:
            # Clean up environment
            os.environ.pop('WORKFLOW_MAX_CONCURRENT', None)
            os.environ.pop('WORKFLOW_TIMEOUT', None)
            os.environ.pop('WORKFLOW_MONITORING_ENABLED', None)
    
    @pytest.mark.asyncio
    async def test_configuration_hot_reload(self):
        """Test configuration hot-reloading without restart."""
        from aromcp.workflow_server.deployment.config import ConfigManager
        
        # Create initial config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            initial_config = {
                "workflow_server": {
                    "max_concurrent_workflows": 5,
                    "enable_debug": False
                }
            }
            yaml.dump(initial_config, f)
            config_path = f.name
        
        try:
            # Initialize config manager
            config_manager = ConfigManager(config_path)
            config_manager.start_watching()
            
            # Get initial config
            config = config_manager.get_config()
            assert config['workflow_server']['max_concurrent_workflows'] == 5
            assert config['workflow_server']['enable_debug'] == False
            
            # Update config file
            updated_config = {
                "workflow_server": {
                    "max_concurrent_workflows": 10,
                    "enable_debug": True
                }
            }
            with open(config_path, 'w') as f:
                yaml.dump(updated_config, f)
            
            # Wait for reload
            await asyncio.sleep(1)
            
            # Verify config reloaded
            new_config = config_manager.get_config()
            assert new_config['workflow_server']['max_concurrent_workflows'] == 10
            assert new_config['workflow_server']['enable_debug'] == True
            
            # Stop watching
            config_manager.stop_watching()
            
        finally:
            # Clean up
            os.unlink(config_path)


class TestMonitoringAPIAvailability:
    """Test monitoring and metrics API availability."""
    
    @pytest.fixture
    def metrics_system(self):
        """Create system with metrics collection."""
        metrics_collector = MetricsCollector()
        metrics_exporter = MetricsExporter(format="prometheus")
        observability = ObservabilityManager()
        
        return {
            'collector': metrics_collector,
            'exporter': metrics_exporter,
            'observability': observability
        }
    
    @pytest.mark.asyncio
    async def test_prometheus_metrics_endpoint(self, metrics_system):
        """Test Prometheus metrics endpoint."""
        collector = metrics_system['collector']
        exporter = metrics_system['exporter']
        
        # Generate some metrics
        collector.increment('workflow_started_total', labels={'type': 'test'})
        collector.increment('workflow_completed_total', labels={'type': 'test', 'status': 'success'})
        collector.record_histogram('workflow_duration_seconds', 2.5, labels={'type': 'test'})
        collector.set_gauge('active_workflows', 3)
        
        # Export metrics in Prometheus format
        metrics_output = exporter.export()
        
        # Verify Prometheus format
        assert '# HELP workflow_started_total' in metrics_output
        assert '# TYPE workflow_started_total counter' in metrics_output
        assert 'workflow_started_total{type="test"} 1' in metrics_output
        
        assert '# HELP workflow_duration_seconds' in metrics_output
        assert '# TYPE workflow_duration_seconds histogram' in metrics_output
        
        assert '# HELP active_workflows' in metrics_output
        assert '# TYPE active_workflows gauge' in metrics_output
        assert 'active_workflows 3' in metrics_output
    
    @pytest.mark.asyncio
    async def test_metrics_api_endpoints(self, metrics_system):
        """Test various metrics API endpoints."""
        observability = metrics_system['observability']
        
        # Test workflow metrics endpoint
        workflow_metrics = await observability.get_workflow_metrics(
            time_range="1h",
            aggregation="5m"
        )
        
        assert 'time_series' in workflow_metrics
        assert 'summary' in workflow_metrics
        
        summary = workflow_metrics['summary']
        assert 'total_workflows' in summary
        assert 'success_rate' in summary
        assert 'avg_duration' in summary
        
        # Test system metrics endpoint
        system_metrics = await observability.get_system_metrics()
        
        assert 'cpu_usage' in system_metrics
        assert 'memory_usage' in system_metrics
        assert 'active_threads' in system_metrics
        assert 'queue_depth' in system_metrics
        
        # Test custom query endpoint
        custom_query = await observability.query_metrics(
            metric="workflow_duration_seconds",
            labels={"type": "test"},
            time_range="30m"
        )
        
        assert 'data' in custom_query
        assert 'metadata' in custom_query


class TestAuditTrailCompleteness:
    """Test audit trail and compliance logging."""
    
    @pytest.mark.asyncio
    async def test_workflow_audit_trail(self):
        """Test complete audit trail for workflow execution."""
        state_manager = StateManager()
        
        # Create audit logger
        from aromcp.workflow_server.deployment.audit import AuditLogger
        audit_logger = AuditLogger()
        
        executor = QueueBasedWorkflowExecutor(
            state_manager=state_manager,
            audit_logger=audit_logger
        )
        
        # Workflow with various operations
        workflow_def = WorkflowDefinition(
            name="audit_test",
            version="1.0",
            metadata={
                "compliance_level": "high",
                "data_classification": "sensitive"
            },
            steps=[
                WorkflowStep(
                    id="user_input",
                    type="user_input",
                    config={
                        "prompt": "Enter sensitive data",
                        "schema": {"type": "object"}
                    }
                ),
                WorkflowStep(
                    id="process_data",
                    type="agent_prompt",
                    config={
                        "prompt": "Process sensitive information"
                    }
                ),
                WorkflowStep(
                    id="store_result",
                    type="state_update",
                    config={
                        "updates": {"processed": True}
                    }
                )
            ]
        )
        
        # Execute workflow
        result = await executor.start_workflow(
            workflow_def,
            {},
            user_context={"user_id": "test_user", "role": "admin"}
        )
        workflow_id = result['workflow_id']
        
        # Mock user input and agent response
        mock_mcp = AsyncMock()
        mock_mcp.call_tool.return_value = {"content": "Processed"}
        
        async def mock_user_input(*args, **kwargs):
            return {"data": "sensitive_info"}
        
        with patch('src.aromcp.workflow_server.workflow.queue_executor.get_mcp_client', return_value=mock_mcp):
            with patch('src.aromcp.workflow_server.workflow.steps.user_input.get_user_input', side_effect=mock_user_input):
                while executor.has_pending_workflows():
                    await executor.execute_next()
        
        # Retrieve audit trail
        audit_trail = audit_logger.get_workflow_audit_trail(workflow_id)
        
        # Verify comprehensive audit logging
        assert len(audit_trail) > 0
        
        # Check for key audit events
        event_types = [event['type'] for event in audit_trail]
        assert 'workflow_started' in event_types
        assert 'user_input_received' in event_types
        assert 'step_executed' in event_types
        assert 'workflow_completed' in event_types
        
        # Verify audit entry structure
        for event in audit_trail:
            assert 'timestamp' in event
            assert 'type' in event
            assert 'user_context' in event
            assert 'details' in event
            
            # Sensitive data should be masked
            if 'data' in event['details']:
                assert 'sensitive_info' not in str(event['details'])
    
    @pytest.mark.asyncio
    async def test_compliance_reporting(self):
        """Test compliance reporting capabilities."""
        from aromcp.workflow_server.deployment.audit import ComplianceReporter
        
        reporter = ComplianceReporter()
        
        # Generate compliance report
        report = await reporter.generate_compliance_report(
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow(),
            compliance_standards=["SOC2", "HIPAA"]
        )
        
        assert 'summary' in report
        assert 'details' in report
        assert 'recommendations' in report
        
        summary = report['summary']
        assert 'total_workflows' in summary
        assert 'compliance_score' in summary
        assert 'violations' in summary
        
        # Check specific compliance checks
        details = report['details']
        assert 'access_controls' in details
        assert 'data_encryption' in details
        assert 'audit_logging' in details
        assert 'retention_policies' in details


class TestSecurityBoundaryValidation:
    """Test security boundaries and access controls."""
    
    @pytest.mark.asyncio
    async def test_workflow_isolation(self):
        """Test workflow isolation and resource boundaries."""
        state_manager = StateManager()
        
        # Create security manager
        from aromcp.workflow_server.deployment.security import SecurityManager
        security_manager = SecurityManager()
        
        executor = QueueBasedWorkflowExecutor(
            state_manager=state_manager,
            security_manager=security_manager
        )
        
        # Create workflows with different security contexts
        workflow_def = WorkflowDefinition(
            name="isolated_workflow",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="access_data",
                    type="state_update",
                    config={
                        "updates": {"data": "sensitive"}
                    }
                )
            ]
        )
        
        # Start workflows in different security contexts
        context1 = {"tenant_id": "tenant1", "user_id": "user1"}
        context2 = {"tenant_id": "tenant2", "user_id": "user2"}
        
        result1 = await executor.start_workflow(workflow_def, {}, security_context=context1)
        result2 = await executor.start_workflow(workflow_def, {}, security_context=context2)
        
        workflow_id1 = result1['workflow_id']
        workflow_id2 = result2['workflow_id']
        
        # Execute workflows
        while executor.has_pending_workflows():
            await executor.execute_next()
        
        # Verify isolation
        # Tenant 1 should not access tenant 2's workflow
        with pytest.raises(PermissionError):
            state_manager.get_workflow_state(
                workflow_id2,
                security_context=context1
            )
        
        # Each tenant can access their own workflow
        state1 = state_manager.get_workflow_state(
            workflow_id1,
            security_context=context1
        )
        assert state1 is not None
        
        state2 = state_manager.get_workflow_state(
            workflow_id2,
            security_context=context2
        )
        assert state2 is not None
    
    @pytest.mark.asyncio
    async def test_resource_access_control(self):
        """Test resource access control enforcement."""
        from aromcp.workflow_server.deployment.security import ResourceAccessControl
        
        rac = ResourceAccessControl()
        
        # Define access policies
        policies = {
            "workflows": {
                "create": ["admin", "developer"],
                "read": ["admin", "developer", "viewer"],
                "update": ["admin", "developer"],
                "delete": ["admin"]
            },
            "monitoring": {
                "read": ["admin", "operator"],
                "export": ["admin"]
            }
        }
        
        rac.load_policies(policies)
        
        # Test access checks
        # Admin should have all permissions
        assert rac.check_access("admin", "workflows", "delete") == True
        assert rac.check_access("admin", "monitoring", "export") == True
        
        # Developer has limited permissions
        assert rac.check_access("developer", "workflows", "create") == True
        assert rac.check_access("developer", "workflows", "delete") == False
        assert rac.check_access("developer", "monitoring", "read") == False
        
        # Viewer has read-only access
        assert rac.check_access("viewer", "workflows", "read") == True
        assert rac.check_access("viewer", "workflows", "create") == False
    
    @pytest.mark.asyncio
    async def test_api_authentication(self):
        """Test API authentication mechanisms."""
        from aromcp.workflow_server.deployment.security import AuthenticationManager
        
        auth_manager = AuthenticationManager(
            provider="jwt",
            secret_key="test_secret_key"
        )
        
        # Generate token for user
        user_info = {
            "user_id": "test_user",
            "role": "developer",
            "tenant_id": "tenant1"
        }
        
        token = auth_manager.generate_token(user_info)
        assert token is not None
        
        # Validate token
        validated_info = auth_manager.validate_token(token)
        assert validated_info is not None
        assert validated_info['user_id'] == user_info['user_id']
        assert validated_info['role'] == user_info['role']
        
        # Test invalid token
        invalid_token = "invalid.token.here"
        validated_info = auth_manager.validate_token(invalid_token)
        assert validated_info is None
        
        # Test expired token
        expired_token = auth_manager.generate_token(
            user_info,
            expiry_seconds=0  # Already expired
        )
        await asyncio.sleep(0.1)
        validated_info = auth_manager.validate_token(expired_token)
        assert validated_info is None


class TestProductionDeploymentScenarios:
    """Test various production deployment scenarios."""
    
    @pytest.mark.asyncio
    async def test_rolling_deployment_compatibility(self):
        """Test compatibility during rolling deployments."""
        # Simulate mixed version deployment
        from aromcp.workflow_server.deployment.versioning import VersionManager
        
        version_manager = VersionManager()
        
        # Old version workflow definition
        old_workflow = {
            "name": "test_workflow",
            "version": "1.0",
            "api_version": "v1",
            "steps": [
                {
                    "id": "step1",
                    "type": "state_update",
                    "config": {
                        "updates": {"value": "test"}
                    }
                }
            ]
        }
        
        # New version with additional features
        new_workflow = {
            "name": "test_workflow",
            "version": "1.0",
            "api_version": "v2",
            "steps": [
                {
                    "id": "step1",
                    "type": "state_update",
                    "config": {
                        "updates": {"value": "test"},
                        "validation": {"required": True}  # New feature
                    }
                }
            ]
        }
        
        # Test backward compatibility
        is_compatible = version_manager.check_compatibility(
            old_version=old_workflow,
            new_version=new_workflow
        )
        
        assert is_compatible == True
        
        # Test migration path
        migration_plan = version_manager.get_migration_plan(
            from_version="v1",
            to_version="v2"
        )
        
        assert migration_plan is not None
        assert 'steps' in migration_plan
        assert len(migration_plan['steps']) > 0
    
    @pytest.mark.asyncio
    async def test_database_migration_safety(self):
        """Test database migration safety checks."""
        from aromcp.workflow_server.deployment.migrations import MigrationManager
        
        migration_manager = MigrationManager()
        
        # Check for pending migrations
        pending = await migration_manager.get_pending_migrations()
        
        # Validate migration safety
        for migration in pending:
            validation = await migration_manager.validate_migration(migration)
            
            assert validation['safe'] == True
            assert 'warnings' in validation
            assert 'estimated_duration' in validation
            
            # Check for blocking operations
            if validation['warnings']:
                for warning in validation['warnings']:
                    assert 'blocking' not in warning.lower()
    
    @pytest.mark.asyncio
    async def test_backup_and_recovery(self):
        """Test backup and recovery procedures."""
        state_manager = StateManager()
        
        from aromcp.workflow_server.deployment.backup import BackupManager
        backup_manager = BackupManager(state_manager=state_manager)
        
        # Create some workflow data
        executor = QueueBasedWorkflowExecutor(state_manager=state_manager)
        
        workflow_def = WorkflowDefinition(
            name="backup_test",
            version="1.0",
            steps=[
                WorkflowStep(
                    id="step1",
                    type="state_update",
                    config={"updates": {"data": "important"}}
                )
            ]
        )
        
        # Execute workflow
        result = await executor.start_workflow(workflow_def, {})
        workflow_id = result['workflow_id']
        await executor.execute_next()
        
        # Create backup
        backup_id = await backup_manager.create_backup(
            backup_type="full",
            description="Test backup"
        )
        
        assert backup_id is not None
        
        # Verify backup
        backup_info = await backup_manager.get_backup_info(backup_id)
        assert backup_info['status'] == 'completed'
        assert backup_info['size'] > 0
        assert 'checksum' in backup_info
        
        # Test restore
        restore_result = await backup_manager.restore_backup(
            backup_id=backup_id,
            target="test_restore"
        )
        
        assert restore_result['success'] == True
        assert restore_result['restored_items'] > 0
        
        # Verify data integrity after restore
        restored_state = state_manager.get_workflow_state(workflow_id)
        assert restored_state['state']['data'] == 'important'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])