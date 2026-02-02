"""SQLite metadata storage for code indexing."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

# SQL Schema for indexed files
INDEXED_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS indexed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    project TEXT NOT NULL,
    language TEXT,
    file_hash TEXT NOT NULL,
    unit_count INTEGER DEFAULT 0,
    indexed_at TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    UNIQUE(file_path, project)
);
"""

INDEXED_FILES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_indexed_files_project
    ON indexed_files(project);
"""

# SQL Schema for call graph
CALL_GRAPH_TABLE = """
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

CALL_GRAPH_INDEX_CALLER = """
CREATE INDEX IF NOT EXISTS idx_call_graph_caller
    ON call_graph(caller_qualified_name, project);
"""

CALL_GRAPH_INDEX_CALLEE = """
CREATE INDEX IF NOT EXISTS idx_call_graph_callee
    ON call_graph(callee_qualified_name, project);
"""

# SQL Schema for projects
PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    root_path TEXT NOT NULL,
    settings TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    last_indexed TEXT
);
"""

# SQL Schema for git index state
GIT_INDEX_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS git_index_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_path TEXT UNIQUE NOT NULL,
    last_indexed_sha TEXT,
    last_indexed_at TEXT,
    commit_count INTEGER DEFAULT 0
);
"""

ALL_TABLES = [
    INDEXED_FILES_TABLE,
    CALL_GRAPH_TABLE,
    PROJECTS_TABLE,
    GIT_INDEX_STATE_TABLE,
]

ALL_INDEXES = [
    INDEXED_FILES_INDEX,
    CALL_GRAPH_INDEX_CALLER,
    CALL_GRAPH_INDEX_CALLEE,
]


@dataclass
class IndexedFile:
    """Represents an indexed source file."""

    id: int | None
    file_path: str
    project: str
    language: str
    file_hash: str
    unit_count: int
    indexed_at: datetime
    last_modified: datetime


@dataclass
class CallGraphEntry:
    """Represents a call relationship between functions."""

    id: int | None
    caller_qualified_name: str
    callee_qualified_name: str
    caller_file: str
    callee_file: str
    project: str
    indexed_at: datetime


@dataclass
class ProjectConfig:
    """Represents project configuration and settings."""

    id: int | None
    name: str
    root_path: str
    settings: dict[str, Any]
    created_at: datetime
    last_indexed: datetime | None


@dataclass
class GitIndexState:
    """Represents git indexing state for a repository."""

    id: int | None
    repo_path: str
    last_indexed_sha: str | None
    last_indexed_at: datetime | None
    commit_count: int


class MetadataStore:
    """Async SQLite metadata storage with WAL mode for concurrent access."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the metadata store.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path).expanduser()
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Initialize the database schema and enable WAL mode."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(str(self.db_path))

        # Enable WAL mode for concurrent access
        await self._conn.execute("PRAGMA journal_mode=WAL;")

        # Create tables
        for table_sql in ALL_TABLES:
            await self._conn.execute(table_sql)

        # Create indexes
        for index_sql in ALL_INDEXES:
            await self._conn.execute(index_sql)

        await self._conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    # IndexedFile operations

    async def add_indexed_file(
        self,
        file_path: str,
        project: str,
        language: str,
        file_hash: str,
        unit_count: int,
        last_modified: datetime,
    ) -> IndexedFile:
        """Add or update an indexed file record."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        indexed_at = datetime.now()

        await self._conn.execute(
            """
            INSERT INTO indexed_files
                (file_path, project, language, file_hash, unit_count,
                 indexed_at, last_modified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path, project) DO UPDATE SET
                language=excluded.language,
                file_hash=excluded.file_hash,
                unit_count=excluded.unit_count,
                indexed_at=excluded.indexed_at,
                last_modified=excluded.last_modified
            """,
            (
                file_path,
                project,
                language,
                file_hash,
                unit_count,
                indexed_at.isoformat(),
                last_modified.isoformat(),
            ),
        )
        await self._conn.commit()

        cursor = await self._conn.execute(
            """
            SELECT id, file_path, project, language, file_hash, unit_count,
                   indexed_at, last_modified
            FROM indexed_files
            WHERE file_path = ? AND project = ?
            """,
            (file_path, project),
        )
        row = await cursor.fetchone()

        if not row:
            raise RuntimeError("Failed to retrieve indexed file after insert")

        return IndexedFile(
            id=row[0],
            file_path=row[1],
            project=row[2],
            language=row[3],
            file_hash=row[4],
            unit_count=row[5],
            indexed_at=datetime.fromisoformat(row[6]),
            last_modified=datetime.fromisoformat(row[7]),
        )

    async def get_indexed_file(
        self, file_path: str, project: str
    ) -> IndexedFile | None:
        """Get an indexed file record."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, file_path, project, language, file_hash, unit_count,
                   indexed_at, last_modified
            FROM indexed_files
            WHERE file_path = ? AND project = ?
            """,
            (file_path, project),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return IndexedFile(
            id=row[0],
            file_path=row[1],
            project=row[2],
            language=row[3],
            file_hash=row[4],
            unit_count=row[5],
            indexed_at=datetime.fromisoformat(row[6]),
            last_modified=datetime.fromisoformat(row[7]),
        )

    async def list_indexed_files(self, project: str | None = None) -> list[IndexedFile]:
        """List indexed files, optionally filtered by project."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        if project:
            cursor = await self._conn.execute(
                """
                SELECT id, file_path, project, language, file_hash, unit_count,
                       indexed_at, last_modified
                FROM indexed_files
                WHERE project = ?
                ORDER BY file_path
                """,
                (project,),
            )
        else:
            cursor = await self._conn.execute(
                """
                SELECT id, file_path, project, language, file_hash, unit_count,
                       indexed_at, last_modified
                FROM indexed_files
                ORDER BY file_path
                """
            )

        rows = await cursor.fetchall()

        return [
            IndexedFile(
                id=row[0],
                file_path=row[1],
                project=row[2],
                language=row[3],
                file_hash=row[4],
                unit_count=row[5],
                indexed_at=datetime.fromisoformat(row[6]),
                last_modified=datetime.fromisoformat(row[7]),
            )
            for row in rows
        ]

    async def delete_indexed_file(self, file_path: str, project: str) -> None:
        """Delete an indexed file record."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        await self._conn.execute(
            "DELETE FROM indexed_files WHERE file_path = ? AND project = ?",
            (file_path, project),
        )
        await self._conn.commit()

    async def delete_project(self, name: str) -> None:
        """Delete a project and all its associated data."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        # Delete in order: call_graph, indexed_files, projects
        await self._conn.execute(
            "DELETE FROM call_graph WHERE project = ?", (name,)
        )
        await self._conn.execute(
            "DELETE FROM indexed_files WHERE project = ?", (name,)
        )
        await self._conn.execute("DELETE FROM projects WHERE name = ?", (name,))
        await self._conn.commit()

    # Git index state operations

    async def get_git_index_state(self, repo_path: str) -> GitIndexState | None:
        """Get indexing state for a repository."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, repo_path, last_indexed_sha, last_indexed_at, commit_count
            FROM git_index_state
            WHERE repo_path = ?
            """,
            (repo_path,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return GitIndexState(
            id=row[0],
            repo_path=row[1],
            last_indexed_sha=row[2],
            last_indexed_at=datetime.fromisoformat(row[3]) if row[3] else None,
            commit_count=row[4],
        )

    async def update_git_index_state(
        self, repo_path: str, last_sha: str, count: int
    ) -> None:
        """Update indexing state after indexing commits."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        now = datetime.now()

        await self._conn.execute(
            """
            INSERT INTO git_index_state (
                repo_path, last_indexed_sha, last_indexed_at, commit_count
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(repo_path) DO UPDATE SET
                last_indexed_sha=excluded.last_indexed_sha,
                last_indexed_at=excluded.last_indexed_at,
                commit_count=commit_count + excluded.commit_count
            """,
            (repo_path, last_sha, now.isoformat(), count),
        )
        await self._conn.commit()

    async def get_indexed_commits(self) -> set[str]:
        """Get set of all indexed commit SHAs."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            "SELECT last_indexed_sha FROM git_index_state "
            "WHERE last_indexed_sha IS NOT NULL"
        )
        rows = await cursor.fetchall()
        return {row[0] for row in rows}

    # Project operations

    async def add_project(
        self,
        name: str,
        root_path: str,
        settings: dict[str, Any] | None = None,
    ) -> ProjectConfig:
        """Add or update a project configuration."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        if settings is None:
            settings = {}

        created_at = datetime.now()
        settings_json = json.dumps(settings)

        await self._conn.execute(
            """
            INSERT INTO projects (name, root_path, settings, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                root_path=excluded.root_path,
                settings=excluded.settings
            """,
            (name, root_path, settings_json, created_at.isoformat()),
        )
        await self._conn.commit()

        cursor = await self._conn.execute(
            """
            SELECT id, name, root_path, settings, created_at, last_indexed
            FROM projects
            WHERE name = ?
            """,
            (name,),
        )
        row = await cursor.fetchone()

        if not row:
            raise RuntimeError("Failed to retrieve project after insert")

        return ProjectConfig(
            id=row[0],
            name=row[1],
            root_path=row[2],
            settings=json.loads(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            last_indexed=datetime.fromisoformat(row[5]) if row[5] else None,
        )

    async def get_project(self, name: str) -> ProjectConfig | None:
        """Get a project configuration."""
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, name, root_path, settings, created_at, last_indexed
            FROM projects
            WHERE name = ?
            """,
            (name,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return ProjectConfig(
            id=row[0],
            name=row[1],
            root_path=row[2],
            settings=json.loads(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            last_indexed=datetime.fromisoformat(row[5]) if row[5] else None,
        )
