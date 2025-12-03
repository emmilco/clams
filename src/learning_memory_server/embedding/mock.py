"""Mock embedding implementation for testing."""

import hashlib

import numpy as np

from .base import EmbeddingService, Vector


class MockEmbedding(EmbeddingService):
    """Mock embedding service with deterministic hash-based vectors.

    Uses MD5 hash of input text to generate reproducible embeddings,
    making tests deterministic and fast without requiring model downloads.

    Produces 768-dimensional vectors to match real embedding services.
    """

    _DIMENSION = 768

    def __init__(self) -> None:
        """Initialize the mock embedding service."""
        pass

    async def embed(self, text: str) -> Vector:
        """Generate deterministic embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            768-dimensional float32 numpy array based on text hash
        """
        return self._hash_to_vector(text)

    async def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Generate deterministic embeddings for multiple texts.

        Args:
            texts: List of input texts to embed

        Returns:
            List of 768-dimensional float32 numpy arrays
        """
        return [self._hash_to_vector(text) for text in texts]

    @property
    def dimension(self) -> int:
        """Return the dimensionality of embeddings (768).

        Returns:
            int: 768
        """
        return self._DIMENSION

    def _hash_to_vector(self, text: str) -> Vector:
        """Convert text to deterministic vector using hash.

        Args:
            text: Input text

        Returns:
            Normalized float32 vector of length 768
        """
        # Use MD5 hash as seed for reproducibility
        hash_bytes = hashlib.md5(text.encode("utf-8")).digest()
        seed = int.from_bytes(hash_bytes[:4], byteorder="big")

        # Generate deterministic random vector
        rng = np.random.RandomState(seed)
        vector = rng.randn(self._DIMENSION).astype(np.float32)

        # Normalize to unit length (common for embeddings)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector
