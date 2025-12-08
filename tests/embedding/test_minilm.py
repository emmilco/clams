"""Tests for MiniLM embedding service."""

import numpy as np
import pytest
import torch

from clams.embedding.base import EmbeddingModelError, EmbeddingSettings
from clams.embedding.minilm import MiniLMEmbedding


@pytest.fixture
def minilm_service() -> MiniLMEmbedding:
    """Create MiniLM embedding service for testing."""
    settings = EmbeddingSettings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return MiniLMEmbedding(settings=settings)


@pytest.mark.asyncio
async def test_embed_single_text(minilm_service: MiniLMEmbedding) -> None:
    """Test embedding a single text."""
    text = "Hello, world!"
    embedding = await minilm_service.embed(text)

    # Verify embedding properties
    assert isinstance(embedding, np.ndarray)
    assert embedding.dtype == np.float32
    assert embedding.shape == (minilm_service.dimension,)
    assert minilm_service.dimension == 384  # all-MiniLM-L6-v2 dimension

    # Verify embedding has non-zero values
    assert np.any(embedding != 0)


@pytest.mark.asyncio
async def test_embed_batch(minilm_service: MiniLMEmbedding) -> None:
    """Test batch embedding multiple texts."""
    texts = ["First text", "Second text", "Third text"]
    embeddings = await minilm_service.embed_batch(texts)

    # Verify batch results
    assert len(embeddings) == 3
    for embedding in embeddings:
        assert isinstance(embedding, np.ndarray)
        assert embedding.dtype == np.float32
        assert embedding.shape == (minilm_service.dimension,)
        assert np.any(embedding != 0)


@pytest.mark.asyncio
async def test_embed_empty_batch(minilm_service: MiniLMEmbedding) -> None:
    """Test batch embedding with empty list."""
    embeddings = await minilm_service.embed_batch([])
    assert embeddings == []


@pytest.mark.asyncio
async def test_dimension_property(minilm_service: MiniLMEmbedding) -> None:
    """Test dimension property returns correct value."""
    dim = minilm_service.dimension
    assert isinstance(dim, int)
    assert dim == 384  # all-MiniLM-L6-v2 dimension


@pytest.mark.asyncio
async def test_mps_fallback_to_cpu(minilm_service: MiniLMEmbedding) -> None:
    """Test that model falls back to CPU when MPS is available.

    This tests the fix for the MPS memory leak issue. Even if MPS
    is available, the model should be forced to CPU.
    """
    # The model should be on CPU regardless of MPS availability
    if torch.backends.mps.is_available():
        # If MPS is available, verify we forced CPU
        # sentence-transformers wraps the model, so check the underlying device
        assert str(minilm_service.model.device) == "cpu"


@pytest.mark.asyncio
async def test_semantic_similarity(minilm_service: MiniLMEmbedding) -> None:
    """Test that semantically similar texts have similar embeddings."""
    text1 = "The cat sat on the mat"
    text2 = "A feline rested on the rug"
    text3 = "Python is a programming language"

    emb1 = await minilm_service.embed(text1)
    emb2 = await minilm_service.embed(text2)
    emb3 = await minilm_service.embed(text3)

    # Compute cosine similarities
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    sim_1_2 = cosine_similarity(emb1, emb2)
    sim_1_3 = cosine_similarity(emb1, emb3)

    # Similar sentences should have higher similarity than unrelated ones
    assert sim_1_2 > sim_1_3


@pytest.mark.asyncio
async def test_invalid_model_name() -> None:
    """Test that invalid model name raises error."""
    settings = EmbeddingSettings(model_name="invalid/model/name/that/does/not/exist")
    with pytest.raises(EmbeddingModelError, match="Failed to load model"):
        MiniLMEmbedding(settings=settings)


@pytest.mark.asyncio
async def test_embed_error_handling(minilm_service: MiniLMEmbedding) -> None:
    """Test error handling for embedding failures."""
    # Patch the model to raise an exception
    original_encode = minilm_service.model.encode

    def failing_encode(*args, **kwargs):
        raise RuntimeError("Simulated embedding failure")

    minilm_service.model.encode = failing_encode

    with pytest.raises(EmbeddingModelError, match="Failed to generate embedding"):
        await minilm_service.embed("test")

    # Restore original method
    minilm_service.model.encode = original_encode


@pytest.mark.asyncio
async def test_batch_embed_error_handling(minilm_service: MiniLMEmbedding) -> None:
    """Test error handling for batch embedding failures."""
    # Patch the model to raise an exception
    original_encode = minilm_service.model.encode

    def failing_encode(*args, **kwargs):
        raise RuntimeError("Simulated batch embedding failure")

    minilm_service.model.encode = failing_encode

    with pytest.raises(
        EmbeddingModelError, match="Failed to generate batch embeddings"
    ):
        await minilm_service.embed_batch(["test1", "test2"])

    # Restore original method
    minilm_service.model.encode = original_encode


@pytest.mark.asyncio
async def test_embedding_consistency(minilm_service: MiniLMEmbedding) -> None:
    """Test that same text produces consistent embeddings."""
    text = "Consistent embedding test"

    emb1 = await minilm_service.embed(text)
    emb2 = await minilm_service.embed(text)

    # Embeddings should be nearly identical (allowing for minor floating point differences)
    np.testing.assert_allclose(emb1, emb2, rtol=1e-5)


@pytest.mark.asyncio
async def test_batch_vs_single_consistency(minilm_service: MiniLMEmbedding) -> None:
    """Test that batch embedding produces same results as single embeddings."""
    texts = ["First text", "Second text"]

    # Get embeddings one at a time
    single_emb1 = await minilm_service.embed(texts[0])
    single_emb2 = await minilm_service.embed(texts[1])

    # Get embeddings as batch
    batch_embs = await minilm_service.embed_batch(texts)

    # Results should be nearly identical
    np.testing.assert_allclose(single_emb1, batch_embs[0], rtol=1e-5)
    np.testing.assert_allclose(single_emb2, batch_embs[1], rtol=1e-5)
