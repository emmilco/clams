"""Base classes and types for vector storage."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic_settings import BaseSettings, SettingsConfigDict

# Type alias for vector representation
Vector = npt.NDArray[np.float32]


@dataclass
class SearchResult:
    """Result from a vector search operation."""

    id: str
    score: float
    payload: dict[str, Any]
    vector: Vector | None = None


class VectorStore(ABC):
    """Abstract base class for vector storage implementations."""

    @abstractmethod
    async def create_collection(
        self, name: str, dimension: int, distance: str = "cosine"
    ) -> None:
        """Create a new collection for storing vectors.

        Args:
            name: Collection name
            dimension: Vector dimension
            distance: Distance metric (cosine, euclidean, dot)
        """
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> None:
        """Delete a collection.

        Args:
            name: Collection name
        """
        pass

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        id: str,
        vector: Vector,
        payload: dict[str, Any],
    ) -> None:
        """Insert or update a vector with metadata.

        Args:
            collection: Collection name
            id: Unique identifier for this vector
            vector: Vector to store
            payload: Metadata associated with the vector
        """
        pass

    @abstractmethod
    async def search(
        self,
        collection: str,
        query: Vector,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors.

        Args:
            collection: Collection name
            query: Query vector
            limit: Maximum number of results
            filters: Optional filters on payload fields

        Returns:
            List of search results ordered by similarity
        """
        pass

    @abstractmethod
    async def delete(self, collection: str, id: str) -> None:
        """Delete a vector by ID.

        Args:
            collection: Collection name
            id: Vector ID to delete
        """
        pass

    @abstractmethod
    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> list[SearchResult]:
        """Retrieve vectors without search (for iteration).

        Args:
            collection: Collection name
            limit: Maximum number of results
            filters: Optional filters on payload fields
            with_vectors: Whether to include vector data

        Returns:
            List of results (not ordered by similarity)
        """
        pass

    @abstractmethod
    async def count(
        self, collection: str, filters: dict[str, Any] | None = None
    ) -> int:
        """Count vectors in a collection.

        Args:
            collection: Collection name
            filters: Optional filters on payload fields

        Returns:
            Number of vectors matching the filters
        """
        pass

    @abstractmethod
    async def get(
        self, collection: str, id: str, with_vector: bool = False
    ) -> SearchResult | None:
        """Get a specific vector by ID.

        Args:
            collection: Collection name
            id: Vector ID
            with_vector: Whether to include vector data

        Returns:
            SearchResult if found, None otherwise
        """
        pass


class StorageSettings(BaseSettings):
    """Storage configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Qdrant settings
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_timeout: float = 30.0

    # Storage paths
    storage_path: str = "~/.learning-memory"
    sqlite_path: str = "~/.learning-memory/metadata.db"
