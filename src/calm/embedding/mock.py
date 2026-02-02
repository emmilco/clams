"""Mock embedding implementation for testing."""

import hashlib

import numpy as np

from .base import EmbeddingService, Vector


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service with deterministic hash-based vectors.

    Uses MD5 hash of input text to generate reproducible embeddings,
    making tests deterministic and fast without requiring model downloads.

    Produces configurable dimensional vectors (default 768 to match Nomic).
    """

    def __init__(self, dimension: int = 768) -> None:
        """Initialize the mock embedding service.

        Args:
            dimension: Dimensionality of the embeddings to produce
        """
        self._dimension = dimension

    async def embed(self, text: str) -> Vector:
        """Generate deterministic embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            Float32 numpy array based on text hash
        """
        return self._hash_to_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Generate deterministic embeddings for multiple texts.

        Args:
            texts: List of input texts to embed

        Returns:
            List of float32 numpy arrays
        """
        return [self._hash_to_vector(text) for text in texts]

    @property
    def dimension(self) -> int:
        """Return the dimensionality of embeddings.

        Returns:
            int: Configured dimension
        """
        return self._dimension

    def _hash_to_vector(self, text: str) -> Vector:
        """Convert text to deterministic vector using hash.

        Args:
            text: Input text

        Returns:
            Normalized float32 vector of configured length
        """
        # Use MD5 hash as seed for reproducibility
        hash_bytes = hashlib.md5(text.encode("utf-8")).digest()
        seed = int.from_bytes(hash_bytes[:4], byteorder="big")

        # Generate deterministic random vector
        rng = np.random.RandomState(seed)
        vector = rng.randn(self._dimension).astype(np.float32)

        # Normalize to unit length (common for embeddings)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector
