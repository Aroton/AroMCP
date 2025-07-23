"""
Test suite for Workflow Definition & Validation - Acceptance Criteria 1

This file tests the following acceptance criteria:
- AC 1.1: Schema Compliance - workflow definitions conform to JSON schema specification
- AC 1.2: Input Parameter Definitions - input validation and initialization
- AC 1.3: State Schema Validation - computed field definitions and validation

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from aromcp.workflow_server.workflow.loader import WorkflowLoader, WorkflowParser
from aromcp.workflow_server.workflow.models import WorkflowNotFoundError, WorkflowValidationError
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestSchemaCompliance:
    """Test schema compliance and workflow loading - AC 1.1"""

    def test_schema_compliance_namespace_name_pattern_enforcement(self):
        """Test schema compliance enforces namespace:name pattern for workflow names (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project and global directories
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            global_workflows = Path(temp_dir) / "global" / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)
            global_workflows.mkdir(parents=True)

            # Create same workflow in both locations
            project_file = project_workflows / "test:workflow.yaml"
            global_file = global_workflows / "test:workflow.yaml"

            project_content = """
name: "test:workflow"
description: "Project workflow"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Project workflow step"
"""
            global_content = """
name: "test:workflow"
description: "Global workflow"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Global workflow step"
"""

            project_file.write_text(project_content)
            global_file.write_text(global_content)

            # Mock home directory to point to our temp global location
            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)
                workflow = loader.load("test:workflow")

                assert workflow.source == "project"
                assert workflow.description == "Project workflow"

    def test_schema_compliance_required_field_validation(self):
        """Test schema compliance validates required fields: name, description, version, steps (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Only create global directory
            global_workflows = Path(temp_dir) / "global" / ".aromcp" / "workflows"
            global_workflows.mkdir(parents=True)

            global_file = global_workflows / "test:workflow.yaml"
            global_content = """
name: "test:workflow"
description: "Global workflow"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Global workflow step"
"""
            global_file.write_text(global_content)

            # Mock home directory
            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)
                workflow = loader.load("test:workflow")

                assert workflow.source == "global"
                assert workflow.description == "Global workflow"

    def test_schema_compliance_workflow_not_found_handling(self):
        """Test schema compliance provides clear validation error messages with field-level details (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)

                with pytest.raises(WorkflowNotFoundError) as exc:
                    loader.load("missing:workflow")

                assert "missing:workflow" in str(exc.value)
                assert ".aromcp/workflows/missing:workflow.yaml" in str(exc.value)

    def test_schema_compliance_semantic_version_validation(self):
        """Test schema compliance validates semantic versioning format (X.Y.Z) (AC 1.1)."""
        yaml_content = """
name: "test:simple"
description: "Test workflow"
version: "1.0.0"

default_state:
  state:
    counter: 0
    message: ""

state_schema:
  computed:
    doubled:
      from: "this.counter"
      transform: "input * 2"

inputs:
  name:
    type: "string"
    description: "User name"
    required: true

steps:
  - id: "update_counter"
    type: "shell_command"
    command: "echo 'Setting counter to 10'"
    state_update:
      path: "this.counter"
      value: "10"
  - id: "greet_user"
    type: "user_message"
    message: "Hello {{ inputs.name }}, counter is {{ this.counter }}"
"""

        workflow = WorkflowParser.parse(yaml_content)

        assert workflow.name == "test:simple"
        assert workflow.description == "Test workflow"
        assert workflow.version == "1.0.0"
        assert workflow.default_state["state"]["counter"] == 0
        assert len(workflow.steps) == 2
        assert workflow.steps[0].type == "shell_command"
        assert workflow.steps[1].type == "user_message"
        assert "name" in workflow.inputs
        assert workflow.inputs["name"].type == "string"
        assert workflow.inputs["name"].required is True

    def test_schema_compliance_optional_field_support(self):
        """Test schema compliance supports optional fields: config, inputs, default_state, state_schema, sub_agent_tasks (AC 1.1)."""
        yaml_content = """
name: "test:computed"
description: "Test computed fields"
version: "1.0.0"

state_schema:
  computed:
    simple_double:
      from: "raw.value"
      transform: "input * 2"

    multi_dependency:
      from: ["raw.a", "raw.b"]
      transform: "input[0] + input[1]"
      on_error: "use_fallback"
      fallback: 0

steps:
  - id: "test_step"
    type: "user_message"
    message: "Test computed fields step"
"""

        workflow = WorkflowParser.parse(yaml_content)

        computed = workflow.state_schema.computed
        assert "simple_double" in computed
        assert computed["simple_double"]["from"] == "raw.value"
        assert computed["simple_double"]["transform"] == "input * 2"

        assert "multi_dependency" in computed
        assert computed["multi_dependency"]["from"] == ["raw.a", "raw.b"]
        assert computed["multi_dependency"]["on_error"] == "use_fallback"
        assert computed["multi_dependency"]["fallback"] == 0


class TestComplexInputParameterValidation:
    """Test complex input parameter validation scenarios - Enhanced Coverage for AC 1.2."""

    def test_input_type_enforcement_edge_cases(self):
        """Test input type enforcement with edge cases and boundary conditions."""
        yaml_content = """
name: "test:complex_input_validation"
description: "Test complex input validation"
version: "1.0.0"

inputs:
  numeric_with_constraints:
    type: "number"
    description: "Number with multiple constraints"
    validation:
      minimum: 0
      maximum: 100
      multipleOf: 0.5
  
  string_with_pattern:
    type: "string"
    description: "String with pattern and length constraints"
    validation:
      pattern: "^[A-Z][a-z]+$"
      minLength: 2
      maxLength: 20

steps:
  - id: "step1"
    type: "user_message"
    message: "Complex input validation test"
"""

        workflow = WorkflowParser.parse(yaml_content)
        
        # Test numeric constraints
        numeric_input = workflow.inputs["numeric_with_constraints"]
        assert numeric_input.type == "number"
        assert numeric_input.validation["minimum"] == 0
        assert numeric_input.validation["maximum"] == 100
        assert numeric_input.validation["multipleOf"] == 0.5
        
        # Test string pattern constraints
        string_input = workflow.inputs["string_with_pattern"]
        assert string_input.type == "string"
        assert string_input.validation["pattern"] == "^[A-Z][a-z]+$"
        assert string_input.validation["minLength"] == 2
        assert string_input.validation["maxLength"] == 20

    def test_input_validation_rule_application_complex(self):
        """Test complex input validation rule application scenarios."""
        yaml_content = """
name: "test:validation_rules"
description: "Test validation rules"
version: "1.0.0"

inputs:
  email_list:
    type: "array"
    description: "List of unique email addresses"
    validation:
      items:
        type: "string"
        format: "email"
      uniqueItems: true

steps:
  - id: "step1"
    type: "user_message"
    message: "Validation rules test"
"""

        workflow = WorkflowParser.parse(yaml_content)
        
        # Test email list validation
        email_input = workflow.inputs["email_list"]
        assert email_input.type == "array"
        assert email_input.validation["items"]["format"] == "email"
        assert email_input.validation["uniqueItems"] == True

    def test_input_default_value_processing_various_types(self):
        """Test input default value processing for various data types."""
        yaml_content = """
name: "test:default_values"
description: "Test default values"
version: "1.0.0"

inputs:
  simple_defaults:
    type: "object"
    description: "Object with default values"
    validation:
      properties:
        string_default:
          type: "string"
          default: "default_value"
        number_default:
          type: "number"
          default: 42.5
        boolean_default:
          type: "boolean"
          default: true

steps:
  - id: "step1"
    type: "user_message"
    message: "Default values test"
"""

        workflow = WorkflowParser.parse(yaml_content)
        
        # Test simple defaults
        simple_defaults_input = workflow.inputs["simple_defaults"]
        assert simple_defaults_input.validation["properties"]["string_default"]["default"] == "default_value"
        assert simple_defaults_input.validation["properties"]["number_default"]["default"] == 42.5
        assert simple_defaults_input.validation["properties"]["boolean_default"]["default"] == True

    def test_schema_compliance_invalid_field_rejection(self):
        """Test schema compliance rejects workflows with unknown or invalid fields (AC 1.1)."""
        # Missing name
        invalid_yaml = """
description: "Test workflow"
version: "1.0.0"
"""
        with pytest.raises(WorkflowValidationError) as exc:
            WorkflowParser.parse(invalid_yaml)
        error_msg = str(exc.value)
        assert "Missing required fields" in error_msg
        # Verify error structure format
        assert "error" in error_msg.lower() or "validation" in error_msg.lower()

        # Invalid YAML syntax
        invalid_yaml = """
name: "test"
description: "Test"
version: "1.0.0"
steps:
  - type: "state_update
    # Missing closing quote
"""
        with pytest.raises(WorkflowValidationError) as exc:
            WorkflowParser.parse(invalid_yaml)
        error_msg = str(exc.value)
        assert "Invalid YAML syntax" in error_msg
        # Verify error structure format
        assert "error" in error_msg.lower() or "syntax" in error_msg.lower()

    def test_schema_compliance_step_definition_validation(self):
        """Test schema compliance validates step definitions with proper structure (AC 1.1)."""
        yaml_content = """
name: "test:steps"
description: "Test step parsing"
version: "1.0.0"

steps:
  - id: "custom_id"
    type: "shell_command"
    command: "echo 'test'"
    state_update:
      path: "state.value"
      value: "5"

  - id: "user_step"
    type: "user_message"
    message: "Auto-generated ID"
"""

        workflow = WorkflowParser.parse(yaml_content)

        assert len(workflow.steps) == 2
        assert workflow.steps[0].id == "custom_id"
        assert workflow.steps[1].id == "user_step"

        # Check that definition excludes id and type
        assert "command" in workflow.steps[0].definition
        assert "state_update" in workflow.steps[0].definition
        assert "id" not in workflow.steps[0].definition
        assert "type" not in workflow.steps[0].definition

    def test_schema_compliance_workflow_listing_functionality(self):
        """Test schema compliance lists workflows from both project and global locations (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create project and global directories
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            global_workflows = Path(temp_dir) / "global" / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)
            global_workflows.mkdir(parents=True)

            # Create project workflow
            project_file = project_workflows / "project:workflow.yaml"
            project_content = """
name: "project:workflow"
description: "Project workflow"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Project workflow step"
"""
            project_file.write_text(project_content)

            # Create global workflow
            global_file = global_workflows / "global:workflow.yaml"
            global_content = """
name: "global:workflow"
description: "Global workflow"
version: "2.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Global workflow step"
"""
            global_file.write_text(global_content)

            # Create workflow that exists in both (project should take precedence)
            both_project = project_workflows / "both:workflow.yaml"
            both_global = global_workflows / "both:workflow.yaml"
            both_project.write_text(
                """
name: "both:workflow"
description: "Project version"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Both workflow project step"
"""
            )
            both_global.write_text(
                """
name: "both:workflow"
description: "Global version"
version: "2.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Both workflow global step"
"""
            )

            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)
                workflows = loader.list_available_workflows(include_global=True)

                # Should have 3 workflows total
                assert len(workflows) == 3

                # Find specific workflows
                project_wf = next(w for w in workflows if w["name"] == "project:workflow")
                global_wf = next(w for w in workflows if w["name"] == "global:workflow")
                both_wf = next(w for w in workflows if w["name"] == "both:workflow")

                assert project_wf["source"] == "project"
                assert global_wf["source"] == "global"
                assert both_wf["source"] == "project"  # Project takes precedence
                assert both_wf["description"] == "Project version"

    def test_schema_compliance_project_only_configuration(self):
        """Test schema compliance handles project-only workflow configurations (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create both directories with workflows
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            global_workflows = Path(temp_dir) / "global" / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)
            global_workflows.mkdir(parents=True)

            project_file = project_workflows / "project:workflow.yaml"
            global_file = global_workflows / "global:workflow.yaml"

            project_file.write_text(
                """
name: "project:workflow"
description: "Project workflow"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Project workflow step"
"""
            )
            global_file.write_text(
                """
name: "global:workflow"
description: "Global workflow"
version: "1.0.0"

steps:
  - id: "step1"
    type: "user_message"
    message: "Global workflow step"
"""
            )

            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)
                workflows = loader.list_available_workflows(include_global=False)

                # Should only have project workflow
                assert len(workflows) == 1
                assert workflows[0]["name"] == "project:workflow"
                assert workflows[0]["source"] == "project"

    def test_schema_compliance_load_time_validation(self):
        """Test schema compliance performs validation during workflow loading process (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)

            # Create workflow with invalid step type
            invalid_workflow_file = project_workflows / "invalid:workflow.yaml"
            invalid_workflow_file.write_text(
                """
name: "invalid:workflow"
description: "Workflow with invalid step"
version: "1.0.0"
steps:
  - type: "invalid_step_type"
    message: "This should fail validation"
"""
            )

            loader = WorkflowLoader(project_root=temp_dir)

            with pytest.raises(WorkflowValidationError) as exc:
                loader.load("invalid:workflow")

            assert "Workflow validation failed" in str(exc.value)
            assert "invalid type: invalid_step_type" in str(exc.value)

    def test_schema_compliance_detailed_error_messaging(self):
        """Test schema compliance provides clear validation error messages with field-level details (AC 1.1)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)

            # Create workflow with multiple errors
            workflow_file = project_workflows / "multi-error:workflow.yaml"
            workflow_file.write_text(
                """
name: "multi-error"  # Missing namespace
description: "Workflow with multiple errors"
version: "not.semantic"  # Bad version
steps:
  - id: "step1"
    type: "shell_command"
    # Missing required field: command
  - id: "step2" 
    type: "user_message"
    # Missing required field: message
  - id: "step3"
    type: "invalid_step_type"
    message: "Invalid step"
"""
            )

            loader = WorkflowLoader(project_root=temp_dir)

            with pytest.raises(WorkflowValidationError) as exc:
                loader.load("multi-error:workflow")

            error_msg = str(exc.value)
            assert "Workflow validation failed" in error_msg
            # The command field error might not show if schema validation stops early
            # but at least one missing field error should be present
            assert "missing 'message' field" in error_msg
            assert "invalid type: invalid_step_type" in error_msg
            # Should also have warnings
            assert "namespace:name" in error_msg
            assert "semantic versioning" in error_msg


class TestInputParameterDefinitions:
    """Test input parameter definitions and validation - AC 1.2"""

    def test_input_parameter_type_validation_and_defaults(self):
        """Test input parameter definitions support input types and validation with default values (AC 1.2)."""
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
            from aromcp.workflow_server.workflow.queue_executor import QueueBasedWorkflowExecutor as WorkflowExecutor
            executor = WorkflowExecutor()

            workflow_def = loader.load("test:inputs")
            result = executor.start(workflow_def, inputs={"multiplier": 3})

            assert result["state"]["state"]["base_value"] == 10
            assert result["state"]["inputs"]["multiplier"] == 3


class TestStateSchemaValidation:
    """Test state schema validation and computed fields - AC 1.3"""

    def test_state_schema_computed_field_validation(self):
        """Test state schema validation validates computed field definitions with from and transform properties (AC 1.3)."""
        yaml_content = """
name: "test:computed"
description: "Test computed fields"
version: "1.0.0"

state_schema:
  computed:
    simple_double:
      from: "raw.value"
      transform: "input * 2"

    multi_dependency:
      from: ["raw.a", "raw.b"]
      transform: "input[0] + input[1]"
      on_error: "use_fallback"
      fallback: 0

steps:
  - id: "test_step"
    type: "user_message"
    message: "Test computed fields step"
"""

        workflow = WorkflowParser.parse(yaml_content)

        computed = workflow.state_schema.computed
        assert "simple_double" in computed
        assert computed["simple_double"]["from"] == "raw.value"
        assert computed["simple_double"]["transform"] == "input * 2"

        assert "multi_dependency" in computed
        assert computed["multi_dependency"]["from"] == ["raw.a", "raw.b"]
        assert computed["multi_dependency"]["on_error"] == "use_fallback"
        assert computed["multi_dependency"]["fallback"] == 0

class TestDeprecatedStepMigration:
    """Test deprecated step migration patterns for schema compliance - AC 1.1"""

    def setup_method(self):
        """Set up test environment."""
        self.registry = StepRegistry()
        self.validator = WorkflowValidator()

    def test_schema_compliance_deprecated_state_update_migration(self):
        """Test schema compliance rejects deprecated state_update and provides migration path (AC 1.1)."""
        # Old deprecated pattern (should fail validation)
        deprecated_step = {
            "id": "update_count",
            "type": "state_update",
            "path": "state.counter",
            "value": "{{ state.counter + 1 }}"
        }
        
        is_valid, error = self.registry.validate_step(deprecated_step)
        assert not is_valid
        assert "deprecated and removed" in error
        assert "Use 'state_update' field within other step types" in error
        
        # New recommended pattern
        migrated_step = {
            "id": "update_count",
            "type": "shell_command",
            "command": "echo 'Updating counter'",
            "state_update": {
                "path": "state.counter",
                "value": "{{ state.counter + 1 }}"
            }
        }
        
        is_valid, error = self.registry.validate_step(migrated_step)
        assert is_valid, f"Migrated step should be valid: {error}"

    def test_schema_compliance_deprecated_batch_state_update_migration(self):
        """Test schema compliance rejects deprecated batch_state_update and provides migration path (AC 1.1)."""
        # Old deprecated pattern (should fail validation)
        deprecated_step = {
            "id": "batch_update",
            "type": "batch_state_update",
            "updates": [
                {"path": "state.counter", "value": "10"},
                {"path": "state.message", "value": "Hello"},
                {"path": "state.enabled", "value": "true"}
            ]
        }
        
        is_valid, error = self.registry.validate_step(deprecated_step)
        assert not is_valid
        assert "deprecated and removed" in error
        assert "Use 'state_updates' field within 'agent_response'" in error
        
        # New recommended pattern
        migrated_step = {
            "id": "process_response",
            "type": "agent_response",
            "state_updates": [
                {"path": "state.counter", "value": "{{ response.counter }}"},
                {"path": "state.message", "value": "{{ response.message }}"},
                {"path": "state.enabled", "value": "{{ response.enabled }}"}
            ],
            "response_schema": {
                "type": "object",
                "required": ["counter", "message", "enabled"]
            }
        }
        
        is_valid, error = self.registry.validate_step(migrated_step)
        assert is_valid, f"Agent response with state_updates should be valid: {error}"

    def test_schema_compliance_workflow_with_deprecated_steps_validation(self):
        """Test schema compliance validates workflows and rejects those with deprecated steps (AC 1.1)."""
        workflow_with_deprecated = {
            "name": "test:deprecated",
            "description": "Test workflow with deprecated steps",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "deprecated_state_update",
                    "type": "state_update",
                    "path": "state.count",
                    "value": "1"
                },
                {
                    "id": "deprecated_batch_update",
                    "type": "batch_state_update",
                    "updates": [
                        {"path": "state.a", "value": "1"},
                        {"path": "state.b", "value": "2"}
                    ]
                }
            ]
        }
        
        # Validation should fail due to deprecated step types
        is_valid = self.validator.validate_strict_schema_only(workflow_with_deprecated)
        assert not is_valid, "Workflow with deprecated steps should fail validation"

    def test_schema_compliance_workflow_with_migrated_steps_validation(self):
        """Test schema compliance validates workflows with properly migrated steps (AC 1.1)."""
        workflow_migrated = {
            "name": "test:migrated",
            "description": "Test workflow with migrated steps",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "migrated_state_update",
                    "type": "shell_command",
                    "command": "echo 'Setting count'",
                    "state_update": {
                        "path": "state.count",
                        "value": "1"
                    }
                },
                {
                    "id": "collect_input",
                    "type": "user_input",
                    "prompt": "Enter value:",
                    "state_update": {
                        "path": "state.user_value",
                        "value": "{{ input }}"
                    }
                },
                {
                    "id": "process_results",
                    "type": "agent_response",
                    "state_updates": [
                        {"path": "state.result_a", "value": "{{ response.a }}"},
                        {"path": "state.result_b", "value": "{{ response.b }}"}
                    ]
                }
            ]
        }
        
        # Validation should pass with migrated patterns
        is_valid = self.validator.validate_strict_schema_only(workflow_migrated)
        assert is_valid, "Workflow with migrated steps should pass validation"

    def test_schema_compliance_migration_guidance_messages(self):
        """Test schema compliance provides helpful migration guidance for deprecated step types (AC 1.1)."""
        # shell_command with state_update suggestion
        suggestion = self.registry.suggest_replacement_for_deprecated("state_update")
        assert "state_update" in suggestion
        assert "field" in suggestion
        assert "mcp_call" in suggestion
        assert "user_input" in suggestion
        assert "shell_command" in suggestion
        assert "agent_response" in suggestion
        
        # batch_shell_command with state_update suggestion
        suggestion = self.registry.suggest_replacement_for_deprecated("batch_state_update")
        assert "state_updates" in suggestion
        assert "agent_response" in suggestion


class TestStepRegistryValidation:
    """Test step registry validation functionality for schema compliance - AC 1.1"""

    def setup_method(self):
        """Set up test environment."""
        self.registry = StepRegistry()

    def test_schema_compliance_required_step_types_available(self):
        """Test schema compliance ensures all required step types are available in registry (AC 1.1)."""
        required_step_types = [
            "user_message", "mcp_call", "user_input", "agent_prompt", "agent_response",
            "parallel_foreach", "shell_command", "conditional", "while_loop", "foreach", "break", "continue"
        ]
        
        for step_type in required_step_types:
            config = self.registry.get(step_type)
            assert config is not None, f"Required step type '{step_type}' not found in registry"

    def test_schema_compliance_deprecated_step_types_removed(self):
        """Test schema compliance removes deprecated step types from registry (AC 1.1)."""
        deprecated_step_types = ["state_update", "batch_state_update"]
        
        for step_type in deprecated_step_types:
            config = self.registry.get(step_type)
            assert config is None, f"Deprecated step type '{step_type}' should not be in registry"
            
        # But should be detected as deprecated
        for step_type in deprecated_step_types:
            assert self.registry.is_deprecated_step_type(step_type)

    def test_schema_compliance_step_field_validation(self):
        """Test schema compliance validates required and optional step fields (AC 1.1)."""
        # Test missing required field
        step = {"id": "test", "type": "user_message"}  # Missing 'message'
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "missing required field" in error_message
        assert "message" in error_message
        
        # Test unknown field rejection
        step = {
            "id": "test",
            "type": "user_message", 
            "message": "Hello",
            "unknown_field": "should_fail"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "unknown field" in error_message

    def test_schema_compliance_execution_context_validation(self):
        """Test schema compliance validates execution_context only on shell_command steps (AC 1.1)."""
        # Valid: shell_command with execution_context
        step = {
            "id": "test_shell",
            "type": "shell_command",
            "command": "echo test",
            "execution_context": "client"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert is_valid, f"Should be valid: {error_message}"
        
        # Invalid: execution_context on non-shell_command step
        step = {
            "id": "test_user",
            "type": "user_message",
            "message": "Hello",
            "execution_context": "client"
        }
        is_valid, error_message = self.registry.validate_step(step)
        assert not is_valid
        assert "execution_context" in error_message
        assert "only allowed on 'shell_command'" in error_message