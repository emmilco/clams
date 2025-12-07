"""Qdrant vector store implementation."""

import uuid
from typing import Any

import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from .base import CollectionInfo, SearchResult, StorageSettings, Vector, VectorStore

# Namespace UUID for generating deterministic UUIDs from string IDs
_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _to_qdrant_id(id: str) -> str:
    """Convert a string ID to a valid Qdrant UUID.

    Qdrant requires point IDs to be either unsigned integers or UUIDs.
    This converts arbitrary string IDs to deterministic UUIDs.
    """
    # If already a valid UUID, use it
    try:
        uuid.UUID(id)
        return id
    except ValueError:
        pass

    # Generate a deterministic UUID from the string
    return str(uuid.uuid5(_NAMESPACE, id))


class QdrantVectorStore(VectorStore):
    """Vector store implementation using Qdrant."""

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """Initialize Qdrant client.

        Args:
            url: Qdrant server URL (defaults to settings). Use
                ":memory:" for in-memory mode.
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
        """
        settings = StorageSettings()
        self._url = url or settings.qdrant_url
        self._api_key = api_key or settings.qdrant_api_key
        self._timeout = timeout or settings.qdrant_timeout

        # Handle in-memory mode
        if self._url == ":memory:":
            self._client = AsyncQdrantClient(
                location=":memory:",
                timeout=int(self._timeout),
            )
        else:
            self._client = AsyncQdrantClient(
                url=self._url,
                api_key=self._api_key,
                timeout=int(self._timeout),
            )

    async def create_collection(
        self, name: str, dimension: int, distance: str = "cosine"
    ) -> None:
        """Create a new collection."""
        # Map distance metric to Qdrant enum
        distance_map = {
            "cosine": qmodels.Distance.COSINE,
            "euclidean": qmodels.Distance.EUCLID,
            "dot": qmodels.Distance.DOT,
        }

        if distance not in distance_map:
            raise ValueError(
                f"Unsupported distance metric: {distance}. "
                f"Supported: {list(distance_map.keys())}"
            )

        await self._client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=dimension,
                distance=distance_map[distance],
            ),
        )

    async def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        await self._client.delete_collection(collection_name=name)

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: Vector,
        payload: dict[str, Any],
    ) -> None:
        """Insert or update a vector."""
        qdrant_id = _to_qdrant_id(id)
        await self._client.upsert(
            collection_name=collection,
            points=[
                qmodels.PointStruct(
                    id=qdrant_id,
                    vector=vector.tolist(),
                    payload={**payload, "_original_id": id},
                )
            ],
        )

    async def search(
        self,
        collection: str,
        query: Vector,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        # Convert filters to Qdrant filter format
        qdrant_filter = self._build_filter(filters) if filters else None

        response = await self._client.query_points(
            collection_name=collection,
            query=query.tolist(),
            limit=limit,
            query_filter=qdrant_filter,
            with_payload=True,
            with_vectors=False,
        )
        results = response.points

        return [
            SearchResult(
                id=(result.payload or {}).get("_original_id", str(result.id)),
                score=result.score,
                payload={
                    k: v
                    for k, v in (result.payload or {}).items()
                    if k != "_original_id"
                },
                vector=None,
            )
            for result in results
        ]

    async def delete(self, collection: str, id: str) -> None:
        """Delete a vector by ID."""
        qdrant_id = _to_qdrant_id(id)
        await self._client.delete(
            collection_name=collection,
            points_selector=qmodels.PointIdsList(points=[qdrant_id]),
        )

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> list[SearchResult]:
        """Retrieve vectors without search."""
        qdrant_filter = self._build_filter(filters) if filters else None

        results, _ = await self._client.scroll(
            collection_name=collection,
            limit=limit,
            scroll_filter=qdrant_filter,
            with_payload=True,
            with_vectors=with_vectors,
        )

        return [
            SearchResult(
                id=(result.payload or {}).get("_original_id", str(result.id)),
                score=0.0,
                payload={
                    k: v
                    for k, v in (result.payload or {}).items()
                    if k != "_original_id"
                },
                vector=(
                    np.array(result.vector, dtype=np.float32)
                    if with_vectors and result.vector is not None
                    else None
                ),
            )
            for result in results
        ]

    async def count(
        self, collection: str, filters: dict[str, Any] | None = None
    ) -> int:
        """Count vectors in a collection."""
        qdrant_filter = self._build_filter(filters) if filters else None

        result = await self._client.count(
            collection_name=collection,
            count_filter=qdrant_filter,
            exact=True,
        )

        return result.count

    async def get(
        self, collection: str, id: str, with_vector: bool = False
    ) -> SearchResult | None:
        """Get a specific vector by ID."""
        qdrant_id = _to_qdrant_id(id)
        results = await self._client.retrieve(
            collection_name=collection,
            ids=[qdrant_id],
            with_payload=True,
            with_vectors=with_vector,
        )

        if not results:
            return None

        result = results[0]
        payload = result.payload or {}
        return SearchResult(
            id=payload.get("_original_id", str(result.id)),
            score=0.0,
            payload={k: v for k, v in payload.items() if k != "_original_id"},
            vector=(
                np.array(result.vector, dtype=np.float32)
                if with_vector and result.vector is not None
                else None
            ),
        )

    def _build_filter(self, filters: dict[str, Any]) -> qmodels.Filter:
        """Build Qdrant filter from simple key-value pairs.

        Supports:
        - Equality matching: {"field": "value"}
        - Multi-value matching: {"field": {"$in": ["val1", "val2"]}}
        - Range queries: {"field": {"$gte": value}}, {"field": {"$lte": value}}

        Note: Range queries only work with numeric values (int, float).
        Timestamps should be stored as Unix timestamps for range queries.
        """
        conditions: list[
            qmodels.FieldCondition
            | qmodels.IsEmptyCondition
            | qmodels.IsNullCondition
            | qmodels.HasIdCondition
            | qmodels.HasVectorCondition
            | qmodels.NestedCondition
            | qmodels.Filter
        ] = []

        for key, value in filters.items():
            # Handle operator queries
            if isinstance(value, dict):
                if "$in" in value:
                    # Multi-value match (ANY of the values)
                    conditions.append(
                        qmodels.FieldCondition(
                            key=key,
                            match=qmodels.MatchAny(any=value["$in"]),
                        )
                    )
                elif any(op in value for op in ("$gte", "$lte", "$gt", "$lt")):
                    # Range query - can combine multiple operators
                    conditions.append(
                        qmodels.FieldCondition(
                            key=key,
                            range=qmodels.Range(
                                gte=value.get("$gte"),
                                lte=value.get("$lte"),
                                gt=value.get("$gt"),
                                lt=value.get("$lt"),
                            ),
                        )
                    )
            else:
                # Simple equality match
                conditions.append(
                    qmodels.FieldCondition(
                        key=key,
                        match=qmodels.MatchValue(value=value),
                    )
                )

        # Qdrant accepts Sequence but list is covariant-compatible
        return qmodels.Filter(must=conditions if conditions else None)

    async def get_collection_info(self, name: str) -> CollectionInfo | None:
        """Get collection metadata from Qdrant.

        Args:
            name: Collection name

        Returns:
            CollectionInfo if collection exists, None if not found

        Raises:
            Exception: For Qdrant connection/network errors
        """
        try:
            collection = await self._client.get_collection(name)
            return CollectionInfo(
                name=name,
                dimension=collection.config.params.vectors.size,
                vector_count=collection.points_count,
            )
        except Exception as e:
            # Distinguish between "not found" vs real errors
            if "not found" in str(e).lower() or "404" in str(e):
                return None
            # Re-raise connection/network errors
            raise
