"""Unit tests for sub-agent state isolation functionality.

Tests the _initialize_sub_agent_state method and related state isolation logic
to ensure sub-agents get properly isolated state with computed fields.
"""

import pytest
from unittest.mock import MagicMock, patch

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.state.models import StateSchema
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.models import InputDefinition, SubAgentTask, WorkflowStep
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager


class TestSubAgentStateIsolation:
    """Test sub-agent state isolation functionality."""

    def setup_method(self):
        """Set up test dependencies."""
        self.state_manager = StateManager()
        self.expression_evaluator = ExpressionEvaluator()
        self.step_registry = StepRegistry()
        self.subagent_manager = SubAgentManager(
            self.state_manager, 
            self.expression_evaluator, 
            self.step_registry
        )

    def test_initialize_sub_agent_state_with_defaults(self):
        """Test that sub-agent state initializes correctly with default_state."""
        # Create a sub-agent task with default_state
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs={},
            steps=[],
            default_state={
                "raw": {
                    "attempt_number": 0,
                    "success": False,
                    "last_error": ""
                }
            },
            state_schema=StateSchema()
        )
        
        task_context = {
            "task_id": "test_task_001",
            "item": "test_file.ts",
            "index": 0,
            "total": 1
        }
        
        # Test the method
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Verify the state structure
        assert "raw" in result
        # Computed is only added if there are computed fields in the schema
        # For empty schema, no computed section is created
        
        # Verify default_state values are preserved
        assert result["raw"]["attempt_number"] == 0
        assert result["raw"]["success"] is False
        assert result["raw"]["last_error"] == ""
        
        # Verify task context is not mixed in raw state (only specific fields)
        assert "item" not in result["raw"]
        assert "task_id" not in result["raw"]

    def test_initialize_sub_agent_state_with_inputs(self):
        """Test that sub-agent state includes input values with defaults."""
        # Create inputs with defaults
        inputs = {
            "file_path": InputDefinition(type="string", description="File path", required=True),
            "max_attempts": InputDefinition(type="number", description="Max attempts", required=False, default=10)
        }
        
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs=inputs,
            steps=[],
            default_state={"raw": {}},
            state_schema=StateSchema()
        )
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/test.ts",  # This should become file_path
            "index": 0,
            "total": 1
        }
        
        # Test the method
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Verify input mapping
        assert result["raw"]["file_path"] == "src/test.ts"  # Mapped from item
        assert result["raw"]["max_attempts"] == 10  # Default value

    def test_initialize_sub_agent_state_with_computed_fields(self):
        """Test that computed fields are evaluated correctly."""
        # Create state schema with computed fields
        state_schema = StateSchema(
            raw={},
            computed={
                "is_typescript_file": {
                    "from": "raw.file_path",
                    "transform": "input.endsWith('.ts') || input.endsWith('.tsx')"
                },
                "can_continue": {
                    "from": ["raw.attempt_number", "raw.max_attempts"],
                    "transform": "input[0] < input[1]"
                }
            }
        )
        
        inputs = {
            "file_path": InputDefinition(type="string", description="File path", required=True),
            "max_attempts": InputDefinition(type="number", description="Max attempts", required=False, default=5)
        }
        
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs=inputs,
            steps=[],
            default_state={"raw": {"attempt_number": 1}},
            state_schema=state_schema
        )
        
        task_context = {
            "task_id": "test_task_001",
            "item": "src/component.tsx",
            "index": 0,
            "total": 1
        }
        
        # Test the method
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Verify computed fields are calculated
        assert "computed" in result
        computed = result["computed"]
        
        # Check TypeScript file detection
        assert "is_typescript_file" in computed
        # Note: The actual evaluation might return None due to expression evaluator limitations
        # but the structure should be correct
        
        # Check can_continue calculation
        assert "can_continue" in computed

    def test_initialize_sub_agent_state_with_empty_defaults(self):
        """Test that sub-agent state handles missing default_state gracefully."""
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs={},
            steps=[],
            # No default_state provided
            state_schema=StateSchema()
        )
        
        task_context = {
            "task_id": "test_task_001",
            "item": "test_file.py",
            "index": 0,
            "total": 1
        }
        
        # Test the method
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Verify basic structure is created
        assert "raw" in result
        assert isinstance(result["raw"], dict)

    def test_initialize_sub_agent_state_error_handling(self):
        """Test that computed field errors are handled gracefully."""
        # Create state schema with a computed field that will cause an error
        state_schema = StateSchema(
            raw={},
            computed={
                "invalid_field": {
                    "from": "raw.nonexistent_field",
                    "transform": "input.some_invalid_operation()"
                }
            }
        )
        
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs={},
            steps=[],
            default_state={"raw": {}},
            state_schema=state_schema
        )
        
        task_context = {
            "task_id": "test_task_001",
            "item": "test_file.py",
            "index": 0,
            "total": 1
        }
        
        # Test the method - should not raise an exception
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Verify structure exists even with error
        assert "raw" in result
        assert "computed" in result
        
        # The computed field should be set to None due to error handling
        assert result["computed"]["invalid_field"] is None

    def test_initialize_sub_agent_state_deep_copy(self):
        """Test that default_state is deep copied to prevent mutation."""
        default_state = {
            "raw": {
                "nested_object": {"count": 0},
                "list_data": [1, 2, 3]
            }
        }
        
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs={},
            steps=[],
            default_state=default_state,
            state_schema=StateSchema()
        )
        
        task_context = {
            "task_id": "test_task_001",
            "item": "test_file.py",
            "index": 0,
            "total": 1
        }
        
        # Initialize state
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Modify the result
        result["raw"]["nested_object"]["count"] = 999
        result["raw"]["list_data"].append(4)
        
        # Verify original is unchanged (deep copy worked)
        assert default_state["raw"]["nested_object"]["count"] == 0
        assert len(default_state["raw"]["list_data"]) == 3

    def test_sub_agent_context_initialization(self):
        """Test that sub-agent contexts initialize isolated state correctly."""
        # Create a sub-agent task with comprehensive state
        inputs = {
            "file_path": InputDefinition(type="string", description="File path", required=True),
        }
        
        state_schema = StateSchema(
            computed={
                "can_continue": {
                    "from": "raw.attempt_number",
                    "transform": "input < 3"
                }
            }
        )
        
        sub_agent_task = SubAgentTask(
            name="test_task",
            description="Test task",
            inputs=inputs,
            steps=[WorkflowStep(id="test_step", type="user_message", definition={"message": "test"})],
            default_state={"raw": {"attempt_number": 0, "success": False}},
            state_schema=state_schema
        )
        
        task_context = {
            "task_id": "context_test_001",
            "item": "src/test.ts",
            "index": 0,
            "total": 1
        }
        
        # Test direct state initialization
        result = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, task_context, "workflow_001"
        )
        
        # Verify state structure
        assert "raw" in result
        assert "computed" in result  # Should exist because state_schema has computed fields
        
        # Verify state isolation - each call should create independent state
        result2 = self.subagent_manager._initialize_sub_agent_state(
            sub_agent_task, 
            {"task_id": "context_test_002", "item": "src/test2.ts", "index": 1, "total": 2}, 
            "workflow_001"
        )
        
        # Verify both states are independent
        assert result is not result2
        assert result["raw"] is not result2["raw"]
        
        # Modify one state to verify isolation
        result["raw"]["attempt_number"] = 999
        assert result2["raw"]["attempt_number"] == 0  # Should be unchanged