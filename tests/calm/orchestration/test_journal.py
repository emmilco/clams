"""Tests for CALM orchestration journal module."""

from pathlib import Path

import pytest

from calm.db.schema import init_database
from calm.orchestration.journal import (
    get_journal_entry,
    list_journal_entries,
    mark_entries_reflected,
    store_journal_entry,
)


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def mock_sessions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary sessions directory."""
    import calm.config

    temp_sessions_dir = tmp_path / "sessions"
    temp_sessions_dir.mkdir()

    # Patch settings to use temp sessions dir
    class MockSettings:
        @property
        def sessions_dir(self) -> Path:
            return temp_sessions_dir

    monkeypatch.setattr(calm.config, "settings", MockSettings())
    monkeypatch.setattr(
        "calm.orchestration.journal.settings", MockSettings()
    )

    return temp_sessions_dir


class TestStoreJournalEntry:
    """Tests for store_journal_entry function."""

    def test_store_basic_entry(self, test_db: Path) -> None:
        """Test storing a basic journal entry."""
        entry_id, session_log_path = store_journal_entry(
            summary="Test session summary",
            working_directory="/test/project",
            db_path=test_db,
        )

        assert entry_id is not None
        assert len(entry_id) == 36  # Full UUID
        assert session_log_path is None

    def test_store_with_friction_points_and_next_steps(self, test_db: Path) -> None:
        """Test storing with friction points and next steps."""
        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            friction_points=["Issue 1", "Issue 2"],
            next_steps=["Step 1", "Step 2"],
            db_path=test_db,
        )

        entry = get_journal_entry(entry_id, db_path=test_db)
        assert entry is not None
        assert entry.friction_points == ["Issue 1", "Issue 2"]
        assert entry.next_steps == ["Step 1", "Step 2"]

    def test_store_with_session_log(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test storing with session log content."""
        log_content = '{"type": "test"}\n{"type": "test2"}\n'

        entry_id, session_log_path = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            session_log_content=log_content,
            db_path=test_db,
        )

        assert session_log_path is not None
        assert Path(session_log_path).exists()
        assert Path(session_log_path).read_text() == log_content

    def test_project_name_extracted(self, test_db: Path) -> None:
        """Test that project name is extracted from working directory."""
        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/Users/test/myproject",
            db_path=test_db,
        )

        entry = get_journal_entry(entry_id, db_path=test_db)
        assert entry is not None
        assert entry.project_name == "myproject"


class TestListJournalEntries:
    """Tests for list_journal_entries function."""

    def test_list_empty(self, test_db: Path) -> None:
        """Test listing when no entries exist."""
        entries = list_journal_entries(db_path=test_db)
        assert entries == []

    def test_list_returns_entries(self, test_db: Path) -> None:
        """Test listing returns stored entries."""
        store_journal_entry(
            summary="Entry 1",
            working_directory="/test/project1",
            db_path=test_db,
        )
        store_journal_entry(
            summary="Entry 2",
            working_directory="/test/project2",
            db_path=test_db,
        )

        entries = list_journal_entries(db_path=test_db)
        assert len(entries) == 2

    def test_list_with_limit(self, test_db: Path) -> None:
        """Test limiting results."""
        for i in range(5):
            store_journal_entry(
                summary=f"Entry {i}",
                working_directory=f"/test/project{i}",
                db_path=test_db,
            )

        entries = list_journal_entries(limit=3, db_path=test_db)
        assert len(entries) == 3

    def test_list_unreflected_only(self, test_db: Path) -> None:
        """Test filtering for unreflected entries."""
        entry1_id, _ = store_journal_entry(
            summary="Entry 1",
            working_directory="/test/project1",
            db_path=test_db,
        )
        store_journal_entry(
            summary="Entry 2",
            working_directory="/test/project2",
            db_path=test_db,
        )

        # Mark entry1 as reflected
        mark_entries_reflected([entry1_id], delete_logs=False, db_path=test_db)

        entries = list_journal_entries(unreflected_only=True, db_path=test_db)
        assert len(entries) == 1
        assert entries[0].summary == "Entry 2"

    def test_list_filter_by_project(self, test_db: Path) -> None:
        """Test filtering by project name."""
        store_journal_entry(
            summary="Entry 1",
            working_directory="/test/project1",
            db_path=test_db,
        )
        store_journal_entry(
            summary="Entry 2",
            working_directory="/test/project2",
            db_path=test_db,
        )

        entries = list_journal_entries(project_name="project1", db_path=test_db)
        assert len(entries) == 1
        assert entries[0].project_name == "project1"

    def test_list_filter_by_working_directory(self, test_db: Path) -> None:
        """Test filtering by exact working directory."""
        store_journal_entry(
            summary="Entry 1",
            working_directory="/test/project",
            db_path=test_db,
        )
        store_journal_entry(
            summary="Entry 2",
            working_directory="/other/project",
            db_path=test_db,
        )

        entries = list_journal_entries(
            working_directory="/test/project", db_path=test_db
        )
        assert len(entries) == 1
        assert entries[0].working_directory == "/test/project"


class TestGetJournalEntry:
    """Tests for get_journal_entry function."""

    def test_get_existing(self, test_db: Path) -> None:
        """Test getting an existing entry."""
        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            friction_points=["Issue 1"],
            next_steps=["Step 1"],
            db_path=test_db,
        )

        entry = get_journal_entry(entry_id, db_path=test_db)
        assert entry is not None
        assert entry.id == entry_id
        assert entry.summary == "Test summary"
        assert entry.working_directory == "/test/project"
        assert entry.friction_points == ["Issue 1"]
        assert entry.next_steps == ["Step 1"]
        assert entry.reflected_at is None
        assert entry.memories_created == 0

    def test_get_nonexistent(self, test_db: Path) -> None:
        """Test getting nonexistent entry returns None."""
        entry = get_journal_entry(
            "00000000-0000-0000-0000-000000000000", db_path=test_db
        )
        assert entry is None

    def test_get_with_log(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test getting entry with session log."""
        log_content = '{"type": "test"}\n'

        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            session_log_content=log_content,
            db_path=test_db,
        )

        entry = get_journal_entry(entry_id, include_log=True, db_path=test_db)
        assert entry is not None
        assert entry.session_log == log_content

    def test_get_without_log_flag(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test getting entry without log flag doesn't load log."""
        log_content = '{"type": "test"}\n'

        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            session_log_content=log_content,
            db_path=test_db,
        )

        entry = get_journal_entry(entry_id, include_log=False, db_path=test_db)
        assert entry is not None
        assert entry.session_log is None


class TestMarkEntriesReflected:
    """Tests for mark_entries_reflected function."""

    def test_mark_single_entry(self, test_db: Path) -> None:
        """Test marking a single entry as reflected."""
        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            db_path=test_db,
        )

        marked_count, logs_deleted = mark_entries_reflected(
            [entry_id], delete_logs=False, db_path=test_db
        )

        assert marked_count == 1
        assert logs_deleted == 0

        entry = get_journal_entry(entry_id, db_path=test_db)
        assert entry is not None
        assert entry.reflected_at is not None

    def test_mark_multiple_entries(self, test_db: Path) -> None:
        """Test marking multiple entries."""
        entry1_id, _ = store_journal_entry(
            summary="Entry 1",
            working_directory="/test/project1",
            db_path=test_db,
        )
        entry2_id, _ = store_journal_entry(
            summary="Entry 2",
            working_directory="/test/project2",
            db_path=test_db,
        )

        marked_count, _ = mark_entries_reflected(
            [entry1_id, entry2_id], delete_logs=False, db_path=test_db
        )

        assert marked_count == 2

    def test_mark_with_memories_created(self, test_db: Path) -> None:
        """Test marking with memories_created count."""
        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            db_path=test_db,
        )

        mark_entries_reflected(
            [entry_id], memories_created=5, delete_logs=False, db_path=test_db
        )

        entry = get_journal_entry(entry_id, db_path=test_db)
        assert entry is not None
        assert entry.memories_created == 5

    def test_mark_deletes_logs(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test that marking with delete_logs=True removes log files."""
        log_content = '{"type": "test"}\n'

        entry_id, session_log_path = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            session_log_content=log_content,
            db_path=test_db,
        )

        assert session_log_path is not None
        assert Path(session_log_path).exists()

        _, logs_deleted = mark_entries_reflected(
            [entry_id], delete_logs=True, db_path=test_db
        )

        assert logs_deleted == 1
        assert not Path(session_log_path).exists()

    def test_mark_nonexistent_entry_ignored(self, test_db: Path) -> None:
        """Test that nonexistent entries are ignored."""
        marked_count, _ = mark_entries_reflected(
            ["00000000-0000-0000-0000-000000000000"],
            delete_logs=False,
            db_path=test_db,
        )
        assert marked_count == 0
