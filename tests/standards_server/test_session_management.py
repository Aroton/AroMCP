"""Tests for session management functionality."""

import asyncio
from datetime import datetime, timedelta

import pytest

from aromcp.standards_server.services.session_manager import SessionManager, SessionState


class TestSessionState:
    """Test SessionState functionality."""

    def test_session_state_initialization(self):
        """Test basic session state initialization."""
        session = SessionState("test-session")

        assert session.session_id == "test-session"
        assert len(session.loaded_rule_ids) == 0
        assert len(session.loaded_patterns) == 0
        assert len(session.file_history) == 0
        assert session.token_count == 0
        assert isinstance(session.last_activity, datetime)
        assert len(session.context_cache) == 0
        assert len(session.pattern_frequency) == 0

    def test_add_rule(self):
        """Test adding rules to session."""
        session = SessionState("test-session")

        session.add_rule("rule1", "validation", 50)
        session.add_rule("rule2", "validation", 30)
        session.add_rule("rule3", "error-handling", 40)

        assert len(session.loaded_rule_ids) == 3
        assert "rule1" in session.loaded_rule_ids
        assert "rule2" in session.loaded_rule_ids
        assert "rule3" in session.loaded_rule_ids

        assert len(session.loaded_patterns) == 2
        assert "validation" in session.loaded_patterns
        assert "error-handling" in session.loaded_patterns

        assert session.token_count == 120
        assert session.pattern_frequency["validation"] == 2
        assert session.pattern_frequency["error-handling"] == 1

    def test_add_file(self):
        """Test adding files to session history."""
        session = SessionState("test-session")

        session.add_file("/path/to/file1.ts")
        session.add_file("/path/to/file2.ts")
        session.add_file("/path/to/file3.ts")

        assert len(session.file_history) == 3
        assert session.file_history[-1] == "/path/to/file3.ts"

        # Test file history limit
        for i in range(25):  # Add more than limit
            session.add_file(f"/path/to/file{i}.ts")

        assert len(session.file_history) == 20  # Should be capped at 20

    def test_pattern_frequency(self):
        """Test pattern frequency tracking."""
        session = SessionState("test-session")

        session.add_rule("rule1", "validation", 50)
        session.add_rule("rule2", "validation", 30)
        session.add_rule("rule3", "error-handling", 40)

        assert session.get_pattern_frequency("validation") == 2
        assert session.get_pattern_frequency("error-handling") == 1
        assert session.get_pattern_frequency("unknown") == 0

    def test_rule_loaded_check(self):
        """Test checking if rules are loaded."""
        session = SessionState("test-session")

        assert not session.is_rule_loaded("rule1")

        session.add_rule("rule1", "validation", 50)

        assert session.is_rule_loaded("rule1")
        assert not session.is_rule_loaded("rule2")

    def test_pattern_seen_check(self):
        """Test checking if patterns are seen."""
        session = SessionState("test-session")

        assert not session.is_pattern_seen("validation")

        session.add_rule("rule1", "validation", 50)

        assert session.is_pattern_seen("validation")
        assert not session.is_pattern_seen("error-handling")

    def test_get_recent_files(self):
        """Test getting recent files."""
        session = SessionState("test-session")

        files = [f"/path/to/file{i}.ts" for i in range(10)]
        for file in files:
            session.add_file(file)

        recent = session.get_recent_files(5)
        assert len(recent) == 5
        assert recent == files[-5:]

        # Test with fewer files than requested
        session2 = SessionState("test-session-2")
        session2.add_file("/single/file.ts")

        recent2 = session2.get_recent_files(5)
        assert len(recent2) == 1
        assert recent2 == ["/single/file.ts"]

    def test_get_stats(self):
        """Test getting session statistics."""
        session = SessionState("test-session")

        session.add_rule("rule1", "validation", 50)
        session.add_rule("rule2", "error-handling", 30)
        session.add_file("/path/to/file.ts")

        stats = session.get_stats()

        assert stats["session_id"] == "test-session"
        assert stats["rules_loaded"] == 2
        assert "validation" in stats["patterns_seen"]
        assert "error-handling" in stats["patterns_seen"]
        assert stats["files_processed"] == 1
        assert stats["total_tokens"] == 80
        assert stats["pattern_frequency"]["validation"] == 1
        assert stats["pattern_frequency"]["error-handling"] == 1
        assert "last_activity" in stats
        assert "session_duration" in stats


class TestSessionManager:
    """Test SessionManager functionality."""

    def test_session_manager_initialization(self):
        """Test session manager initialization."""
        manager = SessionManager()

        assert len(manager.sessions) == 0
        assert manager.cleanup_interval == 3600
        assert manager._cleanup_task is None

    def test_get_or_create_session(self):
        """Test getting or creating sessions."""
        manager = SessionManager()

        # Test creating new session
        session1 = manager.get_or_create_session("session1")
        assert session1.session_id == "session1"
        assert len(manager.sessions) == 1

        # Test getting existing session
        session1_again = manager.get_or_create_session("session1")
        assert session1_again is session1
        assert len(manager.sessions) == 1

        # Test creating another session
        session2 = manager.get_or_create_session("session2")
        assert session2.session_id == "session2"
        assert len(manager.sessions) == 2
        assert session2 is not session1

    def test_get_session(self):
        """Test getting existing sessions."""
        manager = SessionManager()

        # Test getting non-existent session
        assert manager.get_session("nonexistent") is None

        # Create session and test getting it
        session = manager.get_or_create_session("test-session")
        retrieved = manager.get_session("test-session")

        assert retrieved is session

    def test_delete_session(self):
        """Test deleting sessions."""
        manager = SessionManager()

        # Test deleting non-existent session
        assert not manager.delete_session("nonexistent")

        # Create and delete session
        manager.get_or_create_session("test-session")
        assert len(manager.sessions) == 1

        success = manager.delete_session("test-session")
        assert success
        assert len(manager.sessions) == 0

    def test_cleanup_stale_sessions(self):
        """Test cleaning up stale sessions."""
        manager = SessionManager(cleanup_interval=1)  # 1 second for testing

        # Create sessions
        session1 = manager.get_or_create_session("session1")
        manager.get_or_create_session("session2")

        # Make one session stale
        session1.last_activity = datetime.now() - timedelta(seconds=2)

        cleaned = manager.cleanup_stale_sessions()

        assert cleaned == 1
        assert len(manager.sessions) == 1
        assert "session1" not in manager.sessions
        assert "session2" in manager.sessions

    def test_get_active_sessions(self):
        """Test getting active session list."""
        manager = SessionManager()

        assert manager.get_active_sessions() == []

        manager.get_or_create_session("session1")
        manager.get_or_create_session("session2")

        active = manager.get_active_sessions()
        assert len(active) == 2
        assert "session1" in active
        assert "session2" in active

    def test_get_session_count(self):
        """Test getting session count."""
        manager = SessionManager()

        assert manager.get_session_count() == 0

        manager.get_or_create_session("session1")
        assert manager.get_session_count() == 1

        manager.get_or_create_session("session2")
        assert manager.get_session_count() == 2

        manager.delete_session("session1")
        assert manager.get_session_count() == 1

    def test_get_all_stats(self):
        """Test getting all session statistics."""
        manager = SessionManager()

        stats = manager.get_all_stats()
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == []

        session1 = manager.get_or_create_session("session1")
        session1.add_rule("rule1", "validation", 50)

        session2 = manager.get_or_create_session("session2")
        session2.add_rule("rule2", "error-handling", 30)

        stats = manager.get_all_stats()
        assert stats["total_sessions"] == 2
        assert len(stats["active_sessions"]) == 2
        assert "session1" in stats["sessions"]
        assert "session2" in stats["sessions"]
        assert stats["sessions"]["session1"]["rules_loaded"] == 1
        assert stats["sessions"]["session2"]["rules_loaded"] == 1

    @pytest.mark.asyncio
    async def test_start_stop_cleanup_task(self):
        """Test starting and stopping cleanup task."""
        manager = SessionManager(cleanup_interval=0.1)  # Very short for testing

        # Start cleanup task
        await manager.start_cleanup_task()
        assert manager._cleanup_task is not None
        assert not manager._cleanup_task.done()

        # Stop cleanup task
        await manager.stop_cleanup_task()
        assert manager._cleanup_task.done()

    @pytest.mark.asyncio
    async def test_cleanup_loop_functionality(self):
        """Test the cleanup loop functionality."""
        manager = SessionManager(cleanup_interval=0.1)  # Very short for testing

        # Create a stale session
        session = manager.get_or_create_session("stale-session")
        session.last_activity = datetime.now() - timedelta(seconds=1)

        # Start cleanup and wait
        await manager.start_cleanup_task()
        await asyncio.sleep(0.2)  # Wait for cleanup to run

        # Session should be cleaned up
        assert len(manager.sessions) == 0

        await manager.stop_cleanup_task()

    def test_update_activity_on_access(self):
        """Test that activity is updated when accessing sessions."""
        manager = SessionManager()

        session = manager.get_or_create_session("test-session")
        original_time = session.last_activity

        # Wait a bit and access again
        import time

        time.sleep(0.01)

        session_again = manager.get_or_create_session("test-session")
        assert session_again.last_activity > original_time
