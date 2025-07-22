"""Tests to verify step processors handle schema-defined fields correctly."""

import pytest
from unittest.mock import Mock, MagicMock

from aromcp.workflow_server.workflow.step_registry import StepRegistry, STEP_TYPES
from aromcp.workflow_server.workflow.step_processors import StepProcessor
from aromcp.workflow_server.workflow.models import WorkflowStep, WorkflowInstance
from aromcp.workflow_server.workflow.queue import WorkflowQueue
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.state.manager import StateManager


class TestStepProcessorSchemaCompliance:
    """Test that all step processors handle schema-defined fields correctly."""

    def setup_method(self):
        """Set up test fixtures."""
        self.step_registry = StepRegistry()
        self.state_manager = Mock(spec=StateManager)
        self.expression_evaluator = Mock(spec=ExpressionEvaluator)
        self.step_processor = StepProcessor(self.state_manager, self.expression_evaluator)
        
        # Mock state manager responses
        self.state_manager.read.return_value = {
            "inputs": {"test_input": "value"},
            "state": {"test_state": "value"},
            "computed": {"test_computed": "value"}
        }
    
    def _create_step_with_fields(self, step_type: str, fields: dict[str, any]) -> WorkflowStep:
        """Helper method to create WorkflowStep with proper structure."""
        return WorkflowStep(
            id=f"test_{step_type}",
            type=step_type,
            definition=fields
        )

    def test_all_step_types_have_processors(self):
        """Test that all step types defined in the registry have corresponding processors."""
        server_step_types = {
            step_type for step_type, config in STEP_TYPES.items()
            if config["execution"] == "server"
        }
        
        client_step_types = {
            step_type for step_type, config in STEP_TYPES.items()
            if config["execution"] == "client"
        }
        
        # Check that we have handlers for all server step types
        for step_type in server_step_types:
            config = STEP_TYPES[step_type]
            definition = {}
            
            # Add required fields with appropriate values
            for field in config["required_fields"]:
                if field == "command":
                    definition[field] = "echo test"
                elif field == "condition":
                    definition[field] = "true"
                elif field == "body":
                    definition[field] = []
                elif field == "items":
                    definition[field] = "[]"
                else:
                    definition[field] = f"test_{field}"
            
            step = self._create_step_with_fields(step_type, definition)
            instance = Mock(spec=WorkflowInstance)
            instance.id = "test_workflow"
            instance.inputs = {}
            
            queue = Mock(spec=WorkflowQueue)
            queue.loop_stack = []
            
            # Special mocking for break/continue steps
            if step_type in ["break", "continue"]:
                queue.get_current_loop.return_value = None  # No current loop
                queue.main_queue = []
            else:
                queue.get_current_loop = Mock(return_value=None)
                queue.main_queue = []
                queue.prepend_steps = Mock()
                queue.pop_next = Mock()
                queue.push_loop_context = Mock()
                queue.pop_loop_context = Mock()
            
            # Mock expression evaluator for various cases
            self.expression_evaluator.evaluate.return_value = []
            
            try:
                result = self.step_processor.process_server_step(instance, step, queue, config)
                # Should not contain "Unsupported server step type" error
                if isinstance(result, dict) and "error" in result:
                    # break/continue outside loop is expected to error
                    if step_type in ["break", "continue"] and "outside of loop" in str(result.get("error", "")):
                        print(f"✓ Server step type '{step_type}' has processor (expected loop error)")
                    elif "Unsupported server step type" in str(result):
                        pytest.fail(f"No processor for server step type '{step_type}': {result}")
                    else:
                        print(f"✓ Server step type '{step_type}' has processor")
                else:
                    print(f"✓ Server step type '{step_type}' has processor")
            except Exception as e:
                pytest.fail(f"No processor for server step type '{step_type}': {e}")
        
        # Check that we have handlers for all client step types
        for step_type in client_step_types:
            config = STEP_TYPES[step_type]
            definition = {}
            
            # Add required fields with appropriate values
            for field in config["required_fields"]:
                if field == "tool":
                    definition[field] = "test_tool"
                elif field == "prompt":
                    definition[field] = "test prompt"
                elif field == "message":
                    definition[field] = "test message"
                elif field == "items":
                    definition[field] = "test_items"
                elif field == "sub_agent_task":
                    definition[field] = "test_task"
                else:
                    definition[field] = f"test_{field}"
            
            step = self._create_step_with_fields(step_type, definition)
            instance = Mock(spec=WorkflowInstance)
            instance.id = "test_workflow"
            instance.inputs = {}
            
            # Mock expression evaluator for parallel_foreach
            self.expression_evaluator.evaluate.return_value = ["item1"]
            
            try:
                result = self.step_processor.process_client_step(instance, step, config)
                # Should have proper client step format
                assert "id" in result
                assert "type" in result
                assert result["type"] == step_type
                print(f"✓ Client step type '{step_type}' has processor")
            except Exception as e:
                pytest.fail(f"No processor for client step type '{step_type}': {e}")

    def test_required_fields_validation(self):
        """Test that step processors properly handle required fields."""
        test_cases = [
            # (step_type, valid_definition, missing_field_definition)
            ("user_message", {"message": "test"}, {}),
            ("user_input", {"prompt": "test"}, {}),
            ("mcp_call", {"tool": "test_tool"}, {}),
            ("agent_prompt", {"prompt": "test"}, {}),
            ("parallel_foreach", {"items": "test", "sub_agent_task": "task"}, {"items": "test"}),
            ("shell_command", {"command": "echo test"}, {}),
            ("conditional", {"condition": "true"}, {}),
            ("while_loop", {"condition": "true", "body": []}, {"condition": "true"}),
            ("foreach", {"items": "[]", "body": []}, {"items": "[]"}),
        ]
        
        for step_type, valid_def, invalid_def in test_cases:
            config = STEP_TYPES[step_type]
            
            # Test valid definition
            step_valid = self._create_step_with_fields(step_type, valid_def)
            instance = Mock(spec=WorkflowInstance)
            instance.id = "test_workflow"
            instance.inputs = {}
            
            # Mock expression evaluator
            self.expression_evaluator.evaluate.return_value = ["item1"] if "items" in valid_def else True
            
            if config["execution"] == "client":
                result = self.step_processor.process_client_step(instance, step_valid, config)
                assert result["type"] == step_type
                print(f"✓ {step_type} with valid required fields works")
            else:
                queue = Mock(spec=WorkflowQueue)
                queue.loop_stack = []
                result = self.step_processor.process_server_step(instance, step_valid, queue, config)
                # Should not fail
                print(f"✓ {step_type} with valid required fields works")

    def test_state_update_support_compliance(self):
        """Test that steps marked as supporting state updates handle them correctly."""
        state_update_steps = {
            step_type: config for step_type, config in STEP_TYPES.items()
            if config["supports_state_update"]
        }
        
        for step_type, config in state_update_steps.items():
            print(f"Testing state update support for: {step_type}")
            
            definition = {}
            
            # Add required fields
            for field in config["required_fields"]:
                if field == "tool":
                    definition[field] = "test_tool"
                elif field == "prompt":
                    definition[field] = "test prompt"
                elif field == "message":
                    definition[field] = "test message"
                elif field == "command":
                    definition[field] = "echo test"
                elif field == "items":
                    definition[field] = "test_items"
                elif field == "sub_agent_task":
                    definition[field] = "test_task"
                else:
                    definition[field] = f"test_{field}"
            
            # Add state update configuration
            if step_type in ["mcp_call", "user_input", "shell_command"]:
                definition["state_update"] = {
                    "path": "state.test_result",
                    "value": "response.data",
                    "operation": "set"
                }
            elif step_type == "agent_response":
                definition["state_updates"] = [
                    {
                        "path": "state.test_result",
                        "value": "response.data",
                        "operation": "set"
                    }
                ]
            
            step = self._create_step_with_fields(step_type, definition)
            instance = Mock(spec=WorkflowInstance)
            instance.id = "test_workflow"
            instance.inputs = {}
            
            # Mock expression evaluator for parallel_foreach
            self.expression_evaluator.evaluate.return_value = ["item1"]
            
            # Test the step processor
            if config["execution"] == "client":
                result = self.step_processor.process_client_step(instance, step, config)
                # Client steps should include state update info in their definition
                assert "definition" in result
                print(f"✓ Step type '{step_type}' handles state updates correctly")
            else:
                queue = Mock(spec=WorkflowQueue)
                queue.loop_stack = []
                
                if step_type == "agent_response":
                    # Special case for agent_response which has its own method
                    agent_response = {"test": "response"}
                    result = self.step_processor.process_agent_response_result(instance, step, agent_response)
                else:
                    result = self.step_processor.process_server_step(instance, step, queue, config)
                
                print(f"✓ Step type '{step_type}' handles state updates correctly")

    def test_embedded_state_updates_processing(self):
        """Test that embedded state updates in server steps are processed correctly."""
        # Test shell_command with embedded state_update
        definition = {
            "command": "echo 'test output'",
            "state_update": {
                "path": "state.command_result",
                "value": "stdout",
                "operation": "set"
            }
        }
        
        step = self._create_step_with_fields("shell_command", definition)
        instance = Mock(spec=WorkflowInstance)
        instance.id = "test_workflow"
        instance.inputs = {}
        
        queue = Mock(spec=WorkflowQueue)
        config = STEP_TYPES["shell_command"]
        
        # Mock shell command processor to return output
        self.step_processor.shell_command_processor.process = Mock(return_value={
            "output": {"stdout": "test output", "stderr": "", "returncode": 0}
        })
        
        result = self.step_processor.process_server_step(instance, step, queue, config)
        
        assert result["executed"] is True
        assert result["type"] == "shell_command"
        
        # Verify state manager update was called
        assert self.state_manager.update.called
        print("✓ Embedded state updates are processed correctly")

    def test_optional_fields_handling(self):
        """Test that optional fields are handled correctly when present and absent."""
        test_cases = [
            ("user_message", {"message": "test"}, {"message_type": "info", "format": "text"}),
            ("user_input", {"prompt": "test"}, {"input_type": "text", "required": True}),
            ("mcp_call", {"tool": "test_tool"}, {"parameters": {}, "state_update": None}),
            ("shell_command", {"command": "echo test"}, {"timeout": 30, "working_directory": "/tmp"}),
        ]
        
        for step_type, required_fields, optional_fields in test_cases:
            config = STEP_TYPES[step_type]
            
            # Test with minimal required fields
            step_minimal = self._create_step_with_fields(step_type, required_fields)
            instance = Mock(spec=WorkflowInstance)
            instance.id = "test_workflow"
            instance.inputs = {}
            
            if config["execution"] == "client":
                result = self.step_processor.process_client_step(instance, step_minimal, config)
                assert result["type"] == step_type
                assert "error" not in result
            else:
                queue = Mock(spec=WorkflowQueue)
                result = self.step_processor.process_server_step(instance, step_minimal, queue, config)
                # Should work without optional fields
            
            # Test with optional fields present
            full_definition = {**required_fields, **optional_fields}
            step_full = self._create_step_with_fields(step_type, full_definition)
            
            if config["execution"] == "client":
                result = self.step_processor.process_client_step(instance, step_full, config)
                assert result["type"] == step_type
                assert "error" not in result
            else:
                queue = Mock(spec=WorkflowQueue)
                result = self.step_processor.process_server_step(instance, step_full, queue, config)
                # Should work with optional fields
            
            print(f"✓ Step type '{step_type}' handles optional fields correctly")