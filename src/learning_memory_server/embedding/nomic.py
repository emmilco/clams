"""Nomic embedding implementation using sentence-transformers."""

import asyncio
from functools import partial
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from .base import EmbeddingModelError, EmbeddingService, EmbeddingSettings, Vector


class NomicEmbedding(EmbeddingService):
    """Nomic embedding service using sentence-transformers.

    Uses nomic-ai/nomic-embed-text-v1.5 model by default, producing
    768-dimensional embeddings. CPU-bound operations are run in
    executor threads to avoid blocking the event loop.

    Attributes:
        model: The loaded SentenceTransformer model
        settings: Configuration settings for the embedding service
    """

    _DIMENSION = 768

    def __init__(self, settings: EmbeddingSettings | None = None) -> None:
        """Initialize the Nomic embedding service.

        Args:
            settings: Configuration settings (uses defaults if not provided)

        Raises:
            EmbeddingModelError: If model loading fails
        """
        self.settings = settings or EmbeddingSettings()
        try:
            self.model = SentenceTransformer(
                self.settings.model_name,
                cache_folder=self.settings.cache_dir,
                trust_remote_code=True,
            )
        except Exception as e:
            raise EmbeddingModelError(
                f"Failed to load model {self.settings.model_name}: {e}"
            ) from e

    async def embed(self, text: str) -> Vector:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            768-dimensional float32 numpy array

        Raises:
            EmbeddingModelError: If embedding generation fails
        """
        try:
            # Run CPU-bound embedding in executor to avoid blocking event loop
            loop = asyncio.get_event_loop()
            embedding: Any = await loop.run_in_executor(
                None, partial(self.model.encode, text, convert_to_numpy=True)
            )
            # Convert to numpy array and ensure float32 dtype
            result = np.asarray(embedding, dtype=np.float32)
            return result
        except Exception as e:
            raise EmbeddingModelError(f"Failed to generate embedding: {e}") from e

    async def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of input texts to embed

        Returns:
            List of 768-dimensional float32 numpy arrays

        Raises:
            EmbeddingModelError: If embedding generation fails
        """
        if not texts:
            return []

        try:
            # Run batch encoding in executor
            loop = asyncio.get_event_loop()
            embeddings: Any = await loop.run_in_executor(
                None,
                partial(
                    self.model.encode,
                    texts,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                ),
            )
            # Convert to list of individual float32 arrays
            return [np.asarray(embedding, dtype=np.float32) for embedding in embeddings]
        except Exception as e:
            raise EmbeddingModelError(
                f"Failed to generate batch embeddings: {e}"
            ) from e

    @property
    def dimension(self) -> int:
        """Return the dimensionality of embeddings (768).

        Returns:
            int: 768
        """
        return self._DIMENSION
