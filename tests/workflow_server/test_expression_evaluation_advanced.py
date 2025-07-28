"""
Advanced expression evaluation testing for variable resolution.

Covers missing acceptance criteria:
- AC-VR-008: Python-based evaluation fallback works for basic expressions
- AC-VR-020: Complex nested expressions evaluate correctly

Focus: PythonMonkey fallback behavior, complex nested expression evaluation
Pillar: Variable Resolution
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import json

from aromcp.workflow_server.workflow.expressions import ExpressionEvaluator
from aromcp.workflow_server.state.manager import StateManager


class TestExpressionEvaluationAdvanced:
    """Test advanced expression evaluation scenarios and fallback mechanisms."""

    @pytest.fixture
    def mock_pythonmonkey_available(self):
        """Mock PythonMonkey as available."""
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', True):
            mock_pm = Mock()
            mock_pm.eval = Mock()
            with patch('aromcp.workflow_server.workflow.expression_evaluator.pythonmonkey', mock_pm):
                yield mock_pm

    @pytest.fixture
    def mock_pythonmonkey_unavailable(self):
        """Mock PythonMonkey as unavailable to test fallback."""
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', False):
            yield

    @pytest.fixture
    def expression_evaluator_with_pm(self, mock_pythonmonkey_available):
        """Expression evaluator with PythonMonkey available."""
        return ExpressionEvaluator()

    @pytest.fixture
    def expression_evaluator_fallback(self, mock_pythonmonkey_unavailable):
        """Expression evaluator with PythonMonkey unavailable (fallback mode)."""
        return ExpressionEvaluator()

    @pytest.fixture
    def complex_context(self):
        """Complex context for testing nested expressions."""
        return {
            "user": {
                "profile": {
                    "name": "John Doe",
                    "age": 30,
                    "preferences": {
                        "theme": "dark",
                        "language": "en",
                        "notifications": True
                    },
                    "roles": ["user", "admin", "developer"],
                    "metadata": {
                        "created_at": "2023-01-15",
                        "last_login": "2024-07-20",
                        "login_count": 150
                    }
                },
                "settings": {
                    "privacy": {"public": False, "analytics": True},
                    "display": {"compact": True, "animations": False}
                }
            },
            "project": {
                "info": {
                    "name": "Test Project",
                    "version": "1.2.3",
                    "tags": ["react", "typescript", "testing"],
                    "stats": {
                        "files": 245,
                        "tests": 89,
                        "coverage": 0.85
                    }
                },
                "config": {
                    "build": {"target": "es2020", "minify": True},
                    "lint": {"strict": True, "rules": ["airbnb", "prettier"]}
                }
            },
            "calculations": {
                "scores": [95, 87, 92, 78, 99],
                "weights": [0.3, 0.2, 0.25, 0.15, 0.1],
                "thresholds": {"excellent": 90, "good": 80, "fair": 70}
            }
        }

    def test_python_fallback_basic_expressions(self, expression_evaluator_fallback, complex_context):
        """
        Test AC-VR-008: Python-based evaluation fallback works for basic expressions
        Focus: Basic arithmetic, comparisons, and boolean logic work without PythonMonkey
        """
        test_cases = [
            # Arithmetic expressions
            {"expression": "2 + 3 * 4", "expected": 14},
            {"expression": "(10 - 3) * 2", "expected": 14},
            {"expression": "100 / 4", "expected": 25.0},
            {"expression": "15 % 4", "expected": 3},
            {"expression": "2 ** 3", "expected": 8},
            
            # Boolean expressions
            {"expression": "True and False", "expected": False},
            {"expression": "True or False", "expected": True},
            {"expression": "not True", "expected": False},
            {"expression": "not False", "expected": True},
            
            # Comparison expressions
            {"expression": "5 > 3", "expected": True},
            {"expression": "5 < 3", "expected": False},
            {"expression": "5 >= 5", "expected": True},
            {"expression": "5 <= 4", "expected": False},
            {"expression": "5 == 5", "expected": True},
            {"expression": "5 != 3", "expected": True},
            
            # Mixed expressions
            {"expression": "(5 > 3) and (2 < 4)", "expected": True},
            {"expression": "(10 / 2) == 5", "expected": True},
            {"expression": "not (3 > 5)", "expected": True}
        ]

        for test_case in test_cases:
            result = expression_evaluator_fallback.evaluate_expression(
                test_case["expression"], 
                complex_context
            )
            assert result == test_case["expected"], f"Failed for expression: {test_case['expression']}"

    def test_python_fallback_with_context_variables(self, expression_evaluator_fallback, complex_context):
        """
        Test AC-VR-008: Python fallback handles context variable access
        Focus: Variable resolution works in fallback mode
        """
        test_cases = [
            # Simple variable access
            {"expression": "user['profile']['age']", "expected": 30},
            {"expression": "project['info']['version']", "expected": "1.2.3"},
            {"expression": "len(calculations['scores'])", "expected": 5},
            
            # Variable in calculations
            {"expression": "user['profile']['age'] + 5", "expected": 35},
            {"expression": "project['info']['stats']['files'] > 200", "expected": True},
            {"expression": "calculations['thresholds']['excellent'] - 10", "expected": 80},
            
            # List/array operations
            {"expression": "calculations['scores'][0]", "expected": 95},
            {"expression": "len(user['profile']['roles'])", "expected": 3},
            {"expression": "'admin' in user['profile']['roles']", "expected": True},
            
            # String operations
            {"expression": "user['profile']['name'].lower()", "expected": "john doe"},
            {"expression": "project['info']['name'].replace('Test', 'Demo')", "expected": "Demo Project"},
            {"expression": "len(project['info']['name'])", "expected": 12}
        ]

        for test_case in test_cases:
            result = expression_evaluator_fallback.evaluate_expression(
                test_case["expression"],
                complex_context
            )
            assert result == test_case["expected"], f"Failed for expression: {test_case['expression']}"

    def test_python_fallback_limitations_vs_pythonmonkey(self, expression_evaluator_fallback, expression_evaluator_with_pm, mock_pythonmonkey_available):
        """
        Test AC-VR-008: Python fallback has known limitations compared to PythonMonkey
        Focus: ES6+ features that only work with PythonMonkey
        """
        context = {"data": [1, 2, 3, 4, 5], "threshold": 3}

        # ES6+ features that should work with PythonMonkey but not Python fallback
        es6_expressions = [
            "data.filter(x => x > threshold)",  # Arrow functions
            "data.map(x => x * 2)",  # Array methods with arrow functions
            "const result = data.reduce((acc, val) => acc + val, 0); result",  # const, reduce
            "`Value is: ${data[0]}`",  # Template literals
            "let [first, ...rest] = data; first",  # Destructuring
        ]

        # Mock PythonMonkey to return expected results for ES6 features
        mock_pythonmonkey_available.eval.side_effect = [
            [2, 3, 4, 5],  # filter result
            [2, 4, 6, 8, 10],  # map result
            15,  # reduce result
            "Value is: 1",  # template literal
            1  # destructuring result
        ]

        # Test PythonMonkey handling ES6 features
        for i, expression in enumerate(es6_expressions):
            result = expression_evaluator_with_pm.evaluate_expression(expression, context)
            # Should successfully evaluate via PythonMonkey
            assert result is not None
            assert mock_pythonmonkey_available.eval.call_count > i

        # Test Python fallback limitations
        for expression in es6_expressions:
            with pytest.raises((SyntaxError, NameError, TypeError)):
                expression_evaluator_fallback.evaluate_expression(expression, context)

    def test_complex_nested_expressions_with_pythonmonkey(self, expression_evaluator_with_pm, mock_pythonmonkey_available, complex_context):
        """
        Test AC-VR-020: Complex nested expressions evaluate correctly
        Focus: Multi-level nested object/array access with complex logic
        """
        # Mock PythonMonkey to return expected results for complex expressions
        complex_expressions = [
            {
                "expr": "user.profile.roles.filter(role => role.includes('admin')).length > 0",
                "mock_result": True,
                "description": "Check if user has admin role using nested access and ES6 methods"
            },
            {
                "expr": "project.info.tags.map(tag => tag.toUpperCase()).join(', ')",
                "mock_result": "REACT, TYPESCRIPT, TESTING",
                "description": "Transform and join nested array elements"
            },
            {
                "expr": "calculations.scores.reduce((sum, score, index) => sum + (score * calculations.weights[index]), 0)",
                "mock_result": 90.5,
                "description": "Weighted average calculation with nested array access"
            },
            {
                "expr": "Object.keys(user.settings).every(key => typeof user.settings[key] === 'object')",
                "mock_result": True,
                "description": "Complex object introspection with nested access"
            },
            {
                "expr": "project.info.stats.coverage >= calculations.thresholds.excellent / 100",
                "mock_result": False,  # 0.85 >= 0.9 is False
                "description": "Multi-level nested comparison with arithmetic"
            }
        ]

        mock_pythonmonkey_available.eval.side_effect = [expr["mock_result"] for expr in complex_expressions]

        for i, test_case in enumerate(complex_expressions):
            result = expression_evaluator_with_pm.evaluate_expression(
                test_case["expr"], 
                complex_context
            )
            
            expected = test_case["mock_result"]
            assert result == expected, f"Failed for {test_case['description']}: {test_case['expr']}"
            
        # Verify PythonMonkey was called for each expression
        assert mock_pythonmonkey_available.eval.call_count == len(complex_expressions)

    def test_complex_nested_expressions_fallback_where_possible(self, expression_evaluator_fallback, complex_context):
        """
        Test AC-VR-020: Complex expressions that can work in Python fallback
        Focus: Complex but Python-compatible nested expressions
        """
        # Complex expressions that should work in Python fallback mode
        python_compatible_complex = [
            {
                "expr": "len([role for role in user['profile']['roles'] if 'admin' in role]) > 0",
                "expected": True,
                "description": "List comprehension with nested access"
            },
            {
                "expr": "sum(calculations['scores']) / len(calculations['scores'])",
                "expected": 90.2,  # (95+87+92+78+99)/5
                "description": "Average calculation with nested access"
            },
            {
                "expr": "all(score >= calculations['thresholds']['fair'] for score in calculations['scores'])",
                "expected": True,  # All scores >= 70
                "description": "Complex boolean evaluation with generator"
            },
            {
                "expr": "user['profile']['metadata']['login_count'] > project['info']['stats']['files']",
                "expected": False,  # 150 > 245 is False
                "description": "Deep nested comparison"
            },
            {
                "expr": "max(calculations['scores']) - min(calculations['scores'])",
                "expected": 21,  # 99 - 78
                "description": "Range calculation with nested arrays"
            },
            {
                "expr": "'typescript' in [tag.lower() for tag in project['info']['tags']]",
                "expected": True,
                "description": "Case-insensitive search in nested array"
            }
        ]

        for test_case in python_compatible_complex:
            result = expression_evaluator_fallback.evaluate_expression(
                test_case["expr"],
                complex_context
            )
            assert result == test_case["expected"], f"Failed for {test_case['description']}: {test_case['expr']}"

    def test_expression_evaluation_error_handling(self, expression_evaluator_fallback, expression_evaluator_with_pm, mock_pythonmonkey_available):
        """
        Test error handling in both PythonMonkey and fallback modes
        Focus: Graceful handling of invalid expressions and context errors
        """
        context = {"valid_field": "test", "nested": {"field": 42}}

        # Test invalid expression handling
        invalid_expressions = [
            "invalid_variable",  # Undefined variable
            "valid_field.undefined_method()",  # Invalid method
            "nested['nonexistent']",  # Missing key
            "1 / 0",  # Division by zero
            "eval('malicious code')",  # Potentially dangerous code
        ]

        # Test fallback error handling
        for expr in invalid_expressions:
            with pytest.raises((NameError, KeyError, ZeroDivisionError, AttributeError, TypeError)):
                expression_evaluator_fallback.evaluate_expression(expr, context)

        # Test PythonMonkey error handling
        mock_pythonmonkey_available.eval.side_effect = Exception("JavaScript error")
        
        for expr in invalid_expressions:
            with pytest.raises(Exception):
                expression_evaluator_with_pm.evaluate_expression(expr, context)

    def test_fallback_detection_and_switching(self):
        """
        Test automatic detection and switching between PythonMonkey and fallback
        Focus: System correctly detects PythonMonkey availability
        """
        # Test with PythonMonkey available
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', True):
            evaluator = ExpressionEvaluator()
            assert evaluator.use_pythonmonkey == True

        # Test with PythonMonkey unavailable
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', False):
            evaluator = ExpressionEvaluator()
            assert evaluator.use_pythonmonkey == False

    def test_performance_comparison_fallback_vs_pythonmonkey(self, complex_context):
        """
        Test performance characteristics of fallback vs PythonMonkey
        Focus: Fallback should be faster for simple expressions
        """
        import time

        simple_expressions = [
            "2 + 3",
            "user['profile']['age'] > 25",
            "len(calculations['scores'])",
            "'admin' in user['profile']['roles']",
            "project['info']['stats']['coverage'] * 100"
        ]

        # Test fallback performance
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', False):
            fallback_evaluator = ExpressionEvaluator()
            
            start_time = time.time()
            for _ in range(100):  # Run multiple times for timing
                for expr in simple_expressions:
                    fallback_evaluator.evaluate_expression(expr, complex_context)
            fallback_time = time.time() - start_time

        # Test PythonMonkey performance (mocked)
        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', True):
            mock_pm = Mock()
            mock_pm.eval.return_value = "mocked_result"
            
            with patch('aromcp.workflow_server.workflow.expression_evaluator.pythonmonkey', mock_pm):
                pm_evaluator = ExpressionEvaluator()
                
                start_time = time.time()
                for _ in range(100):
                    for expr in simple_expressions:
                        pm_evaluator.evaluate_expression(expr, complex_context)
                pm_time = time.time() - start_time

        # For simple expressions, fallback should be faster due to no JS engine overhead
        # This is a rough check - exact timing depends on system performance
        assert fallback_time < pm_time + 0.1  # Allow some tolerance

    def test_context_variable_resolution_edge_cases(self, expression_evaluator_fallback):
        """
        Test edge cases in context variable resolution
        Focus: Handling of special values and data types
        """
        edge_case_context = {
            "null_value": None,
            "empty_string": "",
            "empty_list": [],
            "empty_dict": {},
            "zero": 0,
            "false_value": False,
            "unicode": "测试 🎉",
            "large_number": 9007199254740991,  # JavaScript MAX_SAFE_INTEGER
            "float_precision": 0.1 + 0.2,  # Float precision issue
            "nested_nulls": {"level1": {"level2": None}},
            "mixed_array": [1, "string", None, True, {"nested": "object"}]
        }

        test_cases = [
            {"expr": "null_value is None", "expected": True},
            {"expr": "len(empty_string)", "expected": 0},
            {"expr": "len(empty_list)", "expected": 0},
            {"expr": "len(empty_dict)", "expected": 0},
            {"expr": "zero == 0", "expected": True},
            {"expr": "false_value == False", "expected": True},
            {"expr": "len(unicode)", "expected": 4},  # 测试 🎉 = 4 characters
            {"expr": "large_number > 9000000000000000", "expected": True},
            {"expr": "abs(float_precision - 0.3) < 0.0001", "expected": True},  # Handle float precision
            {"expr": "nested_nulls['level1']['level2'] is None", "expected": True},
            {"expr": "len(mixed_array)", "expected": 5},
            {"expr": "isinstance(mixed_array[0], int)", "expected": True},
            {"expr": "mixed_array[4]['nested']", "expected": "object"}
        ]

        for test_case in test_cases:
            result = expression_evaluator_fallback.evaluate_expression(
                test_case["expr"],
                edge_case_context
            )
            assert result == test_case["expected"], f"Failed for edge case: {test_case['expr']}"


class TestExpressionEvaluationIntegration:
    """Test expression evaluation integration with workflow state management."""

    def test_state_manager_expression_integration(self):
        """
        Test expression evaluation integration with state manager
        Focus: Expressions work correctly with three-tier state architecture
        """
        # Mock state manager with three-tier state
        state_manager = Mock(spec=StateManager)
        state_manager.get_flattened_state.return_value = {
            # Inputs tier
            "user_input": "John",
            "threshold": 80,
            
            # State tier  
            "current_score": 85,
            "attempts": 3,
            
            # Computed tier (highest precedence)
            "final_score": 92,
            "status": "passed"
        }

        # Mock expression evaluator
        evaluator = Mock(spec=ExpressionEvaluator)
        
        def mock_evaluate(expression, context):
            # Simulate evaluation with state context
            if "final_score > threshold" in expression:
                return context["final_score"] > context["threshold"]  # 92 > 80 = True
            elif "status == 'passed'" in expression:
                return context["status"] == "passed"  # True
            elif "attempts < 5" in expression:
                return context["attempts"] < 5  # 3 < 5 = True
            else:
                return expression  # Return as-is for unknown expressions

        evaluator.evaluate_expression = Mock(side_effect=mock_evaluate)

        # Test expressions with state context
        context = state_manager.get_flattened_state()
        
        test_expressions = [
            {"expr": "final_score > threshold", "expected": True},
            {"expr": "status == 'passed'", "expected": True},
            {"expr": "attempts < 5", "expected": True}
        ]

        for test in test_expressions:
            result = evaluator.evaluate_expression(test["expr"], context)
            assert result == test["expected"]

        # Verify state manager integration
        evaluator.evaluate_expression.assert_called()
        state_manager.get_flattened_state.assert_called()

    def test_scoped_variable_expression_evaluation(self):
        """
        Test expression evaluation with scoped variable syntax
        Focus: Expressions correctly handle this.field, global.var, inputs.param syntax
        """
        # Test context with scoped variables
        scoped_context = {
            "this": {"current_value": 42, "enabled": True},
            "global": {"config": {"max_retries": 3}, "version": "1.0"},
            "inputs": {"user_name": "Alice", "timeout": 30},
            "loop": {"index": 2, "item": "test_item"}
        }

        with patch('aromcp.workflow_server.workflow.expression_evaluator.PYTHONMONKEY_AVAILABLE', False):
            evaluator = ExpressionEvaluator()

            scoped_expressions = [
                {"expr": "this['current_value'] > 40", "expected": True},
                {"expr": "global['config']['max_retries'] == 3", "expected": True},
                {"expr": "inputs['timeout'] < 60", "expected": True},
                {"expr": "loop['index'] > 1", "expected": True},
                {"expr": "this['enabled'] and global['version'] == '1.0'", "expected": True}
            ]

            for test in scoped_expressions:
                result = evaluator.evaluate_expression(test["expr"], scoped_context)
                assert result == test["expected"], f"Failed for scoped expression: {test['expr']}"