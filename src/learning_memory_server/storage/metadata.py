"""SQLite metadata storage for code indexing."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from .schema import ALL_INDEXES, ALL_TABLES


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
        """Add or update an indexed file record.

        Args:
            file_path: Path to the file
            project: Project name
            language: Programming language
            file_hash: Hash of file contents
            unit_count: Number of semantic units indexed
            last_modified: File modification timestamp

        Returns:
            The created or updated IndexedFile
        """
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
        """Get an indexed file record.

        Args:
            file_path: Path to the file
            project: Project name

        Returns:
            The IndexedFile or None if not found
        """
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
        """List indexed files, optionally filtered by project.

        Args:
            project: Optional project filter

        Returns:
            List of IndexedFile records
        """
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

    async def get_stale_files(
        self, project: str, current_files: set[str]
    ) -> list[IndexedFile]:
        """Get indexed files that no longer exist in the project.

        Args:
            project: Project name
            current_files: Set of file paths that currently exist

        Returns:
            List of stale IndexedFile records
        """
        all_files = await self.list_indexed_files(project)
        return [f for f in all_files if f.file_path not in current_files]

    async def delete_indexed_file(self, file_path: str, project: str) -> None:
        """Delete an indexed file record.

        Args:
            file_path: Path to the file
            project: Project name
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        await self._conn.execute(
            "DELETE FROM indexed_files WHERE file_path = ? AND project = ?",
            (file_path, project),
        )
        await self._conn.commit()

    # CallGraph operations

    async def add_call(
        self,
        caller_qualified_name: str,
        callee_qualified_name: str,
        caller_file: str,
        callee_file: str,
        project: str,
    ) -> CallGraphEntry:
        """Add a call graph entry.

        Args:
            caller_qualified_name: Qualified name of the calling function
            callee_qualified_name: Qualified name of the called function
            caller_file: File containing the caller
            callee_file: File containing the callee
            project: Project name

        Returns:
            The created CallGraphEntry
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        indexed_at = datetime.now()

        await self._conn.execute(
            """
            INSERT INTO call_graph
                (caller_qualified_name, callee_qualified_name, caller_file,
                 callee_file, project, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(caller_qualified_name, callee_qualified_name, project)
            DO UPDATE SET
                caller_file=excluded.caller_file,
                callee_file=excluded.callee_file,
                indexed_at=excluded.indexed_at
            """,
            (
                caller_qualified_name,
                callee_qualified_name,
                caller_file,
                callee_file,
                project,
                indexed_at.isoformat(),
            ),
        )
        await self._conn.commit()

        cursor = await self._conn.execute(
            """
            SELECT id, caller_qualified_name, callee_qualified_name, caller_file,
                   callee_file, project, indexed_at
            FROM call_graph
            WHERE caller_qualified_name = ? AND callee_qualified_name = ?
                  AND project = ?
            """,
            (caller_qualified_name, callee_qualified_name, project),
        )
        row = await cursor.fetchone()

        if not row:
            raise RuntimeError("Failed to retrieve call graph entry after insert")

        return CallGraphEntry(
            id=row[0],
            caller_qualified_name=row[1],
            callee_qualified_name=row[2],
            caller_file=row[3],
            callee_file=row[4],
            project=row[5],
            indexed_at=datetime.fromisoformat(row[6]),
        )

    async def get_callers(
        self, callee_qualified_name: str, project: str
    ) -> list[CallGraphEntry]:
        """Get all callers of a function.

        Args:
            callee_qualified_name: Qualified name of the function
            project: Project name

        Returns:
            List of CallGraphEntry records where this function is the callee
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, caller_qualified_name, callee_qualified_name, caller_file,
                   callee_file, project, indexed_at
            FROM call_graph
            WHERE callee_qualified_name = ? AND project = ?
            ORDER BY caller_qualified_name
            """,
            (callee_qualified_name, project),
        )
        rows = await cursor.fetchall()

        return [
            CallGraphEntry(
                id=row[0],
                caller_qualified_name=row[1],
                callee_qualified_name=row[2],
                caller_file=row[3],
                callee_file=row[4],
                project=row[5],
                indexed_at=datetime.fromisoformat(row[6]),
            )
            for row in rows
        ]

    async def get_callees(
        self, caller_qualified_name: str, project: str
    ) -> list[CallGraphEntry]:
        """Get all functions called by a function.

        Args:
            caller_qualified_name: Qualified name of the function
            project: Project name

        Returns:
            List of CallGraphEntry records where this function is the caller
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, caller_qualified_name, callee_qualified_name, caller_file,
                   callee_file, project, indexed_at
            FROM call_graph
            WHERE caller_qualified_name = ? AND project = ?
            ORDER BY callee_qualified_name
            """,
            (caller_qualified_name, project),
        )
        rows = await cursor.fetchall()

        return [
            CallGraphEntry(
                id=row[0],
                caller_qualified_name=row[1],
                callee_qualified_name=row[2],
                caller_file=row[3],
                callee_file=row[4],
                project=row[5],
                indexed_at=datetime.fromisoformat(row[6]),
            )
            for row in rows
        ]

    async def delete_calls_for_file(self, file_path: str, project: str) -> None:
        """Delete all call graph entries for a file.

        Args:
            file_path: Path to the file
            project: Project name
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        await self._conn.execute(
            """
            DELETE FROM call_graph
            WHERE (caller_file = ? OR callee_file = ?) AND project = ?
            """,
            (file_path, file_path, project),
        )
        await self._conn.commit()

    # Project operations

    async def add_project(
        self,
        name: str,
        root_path: str,
        settings: dict[str, Any] | None = None,
    ) -> ProjectConfig:
        """Add or update a project configuration.

        Args:
            name: Project name
            root_path: Root directory path
            settings: Optional settings dictionary

        Returns:
            The created or updated ProjectConfig
        """
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
        """Get a project configuration.

        Args:
            name: Project name

        Returns:
            The ProjectConfig or None if not found
        """
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

    async def list_projects(self) -> list[ProjectConfig]:
        """List all projects.

        Returns:
            List of ProjectConfig records
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        cursor = await self._conn.execute(
            """
            SELECT id, name, root_path, settings, created_at, last_indexed
            FROM projects
            ORDER BY name
            """
        )
        rows = await cursor.fetchall()

        return [
            ProjectConfig(
                id=row[0],
                name=row[1],
                root_path=row[2],
                settings=json.loads(row[3]),
                created_at=datetime.fromisoformat(row[4]),
                last_indexed=datetime.fromisoformat(row[5]) if row[5] else None,
            )
            for row in rows
        ]

    async def update_project_last_indexed(self, name: str) -> None:
        """Update the last_indexed timestamp for a project.

        Args:
            name: Project name
        """
        if not self._conn:
            raise RuntimeError("Database not initialized")

        now = datetime.now()
        await self._conn.execute(
            "UPDATE projects SET last_indexed = ? WHERE name = ?",
            (now.isoformat(), name),
        )
        await self._conn.commit()

    async def delete_project(self, name: str) -> None:
        """Delete a project and all its associated data.

        Args:
            name: Project name
        """
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
        """Get indexing state for a repository.

        Args:
            repo_path: Absolute path to repository root

        Returns:
            GitIndexState or None if not found
        """
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
        """Update indexing state after indexing commits.

        Args:
            repo_path: Absolute path to repository root
            last_sha: SHA of the last indexed commit
            count: Number of commits indexed
        """
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
