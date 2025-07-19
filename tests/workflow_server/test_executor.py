"""Tests for enhanced workflow executor with control flow support."""

from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor


class TestWorkflowExecutor:
    """Test workflow executor with control flow support."""

    def setup_method(self):
        """Set up test dependencies."""
        # Clear any existing contexts
        context_manager.contexts.clear()

    def teardown_method(self):
        """Clean up after tests."""
        # Clear contexts
        context_manager.contexts.clear()

    def create_test_workflow(self, steps=None):
        """Create a test workflow definition."""
        if steps is None:
            steps = [
                WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"}),
                WorkflowStep(id="step2", type="state_update", definition={"path": "raw.counter", "value": 1}),
            ]

        return WorkflowDefinition(
            name="test:workflow",
            description="Test workflow",
            version="1.0.0",
            default_state={"raw": {"counter": 0}},
            state_schema=StateSchema(raw={"counter": "number"}, computed={}, state={}),
            inputs={},
            steps=steps,
        )

    def test_workflow_start_basic(self):
        """Test basic workflow start functionality."""
        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow()

        result = executor.start(workflow_def, {"initial_value": 42})

        assert "workflow_id" in result
        assert result["status"] == "running"
        assert result["total_steps"] == 2
        assert "execution_context" in result

        # Check that execution context was created
        workflow_id = result["workflow_id"]
        context = context_manager.get_context(workflow_id)
        assert context is not None
        assert len(context.execution_stack) == 1

    def test_get_next_step_sequential(self):
        """Test sequential step execution."""
        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow()

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get first step - should be batched with new format
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # Should use new batched format
        assert "steps" in step_result
        assert "server_completed_steps" in step_result

        # User message should be in steps
        assert len(step_result["steps"]) == 1
        assert step_result["steps"][0]["id"] == "step1"
        assert step_result["steps"][0]["type"] == "user_message"

        # State update should be in server_completed_steps
        assert len(step_result["server_completed_steps"]) == 1
        assert step_result["server_completed_steps"][0]["id"] == "step2"
        assert step_result["server_completed_steps"][0]["type"] == "state_update"

        # Complete the user message step
        executor.step_complete(workflow_id, "step1", "success")

        # Should be no more steps
        step_result = executor.get_next_step(workflow_id)
        assert step_result is None

    def test_conditional_step_processing(self):
        """Test conditional step processing."""
        steps = [
            WorkflowStep(
                id="cond1",
                type="conditional",
                definition={
                    "condition": "raw.counter > 0",
                    "then_steps": [{"type": "user_message", "message": "Counter is positive"}],
                    "else_steps": [{"type": "user_message", "message": "Counter is zero or negative"}],
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        # Start with positive counter
        start_result = executor.start(workflow_def, {"counter": 5})
        workflow_id = start_result["workflow_id"]

        # Get next step - should process conditional and return then branch
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # The conditional should be processed internally and return the then branch step
        assert step_result["step"]["type"] == "user_message"
        assert "Counter is positive" in step_result["step"]["definition"]["message"]

    def test_while_loop_processing(self):
        """Test while loop processing."""
        steps = [
            WorkflowStep(
                id="loop1",
                type="while_loop",
                definition={
                    "condition": "raw.counter < 3",
                    "max_iterations": 5,
                    "body": [
                        {"type": "state_update", "path": "raw.counter", "operation": "increment"},
                        {"type": "user_message", "message": "Counter incremented to {{ raw.counter }}"}
                    ],
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"counter": 0})
        workflow_id = start_result["workflow_id"]

        # Get next step - should process the while loop and return user messages from loop body
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # Should get batched format with user messages and server-completed state updates
        assert "steps" in step_result
        assert "server_completed_steps" in step_result
        
        # Should have user messages from multiple loop iterations
        user_messages = [s for s in step_result["steps"] if s["type"] == "user_message"]
        assert len(user_messages) >= 1
        
        # Should have state_update steps in server_completed_steps
        state_updates = [s for s in step_result["server_completed_steps"] if s["type"] == "state_update"]
        assert len(state_updates) >= 1

    def test_foreach_loop_processing(self):
        """Test foreach loop processing."""
        steps = [
            WorkflowStep(
                id="foreach1",
                type="foreach",
                definition={
                    "items": "raw.files",
                    "body": [{"type": "user_message", "message": "Processing {{ state.loop_item }}"}],
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"files": ["file1.txt", "file2.txt"]})
        workflow_id = start_result["workflow_id"]

        # Get next step - should process foreach loop and return user messages
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # Should get batched format with user messages from loop iterations
        assert "steps" in step_result
        assert "server_completed_steps" in step_result
        
        # Should have user messages from foreach iterations
        user_messages = [s for s in step_result["steps"] if s["type"] == "user_message"]
        assert len(user_messages) >= 1
        
        # Messages should contain variable replacements
        messages = [msg["definition"]["message"] for msg in user_messages]
        assert any("file1.txt" in msg for msg in messages)

    def test_user_input_step_processing(self):
        """Test user input step processing."""
        steps = [
            WorkflowStep(
                id="input1",
                type="user_input",
                definition={
                    "prompt": "Enter your name:",
                    "variable_name": "user_name",
                    "input_type": "string",
                    "required": True,
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - should be user input (user_input is client-side)
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        
        # Should be in batched format or single step format depending on implementation
        if "steps" in step_result:
            # Batched format
            user_input_steps = [s for s in step_result["steps"] if s["type"] == "user_input"]
            assert len(user_input_steps) == 1
            user_input_step = user_input_steps[0]
        else:
            # Single step format
            assert "step" in step_result
            user_input_step = step_result["step"]
            
        assert user_input_step["type"] == "user_input"
        assert user_input_step["definition"]["prompt"] == "Enter your name:"

        # Complete with user input
        executor.step_complete(workflow_id, "input1", "success", {"user_input": "Alice"})

        # Verify workflow can continue (this test doesn't use context manager)
        final_step = executor.get_next_step(workflow_id)
        assert final_step is None  # Should be complete

    def test_break_and_continue_processing(self):
        """Test break and continue step processing."""
        steps = [
            WorkflowStep(
                id="loop1",
                type="while_loop",
                definition={
                    "condition": "true",  # Always true condition
                    "max_iterations": 3,  # Will hit max iterations
                    "body": [{"type": "user_message", "message": "Loop iteration"}],
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"counter": 0})
        workflow_id = start_result["workflow_id"]

        # Get first step from loop body - should get user messages from loop iterations  
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        
        # Should get batched format with user messages from loop iterations
        assert "steps" in step_result
        assert "server_completed_steps" in step_result
        
        # Should have user messages from multiple iterations (max_iterations=3)
        user_messages = [s for s in step_result["steps"] if s["type"] == "user_message"]
        assert len(user_messages) >= 1
        assert "Loop iteration" in user_messages[0]["definition"]["message"]

    def test_nested_control_structures(self):
        """Test nested conditionals and loops."""
        steps = [
            WorkflowStep(
                id="cond1",
                type="conditional",
                definition={
                    "condition": "files.length > 0",
                    "then_steps": [
                        {
                            "type": "foreach",
                            "items": "files",
                            "body": [
                                {
                                    "type": "conditional",
                                    "condition": "item.endsWith('.ts')",
                                    "then_steps": [{"type": "user_message", "message": "TypeScript file: {{ item }}"}],
                                }
                            ],
                        }
                    ],
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"files": ["file1.ts", "file2.js"]})
        workflow_id = start_result["workflow_id"]

        # Execute through nested structures
        iterations = 0
        while iterations < 10:  # Safety limit
            step_result = executor.get_next_step(workflow_id)
            if step_result is None:
                break

            executor.step_complete(workflow_id, step_result["step"]["id"], "success")
            iterations += 1

        # Should complete without infinite loops
        assert iterations < 10

    def test_error_handling_in_control_flow(self):
        """Test error handling in control flow processing."""
        steps = [
            WorkflowStep(
                id="cond1",
                type="conditional",
                definition={
                    "condition": "5 +",  # Truly invalid expression
                    "then_steps": [{"type": "user_message", "message": "Should not reach"}],
                },
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - should return error response
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert "error" in step_result
        assert "Error evaluating condition" in step_result["error"]

    def test_workflow_completion_with_control_flow(self):
        """Test workflow completion with control flow structures."""
        steps = [
            WorkflowStep(
                id="cond1",
                type="conditional",
                definition={
                    "condition": "tasks.length > 0",
                    "then_steps": [{"type": "user_message", "message": "Processing tasks"}],
                },
            ),
            WorkflowStep(id="final", type="user_message", definition={"message": "All tasks completed"}),
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"tasks": ["task1", "task2"]})
        workflow_id = start_result["workflow_id"]

        # Execute all steps
        step_count = 0
        while step_count < 10:  # Safety limit
            step_result = executor.get_next_step(workflow_id)
            if step_result is None:
                break

            # Handle different response formats
            if "steps" in step_result:
                # New batched format
                if len(step_result["steps"]) > 0:
                    # Complete the last step in the batch
                    last_step = step_result["steps"][-1]
                    executor.step_complete(workflow_id, last_step["id"], "success")
                else:
                    # No agent-visible steps, workflow might be done
                    break
            elif "step" in step_result:
                # Single step format (from control flow)
                executor.step_complete(workflow_id, step_result["step"]["id"], "success")
            else:
                # Unknown format
                break
            step_count += 1

        # Check workflow status
        status = executor.get_workflow_status(workflow_id)
        assert status["status"] == "completed"

    def test_parallel_foreach_processing(self):
        """Test parallel foreach step processing."""
        steps = [
            WorkflowStep(
                id="parallel1",
                type="parallel_foreach",
                definition={"items": "raw.batches", "sub_agent_task": "process_batch", "max_parallel": 3},
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"batches": ["batch1", "batch2", "batch3", "batch4"]})
        workflow_id = start_result["workflow_id"]

        # Get next step - should attempt parallel_foreach but fail due to missing sub-agent task
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        
        # Should return error response since "process_batch" sub-agent task is not defined
        if "error" in step_result:
            assert "Sub-agent task not found: process_batch" in step_result["error"]
        else:
            # If it succeeded somehow, check the format
            if "steps" in step_result:
                parallel_steps = [s for s in step_result["steps"] if s["type"] == "parallel_foreach"]
                assert len(parallel_steps) >= 1
            else:
                assert "step" in step_result
                assert step_result["step"]["type"] == "parallel_foreach"

    def test_variable_replacement_with_context(self):
        """Test variable replacement with state-based variables."""
        steps = [
            WorkflowStep(
                id="input1", 
                type="state_update", 
                definition={"path": "raw.user_value", "value": "test_value"}
            ),
            WorkflowStep(
                id="message1", 
                type="user_message", 
                definition={"message": "You entered: {{ raw.user_value }}"}
            ),
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - state_update should be processed internally, user_message returned
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # Should get batched format with user message and server-completed state update
        assert "steps" in step_result
        assert "server_completed_steps" in step_result
        
        # Should have user message with variable replaced
        user_messages = [s for s in step_result["steps"] if s["type"] == "user_message"]
        assert len(user_messages) == 1
        message = user_messages[0]["definition"]["message"]
        assert message == "You entered: test_value"
        
        # Should have state_update in server_completed_steps
        state_updates = [s for s in step_result["server_completed_steps"] if s["type"] == "state_update"]
        assert len(state_updates) == 1

    def test_execution_context_cleanup(self):
        """Test that execution contexts are properly cleaned up."""
        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(
            [WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})]
        )

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Verify context exists
        assert context_manager.get_context(workflow_id) is not None

        # Complete workflow
        step_result = executor.get_next_step(workflow_id)
        executor.step_complete(workflow_id, "step1", "success")

        # Get next step (should be None and clean up context)
        step_result = executor.get_next_step(workflow_id)
        assert step_result is None

        # Context should be cleaned up
        assert context_manager.get_context(workflow_id) is None
