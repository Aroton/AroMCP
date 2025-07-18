"""FileSystem server tools implementations."""

from ...utils.json_parameter_middleware import json_convert
from ..models.filesystem_models import (
    ExtractMethodSignaturesResponse,
    FindWhoImportsResponse,
    ListFilesResponse,
    ReadFilesResponse,
    WriteFilesResponse,
)

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
    def list_files(patterns: str | list[str]) -> ListFilesResponse:
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
            → {"files": ["src/main.py", "tests/test_utils.py", "setup.py"], "total_files": 3}

        Note: Returns relative paths from project root. For reading file contents, use read_files.
        """
        files = list_files_impl(patterns)
        return ListFilesResponse(files=files, pattern_used=patterns, total_files=len(files))

    @mcp.tool
    @json_convert
    def read_files(files: str | list[str], page: int = 1, max_tokens: int = 20000) -> ReadFilesResponse:
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

        Note: For listing files by pattern, use read_files. Supports pagination for large file contents.
        """
        from ..models.filesystem_models import ReadFileItem

        result = read_files_impl(files, page, max_tokens)

        # Convert dict items to ReadFileItem dataclasses
        items = []
        for item in result["items"]:
            items.append(
                ReadFileItem(
                    file=item["file"],
                    content=item["content"],
                    encoding=item["encoding"],
                    size=item["size"],
                    exists=True,
                    error=None,
                )
            )

        return ReadFilesResponse(
            items=items,
            page=result["page"],
            total_pages=result.get("total_pages", 1),
            total_files=result.get("total_files", len(items)),
            has_more=result.get("has_more", False),
        )

    @mcp.tool
    @json_convert
    def write_files(files: dict[str, str] | str) -> WriteFilesResponse:
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
        result = write_files_impl(files)
        return WriteFilesResponse(
            files_written=result["files_written"],
            total_files=result["total_files"],
            directories_created=result["directories_created"],
            success=result["success"],
        )

    @mcp.tool
    @json_convert
    def extract_method_signatures(
        file_paths: str | list[str],
        include_docstrings: bool = True,
        include_decorators: bool = True,
        expand_patterns: bool = True,
    ) -> ExtractMethodSignaturesResponse:
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
        from ..models.filesystem_models import MethodSignature

        result = extract_method_signatures_impl(file_paths, include_docstrings, include_decorators, expand_patterns)

        # Convert dict signatures to MethodSignature dataclasses
        signatures = []
        for sig in result["signatures"]:
            signatures.append(
                MethodSignature(
                    name=sig["name"],
                    file_path=sig["file_path"],
                    line=sig["line"],
                    signature=sig["signature"],
                    params=sig.get("params", []),
                    returns=sig.get("returns"),
                    decorators=sig.get("decorators", []),
                    docstring=sig.get("docstring"),
                    class_name=sig.get("class_name"),
                    is_method=sig.get("is_method", False),
                    is_async=sig.get("is_async", False),
                )
            )

        return ExtractMethodSignaturesResponse(
            signatures=signatures,
            total_signatures=result["total_signatures"],
            files_processed=result["files_processed"],
            patterns_used=result["patterns_used"],
        )

    @mcp.tool
    @json_convert
    def find_who_imports(file_path: str) -> FindWhoImportsResponse:
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
        from ..models.filesystem_models import ImportDependency

        result = find_who_imports_impl(file_path)

        # Convert dict dependents to ImportDependency dataclasses
        dependents = []
        for dep in result["dependents"]:
            dependents.append(
                ImportDependency(
                    file=dep["file"],
                    imports=dep["imports"],
                    line_numbers=dep["line_numbers"],
                    import_type=dep["import_type"],
                )
            )

        return FindWhoImportsResponse(
            target_file=result["target_file"],
            dependents=dependents,
            total_dependents=result["total_dependents"],
            safe_to_delete=result["safe_to_delete"],
            impact_analysis=result["impact_analysis"],
        )


__all__ = [
    "list_files_impl",
    "read_files_impl",
    "write_files_impl",
    "extract_method_signatures_impl",
    "find_who_imports_impl",
    "register_filesystem_tools",
]
