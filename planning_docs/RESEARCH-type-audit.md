# Type Audit Report

**Ticket**: R1-A
**Date**: 2024-12-14
**Status**: Complete

## Executive Summary

This audit identifies all duplicate type definitions and ABC inheritance issues in the CLAMS codebase. The analysis found:

- **2 duplicate constant definitions** (VALID_AXES)
- **2 duplicate type definitions** (ClusterInfo, RootCause/Lesson)
- **1 parallel type hierarchy** (CommitResult vs Commit/CommitSearchResult)
- **0 ABC inheritance violations** (all ABCs properly inherited)

The codebase is generally well-structured with clear canonical sources for most types.

---

## 1. Duplicate Constant Definitions

### 1.1 VALID_AXES

| Location | Definition | Type |
|----------|------------|------|
| `src/clams/server/tools/enums.py:45` | `VALID_AXES = ["full", "strategy", "surprise", "root_cause"]` | `list[str]` |
| `src/clams/values/store.py:18` | `VALID_AXES = {"full", "strategy", "surprise", "root_cause"}` | `set[str]` |

**Field Differences**: Same values, different container types (list vs set).

**Canonical**: `src/clams/server/tools/enums.py` - This is the central location for all enum/constant definitions with validation helpers.

**Action**:
- **DELETE**: `src/clams/values/store.py:18` (`VALID_AXES`)
- **KEEP**: `src/clams/server/tools/enums.py:45` (`VALID_AXES`)
- **UPDATE**: `values/store.py` should import from `server/tools/enums.py`

---

## 2. Duplicate Type Definitions

### 2.1 ClusterInfo

| Location | Fields |
|----------|--------|
| `src/clams/clustering/types.py:20` | `label: int`, `centroid: npt.NDArray[np.float32]`, `member_ids: list[str]`, `size: int`, `avg_weight: float` |
| `src/clams/values/types.py:37` | `cluster_id: str`, `axis: str`, `label: int`, `centroid: Vector`, `member_ids: list[str]`, `size: int`, `avg_weight: float` |

**Field Differences**:
- `values/types.py` adds: `cluster_id: str`, `axis: str`
- `values/types.py` uses `Vector` type alias instead of `npt.NDArray[np.float32]` (equivalent)

**Analysis**: These serve different purposes:
- `clustering/types.ClusterInfo`: Raw clustering output from HDBSCAN algorithm
- `values/types.ClusterInfo`: Enriched cluster info for value storage (adds cluster_id and axis context)

**Canonical**: Both are valid for their contexts; this is composition, not duplication.

**Action**:
- **KEEP BOTH**: Different semantic meaning
- **CONSIDER**: Rename `clustering/types.ClusterInfo` to `RawClusterInfo` or have `values/types.ClusterInfo` wrap `clustering/types.ClusterInfo`

### 2.2 RootCause

| Location | Fields |
|----------|--------|
| `src/clams/search/results.py:10` | `category: str`, `description: str` |
| `src/clams/observation/models.py:55` | `category: str`, `description: str`, `to_dict()`, `from_dict()` |

**Field Differences**:
- `observation/models.py` adds serialization methods (`to_dict()`, `from_dict()`)
- Otherwise identical fields

**Analysis**:
- `search/results.py:RootCause`: Simplified dataclass for search results
- `observation/models.py:RootCause`: Full-featured model with serialization for GHAP persistence

**Canonical**: `observation/models.py` - This is the source of truth for GHAP data structures.

**Action**:
- **KEEP**: `src/clams/observation/models.py:RootCause` (canonical with methods)
- **REFACTOR**: `src/clams/search/results.py:RootCause` should import from `observation/models.py` or use a TypedDict for simpler typing

### 2.3 Lesson

| Location | Fields |
|----------|--------|
| `src/clams/search/results.py:17` | `what_worked: str`, `takeaway: str \| None` |
| `src/clams/observation/models.py:77` | `what_worked: str`, `takeaway: str \| None = None`, `to_dict()`, `from_dict()` |

**Field Differences**:
- `observation/models.py` adds serialization methods
- Otherwise identical fields

**Analysis**: Same situation as RootCause.

**Canonical**: `observation/models.py`

**Action**:
- **KEEP**: `src/clams/observation/models.py:Lesson` (canonical with methods)
- **REFACTOR**: `src/clams/search/results.py:Lesson` should import from `observation/models.py`

---

## 3. Parallel Type Hierarchies (Not True Duplicates)

### 3.1 Commit Types

| Location | Class Name | Purpose |
|----------|------------|---------|
| `src/clams/git/base.py:50` | `Commit` | Raw git commit data model |
| `src/clams/git/base.py:64` | `CommitSearchResult` | Commit with search score (wraps `Commit`) |
| `src/clams/search/results.py:227` | `CommitResult` | Flattened search result for API responses |

**Field Comparison**:

| Field | `Commit` | `CommitSearchResult` | `CommitResult` |
|-------|----------|---------------------|----------------|
| sha | Yes | via commit | Yes |
| message | Yes | via commit | Yes |
| author | Yes | via commit | Yes |
| author_email | Yes | via commit | Yes |
| timestamp/committed_at | `timestamp` | via commit | `committed_at` |
| files_changed | Yes | via commit | Yes |
| insertions/deletions | Yes | via commit | No |
| score | No | Yes | Yes |
| id | No | No | Yes |

**Analysis**: These are intentionally different:
- `Commit`: Domain model for git operations
- `CommitSearchResult`: Internal search result (wraps Commit)
- `CommitResult`: API-facing search result with `from_search_result()` factory

**Action**:
- **KEEP ALL**: Different layers, different purposes
- No changes needed

---

## 4. ABC Inheritance Audit

### 4.1 Abstract Base Classes Defined

| ABC | Location | Concrete Implementations |
|-----|----------|-------------------------|
| `Searcher` | `context/searcher_types.py:33` | `search/searcher.py:71` (inherits correctly) |
| `VectorStore` | `storage/base.py:34` | `storage/qdrant.py:33`, `storage/memory.py:10` |
| `EmbeddingService` | `embedding/base.py:32` | `embedding/nomic.py:14`, `embedding/minilm.py:14`, `embedding/mock.py:10` |
| `GitReader` | `git/base.py:145` | `git/reader.py:23` |
| `CodeParser` | `indexers/base.py:65` | `indexers/tree_sitter.py:119` |

### 4.2 Inheritance Verification

All concrete implementations properly inherit from their ABCs:

```python
# Verified in code:
class Searcher(SearcherABC)           # search/searcher.py:71
class QdrantVectorStore(VectorStore)  # storage/qdrant.py:33
class InMemoryVectorStore(VectorStore) # storage/memory.py:10
class NomicEmbedding(EmbeddingService) # embedding/nomic.py:14
class MiniLMEmbedding(EmbeddingService) # embedding/minilm.py:14
class MockEmbedding(EmbeddingService)  # embedding/mock.py:10
class GitPythonReader(GitReader)       # git/reader.py:23
class TreeSitterParser(CodeParser)     # indexers/tree_sitter.py:119
```

**Status**: All ABCs have proper concrete implementations with correct inheritance.

**Historical Note**: BUG-041 previously found that `search/searcher.py:Searcher` did not inherit from `context/searcher_types.py:Searcher`. This has been fixed.

---

## 5. Result Type Re-exports (Correct Pattern)

`src/clams/context/searcher_types.py` correctly re-exports from `src/clams/search/results.py`:

```python
from clams.search.results import (
    CodeResult,
    CommitResult,
    ExperienceResult,
    Lesson,
    MemoryResult,
    RootCause,
    ValueResult,
)
```

**Status**: This is the correct pattern established after BUG-040 fix.

---

## 6. Enum/Constant Consolidation Status

All enum constants in `server/tools/enums.py` are correctly used:

| Constant | Defined In | Used By |
|----------|-----------|---------|
| `DOMAINS` | `enums.py:6` | `__init__.py:20,470,593,724` |
| `STRATEGIES` | `enums.py:19` | `__init__.py:23,475,518` |
| `ROOT_CAUSE_CATEGORIES` | `enums.py:32` | `__init__.py:22,553` |
| `VALID_AXES` | `enums.py:45` | `__init__.py:24,618,678,693,718` |
| `OUTCOME_STATUS_VALUES` | `enums.py:48` | `__init__.py:21,537,598,729` |

**Status**: `server/tools/__init__.py` correctly imports and uses all constants from `enums.py`.

**Issue**: `values/store.py` defines its own `VALID_AXES` instead of importing (see Section 1.1).

---

## 7. Summary: Actions Required

### DELETE (Duplicates to Remove)

| File | Line | Definition | Reason |
|------|------|------------|--------|
| `values/store.py` | 18 | `VALID_AXES = {"full", "strategy", "surprise", "root_cause"}` | Import from `server/tools/enums.py` instead |

### KEEP (Canonical Sources)

| File | Definition | Notes |
|------|------------|-------|
| `server/tools/enums.py:45` | `VALID_AXES` | Canonical constant definition |
| `server/tools/enums.py:6` | `DOMAINS` | Canonical constant definition |
| `server/tools/enums.py:19` | `STRATEGIES` | Canonical constant definition |
| `server/tools/enums.py:32` | `ROOT_CAUSE_CATEGORIES` | Canonical constant definition |
| `server/tools/enums.py:48` | `OUTCOME_STATUS_VALUES` | Canonical constant definition |
| `search/results.py` | All `*Result` dataclasses | Canonical search result types |
| `observation/models.py` | `RootCause`, `Lesson`, `GHAPEntry` | Canonical GHAP models |
| `clustering/types.py` | `ClusterInfo`, `ClusterResult` | Canonical clustering types |
| `values/types.py` | `ClusterInfo`, `Value`, `Experience`, `ValidationResult` | Values-specific types |
| `storage/base.py` | `SearchResult`, `VectorStore` | Canonical storage types |
| `git/base.py` | `Commit`, `GitReader`, etc. | Canonical git types |

### REFACTOR (Recommended Improvements)

| Issue | Current State | Recommended Change | Priority |
|-------|--------------|-------------------|----------|
| `values/store.py` imports | Local `VALID_AXES` | Import from `server/tools/enums.py` | P1 |
| `search/results.py` RootCause/Lesson | Duplicate definitions | Import from `observation/models.py` | P2 |
| `values/types.ClusterInfo` | Similar to `clustering/types.ClusterInfo` | Consider composition or renaming | P3 |

---

## 8. Related Bug References

- **BUG-040**: `CodeResult` was defined twice with different field names (`start_line`/`end_line` vs `line_start`/`line_end`). **FIXED** - `context/searcher_types.py` now re-exports from `search/results.py`.

- **BUG-041**: Concrete `Searcher` in `search/searcher.py` did not inherit from abstract `Searcher` in `context/searcher_types.py`. **FIXED** - Now properly inherits.

- **BUG-026**: JSON schema enums in `tools/__init__.py` differed from validation enums in `tools/enums.py`. **FIXED** - `__init__.py` now imports from `enums.py`.

---

## 9. Files Audited

1. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/context/searcher_types.py`
2. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/search/results.py`
3. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/search/searcher.py`
4. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/search/collections.py`
5. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/enums.py`
6. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/server/tools/__init__.py`
7. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/store.py`
8. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/values/types.py`
9. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/clustering/types.py`
10. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/observation/models.py`
11. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/git/base.py`
12. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/storage/base.py`
13. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/embedding/base.py`
14. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/indexers/base.py`
15. `/Users/elliotmilco/Documents/GitHub/clams/src/clams/context/models.py`
