"""
Conditional Analyzer for TypeScript function call analysis.

This module analyzes conditional execution paths in TypeScript functions,
identifying if/else, switch, try/catch patterns and estimating execution probabilities.
"""

import re
from typing import Any

from ..models.typescript_models import ConditionalPath, ExecutionPath


class ConditionalAnalyzer:
    """Analyzes conditional execution paths in TypeScript functions."""

    def __init__(self, parser=None):
        """Initialize the conditional analyzer.

        Args:
            parser: TypeScript parser (can be None for regex-only mode)
        """
        self.parser = parser

    def analyze_conditional_paths(self, func_name: str, file_path: str) -> list[ConditionalPath]:
        """Analyze conditional execution paths in a function.

        Args:
            func_name: Name of the function to analyze
            file_path: Path to the file containing the function

        Returns:
            List of ConditionalPath objects representing different execution branches
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Find function body
            function_body = self._extract_function_body(func_name, content)
            if not function_body:
                return []

            conditional_paths = []

            # Analyze if/else statements
            if_patterns = self._find_if_statements(function_body)
            for if_info in if_patterns:
                conditional_paths.extend(self._analyze_if_statement(if_info))

            # Analyze switch statements
            switch_patterns = self._find_switch_statements(function_body)
            for switch_info in switch_patterns:
                conditional_paths.extend(self._analyze_switch_statement(switch_info))

            # Analyze try/catch blocks
            try_catch_patterns = self._find_try_catch_blocks(function_body)
            for try_info in try_catch_patterns:
                conditional_paths.extend(self._analyze_try_catch(try_info))

            return conditional_paths

        except Exception:
            return []

    def enhance_execution_paths_with_conditions(
        self, execution_paths: list[ExecutionPath], func_name: str, file_path: str
    ) -> list[ExecutionPath]:
        """Enhance execution paths with conditional information.

        Args:
            execution_paths: Existing execution paths
            func_name: Function name to analyze
            file_path: File containing the function

        Returns:
            Enhanced execution paths with conditional information
        """
        conditional_paths = self.analyze_conditional_paths(func_name, file_path)

        if not conditional_paths:
            return execution_paths

        enhanced_paths = []

        for path in execution_paths:
            # Check if any functions in the path have conditional calls
            path_has_conditions = False

            for i, func in enumerate(path.path):
                matching_conditions = [
                    cp for cp in conditional_paths if any(call in cp.function_calls for call in path.path[i : i + 2])
                ]

                if matching_conditions:
                    # Create enhanced path with condition information
                    condition = matching_conditions[0]
                    enhanced_path = ExecutionPath(
                        path=path.path,
                        condition=condition.condition,
                        execution_probability=condition.execution_probability,
                    )
                    enhanced_paths.append(enhanced_path)
                    path_has_conditions = True
                    break

            # If no conditions found, add original path
            if not path_has_conditions:
                enhanced_paths.append(path)

        return enhanced_paths

    def _extract_function_body(self, func_name: str, content: str) -> str:
        """Extract the body of a function."""
        # Multiple patterns to match different function declarations
        patterns = [
            # export function funcName(...)
            rf"export\s+function\s+{re.escape(func_name)}\s*\([^)]*\)\s*:\s*[^{{]*\s*\{{",
            rf"export\s+function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
            # function funcName(...)
            rf"function\s+{re.escape(func_name)}\s*\([^)]*\)\s*:\s*[^{{]*\s*\{{",
            rf"function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
            # const funcName = (...) =>
            rf"const\s+{re.escape(func_name)}\s*=\s*\([^)]*\)\s*:\s*[^=>]*=>\s*\{{",
            rf"const\s+{re.escape(func_name)}\s*=\s*\([^)]*\)\s*=>\s*\{{",
            # method definition: funcName(...) {
            rf"{re.escape(func_name)}\s*\([^)]*\)\s*:\s*[^{{]*\s*\{{",
            rf"{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                start_pos = match.end() - 1  # Position of opening brace

                # Find matching closing brace
                brace_count = 1
                pos = start_pos + 1
                while pos < len(content) and brace_count > 0:
                    char = content[pos]
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                    pos += 1

                if brace_count == 0:
                    return content[start_pos:pos]

        return ""

    def _find_if_statements(self, code: str) -> list[dict[str, Any]]:
        """Find if/else statements and extract conditions."""
        if_patterns = []

        # Pattern for if/else with proper brace matching
        if_pattern = r"if\s*\(([^)]+)\)\s*\{"
        matches = list(re.finditer(if_pattern, code, re.MULTILINE))

        for match in matches:
            condition = match.group(1).strip()
            start_pos = match.end() - 1  # Position of opening brace

            # Extract if block
            then_block = self._extract_block_content(code, start_pos)

            # Look for corresponding else
            else_block = None
            else_pos = start_pos + len(then_block) + 1

            # Skip whitespace
            while else_pos < len(code) and code[else_pos].isspace():
                else_pos += 1

            # Check for else keyword
            if else_pos < len(code) - 4 and code[else_pos : else_pos + 4] == "else":
                else_match = re.match(r"else\s*\{", code[else_pos:])
                if else_match:
                    else_start = else_pos + else_match.end() - 1
                    else_block = self._extract_block_content(code, else_start)

            if_patterns.append(
                {"condition": condition, "then_block": then_block, "else_block": else_block, "type": "if_statement"}
            )

        return if_patterns

    def _find_switch_statements(self, code: str) -> list[dict[str, Any]]:
        """Find switch statements and extract cases."""
        switch_patterns = []

        switch_pattern = r"switch\s*\(([^)]+)\)\s*\{"
        matches = re.finditer(switch_pattern, code, re.MULTILINE)

        for match in matches:
            switch_expr = match.group(1).strip()
            start_pos = match.end() - 1

            switch_body = self._extract_block_content(code, start_pos)
            cases = self._extract_switch_cases(switch_body)

            switch_patterns.append({"expression": switch_expr, "cases": cases, "type": "switch_statement"})

        return switch_patterns

    def _find_try_catch_blocks(self, code: str) -> list[dict[str, Any]]:
        """Find try/catch blocks."""
        try_patterns = []

        try_pattern = r"try\s*\{"
        matches = re.finditer(try_pattern, code, re.MULTILINE)

        for match in matches:
            start_pos = match.end() - 1
            try_block = self._extract_block_content(code, start_pos)

            # Look for catch block
            catch_block = None
            finally_block = None

            end_pos = start_pos + len(try_block) + 1
            remaining_code = code[end_pos:]

            catch_match = re.match(r"\s*catch\s*\([^)]*\)\s*\{", remaining_code)
            if catch_match:
                catch_start = end_pos + catch_match.end() - 1
                catch_block = self._extract_block_content(code, catch_start)

            try_patterns.append(
                {
                    "try_block": try_block,
                    "catch_block": catch_block,
                    "finally_block": finally_block,
                    "type": "try_catch",
                }
            )

        return try_patterns

    def _extract_block_content(self, code: str, start_pos: int) -> str:
        """Extract content of a code block starting from opening brace."""
        if start_pos >= len(code) or code[start_pos] != "{":
            return ""

        brace_count = 1
        pos = start_pos + 1

        while pos < len(code) and brace_count > 0:
            char = code[pos]
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
            pos += 1

        if brace_count == 0:
            return code[start_pos + 1 : pos - 1]  # Exclude braces
        return ""

    def _extract_switch_cases(self, switch_body: str) -> list[dict[str, Any]]:
        """Extract case statements from switch body."""
        cases = []

        case_pattern = r"case\s+([^:]+):\s*(.*?)(?=case\s|default\s*:|$)"
        case_matches = re.finditer(case_pattern, switch_body, re.MULTILINE | re.DOTALL)

        for match in case_matches:
            case_value = match.group(1).strip()
            case_body = match.group(2).strip()

            cases.append({"value": case_value, "body": case_body, "type": "case"})

        # Look for default case
        default_match = re.search(r"default\s*:\s*(.*)", switch_body, re.MULTILINE | re.DOTALL)
        if default_match:
            cases.append({"value": "default", "body": default_match.group(1).strip(), "type": "default"})

        return cases

    def _analyze_if_statement(self, if_info: dict[str, Any]) -> list[ConditionalPath]:
        """Analyze if statement execution paths."""
        paths = []

        # Then path
        then_calls = self._extract_function_calls(if_info["then_block"])
        paths.append(
            ConditionalPath(
                condition=if_info["condition"],
                execution_probability=0.5,  # Default 50% probability
                function_calls=then_calls,
                path_type="if_then",
            )
        )

        # Else path
        if if_info["else_block"]:
            else_calls = self._extract_function_calls(if_info["else_block"])
            paths.append(
                ConditionalPath(
                    condition=f"!({if_info['condition']})",
                    execution_probability=0.5,
                    function_calls=else_calls,
                    path_type="if_else",
                )
            )

        return paths

    def _analyze_switch_statement(self, switch_info: dict[str, Any]) -> list[ConditionalPath]:
        """Analyze switch statement execution paths."""
        paths = []
        cases = switch_info["cases"]

        if not cases:
            return paths

        # Equal probability for each case (simplified)
        case_probability = 1.0 / len(cases)

        for case in cases:
            case_calls = self._extract_function_calls(case["body"])
            condition = f"{switch_info['expression']} === {case['value']}" if case["type"] != "default" else "default"

            paths.append(
                ConditionalPath(
                    condition=condition,
                    execution_probability=case_probability,
                    function_calls=case_calls,
                    path_type=f"switch_{case['type']}",
                )
            )

        return paths

    def _analyze_try_catch(self, try_info: dict[str, Any]) -> list[ConditionalPath]:
        """Analyze try/catch execution paths."""
        paths = []

        # Try path (normal execution)
        try_calls = self._extract_function_calls(try_info["try_block"])
        paths.append(
            ConditionalPath(
                condition="no exception thrown",
                execution_probability=0.8,  # Assume 80% success rate
                function_calls=try_calls,
                path_type="try_normal",
            )
        )

        # Catch path (exception handling)
        if try_info["catch_block"]:
            catch_calls = self._extract_function_calls(try_info["catch_block"])
            paths.append(
                ConditionalPath(
                    condition="exception thrown",
                    execution_probability=0.2,  # Assume 20% exception rate
                    function_calls=catch_calls,
                    path_type="try_catch",
                )
            )

        return paths

    def _extract_function_calls(self, code_block: str) -> list[str]:
        """Extract function calls from a code block."""
        calls = []

        # Pattern for function calls
        call_pattern = r"(\w+)\s*\("
        matches = re.finditer(call_pattern, code_block)

        for match in matches:
            func_name = match.group(1)

            # Skip common keywords
            if func_name not in ["if", "for", "while", "catch", "return", "new", "typeof", "instanceof"]:
                calls.append(func_name)

        return calls

    def get_condition_complexity_score(self, condition: str) -> float:
        """Calculate complexity score for a condition (0.0-1.0)."""
        # Simple heuristic based on operators and nesting
        complexity_indicators = ["&&", "||", "!", "(", ")", "===", "!==", "<", ">", "<=", ">="]

        score = 0.1  # Base complexity
        for indicator in complexity_indicators:
            score += condition.count(indicator) * 0.1

        return min(score, 1.0)  # Cap at 1.0
