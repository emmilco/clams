# Amendments: Hybrid Search Support

**Date**: 2025-12-03
**Affects**: SPEC-002-02 (EmbeddingService), SPEC-002-03 (VectorStore)
**Required by**: SPEC-002-09 (Searcher), SPEC-002-11 (MCP Tools)

## Background

During spec review for SPEC-002-09 and SPEC-002-11, hybrid search was added to scope. This requires amendments to already-completed modules.

## SPEC-002-02: EmbeddingService Amendments

The EmbeddingService must generate both **dense** and **sparse** vectors.

### Interface Changes

```python
@dataclass
class EmbeddingResult:
    """Result containing both dense and sparse vectors."""
    dense: list[float]           # Dense embedding vector
    sparse: SparseVector | None  # Sparse vector (BM25/SPLADE), None for semantic-only

@dataclass
class SparseVector:
    """Sparse vector representation for keyword search."""
    indices: list[int]   # Token indices
    values: list[float]  # Token weights

class EmbeddingService(Protocol):
    async def embed(
        self,
        text: str,
        include_sparse: bool = False,
    ) -> EmbeddingResult:
        """
        Generate embeddings for text.

        Args:
            text: Text to embed
            include_sparse: If True, also generate sparse vector

        Returns:
            EmbeddingResult with dense vector and optional sparse vector
        """
        ...

    async def embed_batch(
        self,
        texts: list[str],
        include_sparse: bool = False,
    ) -> list[EmbeddingResult]:
        """Batch embedding with optional sparse vectors."""
        ...
```

### Implementation Notes

- Sparse vectors use SPLADE or BM25 tokenization
- SPLADE is preferred (learned sparse representations)
- Fallback: BM25 via tokenizer + TF-IDF weights
- `include_sparse=False` by default for backward compatibility

## SPEC-002-03: VectorStore Amendments

The VectorStore must store and query both dense and sparse vectors.

### Interface Changes

```python
class VectorStore(Protocol):
    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: dict[str, Any],
        sparse_vector: SparseVector | None = None,
    ) -> None:
        """
        Upsert a point with optional sparse vector.

        Args:
            collection: Collection name
            id: Point ID
            vector: Dense embedding vector
            payload: Metadata payload
            sparse_vector: Optional sparse vector for hybrid search
        """
        ...

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        sparse_vector: SparseVector | None = None,
        search_mode: str = "semantic",  # semantic, keyword, hybrid
    ) -> list[SearchResult]:
        """
        Search with optional hybrid mode.

        Args:
            collection: Collection name
            vector: Dense query vector
            limit: Max results
            filters: Metadata filters
            sparse_vector: Sparse query vector (required for keyword/hybrid)
            search_mode: Search mode

        Returns:
            Search results, scored and sorted
        """
        ...
```

### Qdrant Implementation Notes

- Dense vectors: Main vector field (existing)
- Sparse vectors: Named vector `"sparse"`
- Hybrid query: Set both vectors, Qdrant handles RRF fusion
- Collection schema change required (add sparse vector config)

```python
# Qdrant collection config for hybrid
vectors_config = {
    "": models.VectorParams(size=768, distance=Distance.COSINE),  # dense
}
sparse_vectors_config = {
    "sparse": models.SparseVectorParams(),  # sparse
}
```

## Migration Path

1. **Backward compatible**: All changes are additive
2. **Existing data**: Works with `search_mode="semantic"` (no sparse needed)
3. **New data**: Index with `include_sparse=True` to enable hybrid
4. **Re-indexing**: Required for hybrid search on existing collections

## Implementation Priority

This can be implemented as a follow-up task after SPEC-002-09 and SPEC-002-11 complete their initial implementation with semantic-only search. The `search_mode` parameter is in the interface but can initially only support `"semantic"`.

Suggested task: **SPEC-002-XX: Hybrid Search Implementation**
