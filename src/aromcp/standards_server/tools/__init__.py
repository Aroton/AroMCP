"""Standards server tools registration."""

from fastmcp import FastMCP

from ...utils.json_parameter_middleware import json_convert
from .check_updates import check_updates_impl
from .delete import delete_impl
from .hints_for_file import hints_for_file_impl
from .register import register_impl
from .update_rule import update_rule_impl


def register_standards_tools(mcp: FastMCP) -> None:
    """Register all standards management tools."""

    @mcp.tool(
        name="check_updates",
        description="Scans for new or modified standard files and checks what needs updating"
    )
    @json_convert
    def check_updates(standards_path: str, project_root: str | None = None) -> dict:
        """Check for standards that need updating."""
        return check_updates_impl(standards_path, project_root)

    @mcp.tool(
        name="register",
        description="Registers a standard with metadata after AI parsing"
    )
    @json_convert
    def register(
        source_path: str,
        metadata: dict | str,
        project_root: str | None = None
    ) -> dict:
        """Register a standard with its metadata."""
        return register_impl(source_path, metadata, project_root)

    @mcp.tool(
        name="delete",
        description="Removes all rules and hints for a standard"
    )
    @json_convert
    def delete(standard_id: str, project_root: str | None = None) -> dict:
        """Delete a standard and all its associated data."""
        return delete_impl(standard_id, project_root)

    @mcp.tool(
        name="update_rule",
        description="Stores AI hints and ESLint files for a standard"
    )
    @json_convert
    def update_rule(
        standard_id: str,
        clear_existing: bool = False,
        ai_hints: list[dict] | str | None = None,
        eslint_files: dict[str, str] | str | None = None,
        project_root: str | None = None
    ) -> dict:
        """Update AI hints and ESLint files for a standard."""
        return update_rule_impl(
            standard_id, clear_existing, ai_hints, eslint_files, project_root
        )

    @mcp.tool(
        name="hints_for_file",
        description="Gets relevant hints for a specific file with relevance scoring"
    )
    @json_convert
    def hints_for_file(
        file_path: str,
        max_tokens: int = 10000,
        project_root: str | None = None
    ) -> dict:
        """Get relevant coding hints for a specific file."""
        return hints_for_file_impl(file_path, max_tokens, project_root)
