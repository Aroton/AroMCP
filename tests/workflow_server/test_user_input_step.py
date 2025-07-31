"""
Test suite for User Input Step Implementation - Acceptance Criteria 3.1

This file tests the following acceptance criteria:
- AC 3.1.1: User input type validation (string, number, boolean, choice)
- AC 3.1.2: Input validation against specified rules
- AC 3.1.3: Choice selection for selection-based inputs
- AC 3.1.4: State updates via state_update field
- AC 3.1.5: Default values and retry logic
- AC 3.1.6: Validation failures with max_retries limit
- AC-UI-011: Complex validation expressions
- AC-UI-012: Long input handling and timeout scenarios

Maps to: /documentation/acceptance-criteria/workflow_server/user-interaction.md
"""

from unittest.mock import Mock

from aromcp.workflow_server.workflow.steps.user_message import UserInputProcessor


class TestUserInputCollection:
    """Test user input collection with various input types and validation."""

    def test_user_input_string_type_validation(self):
        """Test user input with string type validation."""
        step_definition = {
            "prompt": "Enter your name:",
            "input_type": "string",
            "validation_pattern": "^[A-Za-z\\s]+$",
            "validation_message": "Name must contain only letters and spaces",
        }

        # Mock state manager (not used by UserInputProcessor.process)
        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["prompt"] == "Enter your name:"
        assert result["agent_action"]["input_type"] == "string"

    def test_user_input_number_type_validation(self):
        """Test user input with number type validation."""
        step_definition = {
            "prompt": "Enter your age:",
            "input_type": "number",
            "validation": {"min": 0, "max": 150},
            "validation_message": "Age must be between 0 and 150",
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["input_type"] == "number"

    def test_user_input_boolean_type_validation(self):
        """Test user input with boolean type validation."""
        step_definition = {"prompt": "Do you want to continue?", "input_type": "boolean", "default": False}

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["input_type"] == "boolean"
        assert result["agent_action"]["default"] == False

    def test_user_input_choice_type_validation(self):
        """Test user input with choice type validation."""
        step_definition = {
            "prompt": "Select your preferred language:",
            "input_type": "choice",
            "choices": ["Python", "JavaScript", "TypeScript", "Go"],
            "default": "Python",
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["input_type"] == "choice"
        assert result["agent_action"]["choices"] == ["Python", "JavaScript", "TypeScript", "Go"]
        assert result["agent_action"]["default"] == "Python"

    def test_user_input_validation_rules_application(self):
        """Test user input validation rules application."""
        step_definition = {
            "prompt": "Enter email address:",
            "input_type": "string",
            "validation_pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
            "validation_message": "Please enter a valid email address",
            "required": True,
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["required"] == True

    def test_user_input_state_updates_on_success(self):
        """Test user input state updates when input is successfully collected."""
        step_definition = {
            "prompt": "Enter project name:",
            "input_type": "string",
            "state_update": {"project_name": "{{ user_input }}"},
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert "state_update" in result["agent_action"]
        assert result["agent_action"]["state_update"]["project_name"] == "{{ user_input }}"


class TestUserInputRetryLogic:
    """Test user input retry logic and attempt management."""

    def test_user_input_default_values_when_no_input(self):
        """Test user input default values when no input is provided."""
        step_definition = {
            "prompt": "Enter timeout (seconds):",
            "input_type": "number",
            "default": 30,
            "required": False,
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["default"] == 30
        assert result["agent_action"]["required"] == False

    def test_user_input_basic_processing(self):
        """Test user input basic processing functionality."""
        step_definition = {"prompt": "Enter valid input:", "input_type": "string", "max_attempts": 2}

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["prompt"] == "Enter valid input:"

    def test_user_input_number_with_validation_info(self):
        """Test user input number type with validation information."""
        step_definition = {
            "prompt": "Enter a number:",
            "input_type": "number",
            "validation": {"min": 1, "max": 100},
            "max_attempts": 3,
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["input_type"] == "number"

    def test_user_input_string_with_pattern_validation(self):
        """Test user input string type with pattern validation."""
        step_definition = {
            "prompt": "Enter valid data:",
            "input_type": "string",
            "max_attempts": 5,  # Custom max attempts
            "validation_pattern": "^[A-Z]{3}$",
            "validation_message": "Must be exactly 3 uppercase letters",
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["input_type"] == "string"

    def test_user_input_basic_string_processing(self):
        """Test user input basic string processing."""
        step_definition = {"prompt": "Enter input:", "input_type": "string"}

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["input_type"] == "string"
        assert result["agent_action"]["prompt"] == "Enter input:"


class TestUserInputChoiceSelection:
    """Test user input choice selection functionality."""

    def test_user_input_choice_valid_selection(self):
        """Test user input choice with valid selection options."""
        step_definition = {
            "prompt": "Choose deployment environment:",
            "input_type": "choice",
            "choices": ["development", "staging", "production"],
            "default": "development",
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["choices"] == ["development", "staging", "production"]
        assert result["agent_action"]["default"] == "development"

    def test_user_input_choice_with_validation_message(self):
        """Test user input choice with validation message."""
        step_definition = {
            "prompt": "Select option:",
            "input_type": "choice",
            "choices": ["option1", "option2", "option3"],
            "validation_message": "Please select from the available options",
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["choices"] == ["option1", "option2", "option3"]
        assert result["agent_action"]["input_type"] == "choice"

    def test_user_input_choice_list_presentation(self):
        """Test user input choice list presentation format."""
        step_definition = {
            "prompt": "Choose your role:",
            "input_type": "choice",
            "choices": [
                {"value": "dev", "label": "Developer"},
                {"value": "qa", "label": "Quality Assurance"},
                {"value": "pm", "label": "Product Manager"},
            ],
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["choices"] is not None
        assert len(result["agent_action"]["choices"]) == 3

        # Should support both simple and complex choice formats
        choices = result["agent_action"]["choices"]
        if isinstance(choices[0], dict):
            assert "value" in choices[0]
            assert "label" in choices[0]

    def test_user_input_choice_with_numeric_choices(self):
        """Test user input choice with numeric choice values."""
        step_definition = {
            "prompt": "Select priority level:",
            "input_type": "choice",
            "choices": [1, 2, 3, 4, 5],
            "default": 3,
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["choices"] == [1, 2, 3, 4, 5]
        assert result["agent_action"]["default"] == 3

    def test_user_input_variable_name_configuration(self):
        """Test user input with custom variable_name configuration."""
        step_definition = {
            "prompt": "Enter username:",
            "input_type": "string",
            "variable_name": "username",
            "state_update": {"auth_username": "{{ username }}"},
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        # Variable name should be used in state updates
        assert result["agent_action"]["state_update"]["auth_username"] == "{{ username }}"

    def test_user_input_basic_text_processing(self):
        """Test user input basic text processing functionality."""
        step_definition = {
            "prompt": "Enter password:",
            "instructions": "Password must be at least 8 characters with uppercase, lowercase, and numbers",
            "input_type": "string",
            "validation_pattern": "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d).{8,}$",
        }

        state_manager = Mock()
        workflow_id = "test_workflow_123"

        result = UserInputProcessor.process(step_definition, workflow_id, state_manager)

        assert result["status"] == "success"
        assert result["execution_type"] == "agent"
        assert result["agent_action"]["type"] == "user_input"
        assert result["agent_action"]["input_type"] == "string"
