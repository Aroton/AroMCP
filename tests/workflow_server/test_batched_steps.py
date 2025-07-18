"""Test batched step execution in workflow executor."""

from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.executor import WorkflowExecutor
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep


class TestBatchedStepExecution:
    """Test cases for batched user message and step execution."""

    def test_consecutive_user_messages_batched(self):
        """Test that consecutive user messages are batched with next actionable step."""
        # Create workflow with consecutive user messages
        workflow_def = WorkflowDefinition(
            name="test_batched",
            description="Test batched execution",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(id="msg1", type="user_message", definition={"message": "First message"}),
                WorkflowStep(id="msg2", type="user_message", definition={"message": "Second message"}),
                WorkflowStep(id="msg3", type="user_message", definition={"message": "Third message"}),
                WorkflowStep(id="action1", type="mcp_call", definition={"tool": "test_tool", "parameters": {}}),
            ],
        )

        # Create executor and start workflow
        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get next step - should return batch
        next_step = executor.get_next_step(workflow_id)

        # Verify response format
        assert next_step is not None
        assert "steps" in next_step
        assert "server_completed_steps" in next_step

        # Verify all user messages and actionable step are included
        steps = next_step["steps"]
        assert len(steps) == 4  # 3 user messages + 1 actionable step
        assert steps[0]["id"] == "msg1"
        assert steps[0]["type"] == "user_message"
        assert steps[1]["id"] == "msg2"
        assert steps[1]["type"] == "user_message"
        assert steps[2]["id"] == "msg3"
        assert steps[2]["type"] == "user_message"
        assert steps[3]["id"] == "action1"
        assert steps[3]["type"] == "mcp_call"

        # Should have no server completed steps (only user messages and mcp_call)
        assert len(next_step["server_completed_steps"]) == 0

    def test_single_user_message_with_action(self):
        """Test single user message batched with internal action."""
        workflow_def = WorkflowDefinition(
            name="test_single_batch",
            description="Test single message batch",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(id="msg1", type="user_message", definition={"message": "Status update"}),
                WorkflowStep(
                    id="action1", type="state_update", definition={"path": "raw.status", "value": "processing"}
                ),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        next_step = executor.get_next_step(workflow_id)

        # Should have steps array and server_completed_steps array
        assert "steps" in next_step
        assert "server_completed_steps" in next_step

        # Should have user message in steps
        assert len(next_step["steps"]) == 1
        assert next_step["steps"][0]["id"] == "msg1"
        assert next_step["steps"][0]["type"] == "user_message"

        # Should have state_update in server_completed_steps
        assert len(next_step["server_completed_steps"]) == 1
        assert next_step["server_completed_steps"][0]["id"] == "action1"
        assert next_step["server_completed_steps"][0]["type"] == "state_update"

    def test_user_messages_at_workflow_end(self):
        """Test user messages at the end of workflow."""
        workflow_def = WorkflowDefinition(
            name="test_end_messages",
            description="Test messages at end",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(
                    id="action1",
                    type="mcp_call",  # Use mcp_call as first actionable step
                    definition={"tool": "test_tool", "parameters": {}},
                ),
                WorkflowStep(id="msg1", type="user_message", definition={"message": "Workflow complete"}),
                WorkflowStep(id="msg2", type="user_message", definition={"message": "Thank you!"}),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get first step - should be a single actionable step (not batched)
        first_step = executor.get_next_step(workflow_id)
        assert "step" in first_step  # Single step format
        assert first_step["step"]["id"] == "action1"
        assert first_step["step"]["type"] == "mcp_call"

        # Complete first step
        executor.step_complete(workflow_id, "action1", "success")

        # Get next step - should be batched user messages
        next_step = executor.get_next_step(workflow_id)
        assert "steps" in next_step
        assert "server_completed_steps" in next_step
        assert len(next_step["steps"]) == 2  # Both user messages
        assert len(next_step["server_completed_steps"]) == 0  # No server steps
        assert next_step["steps"][0]["id"] == "msg1"
        assert next_step["steps"][1]["id"] == "msg2"

        # Complete the batch
        executor.step_complete(workflow_id, "msg2", "success")

        # Workflow should be complete
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed"

    def test_non_consecutive_messages_not_batched(self):
        """Test that messages separated by actionable steps create separate batches."""
        workflow_def = WorkflowDefinition(
            name="test_non_consecutive",
            description="Test non-consecutive messages",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(id="msg1", type="user_message", definition={"message": "First message"}),
                WorkflowStep(
                    id="action1",
                    type="mcp_call",  # Use actionable step to separate batches
                    definition={"tool": "test_tool", "parameters": {}},
                ),
                WorkflowStep(id="msg2", type="user_message", definition={"message": "Second message"}),
                WorkflowStep(
                    id="action2",
                    type="mcp_call",  # Use actionable step to separate batches
                    definition={"tool": "test_tool2", "parameters": {}},
                ),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # First batch: starts with user_message, so it triggers batching
        first_batch = executor.get_next_step(workflow_id)
        assert "steps" in first_batch
        assert "server_completed_steps" in first_batch
        assert len(first_batch["steps"]) == 2  # msg1 + action1
        assert len(first_batch["server_completed_steps"]) == 0  # No server steps
        assert first_batch["steps"][0]["id"] == "msg1"
        assert first_batch["steps"][0]["type"] == "user_message"
        assert first_batch["steps"][1]["id"] == "action1"
        assert first_batch["steps"][1]["type"] == "mcp_call"

        # Complete first action
        executor.step_complete(workflow_id, "action1", "success")

        # Second batch: starts with user_message, so it triggers batching
        second_batch = executor.get_next_step(workflow_id)
        assert "steps" in second_batch
        assert "server_completed_steps" in second_batch
        assert len(second_batch["steps"]) == 2  # msg2 + action2
        assert len(second_batch["server_completed_steps"]) == 0  # No server steps
        assert second_batch["steps"][0]["id"] == "msg2"
        assert second_batch["steps"][0]["type"] == "user_message"
        assert second_batch["steps"][1]["id"] == "action2"
        assert second_batch["steps"][1]["type"] == "mcp_call"

    def test_control_flow_with_batched_messages(self):
        """Test batched messages work correctly with control flow."""
        workflow_def = WorkflowDefinition(
            name="test_control_flow_batch",
            description="Test control flow with batching",
            version="1.0.0",
            default_state={"raw": {"condition": True}},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(
                    id="cond1",
                    type="conditional",
                    definition={
                        "condition": "{{ raw.condition }}",
                        "then_steps": [
                            {"id": "then_msg1", "type": "user_message", "definition": {"message": "Condition true"}},
                            {
                                "id": "then_msg2",
                                "type": "user_message",
                                "definition": {"message": "Executing then branch"},
                            },
                            {
                                "id": "then_action",
                                "type": "state_update",
                                "definition": {"path": "raw.result", "value": "then"},
                            },
                        ],
                        "else_steps": [
                            {"id": "else_msg", "type": "user_message", "definition": {"message": "Condition false"}},
                            {
                                "id": "else_action",
                                "type": "state_update",
                                "definition": {"path": "raw.result", "value": "else"},
                            },
                        ],
                    },
                ),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Get next step - conditional is processed internally and returns first step from branch
        next_step = executor.get_next_step(workflow_id)

        # The conditional evaluates to false (raw.condition is True but state is empty)
        # So we get the first step from else branch, which should be batched with the action
        assert next_step is not None

        # Check if it's a batched response or a single step
        if next_step.get("batch"):
            # Batched user messages
            assert len(next_step["user_messages"]) >= 1
        else:
            # Single step - should be a user_message from the conditional branch
            assert next_step["step"]["type"] == "user_message"

    def test_shell_command_not_batched(self):
        """Test that shell commands are processed internally with correct batching behavior."""
        workflow_def = WorkflowDefinition(
            name="test_shell_batch",
            description="Test shell command batching",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(id="msg1", type="user_message", definition={"message": "Running command..."}),
                WorkflowStep(id="cmd1", type="shell_command", definition={"command": "echo 'test'"}),
                WorkflowStep(id="msg2", type="user_message", definition={"message": "Command complete"}),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # First call should process msg1 and cmd1 internally, return ALL steps
        next_step = executor.get_next_step(workflow_id)

        assert next_step is not None
        assert "steps" in next_step, "Should have steps array"
        assert "server_completed_steps" in next_step, "Should have server_completed_steps array"

        # Should have both user messages in steps
        assert len(next_step["steps"]) == 2, "Should have both user messages"
        assert next_step["steps"][0]["id"] == "msg1", "Should have the initial message"
        assert next_step["steps"][0]["type"] == "user_message"
        assert next_step["steps"][0]["definition"]["message"] == "Running command..."
        assert next_step["steps"][1]["id"] == "msg2", "Should have the final message"
        assert next_step["steps"][1]["type"] == "user_message"
        assert next_step["steps"][1]["definition"]["message"] == "Command complete"

        # Should have shell command in server_completed_steps
        assert len(next_step["server_completed_steps"]) == 1, "Should have one server-completed step"
        assert next_step["server_completed_steps"][0]["id"] == "cmd1"
        assert next_step["server_completed_steps"][0]["type"] == "shell_command"
        assert next_step["server_completed_steps"][0]["result"]["status"] == "success"

        # Complete the batch by acknowledging the user message
        executor.step_complete(workflow_id, "msg2", "success")

        # Second call should return None (workflow complete)
        final_step = executor.get_next_step(workflow_id)
        assert final_step is None, "Workflow should be complete"

        # Verify workflow status
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed", "Workflow should be marked as completed"

    def test_shell_command_with_state_update_and_project_directory(self):
        """Test shell command execution with state updates using correct project directory."""
        workflow_def = WorkflowDefinition(
            name="test_shell_state",
            description="Test shell command with state updates",
            version="1.0.0",
            default_state={"raw": {"output": ""}},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(
                    id="prepare_msg", type="user_message", definition={"message": "Preparing to run command..."}
                ),
                WorkflowStep(
                    id="test_cmd",
                    type="shell_command",
                    definition={
                        "command": "pwd && echo 'Hello from workflow'",
                        "state_update": {"path": "raw.output", "value": "stdout"},
                    },
                ),
                WorkflowStep(
                    id="result_msg", type="user_message", definition={"message": "Command output: {{ raw.output }}"}
                ),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # First call should process prepare_msg and test_cmd internally, return result_msg
        next_step = executor.get_next_step(workflow_id)

        assert next_step is not None
        assert "steps" in next_step, "Should have steps array"
        assert "server_completed_steps" in next_step, "Should have server_completed_steps array"

        # Should have both user messages in steps
        assert len(next_step["steps"]) == 2, "Should have both user messages"
        assert next_step["steps"][0]["id"] == "prepare_msg"
        assert next_step["steps"][0]["type"] == "user_message"
        assert next_step["steps"][1]["id"] == "result_msg"
        assert next_step["steps"][1]["type"] == "user_message"

        # Should have shell command in server_completed_steps
        assert len(next_step["server_completed_steps"]) == 1, "Should have shell command"
        assert next_step["server_completed_steps"][0]["id"] == "test_cmd"
        assert next_step["server_completed_steps"][0]["type"] == "shell_command"

        # Verify the shell command was executed and state was updated
        status = executor.get_workflow_status(workflow_id)
        state = status["state"]
        assert "output" in state["raw"], "State should contain output from shell command"
        assert "Hello from workflow" in state["raw"]["output"], "Output should contain command result"

        # Complete the batch by acknowledging the final message
        executor.step_complete(workflow_id, "result_msg", "success")
        final_step = executor.get_next_step(workflow_id)
        assert final_step is None, "Workflow should be complete"

    def test_shell_command_execution_context_flow(self):
        """Test the complete execution flow for shell commands with multiple steps."""
        workflow_def = WorkflowDefinition(
            name="test_execution_flow",
            description="Test complete shell command execution flow",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(id="start_msg", type="user_message", definition={"message": "Starting workflow..."}),
                WorkflowStep(id="first_cmd", type="shell_command", definition={"command": "echo 'First command'"}),
                WorkflowStep(id="middle_msg", type="user_message", definition={"message": "Between commands..."}),
                WorkflowStep(id="second_cmd", type="shell_command", definition={"command": "echo 'Second command'"}),
                WorkflowStep(id="end_msg", type="user_message", definition={"message": "Workflow complete!"}),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # First call: should process start_msg, first_cmd, middle_msg, second_cmd internally
        # and return ALL processed user messages and server-completed shell commands
        step1 = executor.get_next_step(workflow_id)

        assert step1 is not None
        assert "steps" in step1, "Should have steps array"
        assert "server_completed_steps" in step1, "Should have server_completed_steps array"

        # Should have all three user messages in steps
        assert len(step1["steps"]) == 3, "Should have ALL three user messages that were processed"

        # Verify all messages are included in correct order
        msg_ids = [msg["id"] for msg in step1["steps"]]
        expected_msgs = ["start_msg", "middle_msg", "end_msg"]
        assert msg_ids == expected_msgs, f"Expected {expected_msgs} but got {msg_ids}"

        assert step1["steps"][0]["definition"]["message"] == "Starting workflow..."
        assert step1["steps"][1]["definition"]["message"] == "Between commands..."
        assert step1["steps"][2]["definition"]["message"] == "Workflow complete!"

        # Should have both shell commands in server_completed_steps
        assert len(step1["server_completed_steps"]) == 2, "Should have both shell commands"
        server_step_ids = [step["id"] for step in step1["server_completed_steps"]]
        expected_steps = ["first_cmd", "second_cmd"]
        assert server_step_ids == expected_steps, f"Expected {expected_steps} but got {server_step_ids}"

        # Complete the batch (workflow should complete after this)
        for step in step1["steps"]:
            executor.step_complete(workflow_id, step["id"], "success")

        # Workflow should be complete
        step2 = executor.get_next_step(workflow_id)
        assert step2 is None, "Workflow should be complete"

        # Verify final status
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed"

    def test_shell_command_with_actionable_step(self):
        """Test batching behavior when shell commands are followed by an actionable step."""
        workflow_def = WorkflowDefinition(
            name="test_actionable",
            description="Test shell command with actionable step",
            version="1.0.0",
            default_state={},
            state_schema=StateSchema(),
            inputs={},
            steps=[
                WorkflowStep(id="start_msg", type="user_message", definition={"message": "Starting process..."}),
                WorkflowStep(id="first_cmd", type="shell_command", definition={"command": "echo 'Setup complete'"}),
                WorkflowStep(
                    id="actionable_cmd",
                    type="mcp_call",
                    definition={"tool": "some_tool", "parameters": {"param": "value"}},
                ),
            ],
        )

        executor = WorkflowExecutor()
        result = executor.start(workflow_def)
        workflow_id = result["workflow_id"]

        # Should process start_msg and first_cmd internally, then return:
        # - steps: [start_msg, actionable_cmd]
        # - server_completed_steps: [first_cmd]
        step1 = executor.get_next_step(workflow_id)

        assert step1 is not None
        assert "steps" in step1, "Should have steps array"
        assert "server_completed_steps" in step1, "Should have server_completed_steps array"

        # Should have start_msg and actionable_cmd in steps
        assert len(step1["steps"]) == 2, "Should have user message and actionable step"
        assert step1["steps"][0]["id"] == "start_msg"
        assert step1["steps"][0]["type"] == "user_message"
        assert step1["steps"][0]["definition"]["message"] == "Starting process..."
        assert step1["steps"][1]["id"] == "actionable_cmd"
        assert step1["steps"][1]["type"] == "mcp_call"

        # Should have the shell command in server_completed_steps
        assert len(step1["server_completed_steps"]) == 1, "Should have one server-completed step"
        assert step1["server_completed_steps"][0]["id"] == "first_cmd"
        assert step1["server_completed_steps"][0]["type"] == "shell_command"

        # Complete the actionable step
        executor.step_complete(workflow_id, "actionable_cmd", "success")

        # Workflow should be complete
        step2 = executor.get_next_step(workflow_id)
        assert step2 is None, "Workflow should be complete"

        # Verify workflow status
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed", "Workflow should be marked as completed"
