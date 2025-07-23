"""
Test suite for Wait Step Implementation - Acceptance Criteria 3.4

This file tests the following acceptance criteria:
- AC 3.4.1: Workflow execution pause until client polling
- AC 3.4.2: Optional wait message display to client
- AC 3.4.3: Optional timeout configuration (future enhancement)
- AC 3.4.4: Workflow state preservation during wait period

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

import pytest
from unittest.mock import Mock, MagicMock

from aromcp.workflow_server.workflow.steps.wait_step import WaitStepProcessor


class TestWaitStepBehavior:
    """Test wait step behavior and execution pause functionality."""

    def test_wait_step_pauses_execution_for_client_polling(self):
        """Test wait step pauses execution for client polling."""
        step_definition = {
            "message": "Waiting for external process to complete..."
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        assert result["wait_for_client"] == True
        assert result["execution_type"] == "wait"
        assert result["message"] == "Waiting for external process to complete..."

    def test_wait_step_displays_optional_message(self):
        """Test wait step displays optional message to client."""
        step_definition = {
            "message": "Please check the external service status and continue when ready"
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["message"] == "Please check the external service status and continue when ready"
        assert result["status"] == "wait"

    def test_wait_step_default_message_when_none_provided(self):
        """Test wait step uses default message when none provided."""
        step_definition = {}  # No message provided
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["message"] == "Waiting for next client request..."
        assert result["status"] == "wait"
        assert result["wait_for_client"] == True

    def test_wait_step_preserves_workflow_state(self):
        """Test wait step preserves workflow state during wait period."""
        step_definition = {
            "message": "Waiting for user confirmation..."
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Wait step should not modify state
        state_manager.update_state.assert_not_called()
        state_manager.get_state.assert_not_called()
        
        # Should return wait status for queue management
        assert result["status"] == "wait"
        assert result["execution_type"] == "wait"

    def test_wait_step_timeout_configuration_future_enhancement(self):
        """Test wait step timeout configuration (future enhancement)."""
        step_definition = {
            "message": "Waiting with timeout...",
            "timeout_seconds": 300  # 5 minutes
        }
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Current implementation should handle timeout_seconds gracefully
        assert result["status"] == "wait"
        assert result["message"] == "Waiting with timeout..."
        
        # Future: timeout_seconds should be included in result for queue processing
        # This tests that the field is accepted without error

    def test_wait_step_minimal_configuration(self):
        """Test wait step with minimal configuration."""
        step_definition = {}  # Completely empty step definition
        
        workflow_id = "test_workflow_123"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        assert result["wait_for_client"] == True
        assert result["execution_type"] == "wait"
        assert "message" in result  # Should have default message

    def test_wait_step_workflow_id_handling(self):
        """Test wait step properly handles workflow_id parameter."""
        step_definition = {
            "message": "Testing workflow ID handling"
        }
        
        workflow_id = "specific_workflow_456"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Wait step doesn't need to use workflow_id directly,
        # but should accept it without error
        assert result["status"] == "wait"
        assert result["message"] == "Testing workflow ID handling"


class TestWaitStepIntegration:
    """Test wait step integration with workflow execution engine."""

    def test_wait_step_with_subsequent_steps(self):
        """Test wait step integration with subsequent workflow steps."""
        step_definition = {
            "message": "Waiting before next operation..."
        }
        
        workflow_id = "integration_test_789"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Result should indicate to queue executor to pause
        assert result["status"] == "wait"
        assert result["wait_for_client"] == True
        
        # Queue executor should be able to resume after client continues
        assert result["execution_type"] == "wait"

    def test_wait_step_in_loop_constructs(self):
        """Test wait step behavior within loop constructs."""
        step_definition = {
            "message": "Waiting in loop iteration..."
        }
        
        workflow_id = "loop_test_101"
        state_manager = Mock()
        
        # Simulate multiple calls (as would happen in a loop)
        result1 = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        result2 = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Each wait should behave identically
        assert result1["status"] == "wait"
        assert result2["status"] == "wait"
        assert result1["message"] == result2["message"]
        
        # Should not accumulate state or side effects
        assert state_manager.call_count == 0

    def test_wait_step_error_handling(self):
        """Test wait step error handling with invalid configurations."""
        # Test with invalid message type
        step_definition = {
            "message": 12345  # Invalid type, should be string
        }
        
        workflow_id = "error_test_202"
        state_manager = Mock()
        
        # Should handle gracefully (convert to string or use default)
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        # Message should be handled gracefully - converted to string
        assert "message" in result
        assert isinstance(result["message"], str)
        assert result["message"] == "12345"  # Should convert integer to string

    def test_wait_step_with_empty_message(self):
        """Test wait step with empty message string."""
        step_definition = {
            "message": ""  # Empty string
        }
        
        workflow_id = "empty_message_test"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        # Should fall back to default message for empty string
        assert "message" in result
        assert result["message"] == "Waiting for next client request..."

    def test_wait_step_queue_integration_signals(self):
        """Test wait step signals for queue executor integration."""
        step_definition = {
            "message": "Queue integration test"
        }
        
        workflow_id = "queue_test_303"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Should provide all necessary signals for queue management
        expected_signals = ["status", "wait_for_client", "execution_type", "message"]
        for signal in expected_signals:
            assert signal in result
        
        assert result["status"] == "wait"
        assert result["wait_for_client"] == True
        assert result["execution_type"] == "wait"

    def test_wait_step_state_manager_not_used(self):
        """Test wait step doesn't use state_manager parameter."""
        step_definition = {
            "message": "State manager test"
        }
        
        workflow_id = "state_test_404"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        # Wait step should not interact with state manager
        assert not state_manager.called
        assert result["status"] == "wait"

    def test_wait_step_concurrent_processing(self):
        """Test wait step behavior under concurrent processing scenarios."""
        step_definition = {
            "message": "Concurrent processing test"
        }
        
        workflow_id_1 = "concurrent_test_1"
        workflow_id_2 = "concurrent_test_2"
        state_manager = Mock()
        
        # Simulate concurrent calls for different workflows
        result1 = WaitStepProcessor.process(step_definition, workflow_id_1, state_manager)
        result2 = WaitStepProcessor.process(step_definition, workflow_id_2, state_manager)
        
        # Results should be independent
        assert result1["status"] == "wait"
        assert result2["status"] == "wait"
        assert result1["message"] == result2["message"]
        
        # No shared state or interference
        assert result1 == result2  # Same configuration should yield identical results

    def test_wait_step_message_variable_substitution_readiness(self):
        """Test wait step message field for future variable substitution support."""
        step_definition = {
            "message": "Waiting for {{ process_name }} to complete..."
        }
        
        workflow_id = "variable_test_505"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        # Current implementation should preserve template as-is
        # Future enhancement could support variable substitution
        assert "{{ process_name }}" in result["message"]

    def test_wait_step_with_none_message(self):
        """Test wait step with None message value."""
        step_definition = {
            "message": None
        }
        
        workflow_id = "none_message_test"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        assert result["message"] == "Waiting for next client request..."

    def test_wait_step_with_whitespace_only_message(self):
        """Test wait step with whitespace-only message."""
        step_definition = {
            "message": "   \t\n   "  # Only whitespace
        }
        
        workflow_id = "whitespace_message_test"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        assert result["message"] == "Waiting for next client request..."

    def test_wait_step_with_complex_object_message(self):
        """Test wait step with complex object as message."""
        step_definition = {
            "message": {"key": "value", "nested": [1, 2, 3]}
        }
        
        workflow_id = "complex_message_test"
        state_manager = Mock()
        
        result = WaitStepProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "wait"
        assert isinstance(result["message"], str)
        # Should convert dict to string representation
        assert "key" in result["message"] and "value" in result["message"]