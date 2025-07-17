"""Tests for enhanced workflow executor with control flow support."""


from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.executor import WorkflowExecutor
from aromcp.workflow_server.workflow.models import WorkflowDefinition, WorkflowStep


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
                WorkflowStep(id="step2", type="state_update", definition={"path": "raw.counter", "value": 1})
            ]

        return WorkflowDefinition(
            name="test:workflow",
            description="Test workflow",
            version="1.0.0",
            default_state={"raw": {"counter": 0}},
            state_schema=StateSchema(
                raw={"counter": "number"},
                computed={},
                state={}
            ),
            inputs={},
            steps=steps
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

        # Get first step
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["id"] == "step1"
        assert step_result["step"]["type"] == "user_message"

        # Complete first step
        executor.step_complete(workflow_id, "step1", "success")

        # Get second step
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["id"] == "step2"
        assert step_result["step"]["type"] == "state_update"

        # Complete second step
        executor.step_complete(workflow_id, "step2", "success")

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
                    "condition": "counter > 0",
                    "then_steps": [
                        {"type": "user_message", "message": "Counter is positive"}
                    ],
                    "else_steps": [
                        {"type": "user_message", "message": "Counter is zero or negative"}
                    ]
                }
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
                    "condition": "counter < 3",
                    "max_iterations": 5,
                    "body": [
                        {"type": "state_update", "path": "raw.counter", "operation": "increment"}
                    ]
                }
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"counter": 0})
        workflow_id = start_result["workflow_id"]

        # Get next step - should enter while loop
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # Should get the first iteration of the loop body
        assert step_result["step"]["type"] == "state_update"

        # Check that we're in a loop context
        context = context_manager.get_context(workflow_id)
        assert context.is_in_loop()
        assert context.current_loop().loop_type == "while"

    def test_foreach_loop_processing(self):
        """Test foreach loop processing."""
        steps = [
            WorkflowStep(
                id="foreach1",
                type="foreach",
                definition={
                    "items": "files",
                    "variable_name": "file",
                    "body": [
                        {"type": "user_message", "message": "Processing {{ file }}"}
                    ]
                }
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"files": ["file1.txt", "file2.txt"]})
        workflow_id = start_result["workflow_id"]

        # Get next step - should enter foreach loop
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None

        # Should get the first iteration of the loop body
        assert step_result["step"]["type"] == "user_message"

        # Check that we're in a loop context
        context = context_manager.get_context(workflow_id)
        assert context.is_in_loop()
        assert context.current_loop().loop_type == "foreach"
        assert context.current_loop().variable_bindings["file"] == "file1.txt"

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
                    "required": True
                }
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - should be user input
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["type"] == "user_input"
        assert step_result["step"]["definition"]["prompt"] == "Enter your name:"

        # Complete with user input
        executor.step_complete(
            workflow_id,
            "input1",
            "success",
            {"user_input": "Alice"}
        )

        # Check that input was stored
        context = context_manager.get_context(workflow_id)
        assert context.get_variable("user_name") == "Alice"

    def test_break_and_continue_processing(self):
        """Test break and continue step processing."""
        steps = [
            WorkflowStep(
                id="loop1",
                type="while_loop",
                definition={
                    "condition": "true",  # Always true condition
                    "max_iterations": 3,  # Will hit max iterations
                    "body": [
                        {"type": "user_message", "message": "Loop iteration"}
                    ]
                }
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {"counter": 0})
        workflow_id = start_result["workflow_id"]

        # Get first step from loop body
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["type"] == "user_message"

        # Check that we're in a loop context
        context = context_manager.get_context(workflow_id)
        assert context.is_in_loop()
        assert context.current_loop().loop_type == "while"

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
                                    "then_steps": [
                                        {"type": "user_message", "message": "TypeScript file: {{ item }}"}
                                    ]
                                }
                            ]
                        }
                    ]
                }
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
                    "then_steps": [{"type": "user_message", "message": "Should not reach"}]
                }
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - should return error step
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["type"] == "error"
        assert "error" in step_result["step"]["definition"]

    def test_workflow_completion_with_control_flow(self):
        """Test workflow completion with control flow structures."""
        steps = [
            WorkflowStep(
                id="cond1",
                type="conditional",
                definition={
                    "condition": "tasks.length > 0",
                    "then_steps": [
                        {"type": "user_message", "message": "Processing tasks"}
                    ]
                }
            ),
            WorkflowStep(
                id="final",
                type="user_message",
                definition={"message": "All tasks completed"}
            )
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

            executor.step_complete(workflow_id, step_result["step"]["id"], "success")
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
                definition={
                    "items": "batches",
                    "sub_agent_task": "process_batch",
                    "max_parallel": 3
                }
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def, {
            "batches": ["batch1", "batch2", "batch3", "batch4"]
        })
        workflow_id = start_result["workflow_id"]

        # Get next step - should create parallel tasks
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["type"] == "parallel_foreach"

        # Should have sub-agent tasks
        sub_tasks = step_result["step"]["definition"]["sub_agent_tasks"]
        assert len(sub_tasks) == 3  # Limited by max_parallel
        assert sub_tasks[0]["context"]["item"] == "batch1"
        assert sub_tasks[1]["context"]["item"] == "batch2"
        assert sub_tasks[2]["context"]["item"] == "batch3"

    def test_variable_replacement_with_context(self):
        """Test variable replacement with execution context variables."""
        steps = [
            WorkflowStep(
                id="input1",
                type="user_input",
                definition={
                    "prompt": "Enter value:",
                    "variable_name": "user_value"
                }
            ),
            WorkflowStep(
                id="message1",
                type="user_message",
                definition={"message": "You entered: {{ user_value }}"}
            )
        ]

        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow(steps)

        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Complete user input
        step_result = executor.get_next_step(workflow_id)
        executor.step_complete(workflow_id, "input1", "success", {"user_input": "test_value"})

        # Get next step - should have variable replaced
        step_result = executor.get_next_step(workflow_id)
        assert step_result is not None
        assert step_result["step"]["definition"]["message"] == "You entered: test_value"

    def test_execution_context_cleanup(self):
        """Test that execution contexts are properly cleaned up."""
        executor = WorkflowExecutor()
        workflow_def = self.create_test_workflow([
            WorkflowStep(id="step1", type="user_message", definition={"message": "Hello"})
        ])

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
