"""GitPython-based implementation of GitReader."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import git
import structlog

from .base import (
    BinaryFileError,
    BlameEntry,
    Commit,
    FileNotInRepoError,
    GitReader,
    GitReaderError,
    RepositoryNotFoundError,
)

logger = structlog.get_logger(__name__)


class GitPythonReader(GitReader):
    """GitPython-based implementation of GitReader.

    All GitPython calls are wrapped with asyncio.run_in_executor since
    GitPython is a synchronous library.
    """

    def __init__(self, repo_path: str) -> None:
        """Initialize reader with repository path.

        Args:
            repo_path: Absolute path to repository root (containing .git/)

        Raises:
            RepositoryNotFoundError: If path is not a valid git repository
        """
        try:
            self.repo = git.Repo(repo_path)
            self.repo_path = Path(repo_path).resolve()
        except (git.InvalidGitRepositoryError, git.NoSuchPathError) as e:
            raise RepositoryNotFoundError(
                f"Not a valid git repository: {repo_path}"
            ) from e

    async def get_commits(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        path: str | None = None,
        limit: int = 100,
    ) -> list[Commit]:
        """Get commits, optionally filtered by date range and path."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._get_commits_sync, since, until, path, limit
        )

    def _get_commits_sync(
        self,
        since: datetime | None,
        until: datetime | None,
        path: str | None,
        limit: int,
    ) -> list[Commit]:
        """Synchronous implementation of get_commits."""
        try:
            # Build iter_commits arguments
            kwargs: dict[str, object] = {"max_count": limit}

            # Date filtering
            if since:
                kwargs["after"] = since
            if until:
                kwargs["before"] = until

            # Path filtering
            if path:
                kwargs["paths"] = path

            commits: list[Commit] = []

            for git_commit in self.repo.iter_commits(**kwargs):
                try:
                    # Extract commit data
                    sha = git_commit.hexsha
                    message = git_commit.message
                    author = git_commit.author.name
                    author_email = git_commit.author.email

                    # Convert timestamp to UTC timezone-aware datetime
                    timestamp = datetime.fromtimestamp(
                        git_commit.committed_date, tz=UTC
                    )

                    # Get files changed (diff against first parent for merges)
                    files_changed: list[str] = []
                    insertions = 0
                    deletions = 0

                    if git_commit.parents:
                        # Has parents - compute diff
                        parent = git_commit.parents[0]
                        diff = parent.diff(git_commit)

                        for diff_item in diff:
                            # Track all changed files
                            if diff_item.a_path:
                                files_changed.append(diff_item.a_path)
                            if (
                                diff_item.b_path
                                and diff_item.b_path != diff_item.a_path
                            ):
                                files_changed.append(diff_item.b_path)

                        # Get stats for insertions/deletions
                        try:
                            stats = git_commit.stats.total
                            insertions = stats.get("insertions", 0)
                            deletions = stats.get("deletions", 0)
                        except Exception:
                            # Stats unavailable, use 0
                            pass
                    else:
                        # Initial commit - all files are new
                        try:
                            files_changed = list(git_commit.stats.files.keys())
                            stats = git_commit.stats.total
                            insertions = stats.get("insertions", 0)
                            deletions = stats.get("deletions", 0)
                        except Exception:
                            pass

                    # Remove duplicates and sort
                    files_changed = sorted(set(files_changed))

                    commits.append(
                        Commit(
                            sha=sha,
                            message=message,
                            author=author,
                            author_email=author_email,
                            timestamp=timestamp,
                            files_changed=files_changed,
                            insertions=insertions,
                            deletions=deletions,
                        )
                    )

                except Exception as e:
                    sha = (
                        git_commit.hexsha
                        if hasattr(git_commit, "hexsha")
                        else None
                    )
                    logger.warning(
                        "commit_parse_failed",
                        sha=sha,
                        error=str(e),
                    )
                    continue

            return commits

        except git.GitCommandError as e:
            # Check for shallow clone
            if "shallow" in str(e).lower():
                logger.warning(
                    "shallow_clone_detected",
                    repo_path=str(self.repo_path),
                    returning_available_history=True,
                )
                # Return empty list for shallow clones with incomplete history
                return []
            raise GitReaderError(f"Git command failed: {e}") from e

    async def get_blame(self, file_path: str) -> list[BlameEntry]:
        """Get blame information for a file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_blame_sync, file_path)

    def _get_blame_sync(self, file_path: str) -> list[BlameEntry]:
        """Synchronous implementation of get_blame."""
        try:
            # Check if file exists and is tracked
            full_path = self.repo_path / file_path

            if not full_path.exists():
                raise FileNotInRepoError(f"File not found: {file_path}")

            # Check if file is binary
            try:
                with open(full_path, encoding="utf-8") as f:
                    f.read()
            except UnicodeDecodeError:
                raise BinaryFileError(f"Cannot blame binary file: {file_path}")

            # Get blame from git
            blame_entries: list[BlameEntry] = []

            try:
                blame = self.repo.blame("HEAD", file_path)
            except git.GitCommandError as e:
                if "not found" in str(e).lower():
                    raise FileNotInRepoError(f"File not tracked: {file_path}") from e
                raise GitReaderError(f"Git blame failed: {e}") from e

            line_num = 1
            for commit, lines in blame:
                content = "".join(lines)
                line_count = len(lines)

                timestamp = datetime.fromtimestamp(
                    commit.committed_date, tz=UTC
                )

                blame_entries.append(
                    BlameEntry(
                        sha=commit.hexsha,
                        author=commit.author.name,
                        author_email=commit.author.email,
                        timestamp=timestamp,
                        line_start=line_num,
                        line_end=line_num + line_count - 1,
                        content=content,
                    )
                )

                line_num += line_count

            return blame_entries

        except (FileNotInRepoError, BinaryFileError):
            raise
        except Exception as e:
            raise GitReaderError(f"Blame operation failed: {e}") from e

    async def get_file_history(
        self,
        file_path: str,
        limit: int = 100,
    ) -> list[Commit]:
        """Get commit history for a specific file."""
        # Reuse get_commits with path filter
        return await self.get_commits(path=file_path, limit=limit)

    def get_repo_root(self) -> str:
        """Get the absolute repository root path."""
        return str(self.repo_path)

    async def get_head_sha(self) -> str:
        """Get the current HEAD commit SHA."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_head_sha_sync)

    def _get_head_sha_sync(self) -> str:
        """Synchronous implementation of get_head_sha."""
        try:
            return self.repo.head.commit.hexsha
        except ValueError as e:
            # Empty repository
            raise GitReaderError("Cannot resolve HEAD (empty repository?)") from e
