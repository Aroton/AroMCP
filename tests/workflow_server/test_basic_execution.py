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
            WorkflowStep(id="step3", type="state_update", definition={"path": "raw.counter", "value": 2}),
        ]

        workflow_def = WorkflowDefinition(
            name="test:sequential",
            description="Test sequential execution",
            version="1.0.0",
            default_state={"raw": {"counter": 0}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get first step - state_update steps are now processed internally
        # This will process step1 internally, then return step2 (user_message)
        # and process step3 internally as part of the batch
        next_step = executor.get_next_step(workflow_id)

        # Should get new batched format
        assert "steps" in next_step
        assert "server_completed_steps" in next_step

        # User message should be in steps
        assert len(next_step["steps"]) == 1
        assert next_step["steps"][0]["id"] == "step2"
        assert next_step["steps"][0]["type"] == "user_message"

        # Only step3 should be in server_completed_steps (step1 was processed before batching started)
        assert len(next_step["server_completed_steps"]) == 1
        assert next_step["server_completed_steps"][0]["id"] == "step3"
        assert next_step["server_completed_steps"][0]["type"] == "state_update"

        # Complete the user message step
        executor.step_complete(workflow_id, "step2")

        # Should be done
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
            WorkflowStep(id="step2", type="user_message", definition={"message": "This will fail"}),
        ]

        workflow_def = WorkflowDefinition(
            name="test:failure",
            description="Test failure handling",
            version="1.0.0",
            default_state={"raw": {"counter": 0}},
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
        assert "server_completed_steps" in next_step
        assert len(next_step["steps"]) == 1
        assert next_step["steps"][0]["id"] == "step2"
        assert next_step["steps"][0]["type"] == "user_message"

        # No server_completed_steps in this batch (step1 was processed before batching)
        assert len(next_step["server_completed_steps"]) == 0

        # Mark step2 as failed
        completion_result = executor.step_complete(
            workflow_id, "step2", "failed", error_message="Step execution failed"
        )
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

            # Get first step - state_update is processed internally
            # Should get user_message with variables replaced
            first_step = executor.get_next_step(workflow_id)

            # Should get new batched format
            assert "steps" in first_step
            assert "server_completed_steps" in first_step

            # Should have user message with variables replaced
            assert len(first_step["steps"]) == 1
            assert first_step["steps"][0]["type"] == "user_message"
            message_def = first_step["steps"][0]["definition"]

            # state_update was processed before batching (not included in server_completed_steps)
            assert len(first_step["server_completed_steps"]) == 0

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
            default_state={"raw": {"value": 1}},
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

        with pytest.raises(WorkflowExecutionError) as exc:
            executor.get_next_step("nonexistent_workflow")

        assert "Workflow nonexistent_workflow not found" in str(exc.value)


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
                        {"type": "state_update", "path": "raw.processed", "value": True},
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
            default_state={"raw": {"value": 5, "processed": False}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # First step should be the conditional step, which should process internally
        # Since there's no initial user_message, it returns single steps from the conditional
        next_step = executor.get_next_step(workflow_id)

        # Should be the first user message from else_steps (not batched)
        assert "step" in next_step
        assert next_step["step"]["type"] == "user_message"
        assert "Value is 10 or less" in next_step["step"]["definition"]["message"]
        executor.step_complete(workflow_id, next_step["step"]["id"], "success")

        # Next step - now we should get batching since we're continuing from a user_message
        next_step = executor.get_next_step(workflow_id)

        # Should get batched format now
        assert "steps" in next_step
        assert "server_completed_steps" in next_step

        # Should have remaining user messages
        user_messages = [s for s in next_step["steps"] if s["type"] == "user_message"]
        assert len(user_messages) >= 1  # At least "Processing complete" and maybe "Final step"

        # Check for the expected message
        messages = [msg["definition"]["message"] for msg in user_messages]
        assert any("Processing complete" in msg for msg in messages)

        # The state_update was already processed when we were in the conditional branch
        # It won't be in server_completed_steps because it was processed before this batch
        # But we can verify the state was updated
        current_state = executor.state_manager.read(workflow_id)
        assert (
            current_state.get("processed") is True
        ), f"State update from conditional was not applied. State: {current_state}"

        # Complete the last step to finish workflow
        last_step_id = next_step["steps"][-1]["id"]
        executor.step_complete(workflow_id, last_step_id, "success")

        # Verify that the state was actually updated by the conditional else_steps
        current_state = executor.state_manager.read(workflow_id)
        assert current_state.get("processed") is True, f"State was not updated. Current state: {current_state}"

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
                            "state_update": {"path": "raw.changed_files", "value": "stdout"},
                        },
                    ],
                },
            ),
            WorkflowStep(
                id="process_files", type="user_message", definition={"message": "Processing files: {{ changed_files }}"}
            ),
        ]

        workflow_def = WorkflowDefinition(
            name="test:shell_conditional",
            description="Test shell command in conditional else_steps",
            version="1.0.0",
            default_state={"raw": {"commit": "", "changed_files": ""}},
            state_schema=StateSchema(),
            inputs={},
            steps=steps,
        )

        # Start workflow
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get the first step - should execute conditional and return user message
        first_step = executor.get_next_step(workflow_id)

        # The conditional should be processed internally and we should get the user message
        if first_step.get("batch"):
            assert len(first_step["user_messages"]) >= 1
            assert "Getting changed files..." in first_step["user_messages"][0]["definition"]["message"]
            # Complete all user messages
            for msg in first_step["user_messages"]:
                executor.step_complete(workflow_id, msg["id"], "success")
        else:
            assert first_step["step"]["type"] == "user_message"
            assert "Getting changed files..." in first_step["step"]["definition"]["message"]
            # Complete the user message step
            executor.step_complete(workflow_id, first_step["step"]["id"], "success")

        # Now get the next step - the shell command should have been processed internally
        second_step = executor.get_next_step(workflow_id)

        # Check that the state was updated by the shell command
        current_state = executor.state_manager.read(workflow_id)

        # If this test fails, it means the shell command was not executed
        # and the bug is still present
        assert (
            current_state.get("changed_files") == "file1.py\nfile2.py"
        ), f"Shell command was not executed. State: {current_state}"

        # The second step should be the final processing step with variables replaced
        if second_step:
            if second_step.get("batch"):
                # Verify that variable replacement worked in subsequent steps
                assert len(second_step["user_messages"]) >= 1
                message = second_step["user_messages"][0]["definition"]["message"]
                assert "file1.py" in message, f"Variables not replaced properly: {message}"
