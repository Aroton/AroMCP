"""
Comprehensive TypeScript function analysis for Phase 3.

Provides detailed function analysis including:
- Function signature extraction (declarations, arrows, methods, generics)
- Function body analysis (code extraction, call dependency tracking)
- Type information resolution for parameters and return types
- Performance optimization for batch processing
"""

import re
from typing import Any

from ..models.typescript_models import (
    AnalysisError,
    FunctionDetail,
    ParameterType,
    TypeDefinition,
)
from .type_resolver import TypeResolver
from .typescript_parser import TypeScriptParser


class FunctionAnalyzer:
    """
    Comprehensive TypeScript function analysis with performance optimization.

    Features:
    - Multi-pattern function detection (declarations, arrows, methods)
    - Detailed signature extraction with parameter types
    - Function body analysis and call tracking
    - Generic constraint analysis
    - Performance optimized for batch processing
    """

    def __init__(self, parser: TypeScriptParser, type_resolver: TypeResolver):
        """
        Initialize function analyzer.

        Args:
            parser: TypeScript parser instance
            type_resolver: Type resolver for signature analysis
        """
        self.parser = parser
        self.type_resolver = type_resolver

        # Function detection patterns - not used anymore, but kept for reference
        self.function_patterns = []

    def analyze_function(
        self,
        function_name: str,
        file_path: str,
        include_code: bool = True,
        include_types: bool = True,
        include_calls: bool = False,
        resolution_depth: str = "basic",
        analyze_nested_functions: bool = False,
        handle_overloads: bool = False,
        analyze_control_flow: bool = False,
        track_variables: bool = False,
        resolve_imports: bool = False,
        track_cross_file_calls: bool = False,
        track_dynamic_calls: bool = False,
        track_async_calls: bool = False,
        # Phase 3 type resolution parameters
        max_constraint_depth: int = 3,
        track_instantiations: bool = False,
        resolve_conditional_types: bool = False,
        handle_recursive_types: bool = False,
        fallback_on_complexity: bool = False,
    ) -> tuple[FunctionDetail | None, list[AnalysisError]]:
        """
        Comprehensive function analysis.

        Args:
            function_name: Name of the function to analyze
            file_path: File containing the function
            include_code: Include complete function implementation
            include_types: Include type definitions used in function
            include_calls: Include list of functions this one calls
            resolution_depth: Type resolution depth ("basic", "generics", "full_type")

        Returns:
            FunctionDetail with comprehensive analysis or None if not found
        """
        errors = []

        try:
            # Find function definition using multiple patterns
            function_info = self._find_function_definition(function_name, file_path)
            if not function_info:
                return None

            # Extract signature with parameters and return type
            signature = self._extract_signature(function_info, resolution_depth)

            # Extract types if requested
            types = {}
            if include_types:
                types, type_errors = self._extract_types(
                    function_info,
                    file_path,
                    resolution_depth,
                    resolve_imports,
                    max_constraint_depth,
                    track_instantiations,
                    resolve_conditional_types,
                    handle_recursive_types,
                    fallback_on_complexity,
                )
                errors.extend(type_errors)

            # Extract function body if requested
            code = None
            if include_code:
                code = self._extract_function_code(function_info)

            # Find function calls if requested
            calls = []
            if include_calls:
                calls = self._find_function_calls(function_info, file_path)

            # Extract parameter details
            parameters = self._parse_parameters(function_info["parameters"])

            # Analyze nested functions if requested
            nested_functions = {}
            if analyze_nested_functions and code:
                nested_functions = self._find_nested_functions(code)

            # Analyze control flow if requested
            control_flow_info = None
            if analyze_control_flow and code:
                control_flow_info = self._analyze_control_flow(code)

            # Track variables if requested
            variable_info = None
            if track_variables and code:
                variable_info = self._track_variables(code)

            # Find overloads if requested
            overloads = []
            if handle_overloads:
                overloads = self._find_overloads(function_name, file_path)

            # Track detailed call information if requested
            call_info = []
            if track_cross_file_calls and calls:
                call_info = self._build_call_info(calls, file_path)

            # Track dynamic calls if requested
            dynamic_call_info = []
            if track_dynamic_calls and code:
                dynamic_call_info = self._find_dynamic_calls(code)

            # Track async call info if requested
            async_call_info = None
            if track_async_calls and code:
                async_call_info = self._analyze_async_patterns(code)

            # Create the result with the correct attributes
            result = FunctionDetail(
                signature=signature,
                location=f"{file_path}:{function_info['line']}",
                code=code,
                types=types if types else None,
                calls=calls,
                parameters=parameters,
            )

            # Add additional attributes for Phase 3 features
            if nested_functions:
                result.nested_functions = nested_functions
            if control_flow_info:
                result.control_flow_info = control_flow_info
            if variable_info:
                result.variable_info = variable_info
            if overloads:
                result.overloads = overloads
            if call_info:
                result.call_info = call_info
            if dynamic_call_info:
                result.dynamic_call_info = dynamic_call_info
            if async_call_info:
                result.async_call_info = async_call_info

            return result, errors

        except Exception as e:
            # Log analysis error and return None with error
            errors.append(
                AnalysisError(
                    code="FUNCTION_ANALYSIS_ERROR",
                    message=f"Error analyzing function '{function_name}': {str(e)}",
                    file=file_path,
                )
            )
            return None, errors

    def _find_function_definition(self, function_name: str, file_path: str) -> dict | None:
        """
        Find function definition using multiple regex patterns.

        Args:
            function_name: Name of the function to find (can be "ClassName.methodName")
            file_path: File to search in

        Returns:
            Dict with function info or None if not found
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return None

        # Check if this is a class method (ClassName.methodName)
        if "." in function_name:
            class_name, method_name = function_name.rsplit(".", 1)
            # For class methods, we need to find the class first, then the method
            return self._find_class_method(content, class_name, method_name, function_name)

        # First try simpler patterns to locate the function, then parse manually
        # Updated patterns to handle generics and arrow functions properly
        function_start_patterns = [
            # Regular function declaration
            rf"(?:export\s+)?function\s+{re.escape(function_name)}\b",
            # Arrow function (const/let name = ...)
            rf"(?:export\s+)?(?:const|let)\s+{re.escape(function_name)}\s*=",
            # Method definition
            rf"{re.escape(function_name)}\s*(?:<[^>]*>)?\s*\(",
        ]

        # Collect all matches, then prefer implementation over overloads
        all_matches = []

        for pattern in function_start_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                func_start = match.start()
                line_num = content[:func_start].count("\n") + 1

                # Extract the full function signature
                signature_info = self._extract_full_signature(content, func_start, function_name)
                if signature_info:
                    signature_info.update({"line": line_num, "content": content, "start_pos": func_start})

                    # Check if this is an implementation (has '{') or overload (has ';')
                    # Look ahead to see what follows the signature
                    check_pos = func_start
                    while check_pos < len(content) and content[check_pos] not in ";{":
                        check_pos += 1

                    if check_pos < len(content):
                        signature_info["is_implementation"] = content[check_pos] == "{"
                    else:
                        signature_info["is_implementation"] = False

                    all_matches.append(signature_info)

        # If we have multiple matches, prefer the implementation
        if all_matches:
            # First try to find an implementation
            for match in all_matches:
                if match.get("is_implementation", False):
                    return match
            # If no implementation found, return the first match
            return all_matches[0]

        return None

    def _extract_full_signature(self, content: str, start_pos: int, function_name: str) -> dict | None:
        """
        Extract the full function signature including multi-line parameters.

        Args:
            content: File content
            start_pos: Starting position of the function
            function_name: Name of the function

        Returns:
            Dict with signature information
        """
        try:
            # Extract any generic parameters first
            generic_params = ""
            check_pos = start_pos

            # Look for generics between function name and opening paren
            while check_pos < len(content) and content[check_pos] != "(":
                if content[check_pos] == "<":
                    # Found start of generics
                    generic_start = check_pos
                    angle_count = 1
                    check_pos += 1
                    while check_pos < len(content) and angle_count > 0:
                        if content[check_pos] == "<":
                            angle_count += 1
                        elif content[check_pos] == ">":
                            # Check if this '>' is part of '=>' (arrow function syntax)
                            # Arrow functions use '=>', so we need to check if previous char is '='
                            if check_pos > 0 and content[check_pos - 1] == "=":
                                # This is '=>', don't count as closing angle bracket
                                pass  # Skip counting this '>' as a closing bracket
                            else:
                                # This is a standalone '>', count it as closing angle bracket
                                angle_count -= 1
                        check_pos += 1
                    if angle_count == 0:
                        generic_params = content[generic_start:check_pos]
                    break
                check_pos += 1

            # Find the opening parenthesis for function parameters
            # If we have generic parameters, start searching after them
            search_start = check_pos if generic_params else start_pos
            paren_start = content.find("(", search_start)
            if paren_start == -1:
                return None

            # Find the matching closing parenthesis
            paren_count = 0
            pos = paren_start
            paren_end = -1

            while pos < len(content):
                if content[pos] == "(":
                    paren_count += 1
                elif content[pos] == ")":
                    paren_count -= 1
                    if paren_count == 0:
                        paren_end = pos
                        break
                pos += 1

            if paren_end == -1:
                return None

            # Extract parameters
            params_str = content[paren_start + 1 : paren_end].strip()

            # Find return type (look for : after the closing parenthesis)
            return_type_start = paren_end + 1
            return_type_str = "any"

            # Skip whitespace and look for colon
            while return_type_start < len(content) and content[return_type_start].isspace():
                return_type_start += 1

            if return_type_start < len(content) and content[return_type_start] == ":":
                # Found return type annotation
                type_start = return_type_start + 1

                # Find the end of the return type (before { or => or ;)
                type_end = type_start
                brace_count = 0
                paren_count = 0

                # Track angle brackets for generic types
                angle_count = 0

                while type_end < len(content):
                    char = content[type_end]

                    # Track angle brackets for generics
                    if char == "<":
                        angle_count += 1
                    elif char == ">":
                        angle_count -= 1
                    # For arrow functions, track => but don't stop immediately
                    elif (
                        char == "="
                        and type_end + 1 < len(content)
                        and content[type_end + 1] == ">"
                        and brace_count == 0
                        and paren_count == 0
                        and angle_count == 0
                    ):
                        # Include the => in the type
                        type_end += 2
                        # Now check what follows
                        # Skip whitespace
                        check_pos = type_end
                        while check_pos < len(content) and content[check_pos].isspace():
                            check_pos += 1

                        # If we see a word followed by {, check if this ends the type
                        if check_pos < len(content):
                            # Collect the next word
                            word_start = check_pos
                            while check_pos < len(content) and content[check_pos].isalnum():
                                check_pos += 1

                            if word_start < check_pos:
                                word = content[word_start:check_pos]
                                # Skip whitespace after word
                                while check_pos < len(content) and content[check_pos].isspace():
                                    check_pos += 1

                                # If the word is followed by {, this might be function body
                                if check_pos < len(content) and content[check_pos] == "{":
                                    # For simple return types like "void", "string", etc.
                                    # these are complete types when followed by {
                                    if word in ["void", "string", "number", "boolean", "any", "never", "unknown"]:
                                        # Include the word in the type and stop
                                        type_end = word_start + len(word)
                                        break

                        continue  # Continue parsing from type_end
                    # For regular functions, handle opening brace carefully
                    elif char == "{" and brace_count == 0 and paren_count == 0 and angle_count == 0:
                        # Check if this is the start of an object return type or function body
                        # Look ahead to see if this looks like an object type definition
                        lookahead_pos = type_end + 1
                        while lookahead_pos < len(content) and content[lookahead_pos].isspace():
                            lookahead_pos += 1

                        # If we see identifier:, it's likely an object type, not function body
                        if lookahead_pos < len(content):
                            # Look for patterns like "identifier:" or "readonly identifier:" or "[...]:""
                            if content[lookahead_pos] == "[":
                                # Handle mapped type patterns like [P in keyof T]:
                                bracket_count = 0
                                temp_pos = lookahead_pos
                                while temp_pos < len(content):
                                    if content[temp_pos] == "[":
                                        bracket_count += 1
                                    elif content[temp_pos] == "]":
                                        bracket_count -= 1
                                        if bracket_count == 0:
                                            # Found closing bracket, look for colon
                                            temp_pos += 1
                                            while temp_pos < len(content) and content[temp_pos].isspace():
                                                temp_pos += 1
                                            if temp_pos < len(content) and content[temp_pos] == ":":
                                                # This is a mapped type, continue parsing
                                                brace_count += 1
                                                break
                                            else:
                                                # No colon after bracket, assume function body
                                                break
                                    temp_pos += 1
                                else:
                                    # No closing bracket found, assume function body
                                    break
                            else:
                                # Regular identifier pattern
                                identifier_start = lookahead_pos
                                while lookahead_pos < len(content) and (
                                    content[lookahead_pos].isalnum() or content[lookahead_pos] in "_<>"
                                ):
                                    lookahead_pos += 1

                                # Skip whitespace
                                while lookahead_pos < len(content) and content[lookahead_pos].isspace():
                                    lookahead_pos += 1

                                # If we see a colon, this is an object type property
                                if lookahead_pos < len(content) and content[lookahead_pos] == ":":
                                    # This is an object type, continue parsing
                                    brace_count += 1
                                else:
                                    # This might be function body, stop parsing return type
                                    break
                        else:
                            # Empty braces or end of content, assume function body
                            break
                    elif char == ";" and brace_count == 0 and paren_count == 0 and angle_count == 0:
                        break
                    elif char == "(":
                        paren_count += 1
                    elif char == ")":
                        paren_count -= 1
                    elif char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        # If we just closed all braces, check if we should stop
                        if brace_count == 0 and paren_count == 0 and angle_count == 0:
                            # Look ahead to see if this is the end of the type
                            next_pos = type_end + 1
                            while next_pos < len(content) and content[next_pos].isspace():
                                next_pos += 1
                            if next_pos < len(content):
                                next_char = content[next_pos]
                                # Check for various endings
                                if next_char == "{":
                                    # Function body starts - we're done with the type
                                    type_end += 1  # Include the closing brace
                                    break
                                elif next_char == "=" and next_pos + 1 < len(content) and content[next_pos + 1] == ">":
                                    # Arrow function - include the brace and continue
                                    type_end += 1
                                    break

                    type_end += 1

                return_type_str = content[type_start:type_end].strip()

                # Debug: Print what was extracted for complex types
                if len(return_type_str) > 50 or "{" in return_type_str:
                    # Find function name from the content for debugging
                    import re

                    func_name_match = re.search(r"function\s+(\w+)", content[max(0, type_start - 500) : type_start])
                    func_name = func_name_match.group(1) if func_name_match else "unknown"
                    print(
                        f"DEBUG: Extracted return type for function '{func_name}': '{return_type_str[:200]}{'...' if len(return_type_str) > 200 else ''}'"
                    )

                # Clean up return type - remove trailing => if present
                if return_type_str.endswith("=>"):
                    return_type_str = return_type_str[:-2].strip()

                # Normalize whitespace in multi-line types
                # Replace newlines and multiple spaces with single spaces
                return_type_str = " ".join(return_type_str.split())

                # Remove trailing semicolon if present (common in object type syntax)
                if return_type_str.endswith("; }"):
                    # Semicolon inside object type
                    return_type_str = return_type_str[:-3] + " }"
                elif return_type_str.endswith(";"):
                    # Semicolon at end
                    return_type_str = return_type_str[:-1].strip()
            else:
                # No explicit return type annotation
                # For arrow functions, check if they return another function
                check_pos = return_type_start
                while check_pos < len(content) and content[check_pos].isspace():
                    check_pos += 1

                if check_pos + 1 < len(content) and content[check_pos : check_pos + 2] == "=>":
                    # This is an arrow function
                    # Check what follows the arrow
                    expr_start = check_pos + 2
                    while expr_start < len(content) and content[expr_start].isspace():
                        expr_start += 1

                    # If it starts with '(', it might be returning a function
                    if expr_start < len(content) and content[expr_start] == "(":
                        # Find the signature of the returned function
                        inner_paren_end = content.find(")", expr_start)
                        if inner_paren_end != -1:
                            # Look for return type of the inner function
                            inner_pos = inner_paren_end + 1
                            while inner_pos < len(content) and content[inner_pos].isspace():
                                inner_pos += 1

                            if inner_pos < len(content) and content[inner_pos] == ":":
                                # Has return type
                                inner_arrow = content.find("=>", inner_pos)
                                if inner_arrow != -1:
                                    # Extract the returned function's signature
                                    return_type_str = content[expr_start:inner_arrow].strip()

            # Determine pattern type based on function start
            func_start_text = content[start_pos:paren_start]
            if "const" in func_start_text:
                if "async" in func_start_text:
                    pattern_type = "async_arrow_const"
                else:
                    pattern_type = "arrow_const"
            elif "let" in func_start_text:
                pattern_type = "arrow_let"
            elif "function" in func_start_text:
                if "async" in func_start_text:
                    pattern_type = "async_function"
                else:
                    pattern_type = "function_declaration"
            else:
                # Method pattern - check if it's async
                if "async" in func_start_text:
                    pattern_type = "async_method"
                else:
                    pattern_type = "method"

            # Create a mock match object for compatibility
            class MockMatch:
                def __init__(self, start_pos, func_name):
                    self.start_pos = start_pos
                    self.func_name = func_name

                def start(self):
                    return self.start_pos

                def end(self):
                    return self.start_pos + 10  # Not used in current code

                def group(self, n):
                    if n == 0:
                        return self.func_name  # Return function name
                    return ""

            return {
                "match": MockMatch(start_pos, function_name),
                "parameters": params_str,
                "return_type": return_type_str,
                "pattern_type": pattern_type,
                "function_name": function_name,
                "generic_params": generic_params,
            }

        except Exception:
            return None

    def _get_pattern_type(self, pattern_template: str) -> str:
        """Determine the type of function pattern matched."""
        if "function\\s+" in pattern_template:
            if "async\\s+" in pattern_template:
                return "async_function"
            else:
                return "function_declaration"
        elif "const\\s+" in pattern_template:
            if "async" in pattern_template:
                return "async_arrow_const"
            else:
                return "arrow_const"
        elif "let\\s+" in pattern_template:
            return "arrow_let"
        else:
            return "method"

    def _extract_signature(self, function_info: dict, resolution_depth: str) -> str:
        """
        Extract complete function signature with resolved types.

        Args:
            function_info: Function information from pattern matching
            resolution_depth: Type resolution level

        Returns:
            Complete function signature string
        """
        pattern_type = function_info["pattern_type"]
        params_str = function_info["parameters"]
        return_type_str = function_info["return_type"]
        function_name = function_info.get("function_name", function_info["match"].group(0))

        # Parse parameters
        parameters = self._parse_parameters(params_str)

        # Extract generic parameters if present
        generic_params = function_info.get("generic_params", "")

        # For class methods, use just the method name, not the full ClassName.methodName
        display_name = function_name
        if "." in function_name and pattern_type in ["method", "async_method"]:
            _, display_name = function_name.rsplit(".", 1)

        # Build signature based on pattern type
        if pattern_type == "function_declaration":
            signature = f"function {function_name}"
        elif pattern_type == "async_function":
            signature = f"async function {function_name}"
        elif pattern_type in ["arrow_const", "async_arrow_const"]:
            if pattern_type == "async_arrow_const":
                signature = f"const {function_name} = async "
            else:
                signature = f"const {function_name} = "
        elif pattern_type == "arrow_let":
            signature = f"let {function_name} = "
        elif pattern_type == "async_method":
            signature = f"async {display_name}"
        else:  # method
            signature = display_name

        # Add generics before parameters
        if generic_params:
            signature += generic_params

        # Add parameters
        param_strings = []
        for param in parameters:
            param_str = ""
            # Add rest parameter prefix if needed
            if param.is_rest_parameter:
                param_str += "..."
            param_str += param.name
            if param.optional:
                param_str += "?"
            if param.type:
                param_str += f": {param.type}"
            if param.default_value:
                param_str += f" = {param.default_value}"
            param_strings.append(param_str)

        signature += f"({', '.join(param_strings)})"

        # Add return type and arrow

        if pattern_type in ["arrow_const", "arrow_let", "async_arrow_const"]:
            # For arrow functions
            if return_type_str and return_type_str != "any":
                # Check if the return type is a function (starts with '(')
                if return_type_str.startswith("("):
                    # Higher-order function returning another function
                    signature += f" => {return_type_str}"
                else:
                    # Regular return type
                    signature += f": {return_type_str} =>"
            else:
                # No return type
                signature += " =>"
        else:
            # For regular functions
            if return_type_str and return_type_str != "any":
                signature += f": {return_type_str}"

        return signature

    def _parse_parameters(self, params_str: str) -> list[ParameterType]:
        """
        Parse function parameters from parameter string.

        Args:
            params_str: Raw parameter string from function signature

        Returns:
            List of ParameterType objects
        """
        if not params_str.strip():
            return []

        parameters = []

        # Split parameters by comma, but handle nested types
        param_parts = self._split_parameters(params_str)

        for param_part in param_parts:
            param_part = param_part.strip()
            if not param_part:
                continue

            # Parse individual parameter
            param = self._parse_single_parameter(param_part)
            if param:
                parameters.append(param)

        return parameters

    def _split_parameters(self, params_str: str) -> list[str]:
        """Split parameter string by commas, handling nested types and generics."""
        parts = []
        current_part = ""
        paren_depth = 0
        bracket_depth = 0
        brace_depth = 0
        angle_depth = 0

        i = 0
        while i < len(params_str):
            char = params_str[i]

            if char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth -= 1
            elif char == "[":
                bracket_depth += 1
            elif char == "]":
                bracket_depth -= 1
            elif char == "{":
                brace_depth += 1
            elif char == "}":
                brace_depth -= 1
            elif char == "<":
                angle_depth += 1
            elif char == ">":
                # Check if this is part of '=>' (arrow function)
                if i > 0 and params_str[i - 1] == "=":
                    # This is '=>', don't count as angle bracket
                    pass
                else:
                    angle_depth -= 1
            elif char == "," and paren_depth == 0 and bracket_depth == 0 and brace_depth == 0 and angle_depth == 0:
                parts.append(current_part.strip())
                current_part = ""
                i += 1
                continue

            current_part += char
            i += 1

        if current_part.strip():
            parts.append(current_part.strip())

        return parts

    def _find_class_method(self, content: str, class_name: str, method_name: str, full_name: str) -> dict | None:
        """
        Find a method within a class definition.

        Args:
            content: File content
            class_name: Name of the class
            method_name: Name of the method
            full_name: Full name (ClassName.methodName) for reference

        Returns:
            Dict with method info or None if not found
        """
        # First find the class
        class_patterns = [
            rf"(?:export\s+)?(?:abstract\s+)?class\s+{re.escape(class_name)}",
            rf"(?:export\s+)?interface\s+{re.escape(class_name)}",
        ]

        class_start = -1
        for pattern in class_patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                class_start = match.start()
                break

        if class_start == -1:
            return None

        # Find the class body (between { and })
        brace_start = content.find("{", class_start)
        if brace_start == -1:
            return None

        # Find the matching closing brace
        brace_count = 1
        pos = brace_start + 1
        class_end = -1

        while pos < len(content) and brace_count > 0:
            if content[pos] == "{":
                brace_count += 1
            elif content[pos] == "}":
                brace_count -= 1
                if brace_count == 0:
                    class_end = pos
                    break
            pos += 1

        if class_end == -1:
            return None

        # Search for the method within the class body
        class_body = content[brace_start:class_end]

        # Method patterns within a class
        # Use simpler patterns and rely on _extract_full_signature for details
        method_patterns = [
            # Look for method name followed by generics and/or opening paren
            rf"^\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:async\s+)?{re.escape(method_name)}\s*(?:<|\()",
            # Getter/setter
            rf"^\s*(?:get|set)\s+{re.escape(method_name)}\s*\(",
        ]

        for pattern in method_patterns:
            match = re.search(pattern, class_body, re.MULTILINE)
            if match:
                # Calculate the actual position in the file
                method_start = brace_start + match.start()
                line_num = content[:method_start].count("\n") + 1

                # Extract signature using the existing method
                result = self._extract_full_signature(content, method_start, method_name)
                if result:
                    result.update(
                        {
                            "line": line_num,
                            "content": content,
                            "start_pos": method_start,
                            "function_name": full_name,  # Use full name for consistency
                        }
                    )
                    return result

        return None

    def _parse_single_parameter(self, param_str: str) -> ParameterType | None:
        """Parse a single parameter from its string representation."""
        try:
            # Check for rest parameter (...name)
            is_rest = False
            if param_str.strip().startswith("..."):
                is_rest = True
                param_str = param_str.strip()[3:]  # Remove the ...

            # Handle default values first (name: type = default)
            default_value = None
            if "=" in param_str:
                # Find the last = that's not part of =>
                equals_pos = -1
                for i in range(len(param_str) - 1, -1, -1):
                    if param_str[i] == "=" and (i == len(param_str) - 1 or param_str[i + 1] != ">"):
                        equals_pos = i
                        break

                if equals_pos > 0:
                    default_value = param_str[equals_pos + 1 :].strip()
                    param_str = param_str[:equals_pos].strip()

            # Handle optional parameters (name?: type)
            optional = False
            if ":" in param_str:
                colon_pos = param_str.find(":")
                if colon_pos > 0 and param_str[colon_pos - 1] == "?":
                    optional = True
                    # Remove the ? but keep it for now to find name correctly

            # Split name and type at the first colon
            if ":" in param_str:
                colon_pos = param_str.find(":")
                name_part = param_str[:colon_pos]
                type_part = param_str[colon_pos + 1 :].strip()

                # Remove optional marker from name
                if name_part.endswith("?"):
                    name_part = name_part[:-1]

                name = name_part.strip()
                # Normalize whitespace in parameter type (for multi-line types)
                param_type = " ".join(type_part.split())
                # Remove trailing semicolon if present (common in object type syntax)
                if param_type.endswith("; }"):
                    # Semicolon inside object type
                    param_type = param_type[:-3] + " }"
                elif param_type.endswith(";"):
                    # Semicolon at end
                    param_type = param_type[:-1].strip()
            else:
                name = param_str.strip()
                param_type = "any"

            return ParameterType(
                name=name, type=param_type, optional=optional, default_value=default_value, is_rest_parameter=is_rest
            )

        except Exception:
            return None

    def _extract_types(
        self,
        function_info: dict,
        file_path: str,
        resolution_depth: str,
        resolve_imports: bool = False,
        max_constraint_depth: int = 3,
        track_instantiations: bool = False,
        resolve_conditional_types: bool = False,
        handle_recursive_types: bool = False,
        fallback_on_complexity: bool = False,
    ) -> tuple[dict[str, TypeDefinition], list[AnalysisError]]:
        """
        Extract type definitions used in the function.

        Args:
            function_info: Function information
            file_path: File containing the function
            resolution_depth: Type resolution level

        Returns:
            Tuple of (Dictionary of type name to TypeDefinition, List of analysis errors)
        """
        types = {}
        errors = []

        # Extract types from parameters
        params_str = function_info["parameters"]
        param_types = self._extract_parameter_types(params_str)

        # Extract return type - handle complex return types
        return_type = function_info["return_type"]
        if return_type and return_type != "any":
            # For complex return types (e.g., function types), extract all type references
            if resolution_depth in ["generics", "full_inference", "full_type"]:
                type_refs = self.type_resolver._extract_type_references(return_type)
                param_types.extend(type_refs)

            # Always add the full return type too
            param_types.append(return_type)

            # For conditional types, also create a special entry to ensure something shows up in types
            if "extends" in return_type and "?" in return_type and ":" in return_type:
                # This is a conditional type, ensure we have at least the conditional type construct
                param_types.append("ConditionalReturnType")

        # Resolve each type
        for type_annotation in param_types:
            if type_annotation not in self.type_resolver.primitive_types:
                # Extract just the base type name for the key
                base_type_name = type_annotation.split("<")[0] if "<" in type_annotation else type_annotation

                # Handle special conditional type marker
                if base_type_name == "ConditionalReturnType":
                    types["ConditionalReturnType"] = TypeDefinition(
                        kind="conditional",
                        definition=f"Conditional return type: {return_type}",
                        location=f"{file_path}:return_type",
                    )
                    continue

                # Check if this is a builtin utility type first
                if base_type_name in self.type_resolver.builtin_generics and resolution_depth in [
                    "generics",
                    "full_inference",
                    "full_type",
                ]:
                    if base_type_name not in types:
                        types[base_type_name] = TypeDefinition(
                            kind="utility_type",
                            definition=f"TypeScript utility type: {base_type_name}",
                            location=f"{file_path}:builtin",
                        )

                    # Extract type arguments for nested resolution (e.g., Profile from Partial<Profile>)
                    if "<" in type_annotation and ">" in type_annotation:
                        start = type_annotation.find("<") + 1
                        end = type_annotation.rfind(">")
                        if start < end:
                            type_args_str = type_annotation[start:end]
                            # Parse type arguments (simple comma split for now)
                            type_args = [arg.strip() for arg in type_args_str.split(",")]
                            for arg in type_args:
                                if arg and arg not in self.type_resolver.primitive_types and arg not in types:
                                    arg_base = arg.split("<")[0]  # Handle nested generics
                                    arg_def = self.type_resolver.resolve_type(
                                        arg,
                                        file_path,
                                        resolution_depth,
                                        max_constraint_depth=max_constraint_depth,
                                        track_instantiations=track_instantiations,
                                        resolve_conditional_types=resolve_conditional_types,
                                        handle_recursive_types=handle_recursive_types,
                                    )
                                    if arg_def.kind not in ["error", "unknown"]:
                                        types[arg_base] = arg_def
                else:
                    # Otherwise resolve normally
                    type_def = self.type_resolver.resolve_type(
                        type_annotation,
                        file_path,
                        resolution_depth,
                        max_constraint_depth=max_constraint_depth,
                        track_instantiations=track_instantiations,
                        resolve_conditional_types=resolve_conditional_types,
                        handle_recursive_types=handle_recursive_types,
                    )
                    if type_def.kind == "error":
                        # Collect type resolution error
                        error_code = "TYPE_RESOLUTION_ERROR"
                        if ":unknown_type" in type_def.location:
                            error_code = "UNKNOWN_TYPE"
                        elif ":circular_constraint" in type_def.location:
                            error_code = "CIRCULAR_REFERENCE_DETECTED"
                        elif ":constraint_depth_exceeded" in type_def.location:
                            error_code = "CONSTRAINT_DEPTH_EXCEEDED"

                        errors.append(AnalysisError(code=error_code, message=type_def.definition, file=file_path))
                    else:
                        types[base_type_name] = type_def

        # Extract generic constraints if resolution depth is "generics" or higher
        if resolution_depth in ["generics", "full_inference", "full_type"]:
            generic_params = function_info.get("generic_params", "")
            if generic_params:
                constraint_types = self.type_resolver.extract_generic_constraints(
                    generic_params,
                    file_path,
                    resolution_depth,
                    max_constraint_depth=max_constraint_depth,
                    check_circular=True,
                )

                # Separate error types from valid types and collect errors
                for type_name, type_def in constraint_types.items():
                    if type_def.kind == "error":
                        # Extract specific error code from location field
                        error_code = "TYPE_RESOLUTION_ERROR"
                        if ":constraint_depth_exceeded" in type_def.location:
                            error_code = "CONSTRAINT_DEPTH_EXCEEDED"
                        elif ":circular_constraint" in type_def.location:
                            error_code = "CIRCULAR_REFERENCE_DETECTED"
                        elif ":unknown_type" in type_def.location:
                            error_code = "UNKNOWN_TYPE"

                        errors.append(AnalysisError(code=error_code, message=type_def.definition, file=file_path))
                    else:
                        types[type_name] = type_def

        # For classes, also extract base types (extends)
        if resolution_depth in ["generics", "full_inference", "full_type"]:
            for type_name, type_def in list(types.items()):
                if type_def.kind == "class" and "extends" in type_def.definition:
                    # Extract base class name
                    extends_match = re.search(r"extends\s+(\w+)", type_def.definition)
                    if extends_match:
                        base_class = extends_match.group(1)
                        if base_class not in types:
                            base_def = self.type_resolver.resolve_type(
                                base_class,
                                file_path,
                                resolution_depth,
                                max_constraint_depth=max_constraint_depth,
                                track_instantiations=track_instantiations,
                                resolve_conditional_types=resolve_conditional_types,
                                handle_recursive_types=handle_recursive_types,
                            )
                            if base_def.kind == "error":
                                # Collect type resolution error
                                error_code = "TYPE_RESOLUTION_ERROR"
                                if ":unknown_type" in base_def.location:
                                    error_code = "UNKNOWN_TYPE"
                                elif ":circular_constraint" in base_def.location:
                                    error_code = "CIRCULAR_REFERENCE_DETECTED"
                                elif ":constraint_depth_exceeded" in base_def.location:
                                    error_code = "CONSTRAINT_DEPTH_EXCEEDED"

                                errors.append(
                                    AnalysisError(code=error_code, message=base_def.definition, file=file_path)
                                )
                            elif base_def.kind != "unknown":
                                types[base_class] = base_def

        # Extract imported types if resolve_imports is True
        if resolve_imports:
            imported_types = self._extract_imported_types(file_path)
            for imported_type in imported_types:
                if imported_type not in types and imported_type not in self.type_resolver.primitive_types:
                    type_def = self.type_resolver.resolve_type(
                        imported_type,
                        file_path,
                        resolution_depth,
                        max_constraint_depth=max_constraint_depth,
                        track_instantiations=track_instantiations,
                        resolve_conditional_types=resolve_conditional_types,
                        handle_recursive_types=handle_recursive_types,
                    )
                    if type_def.kind == "error":
                        # Collect type resolution error
                        error_code = "TYPE_RESOLUTION_ERROR"
                        if ":unknown_type" in type_def.location:
                            error_code = "UNKNOWN_TYPE"
                        elif ":circular_constraint" in type_def.location:
                            error_code = "CIRCULAR_REFERENCE_DETECTED"
                        elif ":constraint_depth_exceeded" in type_def.location:
                            error_code = "CONSTRAINT_DEPTH_EXCEEDED"

                        errors.append(AnalysisError(code=error_code, message=type_def.definition, file=file_path))
                    else:
                        types[imported_type] = type_def

            # Also extract and resolve local types that are referenced but not yet resolved
            local_types = self._extract_local_types(file_path, param_types)
            for local_type in local_types:
                # Only resolve local types that haven't been resolved yet
                if (
                    local_type not in types
                    and local_type not in self.type_resolver.primitive_types
                    and local_type not in imported_types
                ):  # Avoid duplicating imported types

                    type_def = self.type_resolver.resolve_type(
                        local_type,
                        file_path,
                        resolution_depth,
                        max_constraint_depth=max_constraint_depth,
                        track_instantiations=track_instantiations,
                        resolve_conditional_types=resolve_conditional_types,
                        handle_recursive_types=handle_recursive_types,
                    )

                    if type_def.kind == "error":
                        # Collect type resolution error
                        error_code = "TYPE_RESOLUTION_ERROR"
                        if ":unknown_type" in type_def.location:
                            error_code = "UNKNOWN_TYPE"
                        elif ":circular_constraint" in type_def.location:
                            error_code = "CIRCULAR_REFERENCE_DETECTED"
                        elif ":constraint_depth_exceeded" in type_def.location:
                            error_code = "CONSTRAINT_DEPTH_EXCEEDED"

                        errors.append(AnalysisError(code=error_code, message=type_def.definition, file=file_path))
                    else:
                        types[local_type] = type_def

        # Additional type extraction for full inference level
        if resolution_depth in ["full_inference", "full_type"]:
            # Extract types from function parameter types (e.g., function types like (t: T) => U)
            params_str = function_info["parameters"]
            function_param_types = self._extract_function_parameter_types(params_str)

            for func_type in function_param_types:
                if func_type not in types and func_type not in self.type_resolver.primitive_types:
                    # Use a simple key for complex function types
                    type_key = func_type.split("<")[0] if "<" in func_type else func_type
                    if type_key not in types:
                        type_def = self.type_resolver.resolve_type(
                            func_type,
                            file_path,
                            resolution_depth,
                            max_constraint_depth=max_constraint_depth,
                            track_instantiations=track_instantiations,
                            resolve_conditional_types=resolve_conditional_types,
                            handle_recursive_types=handle_recursive_types,
                        )
                        if type_def.kind != "error":
                            types[type_key] = type_def

            # Extract nested types from resolved interfaces (e.g., Date from BaseEntity.createdAt)
            for type_name, type_def in list(types.items()):
                if type_def.kind == "interface" and type_def.definition:
                    nested_types = self._extract_nested_interface_types(type_def.definition)
                    for nested_type in nested_types:
                        if (
                            nested_type not in types
                            and nested_type not in self.type_resolver.primitive_types
                            and nested_type not in ["T", "U", "K", "V"]
                        ):
                            nested_def = self.type_resolver.resolve_type(
                                nested_type,
                                file_path,
                                resolution_depth,
                                max_constraint_depth=max_constraint_depth,
                                track_instantiations=track_instantiations,
                                resolve_conditional_types=resolve_conditional_types,
                                handle_recursive_types=handle_recursive_types,
                            )
                            if nested_def.kind not in ["error", "unknown"]:
                                types[nested_type] = nested_def

        # Recursive nested type resolution for generics and full_inference
        if resolution_depth in ["generics", "full_inference", "full_type"]:
            # Keep resolving nested types until no new types are found
            max_iterations = 3  # Prevent infinite loops
            for iteration in range(max_iterations):
                initial_type_count = len(types)

                # Look for nested types in all resolved interfaces
                for type_name, type_def in list(types.items()):
                    if type_def.kind == "interface" and type_def.definition:
                        # Extract referenced types from interface properties
                        referenced_types = self._extract_nested_interface_types(type_def.definition)

                        for ref_type in referenced_types:
                            if (
                                ref_type not in types
                                and ref_type not in self.type_resolver.primitive_types
                                and ref_type not in ["T", "U", "K", "V", "P"]
                            ):
                                ref_def = self.type_resolver.resolve_type(
                                    ref_type,
                                    file_path,
                                    resolution_depth,
                                    max_constraint_depth=max_constraint_depth,
                                    track_instantiations=track_instantiations,
                                    resolve_conditional_types=resolve_conditional_types,
                                    handle_recursive_types=handle_recursive_types,
                                )
                                if ref_def.kind not in ["error", "unknown"]:
                                    types[ref_type] = ref_def

                # Stop if no new types were found
                if len(types) == initial_type_count:
                    break

        return types, errors

    def _extract_function_parameter_types(self, params_str: str) -> list[str]:
        """
        Extract function types from parameter declarations for full inference.

        Args:
            params_str: Function parameters string

        Returns:
            List of function type expressions found in parameters
        """
        function_types = []

        # Pattern to match function type parameters: (param: (args) => ReturnType)
        # This matches patterns like: (t: T, u: U) => T & U
        function_type_pattern = r"\([^)]*\)\s*=>\s*[^,)]+"
        matches = re.findall(function_type_pattern, params_str)

        for match in matches:
            # Clean up the match and add to function types
            func_type = match.strip()
            if func_type:
                function_types.append(func_type)

        # Also look for intersection types (T & U) and union types in function parameters
        intersection_pattern = r"\b\w+\s*&\s*\w+(?:\s*&\s*\w+)*"
        intersection_matches = re.findall(intersection_pattern, params_str)
        function_types.extend(intersection_matches)

        return function_types

    def _extract_nested_interface_types(self, interface_definition: str) -> list[str]:
        """
        Extract type names from interface property definitions.

        Args:
            interface_definition: Interface definition string

        Returns:
            List of type names found in the interface
        """
        nested_types = []

        # Pattern to match property types: propertyName: TypeName
        property_pattern = r"\w+\s*:\s*([A-Z]\w*(?:\[\])?(?:\s*\|\s*[A-Z]\w*)*)"
        matches = re.findall(property_pattern, interface_definition)

        for match in matches:
            # Handle union types and arrays
            type_parts = match.replace("[]", "").split("|")
            for part in type_parts:
                type_name = part.strip()
                if type_name and type_name[0].isupper():  # Only capitalize types
                    nested_types.append(type_name)

        return nested_types

    def _extract_imported_types(self, file_path: str) -> list[str]:
        """
        Extract all imported type names from a file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            List of imported type names
        """
        imported_types = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Pattern for named imports: import { Type1, Type2 } from '...'
            named_import_pattern = r"import\s*\{\s*([^}]+)\s*\}\s*from"
            named_matches = re.findall(named_import_pattern, content)

            for match in named_matches:
                # Split by comma and clean up whitespace
                types = [t.strip() for t in match.split(",")]
                for type_name in types:
                    # Handle potential aliases: "Type as Alias"
                    if " as " in type_name:
                        original_name = type_name.split(" as ")[0].strip()
                        imported_types.append(original_name)
                    else:
                        imported_types.append(type_name)

            # Pattern for default imports: import Type from '...'
            default_import_pattern = r"import\s+(\w+)\s+from"
            default_matches = re.findall(default_import_pattern, content)
            imported_types.extend(default_matches)

            # Pattern for type-only imports: import type { Type } from '...'
            type_import_pattern = r"import\s+type\s*\{\s*([^}]+)\s*\}\s*from"
            type_matches = re.findall(type_import_pattern, content)

            for match in type_matches:
                types = [t.strip() for t in match.split(",")]
                for type_name in types:
                    if " as " in type_name:
                        original_name = type_name.split(" as ")[0].strip()
                        imported_types.append(original_name)
                    else:
                        imported_types.append(type_name)

        except Exception:
            # If we can't read the file, return empty list
            pass

        return imported_types

    def _extract_local_types(self, file_path: str, referenced_types: list[str]) -> list[str]:
        """
        Extract locally defined type names that are referenced in the function.

        Args:
            file_path: Path to the file to analyze
            referenced_types: List of type names referenced in function signature/body

        Returns:
            List of locally defined type names
        """
        local_types = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Find all locally defined types (interfaces, types, classes, enums)
            defined_types = set()

            # Find interface definitions: interface TypeName
            interface_pattern = r"(?:export\s+)?interface\s+(\w+)"
            interface_matches = re.findall(interface_pattern, content)
            defined_types.update(interface_matches)

            # Find type alias definitions: type TypeName =
            type_pattern = r"(?:export\s+)?type\s+(\w+)\s*(?:<[^>]*>)?\s*="
            type_matches = re.findall(type_pattern, content)
            defined_types.update(type_matches)

            # Find class definitions: class TypeName
            class_pattern = r"(?:export\s+)?class\s+(\w+)"
            class_matches = re.findall(class_pattern, content)
            defined_types.update(class_matches)

            # Find enum definitions: enum TypeName
            enum_pattern = r"(?:export\s+)?enum\s+(\w+)"
            enum_matches = re.findall(enum_pattern, content)
            defined_types.update(enum_matches)

            # Return only the types that are both defined locally and referenced
            for ref_type in referenced_types:
                # Extract base type name from generic instantiations
                base_type = ref_type.split("<")[0] if "<" in ref_type else ref_type
                if base_type in defined_types:
                    local_types.append(base_type)

        except Exception:
            pass

        return local_types

    def _extract_parameter_types(self, params_str: str) -> list[str]:
        """Extract type annotations from parameter string."""
        type_annotations = []

        if not params_str.strip():
            return type_annotations

        # Parse parameters and extract types
        param_parts = self._split_parameters(params_str)

        for param_part in param_parts:
            if ":" in param_part:
                # Extract type part
                type_part = param_part.split(":", 1)[1]
                if "=" in type_part:
                    type_part = type_part.split("=", 1)[0]

                type_annotation = type_part.strip().rstrip("?")
                if type_annotation and type_annotation != "any":
                    type_annotations.append(type_annotation)

        return type_annotations

    def _extract_function_code(self, function_info: dict) -> str | None:
        """
        Extract complete function implementation code.

        Args:
            function_info: Function information with match details

        Returns:
            Complete function code or None if extraction fails
        """
        try:
            content = function_info["content"]
            start_pos = function_info["start_pos"]
            return_type = function_info["return_type"]
            pattern_type = function_info["pattern_type"]

            # Find where the function body starts
            # We need to find the opening brace after the return type
            search_pos = start_pos

            # Skip to the end of the signature (after parameters and return type)
            # First, find the closing parenthesis
            paren_count = 0
            found_open_paren = False
            while search_pos < len(content):
                if content[search_pos] == "(":
                    if not found_open_paren:
                        found_open_paren = True
                    paren_count += 1
                elif content[search_pos] == ")":
                    paren_count -= 1
                    if paren_count == 0 and found_open_paren:
                        search_pos += 1
                        break
                search_pos += 1

            # Skip past return type annotation if present
            while search_pos < len(content) and content[search_pos].isspace():
                search_pos += 1

            if search_pos < len(content) and content[search_pos] == ":":
                # Has return type, skip it properly handling nested types
                search_pos += 1
                # Skip the return type - handle nested generics and object types
                angle_count = 0
                brace_count = 0
                paren_count = 0

                while search_pos < len(content):
                    char = content[search_pos]

                    if char == "<":
                        angle_count += 1
                    elif char == ">":
                        angle_count -= 1
                    elif char == "{":
                        # Check if this is the function body or part of type
                        if angle_count == 0 and paren_count == 0:
                            # Could be function body or object type
                            # Look ahead to see if we're still in a type definition
                            # If we see a colon or semicolon after the closing brace, it's a type
                            temp_pos = search_pos + 1
                            temp_brace_count = 1
                            while temp_pos < len(content) and temp_brace_count > 0:
                                if content[temp_pos] == "{":
                                    temp_brace_count += 1
                                elif content[temp_pos] == "}":
                                    temp_brace_count -= 1
                                temp_pos += 1

                            # Check what follows the closing brace
                            while temp_pos < len(content) and content[temp_pos].isspace():
                                temp_pos += 1

                            if temp_pos < len(content) and content[temp_pos] in (">", ")", ",", "|", "&", "[", "]"):
                                # Still part of type definition
                                brace_count += 1
                            else:
                                # This is the function body
                                break
                        else:
                            brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                    elif char == "(":
                        paren_count += 1
                    elif char == ")":
                        paren_count -= 1
                    elif search_pos + 1 < len(content) and content[search_pos : search_pos + 2] == "=>":
                        if angle_count == 0 and brace_count == 0 and paren_count == 0:
                            search_pos += 2
                            break

                    search_pos += 1
            elif search_pos + 1 < len(content) and content[search_pos : search_pos + 2] == "=>":
                # Arrow function without return type
                search_pos += 2

            # Now find the opening brace (for regular functions) or the start of expression (for arrow functions)
            while search_pos < len(content) and content[search_pos].isspace():
                search_pos += 1

            if search_pos >= len(content):
                return None

            # Check if it's a single-expression arrow function or a block
            if content[search_pos] == "{":
                # Block body - find matching closing brace
                brace_count = 0
                pos = search_pos

                while pos < len(content):
                    if content[pos] == "{":
                        brace_count += 1
                    elif content[pos] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            # Found matching closing brace
                            function_code = content[start_pos : pos + 1]
                            return function_code.strip()
                    pos += 1
            else:
                # Single expression arrow function
                # Find the end of the expression (semicolon or newline)
                pos = search_pos
                paren_count = 0
                brace_count = 0
                bracket_count = 0

                while pos < len(content):
                    char = content[pos]
                    if char == "(":
                        paren_count += 1
                    elif char == ")":
                        paren_count -= 1
                    elif char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                    elif char == "[":
                        bracket_count += 1
                    elif char == "]":
                        bracket_count -= 1
                    elif char == ";" and paren_count == 0 and brace_count == 0 and bracket_count == 0:
                        # End of expression
                        function_code = content[start_pos : pos + 1]
                        return function_code.strip()
                    elif char == "\n" and paren_count == 0 and brace_count == 0 and bracket_count == 0:
                        # Check if next non-whitespace char starts a new statement
                        next_pos = pos + 1
                        while next_pos < len(content) and content[next_pos].isspace():
                            next_pos += 1
                        if next_pos < len(content) and content[next_pos] not in ".":
                            # Likely end of expression
                            function_code = content[start_pos:pos]
                            return function_code.strip()
                    pos += 1

                # If we reach here, take everything to the end
                function_code = content[start_pos:pos]
                return function_code.strip()

            # If we couldn't find matching brace, return partial code
            return content[start_pos : start_pos + 500] + "..."

        except Exception:
            return None

    def _find_function_calls(self, function_info: dict, file_path: str) -> list[str]:
        """
        Find functions called within this function.

        Args:
            function_info: Function information
            file_path: File containing the function

        Returns:
            List of function names called within this function
        """
        calls = []

        try:
            # Extract function body code
            code = self._extract_function_code(function_info)
            if not code:
                return calls

            # More comprehensive patterns for function calls
            # Pattern 1: Object.method() calls (e.g., console.log, Math.max)
            obj_method_pattern = r"(\w+)\.(\w+)\s*\("
            matches = re.finditer(obj_method_pattern, code)
            for match in matches:
                obj_name = match.group(1)
                method_name = match.group(2)
                # Add as object.method format
                calls.append(f"{obj_name}.{method_name}")

            # Pattern 2: this.method() calls
            this_method_pattern = r"this\.(\w+)\s*\("
            matches = re.finditer(this_method_pattern, code)
            for match in matches:
                method_name = match.group(1)
                calls.append(f"this.{method_name}")

            # Pattern 3: Simple function calls (but not after dots)
            # Negative lookbehind to ensure not preceded by a dot
            simple_call_pattern = r"(?<!\.)\b(\w+)\s*\("
            matches = re.finditer(simple_call_pattern, code)
            for match in matches:
                func_name = match.group(1)
                # Filter out common keywords and language constructs
                if func_name not in [
                    "if",
                    "for",
                    "while",
                    "switch",
                    "try",
                    "catch",
                    "return",
                    "typeof",
                    "function",
                    "async",
                    "await",
                    "new",
                    "throw",
                    "const",
                    "let",
                    "var",
                    "constructor",
                    "super",
                ]:
                    # Only add if not already added as part of object.method
                    if not any(call.endswith(f".{func_name}") for call in calls):
                        calls.append(func_name)

            # Pattern 4: await calls
            await_pattern = r"await\s+(\w+(?:\.\w+)*)\s*\("
            matches = re.finditer(await_pattern, code)
            for match in matches:
                func_name = match.group(1)
                if func_name not in calls:
                    calls.append(func_name)

            # Pattern 5: new Constructor() calls
            new_pattern = r"new\s+(\w+)\s*\("
            matches = re.finditer(new_pattern, code)
            for match in matches:
                class_name = match.group(1)
                if class_name not in calls:
                    calls.append(class_name)

            # Remove duplicates while preserving order
            seen = set()
            unique_calls = []
            for call in calls:
                if call not in seen:
                    seen.add(call)
                    unique_calls.append(call)

            return unique_calls

        except Exception:
            return calls

    def analyze_multiple_functions(
        self, function_names: list[str], file_paths: list[str], **kwargs
    ) -> dict[str, FunctionDetail]:
        """
        Analyze multiple functions with shared context optimization.

        Args:
            function_names: List of function names to analyze
            file_paths: List of files to search in
            **kwargs: Additional arguments for analyze_function

        Returns:
            Dictionary mapping function names to FunctionDetail objects
        """
        results = {}

        # Pre-parse all files to build shared context
        parsed_files = {}
        for file_path in file_paths:
            try:
                parse_result = self.parser.parse_file(file_path)
                if parse_result.success:
                    parsed_files[file_path] = parse_result
            except Exception:
                continue

        # Analyze each function
        for func_name in function_names:
            for file_path in file_paths:
                try:
                    result = self.analyze_function(func_name, file_path, **kwargs)
                    if result:
                        results[func_name] = result
                        break  # Found function, move to next
                except Exception:
                    continue

        return results

    def _find_nested_functions(self, code: str) -> dict[str, str]:
        """
        Find nested function definitions within the given code.

        Args:
            code: Function body code

        Returns:
            Dictionary mapping nested function names to their signatures
        """
        nested_functions = {}

        try:
            # Patterns for nested functions
            patterns = [
                # Regular nested function: function name(...) { ... }
                r"function\s+(\w+)\s*\([^)]*\)\s*(?::\s*[^{]+)?\s*\{",
                # Arrow function assigned to const/let: const name = (...) => ...
                r"(?:const|let)\s+(\w+)\s*=\s*\([^)]*\)\s*=>",
                # Arrow function with single param: const name = param => ...
                r"(?:const|let)\s+(\w+)\s*=\s*\w+\s*=>",
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, code)
                for match in matches:
                    func_name = match.group(1)
                    # Exclude the outer function name from nested functions
                    if func_name and not code.startswith(match.group(0)):
                        nested_functions[func_name] = match.group(0).strip()

            return nested_functions

        except Exception:
            return {}

    def _analyze_control_flow(self, code: str) -> dict[str, Any]:
        """
        Analyze control flow patterns in the function.

        Args:
            code: Function body code

        Returns:
            Dictionary with control flow information
        """
        try:
            control_flow = {
                "has_conditionals": False,
                "has_loops": False,
                "has_switch": False,
                "has_try_catch": False,
                "has_async_await": False,
                "has_multiple_returns": False,
                "has_break_continue": False,
            }

            # Check for conditionals
            if re.search(r"\bif\s*\(", code):
                control_flow["has_conditionals"] = True

            # Check for loops
            if re.search(r"\b(for|while|do)\s*\(", code):
                control_flow["has_loops"] = True

            # Check for switch
            if re.search(r"\bswitch\s*\(", code):
                control_flow["has_switch"] = True

            # Check for try/catch
            if re.search(r"\btry\s*\{", code):
                control_flow["has_try_catch"] = True

            # Check for async/await
            if re.search(r"\b(async|await)\b", code):
                control_flow["has_async_await"] = True

            # Check for multiple returns
            return_matches = re.findall(r"\breturn\b", code)
            if len(return_matches) > 1:
                control_flow["has_multiple_returns"] = True

            # Check for break/continue
            if re.search(r"\b(break|continue)\b", code):
                control_flow["has_break_continue"] = True

            return control_flow

        except Exception:
            return {}

    def _track_variables(self, code: str) -> dict[str, Any]:
        """
        Track variable declarations in the function.

        Args:
            code: Function body code

        Returns:
            Dictionary with variable tracking information
        """
        try:
            declarations = []

            # Pattern for variable declarations
            patterns = [
                # const/let/var declarations
                (r"\b(const|let|var)\s+(\w+)(?:\s*:\s*([^=;]+))?(?:\s*=\s*([^;]+))?", "declaration"),
                # Destructuring assignments
                (r"\b(const|let|var)\s*\{([^}]+)\}\s*=", "destructuring"),
                # Array destructuring
                (r"\b(const|let|var)\s*\[([^\]]+)\]\s*=", "array_destructuring"),
            ]

            for pattern, pattern_type in patterns:
                matches = re.finditer(pattern, code)
                for match in matches:
                    if pattern_type == "declaration":
                        declaration_type = match.group(1)
                        var_name = match.group(2)
                        type_annotation = match.group(3)
                        initial_value = match.group(4)

                        declarations.append(
                            {
                                "name": var_name,
                                "declaration_type": declaration_type,
                                "type": type_annotation.strip() if type_annotation else None,
                                "initial_value": initial_value.strip() if initial_value else None,
                            }
                        )
                    elif pattern_type in ["destructuring", "array_destructuring"]:
                        declaration_type = match.group(1)
                        destructured_vars = match.group(2)

                        # Simple extraction of destructured variable names
                        var_names = re.findall(r"\w+", destructured_vars)
                        for var_name in var_names:
                            declarations.append(
                                {
                                    "name": var_name,
                                    "declaration_type": declaration_type,
                                    "type": None,
                                    "initial_value": None,
                                }
                            )

            return {"declarations": declarations}

        except Exception:
            return {"declarations": []}

    def _find_overloads(self, function_name: str, file_path: str) -> list[str]:
        """
        Find all overload signatures for a function.

        Args:
            function_name: Name of the function (can include class name)
            file_path: File containing the function

        Returns:
            List of overload signatures
        """
        overloads = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Extract just the function name for matching
            if "." in function_name:
                _, method_name = function_name.rsplit(".", 1)
            else:
                method_name = function_name

            # Find all occurrences of the function name
            # Pattern to match function signatures (overloads and implementation)
            pattern = rf"{re.escape(method_name)}\s*(?:<[^>]*>)?\s*\([^)]*\)\s*:[^{{;]+[;{{]"

            matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))

            for match in matches:
                signature_text = match.group(0).strip()
                # Remove trailing semicolon or brace
                if signature_text.endswith(";"):
                    signature_text = signature_text[:-1].strip()
                elif signature_text.endswith("{"):
                    signature_text = signature_text[:-1].strip()

                # Format the signature
                if "." not in function_name:
                    # Regular function
                    signature = f"function {signature_text}"
                else:
                    # Method - just use the signature as is
                    signature = signature_text

                overloads.append(signature)

            return overloads

        except Exception:
            return []

    def _build_call_info(self, calls: list[str], file_path: str) -> list[dict[str, Any]]:
        """
        Build detailed information about function calls.

        Args:
            calls: List of function call names
            file_path: Current file path

        Returns:
            List of call information dictionaries
        """
        call_info = []

        for call in calls:
            info = {
                "function_name": call,
                "source_file": file_path,
                "is_imported": False,  # Could be enhanced to check imports
                "is_external": call.startswith(("console.", "Math.", "Promise.", "Array.")),
                "call_type": "method" if "." in call else "direct",
            }
            call_info.append(info)

        return call_info

    def _find_dynamic_calls(self, code: str) -> list[dict[str, Any]]:
        """
        Find dynamic function calls in the code.

        Args:
            code: Function body code

        Returns:
            List of dynamic call information
        """
        dynamic_calls = []

        # Pattern for dynamic property access: obj[expr]
        dynamic_access_pattern = r"\b(\w+)\[(.*?)\]\s*\("
        matches = re.finditer(dynamic_access_pattern, code)
        for match in matches:
            dynamic_calls.append(
                {"type": "dynamic_property_call", "object": match.group(1), "expression": match.group(2).strip()}
            )

        # Pattern for .call() and .apply()
        call_apply_pattern = r"\b(\w+)\.(?:call|apply)\s*\("
        matches = re.finditer(call_apply_pattern, code)
        for match in matches:
            dynamic_calls.append({"type": "call_apply", "function": match.group(1)})

        return dynamic_calls

    def _analyze_async_patterns(self, code: str) -> dict[str, Any]:
        """
        Analyze async patterns in the function.

        Args:
            code: Function body code

        Returns:
            Dictionary with async pattern information
        """
        async_info = {
            "has_async_calls": False,
            "returns_promise": False,
            "uses_await": False,
            "promise_patterns": [],
            "callback_patterns": [],
        }

        # Check for async/await
        if re.search(r"\bawait\b", code):
            async_info["uses_await"] = True
            async_info["has_async_calls"] = True

        # Check for Promise patterns
        promise_patterns = [
            r"Promise\.all",
            r"Promise\.race",
            r"Promise\.resolve",
            r"Promise\.reject",
            r"new\s+Promise",
        ]

        for pattern in promise_patterns:
            if re.search(pattern, code):
                async_info["has_async_calls"] = True
                async_info["promise_patterns"].append(pattern.replace("\\", ""))

        # Check if returns Promise
        if "Promise<" in code or "return Promise" in code:
            async_info["returns_promise"] = True

        return async_info
