"""Tests for NomicEmbedding implementation.

These tests may be skipped if the model is not available or takes too long to download.
"""

import numpy as np
import pytest

from learning_memory_server.embedding import (
    EmbeddingModelError,
    EmbeddingSettings,
    NomicEmbedding,
)


@pytest.mark.slow
class TestNomicEmbedding:
    """Test suite for NomicEmbedding service.

    Note: Tests marked as 'slow' may download model files on first run.
    Use `pytest -m "not slow"` to skip these tests.
    """

    @pytest.fixture
    def nomic_service(self) -> NomicEmbedding:
        """Create a NomicEmbedding instance for testing.

        May raise EmbeddingModelError if model cannot be loaded.
        """
        try:
            return NomicEmbedding()
        except EmbeddingModelError:
            pytest.skip("Nomic model not available")

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
        settings = EmbeddingSettings(
            model_name="nomic-ai/nomic-embed-text-v1.5",
            cache_dir="/tmp/test_cache",
        )
        try:
            service = NomicEmbedding(settings)
            assert service.settings.model_name == "nomic-ai/nomic-embed-text-v1.5"
            assert service.settings.cache_dir == "/tmp/test_cache"
        except EmbeddingModelError:
            pytest.skip("Nomic model not available")

    def test_invalid_model_raises_error(self) -> None:
        """Test that invalid model name raises EmbeddingModelError."""
        settings = EmbeddingSettings(
            model_name="invalid/model/name/that/does/not/exist"
        )
        with pytest.raises(EmbeddingModelError):
            NomicEmbedding(settings)
