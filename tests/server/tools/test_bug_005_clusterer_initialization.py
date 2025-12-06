"""Regression test for BUG-005: Clusterer initialization.

Tests that ExperienceClusterer and ValueStore are properly initialized
with non-None Clusterer instances, preventing AttributeError when
clustering operations are attempted.
"""

import pytest

from learning_memory_server.clustering import Clusterer, ExperienceClusterer
from learning_memory_server.embedding import EmbeddingSettings, NomicEmbedding
from learning_memory_server.storage.qdrant import QdrantVectorStore
from learning_memory_server.values import ValueStore


def test_clusterer_has_correct_default_parameters() -> None:
    """Test that Clusterer can be initialized with expected parameters.

    This verifies the fix for BUG-005 by ensuring the Clusterer
    class accepts the parameters we use in register_all_tools.
    """
    clusterer = Clusterer(
        min_cluster_size=5,
        min_samples=3,
        metric="cosine",
        cluster_selection_method="eom",
    )

    assert clusterer.min_cluster_size == 5
    assert clusterer.min_samples == 3
    assert clusterer.metric == "cosine"
    assert clusterer.cluster_selection_method == "eom"


def test_experience_clusterer_accepts_clusterer_instance() -> None:
    """Test that ExperienceClusterer can be initialized with a Clusterer.

    This verifies the fix for BUG-005 where ExperienceClusterer was
    initialized with clusterer=None, causing AttributeError when
    clustering operations were attempted.
    """
    clusterer = Clusterer(
        min_cluster_size=5,
        min_samples=3,
        metric="cosine",
        cluster_selection_method="eom",
    )

    vector_store = QdrantVectorStore(url=":memory:")

    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer,
    )

    # Assert: Verify the clusterer is set (not None)
    assert experience_clusterer.clusterer is not None
    assert isinstance(experience_clusterer.clusterer, Clusterer)
    assert experience_clusterer.clusterer.min_cluster_size == 5


def test_value_store_accepts_experience_clusterer_instance() -> None:
    """Test that ValueStore can be initialized with an ExperienceClusterer.

    This verifies the fix for BUG-005 where ValueStore was initialized
    with clusterer=None, causing AttributeError when validation/storage
    operations were attempted.
    """
    clusterer = Clusterer(
        min_cluster_size=5,
        min_samples=3,
        metric="cosine",
        cluster_selection_method="eom",
    )

    vector_store = QdrantVectorStore(url=":memory:")

    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer,
    )

    embedding_settings = EmbeddingSettings(
        model_name="nomic-ai/nomic-embed-text-v1.5"
    )
    embedding_service = NomicEmbedding(settings=embedding_settings)

    value_store = ValueStore(
        embedding_service=embedding_service,
        vector_store=vector_store,
        clusterer=experience_clusterer,
    )

    # Assert: Verify the clusterer is set (not None)
    assert value_store.clusterer is not None
    assert isinstance(value_store.clusterer, ExperienceClusterer)

    # Verify the ExperienceClusterer has a Clusterer
    assert value_store.clusterer.clusterer is not None
    assert isinstance(value_store.clusterer.clusterer, Clusterer)


def test_initialization_matches_fix_plan() -> None:
    """Verify the initialization sequence matches the BUG-005 fix plan.

    This test encodes the exact sequence from the fix plan to ensure
    the components are wired together correctly.
    """
    # Step 1: Create Clusterer
    clusterer = Clusterer(
        min_cluster_size=5,
        min_samples=3,
        metric="cosine",
        cluster_selection_method="eom",
    )

    # Step 2: Create VectorStore
    vector_store = QdrantVectorStore(url=":memory:")

    # Step 3: Create ExperienceClusterer with Clusterer
    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer,
    )

    # Step 4: Create EmbeddingService
    embedding_settings = EmbeddingSettings(
        model_name="nomic-ai/nomic-embed-text-v1.5"
    )
    embedding_service = NomicEmbedding(settings=embedding_settings)

    # Step 5: Create ValueStore with ExperienceClusterer
    value_store = ValueStore(
        embedding_service=embedding_service,
        vector_store=vector_store,
        clusterer=experience_clusterer,
    )

    # Verify the full chain is connected
    assert value_store.clusterer.clusterer is not None
    assert value_store.clusterer.clusterer is clusterer
    assert value_store.clusterer is experience_clusterer

    # Verify no None values in the chain (the bug we're fixing)
    assert clusterer is not None
    assert experience_clusterer.clusterer is not None
    assert value_store.clusterer is not None
