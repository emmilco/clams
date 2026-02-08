"""Shared fixtures for input validation tests.

This module provides fixtures for all tool categories, building on the
fixtures in tests/server/tools/conftest.py.
"""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from calm.clustering import ExperienceClusterer
from calm.clustering.types import ClusterInfo
from calm.ghap import ObservationCollector, ObservationPersister
from calm.storage.base import SearchResult
from calm.tools.code import get_code_tools
from calm.tools.context import get_context_tools
from calm.tools.ghap import get_ghap_tools
from calm.tools.git import get_git_tools
from calm.tools.learning import get_learning_tools
from calm.tools.memory import get_memory_tools
from calm.tools.session import SessionManager, get_session_tools
from calm.values import ValueStore


# Re-export fixtures from parent conftest
@pytest.fixture
def mock_code_embedder() -> AsyncMock:
    """Create mock code embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 384
    service.embed_batch.return_value = [[0.1] * 384, [0.2] * 384]
    service.dimension = 384
    return service


@pytest.fixture
def mock_semantic_embedder() -> AsyncMock:
    """Create mock semantic embedding service."""
    service = AsyncMock()
    service.embed.return_value = [0.1] * 768
    service.embed_batch.return_value = [[0.1] * 768, [0.2] * 768]
    service.dimension = 768
    return service


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Create mock vector store."""
    store = AsyncMock()
    store.upsert.return_value = None
    store.delete.return_value = None
    store.count.return_value = 0
    store.search.return_value = []
    store.scroll.return_value = []
    store.create_collection.return_value = None
    return store


@pytest.fixture
def mock_metadata_store() -> AsyncMock:
    """Create mock metadata store."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_code_indexer() -> MagicMock:
    """Create mock code indexer."""
    indexer = MagicMock()
    mock_stats = MagicMock()
    mock_stats.files_indexed = 10
    mock_stats.units_indexed = 50
    mock_stats.files_skipped = 2
    mock_stats.errors = []
    mock_stats.duration_ms = 100
    indexer.index_directory = AsyncMock(return_value=mock_stats)
    return indexer


@pytest.fixture
def mock_git_analyzer() -> MagicMock:
    """Create mock git analyzer."""
    analyzer = MagicMock()
    # Mock index_commits
    mock_stats = MagicMock()
    mock_stats.commits_indexed = 10
    mock_stats.commits_skipped = 2
    mock_stats.duration_ms = 100
    mock_stats.errors = []
    analyzer.index_commits = AsyncMock(return_value=mock_stats)
    # Mock search_commits
    analyzer.search_commits = AsyncMock(return_value=[])
    # Mock get_churn_hotspots
    analyzer.get_churn_hotspots = AsyncMock(return_value=[])
    # Mock get_file_authors
    analyzer.get_file_authors = AsyncMock(return_value=[])
    # Mock git_reader for file history
    analyzer.git_reader = MagicMock()
    analyzer.git_reader.get_file_history = AsyncMock(return_value=[])
    return analyzer


@pytest.fixture
def mock_search_result() -> Any:
    """Create a mock search result factory."""
    def _create(
        id: str = "12345678-1234-1234-1234-123456789abc",
        score: float = 0.95,
        payload: dict[str, Any] | None = None,
    ) -> SearchResult:
        if payload is None:
            payload = {
                "id": id,
                "content": "Test content",
                "category": "fact",
                "importance": 0.8,
                "tags": [],
                "created_at": "2025-01-01T00:00:00Z",
            }
        return SearchResult(id=id, score=score, payload=payload, vector=None)
    return _create


# Tool fixtures
@pytest.fixture
def memory_tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
) -> dict[str, Any]:
    """Get memory tools with mock services."""
    return get_memory_tools(mock_vector_store, mock_semantic_embedder)


@pytest.fixture
def code_tools(
    mock_vector_store: AsyncMock,
    mock_code_embedder: AsyncMock,
    mock_code_indexer: MagicMock,
) -> dict[str, Any]:
    """Get code tools with mock services."""
    return get_code_tools(mock_vector_store, mock_code_embedder, code_indexer=mock_code_indexer)


@pytest.fixture
def git_tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
    mock_git_analyzer: MagicMock,
) -> dict[str, Any]:
    """Get git tools with mock services."""
    return get_git_tools(mock_vector_store, mock_semantic_embedder, git_analyzer=mock_git_analyzer)


@pytest.fixture
def temp_journal_path() -> Path:
    """Create a temporary journal path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def observation_collector(temp_journal_path: Path) -> ObservationCollector:
    """Create an ObservationCollector with temp path."""
    return ObservationCollector(str(temp_journal_path))


@pytest.fixture
def observation_persister() -> ObservationPersister:
    """Create a mock ObservationPersister."""
    vector_store = MagicMock()
    vector_store.scroll = AsyncMock(return_value=[])
    return ObservationPersister(
        embedding_service=MagicMock(),
        vector_store=vector_store,
    )


@pytest.fixture
def ghap_tools(
    observation_collector: ObservationCollector,
    observation_persister: ObservationPersister,
) -> dict[str, Any]:
    """Get GHAP tools with mock services."""
    return get_ghap_tools(observation_collector, observation_persister)


@pytest.fixture
def experience_clusterer() -> ExperienceClusterer:
    """Create a mock ExperienceClusterer."""
    vector_store = MagicMock()
    vector_store.scroll = AsyncMock(return_value=[])

    clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=MagicMock(),
    )
    clusterer.count_experiences = AsyncMock(return_value=25)
    clusterer.cluster_axis = AsyncMock(
        return_value=[
            ClusterInfo(
                label=0,
                centroid=np.array([1.0, 2.0, 3.0], dtype=np.float32),
                member_ids=["id1", "id2"],
                size=10,
                avg_weight=0.8,
            ),
        ]
    )
    return clusterer


@pytest.fixture
def value_store() -> ValueStore:
    """Create a mock ValueStore."""
    vector_store = MagicMock()
    vector_store.scroll = AsyncMock(return_value=[])

    store = ValueStore(
        embedding_service=MagicMock(),
        vector_store=vector_store,
        clusterer=MagicMock(),
    )
    mock_validation = MagicMock()
    mock_validation.valid = True
    mock_validation.is_valid = True
    mock_validation.similarity = 0.85
    mock_validation.similarity_score = 0.85
    store.validate_value_candidate = AsyncMock(return_value=mock_validation)

    mock_value = MagicMock()
    mock_value.id = "value_123"
    mock_value.text = "Test value"
    mock_value.created_at = "2024-01-15T10:30:00+00:00"
    store.store_value = AsyncMock(return_value=mock_value)
    store.list_values = AsyncMock(return_value=[])
    return store


@pytest.fixture
def learning_tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
    experience_clusterer: ExperienceClusterer,
    value_store: ValueStore,
) -> dict[str, Any]:
    """Get learning tools with mock services."""
    return get_learning_tools(
        mock_vector_store, mock_semantic_embedder,
        experience_clusterer=experience_clusterer,
        value_store=value_store,
    )


@pytest.fixture
def mock_searcher() -> MagicMock:
    """Create a mock Searcher."""
    searcher = MagicMock()
    searcher.search_experiences = AsyncMock(return_value=[])
    return searcher


@pytest.fixture
def search_tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
) -> dict[str, Any]:
    """Get search tools (search_experiences is now in learning tools)."""
    return get_learning_tools(mock_vector_store, mock_semantic_embedder)


@pytest.fixture
def session_manager(temp_journal_path: Path) -> SessionManager:
    """Create a SessionManager with temp path."""
    return SessionManager(
        calm_dir=temp_journal_path,
        journal_dir=temp_journal_path,
    )


@pytest.fixture
def session_tools(session_manager: SessionManager) -> dict[str, Any]:
    """Get session tools with mock services."""
    return get_session_tools(session_manager)


@pytest.fixture
def context_tools(
    mock_vector_store: AsyncMock,
    mock_semantic_embedder: AsyncMock,
) -> dict[str, Any]:
    """Get context tools with mock services."""
    return get_context_tools(mock_vector_store, mock_semantic_embedder)
