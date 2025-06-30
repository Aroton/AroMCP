"""FileSystem server tools implementations."""

from typing import Any

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
    def get_target_files(
        status: str = "working",
        patterns: list[str] | None = None,
        project_root: str = "."
    ) -> dict[str, Any]:
        """List files based on git status or path patterns.
        
        Args:
            status: Git status filter - "working", "staged", "branch", "commit", or "pattern"
            patterns: File patterns to match (used when status="pattern")
            project_root: Root directory of the project
        """
        return get_target_files_impl(status, patterns, project_root)

    @mcp.tool
    def read_files_batch(
        file_paths: list[str],
        project_root: str = ".",
        encoding: str = "auto"
    ) -> dict[str, Any]:
        """Read multiple files in one operation.
        
        Args:
            file_paths: List of file paths to read (relative to project_root)
            project_root: Root directory of the project
            encoding: File encoding ("auto", "utf-8", "ascii", etc.)
        """
        return read_files_batch_impl(file_paths, project_root, encoding)

    @mcp.tool
    def write_files_batch(
        files: dict[str, str],
        project_root: str = ".",
        encoding: str = "utf-8",
        create_backup: bool = True
    ) -> dict[str, Any]:
        """Write multiple files atomically with automatic directory creation.
        
        Args:
            files: Dictionary mapping file paths to content
            project_root: Root directory of the project
            encoding: File encoding to use
            create_backup: Whether to create backups of existing files
        """
        return write_files_batch_impl(files, project_root, encoding, create_backup)

    @mcp.tool
    def extract_method_signatures(
        file_path: str,
        project_root: str = ".",
        include_docstrings: bool = True,
        include_decorators: bool = True
    ) -> dict[str, Any]:
        """Parse code files to extract function/method signatures programmatically.
        
        Args:
            file_path: Path to the code file
            project_root: Root directory of the project
            include_docstrings: Whether to include function docstrings
            include_decorators: Whether to include function decorators
        """
        return extract_method_signatures_impl(file_path, project_root, include_docstrings, include_decorators)

    @mcp.tool
    def find_imports_for_files(
        file_paths: list[str],
        project_root: str = ".",
        search_patterns: list[str] | None = None
    ) -> dict[str, Any]:
        """Identify which files import the given files (dependency analysis).
        
        Args:
            file_paths: List of files to find importers for
            project_root: Root directory of the project
            search_patterns: File patterns to search in (defaults to common code files)
        """
        return find_imports_for_files_impl(file_paths, project_root, search_patterns)

    @mcp.tool
    def load_documents_by_pattern(
        patterns: list[str],
        project_root: str = ".",
        max_file_size: int = 1024 * 1024,
        encoding: str = "auto"
    ) -> dict[str, Any]:
        """Load multiple documents matching glob patterns (for standards, configs).
        
        Args:
            patterns: List of glob patterns to match files
            project_root: Root directory of the project
            max_file_size: Maximum file size to load (bytes)
            encoding: File encoding ("auto", "utf-8", etc.)
        """
        return load_documents_by_pattern_impl(patterns, project_root, max_file_size, encoding)

    @mcp.tool
    def apply_file_diffs(
        diffs: list[dict[str, Any]],
        project_root: str = ".",
        create_backup: bool = True,
        validate_before_apply: bool = True
    ) -> dict[str, Any]:
        """Apply multiple diffs to files with validation and rollback support.
        
        Args:
            diffs: List of diff objects with 'file_path' and 'diff_content' keys
            project_root: Root directory of the project
            create_backup: Whether to create backups before applying diffs
            validate_before_apply: Whether to validate all diffs before applying any
        """
        return apply_file_diffs_impl(diffs, project_root, create_backup, validate_before_apply)

    @mcp.tool
    def preview_file_changes(
        diffs: list[dict[str, Any]],
        project_root: str = ".",
        include_full_preview: bool = True,
        max_preview_lines: int = 50
    ) -> dict[str, Any]:
        """Show consolidated preview of all pending changes.
        
        Args:
            diffs: List of diff objects with 'file_path' and 'diff_content' keys
            project_root: Root directory of the project
            include_full_preview: Whether to include full diff preview for each file
            max_preview_lines: Maximum lines to show in preview
        """
        return preview_file_changes_impl(diffs, project_root, include_full_preview, max_preview_lines)

    @mcp.tool
    def validate_diffs(
        diffs: list[dict[str, Any]],
        project_root: str = ".",
        check_conflicts: bool = True,
        check_syntax: bool = True
    ) -> dict[str, Any]:
        """Pre-validate diffs for conflicts and applicability.
        
        Args:
            diffs: List of diff objects with 'file_path' and 'diff_content' keys
            project_root: Root directory of the project
            check_conflicts: Whether to check for conflicts between diffs
            check_syntax: Whether to validate diff syntax
        """
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
