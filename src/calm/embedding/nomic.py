"""Nomic embedding implementation using sentence-transformers."""

import asyncio
from functools import partial
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

from .base import EmbeddingModelError, EmbeddingService, Vector


class NomicEmbedding(EmbeddingService):
    """Nomic embedding service using sentence-transformers.

    Uses nomic-ai/nomic-embed-text-v1.5 model by default. CPU-bound
    operations are run in executor threads to avoid blocking the event loop.

    Attributes:
        model: The loaded SentenceTransformer model
    """

    def __init__(
        self,
        model_name: str = "nomic-ai/nomic-embed-text-v1.5",
        cache_dir: str | None = None,
    ) -> None:
        """Initialize the Nomic embedding service.

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
            # Force CPU to avoid MPS memory leak
            # MPS backend in PyTorch has known memory management issues
            # that cause severe memory accumulation during batch embeddings
            if torch.backends.mps.is_available():
                self.model = self.model.to(torch.device("cpu"))
        except OSError as e:
            # OSError covers network issues (ConnectionError, TimeoutError)
            # and file-not-found when model isn't cached
            raise EmbeddingModelError(
                f"Failed to download/load model '{model_name}': {e}. "
                f"If this is the first run, check your network connection. "
                f"Models are downloaded from HuggingFace Hub on first use."
            ) from e
        except Exception as e:
            raise EmbeddingModelError(
                f"Failed to load model '{model_name}': {e}"
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
        """Get embedding dimension from the loaded model.

        Returns:
            int: Number of dimensions in output vectors

        Raises:
            EmbeddingModelError: If model does not return embedding dimension
        """
        dim = self.model.get_sentence_embedding_dimension()
        if dim is None:
            raise EmbeddingModelError("Model did not return embedding dimension")
        return int(dim)
