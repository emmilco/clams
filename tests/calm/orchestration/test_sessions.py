"""Tests for CALM orchestration sessions module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.sessions import (
    get_pending_handoff,
    get_session,
    list_sessions,
    mark_session_resumed,
    save_session,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


class TestSaveSession:
    """Tests for save_session function."""

    def test_save_session_returns_id(self, test_db: Path) -> None:
        """Test saving a session returns a session ID."""
        session_id = save_session(
            content="Test handoff content",
            needs_continuation=False,
            db_path=test_db,
        )

        assert session_id is not None
        assert len(session_id) == 8  # UUID prefix

    def test_save_session_with_continuation(self, test_db: Path) -> None:
        """Test saving a session marked for continuation."""
        session_id = save_session(
            content="Continue this work",
            needs_continuation=True,
            db_path=test_db,
        )

        session = get_session(session_id, db_path=test_db)
        assert session is not None
        assert session.needs_continuation is True


class TestGetSession:
    """Tests for get_session function."""

    def test_get_existing_session(self, test_db: Path) -> None:
        """Test getting an existing session."""
        session_id = save_session(
            content="Test content",
            db_path=test_db,
        )

        session = get_session(session_id, db_path=test_db)
        assert session is not None
        assert session.id == session_id
        assert session.handoff_content == "Test content"

    def test_get_nonexistent_session(self, test_db: Path) -> None:
        """Test getting a nonexistent session returns None."""
        session = get_session("nonexistent", db_path=test_db)
        assert session is None


class TestListSessions:
    """Tests for list_sessions function."""

    def test_list_sessions_empty(self, test_db: Path) -> None:
        """Test listing sessions when none exist."""
        sessions = list_sessions(db_path=test_db)
        assert sessions == []

    def test_list_sessions_with_limit(self, test_db: Path) -> None:
        """Test listing sessions with a limit."""
        # Create 3 sessions
        for i in range(3):
            save_session(content=f"Session {i}", db_path=test_db)

        sessions = list_sessions(limit=2, db_path=test_db)
        assert len(sessions) == 2


class TestGetPendingHandoff:
    """Tests for get_pending_handoff function."""

    def test_no_pending_handoff(self, test_db: Path) -> None:
        """Test when there's no pending handoff."""
        # Save a session without continuation
        save_session(content="Test", needs_continuation=False, db_path=test_db)

        pending = get_pending_handoff(db_path=test_db)
        assert pending is None

    def test_get_pending_handoff(self, test_db: Path) -> None:
        """Test getting a pending handoff."""
        session_id = save_session(
            content="Continue this",
            needs_continuation=True,
            db_path=test_db,
        )

        pending = get_pending_handoff(db_path=test_db)
        assert pending is not None
        assert pending.id == session_id
        assert pending.needs_continuation is True


class TestMarkSessionResumed:
    """Tests for mark_session_resumed function."""

    def test_mark_session_resumed(self, test_db: Path) -> None:
        """Test marking a session as resumed."""
        session_id = save_session(
            content="Test",
            needs_continuation=True,
            db_path=test_db,
        )

        mark_session_resumed(session_id, db_path=test_db)

        session = get_session(session_id, db_path=test_db)
        assert session is not None
        assert session.resumed_at is not None

    def test_mark_nonexistent_session_raises(self, test_db: Path) -> None:
        """Test marking nonexistent session raises error."""
        with pytest.raises(ValueError, match="not found"):
            mark_session_resumed("nonexistent", db_path=test_db)
