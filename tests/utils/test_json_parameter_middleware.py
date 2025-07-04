"""Tests for JSON Parameter Middleware."""

import asyncio
from typing import Any
from unittest.mock import Mock

import pytest

from aromcp.utils.json_parameter_middleware import (
    JSONParameterMiddleware,
    debug_json_convert,
    json_convert,
)


class TestJSONParameterMiddleware:
    """Test JSONParameterMiddleware class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.middleware = JSONParameterMiddleware()
        self.debug_middleware = JSONParameterMiddleware(debug=True)

    def test_init_default(self):
        """Test middleware initialization with default parameters."""
        middleware = JSONParameterMiddleware()
        assert middleware.debug is False

    def test_init_debug(self):
        """Test middleware initialization with debug enabled."""
        middleware = JSONParameterMiddleware(debug=True)
        assert middleware.debug is True

    def test_should_try_json_parse_list_type(self):
        """Test JSON parsing detection for list types."""
        # String values that look like JSON
        assert self.middleware._should_try_json_parse('["item1", "item2"]', list[str])
        assert self.middleware._should_try_json_parse('[]', list)

        # Non-string values should not be parsed
        assert not self.middleware._should_try_json_parse(['actual', 'list'], list[str])
        assert not self.middleware._should_try_json_parse(None, list[str])

    def test_should_try_json_parse_dict_type(self):
        """Test JSON parsing detection for dict types."""
        # String values that look like JSON
        assert self.middleware._should_try_json_parse('{"key": "value"}', dict[str, str])
        assert self.middleware._should_try_json_parse('{}', dict)

        # Non-string values should not be parsed
        assert not self.middleware._should_try_json_parse({'actual': 'dict'}, dict[str, str])

    def test_should_try_json_parse_json_like_strings(self):
        """Test JSON parsing detection for JSON-like strings."""
        # Should detect JSON-like strings even without explicit types
        assert self.middleware._should_try_json_parse('["test"]', str)
        assert self.middleware._should_try_json_parse('{"test": 1}', str)
        assert self.middleware._should_try_json_parse('"string"', str)

        # Should not detect regular strings
        assert not self.middleware._should_try_json_parse('regular string', str)
        assert not self.middleware._should_try_json_parse('', str)

    def test_convert_value_list_from_json(self):
        """Test converting JSON string to list."""
        result = self.middleware._convert_value('["a", "b", "c"]', list[str], "test_param")
        assert result == ["a", "b", "c"]
        assert isinstance(result, list)

    def test_convert_value_dict_from_json(self):
        """Test converting JSON string to dict."""
        result = self.middleware._convert_value('{"key": "value"}', dict[str, str], "test_param")
        assert result == {"key": "value"}
        assert isinstance(result, dict)

    def test_convert_value_set_from_json(self):
        """Test converting JSON string to set."""
        result = self.middleware._convert_value('["a", "b", "c"]', set[str], "test_param")
        assert result == {"a", "b", "c"}
        assert isinstance(result, set)

    def test_convert_value_tuple_from_json(self):
        """Test converting JSON string to tuple."""
        result = self.middleware._convert_value('["a", "b", "c"]', tuple[str, ...], "test_param")
        assert result == ("a", "b", "c")
        assert isinstance(result, tuple)

    def test_convert_value_none_handling(self):
        """Test handling of None values."""
        result = self.middleware._convert_value(None, list[str], "test_param")
        assert result is None

    def test_convert_value_union_types(self):
        """Test handling of Union types (e.g., str | list[str])."""
        # Test with list value in union
        result = self.middleware._convert_value(
            '["a", "b"]', str | list[str], "test_param"
        )
        assert result == ["a", "b"]

        # Test with string value in union
        result = self.middleware._convert_value(
            'plain string', str | list[str], "test_param"
        )
        assert result == 'plain string'

    def test_convert_value_invalid_json_error(self):
        """Test error handling for invalid JSON."""
        with pytest.raises(ValueError) as exc_info:
            self.middleware._convert_value(
                '{"invalid": json}', dict[str, str], "test_param"
            )

        assert "Invalid JSON in parameter 'test_param'" in str(exc_info.value)

    def test_convert_value_type_mismatch_error(self):
        """Test error handling for type mismatches."""
        with pytest.raises(ValueError) as exc_info:
            self.middleware._convert_value(
                '["list", "data"]', dict[str, str], "test_param"
            )

        assert "must be a dict" in str(exc_info.value)

    def test_convert_value_string_instead_of_list_error(self):
        """Test error handling when invalid JSON string is passed to list parameter."""
        # For list types, the middleware will try to parse as JSON first
        with pytest.raises(ValueError) as exc_info:
            self.middleware._convert_value(
                'plain string not json', list[str], "test_param"
            )

        assert "Invalid JSON in parameter 'test_param'" in str(exc_info.value)

    def test_convert_value_string_instead_of_dict_error(self):
        """Test error handling when invalid JSON string is passed to dict parameter."""
        # For dict types, the middleware will try to parse as JSON first
        with pytest.raises(ValueError) as exc_info:
            self.middleware._convert_value(
                'plain string not json', dict[str, str], "test_param"
            )

        assert "Invalid JSON in parameter 'test_param'" in str(exc_info.value)

    def test_convert_decorator_basic_function(self):
        """Test the convert decorator with a basic function."""
        @self.middleware.convert
        def test_func(items: list[str]) -> dict[str, int]:
            return {"count": len(items)}

        # Test with JSON string
        result = test_func('["item1", "item2", "item3"]')
        assert result == {"count": 3}

        # Test with actual list
        result = test_func(["item1", "item2"])
        assert result == {"count": 2}

    def test_convert_decorator_error_response(self):
        """Test that decorator returns structured error response for invalid input."""
        @self.middleware.convert
        def test_func(items: list[str]) -> dict[str, int]:
            return {"count": len(items)}

        # Test with invalid JSON
        result = test_func('{"invalid": json}')
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"
        assert "Invalid JSON" in result["error"]["message"]

    def test_convert_decorator_mixed_parameters(self):
        """Test decorator with mixed parameter types."""
        @self.middleware.convert
        def test_func(name: str, items: list[str], metadata: dict[str, Any]) -> dict:
            return {
                "name": name,
                "item_count": len(items),
                "has_metadata": bool(metadata)
            }

        result = test_func(
            name="test",
            items='["a", "b", "c"]',
            metadata='{"version": 1}'
        )

        assert result["name"] == "test"
        assert result["item_count"] == 3
        assert result["has_metadata"] is True

    def test_convert_decorator_skip_context_params(self):
        """Test that decorator skips parameters not in type hints (like ctx)."""
        @self.middleware.convert
        def test_func(ctx, items: list[str]) -> dict:
            return {"count": len(items), "ctx_type": type(ctx).__name__}

        # Mock context object
        mock_ctx = Mock()
        result = test_func(mock_ctx, '["item1", "item2"]')

        assert result["count"] == 2
        assert "ctx_type" in result

    def test_convert_decorator_with_defaults(self):
        """Test decorator with function parameters that have defaults."""
        @self.middleware.convert
        def test_func(items: list[str], limit: int = 10) -> dict:
            return {"count": min(len(items), limit)}

        # Test with only required parameter
        result = test_func('["a", "b", "c"]')
        assert result["count"] == 3

        # Test with both parameters
        result = test_func('["a", "b", "c"]', 2)
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_convert_decorator_async_function(self):
        """Test the convert decorator with async functions."""
        @self.middleware.convert
        async def async_test_func(items: list[str]) -> dict[str, int]:
            await asyncio.sleep(0)  # Simulate async operation
            return {"count": len(items)}

        # Test with JSON string
        result = await async_test_func('["item1", "item2", "item3"]')
        assert result == {"count": 3}

    @pytest.mark.asyncio
    async def test_convert_decorator_async_error_response(self):
        """Test that async decorator returns structured error response."""
        @self.middleware.convert
        async def async_test_func(items: list[str]) -> dict[str, int]:
            return {"count": len(items)}

        # Test with invalid JSON
        result = await async_test_func('{"invalid": json}')
        assert "error" in result
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_debug_mode_output(self, capsys):
        """Test debug mode prints conversion information."""
        @self.debug_middleware.convert
        def test_func(items: list[str]) -> dict:
            return {"count": len(items)}

        test_func('["item1", "item2"]')

        captured = capsys.readouterr()
        assert "[JSONMiddleware]" in captured.out
        assert "Converted items from JSON string to list" in captured.out


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_json_convert_decorator(self):
        """Test json_convert convenience decorator."""
        @json_convert
        def test_func(items: list[str]) -> dict[str, int]:
            return {"count": len(items)}

        result = test_func('["item1", "item2"]')
        assert result == {"count": 2}

    def test_debug_json_convert_decorator(self, capsys):
        """Test debug_json_convert convenience decorator."""
        @debug_json_convert
        def test_func(items: list[str]) -> dict[str, int]:
            return {"count": len(items)}

        result = test_func('["item1", "item2"]')
        assert result == {"count": 2}

        captured = capsys.readouterr()
        assert "[JSONMiddleware]" in captured.out


class TestEdgeCases:
    """Test edge cases and complex scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.middleware = JSONParameterMiddleware()

    def test_empty_json_structures(self):
        """Test handling of empty JSON structures."""
        # Empty list
        result = self.middleware._convert_value('[]', list[str], "test_param")
        assert result == []

        # Empty dict
        result = self.middleware._convert_value('{}', dict[str, str], "test_param")
        assert result == {}

    def test_nested_json_structures(self):
        """Test handling of nested JSON structures."""
        nested_data = (
            '{"users": [{"name": "John", "age": 30}, '
            '{"name": "Jane", "age": 25}]}'
        )
        result = self.middleware._convert_value(nested_data, dict, "test_param")

        expected = {
            "users": [
                {"name": "John", "age": 30},
                {"name": "Jane", "age": 25}
            ]
        }
        assert result == expected

    def test_complex_union_types(self):
        """Test complex union type scenarios."""
        # Test with multiple union options
        result = self.middleware._convert_value(
            '["a", "b"]', str | list[str] | dict, "test_param"
        )
        assert result == ["a", "b"]

        # Test fallback behavior
        result = self.middleware._convert_value('plain string', int | str, "test_param")
        assert result == 'plain string'

    def test_json_string_values(self):
        """Test that JSON strings are handled appropriately for string types."""
        # When expecting a string type, JSON strings should be parsed if they look
        # like JSON
        result = self.middleware._convert_value('"hello world"', str, "test_param")
        # The middleware will parse JSON strings that look like JSON
        assert result == "hello world"

    def test_numeric_json_values(self):
        """Test that numeric JSON values are handled correctly when expected."""
        # This should not be converted since we're not expecting a numeric type
        result = self.middleware._convert_value('42', str, "test_param")
        assert result == '42'

    def test_boolean_json_values(self):
        """Test boolean JSON values."""
        result = self.middleware._convert_value('true', str, "test_param")
        assert result == 'true'  # Should remain as string since type is str

    def test_whitespace_handling(self):
        """Test handling of JSON with extra whitespace."""
        result = self.middleware._convert_value(
            '  ["a", "b"]  ', list[str], "test_param"
        )
        assert result == ["a", "b"]

    def test_function_with_no_type_hints(self):
        """Test decorator behavior with functions that have no type hints."""
        @self.middleware.convert
        def test_func(items):
            return {"received": items}

        # Should pass through unchanged
        result = test_func('["a", "b"]')
        assert result == {"received": '["a", "b"]'}

    def test_partial_type_hints(self):
        """Test decorator with functions that have partial type hints."""
        @self.middleware.convert
        def test_func(typed_param: list[str], untyped_param):
            return {
                "typed_count": len(typed_param),
                "untyped": untyped_param
            }

        result = test_func('["a", "b"]', "unchanged")
        assert result["typed_count"] == 2
        assert result["untyped"] == "unchanged"
