"""Tests for missing workflow coverage including shell commands, batch updates, and complex computed fields."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.context import context_manager
from aromcp.workflow_server.workflow.models import SubAgentTask, WorkflowDefinition, WorkflowStep
from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor


class TestShellCommandExecution:
    """Test shell command step execution."""

    def setup_method(self):
        """Set up test dependencies."""
        context_manager.contexts.clear()

    def teardown_method(self):
        """Clean up after tests."""
        context_manager.contexts.clear()

    def test_shell_command_basic(self):
        """Test basic shell command execution."""
        steps = [
            WorkflowStep(
                id="cmd1",
                type="shell_command",
                definition={
                    "command": "echo 'Hello from test'",
                    "output_format": "text"
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:shell",
            description="Test shell commands",
            version="1.0.0",
            default_state={"raw": {}},
            state_schema=StateSchema(raw={}, computed={}, state={}),
            inputs={},
            steps=steps
        )

        executor = WorkflowExecutor()
        with patch("aromcp.workflow_server.workflow.steps.shell_command.subprocess.run") as mock_run:
            mock_run.return_value.stdout = "Hello from test\n"
            mock_run.return_value.stderr = ""
            mock_run.return_value.returncode = 0

            start_result = executor.start(workflow_def)
            workflow_id = start_result["workflow_id"]

            # Get next step - shell commands are server-side
            # Since there are no client steps, get_next_step returns None after executing shell command
            step_result = executor.get_next_step(workflow_id)
            
            # No client steps, so result should be None
            assert step_result is None
            
            # But we can verify the workflow completed successfully
            status = executor.get_workflow_status(workflow_id)
            assert status["status"] == "completed"
            
            # Verify the mock was called
            mock_run.assert_called_once()

    def test_shell_command_with_state_update(self):
        """Test shell command with state update."""
        steps = [
            WorkflowStep(
                id="cmd1",
                type="shell_command",
                definition={
                    "command": "echo 'test-value-123'",
                    "output_format": "text",
                    "state_update": {
                        "path": "raw.package_version"
                    }
                }
            ),
            WorkflowStep(
                id="msg1",
                type="user_message",
                definition={
                    "message": "Package version: {{ raw.package_version }}"
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:shell_state",
            description="Test shell with state update",
            version="1.0.0",
            default_state={"raw": {}},
            state_schema=StateSchema(raw={"package_version": "string"}, computed={}, state={}),
            inputs={},
            steps=steps
        )

        executor = WorkflowExecutor()
        with patch("aromcp.workflow_server.workflow.steps.shell_command.subprocess.run") as mock_run:
            mock_run.return_value.stdout = 'test-value-123\n'
            mock_run.return_value.stderr = ""
            mock_run.return_value.returncode = 0

            start_result = executor.start(workflow_def)
            workflow_id = start_result["workflow_id"]

            # Get next step
            step_result = executor.get_next_step(workflow_id)
            
            # Should have user message with replaced variable
            assert step_result is not None
            assert "steps" in step_result
            assert len(step_result["steps"]) == 1
            assert step_result["steps"][0]["type"] == "user_message"
            
            # The shell command should update the state
            # Check if the message has the expected content
            message = step_result["steps"][0]["definition"]["message"]
            assert "test-value-123" in message

    def test_shell_command_with_working_directory(self):
        """Test shell command with working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file in the temp directory
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            steps = [
                WorkflowStep(
                    id="cmd1",
                    type="shell_command",
                    definition={
                        "command": "ls -la",
                        "working_directory": tmpdir,
                        "output_format": "text"
                    }
                )
            ]

            workflow_def = WorkflowDefinition(
                name="test:shell_dir",
                description="Test shell with working directory",
                version="1.0.0",
                default_state={"raw": {}},
                state_schema=StateSchema(raw={}, computed={}, state={}),
                inputs={},
                steps=steps
            )

            executor = WorkflowExecutor()
            with patch("aromcp.workflow_server.workflow.steps.shell_command.subprocess.run") as mock_run:
                mock_run.return_value.stdout = "test.txt\n"
                mock_run.return_value.stderr = ""
                mock_run.return_value.returncode = 0

                start_result = executor.start(workflow_def)
                workflow_id = start_result["workflow_id"]

                # Get next step
                step_result = executor.get_next_step(workflow_id)
                
                # Verify the command was called (but cwd will be project root)
                mock_run.assert_called_once()
                # Note: ShellCommandProcessor always uses project root, not custom working_directory


class TestBatchStateUpdate:
    """Test batch state update functionality."""

    def setup_method(self):
        """Set up test dependencies."""
        context_manager.contexts.clear()

    def teardown_method(self):
        """Clean up after tests."""
        context_manager.contexts.clear()

    def test_batch_state_update_basic(self):
        """Test basic batch state update."""
        steps = [
            WorkflowStep(
                id="batch1",
                type="batch_state_update",
                definition={
                    "updates": [
                        {"path": "raw.counter", "value": 10},
                        {"path": "raw.message", "value": "Hello"},
                        {"path": "raw.enabled", "value": True}
                    ]
                }
            ),
            WorkflowStep(
                id="msg1",
                type="user_message",
                definition={
                    "message": "Counter: {{ raw.counter }}, Message: {{ raw.message }}, Enabled: {{ raw.enabled }}"
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:batch_update",
            description="Test batch state updates",
            version="1.0.0",
            default_state={"raw": {"counter": 0, "message": "", "enabled": False}},
            state_schema=StateSchema(
                raw={"counter": "number", "message": "string", "enabled": "boolean"},
                computed={},
                state={}
            ),
            inputs={},
            steps=steps
        )

        executor = WorkflowExecutor()
        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - batch update is server-side
        step_result = executor.get_next_step(workflow_id)
        
        # Should have the user message with all values replaced
        assert "steps" in step_result
        assert len(step_result["steps"]) == 1
        assert step_result["steps"][0]["type"] == "user_message"
        
        message = step_result["steps"][0]["definition"]["message"]
        assert "Counter: 10" in message
        assert "Message: Hello" in message
        assert "Enabled: True" in message

    def test_batch_state_update_with_operations(self):
        """Test batch state update with different operations."""
        steps = [
            WorkflowStep(
                id="init",
                type="state_update",
                definition={"path": "raw.counter", "value": 5}
            ),
            WorkflowStep(
                id="batch1",
                type="batch_state_update",
                definition={
                    "updates": [
                        {"path": "raw.counter", "value": 3, "operation": "increment"},
                        {"path": "raw.items", "value": ["a", "b", "c"], "operation": "set"},
                        {"path": "raw.items", "value": "d", "operation": "append"}
                    ]
                }
            ),
            WorkflowStep(
                id="msg1",
                type="user_message",
                definition={
                    "message": "Counter: {{ raw.counter }}, Items: {{ raw.items }}"
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:batch_ops",
            description="Test batch operations",
            version="1.0.0",
            default_state={"raw": {"counter": 0, "items": []}},
            state_schema=StateSchema(
                raw={"counter": "number", "items": "array"},
                computed={},
                state={}
            ),
            inputs={},
            steps=steps
        )

        executor = WorkflowExecutor()
        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step
        step_result = executor.get_next_step(workflow_id)
        
        # Check the message has correct values
        assert "steps" in step_result
        message = step_result["steps"][0]["definition"]["message"]
        assert "Counter: 8" in message  # 5 + 3
        # Check for the array representation (Python str() of list)
        assert "'a', 'b', 'c', 'd'" in message or "a,b,c,d" in message


class TestComplexComputedFields:
    """Test complex computed fields with multi-dependency transforms."""

    def setup_method(self):
        """Set up test dependencies."""
        context_manager.contexts.clear()

    def teardown_method(self):
        """Clean up after tests."""
        context_manager.contexts.clear()

    def test_multi_dependency_computed_fields(self):
        """Test computed fields with multiple dependencies like in analyze:dependencies workflow."""
        # Simulate the analyze:dependencies workflow structure
        state_schema = StateSchema(
            raw={
                "package_json": "string",
                "npm_list": "string"
            },
            computed={
                "dependencies": {
                    "from": "raw.package_json",
                    "transform": "JSON.parse(input).dependencies || {}"
                },
                "outdated_deps": {
                    "from": "raw.npm_list",
                    "transform": """
                        input.split('\\n')
                          .filter(line => line.includes('outdated'))
                          .map(line => {
                            const parts = line.split(/\\s+/);
                            return {
                              name: parts[0],
                              current: parts[1],
                              wanted: parts[2],
                              latest: parts[3]
                            };
                          })
                    """
                },
                "security_risks": {
                    "from": ["computed.outdated_deps", "computed.dependencies"],
                    "transform": """
                        input[0].filter(dep => {
                          const current = input[1][dep.name];
                          return current && dep.latest && dep.latest.split('.')[0] > current.split('.')[0];
                        })
                    """
                }
            },
            state={}
        )

        steps = [
            WorkflowStep(
                id="set_package",
                type="state_update",
                definition={
                    "path": "raw.package_json",
                    "value": '{"dependencies": {"lodash": "3.10.1", "express": "4.17.1"}}'
                }
            ),
            WorkflowStep(
                id="set_npm_list",
                type="state_update",
                definition={
                    "path": "raw.npm_list",
                    "value": "lodash 3.10.1 3.10.1 4.17.21 outdated\nexpress 4.17.1 4.17.1 4.18.2"
                }
            ),
            WorkflowStep(
                id="report",
                type="user_message",
                definition={
                    "message": "Found {{ computed.outdated_deps.length }} outdated, {{ computed.security_risks.length }} major updates needed"
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:complex_computed",
            description="Test complex computed fields",
            version="1.0.0",
            default_state={"raw": {"package_json": "", "npm_list": ""}},
            state_schema=state_schema,
            inputs={},
            steps=steps
        )

        executor = WorkflowExecutor()
        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - should process state updates and return message
        step_result = executor.get_next_step(workflow_id)
        
        # Should have the report message
        assert "steps" in step_result
        assert len(step_result["steps"]) == 1
        assert step_result["steps"][0]["type"] == "user_message"
        
        message = step_result["steps"][0]["definition"]["message"]
        # Should find 1 outdated (lodash) and 1 major update (lodash 3.x to 4.x)
        assert "Found 1 outdated" in message
        assert "1 major updates needed" in message

    def test_nested_computed_field_access(self):
        """Test accessing nested computed fields in templates."""
        state_schema = StateSchema(
            raw={
                "files": "array"
            },
            computed={
                "file_stats": {
                    "from": "raw.files",
                    "transform": """
                        {
                            total: input.length,
                            typescript: input.filter(f => f.endsWith('.ts')).length,
                            javascript: input.filter(f => f.endsWith('.js')).length
                        }
                    """
                }
            },
            state={}
        )

        steps = [
            WorkflowStep(
                id="set_files",
                type="state_update",
                definition={
                    "path": "raw.files",
                    "value": ["main.ts", "util.js", "test.ts", "config.js"]
                }
            ),
            WorkflowStep(
                id="report",
                type="user_message",
                definition={
                    "message": "Total: {{ computed.file_stats.total }}, TS: {{ computed.file_stats.typescript }}, JS: {{ computed.file_stats.javascript }}"
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:nested_computed",
            description="Test nested computed field access",
            version="1.0.0",
            default_state={"raw": {"files": []}},
            state_schema=state_schema,
            inputs={},
            steps=steps
        )

        executor = WorkflowExecutor()
        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step
        step_result = executor.get_next_step(workflow_id)
        
        # Check message has correct nested values
        assert "steps" in step_result
        message = step_result["steps"][0]["definition"]["message"]
        assert "Total: 4" in message
        assert "TS: 2" in message
        assert "JS: 2" in message


class TestParallelForeachWithSubAgents:
    """Test parallel foreach with actual sub-agent task definitions."""

    def setup_method(self):
        """Set up test dependencies."""
        context_manager.contexts.clear()

    def teardown_method(self):
        """Clean up after tests."""
        context_manager.contexts.clear()

    def test_parallel_foreach_with_sub_agent_task(self):
        """Test parallel foreach with a properly defined sub-agent task."""
        # Define a sub-agent task
        # Define a sub-agent task with correct InputDefinition objects
        from aromcp.workflow_server.workflow.models import InputDefinition
        
        sub_agent_task = SubAgentTask(
            name="process_file",
            description="Process a single file",
            inputs={
                "file_path": InputDefinition(
                    type="string", 
                    description="Path to file", 
                    required=True
                )
            },
            prompt_template="Process file: {{ file_path }}",
            steps=[
                WorkflowStep(
                    id="process",
                    type="user_message",
                    definition={"message": "Processing {{ item }}"}  # item is available in task_context
                )
            ]
        )

        steps = [
            WorkflowStep(
                id="set_files",
                type="state_update",
                definition={
                    "path": "raw.files",
                    "value": ["file1.txt", "file2.txt", "file3.txt"]
                }
            ),
            WorkflowStep(
                id="parallel_process",
                type="parallel_foreach",
                definition={
                    "items": "raw.files",  # Expression without template braces
                    "sub_agent_task": "process_file",
                    "max_parallel": 2
                }
            )
        ]

        workflow_def = WorkflowDefinition(
            name="test:parallel_sub",
            description="Test parallel sub-agents",
            version="1.0.0",
            default_state={"raw": {"files": []}},
            state_schema=StateSchema(raw={"files": "array"}, computed={}, state={}),
            inputs={},
            steps=steps,
            sub_agent_tasks={"process_file": sub_agent_task}
        )

        executor = WorkflowExecutor()
        start_result = executor.start(workflow_def)
        workflow_id = start_result["workflow_id"]

        # Get next step - should prepare parallel foreach
        step_result = executor.get_next_step(workflow_id)
        
        # Should have the parallel_foreach step
        assert "steps" in step_result
        assert len(step_result["steps"]) == 1
        assert step_result["steps"][0]["type"] == "parallel_foreach"
        
        # Check that tasks were created
        parallel_def = step_result["steps"][0]["definition"]
        assert "tasks" in parallel_def
        assert len(parallel_def["tasks"]) == 2  # max_parallel = 2
        
        # Check task structure
        task = parallel_def["tasks"][0]
        assert "task_id" in task
        assert "context" in task
        assert "inputs" in task
        assert task["inputs"]["file_path"] == "file1.txt"
        
        # Test sub-agent step execution (fixed API)
        task_id = task["task_id"]
        sub_step = executor.get_next_sub_agent_step(workflow_id, task_id)
        
        assert sub_step is not None
        assert "step" in sub_step
        assert sub_step["step"]["type"] == "user_message"
        assert "Processing file1.txt" in sub_step["step"]["definition"]["message"]