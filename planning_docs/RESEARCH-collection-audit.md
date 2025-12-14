# Collection Initialization Audit

**Created**: 2024-12-14
**Related Tickets**: R3-A (from recommendations-r1-r4.md)
**Bug References**: BUG-043, BUG-016

## Purpose

This audit documents all modules that use vector store collections, their initialization patterns, and identifies any gaps that could cause 404 errors on cold start (when collections don't yet exist).

---

## Summary

| Module | Collection | Has Ensure Pattern | Called Before Upsert | Status |
|--------|-----------|-------------------|---------------------|--------|
| `git/analyzer.py` | `commits` | Yes | Yes | OK |
| `values/store.py` | `values` | Yes | Yes | OK |
| `indexers/indexer.py` | `code_units` | Yes | Yes | OK |
| `observation/persister.py` | `ghap_*` (4 collections) | Yes | At startup | OK |
| `server/tools/memory.py` | `memories` | Yes | Yes | OK |

**All modules have proper ensure patterns.** No fixes needed.

---

## Detailed Analysis

### 1. GitAnalyzer (`src/clams/git/analyzer.py`)

**Collection**: `commits`

**Ensure Pattern**: `_ensure_commits_collection()` (lines 57-80)
- Instance method with instance-level caching (`self._collection_ensured`)
- Creates collection with dimension from `embedding_service.dimension`
- Handles "already exists" error (409) gracefully

**Called Before Upsert**: Yes
- Called in `index_commits()` at line 112 before any upserts
- Called in `search_commits()` at line 361 before searching

**Upsert Location**: Line 311 in `_upsert_commit()`

**Status**: OK - Pattern correctly implemented

---

### 2. ValueStore (`src/clams/values/store.py`)

**Collection**: `values`

**Ensure Pattern**: `_ensure_values_collection()` (lines 59-81)
- Instance method with instance-level caching (`self._collection_ensured`)
- Creates collection with dimension from `embedding_service.dimension`
- Handles "already exists" error (409) gracefully

**Called Before Upsert**: Yes
- Called in `store_value()` at line 272 before upsert at line 306
- Called in `list_values()` at line 336 before scroll operation

**Upsert Location**: Line 306 in `store_value()`

**Status**: OK - Pattern correctly implemented

---

### 3. CodeIndexer (`src/clams/indexers/indexer.py`)

**Collection**: `code_units`

**Ensure Pattern**: `_ensure_collection()` (lines 39-86)
- Instance method with instance-level caching (`self._collection_ensured`)
- Creates collection with dimension from `embedding_service.dimension`
- **Extra feature**: Checks dimension mismatch and recreates collection if needed (migration support)
- Handles "already exists" error (409) gracefully

**Called Before Upsert**: Yes
- Called in `index_file()` at line 96 before upsert at line 133
- Called in `index_directory()` at line 255 before indexing files

**Upsert Location**: Line 133 in `index_file()`

**Status**: OK - Pattern correctly implemented with bonus dimension migration

---

### 4. ObservationPersister (`src/clams/observation/persister.py`)

**Collections**: `ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause`

**Ensure Pattern**: `ensure_collections()` (lines 128-165)
- Instance method (public, not private)
- No instance-level caching (relies on caller to manage)
- Creates all 4 axis collections in a loop
- Handles "already exists" error (409) gracefully

**Called Before Upsert**: Yes - but at startup
- Called explicitly in `server/tools/__init__.py` at line 880 during `register_all_tools()`
- This happens once at server startup, before any GHAP tools are available

**Upsert Location**: Line 92 in `persist()` method

**Initialization Location**: `src/clams/server/tools/__init__.py:880`
```python
await observation_persister.ensure_collections()
```

**Status**: OK - Pattern correctly implemented (startup initialization is acceptable for this use case)

**Note**: Unlike other modules, this uses startup initialization rather than lazy per-call initialization. This is acceptable because:
1. GHAP collections are always needed when the server runs
2. The persister doesn't have a direct handle to the embedding service dimension in the persist method
3. BUG-016 was specifically fixed by adding this startup call

---

### 5. Memory Tools (`src/clams/server/tools/memory.py`)

**Collection**: `memories`

**Ensure Pattern**: `_ensure_memories_collection()` (lines 34-58)
- Module-level function with module-level caching (`_memories_collection_ensured` global)
- Creates collection with dimension from `services.semantic_embedder.dimension`
- Handles "already exists" error (409) gracefully

**Called Before Upsert**: Yes
- Called in `store_memory()` at line 81 before upsert at line 125
- Called in `retrieve_memories()` at line 150 before search
- Called in `list_memories()` at line 215 before scroll

**Upsert Location**: Line 125 in `store_memory()`

**Status**: OK - Pattern correctly implemented (module-level caching is appropriate for tool functions)

---

## Searcher Module (`src/clams/search/searcher.py`)

**Note**: The Searcher is read-only and does not create or upsert to collections. It only performs search operations on existing collections. If a collection doesn't exist, it raises `CollectionNotFoundError` with a helpful message suggesting the user index the data first.

This is the correct behavior - the Searcher should not create collections; the indexing modules are responsible for that.

---

## Collection Name Summary

| Collection Name | Created By | Used By |
|-----------------|-----------|---------|
| `commits` | `git/analyzer.py` | `git/analyzer.py`, `search/searcher.py` |
| `values` | `values/store.py` | `values/store.py`, `search/searcher.py` |
| `code_units` | `indexers/indexer.py` | `indexers/indexer.py`, `search/searcher.py` |
| `ghap_full` | `observation/persister.py` | `observation/persister.py`, `search/searcher.py`, `clustering/` |
| `ghap_strategy` | `observation/persister.py` | `observation/persister.py`, `search/searcher.py`, `clustering/` |
| `ghap_surprise` | `observation/persister.py` | `observation/persister.py`, `search/searcher.py`, `clustering/` |
| `ghap_root_cause` | `observation/persister.py` | `observation/persister.py`, `search/searcher.py`, `clustering/` |
| `memories` | `server/tools/memory.py` | `server/tools/memory.py`, `search/searcher.py` |

---

## Usage Frequency Priority

If fixes were needed, priority would be based on usage frequency:

1. **High**: `memories` - Most frequently used by agents
2. **High**: `ghap_*` collections - Used on every GHAP operation
3. **Medium**: `code_units` - Used when indexing code
4. **Medium**: `commits` - Used when indexing git history
5. **Low**: `values` - Used only when extracting learnings from clusters

---

## Pattern Variations

The codebase uses two variations of the ensure pattern:

### Pattern A: Instance-level caching (Recommended)
Used by: `GitAnalyzer`, `ValueStore`, `CodeIndexer`

```python
class MyIndexer:
    def __init__(self, ...):
        self._collection_ensured = False

    async def _ensure_collection(self) -> None:
        if self._collection_ensured:
            return
        # ... create collection ...
        self._collection_ensured = True
```

**Pros**: Clean encapsulation, works with dependency injection
**Cons**: Each instance maintains its own flag

### Pattern B: Module-level caching
Used by: `memory.py`

```python
_collection_ensured = False

async def _ensure_collection(services: ServiceContainer) -> None:
    global _collection_ensured
    if _collection_ensured:
        return
    # ... create collection ...
    _collection_ensured = True
```

**Pros**: Single flag across all callers within process
**Cons**: Global state, harder to test, doesn't work well with multiple vector stores

### Pattern C: Startup initialization
Used by: `ObservationPersister`

```python
# In __init__.py at startup:
await persister.ensure_collections()
```

**Pros**: Collections guaranteed to exist before any operations
**Cons**: Slightly slower startup, all collections created even if not used

---

## Recommendations

1. **No immediate fixes needed** - All modules have proper ensure patterns in place.

2. **Consider standardization** (R3-B): The ticket R3-B proposes creating a `CollectionMixin` class to standardize the pattern. This would be a nice-to-have for consistency but is not blocking.

3. **Add cold-start tests** (R3-D): While patterns are correct, adding integration tests that start with empty Qdrant would verify the patterns work in practice.

---

## Verification Commands

The following grep command was used to find all upsert calls:
```bash
grep -rn "vector_store.upsert\|\.upsert(" src/clams --include="*.py"
```

Results (all verified to have preceding ensure calls):
- `src/clams/observation/persister.py:92` - Startup ensure at `__init__.py:880`
- `src/clams/storage/qdrant.py:106` - This is the implementation, not a consumer
- `src/clams/values/store.py:306` - Called after `_ensure_values_collection()` at line 272
- `src/clams/git/analyzer.py:311` - Called after `_ensure_commits_collection()` at line 112
- `src/clams/server/tools/memory.py:125` - Called after `_ensure_memories_collection()` at line 81
- `src/clams/indexers/indexer.py:133` - Called after `_ensure_collection()` at line 96
