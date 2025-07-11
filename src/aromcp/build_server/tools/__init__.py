"""Build server tools implementations."""

from typing import Any

from ...utils.json_parameter_middleware import json_convert
from .check_typescript import check_typescript_impl
from .lint_project import lint_project_impl
from .run_test_suite import run_test_suite_impl


def register_build_tools(mcp):
    """Register build tools with the MCP server."""


    @mcp.tool
    @json_convert
    def check_typescript(files: str | list[str] | None = None) -> dict[str, Any]:
        """Run TypeScript compiler to find type errors.

        Use this tool when:
        - Checking for type safety issues before deployment
        - Debugging TypeScript compilation errors
        - Validating type definitions after refactoring
        - Ensuring code meets TypeScript strict mode requirements

        Replaces bash commands: npx tsc, tsc --noEmit

        Args:
            files: Specific files to check (optional, defaults to all files in project)

        Example:
            check_typescript(["src/app.ts"])
            → {"errors": [{"file": "src/app.ts", "line": 42, "message": "Type error"}], "success": false}

        Note: Requires tsconfig.json in project root. Runs npx tsc --noEmit internally.
        """
        return check_typescript_impl(files)

    @mcp.tool
    def lint_project(use_standards: bool = True) -> dict[str, Any]:
        """Run ESLint to find code style issues and potential bugs.

        Use this tool when:
        - Ensuring code follows project style guidelines
        - Finding potential bugs and code smells
        - Preparing code for review or commit
        - Enforcing consistent code formatting

        Replaces bash commands: npx eslint, eslint .

        Args:
            use_standards: Whether to use standards server generated ESLint config

        Example:
            lint_project()
            → {"issues": [{"file": "src/utils.js", "rule": "no-unused-vars", "line": 10}], "fixable": 5}

        Note: Requires ESLint configuration in project. For auto-fixing, run ESLint with --fix flag manually.
        """
        return lint_project_impl(use_standards)

    @mcp.tool
    def run_test_suite(
        test_command: str | None = None,
        test_framework: str = "auto",
        pattern: str | None = None,
        coverage: bool = False,
        timeout: int = 300
    ) -> dict[str, Any]:
        """Execute tests with parsed results.

        Use this tool when:
        - Running project test suites to verify functionality
        - Checking if tests pass before making commits
        - Validating that changes don't break existing tests
        - Getting detailed test results and coverage information

        Replaces bash commands: npm test, yarn test, pytest, jest

        Args:
            test_command: Custom test command (auto-detected if None)
            test_framework: Test framework ("jest", "vitest", "mocha", "pytest", "auto")
            pattern: Test file pattern to run specific tests
            coverage: Whether to generate coverage report
            timeout: Maximum execution time in seconds

        Example:
            run_test_suite()
            → {"tests_passed": 42, "tests_failed": 1, "framework": "jest", "success": false}
        """
        return run_test_suite_impl(
            test_command, test_framework, pattern, coverage, timeout
        )



__all__ = [
    "check_typescript_impl",
    "lint_project_impl",
    "run_test_suite_impl",
    "register_build_tools"
]
