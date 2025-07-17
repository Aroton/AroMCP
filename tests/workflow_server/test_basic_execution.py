"""Tests for basic workflow execution and step processing."""

import tempfile
from pathlib import Path

import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.executor import VariableReplacer, WorkflowExecutor
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.models import WorkflowExecutionError


class TestWorkflowStart:
    """Test workflow initialization and startup."""

    def test_workflow_start_basic(self):
        """Test basic workflow initialization."""
        # Create a simple workflow
        with tempfile.TemporaryDirectory() as temp_dir:
            workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
            workflows_dir.mkdir(parents=True)

            workflow_file = workflows_dir / "test:simple.yaml"
            workflow_content = """
name: "test:simple"
description: "Simple test workflow"
version: "1.0.0"

default_state:
  raw:
    counter: 0
    message: ""

state_schema:
  computed:
    doubled:
      from: "raw.counter"
      transform: "input * 2"

inputs:
  name:
    type: "string"
    description: "User name"
    required: true

steps:
  - type: "state_update"
    path: "raw.counter"
    value: 5
  - type: "user_message"
    message: "Hello {{ name }}, counter is {{ counter }}"
"""
            workflow_file.write_text(workflow_content)

            # Load and start workflow
            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:simple")
            result = executor.start(workflow_def, inputs={"name": "test"})

            # Verify startup
            assert result["workflow_id"].startswith("wf_")
            assert result["status"] == "running"
            assert result["total_steps"] == 2
            assert result["state"]["counter"] == 0  # Default state
            assert result["state"]["name"] == "test"  # Input applied
            assert result["state"]["doubled"] == 0  # Computed field

    def test_workflow_start_with_inputs(self):
        """Test workflow initialization with input values."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
            workflows_dir.mkdir(parents=True)

            workflow_file = workflows_dir / "test:inputs.yaml"
            workflow_content = """
name: "test:inputs"
description: "Test with inputs"
version: "1.0.0"

default_state:
  raw:
    base_value: 10

inputs:
  multiplier:
    type: "number"
    description: "Multiplier value"
    default: 2

steps:
  - type: "state_update"
    path: "raw.result"
    value: "computed"
"""
            workflow_file.write_text(workflow_content)

            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:inputs")
            result = executor.start(workflow_def, inputs={"multiplier": 3})

            assert result["state"]["base_value"] == 10
            assert result["state"]["multiplier"] == 3

    def test_workflow_start_without_inputs(self):
        """Test workflow startup without providing inputs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
            workflows_dir.mkdir(parents=True)

            workflow_file = workflows_dir / "test:no-inputs.yaml"
            workflow_content = """
name: "test:no-inputs"
description: "Test without inputs"
version: "1.0.0"

default_state:
  raw:
    counter: 5

steps:
  - type: "user_message"
    message: "Counter is {{ counter }}"
"""
            workflow_file.write_text(workflow_content)

            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:no-inputs")
            result = executor.start(workflow_def)

            assert result["state"]["counter"] == 5


class TestSequentialExecution:
    """Test sequential step execution."""

    def test_get_next_step_sequential(self):
        """Test sequential step retrieval."""
        executor = WorkflowExecutor()

        # Create minimal workflow definition for testing
        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        steps = [
            WorkflowStep(id="step1", type="state_update", definition={"path": "raw.counter", "value": 1}),
            WorkflowStep(id="step2", type="user_message", definition={"message": "Hello"}),
            WorkflowStep(id="step3", type="state_update", definition={"path": "raw.counter", "value": 2})
        ]

        workflow_def = WorkflowDefinition(
            name="test:sequential",
            description="Test sequential execution",
            version="1.0.0",
            default_state={"raw": {"counter": 0}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get first step
        next_step = executor.get_next_step(workflow_id)
        assert next_step["step"]["id"] == "step1"
        assert next_step["step"]["type"] == "state_update"
        assert "execution_context" in next_step

        # Complete first step and get second
        executor.step_complete(workflow_id, "step1")
        next_step = executor.get_next_step(workflow_id)
        assert next_step["step"]["id"] == "step2"

        # Complete second step and get third
        executor.step_complete(workflow_id, "step2")
        next_step = executor.get_next_step(workflow_id)
        assert next_step["step"]["id"] == "step3"

        # Complete third step - should be done
        executor.step_complete(workflow_id, "step3")
        next_step = executor.get_next_step(workflow_id)
        assert next_step is None

        # Check workflow is complete
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed"

    def test_step_completion_with_failure(self):
        """Test step completion with failure status."""
        executor = WorkflowExecutor()

        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        steps = [
            WorkflowStep(id="step1", type="state_update", definition={"path": "raw.counter", "value": 1}),
            WorkflowStep(id="step2", type="user_message", definition={"message": "This will fail"})
        ]

        workflow_def = WorkflowDefinition(
            name="test:failure",
            description="Test failure handling",
            version="1.0.0",
            default_state={"raw": {"counter": 0}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps
        )

        # Start workflow and get first step
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        next_step = executor.get_next_step(workflow_id)
        assert next_step["step"]["id"] == "step1"

        # Complete first step successfully
        completion_result = executor.step_complete(workflow_id, "step1", "success")
        assert completion_result["status"] == "running"

        # Get second step
        next_step = executor.get_next_step(workflow_id)
        assert next_step["step"]["id"] == "step2"

        # Fail second step
        completion_result = executor.step_complete(workflow_id, "step2", "failed",
                                                 error_message="Step execution failed")
        assert completion_result["status"] == "failed"
        assert completion_result["error"] == "Step execution failed"

        # Should not be able to get next step
        next_step = executor.get_next_step(workflow_id)
        assert next_step is None

        # Check workflow status
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "failed"
        assert status["error_message"] == "Step execution failed"


class TestVariableReplacement:
    """Test variable interpolation in steps."""

    def test_variable_replacement_basic(self):
        """Test basic variable replacement."""
        state = {"counter": 5, "name": "test"}
        step = {
            "type": "user_message",
            "message": "Hello {{ name }}, count is {{ counter }}"
        }

        replaced = VariableReplacer.replace(step, state)

        assert replaced["message"] == "Hello test, count is 5"
        assert replaced["type"] == "user_message"  # Unchanged

    def test_variable_replacement_nested(self):
        """Test variable replacement in nested objects."""
        state = {"value": 10, "prefix": "Result"}
        step = {
            "type": "mcp_call",
            "tool": "test_tool",
            "parameters": {
                "input": "{{ value }}",
                "message": "{{ prefix }}: {{ value }}"
            },
            "config": {
                "timeout": 30,
                "description": "Processing {{ value }} items"
            }
        }

        replaced = VariableReplacer.replace(step, state)

        assert replaced["parameters"]["input"] == "10"
        assert replaced["parameters"]["message"] == "Result: 10"
        assert replaced["config"]["description"] == "Processing 10 items"
        assert replaced["config"]["timeout"] == 30  # Unchanged

    def test_variable_replacement_arrays(self):
        """Test variable replacement in arrays."""
        state = {"item1": "first", "item2": "second"}
        step = {
            "type": "batch_update",
            "updates": [
                {"path": "raw.field1", "value": "{{ item1 }}"},
                {"path": "raw.field2", "value": "{{ item2 }}"}
            ]
        }

        replaced = VariableReplacer.replace(step, state)

        assert replaced["updates"][0]["value"] == "first"
        assert replaced["updates"][1]["value"] == "second"

    def test_variable_replacement_missing_vars(self):
        """Test behavior with missing variables."""
        state = {"existing": "value"}
        step = {
            "message": "Existing: {{ existing }}, Missing: {{ missing }}"
        }

        replaced = VariableReplacer.replace(step, state)

        # Missing variables should be left as-is
        assert replaced["message"] == "Existing: value, Missing: {{ missing }}"

    def test_variable_replacement_integration(self):
        """Test variable replacement integration with workflow execution."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workflows_dir = Path(temp_dir) / ".aromcp" / "workflows"
            workflows_dir.mkdir(parents=True)

            workflow_file = workflows_dir / "test:variables.yaml"
            workflow_content = """
name: "test:variables"
description: "Test variable replacement"
version: "1.0.0"

default_state:
  raw:
    counter: 0
    name: ""

state_schema:
  computed:
    doubled:
      from: "raw.counter"
      transform: "input * 2"

inputs:
  user_name:
    type: "string"
    description: "User name"

steps:
  - type: "state_update"
    path: "raw.counter"
    value: 5
  - type: "user_message"
    message: "Hello {{ user_name }}, counter is {{ counter }}, doubled is {{ doubled }}"
"""
            workflow_file.write_text(workflow_content)

            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:variables")
            result = executor.start(workflow_def, inputs={"user_name": "Alice"})
            workflow_id = result["workflow_id"]

            # Complete first step (state update)
            first_step = executor.get_next_step(workflow_id)
            assert first_step["step"]["type"] == "state_update"

            # Manually process the state update step for this test
            step_def = first_step["step"]["definition"]
            if step_def.get("path") == "raw.counter" and step_def.get("value") == 5:
                # Apply the state update
                executor.update_workflow_state(workflow_id, [{"path": "raw.counter", "value": 5}])

            executor.step_complete(workflow_id, first_step["step"]["id"])

            # Get second step - should have variables replaced
            second_step = executor.get_next_step(workflow_id)
            assert second_step["step"]["type"] == "user_message"

            # Variables should be replaced based on current state
            message = second_step["step"]["definition"]["message"]
            assert "Alice" in message
            assert "5" in message  # counter value
            assert "10" in message  # doubled value


class TestWorkflowStatusAndManagement:
    """Test workflow status tracking and management."""

    def test_get_workflow_status(self):
        """Test workflow status retrieval."""
        executor = WorkflowExecutor()

        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        workflow_def = WorkflowDefinition(
            name="test:status",
            description="Test status tracking",
            version="1.0.0",
            default_state={"raw": {"value": 1}},
            state_schema=StateSchema(),
            inputs={},
            steps=[WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})]
        )

        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        status = executor.get_workflow_status(workflow_id)

        assert status["workflow_id"] == workflow_id
        assert status["workflow_name"] == "test:status"
        assert status["status"] == "running"
        assert status["created_at"] is not None
        assert status["completed_at"] is None
        assert status["state"]["value"] == 1
        assert "execution_context" in status

    def test_list_active_workflows(self):
        """Test listing active workflow instances."""
        # Create fresh executor with its own state manager
        executor = WorkflowExecutor(StateManager())

        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        # Start multiple workflows
        workflow_def1 = WorkflowDefinition(
            name="test:workflow1",
            description="First workflow",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})]
        )

        workflow_def2 = WorkflowDefinition(
            name="test:workflow2",
            description="Second workflow",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})]
        )

        result1 = executor.start(workflow_def1)
        result2 = executor.start(workflow_def2)

        active_workflows = executor.list_active_workflows()

        assert len(active_workflows) == 2

        workflow_ids = [w["workflow_id"] for w in active_workflows]
        assert result1["workflow_id"] in workflow_ids
        assert result2["workflow_id"] in workflow_ids

        # Find first workflow
        wf1 = next(w for w in active_workflows if w["workflow_id"] == result1["workflow_id"])
        assert wf1["workflow_name"] == "test:workflow1"
        assert wf1["status"] == "running"

    def test_workflow_not_found_error(self):
        """Test error handling for non-existent workflows."""
        executor = WorkflowExecutor()

        with pytest.raises(WorkflowExecutionError) as exc:
            executor.get_next_step("nonexistent_workflow")

        assert "Workflow nonexistent_workflow not found" in str(exc.value)
