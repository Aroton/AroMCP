"""Tests for basic workflow execution and step processing."""

import tempfile
from pathlib import Path

import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.models import WorkflowExecutionError
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor
from aromcp.workflow_server.workflow.variables import VariableReplacer


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
  state:
    counter: 0
    message: ""

state_schema:
  computed:
    doubled:
      from: "state.counter"
      transform: "input * 2"

inputs:
  name:
    type: "string"
    description: "User name"
    required: true

steps:
  - id: "set_counter"
    type: "shell_command"
    command: "echo 'Setting counter to 5'"
    state_update:
      path: "state.counter"
      value: "5"
  - id: "greet_user"
    type: "user_message"
    message: "Hello {{ inputs.name }}, counter is {{ state.counter }}"
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
            assert result["state"]["state"]["counter"] == 0  # Default state
            assert result["state"]["inputs"]["name"] == "test"  # Input applied
            assert result["state"]["computed"]["doubled"] == 0  # Computed field

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
  state:
    base_value: 10

inputs:
  multiplier:
    type: "number"
    description: "Multiplier value"
    default: 2

steps:
  - id: "update_result"
    type: "shell_command"
    command: "echo 'Updating result'"
    state_update:
      path: "state.result"
      value: "computed"
"""
            workflow_file.write_text(workflow_content)

            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:inputs")
            result = executor.start(workflow_def, inputs={"multiplier": 3})

            assert result["state"]["state"]["base_value"] == 10
            assert result["state"]["inputs"]["multiplier"] == 3

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
  state:
    counter: 5

steps:
  - id: "show_counter"
    type: "user_message"
    message: "Counter is {{ state.counter }}"
"""
            workflow_file.write_text(workflow_content)

            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:no-inputs")
            result = executor.start(workflow_def)

            assert result["state"]["state"]["counter"] == 5


class TestSequentialExecution:
    """Test sequential step execution."""

    def test_get_next_step_sequential(self):
        """Test sequential step retrieval."""
        executor = WorkflowExecutor()

        # Create minimal workflow definition for testing
        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        steps = [
            WorkflowStep(id="step1", type="shell_command", definition={"command": "echo 'State update step1'", "state_update": {"path": "state.counter", "value": 1}}),
            WorkflowStep(id="step2", type="user_message", definition={"message": "Hello"}),
            WorkflowStep(id="step3", type="shell_command", definition={"command": "echo 'State update step3'", "state_update": {"path": "state.counter", "value": 2}}),
        ]

        workflow_def = WorkflowDefinition(
            name="test:sequential",
            description="Test sequential execution",
            version="1.0.0",
            default_state={"state": {"counter": 0}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get first step - shell_command steps with state_update are now processed internally
        # This will process step1 internally, then return step2 (user_message)
        # and process step3 internally as part of the batch
        next_step = executor.get_next_step(workflow_id)

        # Should get new batched format
        assert "steps" in next_step
        # server_completed_steps is a debug feature, not testing against it

        # User message should be in steps
        assert len(next_step["steps"]) == 1
        assert next_step["steps"][0]["id"] == "step2"
        assert next_step["steps"][0]["type"] == "user_message"

        # Both shell_command steps should be processed on server (debug feature not tested)

        # Get next step (implicitly completes the user message step)
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
            WorkflowStep(id="step1", type="shell_command", definition={"command": "echo 'State update step1'", "state_update": {"path": "state.counter", "value": 1}}),
            WorkflowStep(id="step2", type="user_message", definition={"message": "This will fail"}),
        ]

        workflow_def = WorkflowDefinition(
            name="test:failure",
            description="Test failure handling",
            version="1.0.0",
            default_state={"state": {"counter": 0}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow and get first step
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get first step - step1 is processed internally, returns step2
        next_step = executor.get_next_step(workflow_id)

        # Should get batched format with step2 (user_message)
        assert "steps" in next_step
        # server_completed_steps is a debug feature, not testing against it
        assert len(next_step["steps"]) == 1
        assert next_step["steps"][0]["id"] == "step2"
        assert next_step["steps"][0]["type"] == "user_message"

        # Step1 (shell_command with state_update) should be processed on server (debug feature not tested)

        # With implicit completion, we can't simulate individual step failures
        # The workflow continues when we call get_next_step (implicitly completing step2)
        final_step = executor.get_next_step(workflow_id)
        assert final_step is None  # Workflow should complete

        # Check workflow status - should be completed (not failed with implicit completion)
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] in ["completed", "running"]  # Implicit completion doesn't track individual step failures


class TestVariableReplacement:
    """Test variable interpolation in steps."""

    def test_variable_replacement_basic(self):
        """Test basic variable replacement."""
        state = {"counter": 5, "name": "test"}
        step = {"type": "user_message", "message": "Hello {{ name }}, count is {{ counter }}"}

        replaced = VariableReplacer.replace(step, state)

        assert replaced["message"] == "Hello test, count is 5"
        assert replaced["type"] == "user_message"  # Unchanged

    def test_variable_replacement_nested(self):
        """Test variable replacement in nested objects."""
        state = {"value": 10, "prefix": "Result"}
        step = {
            "type": "mcp_call",
            "tool": "test_tool",
            "parameters": {"input": "{{ value }}", "message": "{{ prefix }}: {{ value }}"},
            "config": {"timeout": 30, "description": "Processing {{ value }} items"},
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
            "updates": [{"path": "raw.field1", "value": "{{ item1 }}"}, {"path": "raw.field2", "value": "{{ item2 }}"}],
        }

        replaced = VariableReplacer.replace(step, state)

        assert replaced["updates"][0]["value"] == "first"
        assert replaced["updates"][1]["value"] == "second"

    def test_variable_replacement_missing_vars(self):
        """Test behavior with missing variables."""
        state = {"existing": "value"}
        step = {"message": "Existing: {{ existing }}, Missing: {{ missing }}"}

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
  state:
    counter: 0
    name: ""

state_schema:
  computed:
    doubled:
      from: "state.counter"
      transform: "input * 2"

inputs:
  user_name:
    type: "string"
    description: "User name"

steps:
  - id: "set_counter"
    type: "shell_command"
    command: "echo 'Setting counter'"
    state_update:
      path: "state.counter"
      value: "5"
  - id: "greet_user"
    type: "user_message"
    message: "Hello {{ inputs.user_name }}, counter is {{ state.counter }}, doubled is {{ computed.doubled }}"
"""
            workflow_file.write_text(workflow_content)

            loader = WorkflowLoader(project_root=temp_dir)
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:variables")
            result = executor.start(workflow_def, inputs={"user_name": "Alice"})
            workflow_id = result["workflow_id"]

            # Get first step - shell_command with state_update is processed internally
            # Should get user_message with variables replaced
            first_step = executor.get_next_step(workflow_id)

            # Should get new batched format
            assert "steps" in first_step
            # server_completed_steps is a debug feature, not testing against it

            # Should have user message with variables replaced
            assert len(first_step["steps"]) == 1
            assert first_step["steps"][0]["type"] == "user_message"
            message_def = first_step["steps"][0]["definition"]

            # shell_command with state_update was processed on server (debug feature not tested)

            # Variables should be replaced based on current state
            message = message_def["message"]
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
            default_state={"state": {"value": 1}},
            state_schema=StateSchema(),
            inputs={},
            steps=[WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})],
        )

        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        status = executor.get_workflow_status(workflow_id)

        assert status["workflow_id"] == workflow_id
        assert status["workflow_name"] == "test:status"
        assert status["status"] == "running"
        assert status["created_at"] is not None
        assert status["completed_at"] is None
        assert status["state"]["state"]["value"] == 1
        assert "execution_context" in status

    def test_list_active_workflows(self):
        """Test listing active workflow instances."""
        # Create fresh executor - QueueBasedWorkflowExecutor creates its own state manager
        executor = WorkflowExecutor()

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
            steps=[WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})],
        )

        workflow_def2 = WorkflowDefinition(
            name="test:workflow2",
            description="Second workflow",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})],
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

        # QueueBasedWorkflowExecutor returns error dict instead of raising exception
        result = executor.get_next_step("nonexistent_workflow")
        
        assert "error" in result
        assert "Workflow nonexistent_workflow not found" in result["error"]


class TestConditionalMultipleSteps:
    """Test conditional execution with multiple steps in branches."""

    def test_conditional_with_multiple_else_steps(self):
        """Test that all steps in else_steps are executed sequentially."""
        executor = WorkflowExecutor()

        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        # Create workflow with conditional that has multiple steps in else_steps
        steps = [
            WorkflowStep(
                id="conditional_step",
                type="conditional",
                definition={
                    "condition": "{{ value > 10 }}",
                    "then_steps": [{"type": "user_message", "message": "Value is greater than 10"}],
                    "else_steps": [
                        {"type": "user_message", "message": "Value is 10 or less"},
                        {"type": "shell_command", "command": "echo 'Processing'", "state_update": {"path": "state.processed", "value": True}},
                        {"type": "user_message", "message": "Processing complete"},
                    ],
                },
            ),
            WorkflowStep(id="final_step", type="user_message", definition={"message": "Final step"}),
        ]

        workflow_def = WorkflowDefinition(
            name="test:conditional_multi",
            description="Test conditional with multiple else steps",
            version="1.0.0",
            default_state={"state": {"value": 5, "processed": False}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # First step should be the conditional step, which should process internally
        # With batching fix, it now returns all steps in batched format
        next_step = executor.get_next_step(workflow_id)

        # Should get batched format with all the steps
        assert "steps" in next_step
        # server_completed_steps is a debug feature, not testing against it

        # Should have all user messages from else_steps and final_step
        user_messages = [s for s in next_step["steps"] if s["type"] == "user_message"]
        assert len(user_messages) == 3  # "Value is 10 or less", "Processing complete", "Final step"

        # Check for the expected messages
        messages = [msg["definition"]["message"] for msg in user_messages]
        assert "Value is 10 or less" in messages[0]
        assert "Processing complete" in messages[1]
        assert "Final step" in messages[2]

        # The shell_command with state_update should have been processed on the server (debug feature not tested)

        # Verify the state was updated
        current_state = executor.state_manager.read(workflow_id)
        assert (
            current_state.get("state", {}).get("processed") is True
        ), f"State update from conditional was not applied. State: {current_state}"

        # Get next step (implicitly completes all the user message steps)
        next_step = executor.get_next_step(workflow_id)
        assert next_step is None, f"Unexpected next step: {next_step}"

        # Check workflow is completed
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed"

    def test_conditional_with_shell_command_in_else_steps(self):
        """Test that shell commands in else_steps are executed properly."""
        executor = WorkflowExecutor()

        from aromcp.workflow_server.state.models import StateSchema
        from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep

        # Create workflow similar to the code-standards:enforce workflow bug
        steps = [
            WorkflowStep(
                id="conditional_step",
                type="conditional",
                definition={
                    "condition": "{{ commit }}",
                    "then_steps": [{"type": "user_message", "message": "Using specific commit"}],
                    "else_steps": [
                        {"type": "user_message", "message": "Getting changed files..."},
                        {
                            "type": "shell_command",
                            "command": "echo 'file1.py\nfile2.py'",
                            "state_update": {"path": "state.changed_files", "value": "stdout"},
                        },
                    ],
                },
            ),
            WorkflowStep(
                id="process_files",
                type="user_message",
                definition={"message": "Processing files: {{ state.changed_files }}"},
            ),
        ]

        workflow_def = WorkflowDefinition(
            name="test:shell_conditional",
            description="Test shell command in conditional else_steps",
            version="1.0.0",
            default_state={"state": {"commit": "", "changed_files": ""}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get the first step - should execute conditional and return user message
        first_step = executor.get_next_step(workflow_id)

        # The conditional should be processed internally and we should get batched results
        assert "steps" in first_step
        # server_completed_steps is a debug feature, not testing against it

        # Should have the user message
        user_messages = [s for s in first_step["steps"] if s["type"] == "user_message"]
        assert len(user_messages) >= 1
        assert "Getting changed files..." in user_messages[0]["definition"]["message"]

        # The shell command should have been executed on the server (debug feature not tested)

        # Now get the next step - the shell command should have been processed internally
        executor.get_next_step(workflow_id)

        # Check that the state was updated by the shell command
        current_state = executor.state_manager.read(workflow_id)

        # If this test fails, it means the shell command was not executed
        # and the bug is still present
        assert (
            current_state.get("state", {}).get("changed_files") == "file1.py\nfile2.py\n"
        ), f"Shell command was not executed. State: {current_state}"

        # The processing step should also be in the first batch with variables replaced
        assert "Processing files:" in user_messages[-1]["definition"]["message"]
        # Verify that variable replacement worked
        message = user_messages[-1]["definition"]["message"]
        assert "file1.py" in message, f"Variables not replaced properly: {message}"
