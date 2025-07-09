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
        """Get intelligent coding hints based on file context and standards.
        
        Use this tool when:
        - Starting work on a new file to understand conventions
        - Looking for best practices specific to file type or framework
        - Needing reminders about project-specific patterns
        - Wanting context-aware suggestions while coding
        
        This tool analyzes the file path, type, and content to provide
        relevant hints from registered standards, with intelligent
        deduplication and compression to save tokens across your session.
        
        Args:
            file_path: Path to the file to get hints for
            max_tokens: Maximum tokens to return (default: 10000)
            project_root: Root directory of project (defaults to MCP_FILE_ROOT)
            session_id: Session ID for deduplication across requests
            compression_enabled: Enable smart hint compression
            grouping_enabled: Group related hints together
            
        Example:
            hints_for_file("src/components/Button.tsx")
            → {"data": {
                "hints": [
                  {"category": "react", 
                   "hint": "Use functional components with TypeScript interfaces",
                   "example": "interface ButtonProps { ... }",
                   "relevance": 0.95}
                ],
                "session_token_savings": 2500,
                "compression_applied": true
              }}
              
        Note: Hints improve over time as you work. Use analyze_context
        for deeper pattern analysis. Session support prevents duplicate hints.
        """
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
        """Register a coding standard document for hint generation.
        
        Use this tool when:
        - Adding new coding standards or best practices documents
        - Registering team-specific guidelines or conventions
        - Setting up project-specific patterns to follow
        - Updating existing standards with new versions
        
        This tool processes markdown documents containing coding standards
        and makes them available for context-aware hint generation.
        
        Args:
            source_path: Path to the standards document (usually .md file)
            metadata: Metadata about the standard (tags, categories, scope)
            project_root: Root directory of project (defaults to MCP_FILE_ROOT)
            enhanced_format: Use enhanced processing with better categorization
            
        Example:
            register("docs/react-best-practices.md", 
                    {"tags": ["react", "typescript"], "scope": "components"})
            → {"data": {
                "standard_id": "react-best-practices",
                "hints_extracted": 15,
                "rules_extracted": 8,
                "categories": ["components", "hooks", "testing"]
              }}
              
        Note: Standards are automatically parsed for hints and ESLint rules.
        Use check_updates to update existing standards.
        """
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
        """Get statistics about AI coding sessions and hint usage.
        
        Use this tool when:
        - Monitoring hint effectiveness and token savings
        - Understanding which standards are most used
        - Analyzing coding patterns across sessions
        - Debugging session-related issues
        
        This tool provides insights into how hints are being used,
        token savings from deduplication, and session activity.
        
        Args:
            session_id: Specific session ID or None for all sessions
            
        Example:
            get_session_stats()
            → {"data": {
                "active_sessions": 3,
                "total_hints_served": 145,
                "tokens_saved": 15420,
                "most_used_categories": ["react", "typescript"],
                "compression_rate": 0.65
              }}
              
        Note: Sessions auto-expire after inactivity. Use clear_session
        to manually clear old sessions.
        """
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
        """Clear session data to reset hint deduplication.
        
        Use this tool when:
        - Starting fresh work on a different part of the codebase
        - Resetting hint context after major changes
        - Cleaning up expired or unused sessions
        - Forcing hints to re-appear after clearing
        
        This tool clears session tracking data, allowing previously
        shown hints to appear again if relevant.
        
        Args:
            session_id: Specific session to clear or None for all
            
        Example:
            clear_session("session-123")
            → {"data": {
                "cleared": true,
                "session_id": "session-123"
              }}
              
        Note: Clearing sessions doesn't delete standards, only
        the tracking of which hints have been shown.
        """
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
        """Analyze coding patterns and context for intelligent suggestions.
        
        Use this tool when:
        - Starting work on a complex file needing deep context
        - Understanding project-specific patterns to follow
        - Getting advanced insights beyond basic hints
        - Analyzing team coding conventions in use
        
        This tool performs deep analysis of file context, including
        imports, surrounding code patterns, and project conventions
        to provide targeted insights.
        
        Args:
            file_path: File to analyze for context
            session_id: Session ID for tracking
            project_root: Root directory of project
            
        Example:
            analyze_context("src/components/UserProfile.tsx")
            → {"data": {
                "context": {
                  "detected_patterns": ["React hooks", "TypeScript generics"],
                  "framework": "React",
                  "conventions": ["Functional components", "Props interfaces"],
                  "suggestions": ["Follow existing UserCard pattern"]
                },
                "session_stats": {"files_analyzed": 12}
              }}
              
        Note: More comprehensive than hints_for_file but uses more tokens.
        Best for complex files or when starting major features.
        """
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
        """Check for updates to registered coding standards.
        
        Use this tool when:
        - Starting a new coding session to get latest standards
        - After team updates to coding guidelines
        - Periodically to ensure following current best practices
        - Before code reviews to align with latest standards
        
        This tool compares registered standards with their source files
        to detect changes and provide update notifications.
        
        Args:
            standards_path: Path to directory containing standards
            project_root: Root directory of project
            
        Example:
            check_updates("docs/standards")
            → {"data": {
                "updates_available": 2,
                "standards": [
                  {"id": "react-best-practices",
                   "last_updated": "2024-01-15",
                   "changes_detected": true,
                   "summary": "Added hooks guidelines"}
                ]
              }}
              
        Note: Use register to update standards after checking.
        Updates don't apply automatically to allow review.
        """
        return check_updates_impl(standards_path, project_root)

    @mcp.tool(
        name="delete",
        description="Removes all rules and hints for a standard"
    )
    @json_convert
    def delete(standard_id: str, project_root: str | None = None) -> dict:
        """Remove a coding standard and all associated hints/rules.
        
        Use this tool when:
        - Removing outdated or deprecated standards
        - Cleaning up duplicate or conflicting guidelines
        - Replacing old standards with updated versions
        - Removing project-specific standards after migration
        
        This tool completely removes a standard and all its generated
        hints and ESLint rules from the system.
        
        Args:
            standard_id: ID of the standard to delete
            project_root: Root directory of project
            
        Example:
            delete("old-react-patterns")
            → {"data": {
                "deleted": true,
                "standard_id": "old-react-patterns",
                "hints_removed": 23,
                "rules_removed": 12
              }}
              
        Note: This is permanent. Consider using check_updates to
        update standards instead of deleting and re-registering.
        """
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
        """Add a single coding hint to an existing standard.
        
        Use this tool when:
        - Adding project-specific hints discovered during development
        - Incrementally building up coding guidelines
        - Adding context-specific hints for certain file types
        - Capturing lessons learned as reusable hints
        
        This tool adds individual hints to existing standards without
        needing to re-register the entire document.
        
        Args:
            standard_id: ID of the standard to add hint to
            hint_data: Hint content with category, text, and optional example
            project_root: Root directory of project
            
        Example:
            add_hint("react-best-practices", 
                    {"category": "hooks", 
                     "hint": "Extract complex logic into custom hooks",
                     "example": "useUserAuthentication()"})
            → {"data": {
                "added": true,
                "standard_id": "react-best-practices",
                "hint_id": "hint_42"
              }}
              
        Note: Hints are immediately available in hints_for_file.
        Use add_rule for ESLint-specific rules instead.
        """
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
        """Add a single ESLint rule to a standard.
        
        Use this tool when:
        - Enforcing specific coding patterns with linting
        - Adding project-specific ESLint rules
        - Creating custom rules based on team decisions
        - Incrementally building ESLint configuration
        
        This tool adds ESLint rules that can be exported to .eslintrc
        files for enforcement during development.
        
        Args:
            standard_id: ID of the standard to add rule to
            rule_name: ESLint rule name (e.g., "no-console")
            rule_content: Rule configuration ("error", "warn", or detailed config)
            project_root: Root directory of project
            
        Example:
            add_rule("react-best-practices", 
                    "react-hooks/exhaustive-deps", 
                    "error")
            → {"data": {
                "added": true,
                "standard_id": "react-best-practices",
                "rule_name": "react-hooks/exhaustive-deps",
                "total_rules": 15
              }}
              
        Note: Rules can be exported to .eslintrc format.
        Use list_rules to see all rules for a standard.
        """
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
        """List all ESLint rules associated with a standard.
        
        Use this tool when:
        - Reviewing which ESLint rules are enforced
        - Exporting rules to create .eslintrc configuration
        - Auditing linting rules before code review
        - Understanding what patterns are being enforced
        
        This tool shows all ESLint rules that have been added to
        a standard, ready for export or review.
        
        Args:
            standard_id: ID of the standard to list rules for
            project_root: Root directory of project
            
        Example:
            list_rules("react-best-practices")
            → {"data": {
                "standard_id": "react-best-practices",
                "rules": [
                  {"name": "react-hooks/rules-of-hooks", "config": "error"},
                  {"name": "react-hooks/exhaustive-deps", "config": "warn"},
                  {"name": "@typescript-eslint/no-explicit-any", "config": "error"}
                ],
                "total": 15,
                "exportable": true
              }}
              
        Note: Rules can be exported in .eslintrc format.
        Use add_rule to add new rules to the standard.
        """
        return list_rules_impl(standard_id, project_root)

