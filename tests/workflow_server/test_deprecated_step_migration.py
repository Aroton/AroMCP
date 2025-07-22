"""Tests that demonstrate migration from deprecated step types.

This file shows how to migrate from deprecated step types like state_update
and batch_state_update to the new schema-compliant patterns.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.aromcp.workflow_server.workflow.step_registry import StepRegistry
from src.aromcp.workflow_server.workflow.validator import WorkflowValidator


class TestDeprecatedStepMigration:
    """Test migration patterns for deprecated step types."""

    def setup_method(self):
        """Set up test environment."""
        self.registry = StepRegistry()
        self.validator = WorkflowValidator()

    def test_state_update_migration_to_shell_command(self):
        """Test migrating state_update step to shell_command with state_update field."""
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

    def test_state_update_migration_to_mcp_call(self):
        """Test migrating state_update step to mcp_call with state_update field."""
        # New pattern using mcp_call
        migrated_step = {
            "id": "update_from_tool",
            "type": "mcp_call",
            "tool": "get_system_info",
            "parameters": {"type": "memory"},
            "state_update": {
                "path": "state.system_memory",
                "value": "{{ result.memory_mb }}"
            }
        }
        
        is_valid, error = self.registry.validate_step(migrated_step)
        assert is_valid, f"MCP call with state_update should be valid: {error}"

    def test_state_update_migration_to_user_input(self):
        """Test migrating state_update step to user_input with state_update field."""
        # New pattern using user_input
        migrated_step = {
            "id": "collect_name",
            "type": "user_input",
            "prompt": "Please enter your name:",
            "state_update": {
                "path": "state.user_name",
                "value": "{{ input }}"
            }
        }
        
        is_valid, error = self.registry.validate_step(migrated_step)
        assert is_valid, f"User input with state_update should be valid: {error}"

    def test_batch_state_update_migration_to_agent_response(self):
        """Test migrating batch_state_update step to agent_response with state_updates field."""
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

    def test_batch_state_update_with_operations_migration(self):
        """Test migrating batch_state_update with operations to multiple steps."""
        # New pattern: use separate steps or agent_response with operations
        migrated_steps = [
            {
                "id": "increment_counter",
                "type": "shell_command",
                "command": "echo 'Incrementing counter'",
                "state_update": {
                    "path": "state.counter",
                    "value": "3",
                    "operation": "increment"
                }
            },
            {
                "id": "set_items",
                "type": "shell_command", 
                "command": "echo 'Setting items'",
                "state_update": {
                    "path": "state.items",
                    "value": '["a", "b", "c"]',
                    "operation": "set"
                }
            },
            {
                "id": "append_item",
                "type": "shell_command",
                "command": "echo 'Appending item'", 
                "state_update": {
                    "path": "state.items",
                    "value": "d",
                    "operation": "append"
                }
            }
        ]
        
        for step in migrated_steps:
            is_valid, error = self.registry.validate_step(step)
            assert is_valid, f"Migrated step {step['id']} should be valid: {error}"

    def test_workflow_with_deprecated_steps_fails_validation(self):
        """Test that workflows with deprecated steps fail validation."""
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

    def test_workflow_with_migrated_steps_passes_validation(self):
        """Test that workflows with properly migrated steps pass validation."""
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

    def test_migration_guide_suggestions(self):
        """Test that deprecated step types provide helpful migration suggestions."""
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

    def test_execution_context_in_migrated_shell_commands(self):
        """Test that migrated shell commands can use execution_context."""
        # Test with client execution context
        migrated_step = {
            "id": "client_command",
            "type": "shell_command",
            "command": "echo 'Running on client'",
            "execution_context": "client",
            "state_update": {
                "path": "state.client_result",
                "value": "{{ output }}"
            }
        }
        
        is_valid, error = self.registry.validate_step(migrated_step)
        assert is_valid, f"Shell command with client execution_context should be valid: {error}"
        
        # Test with server execution context
        migrated_step["execution_context"] = "server"
        is_valid, error = self.registry.validate_step(migrated_step)
        assert is_valid, f"Shell command with server execution_context should be valid: {error}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])