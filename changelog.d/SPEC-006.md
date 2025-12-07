## SPEC-006: Dual Embedding Model Support for Faster Code Indexing

### Summary
Implemented dual embedding model architecture to accelerate code indexing while maintaining quality for memory/GHAP operations. Code indexing now uses MiniLM (384-dim, fast) while memories/GHAP use Nomic (768-dim, quality).

### Changes
- Added `MiniLMEmbedding` class for fast code embeddings
- Added `EmbeddingRegistry` for lazy-loaded dual embedding models
- Added `code_model` and `semantic_model` to `ServerSettings` (configurable via env vars)
- Added `CollectionInfo` dataclass and `get_collection_info()` to `VectorStore` protocol
- Updated `ServiceContainer` to hold both `code_embedder` and `semantic_embedder`
- Updated `CodeIndexer._ensure_collection()` to handle dimension migration
- Updated server initialization to use embedding registry (models load on first use)
- Updated code tools to use `code_embedder` (MiniLM)
- Updated memory/GHAP/git tools to use `semantic_embedder` (Nomic)

### Migration
- Existing `code_units` collection will auto-recreate on first `index_codebase` call if dimension mismatches
- No user action required - collections auto-migrate
- Existing memory/GHAP data unaffected (no dimension change)
