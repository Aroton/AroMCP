"""Tests for workflow MCP tools."""

import pytest
import tempfile
import os
import yaml
from unittest.mock import AsyncMock, patch

from aromcp.workflow_server.tools.workflow_start import workflow_start_impl
from aromcp.workflow_server.tools.submit_result import submit_result_impl
from aromcp.workflow_server.tools.workflow_status import workflow_status_impl
from aromcp.workflow_server.models.workflow_models import (
    StartWorkflowResponse,
    SubmitResultResponse,
    GetWorkflowStatusResponse
)


class TestWorkflowStartTool:
    """Test class for workflow_start tool."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_workflow(self, filename: str, content: dict) -> str:
        """Create a test workflow file."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w') as f:
            yaml.dump(content, f)
        return file_path

    @pytest.mark.asyncio
    async def test_start_workflow_basic(self):
        """Test basic workflow start functionality."""
        # Define test workflow content
        workflow_content = {
            "name": "test-workflow",
            "steps": [
                {"id": "step1", "type": "shell", "command": "echo hello"}
            ]
        }
        
        # Mock the YAML loader and temporal manager
        with patch('aromcp.workflow_server.tools.workflow_start.load_workflow_yaml') as mock_load_yaml, \
             patch('aromcp.workflow_server.tools.workflow_start.get_temporal_manager') as mock_get_manager, \
             patch('aromcp.workflow_server.pending_actions.get_pending_actions_manager') as mock_get_pending:
            
            # Setup YAML loader mock
            mock_load_yaml.return_value = workflow_content
            
            # Setup temporal manager mock
            mock_manager = AsyncMock()
            mock_manager.connected = True
            
            # Create mock workflow handle (use Mock instead of AsyncMock for get_status)
            from unittest.mock import Mock
            mock_handle = Mock()
            mock_handle.get_status.return_value = {
                "workflow_id": "wf-123",
                "status": "running",
                "result": None,
                "error": None
            }
            
            mock_manager.start_workflow.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            # Setup pending actions manager mock  
            mock_pending_manager = Mock()
            mock_pending_manager.get_action.return_value = None
            mock_get_pending.return_value = mock_pending_manager
            
            # Call workflow_start
            response = await workflow_start_impl("test-workflow", None)
            
            # Verify response
            assert isinstance(response, StartWorkflowResponse)
            assert response.workflow_id == "wf-123"
            assert response.status == "running"
            assert response.action is None
            assert response.result is None
            assert response.error is None

    @pytest.mark.asyncio
    async def test_start_workflow_with_inputs(self):
        """Test workflow start with input parameters."""
        workflow_content = {
            "name": "parameterized-workflow",
            "inputs": {"required": ["param1"]},
            "steps": [
                {"id": "step1", "action": "shell", "command": "echo {{ inputs.param1 }}"}
            ]
        }
        workflow_file = self.create_test_workflow("param.yaml", workflow_content)
        
        with patch('aromcp.workflow_server.tools.workflow_start.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "param-wf-123"
            mock_handle.status = "running"
            mock_manager.start_workflow.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            inputs = {"param1": "test-value"}
            response = await workflow_start_impl(workflow_file, inputs)
            
            assert isinstance(response, WorkflowStartResponse)
            assert response.workflow_id == "param-wf-123"

    @pytest.mark.asyncio
    async def test_start_workflow_with_pending_action(self):
        """Test workflow start that immediately requires Claude action."""
        workflow_content = {
            "name": "interactive-workflow",
            "steps": [
                {"id": "step1", "action": "prompt", "message": "What should I do?"}
            ]
        }
        workflow_file = self.create_test_workflow("interactive.yaml", workflow_content)
        
        with patch('aromcp.workflow_server.tools.workflow_start.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "interactive-wf-123"
            mock_handle.status = "pending_action"
            mock_handle.get_pending_action.return_value = {
                "step_id": "step1",
                "action_type": "prompt",
                "parameters": {"message": "What should I do?"}
            }
            mock_manager.start_workflow.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            response = await workflow_start_impl(workflow_file, None)
            
            assert isinstance(response, WorkflowStartResponse)
            assert response.status == "pending_action"
            assert response.action is not None
            assert response.action["action_type"] == "prompt"

    @pytest.mark.asyncio
    async def test_start_workflow_file_not_found(self):
        """Test workflow start with non-existent file."""
        non_existent_file = "/non/existent/workflow.yaml"
        
        response = await workflow_start_impl(non_existent_file, None)
        
        # Should return error response
        assert isinstance(response, dict)
        assert "error" in response
        assert response["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_start_workflow_malformed_yaml(self):
        """Test workflow start with malformed YAML."""
        # Create malformed YAML
        malformed_file = os.path.join(self.temp_dir, "malformed.yaml")
        with open(malformed_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        response = await workflow_start_impl(malformed_file, None)
        
        assert isinstance(response, dict)
        assert "error" in response
        assert response["error"]["code"] == "INVALID_INPUT"


class TestWorkflowSubmitTool:
    """Test class for submit_result tool."""

    @pytest.mark.asyncio
    async def test_submit_result_basic(self):
        """Test basic result submission."""
        with patch('aromcp.workflow_server.tools.submit_result.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "wf-123"
            mock_handle.status = "running"
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_manager.signal_workflow = AsyncMock()
            mock_get_manager.return_value = mock_manager
            
            result = {"output": "command completed successfully"}
            response = await submit_result_impl("wf-123", result)
            
            assert isinstance(response, WorkflowSubmitResponse)
            assert response.workflow_id == "wf-123"
            assert response.status == "running"
            
            # Verify signal was sent
            mock_manager.signal_workflow.assert_called_once_with(
                "wf-123", "action_result", result
            )

    @pytest.mark.asyncio
    async def test_submit_result_with_next_action(self):
        """Test result submission that leads to next pending action."""
        with patch('aromcp.workflow_server.tools.submit_result.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "wf-456"
            mock_handle.status = "pending_action"
            mock_handle.get_pending_action.return_value = {
                "step_id": "step2",
                "action_type": "shell",
                "parameters": {"command": "ls -la"}
            }
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_manager.signal_workflow = AsyncMock()
            mock_get_manager.return_value = mock_manager
            
            result = {"output": "step1 completed"}
            response = await submit_result_impl("wf-456", result)
            
            assert isinstance(response, WorkflowSubmitResponse)
            assert response.status == "pending_action"
            assert response.action is not None
            assert response.action["action_type"] == "shell"

    @pytest.mark.asyncio
    async def test_submit_result_workflow_completed(self):
        """Test result submission that completes workflow."""
        with patch('aromcp.workflow_server.tools.submit_result.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "wf-789"
            mock_handle.status = "completed"
            mock_handle.result = {"final": "all steps completed"}
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_manager.signal_workflow = AsyncMock()
            mock_get_manager.return_value = mock_manager
            
            result = {"output": "final step done"}
            response = await submit_result_impl("wf-789", result)
            
            assert isinstance(response, WorkflowSubmitResponse)
            assert response.status == "completed"
            assert response.result is not None
            assert response.result["final"] == "all steps completed"

    @pytest.mark.asyncio
    async def test_submit_result_workflow_not_found(self):
        """Test result submission for non-existent workflow."""
        with patch('aromcp.workflow_server.tools.submit_result.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_workflow_handle.return_value = None
            mock_get_manager.return_value = mock_manager
            
            response = await submit_result_impl("non-existent", {"result": "test"})
            
            assert isinstance(response, dict)
            assert "error" in response
            assert response["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_submit_result_workflow_failed(self):
        """Test result submission for failed workflow."""
        with patch('aromcp.workflow_server.tools.submit_result.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "failed-wf"
            mock_handle.status = "failed"
            mock_handle.error = "Workflow execution failed"
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            response = await submit_result_impl("failed-wf", {"result": "test"})
            
            assert isinstance(response, WorkflowSubmitResponse)
            assert response.status == "failed"
            assert response.error == "Workflow execution failed"


class TestWorkflowStatusTool:
    """Test class for workflow_status tool."""

    @pytest.mark.asyncio
    async def test_get_status_running_workflow(self):
        """Test getting status of running workflow."""
        with patch('aromcp.workflow_server.tools.workflow_status.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "running-wf"
            mock_handle.status = "running"
            mock_handle.current_step = 2
            mock_handle.state = {"step1_result": "done", "current": "processing"}
            mock_handle.created_at = "2025-01-01T10:00:00"
            mock_handle.updated_at = "2025-01-01T10:05:00"
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            response = await workflow_status_impl("running-wf")
            
            assert isinstance(response, WorkflowStatusResponse)
            assert response.workflow_id == "running-wf"
            assert response.status == "running"
            assert response.current_step == "step-2"  # Converted to step name
            assert response.state is not None

    @pytest.mark.asyncio
    async def test_get_status_pending_action_workflow(self):
        """Test getting status of workflow with pending action."""
        with patch('aromcp.workflow_server.tools.workflow_status.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "pending-wf"
            mock_handle.status = "pending_action"
            mock_handle.get_pending_action.return_value = {
                "step_id": "step3",
                "action_type": "mcp_call",
                "parameters": {"tool": "list_files", "path": "/tmp"}
            }
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            response = await workflow_status_impl("pending-wf")
            
            assert isinstance(response, WorkflowStatusResponse)
            assert response.status == "pending_action"
            assert response.pending_action is not None
            assert response.pending_action["action_type"] == "mcp_call"

    @pytest.mark.asyncio
    async def test_get_status_completed_workflow(self):
        """Test getting status of completed workflow."""
        with patch('aromcp.workflow_server.tools.workflow_status.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "completed-wf"
            mock_handle.status = "completed"
            mock_handle.result = {"success": True, "output": "All done"}
            mock_handle.total_steps = 5
            mock_handle.current_step = 5
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            response = await workflow_status_impl("completed-wf")
            
            assert isinstance(response, WorkflowStatusResponse)
            assert response.status == "completed"
            assert "success" in str(response.state)  # Result should be in state

    @pytest.mark.asyncio
    async def test_get_status_workflow_not_found(self):
        """Test getting status of non-existent workflow."""
        with patch('aromcp.workflow_server.tools.workflow_status.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_workflow_handle.return_value = None
            mock_get_manager.return_value = mock_manager
            
            response = await workflow_status_impl("non-existent-wf")
            
            assert isinstance(response, dict)
            assert "error" in response
            assert response["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_status_with_progress_info(self):
        """Test getting status with progress information."""
        with patch('aromcp.workflow_server.tools.workflow_status.get_temporal_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_handle = AsyncMock()
            mock_handle.workflow_id = "progress-wf"
            mock_handle.status = "running"
            mock_handle.current_step = 3
            mock_handle.total_steps = 10
            mock_handle.progress = 0.3  # 30% complete
            mock_manager.get_workflow_handle.return_value = mock_handle
            mock_get_manager.return_value = mock_manager
            
            response = await workflow_status_impl("progress-wf")
            
            assert isinstance(response, WorkflowStatusResponse)
            assert response.progress is not None
            # Should include calculated progress information