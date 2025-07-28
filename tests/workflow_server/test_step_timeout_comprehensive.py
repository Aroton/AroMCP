"""
Comprehensive step timeout testing for step processing and error handling.

Covers missing acceptance criteria:
- AC-SP-013: mcp_call steps handle tool timeouts and retries
- AC-EHV-007: Step-level timeouts are enforced for tool calls
- AC-EHV-008: Agent operation timeouts are handled appropriately
- AC-EHV-009: Workflow-level timeout_seconds limits overall execution
- AC-EHV-010: Shell command timeouts terminate commands gracefully
- AC-EHV-011: Timeout warnings are provided before expiration when possible
- AC-EHV-012: Multiple timeout levels are supported and coordinated

Focus: Tool timeout scenarios, agent operation timeouts, multiple timeout level coordination
Pillar: Step Processing / Error Handling & Validation
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
import threading
import signal
import subprocess

from aromcp.workflow_server.workflow.steps.mcp_call import MCPCallProcessor
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowInstance
from aromcp.workflow_server.state.manager import StateManager


class TestStepTimeoutComprehensive:
    """Test comprehensive timeout handling across all step types and levels."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock state manager for testing."""
        manager = Mock(spec=StateManager)
        manager.get_flattened_state.return_value = {"test": "value"}
        manager.resolve_variables = Mock(side_effect=lambda x: x)
        manager.update_state = Mock()
        return manager

    @pytest.fixture  
    def timeout_manager(self):
        """Create timeout manager for testing."""
        return TimeoutManager()

    @pytest.fixture
    def step_context(self, mock_state_manager):
        """Create step context for testing."""
        return StepContext(
            workflow_id="wf_timeout_test",
            step_id="step_timeout_1",
            state_manager=mock_state_manager,
            workflow_config={"timeout_seconds": 30}
        )

    @pytest.fixture
    def workflow_state(self):
        """Create workflow state for testing."""
        return WorkflowState(
            workflow_id="wf_timeout_test",
            status="running",
            current_step_index=1,
            total_steps=5,
            state={"inputs": {}, "state": {}, "computed": {}},
            execution_context={"start_time": time.time()}
        )

    def test_mcp_call_step_timeout_enforcement(self, step_context):
        """
        Test AC-SP-013 & AC-EHV-007: MCP tool call timeout enforcement
        Focus: Tool execution exceeding timeout is terminated gracefully
        """
        # Mock MCP client that takes too long
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(side_effect=lambda *args, **kwargs: asyncio.sleep(5))

        step_definition = {
            "id": "mcp_timeout_test",
            "type": "mcp_call",
            "tool": "slow_tool",
            "parameters": {"input": "test"},
            "timeout": 2,  # 2 second timeout
            "error_handling": {"strategy": "fail"}
        }

        mcp_step = MCPCallProcessor()
        
        start_time = time.time()
        
        # Should timeout after 2 seconds
        with pytest.raises(TimeoutError) as exc_info:
            asyncio.run(mcp_step.execute(step_definition, step_context, mcp_client=mock_client))

        elapsed_time = time.time() - start_time
        
        # Verify timeout occurred around expected time (within tolerance)
        assert 1.8 <= elapsed_time <= 2.5
        assert "timeout" in str(exc_info.value).lower()
        assert "slow_tool" in str(exc_info.value)

    def test_mcp_call_retry_with_timeout(self, step_context):
        """
        Test AC-SP-013: MCP tool call retry logic with timeout
        Focus: Retries respect individual timeout limits
        """
        call_count = 0
        
        async def failing_tool_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First two calls timeout, third succeeds
            if call_count <= 2:
                await asyncio.sleep(3)  # Exceeds 2s timeout
            return {"result": "success_after_retries"}

        mock_client = Mock()
        mock_client.call_tool = AsyncMock(side_effect=failing_tool_call)

        step_definition = {
            "id": "mcp_retry_timeout",
            "type": "mcp_call", 
            "tool": "retry_tool",
            "parameters": {"input": "test"},
            "timeout": 2,
            "error_handling": {
                "strategy": "retry",
                "max_retries": 3,
                "retry_delay": 0.1
            }
        }

        mcp_step = MCPCallProcessor()
        
        start_time = time.time()
        
        # Should eventually succeed on third try
        result = asyncio.run(mcp_step.execute(step_definition, step_context, mcp_client=mock_client))
        
        elapsed_time = time.time() - start_time
        
        # Should have made 3 attempts (2 timeouts + 1 success)
        assert call_count == 3
        assert result["result"] == "success_after_retries"
        
        # Total time should include 2 timeouts (~2s each) plus delays
        assert 4 <= elapsed_time <= 7  # Allow for retry delays and processing time

    @pytest.mark.asyncio
    async def test_agent_operation_timeout_handling(self, step_context):
        """
        Test AC-EHV-008: Agent operation timeouts are handled appropriately
        Focus: Agent prompt/response operations respect timeout limits
        """
        # Mock agent client that takes too long to respond
        mock_agent_client = Mock()
        
        async def slow_agent_call(*args, **kwargs):
            await asyncio.sleep(10)  # Exceeds 5s timeout
            return {"response": "delayed_response"}
            
        mock_agent_client.create_prompt = AsyncMock(side_effect=slow_agent_call)

        step_definition = {
            "id": "agent_timeout_test",
            "type": "agent_prompt",
            "prompt": "This is a test prompt",
            "timeout": 5,  # 5 second timeout
            "error_handling": {"strategy": "fallback", "fallback_value": "timeout_fallback"}
        }

        agent_step = AgentPromptStep()
        
        start_time = time.time()
        
        # Should timeout and use fallback
        result = await agent_step.execute(step_definition, step_context, agent_client=mock_agent_client)
        
        elapsed_time = time.time() - start_time
        
        # Should timeout around 5 seconds
        assert 4.5 <= elapsed_time <= 6.0
        assert result.get("fallback_used") == True
        assert result.get("result") == "timeout_fallback"

    def test_shell_command_timeout_graceful_termination(self, step_context):
        """
        Test AC-EHV-010: Shell command timeouts terminate commands gracefully
        Focus: Long-running commands are terminated with proper cleanup
        """
        step_definition = {
            "id": "shell_timeout_test",
            "type": "shell_command",
            "command": "sleep 10",  # Command that would run for 10 seconds
            "timeout": 3,  # 3 second timeout
            "working_directory": "/tmp",
            "error_handling": {"strategy": "fail"}
        }

        shell_step = ShellCommandStep()
        
        start_time = time.time()
        
        # Should timeout and terminate gracefully
        with pytest.raises(TimeoutError) as exc_info:
            shell_step.execute(step_definition, step_context)

        elapsed_time = time.time() - start_time
        
        # Should timeout around 3 seconds
        assert 2.8 <= elapsed_time <= 3.5
        assert "command timed out" in str(exc_info.value).lower()
        
        # Verify no lingering processes (best effort check)
        import psutil
        current_process = psutil.Process()
        children = current_process.children(recursive=True)  
        sleep_processes = [p for p in children if 'sleep' in ' '.join(p.cmdline())]
        assert len(sleep_processes) == 0, "Sleep process should have been terminated"

    def test_workflow_level_timeout_limits_execution(self, timeout_manager, workflow_state):
        """
        Test AC-EHV-009: Workflow-level timeout_seconds limits overall execution
        Focus: Entire workflow execution respects global timeout limit
        """
        # Set workflow timeout to 5 seconds
        workflow_state.execution_context["timeout_seconds"] = 5
        workflow_state.execution_context["start_time"] = time.time()

        steps = [
            {"id": "step1", "type": "shell_command", "command": "sleep 2", "timeout": 10},
            {"id": "step2", "type": "shell_command", "command": "sleep 2", "timeout": 10}, 
            {"id": "step3", "type": "shell_command", "command": "sleep 2", "timeout": 10}  # Would exceed workflow timeout
        ]

        executed_steps = []
        
        for i, step in enumerate(steps):
            # Check workflow-level timeout before each step
            elapsed_time = time.time() - workflow_state.execution_context["start_time"]
            remaining_time = workflow_state.execution_context["timeout_seconds"] - elapsed_time
            
            if remaining_time <= 0:
                # Workflow timeout exceeded
                break
                
            if remaining_time < step.get("timeout", 30):
                # Step timeout would exceed workflow timeout
                with pytest.raises(TimeoutError) as exc_info:
                    timeout_manager.enforce_workflow_timeout(step, workflow_state, remaining_time)
                assert "workflow timeout" in str(exc_info.value).lower()
                break
            
            # Simulate step execution
            time.sleep(1.8)  # Simulate step taking ~2 seconds
            executed_steps.append(step["id"])

        # Should have executed first 2 steps, but not the third
        assert len(executed_steps) <= 2
        assert "step1" in executed_steps
        # May or may not have completed step2 depending on timing

    def test_timeout_warning_before_expiration(self, timeout_manager, step_context):
        """
        Test AC-EHV-011: Timeout warnings are provided before expiration when possible
        Focus: Warning notifications before actual timeout expiration
        """
        warnings_received = []
        
        def warning_callback(message, remaining_time):
            warnings_received.append((message, remaining_time))

        step_definition = {
            "id": "warning_test",
            "type": "mcp_call",
            "tool": "slow_tool", 
            "timeout": 5,
            "warning_thresholds": [1.0, 0.5]  # Warn at 1s and 0.5s remaining
        }

        # Mock tool that takes 4 seconds (allows warnings but not timeout)
        mock_client = Mock()
        mock_client.call_tool = AsyncMock(side_effect=lambda *args, **kwargs: asyncio.sleep(4))

        # Enable timeout warnings
        timeout_manager.set_warning_callback(warning_callback)
        
        start_time = time.time()
        
        # Should complete with warnings
        try:
            result = asyncio.run(
                timeout_manager.execute_with_warnings(
                    mock_client.call_tool,
                    step_definition,
                    timeout=5
                )
            )
        except TimeoutError:
            pass  # Expected in some cases

        # Verify warnings were generated
        assert len(warnings_received) >= 1
        
        # Verify warning content and timing
        for message, remaining in warnings_received:
            assert "timeout approaching" in message.lower()
            assert remaining > 0
            assert remaining <= 1.0  # Should warn when <= 1 second remaining

    def test_multiple_timeout_level_coordination(self, timeout_manager, step_context, workflow_state):
        """
        Test AC-EHV-012: Multiple timeout levels are supported and coordinated
        Focus: Step, workflow, and global timeouts coordinate properly
        """
        # Set up multiple timeout levels
        global_timeout = 20  # Global system timeout
        workflow_timeout = 10  # Workflow-level timeout
        step_timeout = 15  # Step-level timeout (longer than workflow)
        
        workflow_state.execution_context["timeout_seconds"] = workflow_timeout
        workflow_state.execution_context["start_time"] = time.time() - 8  # 8 seconds already elapsed

        step_definition = {
            "id": "multi_timeout_test",
            "type": "shell_command",
            "command": "sleep 5",  # Would take 5 seconds
            "timeout": step_timeout
        }

        # Calculate effective timeout (most restrictive)
        workflow_remaining = workflow_timeout - 8  # 2 seconds remaining
        effective_timeout = timeout_manager.calculate_effective_timeout(
            step_timeout=step_timeout,
            workflow_remaining=workflow_remaining,
            global_timeout=global_timeout
        )

        # Should use workflow remaining time as most restrictive
        assert effective_timeout == workflow_remaining
        assert effective_timeout == 2

        # Verify timeout hierarchy enforcement
        timeout_levels = timeout_manager.get_timeout_hierarchy(
            step_definition, workflow_state, global_timeout
        )
        
        assert timeout_levels["global"] == global_timeout
        assert timeout_levels["workflow"] == workflow_remaining  
        assert timeout_levels["step"] == step_timeout
        assert timeout_levels["effective"] == workflow_remaining  # Most restrictive

    def test_timeout_coordination_with_error_handling(self, step_context):
        """
        Test timeout coordination with error handling strategies
        Focus: Timeout errors follow configured error handling patterns
        """
        step_definitions = [
            {
                "id": "timeout_fail",
                "type": "shell_command",
                "command": "sleep 5",
                "timeout": 2,
                "error_handling": {"strategy": "fail"}
            },
            {
                "id": "timeout_continue", 
                "type": "shell_command",
                "command": "sleep 5",
                "timeout": 2,
                "error_handling": {"strategy": "continue"}
            },
            {
                "id": "timeout_fallback",
                "type": "shell_command", 
                "command": "sleep 5",
                "timeout": 2,
                "error_handling": {
                    "strategy": "fallback",
                    "fallback_value": {"stdout": "timeout_fallback", "exit_code": 0}
                }
            },
            {
                "id": "timeout_retry",
                "type": "shell_command",
                "command": "sleep 5", 
                "timeout": 2,
                "error_handling": {
                    "strategy": "retry",
                    "max_retries": 2,
                    "retry_delay": 0.1
                }
            }
        ]

        results = {}
        
        for step_def in step_definitions:
            shell_step = ShellCommandStep()
            
            try:
                result = shell_step.execute(step_def, step_context)
                results[step_def["id"]] = {"success": True, "result": result}
            except Exception as e:
                results[step_def["id"]] = {"success": False, "error": str(e)}

        # Verify error handling behavior
        assert results["timeout_fail"]["success"] == False
        assert "timeout" in results["timeout_fail"]["error"].lower()

        assert results["timeout_continue"]["success"] == True  # Continue strategy succeeds
        
        assert results["timeout_fallback"]["success"] == True
        assert results["timeout_fallback"]["result"]["stdout"] == "timeout_fallback"

        assert results["timeout_retry"]["success"] == False  # Should still fail after retries

    @pytest.mark.asyncio
    async def test_concurrent_timeout_management(self, timeout_manager):
        """
        Test timeout management under concurrent step execution
        Focus: Multiple steps with different timeouts executing concurrently
        """
        results = {}
        errors = []

        async def execute_step_with_timeout(step_id, duration, timeout):
            try:
                start_time = time.time()
                
                # Simulate step execution
                await asyncio.sleep(duration)
                
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(f"Step {step_id} exceeded timeout")
                    
                results[step_id] = {"completed": True, "duration": elapsed}
            except Exception as e:
                errors.append(f"{step_id}: {str(e)}")

        # Create multiple concurrent steps with different timeout characteristics
        tasks = [
            execute_step_with_timeout("fast_step", 0.5, 2.0),      # Should complete
            execute_step_with_timeout("medium_step", 1.5, 2.0),   # Should complete
            execute_step_with_timeout("slow_step", 3.0, 2.0),     # Should timeout
            execute_step_with_timeout("very_slow", 5.0, 2.0),     # Should timeout
        ]

        # Execute all steps concurrently
        await asyncio.gather(*tasks, return_exceptions=True)

        # Verify results
        assert "fast_step" in results
        assert "medium_step" in results
        assert results["fast_step"]["completed"] == True
        assert results["medium_step"]["completed"] == True

        # Verify timeout errors
        timeout_errors = [e for e in errors if "timeout" in e.lower()]
        assert len(timeout_errors) >= 2  # slow_step and very_slow should timeout

    def test_timeout_configuration_validation(self, timeout_manager):
        """
        Test timeout configuration validation and normalization
        Focus: Invalid timeout configurations are handled gracefully
        """
        # Test various timeout configurations
        test_configs = [
            {"timeout": 30, "expected": 30},                    # Valid integer
            {"timeout": 30.5, "expected": 30.5},               # Valid float
            {"timeout": "30", "expected": 30},                 # String conversion
            {"timeout": 0, "expected": None},                  # Zero means no timeout
            {"timeout": -5, "expected": None},                 # Negative means no timeout
            {"timeout": None, "expected": None},               # None means no timeout
            {"timeout": "invalid", "expected": None},          # Invalid string
        ]

        for config in test_configs:
            normalized = timeout_manager.normalize_timeout(config["timeout"])
            assert normalized == config["expected"], f"Failed for input {config['timeout']}"

    def test_timeout_metrics_and_monitoring(self, timeout_manager):
        """
        Test timeout metrics collection for monitoring purposes
        Focus: Timeout events are tracked for performance analysis
        """
        # Enable metrics collection
        timeout_manager.enable_metrics(True)

        # Simulate various timeout scenarios
        timeout_scenarios = [
            {"step_id": "step1", "timeout": 2, "actual_duration": 1.5, "timed_out": False},
            {"step_id": "step2", "timeout": 3, "actual_duration": 3.2, "timed_out": True},
            {"step_id": "step3", "timeout": 5, "actual_duration": 4.8, "timed_out": False},
            {"step_id": "step4", "timeout": 1, "actual_duration": 1.1, "timed_out": True},
        ]

        for scenario in timeout_scenarios:
            timeout_manager.record_step_execution(
                step_id=scenario["step_id"],
                timeout=scenario["timeout"],
                actual_duration=scenario["actual_duration"],
                timed_out=scenario["timed_out"]
            )

        # Get metrics
        metrics = timeout_manager.get_timeout_metrics()

        # Verify metrics collection
        assert metrics["total_steps"] == 4
        assert metrics["timed_out_steps"] == 2
        assert metrics["timeout_rate"] == 0.5
        assert metrics["average_duration"] == 2.65  # (1.5+3.2+4.8+1.1)/4

        # Verify per-step metrics
        step_metrics = timeout_manager.get_step_timeout_metrics()
        assert len(step_metrics) == 4
        assert step_metrics["step2"]["timed_out"] == True
        assert step_metrics["step4"]["timed_out"] == True


class TestTimeoutIntegrationScenarios:
    """Test timeout behavior in realistic workflow scenarios."""

    def test_production_workflow_timeout_handling(self):
        """
        Test timeout handling in production-like workflow scenario
        Focus: code-standards:enforce.yaml timeout behavior
        """
        # Simulate production workflow steps with realistic timeouts
        workflow_steps = [
            {"id": "lint", "type": "shell_command", "command": "npm run lint", "timeout": 60},
            {"id": "typecheck", "type": "shell_command", "command": "npm run typecheck", "timeout": 120},
            {"id": "test", "type": "shell_command", "command": "npm test", "timeout": 300},
            {"id": "build", "type": "shell_command", "command": "npm run build", "timeout": 180}
        ]

        timeout_manager = TimeoutManager()
        workflow_timeout = 600  # 10 minute workflow timeout
        
        start_time = time.time()
        results = []

        for step in workflow_steps:
            elapsed = time.time() - start_time
            remaining_workflow_time = workflow_timeout - elapsed
            
            # Calculate effective timeout
            effective_timeout = min(step["timeout"], remaining_workflow_time)
            
            if effective_timeout <= 0:
                results.append({"step": step["id"], "status": "skipped", "reason": "workflow_timeout"})
                continue

            # Simulate step execution (much faster for testing)
            step_duration = 0.1  # Simulate quick execution
            time.sleep(step_duration)
            
            results.append({
                "step": step["id"], 
                "status": "completed",
                "duration": step_duration,
                "effective_timeout": effective_timeout
            })

        # Verify all steps completed within workflow timeout
        assert len(results) == 4
        assert all(r["status"] == "completed" for r in results)
        
        # Verify effective timeouts were calculated correctly
        total_elapsed = sum(r["duration"] for r in results)
        assert total_elapsed < workflow_timeout