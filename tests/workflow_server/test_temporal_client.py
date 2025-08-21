"""Tests for Temporal client (mock implementation)."""

import pytest
import asyncio
import time
from unittest.mock import patch

from aromcp.workflow_server.temporal_client import TemporalManager, MockWorkflowHandle
from aromcp.workflow_server.config import WorkflowServerConfig


class TestMockWorkflowHandle:
    """Test class for MockWorkflowHandle."""

    def test_workflow_handle_creation(self):
        """Test creating a mock workflow handle."""
        handle = MockWorkflowHandle(
            workflow_id="test-workflow",
            workflow_type="TestWorkflow",
            inputs={"param1": "value1"}
        )
        
        assert handle.workflow_id == "test-workflow"
        assert handle.workflow_type == "TestWorkflow"
        assert handle.status == "running"
        assert handle.current_step == 0
        assert handle.inputs == {"param1": "value1"}

    def test_workflow_progress(self):
        """Test workflow step progression."""
        handle = MockWorkflowHandle("test-wf", "TestWorkflow")
        
        # Initial state
        assert handle.current_step == 0
        assert handle.status == "running"
        
        # Progress step
        handle.progress_step()
        assert handle.current_step == 1
        
        # Complete workflow
        handle.complete({"result": "success"})
        assert handle.status == "completed"
        assert handle.result == {"result": "success"}

    def test_workflow_failure(self):
        """Test workflow failure handling."""
        handle = MockWorkflowHandle("test-wf", "TestWorkflow")
        
        # Fail workflow
        handle.fail("Test error message")
        assert handle.status == "failed"
        assert handle.error == "Test error message"

    def test_pending_action_management(self):
        """Test pending action creation and management."""
        handle = MockWorkflowHandle("test-wf", "TestWorkflow")
        
        # Create pending action
        action = handle.create_pending_action(
            "step-1",
            "shell",
            {"command": "echo hello"}
        )
        
        assert action is not None
        assert action.workflow_id == "test-wf"
        assert action.step_id == "step-1"
        assert action.action_type == "shell"
        assert handle.status == "pending_action"

    def test_signal_handling(self):
        """Test workflow signal handling."""
        handle = MockWorkflowHandle("test-wf", "TestWorkflow")
        
        # Create pending action first
        handle.create_pending_action("step-1", "shell", {"command": "echo test"})
        
        # Signal with result
        handle.signal("action_result", {"output": "hello"})
        
        # Should progress and resume running
        assert handle.status == "running"
        assert handle.current_step == 1


class TestTemporalManager:
    """Test class for TemporalManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = WorkflowServerConfig(mock_mode=True)
        self.manager = TemporalManager(self.config)

    @pytest.mark.asyncio
    async def test_connection_mock_mode(self):
        """Test connection in mock mode."""
        await self.manager.connect()
        assert self.manager.client is not None
        assert self.manager._mock_mode is True

    @pytest.mark.asyncio
    async def test_health_check_mock_mode(self):
        """Test health check in mock mode."""
        await self.manager.connect()
        health = await self.manager.health_check()
        assert health is True

    @pytest.mark.asyncio
    async def test_start_workflow_mock(self):
        """Test starting a workflow in mock mode."""
        await self.manager.connect()
        
        handle = await self.manager.start_workflow(
            workflow_type="TestWorkflow",
            workflow_id="test-workflow-1",
            args={"input": "test"}
        )
        
        assert handle is not None
        assert handle.workflow_id == "test-workflow-1"
        assert handle.workflow_type == "TestWorkflow"
        assert handle.status == "running"

    @pytest.mark.asyncio
    async def test_get_workflow_handle(self):
        """Test retrieving workflow handle."""
        await self.manager.connect()
        
        # Start a workflow
        handle1 = await self.manager.start_workflow(
            workflow_type="TestWorkflow",
            workflow_id="test-workflow-2",
            args={"input": "test"}
        )
        
        # Retrieve the handle
        handle2 = await self.manager.get_workflow_handle("test-workflow-2")
        
        assert handle2 is not None
        assert handle1 is handle2  # Should be the same object

    @pytest.mark.asyncio
    async def test_workflow_not_found(self):
        """Test retrieving non-existent workflow."""
        await self.manager.connect()
        
        handle = await self.manager.get_workflow_handle("non-existent")
        assert handle is None

    @pytest.mark.asyncio
    async def test_signal_workflow(self):
        """Test signaling a workflow."""
        await self.manager.connect()
        
        # Start workflow
        handle = await self.manager.start_workflow(
            workflow_type="TestWorkflow",
            workflow_id="signal-test",
            args={"input": "test"}
        )
        
        # Create pending action
        handle.create_pending_action("step-1", "shell", {"command": "echo test"})
        
        # Signal workflow
        await self.manager.signal_workflow("signal-test", "action_result", {"output": "result"})
        
        # Workflow should have progressed
        assert handle.status == "running"

    @pytest.mark.asyncio
    async def test_list_workflows(self):
        """Test listing workflows."""
        await self.manager.connect()
        
        # Start multiple workflows
        await self.manager.start_workflow("WF1", "wf-1", {"input": "1"})
        await self.manager.start_workflow("WF2", "wf-2", {"input": "2"})
        
        workflows = await self.manager.list_workflows()
        assert len(workflows) >= 2
        
        # Check workflow info structure
        wf_ids = [wf["workflow_id"] for wf in workflows]
        assert "wf-1" in wf_ids
        assert "wf-2" in wf_ids

    @pytest.mark.asyncio
    async def test_workflow_step_simulation(self):
        """Test workflow step simulation."""
        await self.manager.connect()
        
        handle = await self.manager.start_workflow(
            workflow_type="MultiStepWorkflow",
            workflow_id="step-test",
            args={"steps": 3}
        )
        
        # Simulate step progression
        for i in range(3):
            # Create action requiring Claude
            action = handle.create_pending_action(
                f"step-{i+1}",
                "shell",
                {"command": f"echo step {i+1}"}
            )
            assert action is not None
            assert handle.status == "pending_action"
            
            # Submit result
            handle.signal("action_result", {"output": f"result {i+1}"})
            handle.progress_step()
        
        # Complete workflow
        handle.complete({"final": "success"})
        assert handle.status == "completed"

    @pytest.mark.asyncio
    async def test_cleanup_workflows(self):
        """Test workflow cleanup functionality."""
        await self.manager.connect()
        
        # Start workflow
        handle = await self.manager.start_workflow("TestWF", "cleanup-test", {})
        assert len(self.manager._workflows) == 1
        
        # Complete workflow
        handle.complete({"result": "done"})
        
        # Cleanup completed workflows
        cleaned = await self.manager.cleanup_completed_workflows()
        assert cleaned >= 1
        assert len(self.manager._workflows) == 0

    @pytest.mark.asyncio
    async def test_connection_failure_simulation(self):
        """Test connection failure handling."""
        # Test with mock_mode disabled
        config = WorkflowServerConfig(mock_mode=False)
        manager = TemporalManager(config)
        
        # Connection should fail without real Temporal server
        with pytest.raises(Exception):
            await manager.connect()

    @pytest.mark.asyncio
    async def test_concurrent_workflow_access(self):
        """Test thread-safe workflow access."""
        await self.manager.connect()
        
        async def create_workflow(wf_id):
            return await self.manager.start_workflow("ConcurrentTest", wf_id, {"id": wf_id})
        
        # Create workflows concurrently
        tasks = [create_workflow(f"concurrent-{i}") for i in range(5)]
        handles = await asyncio.gather(*tasks)
        
        # All workflows should be created successfully
        assert len(handles) == 5
        assert all(h is not None for h in handles)
        
        # All should be accessible
        for i, handle in enumerate(handles):
            retrieved = await self.manager.get_workflow_handle(f"concurrent-{i}")
            assert retrieved is handle