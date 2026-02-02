"""MiniLM embedding implementation using sentence-transformers."""

import asyncio
from functools import partial
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

from .base import EmbeddingModelError, EmbeddingService, Vector


class MiniLMEmbedding(EmbeddingService):
    """MiniLM embedding service using sentence-transformers.

    Model and dimension determined by settings. Optimized for speed while
    maintaining acceptable quality for code search.

    Attributes:
        model: The loaded SentenceTransformer model
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        cache_dir: str | None = None,
    ) -> None:
        """Initialize the MiniLM embedding service.

        Args:
            model_name: Name of the model to load
            cache_dir: Optional directory for caching model files

        Raises:
            EmbeddingModelError: If model loading fails
        """
        self._model_name = model_name
        self._cache_dir = cache_dir
        try:
            self.model = SentenceTransformer(
                model_name,
                cache_folder=cache_dir,
                trust_remote_code=True,
            )
            # Force CPU to avoid MPS memory leak (same as Nomic)
            # MPS backend in PyTorch has known memory management issues
            # that cause severe memory accumulation during batch embeddings
            if torch.backends.mps.is_available():
                self.model = self.model.to(torch.device("cpu"))
        except Exception as e:
            raise EmbeddingModelError(
                f"Failed to load model {model_name}: {e}"
            ) from e

    @property
    def dimension(self) -> int:
        """Get embedding dimension from the loaded model.

        Returns:
            int: Number of dimensions in output vectors
        """
        dim = self.model.get_sentence_embedding_dimension()
        if dim is None:
            raise EmbeddingModelError("Model did not return embedding dimension")
        return int(dim)

    async def embed(self, text: str) -> Vector:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Float32 numpy array with dimension from model

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
            List of float32 numpy arrays with dimension from model

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
