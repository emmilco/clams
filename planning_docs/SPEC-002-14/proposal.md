# Technical Proposal: ObservationPersister Multi-Axis Embedding

**Task**: SPEC-002-14
**Author**: Architect
**Date**: 2025-12-04

## 1. Problem Statement

The ObservationCollector (SPEC-002-08) stores resolved GHAP entries locally as JSON files. To enable semantic search, pattern discovery, and learning from past experiences, these entries must be embedded and stored in the vector database.

Key challenges:
- **Multi-perspective retrieval**: Different use cases require different semantic views of the same data (e.g., "show me all instances where systematic-elimination worked" vs "what are common root causes in debugging")
- **Efficient storage**: Each axis needs its own collection to enable focused retrieval without expensive filtering
- **Template rendering**: Converting structured GHAPEntry data to natural language text for embedding
- **Conditional embedding**: Some axes (surprise, root_cause) only apply to falsified entries

## 2. Proposed Solution

Implement `ObservationPersister` as a multi-axis embedding system that:

1. Takes a resolved `GHAPEntry` object as input
2. Renders 2-4 text templates (depending on outcome status)
3. Generates embeddings for each template using `EmbeddingService`
4. Stores vectors + metadata in separate collections using `VectorStore`

### 2.1 Architecture

```
GHAPEntry (resolved) → ObservationPersister
                          ↓
                     Template Rendering
                          ↓
                     [full, strategy, surprise?, root_cause?]
                          ↓
                     EmbeddingService.embed()
                          ↓
                     VectorStore.upsert()
                          ↓
                     [ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause]
```

### 2.2 Class Structure

```python
class ObservationPersister:
    """Persists resolved GHAP entries to vector store with multi-axis embeddings."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        collection_prefix: str = "ghap",
    ) -> None:
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._collection_prefix = collection_prefix
        self._logger = structlog.get_logger(__name__)

    async def persist(self, entry: GHAPEntry) -> None:
        """Persist a single resolved GHAP entry."""
        # Implementation details below

    async def persist_batch(self, entries: list[GHAPEntry]) -> None:
        """Persist multiple resolved GHAP entries."""
        # Implementation details below

    async def ensure_collections(self) -> None:
        """Ensure all axis collections exist."""
        # Implementation details below
```

## 3. Template Rendering Implementation

### 3.1 Template Engine

We'll use a simple template rendering approach with optional field handling:

```python
def _render_template(self, template: str, entry: GHAPEntry) -> str:
    """Render a template with optional fields.

    Templates contain:
    - {field_name} for required fields
    - [text with {field_name}] for optional fields

    Optional sections are removed if the field is None or empty.

    Limitations:
    - Does not support nested brackets (e.g., [[inner]]).
    - Nested brackets will fail gracefully by not matching the pattern.
    - Current templates don't require nesting, so this is acceptable.
    """
    import re

    # Extract all fields for this entry
    fields = self._extract_fields(entry)

    # Step 1: Extract optional sections (marked with [brackets])
    # Pattern: [any text with {field_name} placeholders]
    optional_pattern = re.compile(r'\[([^\[\]]+)\]')

    def process_optional(match: re.Match[str]) -> str:
        section = match.group(1)

        # Extract field names from this section using {field_name} pattern
        field_pattern = re.compile(r'\{(\w+)\}')
        field_names = field_pattern.findall(section)

        # Check if all fields exist and are non-None/non-empty
        for field_name in field_names:
            if field_name not in fields or not fields[field_name]:
                # Field is missing or empty, remove entire section
                return ""

        # All fields present, render the section (without brackets)
        return section

    # Step 2: Process all optional sections
    rendered = optional_pattern.sub(process_optional, template)

    # Step 3: Render remaining template with all required fields
    # Use str.format() to replace {field_name} placeholders
    try:
        return rendered.format(**fields)
    except KeyError as e:
        # Missing required field
        raise ValueError(f"Template rendering failed: missing field {e}")
```

### 3.2 Templates

#### Full Axis
```python
TEMPLATE_FULL = """Goal: {goal}
Hypothesis: {hypothesis}
Action: {action}
Prediction: {prediction}
Outcome: {outcome_status} - {outcome_result}
[Surprise: {surprise}]
[Lesson: {lesson_what_worked}]"""
```

#### Strategy Axis
```python
TEMPLATE_STRATEGY = """Strategy: {strategy}
Applied to: {goal}
Outcome: {outcome_status} after {iteration_count} iteration(s)
[What worked: {lesson_what_worked}]"""
```

#### Surprise Axis (falsified only)
```python
TEMPLATE_SURPRISE = """Expected: {prediction}
Actual: {outcome_result}
Surprise: {surprise}
Root cause: {root_cause_category} - {root_cause_description}"""
```

#### Root Cause Axis (falsified only)
```python
TEMPLATE_ROOT_CAUSE = """Category: {root_cause_category}
Description: {root_cause_description}
Context: {domain} - {strategy}
Original hypothesis: {hypothesis}"""
```

### 3.3 Field Extraction

```python
def _extract_fields(self, entry: GHAPEntry) -> dict[str, str]:
    """Extract all fields from entry for template rendering."""
    fields = {
        "goal": entry.goal,
        "hypothesis": entry.hypothesis,
        "action": entry.action,
        "prediction": entry.prediction,
        # domain and strategy are non-Optional fields in GHAPEntry model,
        # so .value access is safe (no None check needed)
        "domain": entry.domain.value,
        "strategy": entry.strategy.value,
        "iteration_count": str(entry.iteration_count),
        "outcome_status": entry.outcome.status.value,
        "outcome_result": entry.outcome.result,
    }

    # Optional fields
    if entry.surprise:
        fields["surprise"] = entry.surprise
    if entry.lesson:
        if entry.lesson.what_worked:
            fields["lesson_what_worked"] = entry.lesson.what_worked
        if entry.lesson.takeaway:
            fields["lesson_takeaway"] = entry.lesson.takeaway
    if entry.root_cause:
        fields["root_cause_category"] = entry.root_cause.category
        fields["root_cause_description"] = entry.root_cause.description

    return fields
```

## 4. Collection Management Strategy

### 4.1 Collection Naming

Collections follow the pattern `{prefix}_{axis}`:
- `ghap_full`
- `ghap_strategy`
- `ghap_surprise`
- `ghap_root_cause`

The prefix is configurable (default: "ghap") to support testing and multi-tenant scenarios.

### 4.2 Collection Creation

```python
async def ensure_collections(self) -> None:
    """Ensure all axis collections exist.

    Creates collections if they don't exist. Safe to call multiple times.

    Note: VectorStore.create_collection() raises ValueError if collection
    already exists. This is the documented behavior observed in the codebase
    (see indexers/indexer.py lines 58-61) and matches both InMemoryVectorStore
    and QdrantVectorStore implementations.
    """
    axes = ["full", "strategy", "surprise", "root_cause"]
    dimension = self._embedding_service.dimension  # 768 for Nomic

    for axis in axes:
        collection_name = f"{self._collection_prefix}_{axis}"
        try:
            await self._vector_store.create_collection(
                name=collection_name,
                dimension=dimension,
                distance="cosine",
            )
            self._logger.info(
                "collection_created",
                collection=collection_name,
                dimension=dimension,
            )
        except ValueError as e:
            # Collection already exists - this is expected and safe
            # ValueError is the documented exception for duplicate collections
            self._logger.debug(
                "collection_already_exists",
                collection=collection_name,
                error=str(e),
            )
```

### 4.3 Why Separate Collections?

- **Semantic focus**: Each collection has entries with similar semantic structure
- **Efficient retrieval**: No need to filter by axis type during search
- **Different densities**: Not all entries have surprise/root_cause, so these collections are sparser
- **Collection-level optimization**: Can tune retrieval parameters per axis

## 5. Persistence Flow

### 5.1 Single Entry Persistence

```python
async def persist(self, entry: GHAPEntry) -> None:
    """Persist a single resolved GHAP entry."""

    # 1. Validation
    if entry.outcome is None:
        raise ValueError("Entry must be resolved (outcome must be set)")

    # 2. Extract metadata (shared across all axes)
    metadata = self._build_metadata(entry)

    # 3. Determine which axes to embed
    axes_to_embed = self._determine_axes(entry)

    # 4. For each axis: render template, embed, upsert
    for axis, template in axes_to_embed.items():
        # Render text
        text = self._render_axis_text(entry, axis, template)

        # Generate embedding
        vector = await self._embedding_service.embed(text)

        # Build axis-specific metadata (may add fields like root_cause_category)
        axis_metadata = self._build_axis_metadata(entry, axis, metadata)

        # Store in collection
        collection_name = f"{self._collection_prefix}_{axis}"
        await self._vector_store.upsert(
            collection=collection_name,
            id=entry.id,  # Same ID across all axes for cross-referencing
            vector=vector,
            payload=axis_metadata,
        )

        self._logger.info(
            "axis_persisted",
            ghap_id=entry.id,
            axis=axis,
            collection=collection_name,
        )
```

### 5.2 Axis Determination Logic

```python
def _determine_axes(self, entry: GHAPEntry) -> dict[str, str]:
    """Determine which axes to embed based on entry state.

    Edge case handling:
    - If root_cause exists but surprise is None, skip both surprise and
      root_cause axes (root_cause axis template requires surprise text).
      This is logged as a warning since it indicates incomplete data.
    """
    axes = {
        "full": TEMPLATE_FULL,
        "strategy": TEMPLATE_STRATEGY,
    }

    # Only add surprise and root_cause axes for falsified entries
    if entry.outcome.status == OutcomeStatus.FALSIFIED:
        if entry.surprise:  # Must have surprise text
            axes["surprise"] = TEMPLATE_SURPRISE
            if entry.root_cause:  # Must have root_cause object
                axes["root_cause"] = TEMPLATE_ROOT_CAUSE
        elif entry.root_cause:
            # Root cause exists but no surprise text - skip both axes
            # This is a data quality issue that should be logged
            self._logger.warning(
                "root_cause_without_surprise",
                ghap_id=entry.id,
                note="Skipping root_cause axis (requires surprise text)",
            )

    return axes
```

### 5.3 Metadata Construction

```python
def _build_metadata(self, entry: GHAPEntry) -> dict[str, Any]:
    """Build base metadata payload (shared across all axes)."""
    return {
        "ghap_id": entry.id,
        "session_id": entry.session_id,
        # Timestamps are float (Unix epoch with fractional seconds)
        "created_at": entry.created_at.timestamp(),
        "captured_at": entry.outcome.captured_at.timestamp(),
        "domain": entry.domain.value,
        "strategy": entry.strategy.value,
        "outcome_status": entry.outcome.status.value,
        "confidence_tier": entry.confidence_tier.value if entry.confidence_tier else None,
        "iteration_count": entry.iteration_count,
    }

def _build_axis_metadata(
    self, entry: GHAPEntry, axis: str, base_metadata: dict[str, Any]
) -> dict[str, Any]:
    """Add axis-specific metadata fields."""
    metadata = base_metadata.copy()

    # Add root_cause_category for surprise and root_cause axes
    if axis in ["surprise", "root_cause"] and entry.root_cause:
        metadata["root_cause_category"] = entry.root_cause.category

    return metadata
```

### 5.4 Batch Persistence

```python
async def persist_batch(self, entries: list[GHAPEntry]) -> None:
    """Persist multiple resolved GHAP entries.

    Strategy:
    - Validate all entries first (fail fast)
    - Process entries sequentially
    - On first error, propagate immediately
    - No rollback needed (upserts are idempotent)
    """
    # 1. Validate all entries have outcomes
    for entry in entries:
        if entry.outcome is None:
            raise ValueError(
                f"Entry {entry.id} must be resolved (outcome must be set)"
            )

    # 2. Process entries sequentially
    for entry in entries:
        await self.persist(entry)

    self._logger.info("batch_persisted", count=len(entries))
```

## 6. Error Handling Approach

### 6.1 Error Categories

1. **Validation errors** (ValueError):
   - Entry not resolved (no outcome)
   - Invalid entry state
   - → Raised immediately, caller must fix entry

2. **Embedding errors** (EmbeddingModelError):
   - Model inference failure
   - → Propagated to caller, caller decides retry strategy

3. **Storage errors** (Qdrant/network errors):
   - Connection failures, timeouts
   - → Propagated to caller, caller decides retry strategy

### 6.2 Error Handling Strategy

```python
async def persist(self, entry: GHAPEntry) -> None:
    """Persist with explicit error handling."""
    # Validation errors (immediate)
    if entry.outcome is None:
        raise ValueError("Entry must be resolved (outcome must be set)")

    try:
        # Embed and store
        # ... implementation ...
    except EmbeddingModelError as e:
        self._logger.error(
            "embedding_failed",
            ghap_id=entry.id,
            error=str(e),
        )
        raise  # Propagate to caller
    except Exception as e:
        # Storage or other errors
        self._logger.error(
            "persist_failed",
            ghap_id=entry.id,
            error=str(e),
        )
        raise  # Propagate to caller
```

### 6.3 Idempotency

- **Upsert operation**: VectorStore.upsert() is idempotent (same ID overwrites)
- **Retry safety**: If persist() fails partway through (e.g., after 2 of 4 axes), caller can retry the full operation safely
- **No cleanup needed**: Partial writes don't corrupt state

## 7. Test Strategy

### 7.1 Unit Tests

**Template Rendering Tests** (`test_persister_templates.py`):
```python
def test_render_full_axis_with_all_fields():
    """Verify full template renders correctly with all optional fields."""

def test_render_full_axis_without_optional_fields():
    """Verify optional fields are omitted when None."""

def test_render_strategy_axis():
    """Verify strategy template renders correctly."""

def test_render_surprise_axis():
    """Verify surprise template for falsified entries."""

def test_render_root_cause_axis():
    """Verify root_cause template for falsified entries."""
```

**Metadata Tests**:
```python
def test_build_metadata_structure():
    """Verify metadata contains all required fields."""

def test_metadata_timestamp_conversion():
    """Verify datetime → Unix epoch conversion."""

def test_axis_specific_metadata():
    """Verify root_cause_category added for surprise/root_cause axes."""
```

**Axis Determination Tests**:
```python
def test_confirmed_entry_gets_full_and_strategy_only():
    """Confirmed entries should only get full and strategy axes."""

def test_falsified_entry_with_surprise_gets_all_axes():
    """Falsified with surprise/root_cause gets all 4 axes."""

def test_falsified_without_surprise_skips_surprise_axis():
    """Falsified without surprise field skips surprise axis."""
```

**Edge Case Tests**:
```python
def test_render_with_empty_string_vs_none():
    """Verify empty string "" vs None are handled correctly for optional fields."""

def test_entry_with_no_confidence_tier():
    """Verify metadata construction when confidence_tier is None."""

def test_unicode_emoji_in_fields():
    """Verify template rendering handles unicode/emoji correctly."""

def test_very_long_field_values():
    """Verify handling of very long field values (e.g., 10KB text)."""

def test_concurrent_persist_calls():
    """Verify concurrent calls to persist() are idempotent (same entry)."""

def test_nested_brackets_in_template():
    """Verify graceful failure/error for nested optional sections [[inner]]."""

def test_special_regex_chars_in_field_values():
    """Verify template handles regex special chars in field values: [ ] { } ( ) . * + ? ^ $ \\ |"""

def test_all_confidence_tier_values():
    """Verify metadata construction for all ConfidenceTier enum values (gold, silver, bronze, abandoned)."""

def test_literal_template_syntax_in_fields():
    """Verify fields containing literal text like '{field}' or '[optional]' are rendered correctly."""

def test_root_cause_without_surprise():
    """Verify root_cause axis is skipped when root_cause exists but surprise is None (logs warning)."""
```

### 7.2 Integration Tests

**End-to-End Persistence** (`test_persister_integration.py`):
```python
@pytest.mark.asyncio
async def test_persist_confirmed_entry():
    """Test persisting a confirmed entry with mocks."""
    # Given: mock EmbeddingService and VectorStore
    # When: persist(confirmed_entry)
    # Then: verify embed() called 2x (full, strategy)
    # Then: verify upsert() called 2x with correct collections

@pytest.mark.asyncio
async def test_persist_falsified_entry_with_surprise():
    """Test persisting a falsified entry with surprise."""
    # Given: falsified entry with surprise and root_cause
    # When: persist(entry)
    # Then: verify embed() called 4x
    # Then: verify upsert() called 4x
    # Then: verify root_cause_category in surprise/root_cause metadata

@pytest.mark.asyncio
async def test_persist_batch():
    """Test batch persistence."""
    # Given: list of resolved entries
    # When: persist_batch(entries)
    # Then: verify all entries persisted

@pytest.mark.asyncio
async def test_persist_without_outcome_raises():
    """Test that unresolved entry raises ValueError."""
    # Given: entry without outcome
    # When: persist(entry)
    # Then: raises ValueError
```

**Collection Management Tests**:
```python
@pytest.mark.asyncio
async def test_ensure_collections_creates_all():
    """Test that ensure_collections creates all 4 collections."""

@pytest.mark.asyncio
async def test_ensure_collections_idempotent():
    """Test that calling ensure_collections twice is safe."""
```

### 7.3 Error Handling Tests

```python
@pytest.mark.asyncio
async def test_embedding_failure_propagates():
    """Test that EmbeddingModelError is propagated."""

@pytest.mark.asyncio
async def test_storage_failure_propagates():
    """Test that storage errors are propagated."""

@pytest.mark.asyncio
async def test_batch_fails_on_first_invalid_entry():
    """Test that persist_batch validates all entries upfront."""
```

## 8. Implementation Checklist

### Phase 1: Core Implementation
- [ ] Create `observation/persister.py` with class skeleton
- [ ] Implement template rendering logic with optional field handling
- [ ] Implement `_extract_fields()` helper
- [ ] Implement `_determine_axes()` logic
- [ ] Implement `_build_metadata()` and `_build_axis_metadata()`
- [ ] Implement `persist()` method
- [ ] Implement `persist_batch()` method
- [ ] Implement `ensure_collections()` method

### Phase 2: Testing
- [ ] Write template rendering unit tests
- [ ] Write metadata construction tests
- [ ] Write axis determination tests
- [ ] Write integration tests with mocks
- [ ] Write error handling tests
- [ ] Verify 100% code coverage for persister.py

### Phase 3: Integration Updates
- [ ] Export `ObservationPersister` from `observation/__init__.py`
- [ ] Update `observation/utils.py`: Remove quality assessment comment (lines 49-52)
- [ ] Update `server/tools/ghap.py` (if it exists): Change `persister.persist(resolved.to_dict())` to `persister.persist(resolved)` - note that this file may not exist yet, so update only if present

### Phase 4: Type Checking & Linting
- [ ] Run `mypy --strict` on persister.py
- [ ] Run `ruff check` and fix any issues
- [ ] Ensure all tests pass

## 9. Dependencies

### Required Imports
```python
import re
from dataclasses import asdict
from typing import Any

import structlog

from ..embedding.base import EmbeddingService, EmbeddingModelError
from ..storage.base import VectorStore
from .models import GHAPEntry, OutcomeStatus
```

### External Dependencies
All dependencies already exist in the codebase:
- `structlog` (logging)
- `EmbeddingService` interface (implemented by NomicEmbedding)
- `VectorStore` interface (implemented by QdrantVectorStore)
- `GHAPEntry` dataclass (fully defined)

## 10. Future Optimizations (Out of Scope)

These are explicitly **not** part of the MVP but noted for future consideration:

1. **Cross-entry batching**: Batch embedding calls across multiple entries in `persist_batch()`
2. **Parallel axis embedding**: Embed all axes concurrently using asyncio.gather()
3. **Caching**: Cache rendered templates if the same entry is persisted multiple times
4. **Quality assessment**: Use clustering (SPEC-002-12) to detect bronze-tier hypotheses
5. **Incremental updates**: Support updating only specific axes without re-embedding all

## 11. Open Questions

**None** - All interfaces and requirements are well-defined in the spec.

## 12. Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Template rendering bugs | High | Medium | Comprehensive unit tests with edge cases |
| Embedding service failures | Medium | Low | Error propagation, caller handles retries |
| Storage failures | Medium | Low | Idempotent upserts, safe to retry |
| Memory usage (batch) | Low | Low | Sequential processing prevents memory spikes |

## 13. Success Criteria

- [ ] All acceptance criteria from spec met
- [ ] 100% test coverage on persister.py
- [ ] Type checking passes (mypy --strict)
- [ ] Linting passes (ruff)
- [ ] Integration tests verify end-to-end flow
- [ ] Error cases properly handled and tested
- [ ] Documentation comments complete
