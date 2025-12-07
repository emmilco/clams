# SPEC-006: Dual Embedding Model Support for Faster Code Indexing

## Problem Statement

Code indexing via `index_codebase` is slow due to embedding generation being 99.8% of execution time. Profiling shows:
- Current model (Nomic, 768-dim): ~230ms per code unit
- Total indexing time for clams repo (155 files, 986 units): ~3.4 minutes

Benchmarking shows `all-MiniLM-L6-v2` (384-dim) is 6.2x faster with nearly equivalent code search quality (MRR 0.95 vs 1.0, 9/10 vs 10/10 hits@1).

## Proposed Solution

Support dual embedding models with purpose-specific selection:
- **Code indexing/search**: MiniLM (fast, 384-dim)
- **Memories/GHAP/clustering**: Nomic (quality, 768-dim)

Models load lazily on first use to avoid memory overhead when only one is needed.

## Requirements

### Functional Requirements

1. **Model Selection by Purpose**
   - `index_codebase`, `search_code`, `find_similar_code` → MiniLM
   - `store_memory`, `retrieve_memories` → Nomic
   - `start_ghap`, `search_experiences`, `get_clusters`, `validate_value`, `store_value` → Nomic
   - `index_commits`, `search_commits` → Nomic (commit messages benefit from quality)

2. **Lazy Loading**
   - Neither model loads at server startup
   - Each model loads on first use of a tool that requires it
   - Once loaded, model stays in memory for session duration

3. **Configuration (Optional)**
   - Allow override via environment variables for testing/experimentation:
     - `LMS_CODE_MODEL=all-MiniLM-L6-v2` (default)
     - `LMS_SEMANTIC_MODEL=nomic-ai/nomic-embed-text-v1.5` (default)

4. **Separate Vector Collections**
   - Code units: 384-dim collection (existing `code_units` will need migration or recreation)
   - Memories: 768-dim collection (existing)
   - GHAP axes: 768-dim collections (existing)
   - Commits: 768-dim collection (existing)
   - Values: 768-dim collection (existing)

### Non-Functional Requirements

1. **Performance**: Code indexing should complete in <1 minute for clams repo (currently 3.4 min)
2. **Memory**: Peak memory should not exceed single-model usage (lazy loading prevents both being loaded simultaneously in typical usage)
3. **Backward Compatibility**: Existing memories/GHAP data remains searchable (no dimension change)

### Error Handling Requirements

1. **Model Loading Failures**: If a model fails to load (network issue, missing model, OOM), propagate a clear `EmbeddingModelError` with the model name and underlying cause
2. **Dimension Mismatch**: If a query is made against a collection with mismatched dimensions, raise a descriptive error explaining the mismatch (e.g., "Query vector has 384 dims but collection expects 768")
3. **Invalid Configuration**: If environment variable specifies an invalid model name, fail fast on first model load with a clear error message listing the invalid value

## Design

### Embedding Service Architecture

```
EmbeddingService (Protocol)
    ├── embed(text) -> Vector
    ├── embed_batch(texts) -> list[Vector]
    └── dimension -> int

EmbeddingRegistry
    ├── get_code_embedder() -> EmbeddingService  # Lazy loads MiniLM
    ├── get_semantic_embedder() -> EmbeddingService  # Lazy loads Nomic
    └── _instances: dict[str, EmbeddingService]  # Cache loaded models

NomicEmbedding(EmbeddingService)  # 768-dim, existing
MiniLMEmbedding(EmbeddingService)  # 384-dim, new
```

### Registry Design Details

1. **Instantiation Pattern**: `EmbeddingRegistry` is a module-level singleton created on first import. The MCP server uses this single instance throughout its lifetime.

2. **Thread Safety**: Not required. The MCP server processes requests sequentially (single-threaded asyncio). Model loading happens synchronously within the async context via `run_in_executor`.

3. **Model Lifecycle**: Models are never unloaded during server lifetime. This is intentional:
   - Loading is expensive (~2-3 seconds)
   - Memory is acceptable (~500MB-1GB per model)
   - Typical usage patterns load one or the other, rarely both

4. **Lazy Loading Implementation**:
   ```python
   class EmbeddingRegistry:
       _code_embedder: EmbeddingService | None = None
       _semantic_embedder: EmbeddingService | None = None

       def get_code_embedder(self) -> EmbeddingService:
           if self._code_embedder is None:
               self._code_embedder = MiniLMEmbedding()
           return self._code_embedder

       def get_semantic_embedder(self) -> EmbeddingService:
           if self._semantic_embedder is None:
               self._semantic_embedder = NomicEmbedding()
           return self._semantic_embedder
   ```

### Tool → Embedder Mapping

| Tool | Embedder | Rationale |
|------|----------|-----------|
| `index_codebase` | Code (MiniLM) | Speed critical, quality acceptable |
| `search_code` | Code (MiniLM) | Must match indexed vectors |
| `find_similar_code` | Code (MiniLM) | Must match indexed vectors |
| `store_memory` | Semantic (Nomic) | Quality for long-term retrieval |
| `retrieve_memories` | Semantic (Nomic) | Must match stored vectors |
| `index_commits` | Semantic (Nomic) | Commit messages are natural language |
| `search_commits` | Semantic (Nomic) | Must match indexed vectors |
| `start_ghap` | Semantic (Nomic) | Quality for learning/clustering |
| `search_experiences` | Semantic (Nomic) | Must match GHAP vectors |
| `get_clusters` | Semantic (Nomic) | Clustering needs consistent embeddings |
| `validate_value` | Semantic (Nomic) | Must match cluster centroids |
| `store_value` | Semantic (Nomic) | Must match cluster centroids |

### Migration

The `code_units` collection dimension will change from 768 to 384. Options:
1. **Recreate on first use** (recommended): Delete existing collection, recreate with 384-dim. Users re-index.
2. **Versioned collections**: Create `code_units_v2` (384-dim), deprecate `code_units` (768-dim).

Recommend option 1 since code indexing is fast and transient (re-index on demand).

#### Migration Process (Option 1)

1. On `index_codebase` call, `CodeIndexer._ensure_collection()` checks if collection exists
2. If collection exists, verify dimension matches expected (384):
   ```python
   collection_info = await vector_store.get_collection_info("code_units")
   if collection_info and collection_info.dimension != self.embedding_service.dimension:
       logger.warning("dimension_mismatch",
           expected=self.embedding_service.dimension,
           actual=collection_info.dimension,
           action="recreating_collection")
       await vector_store.delete_collection("code_units")
   ```
3. If dimension mismatches or collection doesn't exist, create with correct dimension
4. User's `index_codebase` call proceeds normally, re-indexing all files

**User Communication**: The dimension change is logged as a warning. No user action required - the collection auto-recreates and re-indexes on next use.

## Acceptance Criteria

1. [ ] `MiniLMEmbedding` class implemented with 384-dim output
2. [ ] `EmbeddingRegistry` provides lazy-loaded embedders by purpose
3. [ ] `CodeIndexer` uses code embedder (MiniLM)
4. [ ] Memory/GHAP tools use semantic embedder (Nomic)
5. [ ] Neither model loads until first tool use
   - **Test**: Start server, call `ping`, verify no model loaded (check memory or mock)
6. [ ] Code indexing completes in <1 minute for clams repo
   - **Test**: `test_indexing_performance` times `index_codebase` on clams repo, asserts <60s
7. [ ] Existing memory/GHAP search continues to work
   - **Test**: Store memory with Nomic, search with Nomic, verify results returned
8. [ ] Environment variable overrides work for both models
   - **Test**: Set `LMS_CODE_MODEL` to different model, verify it loads
9. [ ] Tests cover both embedders and lazy loading behavior
   - **Test**: `test_lazy_loading` - access code embedder, verify only MiniLM loaded
   - **Test**: `test_registry_caches_instances` - call `get_code_embedder()` twice, verify same instance
10. [ ] Dimension mismatch triggers collection recreation
    - **Test**: Create 768-dim collection, call `index_codebase`, verify collection recreated as 384-dim
11. [ ] Model loading errors propagate clearly
    - **Test**: Configure invalid model name, verify `EmbeddingModelError` raised with model name

## Out of Scope

- Quantization (int8/OpenVINO) - future optimization
- User-selectable models per operation - keep it simple
- Embedding caching/persistence - not needed for current workload

## Risks

1. **Quality regression for code search**: Mitigated by benchmark showing 95% equivalent quality
2. **Memory if both models load**: Mitigated by lazy loading; typical usage loads one or the other
3. **Collection dimension mismatch**: Mitigated by auto-recreation of code_units collection
