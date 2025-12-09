"""Regression test for BUG-023: NomicEmbedding.dimension should query model, not hardcode 768."""

from unittest.mock import MagicMock, patch

import pytest
import torch

from clams.embedding.base import EmbeddingModelError, EmbeddingSettings
from clams.embedding.nomic import NomicEmbedding


def test_nomic_dimension_queries_model() -> None:
    """Verify NomicEmbedding.dimension queries the model instead of returning hardcoded 768.

    BUG-023: Previously, dimension property returned a hardcoded _DIMENSION = 768
    instead of querying the model. This breaks when using models with different
    dimensions.
    """
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 768
    mock_model.to.return_value = mock_model

    with (
        patch("clams.embedding.nomic.SentenceTransformer", return_value=mock_model),
        patch.object(torch.backends.mps, "is_available", return_value=False),
    ):
        settings = EmbeddingSettings(model_name="test-model")
        service = NomicEmbedding(settings)

        # Verify dimension comes from model query
        assert service.dimension == 768
        mock_model.get_sentence_embedding_dimension.assert_called()


def test_nomic_dimension_returns_actual_model_dimension() -> None:
    """Verify dimension property returns whatever the model reports.

    This tests that a model with a different dimension (e.g., 384) would
    be correctly reported.
    """
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = 384
    mock_model.to.return_value = mock_model

    with (
        patch("clams.embedding.nomic.SentenceTransformer", return_value=mock_model),
        patch.object(torch.backends.mps, "is_available", return_value=False),
    ):
        settings = EmbeddingSettings(model_name="test-model-384")
        service = NomicEmbedding(settings)

        # Verify dimension matches what the model reports
        assert service.dimension == 384


def test_nomic_dimension_raises_on_none() -> None:
    """Verify dimension property raises EmbeddingModelError if model returns None."""
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = None
    mock_model.to.return_value = mock_model

    with (
        patch("clams.embedding.nomic.SentenceTransformer", return_value=mock_model),
        patch.object(torch.backends.mps, "is_available", return_value=False),
    ):
        settings = EmbeddingSettings(model_name="test-model")
        service = NomicEmbedding(settings)

        with pytest.raises(EmbeddingModelError, match="Model did not return"):
            _ = service.dimension
