"""FileSystem server tools implementations."""

from typing import Any

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
    def list_files(patterns: str | list[str], cursor: str | None = None, max_tokens: int = 20000) -> ListFilesResponse:
        """List files matching advanced glob patterns with full wildcard support.

        This tool uses server-side cursor pagination. The server handles all pagination automatically.
        To retrieve all files:
        1. First call: Always use cursor=None
        2. If response has_more=true, make another call with cursor=next_cursor from response
        3. Repeat until has_more=false

        Use this tool when:
        - Finding files by pattern instead of using find, ls, or grep commands
        - Getting a clean list of file paths for processing
        - Filtering files by extension or directory structure
        - Building file lists for batch operations

        Replaces bash commands: find, ls, locate, fd

        Args:
            patterns: Advanced glob patterns supporting brace expansion, character classes, and wildcards
            cursor: Pagination cursor from previous response. MUST be None for first request, then use exact next_cursor value from previous response. Never generate your own cursor values.
            max_tokens: Maximum tokens per response

        Supported Pattern Types:
            • Basic globs: "**/*.py", "src/**/*.js"
            • Brace expansion: "src/**/*.{js,jsx,ts,tsx}" (matches all 4 extensions)
            • Directory braces: "src/{components,utils}/**/*.ts" (matches files in both dirs)
            • Character classes: "src/**/*.[jt]s" (matches .js and .ts files)
            • Character ranges: "[a-z].py" (matches single lowercase letter filenames)
            • Single wildcards: "?.js" (matches single-character filenames)
            • Multiple wildcards: "??.tsx" (matches two-character filenames)
            • Complex combinations: "src/{pages,components}/**/*.[jt]s?" (all patterns together)

        Examples:
            list_files("src/components/**/*.{js,jsx,ts,tsx}")
            → {"files": ["src/components/Button.js", "src/components/Header.jsx", "src/components/Modal.tsx"], "total_files": 3}

            list_files("src/{components,utils}/**/*.[jt]s")
            → {"files": ["src/components/Button.js", "src/utils/helper.ts"], "total_files": 2}

        Cursor Pagination Examples:
            # First request - ALWAYS start with cursor=None
            list_files(["**/*.py"], cursor=None, max_tokens=5000)
            → {"files": [...25 files...], "total": 150, "next_cursor": "src/utils.py", "has_more": true}
            
            # Second request - use EXACT next_cursor from previous response
            list_files(["**/*.py"], cursor="src/utils.py", max_tokens=5000)  
            → {"files": [...25 more files...], "total": 150, "next_cursor": "tests/test_views.py", "has_more": true}
            
            # Continue until has_more is false
            list_files(["**/*.py"], cursor="tests/test_views.py", max_tokens=5000)
            → {"files": [...final files...], "total": 150, "next_cursor": null, "has_more": false}

        Response always includes:
        - files: Array of file paths for this page
        - total: Total number of matching files across all pages
        - next_cursor: Cursor for next page (null if no more pages)
        - has_more: Boolean indicating if more pages exist

        IMPORTANT: Do NOT attempt to implement your own pagination logic. The server handles all pagination. 
        Simply use the cursor values provided in responses.

        Note: Returns relative paths from project root. For reading file contents, use read_files.
        Supports pagination for large result sets. Malformed patterns treated as literals.
        Automatically excludes common build/dependency folders (node_modules, .git, dist, etc).
        """
        return list_files_impl(patterns, cursor, max_tokens)

    @mcp.tool
    @json_convert
    def read_files(files: str | list[str], cursor: str | None = None, max_tokens: int = 20000) -> ReadFilesResponse:
        """Read multiple files and return their contents.

        This tool uses server-side cursor pagination. The server handles all pagination automatically.
        To retrieve all files:
        1. First call: Always use cursor=None
        2. If response has_more=true, make another call with cursor=next_cursor from response
        3. Repeat until has_more=false

        Use this tool when:
        - Reading file contents for analysis or processing
        - Getting source code for multiple files at once
        - Loading configuration or data files
        - Examining file contents before making changes

        Replaces bash commands: cat, head, tail, less

        Args:
            files: File paths to read
            cursor: Pagination cursor from previous response. MUST be None for first request, then use exact next_cursor value from previous response. Never generate your own cursor values.
            max_tokens: Maximum tokens per response

        Cursor Pagination Examples:
            # First request - ALWAYS start with cursor=None
            read_files(["**/*.py"], cursor=None, max_tokens=5000)
            → {"items": [...15 file contents...], "total": 100, "next_cursor": "src/utils.py", "has_more": true}
            
            # Second request - use EXACT next_cursor from previous response
            read_files(["**/*.py"], cursor="src/utils.py", max_tokens=5000)
            → {"items": [...15 more file contents...], "total": 100, "next_cursor": "tests/test_app.py", "has_more": true}
            
            # Continue until has_more is false
            read_files(["**/*.py"], cursor="tests/test_app.py", max_tokens=5000)
            → {"items": [...final file contents...], "total": 100, "next_cursor": null, "has_more": false}

        Response always includes:
        - items: Array of file content objects for this page
        - total: Total number of files across all pages
        - next_cursor: Cursor for next page (null if no more pages)
        - has_more: Boolean indicating if more pages exist

        IMPORTANT: Do NOT attempt to implement your own pagination logic. The server handles all pagination. 
        Simply use the cursor values provided in responses.

        Note: For listing files by pattern, use list_files. Supports pagination for large file contents.
        """
        from ..models.filesystem_models import ReadFileItem

        result = read_files_impl(files, cursor, max_tokens)

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
            total=result.get("total", len(items)),
            page_size=result.get("page_size"),
            next_cursor=result.get("next_cursor"),
            has_more=result.get("has_more"),
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
        cursor: str | None = None,
        max_tokens: int = 20000,
    ) -> dict[str, Any]:
        """Parse code files to extract function/method signatures programmatically.

        This tool uses server-side cursor pagination. The server handles all pagination automatically.
        To retrieve all signatures:
        1. First call: Always use cursor=None
        2. If response has_more=true, make another call with cursor=next_cursor from response
        3. Repeat until has_more=false

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
            cursor: Pagination cursor from previous response. MUST be None for first request, then use exact next_cursor value from previous response. Never generate your own cursor values.
            max_tokens: Maximum tokens per response

        Example:
            extract_method_signatures(\"**/*.py\")
            → [{\"name\": \"calculate_total\", \"params\": [\"items\", \"tax_rate\"],
                \"file_path\": \"src/utils.py\", \"line\": 42,
                \"decorators\": [\"@lru_cache\"], \"returns\": \"float\",
                \"docstring\": \"Calculate total with tax\"}]

        Cursor Pagination Examples:
            # First request - ALWAYS start with cursor=None
            extract_method_signatures([\"**/*.py\"], cursor=None, max_tokens=5000)
            → {\"signatures\": [...30 signatures...], \"total\": 250, \"next_cursor\": \"src/utils.py\", \"has_more\": true}
            
            # Second request - use EXACT next_cursor from previous response
            extract_method_signatures([\"**/*.py\"], cursor=\"src/utils.py\", max_tokens=5000)
            → {\"signatures\": [...30 more signatures...], \"total\": 250, \"next_cursor\": \"tests/test_app.py\", \"has_more\": true}
            
            # Continue until has_more is false
            extract_method_signatures([\"**/*.py\"], cursor=\"tests/test_app.py\", max_tokens=5000)
            → {\"signatures\": [...final signatures...], \"total\": 250, \"next_cursor\": null, \"has_more\": false}

        Response always includes:
        - signatures: Array of method signature objects for this page
        - total: Total number of signatures across all pages
        - next_cursor: Cursor for next page (null if no more pages)
        - has_more: Boolean indicating if more pages exist

        IMPORTANT: Do NOT attempt to implement your own pagination logic. The server handles all pagination. 
        Simply use the cursor values provided in responses.

        Note: For import analysis use find_who_imports. For API endpoints use extract_api_endpoints.
        Supports Python (.py) files with full AST parsing.
        """
        from ..models.filesystem_models import MethodSignature

        result = extract_method_signatures_impl(file_paths, include_docstrings, include_decorators, expand_patterns, cursor, max_tokens)

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
    def find_who_imports(file_path: str, cursor: str | None = None, max_tokens: int = 20000) -> FindWhoImportsResponse:
        """Find all files that import/depend on the specified file.

        This tool uses server-side cursor pagination. The server handles all pagination automatically.
        To retrieve all dependents:
        1. First call: Always use cursor=None
        2. If response has_more=true, make another call with cursor=next_cursor from response
        3. Repeat until has_more=false

        Use this tool when:
        - Planning to move or rename files (see impact)
        - Refactoring exports (find all consumers)
        - Deleting code (ensure it's safe)
        - Understanding dependency chains

        Replaces bash commands: grep, rg, ag

        Args:
            file_path: File to find importers for
            cursor: Pagination cursor from previous response. MUST be None for first request, then use exact next_cursor value from previous response. Never generate your own cursor values.
            max_tokens: Maximum tokens per response

        Example:
            find_who_imports("src/utils/helper.py")
            → {"dependents": [{"file": "src/main.py", "imports": ["helper_func"]}], "safe_to_delete": false}

        Cursor Pagination Examples:
            # First request - ALWAYS start with cursor=None
            find_who_imports("src/common/utils.py", cursor=None, max_tokens=5000)
            → {"dependents": [...20 dependencies...], "total": 85, "next_cursor": "src/components/Button.js", "has_more": true}
            
            # Second request - use EXACT next_cursor from previous response
            find_who_imports("src/common/utils.py", cursor="src/components/Button.js", max_tokens=5000)
            → {"dependents": [...20 more dependencies...], "total": 85, "next_cursor": "tests/test_utils.py", "has_more": true}
            
            # Continue until has_more is false
            find_who_imports("src/common/utils.py", cursor="tests/test_utils.py", max_tokens=5000)
            → {"dependents": [...final dependencies...], "total": 85, "next_cursor": null, "has_more": false}

        Response always includes:
        - dependents: Array of import dependency objects for this page
        - total: Total number of dependent files across all pages
        - next_cursor: Cursor for next page (null if no more pages)
        - has_more: Boolean indicating if more pages exist

        IMPORTANT: Do NOT attempt to implement your own pagination logic. The server handles all pagination. 
        Simply use the cursor values provided in responses.

        Note: This is reverse dependency analysis - finds who imports FROM this file.
        """
        # The implementation now returns FindWhoImportsResponse directly
        return find_who_imports_impl(file_path, cursor, max_tokens)


__all__ = [
    "list_files_impl",
    "read_files_impl",
    "write_files_impl",
    "extract_method_signatures_impl",
    "find_who_imports_impl",
    "register_filesystem_tools",
]
