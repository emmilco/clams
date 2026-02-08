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
    """GitPython-based implementation of GitReader."""

    def __init__(self, repo_path: str) -> None:
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
        try:
            from typing import Any as _Any
            kwargs: dict[str, _Any] = {"max_count": limit}

            if since:
                kwargs["after"] = since
            if until:
                kwargs["before"] = until
            if path:
                kwargs["paths"] = path

            commits: list[Commit] = []

            try:
                commit_iter = self.repo.iter_commits(**kwargs)
            except ValueError:
                return []

            for git_commit in commit_iter:
                try:
                    sha = git_commit.hexsha
                    if isinstance(git_commit.message, str):
                        message = git_commit.message
                    else:
                        message = git_commit.message.decode('utf-8')
                    author = git_commit.author.name or "Unknown"
                    author_email = (
                        git_commit.author.email or "unknown@example.com"
                    )

                    timestamp = datetime.fromtimestamp(
                        git_commit.committed_date, tz=UTC
                    )

                    files_changed: list[str] = []
                    insertions = 0
                    deletions = 0

                    if git_commit.parents:
                        parent = git_commit.parents[0]
                        diff = parent.diff(git_commit)

                        for diff_item in diff:
                            if diff_item.a_path:
                                files_changed.append(diff_item.a_path)
                            if (
                                diff_item.b_path
                                and diff_item.b_path != diff_item.a_path
                            ):
                                files_changed.append(diff_item.b_path)

                        try:
                            stats = git_commit.stats.total
                            insertions = stats.get("insertions", 0)
                            deletions = stats.get("deletions", 0)
                        except Exception:
                            pass
                    else:
                        try:
                            files_changed = [
                                str(k) for k in git_commit.stats.files.keys()
                            ]
                            stats = git_commit.stats.total
                            insertions = stats.get("insertions", 0)
                            deletions = stats.get("deletions", 0)
                        except Exception:
                            pass

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
                    sha_str: str | None = (
                        git_commit.hexsha
                        if hasattr(git_commit, "hexsha")
                        else None
                    )
                    logger.warning(
                        "commit_parse_failed",
                        sha=sha_str,
                        error=str(e),
                    )
                    continue

            return commits

        except git.GitCommandError as e:
            if "shallow" in str(e).lower():
                logger.warning(
                    "shallow_clone_detected",
                    repo_path=str(self.repo_path),
                    returning_available_history=True,
                )
                return []
            raise GitReaderError(f"Git command failed: {e}") from e

    async def get_blame(self, file_path: str) -> list[BlameEntry]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_blame_sync, file_path)

    def _get_blame_sync(self, file_path: str) -> list[BlameEntry]:
        try:
            full_path = self.repo_path / file_path

            if not full_path.exists():
                raise FileNotInRepoError(f"File not found: {file_path}")

            with open(full_path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    raise BinaryFileError(f"Cannot blame binary file: {file_path}")
                try:
                    chunk.decode("utf-8")
                except UnicodeDecodeError:
                    raise BinaryFileError(f"Cannot blame binary file: {file_path}")

            blame_entries: list[BlameEntry] = []

            try:
                blame = self.repo.blame("HEAD", file_path)
            except git.GitCommandError as e:
                if "not found" in str(e).lower():
                    raise FileNotInRepoError(f"File not tracked: {file_path}") from e
                raise GitReaderError(f"Git blame failed: {e}") from e

            line_num = 1
            for blame_commit, blame_lines in blame:  # type: ignore[misc, union-attr]
                str_lines = [
                    line if isinstance(line, str) else line.decode('utf-8')
                    for line in blame_lines  # type: ignore[union-attr]
                ]
                content = "".join(str_lines)
                line_count = len(str_lines)

                timestamp = datetime.fromtimestamp(
                    blame_commit.committed_date, tz=UTC  # type: ignore[union-attr]
                )

                author_name = blame_commit.author.name or "Unknown"  # type: ignore[union-attr]
                author_email_str = (
                    blame_commit.author.email  # type: ignore[union-attr]
                    or "unknown@example.com"
                )

                blame_entries.append(
                    BlameEntry(
                        sha=blame_commit.hexsha,  # type: ignore[union-attr]
                        author=author_name,
                        author_email=author_email_str,
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
        return await self.get_commits(path=file_path, limit=limit)

    def get_repo_root(self) -> str:
        return str(self.repo_path)

    async def get_head_sha(self) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_head_sha_sync)

    def _get_head_sha_sync(self) -> str:
        try:
            return self.repo.head.commit.hexsha
        except ValueError as e:
            raise GitReaderError("Cannot resolve HEAD (empty repository?)") from e
