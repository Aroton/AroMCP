"""Test enhanced diagnostic information for workflow failures."""

import os
import pytest
from unittest.mock import MagicMock, patch

from aromcp.workflow_server.state.manager import StateManager
from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.workflow.step_registry import StepRegistry
from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager


class TestEnhancedDiagnostics:
    """Test enhanced diagnostic information for better failure analysis."""

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

    def test_debug_template_logging(self):
        """Test that debug mode logs missing template variables."""
        # Enable debug mode temporarily
        with patch.dict(os.environ, {'AROMCP_DEBUG_TEMPLATES': 'true'}):
            with patch('builtins.print') as mock_print:
                state = {"task_id": "test_task", "item": "test_file.ts"}
                
                # Try to resolve a missing variable
                template = "Processing {{ raw.missing_variable }} in {{ file_path }}"
                result = self.subagent_manager._replace_variables(template, state)
                
                # Should have logged debug information
                debug_calls = [call for call in mock_print.call_args_list if 'DEBUG:' in str(call)]
                assert len(debug_calls) > 0, "Should have logged debug information for missing variables"
                
                # Check that it logged the missing variable
                debug_output = str(debug_calls)
                assert "missing_variable" in debug_output, "Should mention the missing variable"
                assert "Available keys:" in debug_output, "Should list available keys"

    def test_sub_agent_failure_logging(self):
        """Test that sub-agent failures are logged with detailed information."""
        # Enable debug mode temporarily
        with patch.dict(os.environ, {'AROMCP_DEBUG_SUBAGENTS': 'true'}):
            with patch('builtins.print') as mock_print:
                # Set up a sub-agent context
                task_id = "failing_task_001"
                self.subagent_manager.sub_agent_contexts[task_id] = {
                    "sub_agent_state": {
                        "raw": {"loop.iteration": 3, "file_path": "src/error.ts"},
                        "computed": {"can_continue": False}
                    },
                    "task_context": {"item": "src/error.ts", "index": 0, "total": 1}
                }
                
                # Log a failure
                error_info = {
                    "error": "MCP tool failed",
                    "step_type": "mcp_call",
                    "tool": "aromcp.lint_project"
                }
                
                self.subagent_manager._log_sub_agent_failure(task_id, "lint_step", error_info)
                
                # Should have logged detailed information
                debug_calls = [call for call in mock_print.call_args_list if 'DEBUG:' in str(call)]
                assert len(debug_calls) >= 3, "Should have logged multiple debug messages"
                
                # Check the logged information
                debug_output = str(debug_calls)
                assert task_id in debug_output, "Should mention the task ID"
                assert "lint_step" in debug_output, "Should mention the failing step"
                assert "MCP tool failed" in debug_output, "Should include error details"
                assert "src/error.ts" in debug_output, "Should include file path from state"

    def test_failure_analysis_conditions(self):
        """Test different failure analysis conditions."""
        test_cases = [
            {
                "name": "hints_not_completed",
                "state": {
                    "computed": {
                        "hints_completed": False,
                        "lint_completed": False,
                        "typescript_completed": False,
                        "is_typescript_file": True
                    },
                    "loop": {"iteration": 1},
                    "max_attempts": 10
                },
                "expected_analysis": "Hints step failed or never completed"
            },
            {
                "name": "lint_not_completed",
                "state": {
                    "computed": {
                        "hints_completed": True,
                        "lint_completed": False,
                        "typescript_completed": False,
                        "is_typescript_file": True
                    },
                    "loop": {"iteration": 2},
                    "max_attempts": 10
                },
                "expected_analysis": "Linting errors not resolved"
            },
            {
                "name": "typescript_not_completed",
                "state": {
                    "computed": {
                        "hints_completed": True,
                        "lint_completed": True,
                        "typescript_completed": False,
                        "is_typescript_file": True
                    },
                    "loop": {"iteration": 3},
                    "max_attempts": 10
                },
                "expected_analysis": "TypeScript errors not resolved"
            },
            {
                "name": "max_attempts_exceeded",
                "state": {
                    "computed": {
                        "hints_completed": True,
                        "lint_completed": True,
                        "typescript_completed": True,
                        "is_typescript_file": True
                    },
                    "loop": {"iteration": 10},
                    "max_attempts": 10
                },
                "expected_analysis": "Maximum attempts exceeded"
            }
        ]
        
        for case in test_cases:
            # Test the ternary logic for failure analysis
            template = """{{
                !computed.hints_completed ? 'Hints step failed or never completed' :
                !computed.lint_completed ? 'Linting errors not resolved' :
                computed.is_typescript_file && !computed.typescript_completed ? 'TypeScript errors not resolved' :
                loop.iteration >= max_attempts ? 'Maximum attempts exceeded' :
                'Unknown failure condition'
            }}"""
            
            result = self.subagent_manager._replace_variables(template, case["state"])
            assert result == case["expected_analysis"], (
                f"For {case['name']}: expected '{case['expected_analysis']}', got '{result}'"
            )

    def test_diagnostic_information_structure(self):
        """Test that diagnostic information includes all necessary fields."""
        state = {
            "file_path": "src/component.tsx",
            "computed": {
                "is_typescript_file": True,
                "hints_completed": True,
                "lint_completed": False,
                "typescript_completed": False,
                "all_steps_completed": False,
                "can_continue": True
            },
            "raw": {
                "step_results": {
                    "hints": {"success": True, "completed_at": 1},
                    "lint": {"success": False, "errors": 3, "error_details": ["Missing semicolon", "Unused variable", "Type error"]},
                    "typescript": None
                }
            },
            "loop": {
                "iteration": 2
            },
            "max_attempts": 10
        }
        
        # Test the diagnostic JSON structure
        diagnostic_template = """{{
          "file_info": {
            "path": "{{ file_path }}",
            "is_typescript": {{ computed.is_typescript_file }}
          },
          "execution_state": {
            "attempt": {{ loop.iteration }},
            "max_attempts": {{ max_attempts }},
            "can_continue": {{ computed.can_continue }},
            "all_completed": {{ computed.all_steps_completed }}
          },
          "step_completion": {
            "hints_completed": {{ computed.hints_completed }},
            "lint_completed": {{ computed.lint_completed }},
            "typescript_completed": {{ computed.typescript_completed }}
          }
        }}"""
        
        result = self.subagent_manager._replace_variables(diagnostic_template, state)
        
        # Should contain all the expected diagnostic information
        assert "src/component.tsx" in result
        assert "True" in result  # Python boolean conversion
        assert '"attempt": 2' in result
        assert '"max_attempts": 10' in result
        assert "True" in result or "False" in result  # Should have boolean values
        assert "2" in result  # Should have attempt number
        assert "10" in result  # Should have max attempts

    def test_enhanced_error_messages_with_context(self):
        """Test that enhanced error messages provide helpful context."""
        # Simulate a realistic failure scenario
        state = {
            "item": "src/complex-component.tsx",
            "task_id": "standards_task_042",
            "computed": {
                "is_typescript_file": True,
                "hints_completed": True,
                "lint_completed": False,  # This is where it failed
                "typescript_completed": False
            },
            "raw": {
                "step_results": {
                    "hints": {"success": True},
                    "lint": {
                        "success": False,
                        "errors": 5,
                        "error_details": ["Expected ';'", "Unused import 'React'", "Type 'string' is not assignable to type 'number'"]
                    },
                    "typescript": None
                }
            },
            "loop": {
                "iteration": 3
            }
        }
        
        # Test enhanced failure message
        failure_template = "❌ Failed to enforce standards on {{ file_path }} after {{ loop.iteration }} attempts"
        result = self.subagent_manager._replace_variables(failure_template, state)
        expected = "❌ Failed to enforce standards on src/complex-component.tsx after 3 attempts"
        assert result == expected
        
        # Test failure reason analysis
        reason_template = """{{
            !computed.hints_completed ? 'Hints step failed or never completed' :
            !computed.lint_completed ? 'Linting errors not resolved' :
            computed.is_typescript_file && !computed.typescript_completed ? 'TypeScript errors not resolved' :
            'Unknown failure condition'
        }}"""
        reason_result = self.subagent_manager._replace_variables(reason_template, state)
        assert reason_result == "Linting errors not resolved"
        
        # Test detailed status with error counts
        status_template = "Lint: {{ computed.lint_completed ? '✅ Completed' : '❌ Failed' }}{{ !computed.lint_completed && raw.step_results.lint ? ' (' + raw.step_results.lint.errors + ' errors)' : '' }}"
        status_result = self.subagent_manager._replace_variables(status_template, state)
        expected_status = "Lint: ❌ Failed (5 errors)"
        assert status_result == expected_status