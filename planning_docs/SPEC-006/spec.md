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

## Acceptance Criteria

1. [ ] `MiniLMEmbedding` class implemented with 384-dim output
2. [ ] `EmbeddingRegistry` provides lazy-loaded embedders by purpose
3. [ ] `CodeIndexer` uses code embedder (MiniLM)
4. [ ] Memory/GHAP tools use semantic embedder (Nomic)
5. [ ] Neither model loads until first tool use
6. [ ] Code indexing completes in <1 minute for clams repo
7. [ ] Existing memory/GHAP search continues to work
8. [ ] Environment variable overrides work for both models
9. [ ] Tests cover both embedders and lazy loading behavior

## Out of Scope

- Quantization (int8/OpenVINO) - future optimization
- User-selectable models per operation - keep it simple
- Embedding caching/persistence - not needed for current workload

## Risks

1. **Quality regression for code search**: Mitigated by benchmark showing 95% equivalent quality
2. **Memory if both models load**: Mitigated by lazy loading; typical usage loads one or the other
3. **Collection dimension mismatch**: Mitigated by auto-recreation of code_units collection
