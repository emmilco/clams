"""Tests for MockEmbedding implementation."""

import numpy as np
import pytest

from clams.embedding import MockEmbedding


class TestMockEmbedding:
    """Test suite for MockEmbedding service."""

    @pytest.fixture
    def mock_service(self) -> MockEmbedding:
        """Create a MockEmbedding instance for testing."""
        return MockEmbedding()

    def test_dimension(self, mock_service: MockEmbedding) -> None:
        """Test that dimension property returns 768."""
        assert mock_service.dimension == 768

    async def test_embed_returns_correct_shape(
        self, mock_service: MockEmbedding
    ) -> None:
        """Test that embed returns vector of correct shape and dtype."""
        text = "Hello, world!"
        embedding = await mock_service.embed(text)

        assert isinstance(embedding, np.ndarray)
        assert embedding.dtype == np.float32
        assert embedding.shape == (768,)

    async def test_embed_deterministic(self, mock_service: MockEmbedding) -> None:
        """Test that same text produces same embedding."""
        text = "Test text"
        embedding1 = await mock_service.embed(text)
        embedding2 = await mock_service.embed(text)

        np.testing.assert_array_equal(embedding1, embedding2)

    async def test_embed_different_texts_produce_different_embeddings(
        self, mock_service: MockEmbedding
    ) -> None:
        """Test that different texts produce different embeddings."""
        text1 = "First text"
        text2 = "Second text"

        embedding1 = await mock_service.embed(text1)
        embedding2 = await mock_service.embed(text2)

        # Embeddings should be different
        assert not np.array_equal(embedding1, embedding2)

    async def test_embed_normalized(self, mock_service: MockEmbedding) -> None:
        """Test that embeddings are normalized to unit length."""
        text = "Normalize me"
        embedding = await mock_service.embed(text)

        norm = np.linalg.norm(embedding)
        # Should be normalized (approximately 1.0)
        assert np.isclose(norm, 1.0, rtol=1e-5)

    async def test_embed_batch_empty_list(self, mock_service: MockEmbedding) -> None:
        """Test that embed_batch handles empty input."""
        embeddings = await mock_service.embed_batch([])
        assert embeddings == []

    async def test_embed_batch_single_item(self, mock_service: MockEmbedding) -> None:
        """Test embed_batch with single text."""
        texts = ["Single text"]
        embeddings = await mock_service.embed_batch(texts)

        assert len(embeddings) == 1
        assert embeddings[0].shape == (768,)
        assert embeddings[0].dtype == np.float32

    async def test_embed_batch_multiple_items(
        self, mock_service: MockEmbedding
    ) -> None:
        """Test embed_batch with multiple texts."""
        texts = ["First", "Second", "Third"]
        embeddings = await mock_service.embed_batch(texts)

        assert len(embeddings) == 3
        for embedding in embeddings:
            assert embedding.shape == (768,)
            assert embedding.dtype == np.float32

        # Each should be different
        assert not np.array_equal(embeddings[0], embeddings[1])
        assert not np.array_equal(embeddings[1], embeddings[2])

    async def test_embed_batch_consistency_with_embed(
        self, mock_service: MockEmbedding
    ) -> None:
        """Test that embed_batch produces same results as individual embed calls."""
        texts = ["Text A", "Text B", "Text C"]

        # Get embeddings individually
        individual_embeddings = [await mock_service.embed(text) for text in texts]

        # Get embeddings in batch
        batch_embeddings = await mock_service.embed_batch(texts)

        # Should be identical
        assert len(individual_embeddings) == len(batch_embeddings)
        for individual, batch in zip(individual_embeddings, batch_embeddings):
            np.testing.assert_array_equal(individual, batch)

    async def test_embed_handles_special_characters(
        self, mock_service: MockEmbedding
    ) -> None:
        """Test that embed handles text with special characters."""
        texts = [
            "Hello! @#$%^&*()",
            "Unicode: 你好世界 🌍",
            "Empty:",
            "",
        ]

        for text in texts:
            embedding = await mock_service.embed(text)
            assert embedding.shape == (768,)
            assert embedding.dtype == np.float32
            assert np.isclose(np.linalg.norm(embedding), 1.0, rtol=1e-5)

    async def test_embed_long_text(self, mock_service: MockEmbedding) -> None:
        """Test that embed handles longer text."""
        long_text = "word " * 1000
        embedding = await mock_service.embed(long_text)

        assert embedding.shape == (768,)
        assert embedding.dtype == np.float32
        assert np.isclose(np.linalg.norm(embedding), 1.0, rtol=1e-5)
