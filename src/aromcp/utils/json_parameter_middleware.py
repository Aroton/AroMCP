"""JSON Parameter Middleware for FastMCP.

This module provides decorator-based middleware that automatically converts
JSON string parameters to their appropriate Python types. This solves the
issue where MCP clients (like Claude Code) pass lists/dicts as JSON strings
instead of native Python types.
"""

import functools
import inspect
import json
import types
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


class JSONParameterMiddleware:
    """
    Middleware class that intercepts FastMCP tool parameters and automatically
    converts JSON strings to their appropriate Python types.

    This solves the issue where Claude Code (or other MCP clients) pass
    lists/dicts as JSON strings instead of native Python types.

    Usage:
        from fastmcp import FastMCP

        mcp = FastMCP("my-server")
        middleware = JSONParameterMiddleware()

        @mcp.tool()
        @middleware.convert
        def get_files(patterns: list[str]) -> dict:
            # patterns will be automatically converted from JSON string to list
            return {"files": patterns}
    """

    def __init__(self, debug: bool = False):
        """
        Initialize the middleware.

        Args:
            debug: If True, print debug information about conversions
        """
        self.debug = debug

    def _should_try_json_parse(self, value: Any, expected_type: type) -> bool:
        """
        Determine if we should attempt to parse a value as JSON.

        Args:
            value: The actual value received
            expected_type: The expected type from the function signature

        Returns:
            True if we should attempt JSON parsing
        """
        # Only try to parse strings
        if not isinstance(value, str):
            return False

        # Get the origin type (e.g., list from list[str])
        origin = get_origin(expected_type)

        # Check if expected type is a collection that could be JSON
        if origin in (list, dict, set, tuple):
            return True

        # Check for non-generic list/dict types
        if expected_type in (list, dict, set, tuple):
            return True

        # Check if it's a Mapping or Sequence type
        if origin and issubclass(origin, Mapping | Sequence):
            return True

        # Check if the string looks like JSON
        value_stripped = value.strip()
        if value_stripped.startswith(("[", "{", '"')) and value_stripped.endswith(("]", "}", '"')):
            return True

        return False

    def _convert_value(self, value: Any, expected_type: type, param_name: str) -> Any:
        """
        Convert a value to the expected type, parsing JSON if necessary.

        Args:
            value: The value to convert
            expected_type: The expected type
            param_name: Parameter name (for debugging)

        Returns:
            The converted value

        Raises:
            ValueError: If JSON parsing fails with an invalid format
        """
        # Handle None/Optional types
        if value is None:
            return None

        # Get origin for generic types
        origin = get_origin(expected_type)

        # Handle Union types (e.g., str | list[str], list[str] | None)
        if origin is types.UnionType:  # Union type in Python 3.10+
            args = get_args(expected_type)
            last_error = None
            # Try each type in the union
            for arg_type in args:
                if arg_type is type(None):  # Skip None in Optional types
                    continue
                try:
                    converted = self._convert_value(value, arg_type, param_name)
                    # If conversion succeeded, return the result
                    return converted
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    last_error = e
                    continue
            # If no conversion worked and we have an error, raise it
            if last_error:
                raise last_error
            # Otherwise return original value
            return value

        # Check if we should try JSON parsing
        if self._should_try_json_parse(value, expected_type):
            try:
                parsed = json.loads(value)

                if self.debug:
                    print(f"[JSONMiddleware] Converted {param_name} from JSON string to {type(parsed).__name__}")  # noqa: T201

                # Validate the parsed type matches expected type
                if origin:
                    # Handle generic types like list[str], dict[str, int]
                    if origin is list and isinstance(parsed, list):
                        return parsed
                    elif origin is dict and isinstance(parsed, dict):
                        return parsed
                    elif origin is set and isinstance(parsed, list):
                        return set(parsed)
                    elif origin is tuple and isinstance(parsed, list):
                        return tuple(parsed)
                    elif issubclass(origin, Mapping) and isinstance(parsed, dict):
                        return parsed
                    elif issubclass(origin, Sequence) and isinstance(parsed, list):
                        return parsed
                else:
                    # Handle non-generic types
                    if expected_type is list and isinstance(parsed, list):
                        return parsed
                    elif expected_type is dict and isinstance(parsed, dict):
                        return parsed
                    elif expected_type is set and isinstance(parsed, list):
                        return set(parsed)
                    elif expected_type is tuple and isinstance(parsed, list):
                        return tuple(parsed)
                    elif expected_type is str and isinstance(parsed, str):
                        return parsed

                # If parsed type doesn't match expected, raise error
                if origin:
                    expected_name = f"{origin.__name__}"
                else:
                    expected_name = expected_type.__name__

                raise ValueError(
                    f"Parameter '{param_name}' must be a {expected_name}, got {type(parsed).__name__} from JSON"
                )

            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in parameter '{param_name}': {e}") from e

        # For list/dict parameters, validate the type even if not JSON
        if expected_type in (list, dict) or origin in (list, dict):
            if expected_type is list or origin is list:
                if not isinstance(value, list):
                    # If it's a string that doesn't look like JSON, it's probably an error
                    if isinstance(value, str):
                        raise ValueError(
                            f"Parameter '{param_name}' expected list but got string. "
                            f"If this is JSON, check the format: {value}"
                        )
            elif expected_type is dict or origin is dict:
                if not isinstance(value, dict):
                    # If it's a string that doesn't look like JSON, it's probably an error
                    if isinstance(value, str):
                        raise ValueError(
                            f"Parameter '{param_name}' expected dict but got string. "
                            f"If this is JSON, check the format: {value}"
                        )

        return value

    def convert(self, func: F) -> F:
        """
        Decorator that wraps a function to automatically convert JSON parameters.

        Args:
            func: The function to wrap

        Returns:
            The wrapped function
        """
        # Get function signature and type hints
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Convert args to kwargs for easier processing
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Process each parameter
            converted_kwargs = {}
            for param_name, param_value in bound_args.arguments.items():
                # Skip special parameters like 'ctx' (Context)
                if param_name not in type_hints:
                    converted_kwargs[param_name] = param_value
                    continue

                expected_type = type_hints[param_name]
                try:
                    converted_value = self._convert_value(param_value, expected_type, param_name)
                    converted_kwargs[param_name] = converted_value
                except ValueError as e:
                    # Return structured error response for invalid parameters
                    return {"error": {"code": "INVALID_INPUT", "message": str(e)}}

            # Call the original function with converted parameters
            return func(**converted_kwargs)

        # For async functions
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Convert args to kwargs for easier processing
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                # Process each parameter
                converted_kwargs = {}
                for param_name, param_value in bound_args.arguments.items():
                    # Skip special parameters like 'ctx' (Context)
                    if param_name not in type_hints:
                        converted_kwargs[param_name] = param_value
                        continue

                    expected_type = type_hints[param_name]
                    try:
                        converted_value = self._convert_value(param_value, expected_type, param_name)
                        converted_kwargs[param_name] = converted_value
                    except ValueError as e:
                        # Return structured error response for invalid parameters
                        return {"error": {"code": "INVALID_INPUT", "message": str(e)}}

                # Call the original function with converted parameters
                return await func(**converted_kwargs)

            return async_wrapper  # type: ignore

        return wrapper  # type: ignore


# Global middleware instance for convenience
_default_middleware = JSONParameterMiddleware()


def json_convert[F: Callable[..., Any]](func: F) -> F:
    """
    Convenience decorator that applies JSON parameter conversion to a function.

    This is a shorthand for @JSONParameterMiddleware().convert that can be used
    directly without creating a middleware instance.

    Usage:
        @mcp.tool()
        @json_convert
        def my_tool(items: list[str]) -> dict:
            return {"count": len(items)}

    Args:
        func: The function to wrap

    Returns:
        The wrapped function with JSON parameter conversion
    """
    return _default_middleware.convert(func)


def debug_json_convert[F: Callable[..., Any]](func: F) -> F:
    """
    Debug version of json_convert that prints conversion information.

    Usage:
        @mcp.tool()
        @debug_json_convert
        def my_tool(items: list[str]) -> dict:
            return {"count": len(items)}

    Args:
        func: The function to wrap

    Returns:
        The wrapped function with debug JSON parameter conversion
    """
    debug_middleware = JSONParameterMiddleware(debug=True)
    return debug_middleware.convert(func)
