"""FileSystem server tools implementations."""

from typing import Any

from ...utils.json_parameter_middleware import json_convert

# from .._security import get_project_root  # Not used in registration
from .extract_method_signatures import extract_method_signatures_impl
from .find_who_imports import find_who_imports_impl
from .list_files import list_files_impl
from .read_files import read_files_impl
from .write_files import write_files_impl


def register_filesystem_tools(mcp):
    """Register filesystem tools with the MCP server."""

    @mcp.tool
    @json_convert
    def list_files(patterns: str | list[str]) -> list[str]:
        """List files matching glob patterns.

        Use this tool when:
        - Finding files by pattern instead of using find, ls, or grep commands
        - Getting a clean list of file paths for processing
        - Filtering files by extension or directory structure
        - Building file lists for batch operations

        Replaces bash commands: find, ls, locate, fd

        Args:
            patterns: Glob patterns to match files (e.g., "**/*.py", "src/**/*.js")

        Example:
            list_files("**/*.py")
            → ["src/main.py", "tests/test_utils.py", "setup.py"]

        Note: Returns relative paths from project root. For reading file contents, use read_files.
        """
        return list_files_impl(patterns)

    @mcp.tool
    @json_convert
    def read_files(
        files: str | list[str],
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Read multiple files and return their contents.

        Use this tool when:
        - Reading file contents for analysis or processing
        - Getting source code for multiple files at once
        - Loading configuration or data files
        - Examining file contents before making changes

        Replaces bash commands: cat, head, tail, less

        Args:
            files: File paths to read
            page: Page number (1-based) for pagination
            max_tokens: Maximum tokens per page

        Example:
            read_files(["src/main.py", "config.json"])
            → {"items": [{"file": "src/main.py", "content": "import os...", "encoding": "utf-8"}], "page": 1}

        Note: For listing files by pattern, use list_files. Supports pagination for large file contents.
        """
        return read_files_impl(files, page, max_tokens)

    @mcp.tool
    @json_convert
    def write_files(files: dict[str, str] | str) -> None:
        """Write content to multiple NEW files with automatic directory creation.

        Use this tool when:
        - Creating new files with content (NOT modifying existing files)
        - Writing generated code or configuration files for new modules
        - Setting up new project structure

        IMPORTANT: Only use for NEW files. For modifying existing files, use Edit or MultiEdit.

        Replaces bash commands: echo >, tee, cp

        Args:
            files: Dictionary mapping file paths to content

        Example:
            write_files({"src/new_module.py": "print('hello')", "new_config.json": "{\\"debug\\": true}"})

        Note: Creates directories automatically. For editing existing files, use Edit or MultiEdit.
        """
        return write_files_impl(files)

    @mcp.tool
    @json_convert
    def extract_method_signatures(
        file_paths: str | list[str],
        include_docstrings: bool = True,
        include_decorators: bool = True,
        expand_patterns: bool = True
    ) -> list[dict[str, Any]]:
        """Parse code files to extract function/method signatures programmatically.

        Use this tool when:
        - Analyzing code structure and API surfaces
        - Documenting function signatures across multiple files
        - Understanding available methods and their parameters
        - Creating code documentation automatically
        - Auditing API consistency across a codebase

        Replaces bash commands: grep -E "def |class ", ctags, cscope

        Args:
            file_paths: Path to code file(s) or glob pattern(s) - can be string or list
            include_docstrings: Whether to include function docstrings (default: True)
            include_decorators: Whether to include function decorators (default: True)
            expand_patterns: Whether to expand glob patterns in file_paths (default: True)

        Example:
            extract_method_signatures(\"**/*.py\")
            → [{\"name\": \"calculate_total\", \"params\": [\"items\", \"tax_rate\"],
                \"file_path\": \"src/utils.py\", \"line\": 42,
                \"decorators\": [\"@lru_cache\"], \"returns\": \"float\",
                \"docstring\": \"Calculate total with tax\"}]

        Note: For import analysis use find_who_imports. For API endpoints use extract_api_endpoints.
        Supports Python (.py) files with full AST parsing.
        """
        return extract_method_signatures_impl(
            file_paths, include_docstrings, include_decorators, expand_patterns
        )

    @mcp.tool
    @json_convert
    def find_who_imports(file_path: str) -> dict[str, Any]:
        """Find all files that import/depend on the specified file.

        Use this tool when:
        - Planning to move or rename files (see impact)
        - Refactoring exports (find all consumers)
        - Deleting code (ensure it's safe)
        - Understanding dependency chains

        Replaces bash commands: grep, rg, ag

        Args:
            file_path: File to find importers for

        Example:
            find_who_imports("src/utils/helper.py")
            → {"dependents": [{"file": "src/main.py", "imports": ["helper_func"]}], "safe_to_delete": false}

        Note: This is reverse dependency analysis - finds who imports FROM this file.
        """
        return find_who_imports_impl(file_path)





__all__ = [
    "list_files_impl",
    "read_files_impl",
    "write_files_impl",
    "extract_method_signatures_impl",
    "find_who_imports_impl",
    "register_filesystem_tools"
]
