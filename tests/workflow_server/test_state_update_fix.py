"""Test fix for state_update template evaluation."""

from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor


class TestStateUpdateFix:
    """Test state_update template evaluation fix."""

    def setup_method(self):
        """Setup test environment."""
        self.executor = WorkflowExecutor()
        self.loader = WorkflowLoader()
        context_manager.contexts.clear()

    def teardown_method(self):
        """Cleanup test environment."""
        context_manager.contexts.clear()
        self.executor.workflows.clear()

    def test_sub_agent_inputs_in_prompt(self):
        """Test that sub-agent tasks include proper inputs in the prompt and context."""

        # Load and start the test workflow
        workflow_def = self.loader.load("test:sub-agents")

        # Manually set state to have files (simulating user input)
        start_result = self.executor.start(workflow_def, {})
        workflow_id = start_result["workflow_id"]

        # Manually update state to simulate the initialize step being completed by user/agent
        update_result = self.executor.state_manager.update(
            workflow_id, [{"path": "raw.files", "value": ["test1.ts", "test2.ts"]}]
        )
        print(f"Update result: {update_result}")

        state_after_update = self.executor.state_manager.read(workflow_id)
        print(f"State after manual update: {state_after_update}")
        print(f"raw.files type after update: {type(state_after_update.get('raw', {}).get('files'))}")

        # Get next step - should be parallel_foreach now
        next_step = self.executor.get_next_step(workflow_id)

        print(f"Next step type: {next_step.get('step', {}).get('type')}")

        if next_step and next_step.get("step", {}).get("type") == "parallel_foreach":
            print("✅ Parallel foreach step returned successfully!")

            # Check that tasks include inputs
            tasks = next_step["step"]["definition"]["tasks"]
            print(f"Tasks created: {len(tasks)}")

            for task in tasks:
                print(f"\n--- Task: {task['task_id']} ---")
                print(f"Context: {task['context']}")

                # Check that inputs are included
                assert "inputs" in task, f"Task {task['task_id']} missing inputs"
                inputs = task["inputs"]
                print(f"Inputs: {inputs}")

                # Check that file_path input is mapped correctly
                assert "file_path" in inputs, f"Task {task['task_id']} missing file_path input"
                assert inputs["file_path"] == task["context"]["item"], "file_path input not mapped correctly"

            # Check the enhanced sub-agent prompt
            subagent_prompt = next_step["step"]["subagent_prompt"]
            print("\n--- Sub-agent Prompt ---")
            print(subagent_prompt)

            # Should contain the inputs JSON template
            assert "SUB_AGENT_INPUTS" in subagent_prompt, "Sub-agent prompt missing inputs template"
            assert "```json" in subagent_prompt, "Sub-agent prompt missing JSON formatting"
            assert '"inputs":' in subagent_prompt, "Sub-agent prompt missing inputs section"

            print("✅ Sub-agent inputs and prompt validation passed!")
        else:
            print(f"❌ Expected parallel_foreach, got: {next_step}")
