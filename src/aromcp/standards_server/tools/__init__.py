"""Standards server tools registration with v2 enhancements."""

import asyncio

from fastmcp import FastMCP

from ...utils.json_parameter_middleware import json_convert
from ..services.context_detector import ContextDetector
from ..services.rule_compressor import RuleCompressor
from ..services.rule_grouper import RuleGrouper
from ..services.session_manager import SessionManager, session_cleanup_loop
from .add_hint import add_hint_impl
from .add_rule import add_rule_impl, list_rules_impl
from .check_updates import check_updates_impl
from .delete import delete_impl
from .hints_for_file import hints_for_file_impl
from .register import register_impl

# Global service instances
_session_manager = None
_context_detector = None
_rule_compressor = None
_rule_grouper = None


def _get_or_create_services():
    """Get or create service instances."""
    global _session_manager, _context_detector, _rule_compressor, _rule_grouper

    if _session_manager is None:
        _session_manager = SessionManager()
    if _context_detector is None:
        _context_detector = ContextDetector()
    if _rule_compressor is None:
        _rule_compressor = RuleCompressor()
    if _rule_grouper is None:
        _rule_grouper = RuleGrouper()

    return _session_manager, _context_detector, _rule_compressor, _rule_grouper


def register_standards_tools(mcp: FastMCP) -> None:
    """Register all standards management tools with v2 enhancements."""

    # Initialize services
    session_manager, context_detector, rule_compressor, rule_grouper = _get_or_create_services()

    # Start session cleanup task (only if event loop is running)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(session_cleanup_loop(session_manager))
    except RuntimeError:
        # No event loop running, will be started later
        pass

    # Enhanced hints_for_file with session support
    @mcp.tool(
        name="hints_for_file",
        description="Gets relevant hints with smart compression and session deduplication"
    )
    @json_convert
    def hints_for_file(
        file_path: str,
        max_tokens: int = 10000,
        project_root: str | None = None,
        session_id: str | None = None,
        compression_enabled: bool = True,
        grouping_enabled: bool = True
    ) -> dict:
        """Get relevant coding hints for a specific file with v2 enhancements."""
        return hints_for_file_impl(
            file_path=file_path,
            max_tokens=max_tokens,
            project_root=project_root,
            session_id=session_id,
            compression_enabled=compression_enabled,
            grouping_enabled=grouping_enabled
        )

    # Enhanced register with enhanced metadata support
    @mcp.tool(
        name="register",
        description="Registers a standard with enhanced metadata and rule processing"
    )
    @json_convert
    def register(
        source_path: str,
        metadata: dict | str,
        project_root: str | None = None,
        enhanced_format: bool = True
    ) -> dict:
        """Register a standard with enhanced metadata support."""
        return register_impl(
            source_path=source_path,
            metadata=metadata,
            project_root=project_root,
            enhanced_format=enhanced_format
        )

    # Session management tools
    @mcp.tool(
        name="get_session_stats",
        description="Get statistics for AI coding sessions"
    )
    @json_convert
    def get_session_stats(session_id: str | None = None) -> dict:
        """Get session statistics."""
        try:
            if session_id:
                session = session_manager.get_session(session_id)
                if session:
                    return {"data": session.get_stats()}
                else:
                    return {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": f"Session {session_id} not found"
                        }
                    }
            else:
                return {"data": session_manager.get_all_stats()}

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to get session stats: {str(e)}"
                }
            }

    @mcp.tool(
        name="clear_session",
        description="Clear a specific session or all sessions"
    )
    @json_convert
    def clear_session(session_id: str | None = None) -> dict:
        """Clear session data."""
        try:
            if session_id:
                success = session_manager.delete_session(session_id)
                return {
                    "data": {
                        "cleared": success,
                        "session_id": session_id
                    }
                }
            else:
                # Clear all sessions
                active_sessions = session_manager.get_active_sessions()
                for sid in active_sessions:
                    session_manager.delete_session(sid)

                return {
                    "data": {
                        "cleared": True,
                        "sessions_cleared": len(active_sessions)
                    }
                }

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to clear session: {str(e)}"
                }
            }

    @mcp.tool(
        name="analyze_context",
        description="Analyze context for a specific file and session"
    )
    @json_convert
    def analyze_context(
        file_path: str,
        session_id: str | None = None,
        project_root: str | None = None
    ) -> dict:
        """Analyze context for a file."""
        try:
            session = session_manager.get_or_create_session(session_id or "default")
            context = context_detector.analyze_session_context(session, file_path)

            return {
                "data": {
                    "context": context,
                    "session_stats": session.get_stats()
                }
            }

        except Exception as e:
            return {
                "error": {
                    "code": "OPERATION_FAILED",
                    "message": f"Failed to analyze context: {str(e)}"
                }
            }

    # Legacy tools (unchanged but use new implementations)
    @mcp.tool(
        name="check_updates",
        description="Scans for new or modified standard files and checks what needs updating"
    )
    @json_convert
    def check_updates(standards_path: str, project_root: str | None = None) -> dict:
        """Check for standards that need updating."""
        return check_updates_impl(standards_path, project_root)

    @mcp.tool(
        name="delete",
        description="Removes all rules and hints for a standard"
    )
    @json_convert
    def delete(standard_id: str, project_root: str | None = None) -> dict:
        """Delete a standard and all its associated data."""
        return delete_impl(standard_id, project_root)

    # New tools for iterative hint and rule management
    @mcp.tool(
        name="add_hint",
        description="Add a single hint to a standard"
    )
    @json_convert
    def add_hint(
        standard_id: str,
        hint_data: dict | str,
        project_root: str | None = None
    ) -> dict:
        """Add a single hint to a standard."""
        return add_hint_impl(standard_id, hint_data, project_root)

    @mcp.tool(
        name="add_rule",
        description="Add a single ESLint rule to a standard"
    )
    @json_convert
    def add_rule(
        standard_id: str,
        rule_name: str,
        rule_content: str,
        project_root: str | None = None
    ) -> dict:
        """Add a single ESLint rule to a standard."""
        return add_rule_impl(standard_id, rule_name, rule_content, project_root)

    @mcp.tool(
        name="list_rules",
        description="List ESLint rules for a standard"
    )
    @json_convert
    def list_rules(
        standard_id: str,
        project_root: str | None = None
    ) -> dict:
        """List ESLint rules for a standard."""
        return list_rules_impl(standard_id, project_root)

