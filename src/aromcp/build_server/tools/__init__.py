"""Build server tools implementations."""

from ...utils.json_parameter_middleware import json_convert
from ..models.build_models import (
    CheckTypescriptResponse,
    LintProjectResponse,
    RunTestSuiteResponse,
)
from .check_typescript import check_typescript_impl
from .lint_project import lint_project_impl
from .run_test_suite import run_test_suite_impl


def register_build_tools(mcp):
    """Register build tools with the MCP server."""

    @mcp.tool
    @json_convert
    def check_typescript(files: str | list[str] | None = None) -> CheckTypescriptResponse:  # noqa: F841
        """Run TypeScript compiler to find type errors.

        Use this tool when:
        - REQUIRED: After every TypeScript/JavaScript file edit before proceeding
        - REQUIRED: Before committing code changes to ensure they will build
        - REQUIRED: After completing any coding task to validate TypeScript compilation
        - After refactoring code to catch type definition issues
        - When you need to verify the project builds without compilation errors

        Replaces bash commands: npx tsc, tsc --noEmit

        Args:
            files: Files, directories, or glob patterns (directories auto-glob with /*, glob patterns passed through)

        Example:
            # WORKFLOW: After editing code, always run this
            check_typescript()  # Check entire project
            → {"errors": [{"file": "src/app.ts", "line": 42, "message": "Type error"}], "total": 3, "check_again": true}
            # Fix the errors, then run again
            check_typescript()  # Re-check after fixes
            → {"errors": [], "check_again": false}  # Now safe to proceed

            check_typescript(["src/app.ts"])  # Check specific files
            → {"errors": [{"file": "src/app.ts", "line": 42, "message": "Type error"}], "total": 3, "check_again": true}

            check_typescript("src/components")  # Auto-globs to src/components/*
            → {"errors": [], "check_again": false}

            check_typescript("src/**/*.ts")  # Glob patterns passed directly to tsc
            → {"errors": [], "check_again": false}

        Note: ESSENTIAL quality gate - run this after EVERY code edit. Requires tsconfig.json in project root.
        Shows only first file's errors with total count. When check_again=true, fix errors and run again.
        Code should NOT be considered complete until this returns check_again=false.
        """
        # Simply return the result from check_typescript_impl, which now returns CheckTypescriptResponse
        return check_typescript_impl(files)

    @mcp.tool
    @json_convert
    def lint_project(
        use_standards: bool = True,
        files: str | list[str] | None = None,
        debug: bool = False,
        cursor: str | None = None,
        max_tokens: int = 20000,
    ) -> LintProjectResponse:  # noqa: F841
        """Run ESLint to find code style issues and potential bugs.

        This tool uses server-side cursor pagination. The server handles all pagination automatically.
        To retrieve all lint issues:
        1. First call: Always use cursor=None
        2. If response has_more=true, make another call with cursor=next_cursor from response
        3. Repeat until has_more=false

        Use this tool when:
        - REQUIRED: After every code edit to catch style issues and bugs early
        - REQUIRED: Before committing code changes to ensure clean, consistent code
        - REQUIRED: After completing any coding task to validate code quality
        - After adding new features to ensure they follow project standards
        - When you need to verify code meets style guidelines before building

        Replaces bash commands: npx eslint, eslint .

        Args:
            use_standards: Whether to use standards server generated ESLint config (recommended)
            files: Files, directories, or glob patterns (directories auto-glob with /*,
                glob patterns passed through)
            debug: Enable detailed debug output for troubleshooting linting issues
            cursor: Pagination cursor from previous response. MUST be None for first request, then use exact next_cursor value from previous response. Never generate your own cursor values.
            max_tokens: Maximum tokens per response

        Example:
            # WORKFLOW: After editing code, always run this
            lint_project()  # Check entire project with standards
            → {"issues": [{"file": "src/utils.js", "rule": "no-unused-vars", "line": 10}],
               "total": 8, "fixable": 5, "check_again": true}
            # Fix the issues, then run again
            lint_project()  # Re-check after fixes
            → {"issues": [], "check_again": false}  # Now safe to proceed

            lint_project(use_standards=True)  # Explicit standards usage
            → {"issues": [{"file": "src/utils.js", "rule": "no-unused-vars", "line": 10}],
               "total": 8, "fixable": 5, "check_again": true}

            lint_project(files="src/components")  # Auto-globs to src/components/*
            → {"issues": [], "check_again": false}

            lint_project(files="src/**/*.ts")  # Glob patterns passed directly to eslint
            → {"issues": [], "check_again": false}

        Cursor Pagination Examples:
            # First request - ALWAYS start with cursor=None
            lint_project(cursor=None, max_tokens=5000)
            → {"issues": [...25 lint issues...], "total": 150, "next_cursor": "src/utils.js", "has_more": true}
            
            # Second request - use EXACT next_cursor from previous response
            lint_project(cursor="src/utils.js", max_tokens=5000)
            → {"issues": [...25 more lint issues...], "total": 150, "next_cursor": "tests/test_app.js", "has_more": true}
            
            # Continue until has_more is false
            lint_project(cursor="tests/test_app.js", max_tokens=5000)
            → {"issues": [...final lint issues...], "total": 150, "next_cursor": null, "has_more": false}

        Response always includes:
        - issues: Array of lint issue objects for this page
        - total: Total number of lint issues across all pages
        - next_cursor: Cursor for next page (null if no more pages)
        - has_more: Boolean indicating if more pages exist

        IMPORTANT: Do NOT attempt to implement your own pagination logic. The server handles all pagination. 
        Simply use the cursor values provided in responses.

        Note: ESSENTIAL quality gate - run this after EVERY code edit. Always use use_standards=True for best results.
        Shows only first file's issues with total count. When check_again=true, fix issues and run again.
        Code should NOT be considered complete until this returns check_again=false.
        """
        # Simply return the result from lint_project_impl, which now returns LintProjectResponse
        return lint_project_impl(use_standards, files, debug, cursor, max_tokens)

    @mcp.tool
    def run_test_suite(  # noqa: F841
        test_command: str | None = None,
        test_framework: str = "auto",
        pattern: str | None = None,
        coverage: bool = False,
        timeout: int = 300,
        cursor: str | None = None,
        max_tokens: int = 20000,
    ) -> RunTestSuiteResponse:
        """Execute tests with parsed results.

        This tool uses server-side cursor pagination. The server handles all pagination automatically.
        To retrieve all test results:
        1. First call: Always use cursor=None
        2. If response has_more=true, make another call with cursor=next_cursor from response
        3. Repeat until has_more=false

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
            cursor: Pagination cursor from previous response. MUST be None for first request, then use exact next_cursor value from previous response. Never generate your own cursor values.
            max_tokens: Maximum tokens per response

        Example:
            run_test_suite()
            → {"tests_passed": 42, "tests_failed": 1, "framework": "jest", "success": false}

        Cursor Pagination Examples:
            # First request - ALWAYS start with cursor=None
            run_test_suite(cursor=None, max_tokens=5000)
            → {"test_results": [...50 test results...], "total": 155, "next_cursor": "tests/components/Button.test.js", "has_more": true}
            
            # Second request - use EXACT next_cursor from previous response
            run_test_suite(cursor="tests/components/Button.test.js", max_tokens=5000)
            → {"test_results": [...50 more test results...], "total": 155, "next_cursor": "tests/utils/helpers.test.js", "has_more": true}
            
            # Continue until has_more is false
            run_test_suite(cursor="tests/utils/helpers.test.js", max_tokens=5000)
            → {"test_results": [...final test results...], "total": 155, "next_cursor": null, "has_more": false}

        Response always includes:
        - test_results: Array of test result objects for this page
        - total: Total number of test results across all pages
        - next_cursor: Cursor for next page (null if no more pages)
        - has_more: Boolean indicating if more pages exist

        IMPORTANT: Do NOT attempt to implement your own pagination logic. The server handles all pagination. 
        Simply use the cursor values provided in responses.

        Note: Auto-detects test framework from package.json or project files. For linting use lint_project,
        for TypeScript checking use check_typescript. Supports parallel test execution where available.
        Results are automatically paginated if they exceed max_tokens.
        """
        # Implementation now returns RunTestSuiteResponse directly
        return run_test_suite_impl(test_command, test_framework, pattern, coverage, timeout, cursor, max_tokens)


__all__ = ["check_typescript_impl", "lint_project_impl", "run_test_suite_impl", "register_build_tools"]
