"""In-memory vector store implementation for testing and development."""

from typing import Any

import numpy as np

from .base import CollectionInfo, SearchResult, Vector, VectorStore


class MemoryStore(VectorStore):
    """In-memory vector store using numpy for cosine similarity."""

    def __init__(self) -> None:
        """Initialize the in-memory store."""
        self._collections: dict[str, dict[str, Any]] = {}

    async def create_collection(
        self, name: str, dimension: int, distance: str = "cosine"
    ) -> None:
        """Create a new collection."""
        if name in self._collections:
            raise ValueError(f"Collection {name} already exists")

        self._collections[name] = {
            "dimension": dimension,
            "distance": distance,
            "vectors": {},  # id -> vector
            "payloads": {},  # id -> payload
        }

    async def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        if name not in self._collections:
            raise ValueError(f"Collection {name} not found")
        del self._collections[name]

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: Vector,
        payload: dict[str, Any],
    ) -> None:
        """Insert or update a vector."""
        if collection not in self._collections:
            raise ValueError(f"Collection {collection} not found")

        coll = self._collections[collection]
        expected_dim = coll["dimension"]

        if vector.shape[0] != expected_dim:
            raise ValueError(
                f"Vector dimension {vector.shape[0]} does not match "
                f"collection dimension {expected_dim}"
            )

        coll["vectors"][id] = vector.copy()
        coll["payloads"][id] = payload.copy()

    async def search(
        self,
        collection: str,
        query: Vector,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors using cosine similarity."""
        if collection not in self._collections:
            raise ValueError(f"Collection {collection} not found")

        coll = self._collections[collection]
        vectors = coll["vectors"]
        payloads = coll["payloads"]

        if not vectors:
            return []

        # Apply filters
        filtered_ids = self._apply_filters(payloads, filters)

        if not filtered_ids:
            return []

        # Compute similarities
        results = []
        query_norm = np.linalg.norm(query)

        for id in filtered_ids:
            vector = vectors[id]
            vector_norm = np.linalg.norm(vector)

            if query_norm == 0 or vector_norm == 0:
                similarity = 0.0
            else:
                # Cosine similarity
                similarity = float(np.dot(query, vector) / (query_norm * vector_norm))

            results.append(
                SearchResult(
                    id=id,
                    score=similarity,
                    payload=payloads[id].copy(),
                    vector=None,
                )
            )

        # Sort by similarity (descending) and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def delete(self, collection: str, id: str) -> None:
        """Delete a vector by ID."""
        if collection not in self._collections:
            raise ValueError(f"Collection {collection} not found")

        coll = self._collections[collection]
        if id in coll["vectors"]:
            del coll["vectors"][id]
            del coll["payloads"][id]

    async def scroll(
        self,
        collection: str,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        with_vectors: bool = False,
    ) -> list[SearchResult]:
        """Retrieve vectors without search."""
        if collection not in self._collections:
            raise ValueError(f"Collection {collection} not found")

        coll = self._collections[collection]
        payloads = coll["payloads"]
        vectors = coll["vectors"]

        # Apply filters
        filtered_ids = self._apply_filters(payloads, filters)

        results = []
        for id in list(filtered_ids)[:limit]:
            results.append(
                SearchResult(
                    id=id,
                    score=0.0,  # No score for scroll
                    payload=payloads[id].copy(),
                    vector=vectors[id].copy() if with_vectors else None,
                )
            )

        return results

    async def count(
        self, collection: str, filters: dict[str, Any] | None = None
    ) -> int:
        """Count vectors in a collection."""
        if collection not in self._collections:
            raise ValueError(f"Collection {collection} not found")

        coll = self._collections[collection]
        payloads = coll["payloads"]

        filtered_ids = self._apply_filters(payloads, filters)
        return len(filtered_ids)

    async def get(
        self, collection: str, id: str, with_vector: bool = False
    ) -> SearchResult | None:
        """Get a specific vector by ID."""
        if collection not in self._collections:
            raise ValueError(f"Collection {collection} not found")

        coll = self._collections[collection]
        if id not in coll["vectors"]:
            return None

        return SearchResult(
            id=id,
            score=0.0,
            payload=coll["payloads"][id].copy(),
            vector=coll["vectors"][id].copy() if with_vector else None,
        )

    def _apply_filters(
        self, payloads: dict[str, dict[str, Any]], filters: dict[str, Any] | None
    ) -> list[str]:
        """Apply filters to payloads, supporting operators like $gte/$lte/$gt/$lt/$in.

        Returns list of IDs that match all filters.
        """
        if not filters:
            return list(payloads.keys())

        matching_ids = []
        for id, payload in payloads.items():
            # Check if all filter conditions match
            matches = True
            for key, value in filters.items():
                if key not in payload:
                    matches = False
                    break

                payload_value = payload[key]

                # Check if value is operator-based filter (dict with $operators)
                if isinstance(value, dict):
                    if not self._match_operators(payload_value, value):
                        matches = False
                        break
                else:
                    # Simple equality check
                    if payload_value != value:
                        matches = False
                        break

            if matches:
                matching_ids.append(id)

        return matching_ids

    def _match_operators(self, payload_value: Any, operators: dict[str, Any]) -> bool:
        """Check if payload value matches all operator conditions.

        Supports:
            $gte: Greater than or equal
            $lte: Less than or equal
            $gt: Greater than
            $lt: Less than
            $in: Value is in list
        """
        for op, op_value in operators.items():
            if op == "$gte":
                if not (payload_value >= op_value):
                    return False
            elif op == "$lte":
                if not (payload_value <= op_value):
                    return False
            elif op == "$gt":
                if not (payload_value > op_value):
                    return False
            elif op == "$lt":
                if not (payload_value < op_value):
                    return False
            elif op == "$in":
                if payload_value not in op_value:
                    return False
            else:
                # Unknown operator - treat as equality with the dict
                if payload_value != operators:
                    return False
                break
        return True

    async def get_collection_info(self, name: str) -> CollectionInfo | None:
        """Get collection metadata from in-memory storage.

        Args:
            name: Collection name

        Returns:
            CollectionInfo if collection exists, None if not found
        """
        if name not in self._collections:
            return None

        collection = self._collections[name]
        return CollectionInfo(
            name=name,
            dimension=collection["dimension"],
            vector_count=len(collection["vectors"]),
        )
