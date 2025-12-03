"""Git history analysis and indexing."""

import asyncio
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import structlog

from ..embedding.base import EmbeddingService
from ..storage.base import VectorStore
from ..storage.metadata import MetadataStore
from .base import (
    AuthorStats,
    BinaryFileError,
    BlameSearchResult,
    ChurnRecord,
    Commit,
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
        """Initialize GitAnalyzer.

        Args:
            git_reader: GitReader instance for accessing git data
            embedding_service: Service for generating embeddings
            vector_store: Vector store for commit search
            metadata_store: Metadata store for indexing state
        """
        self.git_reader = git_reader
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    async def index_commits(
        self,
        since: datetime | None = None,
        limit: int | None = None,
        force: bool = False,
    ) -> IndexingStats:
        """Index commits for semantic search.

        History limit: Only indexes commits from the last 5 years.
        Older commits are ignored (diminishing relevance, storage cost).

        Incremental indexing algorithm:
        1. Get last_indexed_sha from git_index_state table
        2. If force=True or no last_indexed_sha, index all commits (up to 5 years)
        3. Otherwise, traverse from HEAD backwards until we find last_indexed_sha
        4. Index only commits between HEAD and last_indexed_sha
        5. Update last_indexed_sha to current HEAD

        Note: If last_indexed_sha is not in current history (force push, rebase),
        falls back to full reindex.

        Args:
            since: Optional start date for indexing (UTC, timezone-aware)
            limit: Optional maximum number of commits to index
            force: If True, reindex all commits

        Returns:
            IndexingStats with counts and errors
        """
        stats = IndexingStats(commits_indexed=0, commits_skipped=0)
        start_time = time.time()

        repo_path = self.git_reader.get_repo_root()

        # Get current state
        state = await self.metadata_store.get_git_index_state(repo_path)

        # Determine indexing mode
        if force or not state or not state.last_indexed_sha:
            # Full reindex
            logger.info(
                "full_index_starting",
                repo_path=repo_path,
                force=force,
                has_state=state is not None,
            )
            commits = await self._get_commits_to_index(since, limit)
        else:
            # Incremental: find commits since last_indexed_sha
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
                # Already up to date
                logger.info("index_already_up_to_date", repo_path=repo_path)
                stats.duration_ms = int((time.time() - start_time) * 1000)
                return stats

            # Walk backwards from HEAD
            all_commits = await self.git_reader.get_commits(limit=10000)
            new_commits = []

            for commit in all_commits:
                if commit.sha == state.last_indexed_sha:
                    # Found last indexed commit - stop here
                    break
                new_commits.append(commit)
            else:
                # last_indexed_sha not found - history rewritten
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

        # Index the commits
        stats = await self._index_commit_batch(commits, stats)
        stats.duration_ms = int((time.time() - start_time) * 1000)

        return stats

    async def _get_commits_to_index(
        self, since: datetime | None, limit: int | None
    ) -> list[Commit]:
        """Get commits respecting 5-year limit.

        Args:
            since: Optional start date
            limit: Optional limit

        Returns:
            List of commits to index
        """
        five_years_ago = datetime.now(UTC) - timedelta(days=5 * 365)
        effective_since = max(since, five_years_ago) if since else five_years_ago
        return await self.git_reader.get_commits(since=effective_since, limit=limit)

    async def _index_commit_batch(
        self, commits: list[Commit], stats: IndexingStats
    ) -> IndexingStats:
        """Index a batch of commits using batch embedding for performance.

        Args:
            commits: Commits to index
            stats: Current indexing stats

        Returns:
            Updated stats
        """
        if not commits:
            return stats

        repo_path = self.git_reader.get_repo_root()

        # Process in batches of 75 for optimal embedding performance
        batch_size = 75
        for i in range(0, len(commits), batch_size):
            batch = commits[i : i + batch_size]

            try:
                # Build embedding texts for entire batch
                texts = [self._build_embedding_text(commit) for commit in batch]

                # Generate embeddings in batch (5-10x faster than sequential)
                vectors = await self.embedding_service.embed_batch(texts)

                # Upsert all commits in batch
                for commit, vector in zip(batch, vectors):
                    await self._upsert_commit(commit, vector, repo_path)
                    stats.commits_indexed += 1

            except Exception as e:
                # Log batch failure, try individual commits
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

        # Update state
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
        self, commit: Commit, vector: list[float], repo_path: str
    ) -> None:
        """Upsert a single commit to the vector store.

        Args:
            commit: Commit to upsert
            vector: Embedding vector
            repo_path: Repository root path
        """
        payload = {
            "id": commit.sha,
            "sha": commit.sha,
            "message": commit.message,
            "author": commit.author,
            "author_email": commit.author_email,
            "timestamp": commit.timestamp.isoformat(),
            "files_changed": commit.files_changed,
            "file_count": len(commit.files_changed),
            "insertions": commit.insertions,
            "deletions": commit.deletions,
            "indexed_at": datetime.now(UTC).isoformat(),
            "repo_path": repo_path,
        }

        await self.vector_store.upsert(
            collection="commits",
            id=commit.sha,
            vector=vector,
            payload=payload,
        )

    def _build_embedding_text(self, commit: Commit) -> str:
        """Build text for embedding from commit data.

        Format:
            {commit_message}

            Files: {files_changed joined by ", " - truncated to 500 chars if longer}

            Author: {author}

        Args:
            commit: Commit to build text from

        Returns:
            Text for embedding
        """
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
    ) -> list[Commit]:
        """Semantic search over commit messages.

        Embeds query, searches VectorStore, returns matched commits.

        Args:
            query: Natural language search query
            author: Optional author name filter
            since: Optional date filter (UTC, timezone-aware)
            limit: Maximum number of results

        Returns:
            List of matching commits ordered by similarity
        """
        # Generate query embedding
        query_vector = await self.embedding_service.embed(query)

        # Build filters
        filters = {}
        if author:
            filters["author"] = author
        if since:
            filters["timestamp"] = {"$gte": since.isoformat()}

        # Search vector store
        results = await self.vector_store.search(
            collection="commits",
            query=query_vector,
            limit=limit,
            filters=filters or None,
        )

        # Convert payloads back to Commit objects
        commits = []
        for result in results:
            p = result.payload
            commits.append(
                Commit(
                    sha=p["sha"],
                    message=p["message"],
                    author=p["author"],
                    author_email=p["author_email"],
                    timestamp=datetime.fromisoformat(p["timestamp"]),
                    files_changed=p["files_changed"],
                    insertions=p["insertions"],
                    deletions=p["deletions"],
                )
            )

        return commits

    async def get_churn_hotspots(
        self,
        days: int = 90,
        limit: int = 10,
        min_changes: int = 3,
    ) -> list[ChurnRecord]:
        """Find files with highest change frequency.

        Computes on demand from git history (no caching).

        Args:
            days: Number of days to look back
            limit: Maximum number of results
            min_changes: Minimum number of changes to qualify

        Returns:
            List of ChurnRecord ordered by change count descending
        """
        # Compute date range
        since = datetime.now(UTC) - timedelta(days=days)

        # Get all commits in range
        commits = await self.git_reader.get_commits(since=since, limit=None)

        # Aggregate by file
        file_stats: dict[str, dict] = {}

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

                # Note: Using commit-level stats as approximation
                # Ideally would use per-file stats from commit.stats.files
                stats_entry["insertions"] += commit.insertions
                stats_entry["deletions"] += commit.deletions

                stats_entry["authors"].add(commit.author)
                stats_entry["emails"].add(commit.author_email)
                stats_entry["last_changed"] = max(
                    stats_entry["last_changed"], commit.timestamp
                )

        # Filter by min_changes
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

        # Sort by change count descending
        filtered.sort(key=lambda r: r.change_count, reverse=True)

        return filtered[:limit]

    async def get_file_authors(self, file_path: str) -> list[AuthorStats]:
        """Get author statistics for a file (computed on demand).

        Args:
            file_path: Path relative to repo root

        Returns:
            List of AuthorStats ordered by commit count descending
        """
        # Get file history
        commits = await self.git_reader.get_file_history(file_path, limit=None)

        # Aggregate by author
        author_data: dict[str, dict] = defaultdict(
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

        # Convert to AuthorStats objects
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

        # Sort by commit count descending
        stats.sort(key=lambda s: s.commit_count, reverse=True)

        return stats

    async def get_change_frequency(
        self,
        file_or_function: str,
        since: datetime | None = None,
    ) -> ChurnRecord | None:
        """Get change frequency for a specific file or function name.

        Args:
            file_or_function: File path or function name
            since: Optional start date

        Returns:
            ChurnRecord or None if no changes found
        """
        # Treat as file path first
        commits = await self.git_reader.get_commits(
            path=file_or_function, since=since, limit=None
        )

        if not commits:
            return None

        # Aggregate stats
        authors: set[str] = set()
        emails: set[str] = set()
        total_insertions = 0
        total_deletions = 0
        last_changed = commits[0].timestamp  # Most recent

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
        """Search for code pattern and return blame info for matches.

        Uses ripgrep to find matches, then git blame to get authorship.

        Args:
            pattern: Pattern to search for
            file_pattern: Optional file glob pattern
            limit: Maximum number of results

        Returns:
            List of BlameSearchResult with authorship info
        """
        repo_root = self.git_reader.get_repo_root()

        cmd = ["rg", "--line-number", "--no-heading", pattern]
        if file_pattern:
            cmd.extend(["--glob", file_pattern])

        # Run in executor (subprocess is blocking)
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                ),
            )
        except FileNotFoundError:
            # ripgrep not installed
            logger.error(
                "ripgrep_not_found",
                command="rg",
                suggestion="Install ripgrep",
            )
            raise GitAnalyzerError(
                "ripgrep (rg) not found. Install via: brew install ripgrep"
            )
        except Exception as e:
            # Other subprocess errors
            logger.error("ripgrep_failed", error=str(e), command=cmd)
            raise GitAnalyzerError(f"ripgrep search failed: {e}")

        # Check for ripgrep errors
        if result.returncode not in (0, 1):
            # returncode 1 means no matches (expected), other codes are errors
            logger.error(
                "ripgrep_error",
                returncode=result.returncode,
                stderr=result.stderr,
                command=cmd,
            )
            raise GitAnalyzerError(
                f"ripgrep error (code {result.returncode}): {result.stderr}"
            )

        # Parse grep results
        matches: list[tuple[str, int]] = []  # (file_path, line_number)
        for line in result.stdout.splitlines()[: limit * 2]:  # Get extra for filtering
            parts = line.split(":", 2)
            if len(parts) >= 2:
                file_path, line_num_str = parts[0], parts[1]
                try:
                    line_num = int(line_num_str)
                    matches.append((file_path, line_num))
                except ValueError:
                    continue

        # Get blame for each match
        results: list[BlameSearchResult] = []

        for file_path, line_num in matches[:limit]:
            try:
                blame_entries = await self.git_reader.get_blame(file_path)

                # Find entry containing this line
                for entry in blame_entries:
                    if entry.line_start <= line_num <= entry.line_end:
                        # Extract the specific line content
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
                # Skip files we can't blame
                continue

        return results
