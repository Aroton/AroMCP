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

    # Simplified tools for better AI agent adoption - these are aliases with sensible defaults
    @mcp.tool
    def lint_project(
        project_root: str | None = None,
        linter: str = "eslint",
        include_warnings: bool = True
    ) -> dict[str, Any]:
        """Run code quality checks using ESLint, Prettier, or Stylelint.
        
        Use this tool when:
        - Checking code quality before committing changes
        - Finding style violations and potential bugs
        - Ensuring consistent code formatting across the project
        - Preparing for code review
        
        Simple tool to run linters with sensible defaults. Many issues
        can be automatically fixed using the linter's fix options.

        Args:
            project_root: Directory to run linter in (defaults to MCP_FILE_ROOT)
            linter: Which linter to use ("eslint", "prettier", "stylelint")
            include_warnings: Whether to include warnings or just errors
            
        Example:
            lint_project()
            → {"data": {
                "issues": [{"file": "src/app.js", "line": 10, "message": "Missing semicolon"}],
                "summary": {"errors": 2, "warnings": 5, "fixable": 6}
              }}
              
        Note: For auto-fixing issues, use execute_command("npm run lint -- --fix").
        For TypeScript-specific checks, use check_typescript instead.
        """
        project_root = get_project_root(project_root)
        # Call the full implementation with sensible defaults
        return parse_lint_results_impl(
            linter=linter,
            project_root=project_root,
            target_files=None,  # Use linter defaults
            config_file=None,   # Auto-detect
            include_warnings=include_warnings,
            use_standards_eslint=False,  # Keep it simple
            timeout=120,        # Standard timeout
            page=1,            # First page
            max_tokens=20000   # Standard limit
        )

    @mcp.tool
    def check_typescript(
        project_root: str | None = None,
        include_warnings: bool = True
    ) -> dict[str, Any]:
        """Check TypeScript files for type errors and compilation issues.
        
        Use this tool when:
        - Validating TypeScript code compiles without errors
        - Finding type mismatches after refactoring
        - Ensuring type safety before deployment
        - Debugging "cannot find module" or type definition issues
        
        Simple tool to run TypeScript compiler checks with clear error messages.
        Shows exactly where type errors occur and what's wrong.

        Args:
            project_root: Directory containing TypeScript project (defaults to MCP_FILE_ROOT)
            include_warnings: Whether to include warnings or just errors
            
        Example:
            check_typescript()
            → {"data": {
                "errors": [{"file": "src/utils.ts", "line": 15, 
                           "message": "Type 'string' is not assignable to type 'number'"}],
                "summary": {"error_count": 3, "warning_count": 7}
              }}
              
        Note: For code style issues, use lint_project instead.
        This focuses only on TypeScript compilation and type checking.
        """
        project_root = get_project_root(project_root)
        # Call the full implementation with sensible defaults
        return parse_typescript_errors_impl(
            project_root=project_root,
            tsconfig_path="tsconfig.json",  # Standard config
            files=None,                     # Check all files
            include_warnings=include_warnings,
            timeout=120,                    # Standard timeout
            page=1,                        # First page
            max_tokens=20000,              # Standard limit
            use_build_command=False        # Use direct tsc
        )

    @mcp.tool
    def run_tests(
        project_root: str | None = None,
        coverage: bool = False
    ) -> dict[str, Any]:
        """Run your project's test suite with detailed results.
        
        Use this tool when:
        - Validating code changes didn't break existing functionality
        - Running tests before committing or merging
        - Checking test coverage to find untested code
        - Ensuring all tests pass before deployment
        
        Simple tool that auto-detects your test framework (Jest, Vitest, Mocha, etc.)
        and runs all tests with clear pass/fail reporting.

        Args:
            project_root: Directory to run tests in (defaults to MCP_FILE_ROOT)
            coverage: Whether to generate coverage report
            
        Example:
            run_tests(coverage=True)
            → {"data": {
                "tests": {"passed": 45, "failed": 1, "total": 46},
                "failures": [{"test": "should validate email", "error": "Expected true"}],
                "coverage": {"lines": 87.5, "branches": 82.3}
              }}
              
        Note: Test framework is auto-detected from package.json.
        For running specific test files, use the full run_test_suite tool.
        """
        project_root = get_project_root(project_root)
        # Call the full implementation with sensible defaults
        return run_test_suite_impl(
            project_root=project_root,
            test_command=None,        # Auto-detect
            test_framework="auto",    # Auto-detect framework
            pattern=None,            # Run all tests
            coverage=coverage,
            timeout=300              # Standard timeout
        )

    @mcp.tool
    def execute_command(
        command: str,
        project_root: str | None = None
    ) -> dict[str, Any]:
        """Execute safe development commands in your project.
        
        Use this tool when:
        - Running build commands like "npm run build"
        - Installing dependencies with "npm install"
        - Executing project scripts from package.json
        - Running safe system commands for development
        
        Simple tool to run whitelisted commands safely. Common commands
        like npm, yarn, git, and make are pre-approved.

        Args:
            command: Command to execute (must be whitelisted)
            project_root: Directory to execute command in (defaults to MCP_FILE_ROOT)
            
        Example:
            execute_command("npm run build")
            → {"data": {
                "exit_code": 0,
                "stdout": "Build completed successfully in 12.3s",
                "duration_ms": 12340
              }}
              
        Note: Commands are split automatically - just pass the full command string.
        For complex commands with pipes or redirects, use the full run_command tool.
        """
        project_root = get_project_root(project_root)
        # Call the full implementation with sensible defaults
        return run_command_impl(
            command=command,
            args=None,                    # No additional args
            project_root=project_root,
            allowed_commands=None,        # Use default whitelist
            timeout=300,                  # Standard timeout
            capture_output=True,          # Always capture output
            env_vars=None                 # No custom env vars
        )

    @mcp.tool
    def quality_check(
        project_root: str | None = None,
        include_typescript: bool = True,
        include_tests: bool = False
    ) -> dict[str, Any]:
        """Run comprehensive code quality checks in one command.
        
        Use this tool when:
        - Doing a final check before committing or creating a PR
        - Setting up CI/CD quality gates
        - Ensuring all code standards are met at once
        - Getting a quick overall health check of the codebase
        
        This composite tool runs ESLint, TypeScript checking, and optionally
        tests in sequence, providing a unified quality report. Perfect for
        pre-commit hooks or build pipelines.

        Args:
            project_root: Directory to check (defaults to MCP_FILE_ROOT)
            include_typescript: Whether to check TypeScript errors
            include_tests: Whether to run tests as part of quality check
            
        Example:
            quality_check(include_tests=True)
            → {"data": {
                "summary": {
                  "total_issues": 8,
                  "total_errors": 3,
                  "total_warnings": 5,
                  "overall_status": "fail"
                },
                "results": {
                  "lint": {"errors": 1, "warnings": 5},
                  "typescript": {"errors": 2, "warnings": 0},
                  "tests": {"passed": 45, "failed": 0}
                }
              }}
              
        Note: Runs multiple tools in sequence. If you need just one check,
        use lint_project, check_typescript, or run_tests individually.
        """
        project_root = get_project_root(project_root)
        
        results = {
            "lint": None,
            "typescript": None,
            "tests": None
        }
        
        # Run linting
        results["lint"] = parse_lint_results_impl(
            linter="eslint",
            project_root=project_root,
            target_files=None,
            config_file=None,
            include_warnings=True,
            use_standards_eslint=False,
            timeout=120,
            page=1,
            max_tokens=20000
        )
        
        # Run TypeScript checking if requested
        if include_typescript:
            results["typescript"] = parse_typescript_errors_impl(
                project_root=project_root,
                tsconfig_path="tsconfig.json",
                files=None,
                include_warnings=True,
                timeout=120,
                page=1,
                max_tokens=20000,
                use_build_command=False
            )
        
        # Run tests if requested
        if include_tests:
            results["tests"] = run_test_suite_impl(
                project_root=project_root,
                test_command=None,
                test_framework="auto",
                pattern=None,
                coverage=False,
                timeout=300
            )
        
        # Create summary
        total_issues = 0
        total_errors = 0
        total_warnings = 0
        
        if results["lint"] and "data" in results["lint"]:
            lint_summary = results["lint"]["data"].get("summary", {})
            total_issues += lint_summary.get("total_issues", 0)
            total_errors += lint_summary.get("errors", 0)
            total_warnings += lint_summary.get("warnings", 0)
        
        if results["typescript"] and "data" in results["typescript"]:
            ts_summary = results["typescript"]["data"].get("summary", {})
            total_issues += ts_summary.get("total_errors", 0)
            total_errors += ts_summary.get("error_count", 0)
            total_warnings += ts_summary.get("warning_count", 0)
        
        return {
            "data": {
                "summary": {
                    "total_issues": total_issues,
                    "total_errors": total_errors,
                    "total_warnings": total_warnings,
                    "checks_run": [k for k, v in results.items() if v is not None],
                    "overall_status": "fail" if total_errors > 0 else "warning" if total_warnings > 0 else "pass"
                },
                "results": results
            }
        }


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
