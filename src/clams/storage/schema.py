"""SQLite schema definitions for metadata storage."""

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

CREATE_CALL_GRAPH_TABLE = """
CREATE TABLE IF NOT EXISTS call_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_qualified_name TEXT NOT NULL,
    callee_qualified_name TEXT NOT NULL,
    caller_file TEXT NOT NULL,
    callee_file TEXT NOT NULL,
    project TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    UNIQUE(caller_qualified_name, callee_qualified_name, project)
);
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

CREATE_GIT_INDEX_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS git_index_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT NOT NULL UNIQUE,
    last_indexed_sha TEXT,
    last_indexed_at TEXT,
    commit_count INTEGER DEFAULT 0
);
"""

CREATE_INDEXED_FILES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_indexed_files_project
ON indexed_files(project);
"""

CREATE_INDEXED_FILES_MODIFIED_INDEX = """
CREATE INDEX IF NOT EXISTS idx_indexed_files_modified
ON indexed_files(last_modified);
"""

CREATE_CALL_GRAPH_CALLER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_call_graph_caller
ON call_graph(caller_qualified_name, project);
"""

CREATE_CALL_GRAPH_CALLEE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_call_graph_callee
ON call_graph(callee_qualified_name, project);
"""

CREATE_GIT_INDEX_STATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_git_index_state_repo
ON git_index_state(repo_path);
"""

ALL_TABLES = [
    CREATE_INDEXED_FILES_TABLE,
    CREATE_CALL_GRAPH_TABLE,
    CREATE_PROJECTS_TABLE,
    CREATE_GIT_INDEX_STATE_TABLE,
]

ALL_INDEXES = [
    CREATE_INDEXED_FILES_INDEX,
    CREATE_INDEXED_FILES_MODIFIED_INDEX,
    CREATE_CALL_GRAPH_CALLER_INDEX,
    CREATE_CALL_GRAPH_CALLEE_INDEX,
    CREATE_GIT_INDEX_STATE_INDEX,
]
