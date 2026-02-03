"""Tests for the CALM cutover migration script."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

# Import will be deferred for some functions to handle test isolation
from scripts.cutover import (
    CutoverOptions,
    _count_rows,
    _map_worker_status,
    _migrate_journal_entries,
    _remove_old_mcp_server,
    _resolve_worktree_path,
    _table_exists,
    create_backups,
    migrate_clams_data,
    migrate_claws_data,
    run_cutover,
    verify_migration,
)

# ---------------------------------------------------------------------------
# Old-schema DDL (simulates the actual CLAWS database)
# ---------------------------------------------------------------------------

OLD_CLAWS_SCHEMA = """
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    spec_id TEXT,
    title TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'SPEC',
    assigned_specialist TEXT,
    worktree_path TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    blocked_by TEXT,
    notes TEXT,
    task_type TEXT NOT NULL DEFAULT 'feature'
);

CREATE TABLE workers (
    id TEXT PRIMARY KEY,
    specialist_type TEXT NOT NULL,
    current_task_id TEXT,
    status TEXT DEFAULT 'active',
    started_at TIMESTAMP,
    ended_at TIMESTAMP
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    review_num INTEGER,
    reviewer_worker_id TEXT,
    result TEXT NOT NULL,
    issues_found TEXT,
    created_at TIMESTAMP
);

CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    execution_time_seconds REAL,
    failed_tests TEXT,
    run_at TIMESTAMP,
    worktree TEXT,
    commit_sha TEXT,
    total_tests INTEGER,
    errors INTEGER,
    test_files TEXT
);

CREATE TABLE system_counters (
    name TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);

CREATE TABLE phase_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_phase TEXT,
    to_phase TEXT NOT NULL,
    gate_result TEXT,
    gate_details TEXT,
    transitioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE gate_passes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    transition TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    passed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, transition, commit_sha)
);

CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    handoff_content TEXT,
    needs_continuation INTEGER DEFAULT 0,
    resumed_at TEXT
);

CREATE TABLE merge_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    merged_at TIMESTAMP
);

CREATE TABLE violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,
    description TEXT
);
"""

OLD_CLAMS_METADATA_SCHEMA = """
CREATE TABLE indexed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    project TEXT NOT NULL,
    language TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    unit_count INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    UNIQUE(file_path, project)
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    root_path TEXT NOT NULL,
    settings TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_indexed TEXT
);

CREATE TABLE git_index_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL UNIQUE,
    last_indexed_sha TEXT,
    last_indexed_at TEXT,
    commit_count INTEGER DEFAULT 0
);

CREATE TABLE call_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller TEXT NOT NULL,
    callee TEXT NOT NULL,
    project TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _create_mock_claws_db(path: Path) -> None:
    """Create a mock CLAWS database with old schema and sample data."""
    conn = sqlite3.connect(path)
    conn.executescript(OLD_CLAWS_SCHEMA)

    # Tasks
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "SPEC-001",
            None,
            "Test Task",
            "IMPLEMENT",
            "backend",
            ".worktrees/SPEC-001",
            "2025-01-01",
            "2025-01-02",
            None,
            None,
            "feature",
        ),
    )
    conn.execute(
        "INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "SPEC-001-01",
            "SPEC-001",
            "Subtask",
            "DONE",
            "frontend",
            "/absolute/path/wt",
            "2025-01-01",
            "2025-01-03",
            None,
            "some notes",
            "feature",
        ),
    )

    # Workers
    conn.execute(
        "INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?)",
        ("W-001", "backend", "SPEC-001", "active", "2025-01-01", None),
    )
    conn.execute(
        "INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?)",
        ("W-002", "frontend", "SPEC-001-01", "idle", "2025-01-01", "2025-01-02"),
    )
    conn.execute(
        "INSERT INTO workers VALUES (?, ?, ?, ?, ?, ?)",
        ("W-003", "qa", "SPEC-001", "stale", "2025-01-01", None),
    )

    # Reviews
    conn.execute(
        "INSERT INTO reviews (task_id, artifact_type, review_num, "
        "reviewer_worker_id, result, issues_found, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("SPEC-001", "spec", 1, "W-010", "approved", "No issues", "2025-01-01"),
    )
    conn.execute(
        "INSERT INTO reviews (task_id, artifact_type, review_num, "
        "reviewer_worker_id, result, issues_found, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "SPEC-001",
            "code",
            1,
            "W-011",
            "changes_requested",
            "Fix tests",
            "2025-01-02",
        ),
    )

    # Test runs
    conn.execute(
        "INSERT INTO test_runs (task_id, passed, failed, skipped, "
        "execution_time_seconds, failed_tests, run_at, worktree, "
        "commit_sha, total_tests, errors, test_files) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "SPEC-001",
            10,
            2,
            1,
            12.5,
            '["test_foo"]',
            "2025-01-01",
            ".worktrees/SPEC-001",
            "abc123",
            13,
            0,
            '["tests/test_foo.py"]',
        ),
    )

    # Counters
    conn.execute(
        "INSERT INTO system_counters VALUES (?, ?)", ("merge_lock", 0)
    )
    conn.execute(
        "INSERT INTO system_counters VALUES (?, ?)", ("merges_since_e2e", 5)
    )
    conn.execute(
        "INSERT INTO system_counters VALUES (?, ?)", ("merges_since_docs", 3)
    )

    # Phase transitions (including one with NULL from_phase)
    conn.execute(
        "INSERT INTO phase_transitions (task_id, from_phase, to_phase, "
        "gate_result, transitioned_at) VALUES (?, ?, ?, ?, ?)",
        ("SPEC-001", None, "DESIGN", "pass", "2025-01-01"),
    )
    conn.execute(
        "INSERT INTO phase_transitions (task_id, from_phase, to_phase, "
        "gate_result, transitioned_at) VALUES (?, ?, ?, ?, ?)",
        ("SPEC-001", "DESIGN", "IMPLEMENT", "pass", "2025-01-02"),
    )

    # Gate passes
    conn.execute(
        "INSERT INTO gate_passes (task_id, transition, commit_sha, passed_at) "
        "VALUES (?, ?, ?, ?)",
        ("SPEC-001", "SPEC-DESIGN", "def456", "2025-01-01"),
    )

    # Sessions
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
        ("sess-001", "2025-01-01", "Handoff content here", 1, None),
    )

    # merge_log and violations (should NOT be migrated)
    conn.execute(
        "INSERT INTO merge_log (task_id, merged_at) VALUES (?, ?)",
        ("SPEC-001", "2025-01-01"),
    )
    conn.execute(
        "INSERT INTO violations (task_id, description) VALUES (?, ?)",
        ("SPEC-001", "test violation"),
    )

    conn.commit()
    conn.close()


def _create_mock_clams_metadata(path: Path) -> None:
    """Create a mock CLAMS metadata.db with old schema and sample data."""
    conn = sqlite3.connect(path)
    conn.executescript(OLD_CLAMS_METADATA_SCHEMA)

    # Indexed files
    conn.execute(
        "INSERT INTO indexed_files "
        "(file_path, project, language, file_hash, unit_count, "
        "indexed_at, last_modified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("src/main.py", "myproject", "python", "abc123", 5, "2025-01-01", "2025-01-01"),
    )
    conn.execute(
        "INSERT INTO indexed_files "
        "(file_path, project, language, file_hash, unit_count, "
        "indexed_at, last_modified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "src/utils.py",
            "myproject",
            "python",
            "def456",
            3,
            "2025-01-01",
            "2025-01-01",
        ),
    )

    # Projects
    conn.execute(
        "INSERT INTO projects (name, root_path, settings, created_at) "
        "VALUES (?, ?, ?, ?)",
        ("myproject", "/path/to/project", '{"lang": "python"}', "2025-01-01"),
    )

    # Git index state
    conn.execute(
        "INSERT INTO git_index_state (repo_path, last_indexed_sha, "
        "last_indexed_at, commit_count) VALUES (?, ?, ?, ?)",
        ("/path/to/repo", "abc123", "2025-01-01", 50),
    )

    # call_graph (should NOT be migrated)
    conn.execute(
        "INSERT INTO call_graph (caller, callee, project) VALUES (?, ?, ?)",
        ("main", "utils.helper", "myproject"),
    )

    conn.commit()
    conn.close()


@pytest.fixture
def mock_clams_home(tmp_path: Path) -> Path:
    """Create a mock ~/.clams/ with sample data."""
    clams = tmp_path / ".clams"
    clams.mkdir()
    _create_mock_clams_metadata(clams / "metadata.db")

    # Create journal directory with sample JSONL
    journal = clams / "journal"
    journal.mkdir()
    (journal / "session_entries.jsonl").write_text("")

    return clams


@pytest.fixture
def mock_claws_db(tmp_path: Path) -> Path:
    """Create a mock .claude/claws.db with sample data."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    db_path = claude_dir / "claws.db"
    _create_mock_claws_db(db_path)
    return db_path


@pytest.fixture
def mock_calm_home(tmp_path: Path) -> Path:
    """Target directory for CALM."""
    return tmp_path / ".calm"


@pytest.fixture
def cutover_options(
    tmp_path: Path,
    mock_clams_home: Path,
    mock_claws_db: Path,
    mock_calm_home: Path,
) -> CutoverOptions:
    """CutoverOptions pointing to all mock paths."""
    return CutoverOptions(
        dry_run=False,
        skip_server=True,
        clams_home=mock_clams_home,
        calm_home=mock_calm_home,
        claws_db=mock_claws_db,
        repo_root=tmp_path,
        claude_json=tmp_path / ".claude.json",
        settings_json=tmp_path / ".claude" / "settings.json",
    )


def _init_target_db(calm_home: Path) -> Path:
    """Initialize the target database for testing."""
    from calm.db.schema import init_database
    from calm.install.templates import create_directory_structure

    create_directory_structure(calm_home)
    db_path = calm_home / "metadata.db"
    init_database(db_path)
    return db_path


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for helper functions."""

    def test_resolve_worktree_relative(self) -> None:
        """Relative worktree paths are resolved to absolute."""
        repo = Path("/home/user/project")
        result = _resolve_worktree_path(".worktrees/SPEC-001", repo)
        assert result == "/home/user/project/.worktrees/SPEC-001"

    def test_resolve_worktree_absolute(self) -> None:
        """Absolute worktree paths are returned as-is."""
        repo = Path("/home/user/project")
        result = _resolve_worktree_path("/absolute/path/wt", repo)
        assert result == "/absolute/path/wt"

    def test_resolve_worktree_none(self) -> None:
        """None paths remain None."""
        result = _resolve_worktree_path(None, Path("/repo"))
        assert result is None

    def test_map_worker_status_idle(self) -> None:
        """'idle' maps to 'completed'."""
        assert _map_worker_status("idle") == "completed"

    def test_map_worker_status_stale(self) -> None:
        """'stale' maps to 'session_ended'."""
        assert _map_worker_status("stale") == "session_ended"

    def test_map_worker_status_active(self) -> None:
        """'active' passes through."""
        assert _map_worker_status("active") == "active"

    def test_map_worker_status_completed(self) -> None:
        """'completed' passes through."""
        assert _map_worker_status("completed") == "completed"

    def test_remove_old_mcp_server(self) -> None:
        """Removes 'clams' key from mcpServers."""
        config: dict[str, Any] = {
            "mcpServers": {
                "clams": {"command": "old"},
                "other": {"command": "keep"},
            }
        }
        result = _remove_old_mcp_server(config)
        assert "clams" not in result["mcpServers"]
        assert "other" in result["mcpServers"]

    def test_remove_old_mcp_server_no_clams(self) -> None:
        """Handles config without 'clams' key."""
        config: dict[str, Any] = {
            "mcpServers": {"other": {"command": "keep"}}
        }
        result = _remove_old_mcp_server(config)
        assert result["mcpServers"] == {"other": {"command": "keep"}}

    def test_remove_old_mcp_server_no_servers(self) -> None:
        """Handles config without mcpServers."""
        config: dict[str, Any] = {"someKey": "value"}
        result = _remove_old_mcp_server(config)
        assert "someKey" in result

    def test_count_rows_existing_table(self, tmp_path: Path) -> None:
        """Counts rows in an existing table."""
        db = tmp_path / "test.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.execute("INSERT INTO t VALUES (2)")
        conn.commit()
        assert _count_rows(conn, "t") == 2
        conn.close()

    def test_count_rows_missing_table(self, tmp_path: Path) -> None:
        """Returns 0 for missing table."""
        db = tmp_path / "test.db"
        conn = sqlite3.connect(db)
        assert _count_rows(conn, "nonexistent") == 0
        conn.close()

    def test_table_exists(self, tmp_path: Path) -> None:
        """Detects existing and missing tables."""
        db = tmp_path / "test.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE t (id INTEGER)")
        assert _table_exists(conn, "t") is True
        assert _table_exists(conn, "missing") is False
        conn.close()


# ---------------------------------------------------------------------------
# Backup tests
# ---------------------------------------------------------------------------


class TestCreateBackups:
    """Tests for backup creation."""

    def test_creates_backups_for_existing_files(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Backups are created for existing source files."""
        # Create the source config files
        cutover_options.claude_json.write_text("{}")
        cutover_options.settings_json.parent.mkdir(parents=True, exist_ok=True)
        cutover_options.settings_json.write_text("{}")

        ok, msgs = create_backups(cutover_options)
        assert ok

        # Check CLAMS metadata backup
        clams_backup = (
            cutover_options.clams_home / "metadata.db.pre-cutover"
        )
        assert clams_backup.exists()

        # Check claws.db backup
        assert cutover_options.claws_db is not None
        claws_backup = cutover_options.claws_db.parent / (
            cutover_options.claws_db.name + ".pre-cutover"
        )
        assert claws_backup.exists()

    def test_skips_backup_if_pre_cutover_exists(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Does not overwrite existing backup files."""
        # Create existing backup with known content
        clams_backup = (
            cutover_options.clams_home / "metadata.db.pre-cutover"
        )
        clams_backup.write_text("original backup content")

        ok, msgs = create_backups(cutover_options)
        assert ok
        assert clams_backup.read_text() == "original backup content"

    def test_skips_missing_source_files(
        self, tmp_path: Path
    ) -> None:
        """Missing source files are gracefully skipped."""
        options = CutoverOptions(
            clams_home=tmp_path / "nonexistent_clams",
            claws_db=tmp_path / "nonexistent.db",
            claude_json=tmp_path / "nonexistent.json",
            settings_json=tmp_path / "nonexistent_settings.json",
            skip_server=True,
        )
        ok, msgs = create_backups(options)
        assert ok
        assert all("does not exist" in m or "Skipped" in m for m in msgs)

    def test_dry_run_no_files_created(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Dry run does not create backup files."""
        cutover_options.dry_run = True
        ok, msgs = create_backups(cutover_options)
        assert ok

        clams_backup = (
            cutover_options.clams_home / "metadata.db.pre-cutover"
        )
        assert not clams_backup.exists()


# ---------------------------------------------------------------------------
# Infrastructure tests
# ---------------------------------------------------------------------------


class TestEnsureInfrastructure:
    """Tests for CALM infrastructure setup."""

    def test_creates_directory_structure(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Creates expected directories."""
        from scripts.cutover import ensure_calm_infrastructure

        ok, msgs = ensure_calm_infrastructure(cutover_options)
        assert ok
        assert cutover_options.calm_home.exists()
        assert (cutover_options.calm_home / "roles").exists()
        assert (cutover_options.calm_home / "workflows").exists()
        assert (cutover_options.calm_home / "sessions").exists()

    def test_initializes_database_with_all_tables(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Database has all expected tables."""
        from scripts.cutover import ensure_calm_infrastructure

        ok, msgs = ensure_calm_infrastructure(cutover_options)
        assert ok

        db_path = cutover_options.calm_home / "metadata.db"
        conn = sqlite3.connect(db_path)
        for table in (
            "tasks",
            "workers",
            "reviews",
            "test_runs",
            "counters",
            "phase_transitions",
            "gate_passes",
            "sessions",
            "indexed_files",
            "projects",
            "git_index_state",
            "memories",
            "ghap_entries",
            "session_journal",
        ):
            assert _table_exists(conn, table), f"Table {table} missing"
        conn.close()

    def test_idempotent_on_rerun(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Running twice does not fail."""
        from scripts.cutover import ensure_calm_infrastructure

        ok1, _ = ensure_calm_infrastructure(cutover_options)
        ok2, _ = ensure_calm_infrastructure(cutover_options)
        assert ok1
        assert ok2


# ---------------------------------------------------------------------------
# CLAMS data migration tests
# ---------------------------------------------------------------------------


class TestMigrateClamsData:
    """Tests for CLAMS metadata migration."""

    def test_migrates_indexed_files(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """indexed_files rows are migrated."""
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert counts["indexed_files"]["migrated"] == 2

        conn = sqlite3.connect(target_db)
        rows = conn.execute("SELECT * FROM indexed_files").fetchall()
        assert len(rows) == 2
        conn.close()

    def test_migrates_projects(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """projects rows are migrated."""
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert counts["projects"]["migrated"] == 1

    def test_migrates_git_index_state(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """git_index_state rows are migrated."""
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert counts["git_index_state"]["migrated"] == 1

    def test_skips_call_graph(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """call_graph table is NOT migrated."""
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert "call_graph" not in counts

        conn = sqlite3.connect(target_db)
        assert not _table_exists(conn, "call_graph")
        conn.close()

    def test_migrates_journal_jsonl(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """JSONL session entries are migrated."""
        # Write sample JSONL
        journal_path = mock_clams_home / "journal" / "session_entries.jsonl"
        entry = {
            "id": "entry-001",
            "created_at": "2025-01-01",
            "working_directory": "/home/user/project",
            "project_name": "myproject",
            "summary": "Test session",
        }
        journal_path.write_text(json.dumps(entry) + "\n")

        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert counts["session_journal"]["migrated"] == 1

        conn = sqlite3.connect(target_db)
        rows = conn.execute("SELECT * FROM session_journal").fetchall()
        assert len(rows) == 1
        conn.close()

    def test_skips_empty_journal(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """Empty journal file produces zero migrated entries."""
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert counts["session_journal"]["migrated"] == 0

    def test_skips_when_source_missing(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Missing source directory is gracefully skipped."""
        cutover_options.clams_home = Path("/nonexistent/clams")
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert len(counts) == 0

    def test_idempotent_on_rerun(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """Running twice produces same row counts."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_clams_data(cutover_options, target_db)
        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        # Row counts should be stable after second run
        assert counts["indexed_files"]["migrated"] == 2
        assert counts["projects"]["migrated"] == 1


# ---------------------------------------------------------------------------
# CLAWS data migration tests
# ---------------------------------------------------------------------------


class TestMigrateClawsData:
    """Tests for CLAWS orchestration data migration."""

    def test_tasks_column_rename(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """assigned_specialist -> specialist, project_path added."""
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_claws_data(cutover_options, target_db)
        assert ok
        assert counts["tasks"]["migrated"] == 2

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = 'SPEC-001'"
        ).fetchone()
        assert row is not None
        assert row["specialist"] == "backend"
        assert row["project_path"] == str(cutover_options.repo_root)
        conn.close()

    def test_tasks_worktree_path_absolute(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """Relative worktree paths are converted to absolute."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row

        # SPEC-001 had relative path ".worktrees/SPEC-001"
        row = conn.execute(
            "SELECT worktree_path FROM tasks WHERE id = 'SPEC-001'"
        ).fetchone()
        assert row is not None
        assert row["worktree_path"] is not None
        assert row["worktree_path"].startswith("/")

        # SPEC-001-01 had absolute path already
        row2 = conn.execute(
            "SELECT worktree_path FROM tasks WHERE id = 'SPEC-001-01'"
        ).fetchone()
        assert row2 is not None
        assert row2["worktree_path"] == "/absolute/path/wt"

        conn.close()

    def test_workers_column_rename(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """specialist_type -> role, current_task_id -> task_id."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM workers WHERE id = 'W-001'"
        ).fetchone()
        assert row is not None
        assert row["role"] == "backend"
        assert row["task_id"] == "SPEC-001"
        assert row["project_path"] == str(cutover_options.repo_root)
        conn.close()

    def test_workers_status_mapping(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """'idle' -> 'completed', 'stale' -> 'session_ended'."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row

        # W-001: was 'active' -> stays 'active'
        w1 = conn.execute(
            "SELECT status FROM workers WHERE id = 'W-001'"
        ).fetchone()
        assert w1 is not None
        assert w1["status"] == "active"

        # W-002: was 'idle' -> 'completed'
        w2 = conn.execute(
            "SELECT status FROM workers WHERE id = 'W-002'"
        ).fetchone()
        assert w2 is not None
        assert w2["status"] == "completed"

        # W-003: was 'stale' -> 'session_ended'
        w3 = conn.execute(
            "SELECT status FROM workers WHERE id = 'W-003'"
        ).fetchone()
        assert w3 is not None
        assert w3["status"] == "session_ended"

        conn.close()

    def test_reviews_column_rename(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """artifact_type -> review_type, reviewer_worker_id -> worker_id,
        issues_found -> reviewer_notes, review_num dropped."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM reviews ORDER BY id"
        ).fetchall()
        assert len(rows) == 2

        # First review
        r1 = dict(rows[0])
        assert r1["review_type"] == "spec"
        assert r1["worker_id"] == "W-010"
        assert r1["reviewer_notes"] == "No issues"
        # review_num should NOT exist in new schema
        assert "review_num" not in r1

        conn.close()

    def test_test_runs_column_rename(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """execution_time_seconds -> duration_seconds, dropped columns."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM test_runs").fetchone()
        assert row is not None
        r = dict(row)
        assert r["duration_seconds"] == 12.5
        assert r["passed"] == 10
        assert r["failed"] == 2
        # Dropped columns should not be in new schema
        assert "worktree" not in r
        assert "commit_sha" not in r
        assert "total_tests" not in r
        assert "errors" not in r
        assert "test_files" not in r
        conn.close()

    def test_counters_table_rename(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """system_counters -> counters."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT name, value FROM counters ORDER BY name"
        ).fetchall()
        names = {r["name"]: r["value"] for r in rows}
        assert "merge_lock" in names
        assert "merges_since_e2e" in names
        assert names["merges_since_e2e"] == 5
        conn.close()

    def test_counters_max_merge(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """Pre-existing counter: result is MAX(old, new)."""
        target_db = _init_target_db(cutover_options.calm_home)

        # Pre-populate target with a higher counter value
        conn = sqlite3.connect(target_db)
        conn.execute(
            "INSERT OR REPLACE INTO counters (name, value) "
            "VALUES ('merges_since_e2e', 10)"
        )
        conn.commit()
        conn.close()

        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        row = conn.execute(
            "SELECT value FROM counters WHERE name = 'merges_since_e2e'"
        ).fetchone()
        assert row is not None
        # Source has 5, target had 10. MAX(10, 5) = 10
        assert row[0] == 10
        conn.close()

    def test_phase_transitions_null_from_phase(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """NULL from_phase is converted to empty string."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM phase_transitions ORDER BY id"
        ).fetchall()
        assert len(rows) == 2

        # First had NULL from_phase -> ''
        assert rows[0]["from_phase"] == ""
        # Second had 'DESIGN' -> 'DESIGN'
        assert rows[1]["from_phase"] == "DESIGN"
        conn.close()

    def test_gate_passes_direct_copy(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """gate_passes rows are copied directly."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM gate_passes").fetchone()
        assert row is not None
        assert row["task_id"] == "SPEC-001"
        assert row["transition"] == "SPEC-DESIGN"
        assert row["commit_sha"] == "def456"
        conn.close()

    def test_sessions_direct_copy(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """sessions rows are copied directly."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM sessions").fetchone()
        assert row is not None
        assert row["id"] == "sess-001"
        assert row["handoff_content"] == "Handoff content here"
        assert row["needs_continuation"] == 1
        conn.close()

    def test_skips_merge_log(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """merge_log is NOT migrated."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        assert not _table_exists(conn, "merge_log")
        conn.close()

    def test_skips_violations(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """violations is NOT migrated."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        conn = sqlite3.connect(target_db)
        assert not _table_exists(conn, "violations")
        conn.close()

    def test_skips_when_source_missing(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Missing source DB is gracefully skipped."""
        cutover_options.claws_db = Path("/nonexistent/claws.db")
        target_db = _init_target_db(cutover_options.calm_home)
        ok, counts = migrate_claws_data(cutover_options, target_db)
        assert ok
        assert len(counts) == 0

    def test_idempotent_on_rerun(
        self, cutover_options: CutoverOptions, mock_claws_db: Path
    ) -> None:
        """Running twice produces same row counts."""
        target_db = _init_target_db(cutover_options.calm_home)
        migrate_claws_data(cutover_options, target_db)

        # Run again
        ok, counts = migrate_claws_data(cutover_options, target_db)
        assert ok
        assert counts["tasks"]["migrated"] == 2
        assert counts["workers"]["migrated"] == 3
        assert counts["reviews"]["migrated"] == 2


# ---------------------------------------------------------------------------
# Configuration tests
# ---------------------------------------------------------------------------


class TestUpdateConfiguration:
    """Tests for config file updates."""

    def test_removes_old_clams_server(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Old 'clams' MCP server is removed."""
        # Pre-populate config with old clams server
        config: dict[str, Any] = {
            "mcpServers": {
                "clams": {"command": "old-server"},
                "other": {"command": "keep-me"},
            }
        }
        cutover_options.claude_json.write_text(json.dumps(config))

        from scripts.cutover import update_configuration

        ok, msgs = update_configuration(cutover_options)
        assert ok

        result = json.loads(cutover_options.claude_json.read_text())
        assert "clams" not in result.get("mcpServers", {})
        assert "other" in result.get("mcpServers", {})

    def test_registers_calm_server(
        self, cutover_options: CutoverOptions
    ) -> None:
        """CALM MCP server is registered."""
        cutover_options.claude_json.write_text("{}")

        from scripts.cutover import update_configuration

        ok, msgs = update_configuration(cutover_options)
        assert ok

        result = json.loads(cutover_options.claude_json.read_text())
        assert "calm" in result.get("mcpServers", {})

    def test_registers_calm_hooks(
        self, cutover_options: CutoverOptions
    ) -> None:
        """CALM hooks are registered."""
        cutover_options.settings_json.parent.mkdir(parents=True, exist_ok=True)
        cutover_options.settings_json.write_text("{}")

        from scripts.cutover import update_configuration

        ok, msgs = update_configuration(cutover_options)
        assert ok

        result = json.loads(cutover_options.settings_json.read_text())
        hooks = result.get("hooks", {})
        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks

    def test_removes_old_clams_hooks(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Old clams_scripts hooks are removed."""
        cutover_options.settings_json.parent.mkdir(parents=True, exist_ok=True)
        old_settings: dict[str, Any] = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "clams_scripts/hooks/pre_tool.sh",
                            }
                        ],
                    }
                ]
            }
        }
        cutover_options.settings_json.write_text(json.dumps(old_settings))

        from scripts.cutover import update_configuration

        ok, msgs = update_configuration(cutover_options)
        assert ok

        result = json.loads(cutover_options.settings_json.read_text())
        hooks = result.get("hooks", {})
        # Old clams hook should be gone
        for hook_list in hooks.values():
            if isinstance(hook_list, list):
                for h in hook_list:
                    for inner in h.get("hooks", []):
                        assert "clams_scripts" not in inner.get("command", "")

    def test_preserves_other_servers(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Other MCP servers are preserved."""
        config: dict[str, Any] = {
            "mcpServers": {"custom": {"command": "my-server"}}
        }
        cutover_options.claude_json.write_text(json.dumps(config))

        from scripts.cutover import update_configuration

        update_configuration(cutover_options)

        result = json.loads(cutover_options.claude_json.read_text())
        assert "custom" in result["mcpServers"]
        assert "calm" in result["mcpServers"]

    def test_creates_files_if_missing(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Config files are created if they don't exist."""
        # Ensure files don't exist
        assert not cutover_options.claude_json.exists()
        assert not cutover_options.settings_json.exists()

        from scripts.cutover import update_configuration

        ok, msgs = update_configuration(cutover_options)
        assert ok
        assert cutover_options.claude_json.exists()
        assert cutover_options.settings_json.exists()

    def test_dry_run_no_changes(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Dry run reports but does not modify."""
        cutover_options.dry_run = True
        cutover_options.claude_json.write_text('{"mcpServers": {"clams": {}}}')

        from scripts.cutover import update_configuration

        ok, msgs = update_configuration(cutover_options)
        assert ok

        # File should be unchanged
        result = json.loads(cutover_options.claude_json.read_text())
        assert "clams" in result["mcpServers"]


# ---------------------------------------------------------------------------
# Verification tests
# ---------------------------------------------------------------------------


class TestVerifyMigration:
    """Tests for migration verification."""

    def test_reports_matching_counts(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Matching counts produce success."""
        counts: dict[str, dict[str, int]] = {
            "tasks": {"source": 5, "migrated": 5},
            "reviews": {"source": 3, "migrated": 3},
        }
        ok, msgs = verify_migration(cutover_options, counts)
        assert ok
        assert any("Migration complete" in m for m in msgs)

    def test_warns_on_mismatched_counts(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Mismatched counts produce warnings but still succeed."""
        counts: dict[str, dict[str, int]] = {
            "tasks": {"source": 5, "migrated": 3},
        }
        ok, msgs = verify_migration(cutover_options, counts)
        assert ok
        assert any("WARNING" in m for m in msgs)


# ---------------------------------------------------------------------------
# Dry run tests
# ---------------------------------------------------------------------------


class TestDryRun:
    """Tests for dry run mode."""

    def test_reports_counts_without_modifying(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """Dry run queries source DBs for counts but creates nothing."""
        cutover_options.dry_run = True
        target_db = cutover_options.calm_home / "metadata.db"

        ok, counts = migrate_clams_data(cutover_options, target_db)
        assert ok
        assert counts["indexed_files"]["source"] == 2
        assert counts["indexed_files"]["migrated"] == 0

    def test_no_target_database_created(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Dry run does not create target database."""
        cutover_options.dry_run = True
        run_cutover(cutover_options)
        assert not (cutover_options.calm_home / "metadata.db").exists()

    def test_no_config_files_modified(
        self, cutover_options: CutoverOptions
    ) -> None:
        """Dry run does not modify config files."""
        cutover_options.dry_run = True
        cutover_options.claude_json.write_text('{"original": true}')

        run_cutover(cutover_options)

        content = json.loads(cutover_options.claude_json.read_text())
        assert content == {"original": True}


# ---------------------------------------------------------------------------
# Idempotency tests
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Tests for idempotent execution."""

    def test_running_twice_same_result(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """Running cutover twice produces the same row counts in target."""
        # First run
        result1 = run_cutover(cutover_options)
        assert result1.success

        target_db = cutover_options.calm_home / "metadata.db"
        conn = sqlite3.connect(target_db)
        counts_after_first: dict[str, int] = {}
        for table in (
            "tasks",
            "workers",
            "reviews",
            "test_runs",
            "counters",
            "phase_transitions",
            "gate_passes",
            "sessions",
            "indexed_files",
            "projects",
            "git_index_state",
        ):
            counts_after_first[table] = _count_rows(conn, table)
        conn.close()

        # Second run
        result2 = run_cutover(cutover_options)
        assert result2.success

        conn = sqlite3.connect(target_db)
        for table, expected_count in counts_after_first.items():
            actual = _count_rows(conn, table)
            assert actual == expected_count, (
                f"Table {table}: expected {expected_count} after second run, "
                f"got {actual}"
            )
        conn.close()


# ---------------------------------------------------------------------------
# Journal migration tests
# ---------------------------------------------------------------------------


class TestJournalMigration:
    """Tests for JSONL journal entry migration."""

    def test_migrate_journal_entries(self, tmp_path: Path) -> None:
        """JSONL entries are parsed and inserted."""
        from calm.db.schema import init_database

        db_path = tmp_path / "test.db"
        init_database(db_path)

        jsonl_path = tmp_path / "entries.jsonl"
        entries = [
            {
                "id": "e1",
                "created_at": "2025-01-01",
                "working_directory": "/home",
                "summary": "Session 1",
            },
            {
                "id": "e2",
                "created_at": "2025-01-02",
                "working_directory": "/work",
                "summary": "Session 2",
                "friction_points": ["slow tests"],
            },
        ]
        jsonl_path.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n"
        )

        conn = sqlite3.connect(db_path)
        count = _migrate_journal_entries(jsonl_path, conn)
        assert count == 2

        rows = conn.execute("SELECT * FROM session_journal").fetchall()
        assert len(rows) == 2
        conn.close()

    def test_migrate_empty_journal(self, tmp_path: Path) -> None:
        """Empty JSONL file returns 0."""
        from calm.db.schema import init_database

        db_path = tmp_path / "test.db"
        init_database(db_path)

        jsonl_path = tmp_path / "entries.jsonl"
        jsonl_path.write_text("")

        conn = sqlite3.connect(db_path)
        count = _migrate_journal_entries(jsonl_path, conn)
        assert count == 0
        conn.close()

    def test_migrate_missing_journal(self, tmp_path: Path) -> None:
        """Missing JSONL file returns 0."""
        from calm.db.schema import init_database

        db_path = tmp_path / "test.db"
        init_database(db_path)

        jsonl_path = tmp_path / "does_not_exist.jsonl"
        conn = sqlite3.connect(db_path)
        count = _migrate_journal_entries(jsonl_path, conn)
        assert count == 0
        conn.close()


# ---------------------------------------------------------------------------
# Full integration test
# ---------------------------------------------------------------------------


class TestFullCutover:
    """End-to-end integration test."""

    def test_full_cutover_with_sample_data(
        self, cutover_options: CutoverOptions, mock_clams_home: Path
    ) -> None:
        """Full cutover migrates all data and updates config."""
        # Create config files
        config: dict[str, Any] = {
            "mcpServers": {"clams": {"command": "old"}}
        }
        cutover_options.claude_json.write_text(json.dumps(config))
        cutover_options.settings_json.parent.mkdir(parents=True, exist_ok=True)
        cutover_options.settings_json.write_text("{}")

        result = run_cutover(cutover_options)

        assert result.success
        assert len(result.steps_completed) == 8

        # Verify target database
        target_db = cutover_options.calm_home / "metadata.db"
        conn = sqlite3.connect(target_db)
        conn.row_factory = sqlite3.Row

        # Tasks migrated
        assert _count_rows(conn, "tasks") == 2
        # Workers migrated
        assert _count_rows(conn, "workers") == 3
        # Reviews migrated
        assert _count_rows(conn, "reviews") == 2
        # Test runs migrated
        assert _count_rows(conn, "test_runs") == 1
        # Counters migrated
        assert _count_rows(conn, "counters") >= 3
        # Phase transitions migrated
        assert _count_rows(conn, "phase_transitions") == 2
        # Gate passes migrated
        assert _count_rows(conn, "gate_passes") == 1
        # Sessions migrated
        assert _count_rows(conn, "sessions") == 1
        # CLAMS indexed_files migrated
        assert _count_rows(conn, "indexed_files") == 2
        # CLAMS projects migrated
        assert _count_rows(conn, "projects") == 1
        # CLAMS git_index_state migrated
        assert _count_rows(conn, "git_index_state") == 1

        conn.close()

        # Verify config updated
        claude_config = json.loads(cutover_options.claude_json.read_text())
        assert "clams" not in claude_config.get("mcpServers", {})
        assert "calm" in claude_config.get("mcpServers", {})

        settings_config = json.loads(
            cutover_options.settings_json.read_text()
        )
        assert "hooks" in settings_config

        # Verify backups created
        assert cutover_options.claws_db is not None
        claws_backup = cutover_options.claws_db.parent / (
            cutover_options.claws_db.name + ".pre-cutover"
        )
        assert claws_backup.exists()
