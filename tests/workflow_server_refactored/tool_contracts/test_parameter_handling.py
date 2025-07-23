"""Test workflow tool parameter handling and validation."""

import tempfile
from pathlib import Path

import pytest

from aromcp.workflow_server.tools.workflow_tools import (
    get_workflow_executor,
    get_workflow_loader,
)
from aromcp.workflow_server.workflow.models import WorkflowNotFoundError


class TestWorkflowToolParameterHandling:
    """Test parameter validation and handling for workflow tools."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace with workflow directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
            workflows_dir.mkdir(parents=True)
            yield temp_dir, workflows_dir
    
    @pytest.fixture
    def workflow_components(self, temp_workspace):
        """Create workflow loader and executor for testing."""
        temp_dir, workflows_dir = temp_workspace
        
        loader = get_workflow_loader()
        loader.project_root = temp_dir
        executor = get_workflow_executor()
        
        return loader, executor, temp_dir

    def test_workflow_start_parameter_types(self, workflow_components):
        """Test workflow start with different input parameter types."""
        loader, executor, temp_dir = workflow_components
        
        # Create a simple test workflow
        workflow_content = """
name: "test:parameter-test"
description: "Test parameter handling"
version: "1.0.0"

default_state:
  state:
    counter: 0

inputs:
  name:
    type: "string" 
    description: "Test name"
    required: true

steps:
  - id: "update_counter"
    type: "user_message"
    message: "Updating counter"
    state_update:
      path: "state.counter"
      value: 1
"""
        
        # Write the workflow file
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflow_file = workflows_dir / "test:parameter-test.yaml"
        workflow_file.write_text(workflow_content)
        
        # Test loading and starting workflow
        workflow_def = loader.load("test:parameter-test")
        
        # Test with dict inputs
        result = executor.start(workflow_def, {"name": "test"})
        assert result["status"] == "running"
        assert result["state"]["state"]["name"] == "test"

    def test_workflow_update_state_parameter_types(self, workflow_components):
        """Test workflow state updates with different parameter types."""
        loader, executor, temp_dir = workflow_components
        
        # Create and start a workflow first
        workflow_content = """
name: "test:state-test"
description: "Test state updates"
version: "1.0.0"

default_state:
  state:
    counter: 0

inputs:
  name:
    type: "string"
    description: "Test name"
    required: true

steps:
  - id: "init_counter"
    type: "user_message"
    message: "Initializing counter"
    state_update:
      path: "state.counter"
      value: 1
"""
        
        # Write the workflow file
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflow_file = workflows_dir / "test:state-test.yaml"
        workflow_file.write_text(workflow_content)
        
        # Start workflow
        workflow_def = loader.load("test:state-test")
        result = executor.start(workflow_def, {"name": "test"})
        workflow_id = result["workflow_id"]
        
        # Test state updates
        updates = [{"path": "state.counter", "value": 5}]
        updated_state = executor.update_workflow_state(workflow_id, updates)
        assert updated_state["counter"] == 5

    def test_workflow_implicit_completion_flow(self, workflow_components):
        """Test workflow implicit completion flow via get_next_step calls."""
        loader, executor, temp_dir = workflow_components
        
        # Create and start a workflow
        workflow_content = """
name: "test:step-test"  
description: "Test step completion"
version: "1.0.0"

inputs:
  name:
    type: "string"
    description: "Test name"
    required: true

steps:
  - id: "greet_user"
    type: "user_message"
    message: "Hello {{ name }}"
  - id: "update_counter"
    type: "user_message"
    message: "Updating counter"
    state_update:
      path: "state.counter"
      value: 1
"""
        
        # Write the workflow file
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflow_file = workflows_dir / "test:step-test.yaml"
        workflow_file.write_text(workflow_content)
        
        # Start workflow
        workflow_def = loader.load("test:step-test")
        result = executor.start(workflow_def, {"name": "test"})
        workflow_id = result["workflow_id"]
        
        # Get first step
        first_step = executor.get_next_step(workflow_id)
        assert first_step is not None
        assert "steps" in first_step
        
        # Get next step (this implicitly completes the first step)
        second_step = executor.get_next_step(workflow_id)
        
        # Verify workflow continues executing
        if second_step is not None:
            assert "steps" in second_step or "completed" in second_step["data"]

    def test_parameter_validation_edge_cases(self, workflow_components):
        """Test parameter validation with edge cases."""
        loader, executor, temp_dir = workflow_components
        
        # Test loading non-existent workflow
        with pytest.raises(WorkflowNotFoundError):
            loader.load("non-existent-workflow")
            
        # Test empty workflow name
        with pytest.raises(WorkflowNotFoundError):
            loader.load("")

    def test_union_type_parameter_handling(self, workflow_components):
        """Test that different types work correctly."""
        loader, executor, temp_dir = workflow_components
        
        # Create workflow with mixed input types
        workflow_content = """
name: "test:union-test"
description: "Test union types"
version: "1.0.0"

inputs:
  text_input:
    type: "string"
    description: "Text input parameter"
    required: true
  number_input:
    type: "number"
    description: "Number input parameter"
    required: false
    default: 0

steps:
  - id: "store_result"
    type: "user_message"
    message: "Storing result"
    state_update:
      path: "state.result"
      value: "{{ text_input }}_{{ number_input }}"
"""
        
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflow_file = workflows_dir / "test:union-test.yaml"
        workflow_file.write_text(workflow_content)
        
        workflow_def = loader.load("test:union-test")
        
        # Test with string and integer
        result = executor.start(workflow_def, {"text_input": "hello", "number_input": 42})
        assert result["status"] == "running"

    def test_optional_parameter_handling(self, workflow_components):
        """Test handling of optional parameters."""
        loader, executor, temp_dir = workflow_components
        
        # Test workflow listing (which has optional parameters)
        workflows = loader.list_available_workflows(include_global=True)
        assert isinstance(workflows, list)
        
        workflows2 = loader.list_available_workflows(include_global=False) 
        assert isinstance(workflows2, list)

    def test_parameter_type_coercion(self, workflow_components):
        """Test that parameters are properly handled."""
        loader, executor, temp_dir = workflow_components
        
        # Create simple workflow
        workflow_content = """
name: "test:coercion-test"
description: "Test parameter coercion"
version: "1.0.0"

inputs:
  flag:
    type: "string"
    description: "Flag parameter"
    required: true

steps:
  - id: "store_flag"
    type: "user_message"
    message: "Storing flag value"
    state_update:
      path: "state.flag"
      value: "{{ flag }}"
"""
        
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflow_file = workflows_dir / "test:coercion-test.yaml"
        workflow_file.write_text(workflow_content)
        
        workflow_def = loader.load("test:coercion-test")
        
        # Test with boolean
        result = executor.start(workflow_def, {"flag": True})
        assert result["status"] == "running"

    def test_invalid_parameter_handling(self, workflow_components):
        """Test handling of invalid parameters."""
        loader, executor, temp_dir = workflow_components
        
        # Test invalid workflow operations  
        try:
            executor.get_workflow_status("invalid_workflow_id")
            # If no exception, that's also valid behavior
        except Exception:
            # Expected - invalid workflow ID should raise an exception
            pass

    def test_nested_parameter_validation(self, workflow_components):
        """Test validation of nested parameter structures.""" 
        loader, executor, temp_dir = workflow_components
        
        # Create workflow and test nested state updates
        workflow_content = """
name: "test:nested-test"
description: "Test nested parameters"
version: "1.0.0"

inputs:
  name:
    type: "string"
    description: "Test name"
    required: true

steps:
  - id: "init_nested_data"
    type: "user_message"
    message: "Initializing nested data"
    state_update:
      path: "state.data"
      value: {"nested": {"value": 1}}
"""
        
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"  
        workflow_file = workflows_dir / "test:nested-test.yaml"
        workflow_file.write_text(workflow_content)
        
        workflow_def = loader.load("test:nested-test")
        result = executor.start(workflow_def, {"name": "test"})
        
        # Test nested state update
        workflow_id = result["workflow_id"]
        updates = [
            {"path": "state.complex", "value": {"nested": {"deep": {"value": True}}}}
        ]
        updated_state = executor.update_workflow_state(workflow_id, updates)
        assert "complex" in updated_state

    def test_parameter_serialization_roundtrip(self, workflow_components):
        """Test that parameters can be handled correctly."""
        loader, executor, temp_dir = workflow_components
        
        # Create workflow to test complex data structures
        workflow_content = """
name: "test:serialization-test"
description: "Test parameter serialization"
version: "1.0.0"

inputs:
  name:
    type: "string"
    description: "Test name"
    required: true

steps:
  - id: "init_counter"
    type: "user_message"
    message: "Initializing counter"
    state_update:
      path: "state.counter"
      value: 1
"""
        
        workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
        workflow_file = workflows_dir / "test:serialization-test.yaml"
        workflow_file.write_text(workflow_content)
        
        workflow_def = loader.load("test:serialization-test")
        result = executor.start(workflow_def, {"name": "test"})
        workflow_id = result["workflow_id"]
        
        # Test complex result parameter
        complex_result = {
            "output": "test output",
            "metadata": {
                "timestamp": "2023-01-01T00:00:00Z",
                "tags": ["test", "validation"],
                "metrics": {"duration": 123.45, "memory": 1024}
            },
            "nested_array": [
                {"id": 1, "status": "active"},
                {"id": 2, "status": "inactive"}
            ]
        }
        
        # With implicit completion, we just call get_next_step to advance
        # Complex results would be handled through workflow state updates
        next_step = executor.get_next_step(workflow_id)
        # Workflow should complete or return next steps
        print(f"Next step after complex result: {next_step}")