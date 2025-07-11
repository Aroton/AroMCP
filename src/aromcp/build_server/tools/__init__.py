"""Build server tools implementations."""

from typing import Any

from ...filesystem_server._security import get_project_root
from ...utils.json_parameter_middleware import json_convert
from .check_dependencies import check_dependencies_impl
from .get_build_config import get_build_config_impl
from .parse_lint_results import parse_lint_results_impl
from .parse_typescript_errors import parse_typescript_errors_impl
from .run_command import run_command_impl
from .run_nextjs_build import run_nextjs_build_impl
from .run_test_suite import run_test_suite_impl


def register_build_tools(mcp):
    """Register build tools with the MCP server."""

    @mcp.tool
    @json_convert
    def run_command(
        command: str,
        args: str | list[str] | None = None,
        project_root: str | None = None,
        allowed_commands: str | list[str] | None = None,
        timeout: int = 300,
        capture_output: bool = True,
        env_vars: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Execute whitelisted commands safely with structured output.

        Use this tool when:
        - Running build scripts like 'npm run build' or 'make'
        - Executing package manager commands (npm install, pip install)
        - Running custom project scripts defined in package.json
        - Executing safe system commands for project tasks

        This tool executes commands in a controlled environment with timeout
        protection and output capture. Only whitelisted commands are allowed
        to prevent security issues.

        Args:
            command: Command to execute (must be in whitelist)
            args: Arguments to pass to the command
            project_root: Directory to execute command in (defaults to MCP_FILE_ROOT)
            allowed_commands: List of allowed commands (defaults to predefined
                whitelist)
            timeout: Maximum execution time in seconds (default: 300)
            capture_output: Whether to capture stdout/stderr (default: True)
            env_vars: Additional environment variables to set

        Example:
            run_command("npm", args=["run", "build"])
            → {"data": {
                "exit_code": 0,
                "stdout": "Build completed successfully",
                "stderr": "",
                "duration_ms": 5234
              }}

        Note: For simplified usage, use execute_command.
        Common whitelisted commands include npm, yarn, pnpm, pip, git, make.
        """
        project_root = get_project_root(project_root)
        return run_command_impl(
            command, args, project_root, allowed_commands, timeout, capture_output,
            env_vars
        )

    @mcp.tool
    def get_build_config(
        project_root: str | None = None,
        config_files: str | list[str] | None = None
    ) -> dict[str, Any]:
        """Detect and analyze build tools and configuration in your project.

        Use this tool when:
        - Setting up a new development environment
        - Understanding an unfamiliar project's build system
        - Debugging build configuration issues
        - Documenting project setup requirements

        This tool scans for common build configurations (package.json,
        tsconfig.json, webpack.config.js, etc.) and extracts key settings
        like entry points, output paths, and build scripts.

        Args:
            project_root: Directory to search for config files (defaults to
                MCP_FILE_ROOT)
            config_files: Specific config files to read (defaults to common build
                configs)

        Example:
            get_build_config()
            → {"data": {
                "build_tools": ["npm", "webpack", "typescript"],
                "scripts": {"build": "webpack --mode production",
                           "dev": "webpack-dev-server"},
                "entry_points": ["src/index.ts"],
                "output_dir": "dist"
              }}

        Note: To run build commands found here, use run_command or execute_command.
        """
        project_root = get_project_root(project_root)
        return get_build_config_impl(project_root, config_files)

    @mcp.tool
    def check_dependencies(
        project_root: str | None = None,
        package_manager: str = "auto",
        check_outdated: bool = True,
        check_security: bool = True
    ) -> dict[str, Any]:
        """Analyze project dependencies for issues, updates, and vulnerabilities.

        Use this tool when:
        - Auditing for security vulnerabilities before deployment
        - Checking for outdated packages that need updates
        - Understanding the dependency tree and potential conflicts
        - Finding unused dependencies to reduce bundle size

        This tool examines package.json and lock files to analyze
        direct and transitive dependencies, checking for security
        issues, outdated versions, and potential conflicts.

        Args:
            project_root: Directory containing package.json (defaults to MCP_FILE_ROOT)
            package_manager: Package manager to use ("npm", "yarn", "pnpm", or "auto")
            check_outdated: Whether to check for outdated packages
            check_security: Whether to run security audit

        Example:
            check_dependencies(check_security=True)
            → {"data": {
                "vulnerabilities": {"high": 2, "medium": 5, "low": 12},
                "outdated": {"major": 3, "minor": 12, "patch": 25},
                "unused": ["lodash", "moment"],
                "total_dependencies": 145
              }}

        Note: To update dependencies, use run_command with npm/yarn/pnpm commands.
        For finding unused code (not packages), use find_dead_code.
        """
        project_root = get_project_root(project_root)
        return check_dependencies_impl(
            project_root, package_manager, check_outdated, check_security
        )

    @mcp.tool
    @json_convert
    def parse_typescript_errors(
        project_root: str | None = None,
        tsconfig_path: str = "tsconfig.json",
        files: str | list[str] | None = None,
        include_warnings: bool = True,
        timeout: int = 120,
        page: int = 1,
        max_tokens: int = 20000,
        use_build_command: bool = False
    ) -> dict[str, Any]:
        """Run TypeScript compiler to find type errors and issues.

        Use this tool when:
        - Checking for type safety issues before deployment
        - Debugging TypeScript compilation errors
        - Validating type definitions after refactoring
        - Ensuring code meets TypeScript strict mode requirements

        This tool runs the TypeScript compiler (tsc) and parses its output
        into structured error data with file locations, error codes, and
        suggested fixes.

        Args:
            project_root: Directory containing TypeScript project (defaults to
                MCP_FILE_ROOT)
            tsconfig_path: Path to tsconfig.json relative to project_root
            files: Specific files to check (optional, defaults to all files in project)
            include_warnings: Whether to include TypeScript warnings
            timeout: Maximum execution time in seconds
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
            use_build_command: Whether to use build command for type checking (e.g., "npm run build")

        Example:
            parse_typescript_errors(include_warnings=True)
            → {"data": {
                "errors": [
                  {"file": "src/app.ts", "line": 42, "column": 15,
                   "code": "TS2345", "severity": "error",
                   "message": "Argument of type 'string' is not assignable to parameter of type 'number'"}
                ],
                "summary": {"error_count": 3, "warning_count": 7, "files_with_errors": 2}
              }}

        Note: For simplified usage, use check_typescript.
        This tool actually runs tsc, not just parses existing output.
        """
        project_root = get_project_root(project_root)
        return parse_typescript_errors_impl(
            project_root, tsconfig_path, files, include_warnings, timeout, page,
            max_tokens, use_build_command
        )

    @mcp.tool
    @json_convert
    def parse_lint_results(
        linter: str = "eslint",
        project_root: str | None = None,
        target_files: str | list[str] | None = None,
        config_file: str | None = None,
        include_warnings: bool = True,
        use_standards_eslint: bool = False,
        timeout: int = 120,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Run code linters to find style issues and potential bugs.

        Use this tool when:
        - Ensuring code follows project style guidelines
        - Finding potential bugs and code smells
        - Preparing code for review or commit
        - Enforcing consistent code formatting

        This tool runs the specified linter (ESLint, Prettier, or Stylelint)
        and returns categorized issues with locations, severity levels, and
        fix suggestions. Many issues can be auto-fixed.

        Args:
            linter: Linter to use ("eslint", "prettier", "stylelint")
            project_root: Directory to run linter in (defaults to MCP_FILE_ROOT)
            target_files: Specific files to lint (defaults to linter defaults)
            config_file: Path to linter config file
            include_warnings: Whether to include warnings
            use_standards_eslint: Whether to include generated ESLint rules from standards server
            timeout: Maximum execution time in seconds
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)

        Example:
            parse_lint_results(linter="eslint", include_warnings=True)
            → {"data": {
                "issues": [
                  {"file": "src/utils.js", "line": 10, "column": 5,
                   "severity": "warning", "rule": "no-unused-vars",
                   "message": "'temp' is defined but never used",
                   "fixable": true}
                ],
                "summary": {"errors": 2, "warnings": 15, "fixable": 12}
              }}

        Note: For simplified usage, use lint_project.
        This tool actually runs the linter, not just parses existing results.
        To auto-fix issues, use run_command with '--fix' flag.
        """
        project_root = get_project_root(project_root)
        return parse_lint_results_impl(
            linter, project_root, target_files, config_file, include_warnings,
            use_standards_eslint, timeout, page, max_tokens
        )

    @mcp.tool
    def run_test_suite(
        project_root: str | None = None,
        test_command: str | None = None,
        test_framework: str = "auto",
        pattern: str | None = None,
        coverage: bool = False,
        timeout: int = 300
    ) -> dict[str, Any]:
        """Execute tests with parsed results.

        Args:
            project_root: Directory to run tests in (defaults to MCP_FILE_ROOT)
            test_command: Custom test command (auto-detected if None)
            test_framework: Test framework ("jest", "vitest", "mocha", "pytest", "auto")
            pattern: Test file pattern to run specific tests
            coverage: Whether to generate coverage report
            timeout: Maximum execution time in seconds
        """
        project_root = get_project_root(project_root)
        return run_test_suite_impl(
            project_root, test_command, test_framework, pattern, coverage, timeout
        )

    @mcp.tool
    def run_nextjs_build(
        project_root: str | None = None,
        build_command: str = "npm run build",
        include_typescript_check: bool = True,
        include_lint_check: bool = True,
        timeout: int = 600
    ) -> dict[str, Any]:
        """Run Next.js build process with detailed error reporting.

        Use this tool when:
        - Building a Next.js application for production deployment
        - Validating that the Next.js app compiles without errors
        - Checking for build-time issues specific to Next.js
        - Generating optimized production bundles

        This tool runs the Next.js build process and provides detailed
        error reporting for TypeScript, ESLint, and Next.js-specific
        issues like missing pages or API routes.

        Args:
            project_root: Directory containing Next.js project (defaults to
                MCP_FILE_ROOT)
            build_command: Command to run the build (default: "npm run build")
            include_typescript_check: Whether to include TypeScript type checking
            include_lint_check: Whether to include ESLint checking
            timeout: Maximum execution time in seconds

        Example:
            run_nextjs_build()
            → {"data": {
                "success": false,
                "errors": {
                  "typescript": [{"file": "pages/api/user.ts", "error": "Type error"}],
                  "eslint": [{"file": "components/Header.tsx", "error": "Missing key prop"}],
                  "nextjs": [{"type": "missing_export", "page": "/about"}]
                },
                "build_output": "Compiled with errors..."
              }}

        Note: This is specific to Next.js projects. For general builds, use run_command.
        Includes Next.js-specific validations like page exports and API routes.
        """
        project_root = get_project_root(project_root)
        return run_nextjs_build_impl(
            project_root, build_command, include_typescript_check, include_lint_check,
            timeout
        )


__all__ = [
    "run_command_impl",
    "get_build_config_impl",
    "check_dependencies_impl",
    "parse_typescript_errors_impl",
    "parse_lint_results_impl",
    "run_test_suite_impl",
    "run_nextjs_build_impl",
    "register_build_tools"
]
