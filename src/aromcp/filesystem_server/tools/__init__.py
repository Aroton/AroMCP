"""FileSystem server tools implementations."""

from typing import Any

from ...utils.json_parameter_middleware import json_convert
from .._security import get_project_root
from .apply_file_diffs import apply_file_diffs_impl
from .extract_method_signatures import extract_method_signatures_impl
from .find_imports_for_files import find_imports_for_files_impl
from .get_target_files import get_target_files_impl
from .load_documents_by_pattern import load_documents_by_pattern_impl
from .preview_file_changes import preview_file_changes_impl
from .read_files_batch import read_files_batch_impl
from .validate_diffs import validate_diffs_impl
from .write_files_batch import write_files_batch_impl


def register_filesystem_tools(mcp):
    """Register filesystem tools with the MCP server."""

    @mcp.tool
    @json_convert
    def get_target_files(
        patterns: str | list[str],
        project_root: str | None = None,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """List files based on path patterns.

        Args:
            patterns: Glob patterns to match files (e.g., "**/*.py", "src/**/*.js")
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
        """
        project_root = get_project_root(project_root)
        return get_target_files_impl(patterns, project_root, page, max_tokens)

    @mcp.tool
    @json_convert
    def read_files_batch(
        file_paths: str | list[str],
        project_root: str | None = None,
        encoding: str = "auto",
        expand_patterns: bool = True,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Read multiple files in one operation.

        Args:
            file_paths: List of file paths or glob patterns to read
                       (relative to project_root)
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            encoding: File encoding ("auto", "utf-8", "ascii", etc.)
            expand_patterns: Whether to expand glob patterns in file_paths
                            (default: True)
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
        """
        project_root = get_project_root(project_root)
        return read_files_batch_impl(
            file_paths, project_root, encoding, expand_patterns, page, max_tokens
        )

    @mcp.tool
    @json_convert
    def write_files_batch(
        files: dict[str, str] | str,
        project_root: str | None = None,
        encoding: str = "utf-8",
        create_backup: bool = True
    ) -> dict[str, Any]:
        """Write multiple files atomically with automatic directory creation.

        Args:
            files: Dictionary mapping static file paths to content (no pattern support)
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            encoding: File encoding to use
            create_backup: Whether to create backups of existing files
        """
        project_root = get_project_root(project_root)
        return write_files_batch_impl(files, project_root, encoding, create_backup)

    @mcp.tool
    def extract_method_signatures(
        file_paths: str | list[str],
        project_root: str | None = None,
        include_docstrings: bool = True,
        include_decorators: bool = True,
        expand_patterns: bool = True,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Parse code files to extract function/method signatures programmatically.

        Args:
            file_paths: Path to code file(s) or glob pattern(s) - can be string or list
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            include_docstrings: Whether to include function docstrings
            include_decorators: Whether to include function decorators
            expand_patterns: Whether to expand glob patterns in file_paths
                            (default: True)
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
        """
        project_root = get_project_root(project_root)
        return extract_method_signatures_impl(
            file_paths, project_root, include_docstrings, include_decorators,
            expand_patterns, page, max_tokens
        )

    @mcp.tool
    @json_convert
    def find_imports_for_files(
        file_paths: str | list[str],
        project_root: str | None = None,
        search_patterns: str | list[str] | None = None,
        expand_patterns: bool = True,
        page: int = 1,
        max_tokens: int = 20000
    ) -> dict[str, Any]:
        """Identify which files import the given files (dependency analysis).

        Args:
            file_paths: List of files or glob patterns to find importers for
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            search_patterns: File patterns to search in (defaults to common code files)
            expand_patterns: Whether to expand glob patterns in file_paths
                            (default: True)
            page: Page number for pagination (1-based, default: 1)
            max_tokens: Maximum tokens per page (default: 20000)
        """
        project_root = get_project_root(project_root)
        return find_imports_for_files_impl(
            file_paths, project_root, search_patterns, expand_patterns, page, max_tokens
        )

    @mcp.tool
    @json_convert
    def load_documents_by_pattern(
        patterns: str | list[str],
        project_root: str | None = None,
        max_file_size: int = 1024 * 1024,
        encoding: str = "auto"
    ) -> dict[str, Any]:
        """Load multiple documents matching glob patterns (for standards, configs).

        Args:
            patterns: List of glob patterns to match files (e.g., "**/*.md", "*.json")
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            max_file_size: Maximum file size to load (bytes)
            encoding: File encoding ("auto", "utf-8", etc.)
        """
        project_root = get_project_root(project_root)
        return load_documents_by_pattern_impl(
            patterns, project_root, max_file_size, encoding
        )

    @mcp.tool
    @json_convert
    def apply_file_diffs(
        diffs: list[dict[str, Any]] | str,
        project_root: str | None = None,
        create_backup: bool = True,
        validate_before_apply: bool = True
    ) -> dict[str, Any]:
        """Apply multiple diffs to files with validation and rollback support.

        Args:
            diffs: List of diff objects with 'file_path' and 'diff_content' keys
                  (file_path must be static path, no pattern support)
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            create_backup: Whether to create backups before applying diffs
            validate_before_apply: Whether to validate all diffs before applying any
        """
        project_root = get_project_root(project_root)
        return apply_file_diffs_impl(
            diffs, project_root, create_backup, validate_before_apply
        )

    @mcp.tool
    @json_convert
    def preview_file_changes(
        diffs: list[dict[str, Any]] | str,
        project_root: str | None = None,
        include_full_preview: bool = True,
        max_preview_lines: int = 50
    ) -> dict[str, Any]:
        """Show consolidated preview of all pending changes.

        Args:
            diffs: List of diff objects with 'file_path' and 'diff_content' keys
                  (file_path must be static path, no pattern support)
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            include_full_preview: Whether to include full diff preview for each file
            max_preview_lines: Maximum lines to show in preview
        """
        project_root = get_project_root(project_root)
        return preview_file_changes_impl(
            diffs, project_root, include_full_preview, max_preview_lines
        )

    @mcp.tool
    @json_convert
    def validate_diffs(
        diffs: list[dict[str, Any]] | str,
        project_root: str | None = None,
        check_conflicts: bool = True,
        check_syntax: bool = True
    ) -> dict[str, Any]:
        """Pre-validate diffs for conflicts and applicability.

        Args:
            diffs: List of diff objects with 'file_path' and 'diff_content' keys
                  (file_path must be static path, no pattern support)
            project_root: Root directory of the project (defaults to MCP_FILE_ROOT)
            check_conflicts: Whether to check for conflicts between diffs
            check_syntax: Whether to validate diff syntax
        """
        project_root = get_project_root(project_root)
        return validate_diffs_impl(diffs, project_root, check_conflicts, check_syntax)


__all__ = [
    "get_target_files_impl",
    "read_files_batch_impl",
    "write_files_batch_impl",
    "extract_method_signatures_impl",
    "find_imports_for_files_impl",
    "load_documents_by_pattern_impl",
    "apply_file_diffs_impl",
    "preview_file_changes_impl",
    "validate_diffs_impl",
    "register_filesystem_tools"
]
