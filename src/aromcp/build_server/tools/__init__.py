"""Build server tools implementations."""

from ...utils.json_parameter_middleware import json_convert
from ..models.build_models import (
    CheckTypescriptResponse,
    LintProjectResponse,
    RunTestSuiteResponse,
    TestSuiteInfo,
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
        from ..models.build_models import TypescriptError

        result = check_typescript_impl(files)

        # Convert dict errors to TypescriptError dataclasses
        errors = []
        for error in result["errors"]:
            errors.append(
                TypescriptError(
                    file=error["file"],
                    line=error["line"],
                    column=error["column"],
                    message=error["message"],
                    code=error["code"],
                    severity=error["severity"],
                )
            )

        return CheckTypescriptResponse(
            errors=errors,
            total_errors=result["total_errors"],
            files_checked=result["files_checked"],
            check_again=result["check_again"],
            success=result["success"],
        )

    @mcp.tool
    @json_convert
    def lint_project(
        use_standards: bool = True, files: str | list[str] | None = None, debug: bool = False
    ) -> LintProjectResponse:  # noqa: F841
        """Run ESLint to find code style issues and potential bugs.

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

        Note: ESSENTIAL quality gate - run this after EVERY code edit. Always use use_standards=True for best results.
        Shows only first file's issues with total count. When check_again=true, fix issues and run again.
        Code should NOT be considered complete until this returns check_again=false.
        """
        from ..models.build_models import LintIssue

        result = lint_project_impl(use_standards, files, debug)

        # Convert dict issues to LintIssue dataclasses
        issues = []
        for issue in result["issues"]:
            issues.append(
                LintIssue(
                    file=issue["file"],
                    line=issue["line"],
                    column=issue["column"],
                    rule=issue["rule"],
                    message=issue["message"],
                    severity=issue["severity"],
                    fixable=issue["fixable"],
                )
            )

        return LintProjectResponse(
            issues=issues,
            total_issues=result["total_issues"],
            fixable_issues=result["fixable_issues"],
            files_checked=result["files_checked"],
            check_again=result["check_again"],
            success=result["success"],
        )

    @mcp.tool
    def run_test_suite(  # noqa: F841
        test_command: str | None = None,
        test_framework: str = "auto",
        pattern: str | None = None,
        coverage: bool = False,
        timeout: int = 300,
    ) -> RunTestSuiteResponse:
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

        Note: Auto-detects test framework from package.json or project files. For linting use lint_project,
        for TypeScript checking use check_typescript. Supports parallel test execution where available.
        """
        from ..models.build_models import TestResult

        result = run_test_suite_impl(test_command, test_framework, pattern, coverage, timeout)

        # Convert test_results to TestResult dataclasses
        test_results = []
        for test_result in result["test_results"]:
            if isinstance(test_result, dict):
                status = test_result.get("status", "unknown")
                # Filter out test results with unknown status
                if status != "unknown":
                    test_results.append(
                        TestResult(
                            name=test_result.get("name", ""),
                            status=status,
                            duration=test_result.get("duration", 0.0),
                            file=test_result.get("file", ""),
                            error_message=test_result.get("error_message"),
                        )
                    )

        # Handle test_suites if present
        test_suites = None
        if "test_suites" in result:
            test_suites_data = result["test_suites"]
            test_suites = TestSuiteInfo(
                total=test_suites_data["total"],
                passed=test_suites_data["passed"],
                failed=test_suites_data["failed"],
            )

        return RunTestSuiteResponse(
            tests_passed=result["tests_passed"],
            tests_failed=result["tests_failed"],
            tests_skipped=result["tests_skipped"],
            total_tests=result["total_tests"],
            framework=result["framework"],
            duration=result["duration"],
            success=result["success"],
            coverage=result["coverage"],
            test_results=test_results,
            test_suites=test_suites,
        )


__all__ = ["check_typescript_impl", "lint_project_impl", "run_test_suite_impl", "register_build_tools"]
