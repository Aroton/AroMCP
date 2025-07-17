"""Tests for expression evaluation engine."""

import pytest

from aromcp.workflow_server.workflow.expressions import (
    ExpressionError,
    ExpressionEvaluator,
    ExpressionLexer,
    ExpressionParser,
    TokenType,
)


class TestExpressionLexer:
    """Test the expression tokenizer."""

    def test_simple_tokens(self):
        """Test tokenization of simple tokens."""
        lexer = ExpressionLexer("42 + 'hello'")
        tokens = lexer.tokenize()

        assert len(tokens) == 4  # number, operator, string, EOF
        assert tokens[0].type == TokenType.NUMBER
        assert tokens[0].value == "42"
        assert tokens[1].type == TokenType.OPERATOR
        assert tokens[1].value == "+"
        assert tokens[2].type == TokenType.STRING
        assert tokens[2].value == "hello"

    def test_boolean_and_null_literals(self):
        """Test tokenization of boolean and null literals."""
        lexer = ExpressionLexer("true false null")
        tokens = lexer.tokenize()

        assert tokens[0].type == TokenType.BOOLEAN
        assert tokens[0].value == "true"
        assert tokens[1].type == TokenType.BOOLEAN
        assert tokens[1].value == "false"
        assert tokens[2].type == TokenType.NULL
        assert tokens[2].value == "null"

    def test_operators_and_comparisons(self):
        """Test tokenization of operators and comparisons."""
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

    def test_string_escaping(self):
        """Test string tokenization with escape sequences."""
        lexer = ExpressionLexer('"hello\\nworld\\t"')
        tokens = lexer.tokenize()

        assert tokens[0].type == TokenType.STRING
        assert tokens[0].value == "hello\nworld\t"


class TestExpressionParser:
    """Test the expression parser."""

    def test_simple_binary_expression(self):
        """Test parsing of simple binary expressions."""
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


class TestExpressionEvaluator:
    """Test expression evaluation."""

    def test_boolean_expressions(self):
        """Test expression evaluation with boolean logic."""
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

    def test_property_access(self):
        """Test nested property access."""
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


class TestExpressionIntegration:
    """Integration tests for expression evaluation."""

    def test_workflow_condition_evaluation(self):
        """Test expression evaluation in workflow conditions."""
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

    def test_template_variable_conditions(self):
        """Test conditions that might come from template variables."""
        evaluator = ExpressionEvaluator()

        # Test with template-style braces (should be cleaned)
        state = {"counter": 5, "limit": 10}

        # These would come from template replacement
        assert evaluator.evaluate("counter < limit", state)
        assert not evaluator.evaluate("counter >= limit", state)

    def test_foreach_item_expressions(self):
        """Test expressions used in foreach loops."""
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
