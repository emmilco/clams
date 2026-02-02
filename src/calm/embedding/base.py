"""Base embedding service interface and types."""

from abc import ABC, abstractmethod

import numpy as np
import numpy.typing as npt

# Vector type alias - numpy array of float32
Vector = npt.NDArray[np.float32]


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
