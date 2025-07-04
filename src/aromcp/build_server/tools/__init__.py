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
        """Execute whitelisted commands with structured output.

        Args:
            command: Command to execute (must be in whitelist)
            args: Arguments to pass to the command
            project_root: Directory to execute command in (defaults to MCP_FILE_ROOT)
            allowed_commands: List of allowed commands (defaults to predefined
                whitelist)
            timeout: Maximum execution time in seconds (default: 300)
            capture_output: Whether to capture stdout/stderr (default: True)
            env_vars: Additional environment variables to set
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
        """Extract build configuration from various sources.

        Args:
            project_root: Directory to search for config files (defaults to
                MCP_FILE_ROOT)
            config_files: Specific config files to read (defaults to common build
                configs)
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
        """Analyze package.json and installed dependencies.

        Args:
            project_root: Directory containing package.json (defaults to MCP_FILE_ROOT)
            package_manager: Package manager to use ("npm", "yarn", "pnpm", or "auto")
            check_outdated: Whether to check for outdated packages
            check_security: Whether to run security audit
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
        files: list[str] | None = None,
        include_warnings: bool = True,
        timeout: int = 120,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Run tsc and return structured error data.

        Args:
            project_root: Directory containing TypeScript project (defaults to
                MCP_FILE_ROOT)
            tsconfig_path: Path to tsconfig.json relative to project_root
            files: Specific files to check (optional, defaults to all files in project)
            include_warnings: Whether to include TypeScript warnings
            timeout: Maximum execution time in seconds
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
        """
        project_root = get_project_root(project_root)
        return parse_typescript_errors_impl(
            project_root, tsconfig_path, files, include_warnings, timeout, page,
            max_tokens
        )

    @mcp.tool
    @json_convert
    def parse_lint_results(
        linter: str = "eslint",
        project_root: str | None = None,
        target_files: str | list[str] | None = None,
        config_file: str | None = None,
        include_warnings: bool = True,
        timeout: int = 120,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Run linters and return categorized issues.

        Args:
            linter: Linter to use ("eslint", "prettier", "stylelint")
            project_root: Directory to run linter in (defaults to MCP_FILE_ROOT)
            target_files: Specific files to lint (defaults to linter defaults)
            config_file: Path to linter config file
            include_warnings: Whether to include warnings
            timeout: Maximum execution time in seconds
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
        """
        project_root = get_project_root(project_root)
        return parse_lint_results_impl(
            linter, project_root, target_files, config_file, include_warnings,
            timeout, page, max_tokens
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
        """Run Next.js build with categorized error reporting.

        Args:
            project_root: Directory containing Next.js project (defaults to
                MCP_FILE_ROOT)
            build_command: Command to run the build (default: "npm run build")
            include_typescript_check: Whether to include TypeScript type checking
            include_lint_check: Whether to include ESLint checking
            timeout: Maximum execution time in seconds
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
