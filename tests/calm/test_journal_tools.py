"""Tests for CALM journal MCP tools."""

import re
from pathlib import Path

import pytest

import calm.config
from calm.db.schema import init_database
from calm.tools.journal import get_journal_tools


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    return db_path


@pytest.fixture
def mock_sessions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary sessions directory."""
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


class TestStoreJournalEntryTool:
    """Tests for store_journal_entry MCP tool."""

    @pytest.mark.asyncio
    async def test_store_basic_entry(self, test_db: Path) -> None:
        """Test storing a basic journal entry."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
            summary="Test session summary",
            working_directory="/test/project",
        )

        assert "id" in result
        assert result["session_log_path"] is None

    @pytest.mark.asyncio
    async def test_store_with_all_fields(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test storing with all optional fields."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
            summary="Test session summary",
            working_directory="/test/project",
            friction_points=["Issue 1", "Issue 2"],
            next_steps=["Step 1", "Step 2"],
            session_log_content='{"type": "test"}\n',
        )

        assert "id" in result
        assert result["session_log_path"] is not None

    @pytest.mark.asyncio
    async def test_store_empty_summary_fails(self, test_db: Path) -> None:
        """Test that empty summary raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
                summary="",
                working_directory="/test/project",
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Summary is required", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_store_whitespace_summary_fails(self, test_db: Path) -> None:
        """Test that whitespace-only summary raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
                summary="   ",
                working_directory="/test/project",
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Summary is required", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_store_empty_working_directory_fails(self, test_db: Path) -> None:
        """Test that empty working directory raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
                summary="Test summary",
                working_directory="",
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Working directory", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_store_summary_too_long_fails(self, test_db: Path) -> None:
        """Test that overly long summary raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
                summary="x" * 10001,
                working_directory="/test/project",
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"too long", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_store_too_many_friction_points_fails(
        self, test_db: Path
    ) -> None:
        """Test that too many friction points raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
                summary="Test summary",
                working_directory="/test/project",
                friction_points=[f"Point {i}" for i in range(51)],
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Maximum 50", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_store_too_many_next_steps_fails(
        self, test_db: Path
    ) -> None:
        """Test that too many next steps raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["store_journal_entry"](
                summary="Test summary",
                working_directory="/test/project",
                next_steps=[f"Step {i}" for i in range(51)],
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Maximum 50", result["error"]["message"])
class TestListJournalEntriesTool:
    """Tests for list_journal_entries MCP tool."""

    @pytest.mark.asyncio
    async def test_list_empty(self, test_db: Path) -> None:
        """Test listing when no entries exist."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["list_journal_entries"]()

        assert result["entries"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_list_returns_entries(self, test_db: Path) -> None:
        """Test listing returns stored entries."""
        tools = get_journal_tools(db_path=test_db)

        # Store some entries
        await tools["store_journal_entry"](
            summary="Entry 1",
            working_directory="/test/project1",
        )
        await tools["store_journal_entry"](
            summary="Entry 2",
            working_directory="/test/project2",
        )

        result = await tools["list_journal_entries"]()

        assert len(result["entries"]) == 2
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_list_with_limit(self, test_db: Path) -> None:
        """Test limiting results."""
        tools = get_journal_tools(db_path=test_db)

        for i in range(5):
            await tools["store_journal_entry"](
                summary=f"Entry {i}",
                working_directory=f"/test/project{i}",
            )

        result = await tools["list_journal_entries"](limit=3)

        assert len(result["entries"]) == 3
        assert result["count"] == 3

    @pytest.mark.asyncio
    async def test_list_invalid_limit_fails(self, test_db: Path) -> None:
        """Test that invalid limit raises validation error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["list_journal_entries"](limit=0)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"out of range", result["error"]["message"])
        result = await tools["list_journal_entries"](limit=201)
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"out of range", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_list_unreflected_only(self, test_db: Path) -> None:
        """Test filtering for unreflected entries."""
        tools = get_journal_tools(db_path=test_db)

        result1 = await tools["store_journal_entry"](
            summary="Entry 1",
            working_directory="/test/project1",
        )
        await tools["store_journal_entry"](
            summary="Entry 2",
            working_directory="/test/project2",
        )

        # Mark entry1 as reflected
        await tools["mark_entries_reflected"](
            entry_ids=[result1["id"]], delete_logs=False
        )

        result = await tools["list_journal_entries"](unreflected_only=True)

        assert len(result["entries"]) == 1
        assert result["entries"][0]["summary"] == "Entry 2"

    @pytest.mark.asyncio
    async def test_list_filter_by_project(self, test_db: Path) -> None:
        """Test filtering by project name."""
        tools = get_journal_tools(db_path=test_db)

        await tools["store_journal_entry"](
            summary="Entry 1",
            working_directory="/test/project1",
        )
        await tools["store_journal_entry"](
            summary="Entry 2",
            working_directory="/test/project2",
        )

        result = await tools["list_journal_entries"](project_name="project1")

        assert len(result["entries"]) == 1
        assert result["entries"][0]["project_name"] == "project1"


class TestGetJournalEntryTool:
    """Tests for get_journal_entry MCP tool."""

    @pytest.mark.asyncio
    async def test_get_existing(self, test_db: Path) -> None:
        """Test getting an existing entry."""
        tools = get_journal_tools(db_path=test_db)

        store_result = await tools["store_journal_entry"](
            summary="Test summary",
            working_directory="/test/project",
            friction_points=["Issue 1"],
            next_steps=["Step 1"],
        )

        result = await tools["get_journal_entry"](entry_id=store_result["id"])

        assert result["id"] == store_result["id"]
        assert result["summary"] == "Test summary"
        assert result["friction_points"] == ["Issue 1"]
        assert result["next_steps"] == ["Step 1"]
        assert result["reflected_at"] is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_fails(self, test_db: Path) -> None:
        """Test getting nonexistent entry raises error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["get_journal_entry"](
                entry_id="00000000-0000-0000-0000-000000000000"
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"not found", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_invalid_uuid_fails(self, test_db: Path) -> None:
        """Test getting with invalid UUID raises error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["get_journal_entry"](entry_id="invalid")
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Invalid UUID", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_get_with_log(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test getting entry with session log."""
        tools = get_journal_tools(db_path=test_db)

        log_content = '{"type": "test"}\n'
        store_result = await tools["store_journal_entry"](
            summary="Test summary",
            working_directory="/test/project",
            session_log_content=log_content,
        )

        result = await tools["get_journal_entry"](
            entry_id=store_result["id"], include_log=True
        )

        assert result["session_log"] == log_content


class TestMarkEntriesReflectedTool:
    """Tests for mark_entries_reflected MCP tool."""

    @pytest.mark.asyncio
    async def test_mark_single_entry(self, test_db: Path) -> None:
        """Test marking a single entry."""
        tools = get_journal_tools(db_path=test_db)

        store_result = await tools["store_journal_entry"](
            summary="Test summary",
            working_directory="/test/project",
        )

        result = await tools["mark_entries_reflected"](
            entry_ids=[store_result["id"]], delete_logs=False
        )

        assert result["marked_count"] == 1
        assert result["logs_deleted"] == 0

        # Verify entry is marked
        entry = await tools["get_journal_entry"](entry_id=store_result["id"])
        assert entry["reflected_at"] is not None

    @pytest.mark.asyncio
    async def test_mark_empty_list_fails(self, test_db: Path) -> None:
        """Test marking empty list raises error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["mark_entries_reflected"](
                entry_ids=[], delete_logs=False
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"At least one", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_mark_invalid_uuid_fails(self, test_db: Path) -> None:
        """Test marking with invalid UUID raises error."""
        tools = get_journal_tools(db_path=test_db)

        result = await tools["mark_entries_reflected"](
                entry_ids=["invalid"], delete_logs=False
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"Invalid UUID", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_mark_with_memories_created(self, test_db: Path) -> None:
        """Test marking with memories_created count."""
        tools = get_journal_tools(db_path=test_db)

        store_result = await tools["store_journal_entry"](
            summary="Test summary",
            working_directory="/test/project",
        )

        await tools["mark_entries_reflected"](
            entry_ids=[store_result["id"]],
            memories_created=5,
            delete_logs=False,
        )

        entry = await tools["get_journal_entry"](entry_id=store_result["id"])
        assert entry["memories_created"] == 5

    @pytest.mark.asyncio
    async def test_mark_negative_memories_fails(self, test_db: Path) -> None:
        """Test marking with negative memories_created fails."""
        tools = get_journal_tools(db_path=test_db)

        store_result = await tools["store_journal_entry"](
            summary="Test summary",
            working_directory="/test/project",
        )

        result = await tools["mark_entries_reflected"](
                entry_ids=[store_result["id"]],
                memories_created=-1,
                delete_logs=False,
            )
        assert "error" in result
        assert result["error"]["type"] == "validation_error"
        assert re.search(r"memories_created", result["error"]["message"])
    @pytest.mark.asyncio
    async def test_mark_deletes_logs(
        self, test_db: Path, mock_sessions_dir: Path
    ) -> None:
        """Test that marking with delete_logs=True removes log files."""
        tools = get_journal_tools(db_path=test_db)

        log_content = '{"type": "test"}\n'
        store_result = await tools["store_journal_entry"](
            summary="Test summary",
            working_directory="/test/project",
            session_log_content=log_content,
        )

        log_path = Path(store_result["session_log_path"])
        assert log_path.exists()

        result = await tools["mark_entries_reflected"](
            entry_ids=[store_result["id"]], delete_logs=True
        )

        assert result["logs_deleted"] == 1
        assert not log_path.exists()
