"""Tests for workflow loading and YAML parsing."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from aromcp.workflow_server.workflow.loader import WorkflowLoader, WorkflowParser
from aromcp.workflow_server.workflow.models import WorkflowNotFoundError, WorkflowValidationError


class TestWorkflowLoader:
    """Test workflow loading with name resolution."""

    def test_workflow_name_resolution_project_first(self):
        """Test that project workflows take precedence over global ones."""
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
  - type: "user_message"
    message: "Project workflow step"
"""
            global_content = """
name: "test:workflow"
description: "Global workflow"
version: "1.0.0"

steps:
  - type: "user_message"
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

    def test_workflow_name_resolution_global_fallback(self):
        """Test fallback to global workflow when project doesn't exist."""
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
  - type: "user_message"
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

    def test_workflow_not_found(self):
        """Test error when workflow doesn't exist in either location."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)

                with pytest.raises(WorkflowNotFoundError) as exc:
                    loader.load("missing:workflow")

                assert "missing:workflow" in str(exc.value)
                assert ".aromcp/workflows/missing:workflow.yaml" in str(exc.value)

    def test_yaml_parsing_basic(self):
        """Test basic YAML workflow definition parsing."""
        yaml_content = """
name: "test:simple"
description: "Test workflow"
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
    value: 10
  - type: "user_message"
    message: "Hello {{ name }}, counter is {{ counter }}"
"""

        workflow = WorkflowParser.parse(yaml_content)

        assert workflow.name == "test:simple"
        assert workflow.description == "Test workflow"
        assert workflow.version == "1.0.0"
        assert workflow.default_state["raw"]["counter"] == 0
        assert len(workflow.steps) == 2
        assert workflow.steps[0].type == "state_update"
        assert workflow.steps[1].type == "user_message"
        assert "name" in workflow.inputs
        assert workflow.inputs["name"].type == "string"
        assert workflow.inputs["name"].required is True

    def test_yaml_parsing_with_computed_fields(self):
        """Test parsing of computed field definitions."""
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
  - type: "user_message"
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

    def test_yaml_parsing_validation_errors(self):
        """Test validation of required fields."""
        # Missing name
        invalid_yaml = """
description: "Test workflow"
version: "1.0.0"
"""
        with pytest.raises(WorkflowValidationError) as exc:
            WorkflowParser.parse(invalid_yaml)
        assert "Missing required fields" in str(exc.value)

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
        assert "Invalid YAML syntax" in str(exc.value)

    def test_steps_parsing_with_ids(self):
        """Test step parsing with explicit and generated IDs."""
        yaml_content = """
name: "test:steps"
description: "Test step parsing"
version: "1.0.0"

steps:
  - id: "custom_id"
    type: "state_update"
    path: "raw.value"
    value: 5

  - type: "user_message"
    message: "Auto-generated ID"
"""

        workflow = WorkflowParser.parse(yaml_content)

        assert len(workflow.steps) == 2
        assert workflow.steps[0].id == "custom_id"
        assert workflow.steps[1].id == "step_1"  # Auto-generated

        # Check that definition excludes id and type
        assert "path" in workflow.steps[0].definition
        assert "value" in workflow.steps[0].definition
        assert "id" not in workflow.steps[0].definition
        assert "type" not in workflow.steps[0].definition

    def test_list_available_workflows(self):
        """Test listing workflows from both project and global locations."""
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
  - type: "user_message"
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
  - type: "user_message"
    message: "Global workflow step"
"""
            global_file.write_text(global_content)

            # Create workflow that exists in both (project should take precedence)
            both_project = project_workflows / "both:workflow.yaml"
            both_global = global_workflows / "both:workflow.yaml"
            both_project.write_text("""
name: "both:workflow"
description: "Project version"
version: "1.0.0"

steps:
  - type: "user_message"
    message: "Both workflow project step"
""")
            both_global.write_text("""
name: "both:workflow"
description: "Global version"
version: "2.0.0"

steps:
  - type: "user_message"
    message: "Both workflow global step"
""")

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

    def test_list_workflows_project_only(self):
        """Test listing workflows with global disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create both directories with workflows
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            global_workflows = Path(temp_dir) / "global" / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)
            global_workflows.mkdir(parents=True)

            project_file = project_workflows / "project:workflow.yaml"
            global_file = global_workflows / "global:workflow.yaml"

            project_file.write_text("""
name: "project:workflow"
description: "Project workflow"
version: "1.0.0"

steps:
  - type: "user_message"
    message: "Project workflow step"
""")
            global_file.write_text("""
name: "global:workflow"
description: "Global workflow"
version: "1.0.0"

steps:
  - type: "user_message"
    message: "Global workflow step"
""")

            with patch("os.path.expanduser") as mock_expanduser:
                mock_expanduser.return_value = str(Path(temp_dir) / "global")

                loader = WorkflowLoader(project_root=temp_dir)
                workflows = loader.list_available_workflows(include_global=False)

                # Should only have project workflow
                assert len(workflows) == 1
                assert workflows[0]["name"] == "project:workflow"
                assert workflows[0]["source"] == "project"

    def test_validation_called_during_load(self):
        """Test that validation is performed when loading workflows."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)
            
            # Create workflow with invalid step type
            invalid_workflow_file = project_workflows / "invalid:workflow.yaml"
            invalid_workflow_file.write_text("""
name: "invalid:workflow"
description: "Workflow with invalid step"
version: "1.0.0"
steps:
  - type: "invalid_step_type"
    message: "This should fail validation"
""")
            
            loader = WorkflowLoader(project_root=temp_dir)
            
            with pytest.raises(WorkflowValidationError) as exc:
                loader.load("invalid:workflow")
            
            assert "Workflow validation failed" in str(exc.value)
            assert "invalid type: invalid_step_type" in str(exc.value)
    
    def test_validation_with_complex_errors(self):
        """Test that multiple validation errors are reported."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_workflows = Path(temp_dir) / ".aromcp" / "workflows"
            project_workflows.mkdir(parents=True)
            
            # Create workflow with multiple errors
            workflow_file = project_workflows / "multi-error:workflow.yaml"
            workflow_file.write_text("""
name: "multi-error"  # Missing namespace
description: "Workflow with multiple errors"
version: "not.semantic"  # Bad version
steps:
  - type: "state_update"
    # Missing required fields: path and value
  - type: "user_message"
    # Missing required field: message
  - type: "invalid_step_type"
    message: "Invalid step"
""")
            
            loader = WorkflowLoader(project_root=temp_dir)
            
            with pytest.raises(WorkflowValidationError) as exc:
                loader.load("multi-error:workflow")
            
            error_msg = str(exc.value)
            assert "Workflow validation failed" in error_msg
            assert "missing 'path' field" in error_msg
            assert "missing 'message' field" in error_msg
            assert "invalid type: invalid_step_type" in error_msg
            # Should also have warnings
            assert "namespace:name" in error_msg
            assert "semantic versioning" in error_msg
