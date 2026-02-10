"""Tests for session management tools."""

import json
from pathlib import Path

import pytest

from calm.tools.session import SessionManager, get_session_id, get_session_tools


@pytest.fixture
def temp_session_dirs(tmp_path: Path) -> tuple[Path, Path]:
    """Create temporary directories for session testing."""
    clams_dir = tmp_path / ".clams"
    journal_dir = clams_dir / "journal"
    journal_dir.mkdir(parents=True)
    return clams_dir, journal_dir


@pytest.fixture
def session_manager(temp_session_dirs: tuple[Path, Path]) -> SessionManager:
    """Create session manager with temp paths."""
    clams_dir, journal_dir = temp_session_dirs
    return SessionManager(calm_dir=clams_dir, journal_dir=journal_dir)


class TestGetSessionId:
    """Test module-level get_session_id function."""

    def test_env_var_takes_priority(
        self,
        monkeypatch: pytest.MonkeyPatch,
        temp_session_dirs: tuple[Path, Path],
    ) -> None:
        """CLAUDE_SESSION_ID env var should take priority over file."""
        _, journal_dir = temp_session_dirs
        session_id_file = journal_dir / ".session_id"
        session_id_file.write_text("file-session-id")

        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session-id")
        result = get_session_id(session_id_file=session_id_file)
        assert result == "env-session-id"

    def test_file_fallback_when_no_env_var(
        self,
        monkeypatch: pytest.MonkeyPatch,
        temp_session_dirs: tuple[Path, Path],
    ) -> None:
        """Should fall back to file when env var is not set."""
        _, journal_dir = temp_session_dirs
        session_id_file = journal_dir / ".session_id"
        session_id_file.write_text("file-session-id")

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        result = get_session_id(session_id_file=session_id_file)
        assert result == "file-session-id"

    def test_returns_none_when_neither_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
        temp_session_dirs: tuple[Path, Path],
    ) -> None:
        """Should return None when neither env var nor file is available."""
        _, journal_dir = temp_session_dirs
        session_id_file = journal_dir / ".session_id"
        # Don't create the file

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        result = get_session_id(session_id_file=session_id_file)
        assert result is None

    def test_empty_env_var_falls_back_to_file(
        self,
        monkeypatch: pytest.MonkeyPatch,
        temp_session_dirs: tuple[Path, Path],
    ) -> None:
        """Empty CLAUDE_SESSION_ID should fall back to file."""
        _, journal_dir = temp_session_dirs
        session_id_file = journal_dir / ".session_id"
        session_id_file.write_text("file-session-id")

        monkeypatch.setenv("CLAUDE_SESSION_ID", "")
        result = get_session_id(session_id_file=session_id_file)
        assert result == "file-session-id"

    def test_empty_file_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
        temp_session_dirs: tuple[Path, Path],
    ) -> None:
        """Empty session ID file should return None."""
        _, journal_dir = temp_session_dirs
        session_id_file = journal_dir / ".session_id"
        session_id_file.write_text("")

        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        result = get_session_id(session_id_file=session_id_file)
        assert result is None


class TestSessionManager:
    """Test SessionManager state management."""

    def test_init_creates_manager(
        self, temp_session_dirs: tuple[Path, Path]
    ) -> None:
        """SessionManager should initialize with custom paths."""
        clams_dir, journal_dir = temp_session_dirs
        manager = SessionManager(calm_dir=clams_dir, journal_dir=journal_dir)

        assert manager.calm_dir == clams_dir
        assert manager.journal_dir == journal_dir
        assert manager._tool_count == 0

    def test_load_tool_count_from_file(
        self, temp_session_dirs: tuple[Path, Path]
    ) -> None:
        """SessionManager should load tool count from file."""
        clams_dir, journal_dir = temp_session_dirs
        tool_count_file = journal_dir / ".tool_count"
        tool_count_file.write_text("42")

        manager = SessionManager(calm_dir=clams_dir, journal_dir=journal_dir)

        assert manager._tool_count == 42

    def test_load_tool_count_invalid_file(
        self, temp_session_dirs: tuple[Path, Path]
    ) -> None:
        """SessionManager should default to 0 for invalid tool count."""
        clams_dir, journal_dir = temp_session_dirs
        tool_count_file = journal_dir / ".tool_count"
        tool_count_file.write_text("invalid")

        manager = SessionManager(calm_dir=clams_dir, journal_dir=journal_dir)

        assert manager._tool_count == 0

    def test_save_tool_count(self, session_manager: SessionManager) -> None:
        """_save_tool_count should write count to file."""
        session_manager._tool_count = 15
        session_manager._save_tool_count()

        assert session_manager.tool_count_file.read_text() == "15"

    def test_get_current_session_id_from_file(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_current_session_id should return session ID from file when no env var."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        session_manager.session_id_file.write_text("test-session-123")

        assert session_manager.get_current_session_id() == "test-session-123"

    def test_get_current_session_id_prefers_env_var(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_current_session_id should prefer env var over file."""
        session_manager.session_id_file.write_text("file-session")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-session")

        assert session_manager.get_current_session_id() == "env-session"

    def test_get_current_session_id_no_file(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_current_session_id should return None if no file and no env var."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        assert session_manager.get_current_session_id() is None


class TestStartSession:
    """Test start_session tool."""

    @pytest.mark.asyncio
    async def test_uses_env_var_when_available(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_session should use CLAUDE_SESSION_ID env var when set."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "claude-env-session-42")
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()

        assert result["session_id"] == "claude-env-session-42"
        # Should also write to file for ObservationCollector compatibility
        assert session_manager.session_id_file.read_text() == "claude-env-session-42"

    @pytest.mark.asyncio
    async def test_generates_collector_format_without_env_var(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_session should generate session_YYYYMMDD_HHMMSS_random6 format without env var."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()

        session_id = result["session_id"]
        # Should match ObservationCollector format: session_YYYYMMDD_HHMMSS_random6
        assert session_id.startswith("session_")
        parts = session_id.split("_")
        assert len(parts) == 4  # session, date, time, random
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 6  # random hex

    @pytest.mark.asyncio
    async def test_writes_session_id_file(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_session should write session ID to file."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()

        session_id = session_manager.session_id_file.read_text()
        assert session_id == result["session_id"]

    @pytest.mark.asyncio
    async def test_resets_tool_count(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_session should reset tool count to 0."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        session_manager._tool_count = 50
        session_manager._save_tool_count()

        tools = get_session_tools(session_manager)
        await tools["start_session"]()

        assert session_manager._tool_count == 0
        assert session_manager.tool_count_file.read_text() == "0"

    @pytest.mark.asyncio
    async def test_returns_timestamp(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """start_session should return started_at timestamp."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()

        assert "started_at" in result
        # Should be ISO format
        assert "T" in result["started_at"]

    @pytest.mark.asyncio
    async def test_consistency_env_var_and_file(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After start_session with env var, get_current_session_id returns same value."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "consistent-session")
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()

        assert result["session_id"] == session_manager.get_current_session_id()

    @pytest.mark.asyncio
    async def test_consistency_generated_and_file(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """After start_session without env var, get_current_session_id returns same value."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        tools = get_session_tools(session_manager)
        result = await tools["start_session"]()

        assert result["session_id"] == session_manager.get_current_session_id()


class TestGetOrphanedGhap:
    """Test get_orphaned_ghap tool."""

    @pytest.mark.asyncio
    async def test_no_orphan_when_no_ghap_file(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_orphaned_ghap should return has_orphan=False if no file."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        tools = get_session_tools(session_manager)
        result = await tools["get_orphaned_ghap"]()

        assert result["has_orphan"] is False

    @pytest.mark.asyncio
    async def test_no_orphan_when_same_session(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_orphaned_ghap should return has_orphan=False for current session."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        # Set up session and GHAP
        session_manager.session_id_file.write_text("current-session")
        session_manager.current_ghap_file.write_text(
            json.dumps({
                "session_id": "current-session",
                "goal": "Test goal",
                "hypothesis": "Test hypothesis",
            })
        )

        tools = get_session_tools(session_manager)
        result = await tools["get_orphaned_ghap"]()

        assert result["has_orphan"] is False

    @pytest.mark.asyncio
    async def test_orphan_detected_for_different_session(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_orphaned_ghap should detect orphan from different session."""
        monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
        # Set up session and orphaned GHAP
        session_manager.session_id_file.write_text("new-session")
        session_manager.current_ghap_file.write_text(
            json.dumps({
                "session_id": "old-session",
                "goal": "Old goal",
                "hypothesis": "Old hypothesis",
                "action": "Old action",
                "prediction": "Old prediction",
                "created_at": "2024-01-01T00:00:00Z",
            })
        )

        tools = get_session_tools(session_manager)
        result = await tools["get_orphaned_ghap"]()

        assert result["has_orphan"] is True
        assert result["session_id"] == "old-session"
        assert result["goal"] == "Old goal"
        assert result["hypothesis"] == "Old hypothesis"

    @pytest.mark.asyncio
    async def test_orphan_detected_via_env_var(
        self,
        session_manager: SessionManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """get_orphaned_ghap should use env var for current session comparison."""
        monkeypatch.setenv("CLAUDE_SESSION_ID", "env-current-session")
        # File says one thing, env var says another - env var wins
        session_manager.session_id_file.write_text("old-session")
        session_manager.current_ghap_file.write_text(
            json.dumps({
                "session_id": "old-session",
                "goal": "Test goal",
                "hypothesis": "Test hypothesis",
                "action": "Test action",
                "prediction": "Test prediction",
            })
        )

        tools = get_session_tools(session_manager)
        result = await tools["get_orphaned_ghap"]()

        # Should detect orphan because env var != ghap session
        assert result["has_orphan"] is True
        assert result["session_id"] == "old-session"


class TestShouldCheckIn:
    """Test should_check_in tool."""

    @pytest.mark.asyncio
    async def test_returns_false_when_count_low(
        self, session_manager: SessionManager
    ) -> None:
        """should_check_in should return False when count < frequency."""
        session_manager._tool_count = 5

        tools = get_session_tools(session_manager)
        result = await tools["should_check_in"](frequency=10)

        assert result["should_check_in"] is False

    @pytest.mark.asyncio
    async def test_returns_true_when_count_equals_frequency(
        self, session_manager: SessionManager
    ) -> None:
        """should_check_in should return True when count >= frequency."""
        session_manager._tool_count = 10

        tools = get_session_tools(session_manager)
        result = await tools["should_check_in"](frequency=10)

        assert result["should_check_in"] is True

    @pytest.mark.asyncio
    async def test_returns_true_when_count_exceeds_frequency(
        self, session_manager: SessionManager
    ) -> None:
        """should_check_in should return True when count > frequency."""
        session_manager._tool_count = 15

        tools = get_session_tools(session_manager)
        result = await tools["should_check_in"](frequency=10)

        assert result["should_check_in"] is True

    @pytest.mark.asyncio
    async def test_uses_default_frequency(
        self, session_manager: SessionManager
    ) -> None:
        """should_check_in should use default frequency of 10."""
        session_manager._tool_count = 9

        tools = get_session_tools(session_manager)
        result = await tools["should_check_in"]()

        assert result["should_check_in"] is False


class TestIncrementToolCount:
    """Test increment_tool_count tool."""

    @pytest.mark.asyncio
    async def test_increments_count(
        self, session_manager: SessionManager
    ) -> None:
        """increment_tool_count should increase count by 1."""
        session_manager._tool_count = 5

        tools = get_session_tools(session_manager)
        result = await tools["increment_tool_count"]()

        assert result["tool_count"] == 6
        assert session_manager._tool_count == 6

    @pytest.mark.asyncio
    async def test_persists_to_file(
        self, session_manager: SessionManager
    ) -> None:
        """increment_tool_count should save count to file."""
        tools = get_session_tools(session_manager)
        await tools["increment_tool_count"]()
        await tools["increment_tool_count"]()
        await tools["increment_tool_count"]()

        assert session_manager.tool_count_file.read_text() == "3"


class TestResetToolCount:
    """Test reset_tool_count tool."""

    @pytest.mark.asyncio
    async def test_resets_count_to_zero(
        self, session_manager: SessionManager
    ) -> None:
        """reset_tool_count should set count to 0."""
        session_manager._tool_count = 25

        tools = get_session_tools(session_manager)
        result = await tools["reset_tool_count"]()

        assert result["tool_count"] == 0
        assert session_manager._tool_count == 0

    @pytest.mark.asyncio
    async def test_persists_to_file(
        self, session_manager: SessionManager
    ) -> None:
        """reset_tool_count should save zero to file."""
        session_manager._tool_count = 25
        session_manager._save_tool_count()

        tools = get_session_tools(session_manager)
        await tools["reset_tool_count"]()

        assert session_manager.tool_count_file.read_text() == "0"
