"""SQLite schema definitions for CALM metadata storage.

This module defines all database tables for the unified CALM system,
including memory, session, GHAP, and orchestration tables.
"""

import sqlite3
from pathlib import Path

# ===================
# MEMORY TABLES
# ===================

CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN (
        'preference', 'fact', 'event', 'workflow', 'context', 'error', 'decision'
    )),
    importance REAL DEFAULT 0.5 CHECK (importance >= 0.0 AND importance <= 1.0),
    tags TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    embedding_id TEXT  -- Reference to vector store
);
"""

CREATE_MEMORIES_CATEGORY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
"""

CREATE_MEMORIES_IMPORTANCE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
"""

# ===================
# SESSION TABLES
# ===================

CREATE_SESSION_JOURNAL_TABLE = """
CREATE TABLE IF NOT EXISTS session_journal (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    working_directory TEXT NOT NULL,
    project_name TEXT,  -- Last component of path
    session_log_path TEXT,  -- Path to copied log in ~/.calm/sessions/
    summary TEXT NOT NULL,
    friction_points TEXT,  -- JSON array
    next_steps TEXT,  -- JSON array
    reflected_at TEXT,  -- NULL if unreflected
    memories_created INTEGER DEFAULT 0
);
"""

CREATE_JOURNAL_REFLECTED_INDEX = """
CREATE INDEX IF NOT EXISTS idx_journal_reflected ON session_journal(reflected_at);
"""

CREATE_JOURNAL_PROJECT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_journal_project ON session_journal(project_name);
"""

CREATE_JOURNAL_DIRECTORY_INDEX = """
CREATE INDEX IF NOT EXISTS idx_journal_directory ON session_journal(working_directory);
"""

# Sessions table for orchestration handoffs
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    handoff_content TEXT,
    needs_continuation INTEGER DEFAULT 0,
    resumed_at TEXT
);
"""

CREATE_SESSIONS_PENDING_INDEX = """
CREATE INDEX IF NOT EXISTS idx_sessions_pending
    ON sessions(needs_continuation, resumed_at);
"""

# ===================
# GHAP TABLES
# ===================

CREATE_GHAP_ENTRIES_TABLE = """
CREATE TABLE IF NOT EXISTS ghap_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    domain TEXT NOT NULL,
    strategy TEXT NOT NULL,
    goal TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    action TEXT NOT NULL,
    prediction TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN (
        'active', 'confirmed', 'falsified', 'abandoned'
    )),
    result TEXT,
    surprise TEXT,
    root_cause_category TEXT,
    root_cause_description TEXT,
    lesson_what_worked TEXT,
    lesson_takeaway TEXT,
    iteration_count INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    project_path TEXT
);
"""

CREATE_GHAP_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ghap_status ON ghap_entries(status);
"""

CREATE_GHAP_PROJECT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_ghap_project ON ghap_entries(project_path);
"""

# ===================
# ORCHESTRATION TABLES
# ===================

CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    spec_id TEXT,  -- Parent spec if this is a subtask
    task_type TEXT DEFAULT 'feature' CHECK (task_type IN ('feature', 'bug')),
    phase TEXT NOT NULL,
    specialist TEXT,
    notes TEXT,
    blocked_by TEXT,  -- JSON array of task IDs
    worktree_path TEXT,
    project_path TEXT NOT NULL,  -- Associates task with project
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_TASKS_PHASE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_tasks_phase ON tasks(phase);
"""

CREATE_TASKS_PROJECT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_path);
"""

CREATE_TASKS_TYPE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_tasks_type ON tasks(task_type);
"""

CREATE_WORKERS_TABLE = """
CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN (
        'active', 'completed', 'failed', 'session_ended'
    )),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    project_path TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""

CREATE_WORKERS_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
"""

CREATE_WORKERS_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_workers_task ON workers(task_id);
"""

CREATE_REVIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    review_type TEXT NOT NULL CHECK (review_type IN (
        'spec', 'proposal', 'code', 'bugfix'
    )),
    result TEXT NOT NULL CHECK (result IN ('approved', 'changes_requested')),
    worker_id TEXT,
    reviewer_notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""

CREATE_REVIEWS_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reviews_task ON reviews(task_id);
"""

CREATE_REVIEWS_TYPE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_reviews_type ON reviews(review_type);
"""

CREATE_TEST_RUNS_TABLE = """
CREATE TABLE IF NOT EXISTS test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    skipped INTEGER DEFAULT 0,
    duration_seconds REAL,
    failed_tests TEXT,  -- JSON array
    run_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""

CREATE_COUNTERS_TABLE = """
CREATE TABLE IF NOT EXISTS counters (
    name TEXT PRIMARY KEY,
    value INTEGER DEFAULT 0
);
"""

# Initial counter values
INIT_COUNTERS = """
INSERT OR IGNORE INTO counters (name, value) VALUES ('merge_lock', 0);
INSERT OR IGNORE INTO counters (name, value) VALUES ('merges_since_e2e', 0);
INSERT OR IGNORE INTO counters (name, value) VALUES ('merges_since_docs', 0);
"""

# Phase transitions table for history tracking
CREATE_PHASE_TRANSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS phase_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    from_phase TEXT NOT NULL,
    to_phase TEXT NOT NULL,
    gate_result TEXT,
    gate_details TEXT,
    transitioned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
"""

CREATE_PHASE_TRANSITIONS_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_transitions_task ON phase_transitions(task_id);
"""

# Gate passes table for commit-anchored verification
CREATE_GATE_PASSES_TABLE = """
CREATE TABLE IF NOT EXISTS gate_passes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    transition TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    passed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_id, transition, commit_sha)
);
"""

CREATE_GATE_PASSES_TASK_INDEX = """
CREATE INDEX IF NOT EXISTS idx_gate_passes_task ON gate_passes(task_id, transition);
"""

# ===================
# CODE INDEXING TABLES (from clams)
# ===================

CREATE_INDEXED_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS indexed_files (
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
"""

CREATE_INDEXED_FILES_PROJECT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_indexed_files_project ON indexed_files(project);
"""

CREATE_INDEXED_FILES_MODIFIED_INDEX = """
CREATE INDEX IF NOT EXISTS idx_indexed_files_modified ON indexed_files(last_modified);
"""

CREATE_GIT_INDEX_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS git_index_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL UNIQUE,
    last_indexed_sha TEXT,
    last_indexed_at TEXT,
    commit_count INTEGER DEFAULT 0
);
"""

CREATE_GIT_INDEX_STATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_git_index_state_repo ON git_index_state(repo_path);
"""

CREATE_PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    root_path TEXT NOT NULL,
    settings TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_indexed TEXT
);
"""

# ===================
# ALL TABLES AND INDEXES
# ===================

ALL_TABLES = [
    # Memory tables
    CREATE_MEMORIES_TABLE,
    # Session tables
    CREATE_SESSION_JOURNAL_TABLE,
    CREATE_SESSIONS_TABLE,
    # GHAP tables
    CREATE_GHAP_ENTRIES_TABLE,
    # Orchestration tables
    CREATE_TASKS_TABLE,
    CREATE_WORKERS_TABLE,
    CREATE_REVIEWS_TABLE,
    CREATE_TEST_RUNS_TABLE,
    CREATE_COUNTERS_TABLE,
    CREATE_PHASE_TRANSITIONS_TABLE,
    CREATE_GATE_PASSES_TABLE,
    # Code indexing tables
    CREATE_INDEXED_FILES_TABLE,
    CREATE_GIT_INDEX_STATE_TABLE,
    CREATE_PROJECTS_TABLE,
]

ALL_INDEXES = [
    # Memory indexes
    CREATE_MEMORIES_CATEGORY_INDEX,
    CREATE_MEMORIES_IMPORTANCE_INDEX,
    # Session indexes
    CREATE_JOURNAL_REFLECTED_INDEX,
    CREATE_JOURNAL_PROJECT_INDEX,
    CREATE_JOURNAL_DIRECTORY_INDEX,
    CREATE_SESSIONS_PENDING_INDEX,
    # GHAP indexes
    CREATE_GHAP_STATUS_INDEX,
    CREATE_GHAP_PROJECT_INDEX,
    # Orchestration indexes
    CREATE_TASKS_PHASE_INDEX,
    CREATE_TASKS_PROJECT_INDEX,
    CREATE_TASKS_TYPE_INDEX,
    CREATE_WORKERS_STATUS_INDEX,
    CREATE_WORKERS_TASK_INDEX,
    CREATE_REVIEWS_TASK_INDEX,
    CREATE_REVIEWS_TYPE_INDEX,
    CREATE_PHASE_TRANSITIONS_TASK_INDEX,
    CREATE_GATE_PASSES_TASK_INDEX,
    # Code indexing indexes
    CREATE_INDEXED_FILES_PROJECT_INDEX,
    CREATE_INDEXED_FILES_MODIFIED_INDEX,
    CREATE_GIT_INDEX_STATE_INDEX,
]


def init_database(db_path: Path) -> None:
    """Initialize the CALM database with all tables and indexes.

    This function is idempotent - safe to call multiple times.

    Args:
        db_path: Path to the SQLite database file
    """
    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON;")

        # Create all tables
        for table_sql in ALL_TABLES:
            cursor.execute(table_sql)

        # Create all indexes
        for index_sql in ALL_INDEXES:
            cursor.execute(index_sql)

        # Initialize counters
        for line in INIT_COUNTERS.strip().split(";"):
            line = line.strip()
            if line:
                cursor.execute(line + ";")

        conn.commit()
    finally:
        conn.close()
