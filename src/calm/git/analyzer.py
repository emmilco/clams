"""Git history analysis and indexing."""

import asyncio
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import structlog

from calm.embedding.base import EmbeddingService
from calm.storage.base import VectorStore
from calm.storage.metadata import MetadataStore

from .base import (
    AuthorStats,
    BinaryFileError,
    BlameSearchResult,
    ChurnRecord,
    Commit,
    CommitSearchResult,
    FileNotInRepoError,
    GitAnalyzerError,
    GitReader,
    IndexingError,
    IndexingStats,
)

logger = structlog.get_logger(__name__)


class GitAnalyzer:
    """Analyzes and indexes git history for semantic search and metrics."""

    def __init__(
        self,
        git_reader: GitReader,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        metadata_store: MetadataStore,
    ) -> None:
        self.git_reader = git_reader
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_store = metadata_store
        self._collection_ensured = False

    async def _ensure_commits_collection(self) -> None:
        """Ensure commits collection exists."""
        if self._collection_ensured:
            return

        try:
            await self.vector_store.create_collection(
                name="commits",
                dimension=self.embedding_service.dimension,
                distance="cosine",
            )
            logger.info("collection_created", name="commits")
        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "409" in str(e):
                logger.debug("collection_exists", name="commits")
            else:
                raise

        self._collection_ensured = True

    async def index_commits(
        self,
        since: datetime | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> IndexingStats:
        """Index commits for semantic search (5-year limit, incremental)."""
        await self._ensure_commits_collection()

        stats = IndexingStats(commits_indexed=0, commits_skipped=0)
        start_time = time.time()

        repo_path = self.git_reader.get_repo_root()
        state = await self.metadata_store.get_git_index_state(repo_path)

        if force or not state or not state.last_indexed_sha:
            logger.info(
                "full_index_starting",
                repo_path=repo_path,
                force=force,
                has_state=state is not None,
            )
            commits = await self._get_commits_to_index(since, limit)
        else:
            try:
                head_sha = await self.git_reader.get_head_sha()
            except Exception as e:
                logger.error("failed_to_get_head_sha", error=str(e))
                stats.errors.append(
                    IndexingError(
                        sha=None,
                        error_type=type(e).__name__,
                        message=f"Failed to get HEAD SHA: {e}",
                    )
                )
                stats.duration_ms = int((time.time() - start_time) * 1000)
                return stats

            if head_sha == state.last_indexed_sha:
                logger.info("index_already_up_to_date", repo_path=repo_path)
                stats.duration_ms = int((time.time() - start_time) * 1000)
                return stats

            all_commits = await self.git_reader.get_commits(limit=10000)
            new_commits = []

            for commit in all_commits:
                if commit.sha == state.last_indexed_sha:
                    break
                new_commits.append(commit)
            else:
                logger.warning(
                    "last_indexed_sha_not_found",
                    last_sha=state.last_indexed_sha,
                    head_sha=head_sha,
                    action="full_reindex",
                )
                commits = await self._get_commits_to_index(since, limit)
                stats = await self._index_commit_batch(commits, stats)
                stats.duration_ms = int((time.time() - start_time) * 1000)
                return stats

            logger.info(
                "incremental_index_starting",
                repo_path=repo_path,
                new_commits=len(new_commits),
            )
            commits = new_commits

        stats = await self._index_commit_batch(commits, stats)
        stats.duration_ms = int((time.time() - start_time) * 1000)

        return stats

    async def _get_commits_to_index(
        self, since: datetime | None, limit: int | None
    ) -> list[Commit]:
        five_years_ago = datetime.now(UTC) - timedelta(days=5 * 365)
        effective_since = max(since, five_years_ago) if since else five_years_ago
        effective_limit = limit if limit is not None else 100000
        return await self.git_reader.get_commits(
            since=effective_since, limit=effective_limit
        )

    async def _index_commit_batch(
        self, commits: list[Commit], stats: IndexingStats
    ) -> IndexingStats:
        if not commits:
            return stats

        repo_path = self.git_reader.get_repo_root()

        batch_size = 75
        for i in range(0, len(commits), batch_size):
            batch = commits[i : i + batch_size]

            try:
                texts = [self._build_embedding_text(commit) for commit in batch]
                vectors = await self.embedding_service.embed_batch(texts)

                for commit, vector in zip(batch, vectors):
                    await self._upsert_commit(commit, vector, repo_path)
                    stats.commits_indexed += 1

            except Exception as e:
                logger.warning(
                    "batch_embed_failed",
                    error=str(e),
                    falling_back_to_sequential=True,
                )
                for commit in batch:
                    try:
                        text = self._build_embedding_text(commit)
                        vector = await self.embedding_service.embed(text)
                        await self._upsert_commit(commit, vector, repo_path)
                        stats.commits_indexed += 1
                    except Exception as e2:
                        logger.error(
                            "commit_index_failed", sha=commit.sha, error=str(e2)
                        )
                        stats.errors.append(
                            IndexingError(
                                sha=commit.sha,
                                error_type=type(e2).__name__,
                                message=str(e2),
                            )
                        )

        if commits:
            try:
                head_sha = await self.git_reader.get_head_sha()
                await self.metadata_store.update_git_index_state(
                    repo_path=repo_path,
                    last_sha=head_sha,
                    count=stats.commits_indexed,
                )
            except Exception as e:
                logger.error("failed_to_update_index_state", error=str(e))

        return stats

    async def _upsert_commit(
        self, commit: Commit, vector: np.ndarray, repo_path: str
    ) -> None:
        payload = {
            "id": commit.sha,
            "sha": commit.sha,
            "message": commit.message,
            "author": commit.author,
            "author_email": commit.author_email,
            "timestamp": commit.timestamp.timestamp(),
            "timestamp_iso": commit.timestamp.isoformat(),
            "files_changed": commit.files_changed,
            "file_count": len(commit.files_changed),
            "insertions": commit.insertions,
            "deletions": commit.deletions,
            "indexed_at": datetime.now(UTC).timestamp(),
            "indexed_at_iso": datetime.now(UTC).isoformat(),
            "repo_path": repo_path,
        }

        await self.vector_store.upsert(
            collection="commits",
            id=commit.sha,
            vector=vector,
            payload=payload,
        )

    def _build_embedding_text(self, commit: Commit) -> str:
        files_str = ", ".join(commit.files_changed)
        if len(files_str) > 500:
            files_str = files_str[:500] + "..."

        return f"{commit.message}\n\nFiles: {files_str}\n\nAuthor: {commit.author}"

    async def search_commits(
        self,
        query: str,
        author: str | None = None,
        since: datetime | None = None,
        limit: int = 10,
    ) -> list[CommitSearchResult]:
        await self._ensure_commits_collection()

        query_vector = await self.embedding_service.embed(query)

        filters: dict[str, Any] = {}
        if author:
            filters["author"] = author
        if since:
            filters["timestamp"] = {"$gte": since.timestamp()}

        results = await self.vector_store.search(
            collection="commits",
            query=query_vector,
            limit=limit,
            filters=filters or None,
        )

        search_results = []
        for result in results:
            p = result.payload
            commit = Commit(
                sha=p["sha"],
                message=p["message"],
                author=p["author"],
                author_email=p["author_email"],
                timestamp=datetime.fromisoformat(p["timestamp_iso"]),
                files_changed=p["files_changed"],
                insertions=p["insertions"],
                deletions=p["deletions"],
            )
            search_results.append(CommitSearchResult(commit=commit, score=result.score))

        return search_results

    async def get_churn_hotspots(
        self,
        days: int = 90,
        limit: int = 10,
        min_changes: int = 3,
    ) -> list[ChurnRecord]:
        since = datetime.now(UTC) - timedelta(days=days)
        commits = await self.git_reader.get_commits(since=since, limit=100000)

        file_stats: dict[str, dict[str, Any]] = {}

        for commit in commits:
            for file_path in commit.files_changed:
                if file_path not in file_stats:
                    file_stats[file_path] = {
                        "change_count": 0,
                        "insertions": 0,
                        "deletions": 0,
                        "authors": set(),
                        "emails": set(),
                        "last_changed": commit.timestamp,
                    }

                stats_entry = file_stats[file_path]
                stats_entry["change_count"] += 1
                stats_entry["insertions"] += commit.insertions
                stats_entry["deletions"] += commit.deletions
                stats_entry["authors"].add(commit.author)
                stats_entry["emails"].add(commit.author_email)
                stats_entry["last_changed"] = max(
                    stats_entry["last_changed"], commit.timestamp
                )

        filtered = [
            ChurnRecord(
                file_path=path,
                change_count=stats_data["change_count"],
                total_insertions=stats_data["insertions"],
                total_deletions=stats_data["deletions"],
                authors=sorted(stats_data["authors"]),
                author_emails=sorted(stats_data["emails"]),
                last_changed=stats_data["last_changed"],
            )
            for path, stats_data in file_stats.items()
            if stats_data["change_count"] >= min_changes
        ]

        filtered.sort(key=lambda r: r.change_count, reverse=True)
        return filtered[:limit]

    async def get_file_authors(self, file_path: str) -> list[AuthorStats]:
        commits = await self.git_reader.get_file_history(file_path, limit=100000)

        author_data: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "commit_count": 0,
                "lines_added": 0,
                "lines_removed": 0,
                "first_commit": None,
                "last_commit": None,
                "email": "",
            }
        )

        for commit in commits:
            author_key = commit.author
            data = author_data[author_key]

            data["commit_count"] += 1
            data["lines_added"] += commit.insertions
            data["lines_removed"] += commit.deletions
            data["email"] = commit.author_email

            if data["first_commit"] is None or commit.timestamp < data["first_commit"]:
                data["first_commit"] = commit.timestamp
            if data["last_commit"] is None or commit.timestamp > data["last_commit"]:
                data["last_commit"] = commit.timestamp

        stats = [
            AuthorStats(
                author=author,
                author_email=data["email"],
                commit_count=data["commit_count"],
                lines_added=data["lines_added"],
                lines_removed=data["lines_removed"],
                first_commit=data["first_commit"],
                last_commit=data["last_commit"],
            )
            for author, data in author_data.items()
        ]

        stats.sort(key=lambda s: s.commit_count, reverse=True)
        return stats

    async def get_change_frequency(
        self,
        file_or_function: str,
        since: datetime | None = None,
    ) -> ChurnRecord | None:
        commits = await self.git_reader.get_commits(
            path=file_or_function, since=since, limit=100000
        )

        if not commits:
            return None

        authors: set[str] = set()
        emails: set[str] = set()
        total_insertions = 0
        total_deletions = 0
        last_changed = commits[0].timestamp

        for commit in commits:
            authors.add(commit.author)
            emails.add(commit.author_email)
            total_insertions += commit.insertions
            total_deletions += commit.deletions

        return ChurnRecord(
            file_path=file_or_function,
            change_count=len(commits),
            total_insertions=total_insertions,
            total_deletions=total_deletions,
            authors=sorted(authors),
            author_emails=sorted(emails),
            last_changed=last_changed,
        )

    async def blame_search(
        self,
        pattern: str,
        file_pattern: str | None = None,
        limit: int = 20,
    ) -> list[BlameSearchResult]:
        repo_root = self.git_reader.get_repo_root()

        cmd = ["rg", "--line-number", "--no-heading", pattern]
        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    stdin=subprocess.DEVNULL,
                ),
            )
        except FileNotFoundError:
            logger.error("ripgrep_not_found", command="rg")
            raise GitAnalyzerError(
                "ripgrep (rg) not found. Install via: brew install ripgrep"
            )
        except Exception as e:
            logger.error("ripgrep_failed", error=str(e), command=cmd)
            raise GitAnalyzerError(f"ripgrep search failed: {e}")

        if result.returncode not in (0, 1):
            logger.error(
                "ripgrep_error",
                returncode=result.returncode,
                stderr=result.stderr,
                command=cmd,
            )
            raise GitAnalyzerError(
                f"ripgrep error (code {result.returncode}): {result.stderr}"
            )

        matches: list[tuple[str, int]] = []
        for line in result.stdout.splitlines()[: limit * 2]:
            parts = line.split(":", 2)
            if len(parts) >= 2:
                file_path, line_num_str = parts[0], parts[1]
                try:
                    line_num = int(line_num_str)
                    matches.append((file_path, line_num))
                except ValueError:
                    continue

        results: list[BlameSearchResult] = []

        for file_path, line_num in matches[:limit]:
            try:
                blame_entries = await self.git_reader.get_blame(file_path)

                for entry in blame_entries:
                    if entry.line_start <= line_num <= entry.line_end:
                        lines = entry.content.splitlines()
                        line_index = line_num - entry.line_start
                        if 0 <= line_index < len(lines):
                            line_content = lines[line_index]
                        else:
                            line_content = ""

                        results.append(
                            BlameSearchResult(
                                file_path=file_path,
                                line_number=line_num,
                                content=line_content,
                                sha=entry.sha,
                                author=entry.author,
                                author_email=entry.author_email,
                                timestamp=entry.timestamp,
                            )
                        )
                        break

            except (BinaryFileError, FileNotInRepoError):
                continue

        return results
