# SPEC-002-14: ObservationPersister Multi-Axis Embedding

## Summary

Implement `ObservationPersister` to embed and store resolved GHAP entries using multi-axis embedding, enabling retrieval from different semantic perspectives.

## Background

The ObservationCollector (SPEC-002-08) stores GHAP entries locally as JSON files. To enable semantic search and pattern discovery, resolved entries must be embedded and stored in the vector database. Each entry is embedded along multiple axes to support different retrieval use cases.

## Requirements

### Interface

```python
class ObservationPersister:
    """Persists resolved GHAP entries to vector store with multi-axis embeddings."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        collection_prefix: str = "ghap",
    ) -> None:
        """Initialize the persister.

        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector database for storage
            collection_prefix: Prefix for collection names (default: "ghap")
        """

    async def persist(self, entry: GHAPEntry) -> None:
        """Persist a single resolved GHAP entry.

        Creates embeddings for all applicable axes and stores them.

        Args:
            entry: Resolved GHAP entry to persist

        Raises:
            ValueError: If entry is not resolved (no outcome)
        """

    async def persist_batch(self, entries: list[GHAPEntry]) -> None:
        """Persist multiple resolved GHAP entries.

        Args:
            entries: List of resolved entries to persist

        Raises:
            ValueError: If any entry is not resolved
        """

    async def ensure_collections(self) -> None:
        """Ensure all axis collections exist.

        Creates collections if they don't exist. Safe to call multiple times.
        """
```

### Multi-Axis Embedding Strategy

Each resolved GHAP entry is embedded along **4 axes**:

#### 1. Full Axis (`{prefix}_full`)

Complete narrative for general semantic search.

**Text Template:**
```
Goal: {goal}
Hypothesis: {hypothesis}
Action: {action}
Prediction: {prediction}
Outcome: {outcome_status} - {outcome_result}
[Surprise: {surprise}]
[Lesson: {lesson_what_worked}]
```

**Metadata (stored in vector payload):**
- `ghap_id`: str - Entry ID
- `session_id`: str - Session ID
- `created_at`: float - Creation timestamp (Unix epoch seconds)
- `captured_at`: float - Resolution timestamp from `entry.outcome.captured_at` (Unix epoch seconds)
- `domain`: str - Domain enum value (e.g., "debugging") - **for filtering, not embedded**
- `strategy`: str - Strategy enum value (e.g., "systematic-elimination")
- `outcome_status`: str - "confirmed", "falsified", or "abandoned"
- `confidence_tier`: str - "gold", "silver", "bronze", or "abandoned"
- `iteration_count`: int - Number of iterations

#### 2. Strategy Axis (`{prefix}_strategy`)

Strategy performance tracking - how well does each strategy work?

**Text Template:**
```
Strategy: {strategy}
Applied to: {goal}
Outcome: {outcome_status} after {iteration_count} iteration(s)
[What worked: {lesson_what_worked}]
```

**Metadata:** Same as full axis

#### 3. Surprise Axis (`{prefix}_surprise`) - Falsified Only

Captures unexpected findings for learning from failures.

**Text Template:**
```
Expected: {prediction}
Actual: {outcome_result}
Surprise: {surprise}
Root cause: {root_cause_category} - {root_cause_description}
```

**Metadata:** Same as full axis, plus:
- `root_cause_category`: Category of failure

#### 4. Root Cause Axis (`{prefix}_root_cause`) - Falsified Only

Failure analysis for pattern recognition.

**Text Template:**
```
Category: {root_cause_category}
Description: {root_cause_description}
Context: {domain} - {strategy}
Original hypothesis: {hypothesis}
```

**Metadata:** Same as surprise axis

### Template Rendering Rules

**Optional fields** (marked with `[brackets]` in templates):
- If the field is `None` or empty, omit the entire line from the rendered text
- Example: If `surprise` is `None`, the line `[Surprise: {surprise}]` is not included

**Field access:**
- `{goal}` → `entry.goal`
- `{hypothesis}` → `entry.hypothesis`
- `{action}` → `entry.action`
- `{prediction}` → `entry.prediction`
- `{strategy}` → `entry.strategy.value`
- `{iteration_count}` → `entry.iteration_count`
- `{outcome_status}` → `entry.outcome.status.value`
- `{outcome_result}` → `entry.outcome.result`
- `{surprise}` → `entry.surprise` (if exists)
- `{lesson_what_worked}` → `entry.lesson.what_worked` (if lesson exists)
- `{lesson_takeaway}` → `entry.lesson.takeaway` (if lesson exists)
- `{root_cause_category}` → `entry.root_cause.category` (if root_cause exists)
- `{root_cause_description}` → `entry.root_cause.description` (if root_cause exists)

### Collection Management

- **Collection naming**: `{prefix}_{axis}` where prefix defaults to "ghap"
  - Collections: `ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause`
- **Vector dimension**: Must match `embedding_service.dimension` (typically 768 for Nomic)
- **Distance metric**: Cosine similarity
- **Collection creation**: Lazily on first persist, or explicitly via `ensure_collections()`
- **Why separate collections**: Each axis has different semantic focus; keeping them separate enables focused retrieval without axis filtering

### Error Handling

- **Missing outcome**: If `entry.outcome` is `None`, raise `ValueError("Entry must be resolved")`
- **Embedding failure**: Propagate `EmbeddingModelError` from embedding service
- **Storage failure**: Propagate storage errors (no retry - caller handles retries)
- **Batch operations**:
  - Validate all entries have outcomes before starting (fail fast)
  - Process entries sequentially; on first error, propagate immediately
  - No rollback needed - upserts are idempotent, partial writes are safe
  - Caller can retry the full batch or process remaining entries

### Batching Strategy

`persist_batch()` processes entries efficiently:
1. Validate all entries have outcomes (fail fast before any work)
2. For each entry, call `persist()` sequentially
3. Embedding calls are per-axis (not batched across entries for simplicity)
4. Future optimization: batch embedding calls across entries (not required for MVP)

### Dependencies

- `GHAPEntry` from `learning_memory_server.observation.models` (dataclass)
- `EmbeddingService` from `learning_memory_server.embedding.base`
- `VectorStore` from `learning_memory_server.storage.base`

### Integration Notes

**Input type**: `persist()` takes `GHAPEntry` directly (not dict). The caller passes the GHAPEntry object; the persister handles serialization internally.

**GHAP tools update required**: Current code in `server/tools/ghap.py` calls `persister.persist(resolved.to_dict())`. This should change to `persister.persist(resolved)` after implementation.

**Comment cleanup**: Remove misleading comment in `observation/utils.py` (lines 49-52) about quality assessment being done by persister - quality assessment is out of scope for this task.

## File Structure

```
src/learning_memory_server/observation/
    persister.py          # New: ObservationPersister implementation
    __init__.py           # Update: export ObservationPersister

tests/observation/
    test_persister.py     # New: Unit tests for persister
```

## Acceptance Criteria

- [ ] `ObservationPersister` class implemented in `observation/persister.py`
- [ ] `persist(entry: GHAPEntry)` creates embeddings for all applicable axes
- [ ] Surprise and root_cause axes only created for falsified entries
- [ ] Metadata payload matches schema for each axis
- [ ] `persist_batch()` processes multiple entries efficiently
- [ ] `ensure_collections()` creates collections with correct settings
- [ ] Unit tests verify each axis text template produces correct text
- [ ] Unit tests verify metadata schema for each axis
- [ ] Integration tests verify end-to-end persistence (mock embedding/storage)
- [ ] Entry without outcome raises `ValueError`
- [ ] Update `server/tools/ghap.py` to pass `GHAPEntry` directly (not `.to_dict()`)
- [ ] Remove misleading quality assessment comment from `observation/utils.py`
- [ ] All code passes mypy strict type checking
- [ ] All code passes ruff linting

## Out of Scope

- Hypothesis quality assessment (done by clustering in SPEC-002-12)
- Retrieval/search functionality (done by Searcher in SPEC-002-09)
- Automatic background persistence (caller responsibility)
