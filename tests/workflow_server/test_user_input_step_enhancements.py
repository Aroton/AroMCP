"""
Enhanced tests for User Input Step - AC-UI-011 and AC-UI-012

This file contains additional tests for:
- AC-UI-011: Complex validation expressions
- AC-UI-012: Long input handling and timeout scenarios
"""

import time
from unittest.mock import Mock

import pytest

from aromcp.workflow_server.workflow.steps.user_message import UserInputProcessor


class TestComplexValidationExpressions:
    """Test complex validation expressions - AC-UI-011"""

    def test_user_input_with_expression_based_validation(self):
        """Test user input with complex expression-based validation (AC-UI-011)."""
        step_definition = {
            "prompt": "Enter quantity:",
            "input_type": "number",
            "validation_expression": "value >= state.min_quantity && value <= state.max_quantity",
            "validation_message": "Quantity must be between {{ state.min_quantity }} and {{ state.max_quantity }}",
            "state_context": ["state.min_quantity", "state.max_quantity"]
        }
        
        state_manager = Mock()
        state_manager.read.return_value = {
            "state": {"min_quantity": 10, "max_quantity": 100}
        }
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert "validation_expression" in result["agent_action"]
        assert "state_context" in result["agent_action"]

    def test_user_input_with_conditional_validation(self):
        """Test user input with conditional validation based on state (AC-UI-011)."""
        step_definition = {
            "prompt": "Enter discount code:",
            "input_type": "string",
            "validation_expression": "state.is_premium_user ? true : value.match(/^BASIC-/)",
            "validation_message": "Non-premium users must use codes starting with 'BASIC-'",
            "state_context": ["state.is_premium_user"]
        }
        
        state_manager = Mock()
        state_manager.read.return_value = {
            "state": {"is_premium_user": False}
        }
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["validation_expression"] is not None

    def test_user_input_with_multi_field_validation(self):
        """Test user input validation against multiple state fields (AC-UI-011)."""
        step_definition = {
            "prompt": "Enter allocation percentage:",
            "input_type": "number",
            "validation_expression": """
                (value + state.current_allocation) <= 100 && 
                value >= computed.min_allocation_size &&
                value % inputs.allocation_increment === 0
            """,
            "validation_message": "Invalid allocation percentage",
            "state_context": [
                "state.current_allocation",
                "computed.min_allocation_size",
                "inputs.allocation_increment"
            ]
        }
        
        state_manager = Mock()
        state_manager.read.return_value = {
            "state": {"current_allocation": 60},
            "computed": {"min_allocation_size": 5},
            "inputs": {"allocation_increment": 5}
        }
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert len(result["agent_action"]["state_context"]) == 3

    def test_user_input_with_async_validation_callback(self):
        """Test user input with async validation callback support (AC-UI-011)."""
        step_definition = {
            "prompt": "Enter username:",
            "input_type": "string",
            "validation_callback": "check_username_availability",
            "validation_message": "Username is not available",
            "validation_timeout": 5
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert "validation_callback" in result["agent_action"]
        assert result["agent_action"]["validation_timeout"] == 5

    def test_user_input_with_custom_error_messages(self):
        """Test user input with custom error messages based on validation type (AC-UI-011)."""
        step_definition = {
            "prompt": "Enter password:",
            "input_type": "string",
            "validations": [
                {
                    "expression": "value.length >= 8",
                    "message": "Password must be at least 8 characters long"
                },
                {
                    "expression": "value.match(/[A-Z]/)",
                    "message": "Password must contain at least one uppercase letter"
                },
                {
                    "expression": "value.match(/[0-9]/)",
                    "message": "Password must contain at least one number"
                },
                {
                    "expression": "value.match(/[!@#$%^&*]/)",
                    "message": "Password must contain at least one special character"
                }
            ]
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert "validations" in result["agent_action"]
        assert len(result["agent_action"]["validations"]) == 4


class TestLongInputAndTimeoutScenarios:
    """Test long input handling and timeout scenarios - AC-UI-012"""

    def test_user_input_with_timeout_configuration(self):
        """Test user input with timeout configuration (AC-UI-012)."""
        step_definition = {
            "prompt": "Please provide detailed feedback:",
            "input_type": "string",
            "timeout_seconds": 300,  # 5 minute timeout
            "timeout_warning_seconds": 240,  # Warning at 4 minutes
            "timeout_message": "Your input session will expire in 1 minute"
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["agent_action"]["timeout_seconds"] == 300
        assert result["agent_action"]["timeout_warning_seconds"] == 240

    def test_user_input_with_large_text_handling(self):
        """Test user input handling for large text inputs (AC-UI-012)."""
        step_definition = {
            "prompt": "Paste your configuration file:",
            "input_type": "text",  # Multi-line text
            "max_length": 50000,  # 50KB limit
            "encoding": "utf-8",
            "sanitize": True,
            "compress_storage": True  # Store compressed if over 10KB
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["agent_action"]["max_length"] == 50000
        assert result["agent_action"]["compress_storage"] is True

    def test_user_input_with_file_upload_simulation(self):
        """Test user input with file upload simulation (AC-UI-012)."""
        step_definition = {
            "prompt": "Upload your CSV file:",
            "input_type": "file",
            "accepted_formats": [".csv", ".tsv"],
            "max_file_size": 10485760,  # 10MB
            "parse_content": True,
            "validation_expression": "parsed_data.rows.length > 0 && parsed_data.rows.length <= 10000"
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["agent_action"]["input_type"] == "file"
        assert result["agent_action"]["max_file_size"] == 10485760

    def test_user_input_with_progressive_disclosure(self):
        """Test user input with progressive disclosure pattern (AC-UI-012)."""
        step_definition = {
            "prompt": "Configure advanced settings:",
            "input_type": "structured",
            "fields": [
                {
                    "name": "mode",
                    "type": "choice",
                    "choices": ["basic", "advanced"],
                    "default": "basic"
                },
                {
                    "name": "advanced_options",
                    "type": "object",
                    "visible_when": "mode === 'advanced'",
                    "fields": [
                        {"name": "cache_size", "type": "number", "default": 100},
                        {"name": "enable_compression", "type": "boolean", "default": False}
                    ]
                }
            ]
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["agent_action"]["input_type"] == "structured"
        assert "fields" in result["agent_action"]

    def test_user_input_with_retry_after_timeout(self):
        """Test user input retry behavior after timeout (AC-UI-012)."""
        step_definition = {
            "prompt": "Enter verification code:",
            "input_type": "string",
            "timeout_seconds": 60,
            "timeout_action": "retry",
            "timeout_retry_prompt": "The code has expired. A new code has been sent.",
            "max_timeout_retries": 3,
            "final_timeout_action": "fail"
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert result["agent_action"]["timeout_action"] == "retry"
        assert result["agent_action"]["max_timeout_retries"] == 3


class TestUserInputIntegrationWithInfrastructure:
    """Test user input integration with new infrastructure components"""

    def test_user_input_with_timeout_manager_integration(self):
        """Test user input timeout handling with TimeoutManager (AC-UI-012)."""
        from aromcp.workflow_server.workflow.timeout_manager import TimeoutManager
        
        timeout_manager = TimeoutManager()
        
        step_definition = {
            "prompt": "Enter your response:",
            "input_type": "string",
            "timeout_seconds": 120
        }
        
        # Set up timeout tracking
        timeout_manager.set_step_timeout("user_input_1", timeout_seconds=120)
        timeout_manager.start_step("user_input_1")
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        
        # Verify timeout is being tracked
        assert not timeout_manager.check_timeout("user_input_1")
        
        # Simulate timeout scenario
        # In real scenario, would wait for actual timeout
        # time.sleep(121)
        # assert timeout_manager.check_timeout("user_input_1")

    def test_user_input_with_debug_manager_tracking(self):
        """Test user input tracking with DebugManager (AC-UI-011)."""
        from aromcp.workflow_server.debugging.debug_tools import DebugManager
        
        debug_manager = DebugManager()
        debug_manager.set_debug_mode(True)
        
        step_definition = {
            "prompt": "Enter debug value:",
            "input_type": "string",
            "debug_capture": True
        }
        
        # Add checkpoint before input
        debug_manager.add_checkpoint(
            workflow_id="test_workflow_123",
            step_id="user_input_debug",
            state_before={"awaiting_input": True},
            step_config=step_definition
        )
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        
        # Verify debug tracking
        checkpoints = debug_manager.get_workflow_checkpoints("test_workflow_123")
        assert len(checkpoints) > 0
        assert checkpoints[0].step_config["prompt"] == "Enter debug value:"

    def test_user_input_with_performance_monitoring(self):
        """Test user input performance monitoring (AC-UI-012)."""
        from aromcp.workflow_server.monitoring.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        # Start monitoring user input operation
        monitor.start_operation("user_input_collection", {
            "workflow_id": "test_workflow_123",
            "input_type": "complex_form"
        })
        
        step_definition = {
            "prompt": "Complete the form:",
            "input_type": "structured",
            "performance_tracking": True
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        start_time = time.time()
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        processing_time = time.time() - start_time
        monitor.record_metric("input_processing_time", processing_time)
        
        monitor.end_operation("user_input_collection")
        
        # Verify metrics collected
        metrics = monitor.get_metrics_summary("input_processing_time")
        assert metrics is not None
        assert metrics["count"] >= 1

    def test_user_input_validation_error_recovery(self):
        """Test user input validation error recovery with retry logic (AC-UI-011)."""
        from aromcp.workflow_server.errors.handlers import ErrorHandlerRegistry, ErrorHandler
        from aromcp.workflow_server.errors.models import ErrorStrategyType
        
        error_registry = ErrorHandlerRegistry()
        
        # Register validation error handler
        validation_handler = ErrorHandler(
            strategy=ErrorStrategyType.RETRY,
            retry_count=3,
            retry_delay=1000,
            retry_on_error_types=["ValidationError"]
        )
        error_registry.register_handler("user_input_validation", validation_handler)
        
        step_definition = {
            "prompt": "Enter valid code:",
            "input_type": "string",
            "validation_pattern": "^[A-Z]{4}-[0-9]{4}$",
            "error_handler": "user_input_validation"
        }
        
        state_manager = Mock()
        workflow_id = "test_workflow_123"
        
        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)
        
        assert result["status"] == "success"
        assert "error_handler" in result["agent_action"]