"""Code indexer implementation for semantic code search."""

import os
import time
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import structlog

from calm.config import settings
from calm.embedding.base import EmbeddingModelError, EmbeddingService
from calm.search.collections import CollectionName
from calm.storage.base import Vector, VectorStore
from calm.storage.metadata import MetadataStore

from .base import CodeParser, IndexingError, IndexingStats, ParseError, SemanticUnit
from .utils import EXTENSION_MAP, compute_file_hash, generate_unit_id

logger = structlog.get_logger(__name__)


class CodeIndexer:
    """Index parsed code units for semantic search."""

    COLLECTION_NAME = CollectionName.CODE

    DEFAULT_EXCLUDED_DIRS: set[str] = {
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".tox",
        ".nox",
        "dist",
        "build",
        "target",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "htmlcov",
        ".eggs",
        ".worktrees",
    }

    @property
    def embedding_batch_size(self) -> int:
        """Get embedding batch size from configuration."""
        return settings.indexer.embedding_batch_size

    def __init__(
        self,
        parser: CodeParser,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        metadata_store: MetadataStore,
    ) -> None:
        self.parser = parser
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.metadata_store = metadata_store
        self._collection_ensured = False

    async def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist, recreate if dimension mismatches."""
        if self._collection_ensured:
            return

        try:
            try:
                info = await self.vector_store.get_collection_info(self.COLLECTION_NAME)
                if info and info.dimension != self.embedding_service.dimension:
                    logger.warning(
                        "dimension_mismatch",
                        collection=self.COLLECTION_NAME,
                        expected=self.embedding_service.dimension,
                        actual=info.dimension,
                        action="recreating_collection",
                    )
                    await self.vector_store.delete_collection(self.COLLECTION_NAME)
            except Exception:
                pass

            await self.vector_store.create_collection(
                name=self.COLLECTION_NAME,
                dimension=self.embedding_service.dimension,
            )
            logger.info(
                "collection_created",
                name=self.COLLECTION_NAME,
                dimension=self.embedding_service.dimension,
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "already exists" in error_msg or "409" in str(e):
                logger.debug("collection_exists", name=self.COLLECTION_NAME)
            else:
                raise

        self._collection_ensured = True

    async def index_file(self, path: str, project: str) -> IndexingStats:
        """Index a single file."""
        stats = IndexingStats(files_indexed=0, units_indexed=0, files_skipped=0)

        await self._ensure_collection()

        if not await self.needs_reindex(path, project):
            logger.info("file_skipped", path=path, reason="no_changes")
            stats.files_skipped = 1
            return stats

        try:
            units = await self.parser.parse_file(path)
        except ParseError as e:
            logger.warning("parse_failed", path=path, error=e.message)
            stats.errors.append(IndexingError(path, e.error_type, e.message))
            return stats

        if not units:
            stats.files_skipped = 1
            return stats

        await self._delete_file_units(path, project)

        successful_units, embeddings = await self._embed_units(units, stats.errors)

        if not successful_units:
            return stats

        unit_ids = [
            generate_unit_id(project, path, u.qualified_name)
            for u in successful_units
        ]
        for unit, unit_id, embedding in zip(successful_units, unit_ids, embeddings):
            payload = self._build_payload(unit, project)
            await self.vector_store.upsert(
                collection=self.COLLECTION_NAME,
                id=unit_id,
                vector=embedding,
                payload=payload,
            )

        file_hash = compute_file_hash(path)
        mtime = Path(path).stat().st_mtime
        language = self.parser.detect_language(path)
        await self.metadata_store.add_indexed_file(
            file_path=path,
            project=project,
            language=language or "unknown",
            file_hash=file_hash,
            unit_count=len(successful_units),
            last_modified=datetime.fromtimestamp(mtime),
        )

        stats.files_indexed = 1
        stats.units_indexed = len(successful_units)
        return stats

    async def _embed_units(
        self, units: list[SemanticUnit], errors: list[IndexingError]
    ) -> tuple[list[SemanticUnit], list[Vector]]:
        """Embed units in batches."""
        successful_units: list[SemanticUnit] = []
        embeddings: list[Vector] = []
        batch_size = self.embedding_batch_size

        for i in range(0, len(units), batch_size):
            batch = units[i : i + batch_size]
            texts = [self._prepare_embedding_text(u) for u in batch]

            try:
                batch_embeddings = await self.embedding_service.embed_batch(texts)
                embeddings.extend(batch_embeddings)
                successful_units.extend(batch)
            except EmbeddingModelError as e:
                logger.warning(
                    "embedding_batch_failed",
                    batch_size=len(batch),
                    batch_start=i,
                    error=str(e),
                )
                for unit in batch:
                    errors.append(
                        IndexingError(
                            file_path=unit.file_path,
                            error_type="embedding_error",
                            message=f"Failed to embed {unit.qualified_name}: {e}",
                        )
                    )

        return successful_units, embeddings

    def _prepare_embedding_text(self, unit: SemanticUnit) -> str:
        """Format unit for embedding."""
        parts = [unit.signature]

        if unit.docstring:
            parts.append(unit.docstring)

        content = unit.content
        if len(content) > 4000:
            content = content[:4000]
        parts.append(content)

        return "\n\n".join(parts)

    def _build_payload(
        self, unit: SemanticUnit, project: str
    ) -> dict[str, Any]:
        """Build vector store payload from SemanticUnit."""
        return {
            "project": project,
            "file_path": unit.file_path,
            "name": unit.name,
            "qualified_name": unit.qualified_name,
            "unit_type": unit.unit_type.value,
            "signature": unit.signature,
            "language": unit.language,
            "start_line": unit.start_line,
            "end_line": unit.end_line,
            "line_count": unit.end_line - unit.start_line + 1,
            "complexity": unit.complexity,
            "has_docstring": unit.docstring is not None,
            "indexed_at": datetime.now().isoformat(),
        }

    async def needs_reindex(self, path: str, project: str) -> bool:
        """Check if file needs reindexing."""
        indexed_file = await self.metadata_store.get_indexed_file(path, project)
        if not indexed_file:
            return True

        current_mtime = Path(path).stat().st_mtime
        if current_mtime <= indexed_file.last_modified.timestamp():
            return False

        current_hash = compute_file_hash(path)
        return current_hash != indexed_file.file_hash

    async def index_directory(
        self,
        path: str,
        project: str,
        recursive: bool = True,
        exclude_patterns: list[str] | None = None,
    ) -> IndexingStats:
        """Index all supported files in directory."""
        await self._ensure_collection()

        start_time = time.time()
        stats = IndexingStats(files_indexed=0, units_indexed=0, files_skipped=0)

        files = self._find_files(path, recursive, exclude_patterns)

        for file_path in files:
            file_stats = await self.index_file(file_path, project)
            stats.files_indexed += file_stats.files_indexed
            stats.units_indexed += file_stats.units_indexed
            stats.files_skipped += file_stats.files_skipped
            stats.errors.extend(file_stats.errors)

        stats.duration_ms = int((time.time() - start_time) * 1000)
        return stats

    def _find_files(
        self, root: str, recursive: bool, exclude_patterns: list[str] | None
    ) -> list[str]:
        """Find all supported files in directory.

        Uses os.walk with in-place directory pruning to avoid descending
        into excluded directories (e.g. .venv, node_modules). This prevents
        the performance cost of enumerating thousands of irrelevant files.
        """
        supported_exts = set(EXTENSION_MAP.keys())
        files: list[str] = []

        root_path = Path(root).expanduser()
        excluded_dirs = self._build_excluded_dirs(exclude_patterns)

        try:
            for dirpath, dirnames, filenames in os.walk(
                str(root_path), followlinks=False
            ):
                # Prune excluded directories in-place to prevent descent
                dirnames[:] = [
                    d for d in dirnames if d not in excluded_dirs
                ]

                for filename in filenames:
                    file_path = Path(dirpath) / filename
                    if file_path.is_symlink():
                        continue
                    if file_path.suffix not in supported_exts:
                        continue
                    if self._should_exclude(str(file_path), exclude_patterns):
                        continue
                    files.append(str(file_path))

                if not recursive:
                    break
        except PermissionError as e:
            logger.warning(
                "directory_permission_error", path=str(root_path), error=str(e)
            )

        return files

    def _build_excluded_dirs(
        self, exclude_patterns: list[str] | None
    ) -> set[str]:
        """Build set of directory names to skip during os.walk.

        Combines the class-level DEFAULT_EXCLUDED_DIRS with directory names
        extracted from the provided exclusion patterns.
        """
        excluded = set(self.DEFAULT_EXCLUDED_DIRS)

        if exclude_patterns:
            for pattern in exclude_patterns:
                # Extract directory names from glob patterns like
                # "**/.venv/**" or "**/node_modules/**"
                parts = Path(pattern).parts
                for part in parts:
                    if part not in ("**", "*") and not part.startswith("*."):
                        excluded.add(part)

        return excluded

    def _should_exclude(self, path: str, patterns: list[str] | None) -> bool:
        """Check if path matches any exclusion pattern."""
        if not patterns:
            return False

        for pattern in patterns:
            if fnmatch(path, pattern):
                return True
        return False

    async def remove_file(self, path: str, project: str) -> int:
        """Remove all indexed units for a file."""
        count = await self._count_file_units(path, project)
        await self._delete_file_units(path, project)
        await self.metadata_store.delete_indexed_file(path, project)
        logger.info("file_removed", path=path, project=project, units_removed=count)
        return count

    async def remove_project(self, project: str) -> int:
        """Remove all indexed units for a project."""
        files = await self.metadata_store.list_indexed_files(project=project)
        for file_info in files:
            await self._delete_file_units(file_info.file_path, project)
        await self.metadata_store.delete_project(project)
        logger.info("project_removed", project=project, files_count=len(files))
        return len(files)

    async def get_indexing_stats(
        self, project: str | None = None
    ) -> dict[str, Any]:
        """Get indexing statistics."""
        files = await self.metadata_store.list_indexed_files(project=project)
        total_files = len(files)
        total_units = sum(f.unit_count for f in files)
        languages: dict[str, int] = {}
        for file_info in files:
            lang = file_info.language or "unknown"
            languages[lang] = languages.get(lang, 0) + 1
        return {
            "total_files": total_files,
            "total_units": total_units,
            "languages": languages,
            "projects": len(set(f.project for f in files)) if project is None else 1,
        }

    async def is_file_indexed(self, path: str, project: str) -> bool:
        """Check if a file is indexed."""
        file_info = await self.metadata_store.get_indexed_file(path, project)
        return file_info is not None

    async def _count_file_units(self, path: str, project: str) -> int:
        """Count units for a file in the vector store."""
        return await self.vector_store.count(
            collection=self.COLLECTION_NAME,
            filters={"file_path": path, "project": project},
        )

    async def _delete_file_units(self, path: str, project: str) -> None:
        """Delete all vector store entries for a file."""
        total_deleted = 0
        while True:
            results = await self.vector_store.scroll(
                collection=self.COLLECTION_NAME,
                filters={"file_path": path, "project": project},
                limit=1000,
                with_vectors=False,
            )
            if not results:
                break
            for result in results:
                await self.vector_store.delete(
                    collection=self.COLLECTION_NAME,
                    id=result.id,
                )
            total_deleted += len(results)
        logger.debug(
            "file_units_deleted", path=path, project=project, count=total_deleted
        )
