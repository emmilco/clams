"""Base embedding service interface and types."""

from abc import ABC, abstractmethod

import numpy as np
from pydantic_settings import BaseSettings, SettingsConfigDict

# Vector type alias - numpy array of float32
type Vector = np.ndarray  # shape: (dimension,), dtype: float32


class EmbeddingSettings(BaseSettings):
    """Configuration for embedding services.

    Attributes:
        model_name: Name/identifier of the embedding model to use
        cache_dir: Optional directory for caching model files
    """

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    cache_dir: str | None = None


class EmbeddingModelError(Exception):
    """Raised when embedding model operations fail."""

    pass


class EmbeddingService(ABC):
    """Abstract base class for embedding generation services.

    Implementations must provide async methods for embedding single texts
    and batches, along with dimension information.
    """

    @abstractmethod
    async def embed(self, text: str) -> Vector:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Vector: Embedding vector as float32 numpy array

        Raises:
            EmbeddingModelError: If embedding generation fails
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors, one per input text

        Raises:
            EmbeddingModelError: If embedding generation fails
        """
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of embeddings produced by this service.

        Returns:
            int: Number of dimensions in output vectors
        """
        ...
