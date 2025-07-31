"""FileSystem server tools implementations."""

from typing import Any

from ...utils.json_parameter_middleware import json_convert
from ..models.filesystem_models import (
    ListFilesResponse,
    ReadFilesResponse,
    WriteFilesResponse,
)

# from .._security import get_project_root  # Not used in registration
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


__all__ = [
    "list_files_impl",
    "read_files_impl",
    "write_files_impl",
    "register_filesystem_tools",
]
