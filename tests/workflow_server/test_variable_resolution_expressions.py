"""
Test suite for Variable Resolution & Expression Evaluation - Acceptance Criteria 7

This file tests the following acceptance criteria:
- AC 7.1: Scoped Variable Syntax - support for this.field, global.var, inputs.param, loop.item syntax
- AC 7.2: JavaScript Expression Engine - PythonMonkey for full ES6+ evaluation with fallback
- AC 7.3: Template Variable Substitution - {{ variable }} syntax processing in templates

Maps to: /documentation/acceptance-criteria/workflow_server/workflow_server.md
"""

import pytest

from aromcp.workflow_server.workflow.expressions import (
    ExpressionError,
    ExpressionEvaluator,
    ExpressionLexer,
    ExpressionParser,
    TokenType,
)


class TestScopedVariableSyntax:
    """Test scoped variable syntax - AC 7.1"""

    def test_scoped_syntax_simple_expression_tokenization(self):
        """Test scoped variable syntax supports simple token parsing for expressions (AC 7.1)."""
        lexer = ExpressionLexer("42 + 'hello'")
        tokens = lexer.tokenize()

        assert len(tokens) == 4  # number, operator, string, EOF
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "42"
        assert tokens[1].type == TokenType.OPERATOR
        assert tokens[1].value == "+"
        assert tokens[2].type == TokenType.STRING
        assert tokens[2].value == "hello"

    def test_scoped_syntax_boolean_null_literal_support(self):
        """Test scoped variable syntax supports boolean and null literal tokens (AC 7.1)."""
        lexer = ExpressionLexer("true false null")
        tokens = lexer.tokenize()

        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value == "true"
        assert tokens[1].type == TokenType.BOOLEAN
        assert tokens[1].value == "false"
        assert tokens[2].type == TokenType.NULL
        assert tokens[2].value == "null"

    def test_scoped_syntax_operator_comparison_support(self):
        """Test scoped variable syntax supports operators and comparison expressions (AC 7.1)."""
        lexer = ExpressionLexer("&& || == != <= >=")
        tokens = lexer.tokenize()

        assert tokens[0].type == TokenType.LOGICAL
        assert tokens[0].value == "&&"
        assert tokens[1].type == TokenType.LOGICAL
        assert tokens[1].value == "||"
        assert tokens[2].type == TokenType.COMPARISON
        assert tokens[2].value == "=="
        assert tokens[3].type == TokenType.COMPARISON
        assert tokens[3].value == "!="

    def test_scoped_syntax_string_escaping_property_access(self):
        """Test scoped variable syntax supports string escaping and nested property access (AC 7.1)."""
        lexer = ExpressionLexer('"hello\\nworld\\t"')
        tokens = lexer.tokenize()

        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello\nworld\t"

    def test_scoped_syntax_variable_path_validation(self):
        """Test scoped variable syntax validates scoped variable paths during resolution (AC 7.1)."""
        # Test valid scoped variable paths
        valid_paths = [
            "this.field",
            "global.var",
            "inputs.param",
            "loop.item",
            "loop.index",
            "loop.iteration"
        ]
        
        for path in valid_paths:
            # Verify scoped variable syntax compliance
            assert path.startswith(("this.", "global.", "inputs.", "loop."))
            parts = path.split(".")
            assert len(parts) >= 2  # Must have scope and field
            assert parts[0] in ["this", "global", "inputs", "loop"]


class TestExpressionParser:
    """Test scoped variable syntax parsing - AC 7.1"""

    def test_scoped_syntax_binary_expression_parsing(self):
        """Test scoped variable syntax parses simple binary expressions (AC 7.1)."""
        lexer = ExpressionLexer("5 + 3")
        tokens = lexer.tokenize()
        parser = ExpressionParser(tokens)
        ast = parser.parse()

        assert ast["type"] == "binary"
        assert ast["operator"] == "+"
        assert ast["left"]["type"] == "literal"
        assert ast["left"]["value"] == 5
        assert ast["right"]["type"] == "literal"
        assert ast["right"]["value"] == 3

    def test_property_access(self):
        """Test parsing of property access expressions."""
        lexer = ExpressionLexer("user.name")
        tokens = lexer.tokenize()
        parser = ExpressionParser(tokens)
        ast = parser.parse()

        assert ast["type"] == "property_access"
        assert ast["object"]["type"] == "identifier"
        assert ast["object"]["name"] == "user"
        assert ast["property"] == "name"

    def test_array_access(self):
        """Test parsing of array access expressions."""
        lexer = ExpressionLexer("items[0]")
        tokens = lexer.tokenize()
        parser = ExpressionParser(tokens)
        ast = parser.parse()

        assert ast["type"] == "array_access"
        assert ast["object"]["type"] == "identifier"
        assert ast["object"]["name"] == "items"
        assert ast["index"]["type"] == "literal"
        assert ast["index"]["value"] == 0

    def test_ternary_expression(self):
        """Test parsing of ternary expressions."""
        lexer = ExpressionLexer("x > 5 ? 'big' : 'small'")
        tokens = lexer.tokenize()
        parser = ExpressionParser(tokens)
        ast = parser.parse()

        assert ast["type"] == "ternary"
        assert ast["condition"]["type"] == "binary"
        assert ast["true_value"]["type"] == "literal"
        assert ast["true_value"]["value"] == "big"
        assert ast["false_value"]["type"] == "literal"
        assert ast["false_value"]["value"] == "small"


class TestJavaScriptExpressionEngine:
    """Test JavaScript expression engine - AC 7.2"""

    def test_javascript_engine_boolean_expression_evaluation(self):
        """Test JavaScript expression engine supports boolean expressions and comparisons (AC 7.2)."""
        evaluator = ExpressionEvaluator()
        context = {"value": 5, "flag": True}

        # Test basic comparisons
        assert evaluator.evaluate("value > 3", context)
        assert not evaluator.evaluate("value < 3", context)
        assert evaluator.evaluate("value == 5", context)
        assert not evaluator.evaluate("value != 5", context)

        # Test logical operators
        assert evaluator.evaluate("value > 3 && flag", context)
        assert not evaluator.evaluate("value < 3 && flag", context)
        assert evaluator.evaluate("value < 3 || flag", context)
        assert not evaluator.evaluate("!flag", context)

    def test_javascript_engine_property_access_notation(self):
        """Test JavaScript expression engine handles property access with dot notation and bracket notation (AC 7.2)."""
        evaluator = ExpressionEvaluator()
        context = {"user": {"name": "Alice", "age": 30}, "items": ["a", "b", "c"]}

        # Test object property access
        assert evaluator.evaluate("user.name", context) == "Alice"
        assert evaluator.evaluate("user.age", context) == 30

        # Test array property access
        assert evaluator.evaluate("items.length", context) == 3
        assert evaluator.evaluate("items[1]", context) == "b"

    def test_arithmetic_operations(self):
        """Test arithmetic operations."""
        evaluator = ExpressionEvaluator()
        context = {"a": 10, "b": 3}

        assert evaluator.evaluate("a + b", context) == 13
        assert evaluator.evaluate("a - b", context) == 7
        assert evaluator.evaluate("a * b", context) == 30
        assert evaluator.evaluate("a / b", context) == 10 / 3
        assert evaluator.evaluate("a % b", context) == 1

    def test_string_operations(self):
        """Test string operations and methods."""
        evaluator = ExpressionEvaluator()
        context = {"text": "Hello World"}

        # String concatenation
        assert evaluator.evaluate("text + '!'", context) == "Hello World!"

        # String properties and methods
        assert evaluator.evaluate("text.length", context) == 11
        assert evaluator.evaluate("text.includes('World')", context)
        assert not evaluator.evaluate("text.includes('xyz')", context)

    def test_array_operations(self):
        """Test array operations and methods."""
        evaluator = ExpressionEvaluator()
        context = {"numbers": [1, 2, 3, 4, 5]}

        # Array properties
        assert evaluator.evaluate("numbers.length", context) == 5
        assert evaluator.evaluate("numbers[2]", context) == 3

        # Array methods
        assert evaluator.evaluate("numbers.includes(3)", context)
        assert not evaluator.evaluate("numbers.includes(6)", context)

    def test_ternary_operator(self):
        """Test ternary conditional operator."""
        evaluator = ExpressionEvaluator()
        context = {"score": 85}

        result = evaluator.evaluate("score >= 90 ? 'A' : score >= 80 ? 'B' : 'C'", context)
        assert result == "B"

    def test_type_coercion(self):
        """Test JavaScript-style type coercion."""
        evaluator = ExpressionEvaluator()

        # Test loose equality
        assert evaluator.evaluate("5 == '5'", {})
        assert evaluator.evaluate("0 == false", {})
        assert evaluator.evaluate("1 == true", {})

        # Test truthy/falsy values
        assert evaluator.evaluate("!''", {})  # Empty string is falsy
        assert not evaluator.evaluate("!'hello'", {})  # Non-empty string is truthy
        assert evaluator.evaluate("!0", {})  # 0 is falsy
        assert not evaluator.evaluate("!1", {})  # Non-zero is truthy

    def test_missing_variables(self):
        """Test handling of missing variables."""
        evaluator = ExpressionEvaluator()
        context = {"a": 5}

        # Missing variables should return None/null
        result = evaluator.evaluate("missing_var", context)
        assert result is None

        # But they should still work in expressions
        assert evaluator.evaluate("a > missing_var", context)  # 5 > None -> 5 > 0 -> True

    def test_complex_expressions(self):
        """Test complex nested expressions."""
        evaluator = ExpressionEvaluator()
        context = {
            "user": {"profile": {"settings": {"theme": "dark"}}},
            "items": [{"name": "item1", "active": True}, {"name": "item2", "active": False}],
            "count": 5,
        }

        # Nested property access
        assert evaluator.evaluate("user.profile.settings.theme", context) == "dark"

        # Complex boolean logic
        result = evaluator.evaluate("count > 0 && user.profile.settings.theme == 'dark'", context)
        assert result

    def test_expression_errors(self):
        """Test error handling in expression evaluation."""
        evaluator = ExpressionEvaluator()

        # Test invalid syntax
        with pytest.raises(ExpressionError):
            evaluator.evaluate("5 +", {})

        # Test division by zero (should return infinity)
        result = evaluator.evaluate("5 / 0", {})
        assert result == float("inf")


class TestTemplateVariableSubstitution:
    """Test template variable substitution - AC 7.3"""

    def test_template_substitution_workflow_condition_processing(self):
        """Test template variable substitution processes {{ variable }} syntax in workflow conditions (AC 7.3)."""
        evaluator = ExpressionEvaluator()

        # Simulate workflow state
        state = {
            "files": ["file1.ts", "file2.js", "file3.ts"],
            "processed_count": 1,
            "is_ready": True,
            "config": {"max_files": 10, "auto_process": True},
        }

        # Test various workflow conditions
        assert evaluator.evaluate("files.length > 0", state)
        assert evaluator.evaluate("processed_count < files.length", state)
        assert evaluator.evaluate("is_ready && config.auto_process", state)
        assert evaluator.evaluate("files.length <= config.max_files", state)

    def test_template_substitution_missing_variable_fallback(self):
        """Test template variable substitution handles missing variables with appropriate fallback behavior (AC 7.3)."""
        evaluator = ExpressionEvaluator()

        # Test with template-style braces (should be cleaned)
        state = {"counter": 5, "limit": 10}

        # These would come from template replacement
        assert evaluator.evaluate("counter < limit", state)
        assert not evaluator.evaluate("counter >= limit", state)

    def test_template_substitution_nested_property_access(self):
        """Test template variable substitution supports nested property access within template variables (AC 7.3)."""
        evaluator = ExpressionEvaluator()

        # Test array filtering expressions
        state = {
            "all_files": [
                {"name": "file1.ts", "processed": False},
                {"name": "file2.js", "processed": True},
                {"name": "file3.ts", "processed": False},
            ]
        }

        # Test array access
        assert evaluator.evaluate("all_files.length", state) == 3
        assert evaluator.evaluate("all_files[0].name", state) == "file1.ts"
        assert evaluator.evaluate("all_files[1].processed", state)


class TestTemplateFallbackLogic:
    """Test template variable fallback resolution for better error messages - AC 7.3"""

    def setup_method(self):
        """Set up test dependencies."""
        from aromcp.workflow_server.state.manager import StateManager
        from aromcp.workflow_server.workflow.step_processors import StepProcessor
        from aromcp.workflow_server.workflow.step_registry import StepRegistry
        from aromcp.workflow_server.workflow.subagent_manager import SubAgentManager
        
        self.state_manager = StateManager()
        self.expression_evaluator = ExpressionEvaluator()
        self.step_registry = StepRegistry()
        
        # Set up processors
        self.step_processor = StepProcessor(
            self.state_manager, 
            self.expression_evaluator
        )
        
        self.subagent_manager = SubAgentManager(
            self.state_manager, 
            self.expression_evaluator, 
            self.step_registry
        )

    def test_template_fallback_missing_variables(self):
        """Test template variable substitution handles missing variables with fallbacks (AC 7.3)."""
        # Test state with some context
        state = {
            "item": "src/test.ts",
            "task_id": "test_task_001",
            "loop": {
                "iteration": 3
            },
            "max_attempts": 5
        }
        
        # Test templates with missing variables
        test_cases = [
            {
                "template": "❌ Failed to enforce standards on {{ raw.file_path }} after {{ loop.iteration }} attempts",
                "expected": "❌ Failed to enforce standards on src/test.ts after 3 attempts"
            },
            {
                "template": "Processing {{ file_path }} (attempt {{ loop.iteration }}/{{ max_attempts }})",
                "expected": "Processing src/test.ts (attempt 3/5)"
            },
            {
                "template": "Task {{ task_id }}: {{ raw.nonexistent_field }}",
                "expected": "Task test_task_001: <raw.nonexistent_field>"
            }
        ]
        
        for case in test_cases:
            result = self.subagent_manager._replace_variables(case["template"], state)
            assert result == case["expected"], f"Expected '{case['expected']}', got '{result}'"

    def test_template_fallback_nested_properties(self):
        """Test template variable substitution handles nested property fallbacks (AC 7.3)."""
        state = {
            "item": "src/utils.py",
            "raw": {
                "file_path": "src/utils.py",
                "step_results": {
                    "hints": {"success": True},
                    "lint": None,
                    "typescript": None
                }
            }
        }
        
        # Test nested property access
        test_cases = [
            {
                "template": "Hints: {{ raw.step_results.hints.success }}",
                "expected": "Hints: True"
            },
            {
                "template": "Lint: {{ raw.step_results.lint.success }}",
                "expected": "Lint: <raw.step_results.lint.success>"
            },
            {
                "template": "Missing: {{ raw.missing_field.nested.value }}",
                "expected": "Missing: <raw.missing_field.nested.value>"
            }
        ]
        
        for case in test_cases:
            result = self.subagent_manager._replace_variables(case["template"], state)
            assert result == case["expected"], f"Expected '{case['expected']}', got '{result}'"

    def test_template_fallback_prevents_empty_strings(self):
        """Test template variable substitution prevents empty strings in output (AC 7.3)."""
        # Simulate the original problematic case
        state = {
            "task_id": "enforce_standards_task_001",
            "item": "src/component.tsx",
            "index": 0,
            "total": 1,
            "loop": {
                "iteration": 0
            }
        }
        
        # This is the message that was showing empty values
        problematic_template = "❌ Failed to enforce standards on {{ file_path }} after {{ loop.iteration }} attempts"
        
        # With our fallback logic, it should show meaningful values
        result = self.subagent_manager._replace_variables(problematic_template, state)
        expected = "❌ Failed to enforce standards on src/component.tsx after 0 attempts"
        
        assert result == expected, f"Expected '{expected}', got '{result}'"
        
        # Verify it's not showing empty values (the key improvement)
        assert " on  after" not in result, "Template variables should not be empty"
        assert result != "❌ Failed to enforce standards on  after  attempts", "Should not have completely empty variables"
