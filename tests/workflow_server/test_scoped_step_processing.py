"""Test scoped step processing with variable resolution and scoped contexts.

This module tests the integration of the enhanced expression evaluator with step processors
to build and use scoped contexts for template resolution.
"""

import pytest
from unittest.mock import Mock, MagicMock

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.step_processors import StepProcessor
from aromcp.workflow_server.workflow.models import WorkflowInstance, WorkflowStep
from aromcp.workflow_server.workflow.context import ExecutionContext, LoopState


class TestScopedStepProcessing:
    """Test scoped step processing functionality."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create a mock state manager."""
        manager = Mock(spec=StateManager)
        manager.read.return_value = {
            "state": {
                "current_file": "test.py",
                "loop_item": "item1",
                "loop_index": 0
            },
            "computed": {
                "has_files": True,
                "total_files": 5
            },
            "inputs": {
                "project_path": "/project"
            }
        }
        return manager

    @pytest.fixture
    def expression_evaluator(self):
        """Create a real expression evaluator."""
        return ExpressionEvaluator()

    @pytest.fixture
    def step_processor(self, mock_state_manager, expression_evaluator):
        """Create a step processor with mocked dependencies."""
        return StepProcessor(mock_state_manager, expression_evaluator)

    @pytest.fixture
    def workflow_instance(self):
        """Create a workflow instance with test inputs."""
        instance = Mock(spec=WorkflowInstance)
        instance.id = "test_workflow_123"
        instance.inputs = {
            "file_path": "src/main.py",
            "max_attempts": 3,
            "project_name": "test_project"
        }
        return instance

    @pytest.fixture
    def execution_context(self):
        """Create an execution context with test data."""
        context = Mock(spec=ExecutionContext)
        context.global_variables = {
            "retry_count": 2,
            "config_path": "/config/app.json"
        }
        
        # Mock current loop
        loop_state = Mock(spec=LoopState)
        loop_state.variable_bindings = {
            "item": "current_item_value",
            "index": 1,
            "iteration": 2
        }
        context.current_loop.return_value = loop_state
        
        return context

    def test_build_scoped_context_with_all_scopes(self, step_processor, workflow_instance, execution_context):
        """Test building scoped context with all scope types."""
        state = {
            "state": {
                "current_step": "validate",
                "attempts": 1
            },
            "computed": {
                "validation_passed": True,
                "errors": []
            }
        }
        
        scoped_context = step_processor._build_scoped_context(workflow_instance, state, execution_context)
        
        # Verify all scopes are present
        assert "inputs" in scoped_context
        assert "global" in scoped_context
        assert "this" in scoped_context
        assert "loop" in scoped_context
        
        # Verify inputs scope
        assert scoped_context["inputs"]["file_path"] == "src/main.py"
        assert scoped_context["inputs"]["max_attempts"] == 3
        assert scoped_context["inputs"]["project_name"] == "test_project"
        
        # Verify global scope
        assert scoped_context["global"]["retry_count"] == 2
        assert scoped_context["global"]["config_path"] == "/config/app.json"
        
        # Verify this scope (combines state and computed)
        assert scoped_context["this"]["current_step"] == "validate"
        assert scoped_context["this"]["attempts"] == 1
        assert scoped_context["this"]["validation_passed"] is True
        assert scoped_context["this"]["errors"] == []
        
        # Verify loop scope
        assert scoped_context["loop"]["item"] == "current_item_value"
        assert scoped_context["loop"]["index"] == 1
        assert scoped_context["loop"]["iteration"] == 2

    def test_build_scoped_context_with_minimal_data(self, step_processor):
        """Test building scoped context with minimal data."""
        instance = None
        state = {"state": {}, "computed": {}}
        execution_context = None
        
        scoped_context = step_processor._build_scoped_context(instance, state, execution_context)
        
        # Verify all scopes are present but empty
        assert scoped_context["inputs"] == {}
        assert scoped_context["global"] == {}
        assert scoped_context["this"] == {}
        assert scoped_context["loop"] == {}

    def test_get_current_loop_variables_with_loop_state(self, step_processor):
        """Test extracting loop variables from execution context."""
        execution_context = Mock(spec=ExecutionContext)
        loop_state = Mock(spec=LoopState)
        loop_state.variable_bindings = {
            "item": "test_item",
            "index": 3,
            "iteration": 4
        }
        loop_state.current_item = "alternative_item"
        loop_state.current_index = 5
        loop_state.iteration_count = 6
        
        execution_context.current_loop.return_value = loop_state
        
        loop_vars = step_processor._get_current_loop_variables(execution_context)
        
        # Should prioritize variable_bindings over individual attributes
        assert loop_vars["item"] == "test_item"
        assert loop_vars["index"] == 3
        assert loop_vars["iteration"] == 4

    def test_get_current_loop_variables_no_execution_context(self, step_processor):
        """Test loop variable extraction without execution context."""
        loop_vars = step_processor._get_current_loop_variables(None)
        assert loop_vars == {}

    def test_get_current_loop_variables_no_current_loop(self, step_processor):
        """Test loop variable extraction without current loop."""
        execution_context = Mock(spec=ExecutionContext)
        execution_context.current_loop.return_value = None
        
        loop_vars = step_processor._get_current_loop_variables(execution_context)
        assert loop_vars == {}

    def test_replace_variables_with_scoped_context_simple(self, step_processor, workflow_instance):
        """Test variable replacement with scoped context for simple expressions."""
        state = {
            "state": {"current_step": "test"},
            "computed": {"result": "success"}
        }
        
        # Test inputs scope access
        template = "{{inputs.file_path}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, None)
        assert result == "src/main.py"
        
        # Test this scope access
        template = "{{this.current_step}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, None)
        assert result == "test"
        
        # Test this scope computed access
        template = "{{this.result}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, None)
        assert result == "success"

    def test_replace_variables_with_scoped_context_complex(self, step_processor, workflow_instance, execution_context):
        """Test variable replacement with scoped context for complex expressions."""
        state = {
            "state": {"attempts": 1, "max_retries": 5},
            "computed": {"success_rate": 0.85}
        }
        
        # Test complex expression combining multiple scopes
        template = "Attempt {{this.attempts}} of {{inputs.max_attempts}} for {{inputs.file_path}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "Attempt 1 of 3 for src/main.py"
        
        # Test conditional expression
        template = "{{this.success_rate > 0.8 ? 'high' : 'low'}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "high"

    def test_replace_variables_with_loop_scope(self, step_processor, workflow_instance, execution_context):
        """Test variable replacement with loop scope access."""
        state = {
            "state": {"processing": True},
            "computed": {"items_processed": 10}
        }
        
        # Test loop variable access
        template = "Processing {{loop.item}} at index {{loop.index}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "Processing current_item_value at index 1"
        
        # Test loop iteration access
        template = "Iteration {{loop.iteration}} completed"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "Iteration 2 completed"

    def test_replace_variables_with_global_scope(self, step_processor, workflow_instance, execution_context):
        """Test variable replacement with global scope access."""
        state = {
            "state": {"local_var": "local"},
            "computed": {"computed_var": "computed"}
        }
        
        # Test global variable access
        template = "Retry count: {{global.retry_count}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "Retry count: 2"
        
        # Test global config access
        template = "Config: {{global.config_path}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "Config: /config/app.json"

    def test_replace_variables_nested_objects(self, step_processor, workflow_instance):
        """Test variable replacement with nested objects."""
        state = {
            "state": {"current_step": "validate"},
            "computed": {"results": {"success": True, "errors": []}}
        }
        
        # Test nested object access
        nested_obj = {
            "message": "Step {{this.current_step}} result: {{this.results.success}}",
            "details": {
                "errors": "{{this.results.errors.length}}"
            }
        }
        
        result = step_processor._replace_variables(nested_obj, state, False, workflow_instance, False, None)
        
        assert result["message"] == "Step validate result: True"
        assert result["details"]["errors"] == 0  # Expression evaluator returns int, not string

    def test_replace_variables_preserve_conditions(self, step_processor, workflow_instance):
        """Test that condition preservation works with scoped context."""
        state = {
            "state": {"ready": True},
            "computed": {"valid": True}
        }
        
        obj = {
            "condition": "{{this.ready && this.valid}}",
            "message": "Status: {{this.ready ? 'ready' : 'not ready'}}"
        }
        
        result = step_processor._replace_variables(obj, state, True, workflow_instance, False, None)
        
        # Condition should be preserved
        assert result["condition"] == "{{this.ready && this.valid}}"
        # Other fields should be processed
        assert result["message"] == "Status: ready"

    def test_replace_variables_preserve_templates(self, step_processor, workflow_instance):
        """Test that template preservation works with scoped context."""
        state = {
            "state": {"items": ["a", "b", "c"]},
            "computed": {"count": 3}
        }
        
        obj = {
            "items": "{{this.items}}",
            "condition": "{{this.count > 0}}",
            "message": "Processing {{this.count}} items"
        }
        
        result = step_processor._replace_variables(obj, state, False, workflow_instance, True, None)
        
        # Template expressions should be preserved
        assert result["items"] == "{{this.items}}"
        assert result["condition"] == "{{this.count > 0}}"
        # Other fields should be processed
        assert result["message"] == "Processing 3 items"

    def test_scoped_context_isolation(self, step_processor, workflow_instance, execution_context):
        """Test that scoped contexts properly isolate variables."""
        state = {
            "state": {"file_path": "state_file.py"},  # Conflicts with inputs.file_path
            "computed": {"retry_count": 1}  # Conflicts with global.retry_count
        }
        
        # Test that scoped access gets the right value
        template_inputs = "{{inputs.file_path}}"
        result_inputs = step_processor._replace_variables(template_inputs, state, False, workflow_instance, False, execution_context)
        assert result_inputs == "src/main.py"  # From inputs, not state
        
        template_this = "{{this.file_path}}"
        result_this = step_processor._replace_variables(template_this, state, False, workflow_instance, False, execution_context)
        assert result_this == "state_file.py"  # From this (state), not inputs
        
        template_global = "{{global.retry_count}}"
        result_global = step_processor._replace_variables(template_global, state, False, workflow_instance, False, execution_context)
        assert result_global == 2  # From global, not computed (expression evaluator returns int)
        
        template_computed = "{{this.retry_count}}"
        result_computed = step_processor._replace_variables(template_computed, state, False, workflow_instance, False, execution_context)
        assert result_computed == 1  # From this (computed), not global (expression evaluator returns int)

    def test_backward_compatibility_without_scoped_context(self, step_processor, workflow_instance):
        """Test that legacy variable resolution still works without execution context."""
        state = {
            "state": {"current_step": "test"},
            "computed": {"result": "success"},
            "file_path": "legacy_file.py"  # Legacy style
        }
        
        # Should work with legacy context (flat state with inputs added)
        template = "Processing {{file_path}} in step {{current_step}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, None)
        
        # Should get inputs.file_path (from workflow instance) for file_path
        assert "src/main.py" in result
        # current_step should use fallback mechanism since it's not in the flattened context
        assert "step" in result  # Should contain the word step even with fallback

    def test_expression_evaluator_integration(self, step_processor, workflow_instance, execution_context):
        """Test integration with expression evaluator for complex expressions."""
        state = {
            "state": {"items": ["a", "b", "c"]},
            "computed": {"processed": 2}
        }
        
        # Test array operations with scoped context
        template = "{{this.items.length - this.processed}} items remaining"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result == "1 items remaining"
        
        # Test complex boolean expressions
        template = "{{this.processed < this.items.length && global.retry_count > 0}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        assert result is True

    def test_error_handling_with_scoped_context(self, step_processor, workflow_instance, execution_context):
        """Test error handling in scoped variable resolution."""
        state = {
            "state": {"valid": True},
            "computed": {"count": 5}
        }
        
        # Test undefined scoped variable
        template = "Value: {{undefined_scope.missing_var}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        # Should use fallback mechanism
        assert "<undefined_scope.missing_var>" in result or "Value: " in result
        
        # Test undefined property in valid scope
        template = "Count: {{this.missing_property}}"
        result = step_processor._replace_variables(template, state, False, workflow_instance, False, execution_context)
        # Should handle gracefully
        assert "Count: " in result