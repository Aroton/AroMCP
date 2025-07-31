"""
Comprehensive user interaction testing for user interaction system.

Covers missing acceptance criteria:
- AC-UI-002: Message formats support text, markdown, and code display
- AC-UI-005: Long messages are handled appropriately
- AC-UI-014: Input validation supports custom validation expressions
- AC-UI-022: User interaction timeouts are configurable

Focus: Message format validation, long message handling, custom validation expressions, timeouts
Pillar: User Interaction
"""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.steps.user_input import UserInputProcessor
from aromcp.workflow_server.workflow.steps.user_message import UserMessageProcessor


class TestUserInteractionComprehensive:
    """Test comprehensive user interaction scenarios and edge cases."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock state manager for testing."""
        manager = Mock(spec=StateManager)
        manager.get_flattened_state.return_value = {"user_name": "Alice", "current_score": 85}
        manager.resolve_variables = Mock(side_effect=lambda x: x.replace("{{ user_name }}", "Alice"))
        manager.update_state = Mock()
        return manager

    @pytest.fixture
    def step_context(self, mock_state_manager):
        """Create step context for testing."""
        return StepContext(
            workflow_id="wf_interaction_test",
            step_id="interaction_step",
            state_manager=mock_state_manager,
            workflow_config={"timeout_seconds": 60},
        )

    @pytest.fixture
    def workflow_state(self):
        """Create workflow state for testing."""
        return WorkflowState(
            workflow_id="wf_interaction_test",
            status="running",
            current_step_index=2,
            total_steps=5,
            state={"inputs": {}, "state": {"user_name": "Alice"}, "computed": {}},
            execution_context={"interaction_history": []},
        )

    def test_message_format_validation_and_rendering(self, step_context):
        """
        Test AC-UI-002: Message formats support text, markdown, and code display
        Focus: Different message formats are validated and rendered correctly
        """
        message_step = UserMessageProcessor()

        # Test different message formats
        format_test_cases = [
            {
                "format": "text",
                "message": "This is a plain text message with no special formatting.",
                "expected_format": "text",
                "should_validate": True,
            },
            {
                "format": "markdown",
                "message": "# Header\n\nThis is **bold** and *italic* text with [links](http://example.com).\n\n- List item 1\n- List item 2",
                "expected_format": "markdown",
                "should_validate": True,
            },
            {
                "format": "code",
                "message": "function example() {\n  console.log('Hello, world!');\n  return 42;\n}",
                "expected_format": "code",
                "should_validate": True,
            },
            {
                "format": "json",
                "message": '{\n  "status": "success",\n  "data": {\n    "id": 123,\n    "name": "test"\n  }\n}',
                "expected_format": "json",
                "should_validate": True,
            },
            {
                "format": "invalid_format",
                "message": "This format should not be accepted",
                "expected_format": None,
                "should_validate": False,
            },
        ]

        for test_case in format_test_cases:
            step_definition = {
                "id": "format_test",
                "type": "user_message",
                "message": test_case["message"],
                "format": test_case["format"],
                "message_type": "info",
            }

            if test_case["should_validate"]:
                result = message_step.execute(step_definition, step_context)

                assert result["status"] == "completed"
                assert result["message_data"]["format"] == test_case["expected_format"]
                assert result["message_data"]["content"] == test_case["message"]
            else:
                with pytest.raises(ValueError) as exc_info:
                    message_step.execute(step_definition, step_context)
                assert "invalid format" in str(exc_info.value).lower()

    def test_message_format_specific_validation(self, step_context):
        """
        Test format-specific validation rules
        Focus: Each format has appropriate validation constraints
        """
        message_step = UserMessageProcessor()

        # Test markdown format validation
        markdown_test_cases = [
            {"message": "# Valid Markdown\n\n**Bold** and *italic* text.", "valid": True},
            {
                "message": "Invalid markdown with <script>alert('xss')</script>",
                "valid": False,  # Should reject potentially dangerous HTML
            },
        ]

        for test_case in markdown_test_cases:
            step_definition = {
                "id": "markdown_test",
                "type": "user_message",
                "message": test_case["message"],
                "format": "markdown",
                "message_type": "info",
            }

            if test_case["valid"]:
                result = message_step.execute(step_definition, step_context)
                assert result["status"] == "completed"
            else:
                # Should either reject or sanitize dangerous content
                result = message_step.execute(step_definition, step_context)
                # Verify script tags are removed/escaped
                assert "<script>" not in result["message_data"]["content"]

        # Test code format validation
        code_test_cases = [
            {"message": "def hello():\n    print('Hello, world!')", "language": "python", "valid": True},
            {"message": "SELECT * FROM users WHERE id = 1;", "language": "sql", "valid": True},
            {"message": "{ invalid json", "language": "json", "valid": False},
        ]

        for test_case in code_test_cases:
            step_definition = {
                "id": "code_test",
                "type": "user_message",
                "message": test_case["message"],
                "format": "code",
                "language": test_case.get("language"),
                "message_type": "info",
            }

            result = message_step.execute(step_definition, step_context)
            if test_case["valid"]:
                assert result["status"] == "completed"
                if "language" in test_case:
                    assert result["message_data"]["language"] == test_case["language"]

    def test_long_message_handling_strategies(self, step_context):
        """
        Test AC-UI-005: Long messages are handled appropriately
        Focus: Various strategies for handling messages exceeding display limits
        """
        message_step = UserMessageProcessor()

        # Create very long message (10KB)
        long_message = "This is a very long message. " * 350  # ~10KB

        # Test different handling strategies
        handling_strategies = [
            {"strategy": "truncate", "max_length": 1000, "expected_behavior": "truncated"},
            {"strategy": "paginate", "page_size": 500, "expected_behavior": "paginated"},
            {"strategy": "full", "expected_behavior": "full_display"},
            {"strategy": "summarize", "max_length": 500, "expected_behavior": "summarized"},
        ]

        for strategy_config in handling_strategies:
            step_definition = {
                "id": "long_message_test",
                "type": "user_message",
                "message": long_message,
                "format": "text",
                "message_type": "info",
                "long_message_handling": strategy_config,
            }

            result = message_step.execute(step_definition, step_context)

            assert result["status"] == "completed"

            if strategy_config["strategy"] == "truncate":
                assert len(result["message_data"]["content"]) <= strategy_config["max_length"]
                assert result["message_data"]["truncated"] == True

            elif strategy_config["strategy"] == "paginate":
                assert "pages" in result["message_data"]
                assert result["message_data"]["total_pages"] > 1

            elif strategy_config["strategy"] == "full":
                assert len(result["message_data"]["content"]) == len(long_message)

            elif strategy_config["strategy"] == "summarize":
                assert len(result["message_data"]["content"]) <= strategy_config["max_length"]
                assert result["message_data"]["summarized"] == True

    def test_custom_validation_expressions(self, step_context):
        """
        Test AC-UI-014: Input validation supports custom validation expressions
        Focus: JavaScript expressions for complex input validation
        """
        input_step = UserInputProcessor()

        # Mock expression evaluator for validation
        def mock_evaluate_validation(expression, context):
            """Mock validation expression evaluation."""
            user_input = context.get("user_input", "")

            if "length >= 8" in expression:
                return len(user_input) >= 8
            elif "includes('@')" in expression:
                return "@" in user_input
            elif "match(/^[A-Z]/" in expression:
                return user_input and user_input[0].isupper()
            elif "parseInt(value) > 0" in expression:
                try:
                    return int(user_input) > 0
                except:
                    return False
            elif "endsWith('.com')" in expression:
                return user_input.endswith(".com")
            else:
                return True

        with patch("src.aromcp.workflow_server.workflow.steps.user_input.ExpressionEvaluator") as mock_evaluator_class:
            mock_evaluator = Mock()
            mock_evaluator.evaluate_expression = Mock(side_effect=mock_evaluate_validation)
            mock_evaluator_class.return_value = mock_evaluator

            # Test various custom validation scenarios
            validation_test_cases = [
                {
                    "description": "Password strength validation",
                    "input_type": "string",
                    "validation_expression": "user_input.length >= 8 && user_input.match(/[A-Z]/) && user_input.match(/[0-9]/)",
                    "test_inputs": [
                        {"input": "Password123", "should_pass": True},
                        {"input": "weak", "should_pass": False},
                        {"input": "NoNumbers!", "should_pass": False},
                    ],
                },
                {
                    "description": "Email format validation",
                    "input_type": "string",
                    "validation_expression": "user_input.includes('@') && user_input.endsWith('.com')",
                    "test_inputs": [
                        {"input": "user@example.com", "should_pass": True},
                        {"input": "invalid-email", "should_pass": False},
                        {"input": "user@domain.org", "should_pass": False},
                    ],
                },
                {
                    "description": "Positive number validation",
                    "input_type": "number",
                    "validation_expression": "parseInt(user_input) > 0 && parseInt(user_input) <= 100",
                    "test_inputs": [
                        {"input": "50", "should_pass": True},
                        {"input": "0", "should_pass": False},
                        {"input": "150", "should_pass": False},
                    ],
                },
            ]

            for test_case in validation_test_cases:
                step_definition = {
                    "id": "custom_validation_test",
                    "type": "user_input",
                    "prompt": f"Enter {test_case['description']}",
                    "input_type": test_case["input_type"],
                    "validation": {
                        "custom_expression": test_case["validation_expression"],
                        "error_message": f"Invalid {test_case['description']}",
                    },
                    "max_retries": 1,
                }

                for input_test in test_case["test_inputs"]:
                    # Mock user providing input
                    with patch.object(input_step, "_collect_user_input", return_value=input_test["input"]):

                        if input_test["should_pass"]:
                            result = input_step.execute(step_definition, step_context)
                            assert result["status"] == "completed"
                            assert result["user_input"] == input_test["input"]
                        else:
                            # Should fail validation
                            result = input_step.execute(step_definition, step_context)
                            assert result["status"] in ["validation_failed", "retry_exhausted"]

    def test_user_interaction_timeout_configuration(self, step_context):
        """
        Test AC-UI-022: User interaction timeouts are configurable
        Focus: Different timeout configurations for user input and wait steps
        """
        input_step = UserInputProcessor()
        wait_step = WaitStep()

        # Test user input timeout
        input_timeout_cases = [
            {
                "timeout": 5,  # 5 second timeout
                "user_response_delay": 3,  # User responds in 3 seconds
                "should_timeout": False,
            },
            {
                "timeout": 2,  # 2 second timeout
                "user_response_delay": 4,  # User responds in 4 seconds (too late)
                "should_timeout": True,
            },
        ]

        for test_case in input_timeout_cases:
            step_definition = {
                "id": "timeout_input_test",
                "type": "user_input",
                "prompt": "Please respond quickly",
                "input_type": "string",
                "timeout": test_case["timeout"],
                "error_handling": {"strategy": "fallback", "fallback_value": "timeout_default"},
            }

            # Mock user input with delay
            def delayed_input(*args, **kwargs):
                time.sleep(test_case["user_response_delay"])
                return "user_response"

            with patch.object(input_step, "_collect_user_input", side_effect=delayed_input):
                start_time = time.time()
                result = input_step.execute(step_definition, step_context)
                elapsed_time = time.time() - start_time

                if test_case["should_timeout"]:
                    # Should timeout and use fallback
                    assert elapsed_time <= test_case["timeout"] + 0.5  # Small tolerance
                    assert result["timed_out"] == True
                    assert result["user_input"] == "timeout_default"
                else:
                    # Should complete normally
                    assert result["status"] == "completed"
                    assert result["user_input"] == "user_response"

        # Test wait step timeout
        wait_timeout_cases = [
            {"timeout": 3, "client_resume_delay": 2, "should_timeout": False},
            {"timeout": 1, "client_resume_delay": 3, "should_timeout": True},
        ]

        for test_case in wait_timeout_cases:
            step_definition = {
                "id": "timeout_wait_test",
                "type": "wait_step",
                "message": "Waiting for client action",
                "timeout": test_case["timeout"],
                "error_handling": {"strategy": "continue"},
            }

            # Mock client resume action with delay
            def delayed_resume():
                time.sleep(test_case["client_resume_delay"])
                return {"action": "resume"}

            with patch.object(wait_step, "_wait_for_client_action", side_effect=delayed_resume):
                start_time = time.time()
                result = wait_step.execute(step_definition, step_context)
                elapsed_time = time.time() - start_time

                if test_case["should_timeout"]:
                    assert elapsed_time <= test_case["timeout"] + 0.5
                    assert result["timed_out"] == True
                else:
                    assert result["status"] == "completed"

    def test_timeout_warning_notifications(self, step_context):
        """
        Test timeout warning notifications for user interactions
        Focus: Users receive warnings before timeout expiration
        """
        input_step = UserInputProcessor()
        warnings_received = []

        def warning_callback(message, remaining_time):
            warnings_received.append({"message": message, "remaining": remaining_time, "timestamp": time.time()})

        step_definition = {
            "id": "warning_test",
            "type": "user_input",
            "prompt": "Please enter your response",
            "input_type": "string",
            "timeout": 5,  # 5 second timeout
            "warning_thresholds": [2, 1],  # Warn at 2s and 1s remaining
            "warning_callback": warning_callback,
        }

        # Mock user input that arrives just before timeout
        def almost_timeout_input(*args, **kwargs):
            time.sleep(4.5)  # Almost timeout
            return "just_in_time"

        with patch.object(input_step, "_collect_user_input", side_effect=almost_timeout_input):
            result = input_step.execute(step_definition, step_context)

            # Should have completed successfully
            assert result["status"] == "completed"
            assert result["user_input"] == "just_in_time"

            # Should have received warnings
            assert len(warnings_received) >= 1

            # Verify warning timing and content
            for warning in warnings_received:
                assert warning["remaining"] > 0
                assert warning["remaining"] <= 2  # Should warn when <= 2 seconds remaining
                assert "timeout" in warning["message"].lower()

    def test_concurrent_user_interactions(self, step_context):
        """
        Test multiple concurrent user interactions
        Focus: Isolation and proper handling of multiple simultaneous user inputs
        """
        input_step = UserInputProcessor()

        # Simulate multiple concurrent user sessions
        interaction_results = {}
        interaction_errors = []

        def concurrent_interaction(session_id, prompt_text, response_delay):
            try:
                step_def = {
                    "id": f"concurrent_input_{session_id}",
                    "type": "user_input",
                    "prompt": prompt_text,
                    "input_type": "string",
                    "timeout": 5,
                    "session_id": session_id,
                }

                # Mock user response with varying delays
                def delayed_response(*args, **kwargs):
                    time.sleep(response_delay)
                    return f"response_from_session_{session_id}"

                with patch.object(input_step, "_collect_user_input", side_effect=delayed_response):
                    result = input_step.execute(step_def, step_context)
                    interaction_results[session_id] = result

            except Exception as e:
                interaction_errors.append(f"Session {session_id}: {str(e)}")

        # Create multiple concurrent threads
        threads = []
        for i in range(5):
            thread = threading.Thread(
                target=concurrent_interaction, args=(i, f"Prompt for session {i}", 0.1 * i)  # Varying delays
            )
            threads.append(thread)

        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        elapsed_time = time.time() - start_time

        # Verify concurrent execution
        assert len(interaction_errors) == 0, f"Concurrent interaction errors: {interaction_errors}"
        assert len(interaction_results) == 5

        # All should complete successfully
        for session_id, result in interaction_results.items():
            assert result["status"] == "completed"
            assert result["user_input"] == f"response_from_session_{session_id}"

        # Should complete faster than sequential execution (would be ~1s sequential)
        assert elapsed_time < 0.8  # Allow some overhead

    def test_input_validation_with_retry_logic(self, step_context):
        """
        Test complex input validation with retry mechanisms
        Focus: Multiple validation failures with incremental guidance
        """
        input_step = UserInputProcessor()

        # Mock validation that becomes more lenient with retries
        validation_attempts = []

        def mock_validate_with_retries(expression, context):
            attempt_count = len(validation_attempts) + 1
            validation_attempts.append(attempt_count)

            user_input = context.get("user_input", "")

            if attempt_count == 1:
                # First attempt: strict validation
                return len(user_input) >= 10 and any(c.isdigit() for c in user_input)
            elif attempt_count == 2:
                # Second attempt: relaxed validation
                return len(user_input) >= 6
            else:
                # Final attempts: very lenient
                return len(user_input) > 0

        with patch("src.aromcp.workflow_server.workflow.steps.user_input.ExpressionEvaluator") as mock_evaluator_class:
            mock_evaluator = Mock()
            mock_evaluator.evaluate_expression = Mock(side_effect=mock_validate_with_retries)
            mock_evaluator_class.return_value = mock_evaluator

            step_definition = {
                "id": "retry_validation_test",
                "type": "user_input",
                "prompt": "Enter a complex password",
                "input_type": "string",
                "validation": {
                    "custom_expression": "user_input.length >= 10 && /\\d/.test(user_input)",
                    "retry_guidance": [
                        "Password must be at least 10 characters with a number",
                        "Password must be at least 6 characters",
                        "Password must not be empty",
                    ],
                },
                "max_retries": 3,
            }

            # Mock user inputs that gradually improve
            user_inputs = ["weak", "better", "final_attempt"]
            input_iter = iter(user_inputs)

            def mock_progressive_input(*args, **kwargs):
                return next(input_iter)

            with patch.object(input_step, "_collect_user_input", side_effect=mock_progressive_input):
                result = input_step.execute(step_definition, step_context)

                # Should eventually succeed after retries
                assert result["status"] == "completed"
                assert result["user_input"] == "final_attempt"
                assert len(validation_attempts) == 3  # Three validation attempts

                # Should have received progressive guidance
                assert result["retry_count"] == 2  # Two retries before success


class TestUserInteractionIntegration:
    """Test user interaction integration with broader workflow scenarios."""

    def test_production_user_feedback_workflow(self):
        """
        Test user interaction in production-like feedback collection workflow
        Focus: Realistic user interaction patterns similar to code review workflows
        """
        state_manager = Mock(spec=StateManager)
        state_manager.get_flattened_state.return_value = {
            "review_items": ["lint_errors", "type_errors", "test_failures"],
            "current_item": "lint_errors",
            "review_status": "pending",
        }

        step_context = StepContext(
            workflow_id="wf_code_review",
            step_id="user_feedback",
            state_manager=state_manager,
            workflow_config={"timeout_seconds": 300},  # 5 minute timeout for code review
        )

        # Simulate code review workflow user interactions
        interaction_steps = [
            {
                "type": "user_message",
                "message": "## Code Review Results\n\n**Lint Errors Found:** 3\n**Type Errors:** 1\n**Test Failures:** 0",
                "format": "markdown",
                "message_type": "info",
            },
            {
                "type": "user_input",
                "prompt": "Would you like to auto-fix the lint errors? (yes/no)",
                "input_type": "choice",
                "choices": ["yes", "no"],
                "timeout": 60,
            },
            {
                "type": "user_input",
                "prompt": "Please provide any additional comments for this review:",
                "input_type": "string",
                "required": False,
                "validation": {"max_length": 500},
                "timeout": 120,
            },
        ]

        results = []

        # Mock user responses
        user_responses = ["yes", "Looks good overall, just minor formatting issues"]
        response_iter = iter(user_responses)

        for step_def in interaction_steps:
            if step_def["type"] == "user_message":
                message_step = UserMessageProcessor()
                result = message_step.execute(step_def, step_context)
                results.append(result)

            elif step_def["type"] == "user_input":
                input_step = UserInputProcessor()

                def mock_user_response(*args, **kwargs):
                    try:
                        return next(response_iter)
                    except StopIteration:
                        return ""  # Default for optional inputs

                with patch.object(input_step, "_collect_user_input", side_effect=mock_user_response):
                    result = input_step.execute(step_def, step_context)
                    results.append(result)

        # Verify workflow completion
        assert len(results) == 3
        assert all(r["status"] == "completed" for r in results)

        # Verify specific results
        message_result = results[0]
        assert message_result["message_data"]["format"] == "markdown"
        assert "Code Review Results" in message_result["message_data"]["content"]

        choice_result = results[1]
        assert choice_result["user_input"] == "yes"

        comment_result = results[2]
        assert "formatting issues" in comment_result["user_input"]

    def test_user_interaction_state_integration(self):
        """
        Test user interaction integration with workflow state management
        Focus: User inputs properly update workflow state across tiers
        """
        # Mock state manager with three-tier architecture
        state_manager = Mock(spec=StateManager)
        current_state = {"user_preferences": {}, "form_data": {}, "validation_results": {}}

        def mock_get_state():
            return current_state

        def mock_update_state(updates):
            for update in updates:
                if update["path"] == "user_preferences.theme":
                    current_state["user_preferences"]["theme"] = update["value"]
                elif update["path"] == "form_data.email":
                    current_state["form_data"]["email"] = update["value"]
                elif update["path"] == "validation_results.email_valid":
                    current_state["validation_results"]["email_valid"] = update["value"]

        state_manager.get_flattened_state = Mock(side_effect=mock_get_state)
        state_manager.update_state = Mock(side_effect=mock_update_state)

        step_context = StepContext(
            workflow_id="wf_state_integration", step_id="user_form", state_manager=state_manager, workflow_config={}
        )

        # User input step that updates state
        input_step = UserInputProcessor()

        step_definition = {
            "id": "email_input",
            "type": "user_input",
            "prompt": "Enter your email address:",
            "input_type": "string",
            "validation": {"pattern": r"^[^@]+@[^@]+\.[^@]+$", "error_message": "Please enter a valid email address"},
            "state_updates": [
                {"path": "form_data.email", "value": "{{ user_input }}"},
                {"path": "validation_results.email_valid", "value": True},
            ],
        }

        # Mock valid email input
        with patch.object(input_step, "_collect_user_input", return_value="user@example.com"):
            result = input_step.execute(step_definition, step_context)

            # Verify execution success
            assert result["status"] == "completed"
            assert result["user_input"] == "user@example.com"

            # Verify state updates were called
            state_manager.update_state.assert_called()

            # Verify final state
            final_state = mock_get_state()
            assert final_state["form_data"].get("email") == "user@example.com"
            assert final_state["validation_results"].get("email_valid") == True
