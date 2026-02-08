"""Tests for NomicEmbedding implementation."""

import numpy as np
import pytest

from calm.embedding.base import EmbeddingModelError
from calm.embedding.nomic import NomicEmbedding


@pytest.mark.slow
class TestNomicEmbedding:
    """Test suite for NomicEmbedding service.

    Note: Model files are downloaded on first run (~500MB).
    Use `pytest -m "not slow"` to exclude these tests.
    """

    @pytest.fixture
    def nomic_service(self) -> NomicEmbedding:
        """Create a NomicEmbedding instance for testing."""
        return NomicEmbedding()

    def test_dimension(self, nomic_service: NomicEmbedding) -> None:
        """Test that dimension property returns 768."""
        assert nomic_service.dimension == 768

    async def test_embed_returns_correct_shape(
        self, nomic_service: NomicEmbedding
    ) -> None:
        """Test that embed returns vector of correct shape and dtype."""
        text = "Hello, world!"
        embedding = await nomic_service.embed(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.dtype == np.float32
        assert embedding.shape == (768,)

    async def test_embed_multiple_calls(self, nomic_service: NomicEmbedding) -> None:
        """Test multiple embed calls."""
        texts = ["First text", "Second text"]

        embedding1 = await nomic_service.embed(texts[0])
        embedding2 = await nomic_service.embed(texts[1])

        assert embedding1.shape == (768,)
        assert embedding2.shape == (768,)
        # Different texts should produce different embeddings
        assert not np.array_equal(embedding1, embedding2)

    async def test_embed_batch_empty_list(self, nomic_service: NomicEmbedding) -> None:
        """Test that embed_batch handles empty input."""
        embeddings = await nomic_service.embed_batch([])
        assert embeddings == []

    async def test_embed_batch_single_item(
        self, nomic_service: NomicEmbedding
    ) -> None:
        """Test embed_batch with single text."""
        texts = ["Single text"]
        embeddings = await nomic_service.embed_batch(texts)

        assert len(embeddings) == 1
        assert embeddings[0].shape == (768,)
        assert embeddings[0].dtype == np.float32

    async def test_embed_batch_multiple_items(
        self, nomic_service: NomicEmbedding
    ) -> None:
        """Test embed_batch with multiple texts."""
        texts = ["First", "Second", "Third"]
        embeddings = await nomic_service.embed_batch(texts)

        assert len(embeddings) == 3
        for embedding in embeddings:
            assert embedding.shape == (768,)
            assert embedding.dtype == np.float32

    def test_custom_settings(self) -> None:
        """Test that custom settings are respected."""
        service = NomicEmbedding(
            model_name="nomic-ai/nomic-embed-text-v1.5",
            cache_dir="/tmp/test_cache",
        )
        assert service._model_name == "nomic-ai/nomic-embed-text-v1.5"
        assert service._cache_dir == "/tmp/test_cache"

    def test_invalid_model_raises_error(self) -> None:
        """Test that invalid model name raises EmbeddingModelError."""
        with pytest.raises(EmbeddingModelError):
            NomicEmbedding(model_name="invalid/model/name/that/does/not/exist")
