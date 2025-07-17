"""Session management for AI coding sessions."""

import asyncio
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class SessionState:
    """Track state for an AI session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.loaded_rule_ids: set[str] = set()
        self.loaded_patterns: set[str] = set()  # Track pattern types seen
        self.file_history: list[str] = []
        self.token_count: int = 0
        self.last_activity: datetime = datetime.now()
        self.context_cache: dict[str, Any] = {}
        self.pattern_frequency: dict[str, int] = {}  # Track how often patterns are used
        self.rule_visit_counts: dict[str, int] = {}  # Track how many times each rule has been seen

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now()

    def add_rule(self, rule_id: str, pattern_type: str, tokens: int) -> None:
        """Add a rule to the session."""
        self.loaded_rule_ids.add(rule_id)
        self.loaded_patterns.add(pattern_type)
        self.token_count += tokens
        self.pattern_frequency[pattern_type] = self.pattern_frequency.get(pattern_type, 0) + 1
        self.rule_visit_counts[rule_id] = self.rule_visit_counts.get(rule_id, 0) + 1

    def add_file(self, file_path: str) -> None:
        """Add a file to the session history."""
        self.file_history.append(file_path)
        # Keep only last 20 files to prevent memory bloat
        if len(self.file_history) > 20:
            self.file_history = self.file_history[-20:]

    def get_pattern_frequency(self, pattern_type: str) -> int:
        """Get frequency of a pattern type in this session."""
        return self.pattern_frequency.get(pattern_type, 0)

    def is_rule_loaded(self, rule_id: str) -> bool:
        """Check if a rule is already loaded."""
        return rule_id in self.loaded_rule_ids

    def is_pattern_seen(self, pattern_type: str) -> bool:
        """Check if a pattern type has been seen."""
        return pattern_type in self.loaded_patterns

    def get_rule_visit_count(self, rule_id: str) -> int:
        """Get how many times a rule has been visited."""
        return self.rule_visit_counts.get(rule_id, 0)

    def get_recent_files(self, count: int = 5) -> list[str]:
        """Get recent files from history."""
        return self.file_history[-count:] if self.file_history else []

    def get_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        return {
            "session_id": self.session_id,
            "rules_loaded": len(self.loaded_rule_ids),
            "patterns_seen": list(self.loaded_patterns),
            "files_processed": len(self.file_history),
            "total_tokens": self.token_count,
            "pattern_frequency": dict(self.pattern_frequency),
            "rule_visit_counts": dict(self.rule_visit_counts),
            "last_activity": self.last_activity.isoformat(),
            "session_duration": (datetime.now() - self.last_activity).total_seconds(),
        }


class SessionManager:
    """Manage AI coding sessions."""

    def __init__(self, cleanup_interval: int = 3600):
        self.sessions: dict[str, SessionState] = {}
        self.cleanup_interval = cleanup_interval  # seconds
        self._cleanup_task: asyncio.Task | None = None

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get existing session or create new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id)
            logger.info(f"Created new session: {session_id}")

        session = self.sessions[session_id]
        session.update_activity()
        return session

    def get_session(self, session_id: str) -> SessionState | None:
        """Get existing session without creating new one."""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False

    def cleanup_stale_sessions(self) -> int:
        """Remove inactive sessions."""
        current_time = datetime.now()
        stale_sessions = []

        for session_id, session in self.sessions.items():
            if (current_time - session.last_activity).total_seconds() > self.cleanup_interval:
                stale_sessions.append(session_id)

        for session_id in stale_sessions:
            del self.sessions[session_id]
            logger.info(f"Cleaned up stale session: {session_id}")

        return len(stale_sessions)

    def get_active_sessions(self) -> list[str]:
        """Get list of active session IDs."""
        return list(self.sessions.keys())

    def get_session_count(self) -> int:
        """Get number of active sessions."""
        return len(self.sessions)

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all sessions."""
        return {
            "total_sessions": len(self.sessions),
            "active_sessions": list(self.sessions.keys()),
            "cleanup_interval": self.cleanup_interval,
            "sessions": {session_id: session.get_stats() for session_id, session in self.sessions.items()},
        }

    async def start_cleanup_task(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                cleaned = self.cleanup_stale_sessions()
                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} stale sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    def __del__(self):
        """Cleanup on deletion."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()


async def session_cleanup_loop(session_manager: SessionManager) -> None:
    """Standalone cleanup loop function."""
    await session_manager.start_cleanup_task()
