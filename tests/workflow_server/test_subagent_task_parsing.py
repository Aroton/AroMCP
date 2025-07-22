"""Unit tests for SubAgentTask field parsing in WorkflowLoader.

Tests the parsing of default_state and state_schema fields for sub-agent tasks
to ensure the new fields are correctly loaded from YAML workflow definitions.
"""

import pytest
import yaml

from aromcp.workflow_server.workflow.loader import WorkflowLoader
from aromcp.workflow_server.workflow.models import WorkflowValidationError


class TestSubAgentTaskParsing:
    """Test SubAgentTask field parsing in WorkflowLoader."""

    def setup_method(self):
        """Set up test dependencies."""
        self.loader = WorkflowLoader()

    def test_parse_sub_agent_task_with_default_state(self):
        """Test parsing sub-agent task with default_state field."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          test_task:
            description: "Test sub-agent task"
            inputs:
              file_path:
                type: "string"
                description: "File path"
                required: true
            default_state:
              state:
                attempt_number: 0
                success: false
                last_error: ""
                step_results:
                  hints: null
                  lint: null
                  typescript: null
            steps:
              - id: "test_step"
                type: "user_message"
                message: "Test message"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify sub-agent task was parsed
        assert "test_task" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["test_task"]
        
        # Verify default_state was parsed correctly
        assert hasattr(task, 'default_state')
        assert task.default_state is not None
        assert "raw" in task.default_state
        assert task.default_state["state"]["attempt_number"] == 0
        assert task.default_state["state"]["success"] is False
        assert task.default_state["state"]["last_error"] == ""
        assert task.default_state["state"]["step_results"]["hints"] is None

    def test_parse_sub_agent_task_with_state_schema(self):
        """Test parsing sub-agent task with state_schema field."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          test_task:
            description: "Test sub-agent task"
            inputs:
              file_path:
                type: "string"
                description: "File path"
                required: true
            state_schema:
              computed:
                is_typescript_file:
                  from: "raw.file_path"
                  transform: "input.endsWith('.ts') || input.endsWith('.tsx')"
                can_continue:
                  from: ["raw.attempt_number", "raw.max_attempts"]
                  transform: "input[0] < input[1]"
            steps:
              - id: "test_step"
                type: "user_message"
                message: "Test message"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify sub-agent task was parsed
        assert "test_task" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["test_task"]
        
        # Verify state_schema was parsed correctly
        assert hasattr(task, 'state_schema')
        assert task.state_schema is not None
        assert hasattr(task.state_schema, 'computed')
        
        computed = task.state_schema.computed
        assert "is_typescript_file" in computed
        assert "can_continue" in computed
        
        # Verify computed field definitions
        is_ts_field = computed["is_typescript_file"]
        assert is_ts_field["from"] == "raw.file_path"
        assert "endsWith" in is_ts_field["transform"]
        
        can_continue_field = computed["can_continue"]
        assert can_continue_field["from"] == ["raw.attempt_number", "raw.max_attempts"]
        assert "input[0] < input[1]" in can_continue_field["transform"]

    def test_parse_sub_agent_task_with_both_fields(self):
        """Test parsing sub-agent task with both default_state and state_schema."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          complete_task:
            description: "Complete sub-agent task"
            inputs:
              file_path:
                type: "string"
                description: "File path"
                required: true
              max_attempts:
                type: "number"
                description: "Maximum attempts"
                required: false
                default: 5
            default_state:
              state:
                attempt_number: 0
                success: false
                results: {}
            state_schema:
              computed:
                attempts_remaining:
                  from: ["raw.attempt_number", "{{ max_attempts }}"]
                  transform: "input[1] - input[0]"
                is_complete:
                  from: "raw.success"
                  transform: "input === true"
            steps:
              - id: "process_step"
                type: "mcp_call"
                tool: "test_tool"
                parameters:
                  input: "{{ file_path }}"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify sub-agent task was parsed
        assert "complete_task" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["complete_task"]
        
        # Verify both fields are present
        assert hasattr(task, 'default_state')
        assert hasattr(task, 'state_schema')
        
        # Verify default_state
        assert task.default_state["state"]["attempt_number"] == 0
        assert task.default_state["state"]["success"] is False
        assert isinstance(task.default_state["state"]["results"], dict)
        
        # Verify state_schema
        computed = task.state_schema.computed
        assert "attempts_remaining" in computed
        assert "is_complete" in computed
        
        # Verify computed field with template reference
        attempts_field = computed["attempts_remaining"]
        assert attempts_field["from"] == ["raw.attempt_number", "{{ max_attempts }}"]

    def test_parse_sub_agent_task_without_new_fields(self):
        """Test parsing sub-agent task without default_state or state_schema (backward compatibility)."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          simple_task:
            description: "Simple sub-agent task"
            inputs:
              input_param:
                type: "string"
                description: "Input parameter"
                required: true
            steps:
              - id: "simple_step"
                type: "user_message"
                message: "Simple test"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify sub-agent task was parsed
        assert "simple_task" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["simple_task"]
        
        # Verify fields have default values
        assert hasattr(task, 'default_state')
        assert hasattr(task, 'state_schema')
        assert task.default_state == {}  # Default empty dict
        assert task.state_schema is not None  # Default StateSchema

    def test_parse_sub_agent_task_with_empty_fields(self):
        """Test parsing sub-agent task with explicitly empty default_state and state_schema."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          empty_task:
            description: "Task with empty fields"
            inputs: {}
            default_state: {}
            state_schema: {}
            steps:
              - id: "empty_step"
                type: "user_message"
                message: "Empty test"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify sub-agent task was parsed
        assert "empty_task" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["empty_task"]
        
        # Verify empty fields are handled correctly
        assert task.default_state == {}
        assert task.state_schema is not None
        assert task.state_schema.computed == {}

    def test_parse_sub_agent_task_complex_state_schema(self):
        """Test parsing sub-agent task with complex state_schema including raw and state tiers."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          complex_task:
            description: "Task with complex state schema"
            inputs:
              file_path:
                type: "string"
                description: "File path"
                required: true
            default_state:
              state:
                counters:
                  attempts: 0
                  successes: 0
                  failures: 0
              state:
                metadata:
                  created_at: "2024-01-01"
            state_schema:
              state:
                counters:
                  type: "object"
                  description: "Counter values"
              computed:
                total_attempts:
                  from: "raw.counters"
                  transform: "input.attempts + input.successes + input.failures"
                success_rate:
                  from: ["raw.counters.successes", "computed.total_attempts"]
                  transform: "input[1] > 0 ? input[0] / input[1] : 0"
              state:
                metadata:
                  type: "object"
                  description: "Task metadata"
            steps:
              - id: "complex_step"
                type: "user_message"
                message: "Complex test"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify sub-agent task was parsed
        assert "complex_task" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["complex_task"]
        
        # Verify complex default_state structure
        assert "raw" in task.default_state
        assert "state" in task.default_state
        assert task.default_state["state"]["counters"]["attempts"] == 0
        assert task.default_state["state"]["metadata"]["created_at"] == "2024-01-01"
        
        # Verify complex state_schema structure
        assert hasattr(task.state_schema, 'raw')
        assert hasattr(task.state_schema, 'computed')
        assert hasattr(task.state_schema, 'state')
        
        # Verify computed fields
        computed = task.state_schema.computed
        assert "total_attempts" in computed
        assert "success_rate" in computed
        
        # Verify raw schema
        assert "counters" in task.state_schema.raw
        assert task.state_schema.raw["counters"]["type"] == "object"

    def test_parse_invalid_sub_agent_task_state_schema(self):
        """Test error handling for invalid state_schema in sub-agent task."""
        yaml_content = """
        name: "test:workflow"
        description: "Test workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          invalid_task:
            description: "Task with invalid state schema"
            inputs: {}
            state_schema: "invalid_string_instead_of_dict"
            steps:
              - id: "invalid_step"
                type: "user_message"
                message: "Invalid test"
        """
        
        # This should raise a validation error for invalid state_schema
        with pytest.raises(WorkflowValidationError):
            self.loader._parse_yaml(yaml_content, "<test>", "test")

    def test_real_world_sub_agent_task_parsing(self):
        """Test parsing a real-world sub-agent task similar to the code-standards:enforce workflow."""
        yaml_content = """
        name: "test:code-standards"
        description: "Code standards enforcement workflow"
        version: "1.0.0"
        default_state:
          state: {}
        state_schema:
          state: {}
          computed: {}
        inputs: {}
        steps: []
        sub_agent_tasks:
          enforce_standards_on_file:
            description: "Enforce code standards on a single file"
            inputs:
              file_path:
                type: "string"
                description: "Path to the file to process"
                required: true
              max_attempts:
                type: "number"
                description: "Maximum fix attempts"
                required: false
                default: 10
            default_state:
              state:
                attempt_number: 0
                success: false
                last_error: ""
                step_results:
                  hints: null
                  lint: null
                  typescript: null
            state_schema:
              computed:
                is_typescript_file:
                  from: "{{ file_path }}"
                  transform: "input.endsWith('.ts') || input.endsWith('.tsx')"
                hints_completed:
                  from: "raw.step_results"
                  transform: "input.hints !== null && input.hints.success === true"
                lint_completed:
                  from: "raw.step_results"
                  transform: "input.lint !== null && input.lint.success === true"
                typescript_completed:
                  from: ["raw.step_results", "computed.is_typescript_file"]
                  transform: "!input[1] || (input[0].typescript !== null && input[0].typescript.success === true)"
                all_steps_completed:
                  from: ["computed.hints_completed", "computed.lint_completed", "computed.typescript_completed"]
                  transform: "input[0] && input[1] && input[2]"
                can_continue:
                  from: ["raw.attempt_number", "{{ max_attempts }}", "computed.all_steps_completed"]
                  transform: "input[0] < input[1] && !input[2]"
            steps:
              - id: "standards_loop"
                type: "while_loop"
                condition: "{{ computed.can_continue }}"
                max_iterations: 10
                body:
                  - id: "increment_attempt"
                    type: "state_update"
                    path: "raw.attempt_number"
                    value: "{{ state.attempt_number + 1 }}"
                  - id: "process_file"
                    type: "user_message"
                    message: "Processing {{ file_path }} (attempt {{ state.attempt_number }})"
        """
        
        workflow_def = self.loader._parse_yaml(yaml_content, "<test>", "test")
        
        # Verify the complex sub-agent task was parsed correctly
        assert "enforce_standards_on_file" in workflow_def.sub_agent_tasks
        task = workflow_def.sub_agent_tasks["enforce_standards_on_file"]
        
        # Verify inputs
        assert "file_path" in task.inputs
        assert "max_attempts" in task.inputs
        assert task.inputs["max_attempts"].default == 10
        
        # Verify default_state structure
        assert task.default_state["state"]["attempt_number"] == 0
        assert task.default_state["state"]["step_results"]["hints"] is None
        
        # Verify computed fields
        computed = task.state_schema.computed
        expected_fields = [
            "is_typescript_file",
            "hints_completed", 
            "lint_completed",
            "typescript_completed",
            "all_steps_completed",
            "can_continue"
        ]
        for field in expected_fields:
            assert field in computed, f"Missing computed field: {field}"
        
        # Verify can_continue field specifically (this was the problematic one)
        can_continue = computed["can_continue"]
        assert can_continue["from"] == ["raw.attempt_number", "{{ max_attempts }}", "computed.all_steps_completed"]
        assert "input[0] < input[1] && !input[2]" in can_continue["transform"]
        
        # Verify steps including while_loop
        assert len(task.steps) == 1
        assert task.steps[0].type == "while_loop"
        assert task.steps[0].definition["condition"] == "{{ computed.can_continue }}"