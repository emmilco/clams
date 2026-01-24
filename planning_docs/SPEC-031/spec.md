# SPEC-031: Cross-Component Integration Tests

## Problem Statement

Multiple bugs in the CLAMS codebase (BUG-006, BUG-019, BUG-027, BUG-036, BUG-040, BUG-041) have been caused by data transformation issues at component boundaries. These issues manifest in various ways:

1. **Schema mismatches**: Data stored by one component lacks fields expected by another (BUG-006: `ObservationPersister` stored incomplete GHAP payload that `ExperienceResult.from_search_result()` expected)

2. **Type mismatches**: Data serialized in one format but deserialized expecting another (BUG-027: `created_at` stored as ISO string but read expecting Unix timestamp)

3. **Validation gaps**: Invalid inputs propagate through layers before failing (BUG-036: `distribute_budget` received invalid context type, raised unhelpful KeyError)

4. **API contract violations**: Return values don't match expected types (BUG-019: `validate_value` returned `similarity=None` when clients expected a float)

5. **Duplicate/conflicting types**: Multiple type definitions for same concept (BUG-040, BUG-041: `Searcher` ABC vs concrete implementation, duplicate result types)

The existing `tests/integration/test_data_flows.py` and `tests/integration/test_round_trip.py` provide good coverage of round-trip serialization and some data flow scenarios, but they don't systematically test the data transformation contracts at each component boundary.

## Proposed Solution

Create a comprehensive suite of integration tests that verify data contracts at each component boundary in the system. These tests will:

1. Define explicit contracts for data shapes at each boundary
2. Test that data transformations preserve required fields and types
3. Verify that error cases are handled gracefully with appropriate messages
4. Catch schema drift and type mismatches before they reach production

## Component Boundaries to Test

### 1. Storage Layer Boundaries

| Boundary | Components | Data Flow | Critical Fields |
|----------|------------|-----------|-----------------|
| Persist GHAP | `ObservationCollector` -> `ObservationPersister` -> `VectorStore` | GHAPEntry -> payload dict -> Qdrant point | `ghap_id`, `axis`, `goal`, `hypothesis`, `action`, `prediction`, `outcome_status`, `outcome_result`, `created_at` (ISO), `captured_at` (timestamp), `surprise`, `root_cause`, `lesson` |
| Persist Memory | Memory tools -> `VectorStore` | Memory dict -> payload dict -> Qdrant point | `id`, `content`, `category`, `importance` (float), `tags` (list), `created_at` (ISO), `verified_at` (ISO, optional), `verification_status` |
| Persist Code | `TreeSitterIndexer` -> `VectorStore` | CodeUnit -> payload dict -> Qdrant point | `id`, `project`, `file_path`, `language`, `unit_type`, `qualified_name`, `code`, `docstring`, `line_start`, `line_end` |
| Persist Commit | Git tools -> `VectorStore` | Commit data -> payload dict -> Qdrant point | `id`, `sha`, `message`, `author`, `author_email`, `committed_at` (ISO), `files_changed` (list) |
| Persist Value | `ValueStore` -> `VectorStore` | Value data -> payload dict -> Qdrant point | `id`, `axis`, `cluster_id`, `text`, `member_count`, `avg_confidence` (float), `created_at` (ISO) |

### 2. Retrieval Layer Boundaries

| Boundary | Components | Data Flow | Critical Transformation |
|----------|------------|-----------|------------------------|
| Search Experiences | `VectorStore` -> `Searcher` -> `ExperienceResult` | Qdrant point -> SearchResult -> ExperienceResult | `from_search_result()` must find all required fields in payload |
| Search Memories | `VectorStore` -> `Searcher` -> `MemoryResult` | Qdrant point -> SearchResult -> MemoryResult | `from_search_result()` must parse `created_at` as ISO string |
| Search Code | `VectorStore` -> `Searcher` -> `CodeResult` | Qdrant point -> SearchResult -> CodeResult | `from_search_result()` must find line numbers, code content |
| Search Commits | `VectorStore` -> `Searcher` -> `CommitResult` | Qdrant point -> SearchResult -> CommitResult | `from_search_result()` must parse `committed_at` as ISO string |
| Search Values | `VectorStore` -> `Searcher` -> `ValueResult` | Qdrant point -> SearchResult -> ValueResult | `from_search_result()` must find cluster metadata |

### 3. Context Assembly Boundaries

| Boundary | Components | Data Flow | Critical Transformation |
|----------|------------|-----------|------------------------|
| Experience -> ContextItem | `Searcher` -> `ContextAssembler` | ExperienceResult -> ContextItem | `format_experience()` expects `domain`, `strategy`, `goal`, `hypothesis`, `action`, `prediction`, `outcome_status`, `outcome_result`, optional `surprise`, `lesson` |
| Memory -> ContextItem | `Searcher` -> `ContextAssembler` | MemoryResult -> ContextItem | `format_memory()` expects `content`, `category`, `importance` |
| Code -> ContextItem | `Searcher` -> `ContextAssembler` | CodeResult -> ContextItem | `format_code()` expects `unit_type`, `qualified_name`, `file_path`, `line_start`, `language`, `code`, optional `docstring` |
| Commit -> ContextItem | `Searcher` -> `ContextAssembler` | CommitResult -> ContextItem | `format_commit()` expects `sha`, `author`, `committed_at`, `message`, `files_changed` |
| Value -> ContextItem | `Searcher` -> `ContextAssembler` | ValueResult -> ContextItem | `format_value()` expects `axis`, `member_count`, `text` |
| ContextItem -> Markdown | `ContextAssembler` | ContextItem list -> FormattedContext | `assemble_markdown()` groups by source, respects token budget |
| Token Budget | `distribute_budget()` | context_types list -> budget dict | Validates input against `SOURCE_WEIGHTS` keys |

### 4. Embedding Layer Boundaries

| Boundary | Components | Data Flow | Critical Constraint |
|----------|------------|-----------|---------------------|
| Text -> Vector | `EmbeddingService` | str -> np.ndarray[float32] | Dimension must match collection (768 for Nomic) |
| Vector -> Storage | `EmbeddingService` -> `VectorStore` | np.ndarray -> Qdrant vector | Float32 precision preserved |

### 5. Tool Response Boundaries

| Boundary | Components | Data Flow | Critical Constraint |
|----------|------------|-----------|---------------------|
| validate_value | `ValueStore` -> tool response | ValidationResult -> JSON | `similarity` must be float or absent (not None) |
| list_ghap_entries | `VectorStore` -> tool response | Qdrant payload -> JSON | `created_at` must be parsed correctly (ISO string, not timestamp) |
| search_experiences | `Searcher` -> tool response | ExperienceResult list -> JSON | All required fields present, no KeyError |

## Data Flow Scenarios to Test

### Scenario 1: GHAP Complete Lifecycle (Confirmed Outcome)

```
create_ghap() -> get_current() -> update_ghap() -> resolve_ghap(confirmed)
    -> persist() -> search_experiences() -> format_experience() -> assemble_markdown()
```

**Validation checkpoints:**
1. After `create_ghap()`: Entry has valid `id`, `session_id`, `created_at`, `domain`, `strategy`
2. After `persist()`: Qdrant payload contains all fields from `_build_axis_metadata()`
3. After `search_experiences()`: `ExperienceResult` has all content fields (not just metadata)
4. After `format_experience()`: ContextItem.content is valid markdown with all sections

### Scenario 2: GHAP Falsified with Root Cause

```
create_ghap() -> resolve_ghap(falsified, surprise, root_cause, lesson)
    -> persist() -> search_experiences(axis=root_cause) -> format_experience()
```

**Validation checkpoints:**
1. After `persist()`: Entry exists in all 4 axes (full, strategy, surprise, root_cause)
2. After retrieval: `root_cause` is a dict with `category` and `description`
3. After retrieval: `lesson` is a dict with `what_worked` and `takeaway`

### Scenario 3: Memory Store and Retrieve

```
store_memory() -> retrieve_memories() -> search_memories() -> format_memory()
```

**Validation checkpoints:**
1. After storage: `importance` is float (not string or int)
2. After storage: `created_at` is ISO string (not timestamp)
3. After retrieval: `tags` is list (not comma-separated string)
4. After format: Importance displays with 2 decimal places

### Scenario 4: Code Index and Search

```
index_code() -> search_code() -> format_code() -> assemble_markdown()
```

**Validation checkpoints:**
1. After indexing: `line_start` and `line_end` are integers
2. After retrieval: `code` content is preserved (not truncated unexpectedly)
3. After format: Code block has correct language fence

### Scenario 5: Context Assembly Pipeline

```
assemble_context(types=[memories, code, experiences])
    -> parallel search all types -> deduplicate -> distribute_budget -> select_items -> format
```

**Validation checkpoints:**
1. Input validation: Invalid context type raises `InvalidContextTypeError` (not KeyError)
2. Token budget: Each source gets proportional allocation
3. Deduplication: Same content from multiple sources appears once
4. Truncation: Long items are truncated with clear indicator

### Scenario 6: Premortem Context Assembly

```
get_premortem_context(domain, strategy)
    -> search experiences (4 axes) -> search values -> format premortem markdown
```

**Validation checkpoints:**
1. Experiences grouped by axis in output
2. Values appear in "Relevant Principles" section
3. Partial failures don't crash (graceful degradation)

### Scenario 7: Value Validation Flow

```
validate_value(text, cluster_id) -> get_cluster() -> compute_similarity -> return result
```

**Validation checkpoints:**
1. Success path: `similarity` is float
2. Failure path (empty cluster): `similarity` absent or float (never None)
3. Invalid cluster: Clear error message

### Scenario 8: Datetime Round-Trip

```
datetime.now(UTC) -> .isoformat() -> store -> retrieve -> fromisoformat() -> compare
```

**Validation checkpoints:**
1. Timezone preserved through round-trip
2. Microsecond precision preserved
3. Both ISO string and timestamp formats handled consistently

## Validation Requirements

### Field Presence Validation

For each result type, validate that `from_search_result()` successfully creates an object when given a payload from actual storage. Test should fail if:
- Required field is missing in payload
- Required field has wrong type
- Optional field handling differs from expectation

### Type Consistency Validation

For each boundary crossing, validate:
- Numeric types (int vs float) are consistent
- Datetime formats (ISO string vs Unix timestamp) are consistent
- Collection types (list vs tuple) are consistent
- Optional types (None vs omitted) are consistent

### Error Message Validation

For validation failures, test that:
- Error type is specific (not generic Exception)
- Error message includes the problematic value
- Error message includes valid options (for enum-like inputs)

### Graceful Degradation Validation

For partial failures, test that:
- Some results return even if one source fails
- Error is logged but doesn't crash
- Response indicates which sources failed

## Acceptance Criteria

### Test Coverage

- [ ] Test file exists at `tests/integration/test_boundary_contracts.py`
- [ ] Tests for all 5 storage layer boundaries (GHAP, Memory, Code, Commit, Value)
- [ ] Tests for all 5 retrieval layer boundaries (5 result types)
- [ ] Tests for all 5 context assembly boundaries (5 formatters + assembly)
- [ ] Tests for embedding dimension consistency
- [ ] Tests for tool response boundaries (validate_value, list_ghap_entries, search_experiences)

### Data Contract Tests

- [ ] Each boundary test verifies required field presence
- [ ] Each boundary test verifies field types (int, float, str, list, dict)
- [ ] Each boundary test verifies datetime format handling
- [ ] Each boundary test verifies optional field handling

### Error Handling Tests

- [ ] Invalid context type raises `InvalidContextTypeError` with valid options
- [ ] Missing required field raises descriptive error (not KeyError)
- [ ] Type mismatch raises descriptive error (not TypeError)
- [ ] Partial search failures don't crash context assembly

### Regression Prevention

- [ ] Test for BUG-006: GHAP payload contains all content fields
- [ ] Test for BUG-019: validate_value similarity is never JSON null
- [ ] Test for BUG-027: created_at stored as ISO string, read correctly
- [ ] Test for BUG-036: distribute_budget rejects invalid context types
- [ ] Test for BUG-040: No duplicate result types confusion
- [ ] Test for BUG-041: Searcher ABC and concrete class compatibility

## Implementation Notes

### Test Structure

```python
# tests/integration/test_boundary_contracts.py

class TestStorageBoundaryContracts:
    """Test data contracts at storage layer boundaries."""

    async def test_ghap_persist_contract(self):
        """Verify persisted GHAP contains all required fields."""

    async def test_memory_persist_contract(self):
        """Verify persisted memory contains all required fields."""

    # ... etc


class TestRetrievalBoundaryContracts:
    """Test data contracts at retrieval layer boundaries."""

    async def test_experience_result_contract(self):
        """Verify ExperienceResult.from_search_result() handles actual payloads."""

    # ... etc


class TestContextAssemblyBoundaryContracts:
    """Test data contracts at context assembly boundaries."""

    async def test_format_experience_contract(self):
        """Verify format_experience() handles all field variations."""

    async def test_distribute_budget_validation(self):
        """Verify distribute_budget() rejects invalid types with clear message."""

    # ... etc


class TestToolResponseBoundaryContracts:
    """Test data contracts at tool response boundaries."""

    async def test_validate_value_response_contract(self):
        """Verify validate_value response never has null similarity."""

    # ... etc
```

### Contract Definition Pattern

For each boundary, define:

```python
# Expected fields for GHAP payload after persist()
GHAP_PAYLOAD_CONTRACT = {
    "required": {
        "ghap_id": str,
        "axis": str,
        "domain": str,
        "strategy": str,
        "goal": str,
        "hypothesis": str,
        "action": str,
        "prediction": str,
        "outcome_status": str,
        "outcome_result": str,
        "created_at": str,  # ISO format
        "captured_at": (int, float),  # Unix timestamp
        "confidence_tier": str,
        "iteration_count": int,
        "session_id": str,
    },
    "optional": {
        "surprise": str,
        "root_cause": dict,  # {"category": str, "description": str}
        "lesson": dict,  # {"what_worked": str, "takeaway": str}
    },
}
```

### Test Isolation

- Use test-prefixed collections to avoid polluting production data
- Clean up collections after each test
- Use MockEmbedding for deterministic tests
- Use in-memory Qdrant where possible

## Testing Requirements

- Tests require Qdrant to be running (use `pytest.mark.integration`)
- Tests should fail fast with clear messages about which contract was violated
- Tests should run in CI/CD pipeline
- Tests should complete in under 30 seconds total

## Out of Scope

- Testing MCP protocol conformance (covered by SPEC-020)
- Testing HTTP API schemas (covered by SPEC-022)
- Testing hook output schemas (covered by SPEC-020)
- Testing embedding model accuracy (unit tested separately)
- Load/performance testing (separate spec)

## Dependencies

- Existing `tests/integration/test_data_flows.py` for reference patterns
- Existing `tests/integration/test_round_trip.py` for serialization patterns
- Existing bug reports for regression test cases

## Success Metrics

1. All known data transformation bugs (BUG-006, BUG-019, BUG-027, BUG-036, BUG-040, BUG-041) would be caught by these tests
2. Tests prevent future schema drift by failing when field contracts change
3. Tests provide clear, actionable error messages when contracts are violated
