# SPEC-002-15: MCP Tools for GHAP and Learning

## Overview

Implement MCP tool interfaces for GHAP tracking and learning features. These tools enable Claude Code agents to track working state through Goal-Hypothesis-Action-Prediction entries, trigger clustering, form values, and search experiences.

This spec complements SPEC-002-11 (memory, code, git tools) by adding the intelligence layer: GHAP state management, experience clustering, and value formation.

### Tool Audiences

Different tool groups serve different users:

| Tool Group | Primary User | When Used |
|------------|--------------|-----------|
| **GHAP tools** | Working agents | During active tasks - agents track their hypotheses and outcomes |
| **Learning tools** | `/retro` process | Periodic retrospective ritual - clustering experiences and forming values |
| **Search tools** | ContextAssembler | Context assembly for new tasks; also available for ad-hoc reactive search |

This distinction matters for UX: GHAP tools should be low-friction for frequent use, while learning tools can be more detailed since they're used in a dedicated retrospective session.

## Dependencies

### Completed
- SPEC-002-02: EmbeddingService
- SPEC-002-03: VectorStore
- SPEC-002-04: SQLite metadata store
- SPEC-002-05: MCP server skeleton

### In Progress (will be completed before this task)
- SPEC-002-10: ObservationCollector + ObservationPersister
- SPEC-002-09: Searcher
- SPEC-002-12: Clusterer (HDBSCAN)
- SPEC-002-13: ValueStore

## Components

This spec defines three tool modules:

1. **GHAP Tools** (`server/tools/ghap.py`) - Track agent working state (goal, hypothesis, action, prediction)
2. **Learning Tools** (`server/tools/learning.py`) - Clustering, value formation, experience search
3. **Search Tools** (`server/tools/search.py`) - Semantic search across experiences

Each module registers its tools with the MCP server and wires to underlying services.

---

## GHAP Tools

### Purpose

Enable Claude Code agents to track their working state through structured GHAP entries, supporting the learning feedback loop.

### Tool Definitions

#### start_ghap

**Purpose**: Begin tracking a new GHAP entry.

**Input Schema**:
```python
{
    "domain": str,            # Required: One of: debugging, refactoring, feature, testing, configuration, documentation, performance, security, integration
    "strategy": str,          # Required: One of: systematic-elimination, trial-and-error, research-first, divide-and-conquer, root-cause-analysis, copy-from-similar, check-assumptions, read-the-error, ask-user
    "goal": str,              # Required: What meaningful change are you trying to make?
    "hypothesis": str,        # Required: What do you believe about the situation?
    "action": str,            # Required: What are you doing based on this belief?
    "prediction": str,        # Required: If your hypothesis is correct, what will you observe?
}
```

**Output Schema**:
```python
{
    "id": str,                # Generated GHAP entry ID
    "domain": str,
    "strategy": str,
    "goal": str,
    "hypothesis": str,
    "action": str,
    "prediction": str,
    "created_at": str,        # ISO timestamp (UTC)
}
```

**Behavior**:
1. Validate inputs (domain and strategy enums, text length)
2. Check if there's already an active GHAP entry
3. If active entry exists, warn but allow (orphaned entries handled by collector)
4. Delegate to ObservationCollector.create_ghap()
5. Return GHAP entry record

**Error Handling**:
- Invalid domain: Raise ValidationError with valid options
- Invalid strategy: Raise ValidationError with valid options
- Empty required fields: Raise ValidationError with field name
- Goal/hypothesis/action/prediction too long (>1000 chars): Raise ValidationError with limit
- Collector failure: Raise MCPError with details

#### update_ghap

**Purpose**: Update the current GHAP entry (hypothesis, action, prediction).

**Input Schema**:
```python
{
    "hypothesis": str | None, # Optional: Updated hypothesis
    "action": str | None,     # Optional: Updated action
    "prediction": str | None, # Optional: Updated prediction
    "strategy": str | None,   # Optional: Updated strategy
    "note": str | None,       # Optional: Additional note (for history tracking)
}
```

**Output Schema**:
```python
{
    "success": bool,
    "iteration_count": int,   # Current iteration count
}
```

**Behavior**:
1. Validate inputs (strategy enum if provided, text length)
2. Check if there's an active GHAP entry
3. If no active entry, raise error
4. Delegate to ObservationCollector.update_ghap()
5. Return success status and iteration count

**Error Handling**:
- No active GHAP: Raise NotFoundError with suggestion to start_ghap
- Invalid strategy: Raise ValidationError with valid options
- Fields too long (>1000 chars): Raise ValidationError with limit
- Collector failure: Raise MCPError with details

#### resolve_ghap

**Purpose**: Mark the current GHAP entry as resolved (confirmed/falsified/abandoned).

**Input Schema**:
```python
{
    "status": str,            # Required: One of: confirmed, falsified, abandoned
    "result": str,            # Required: What actually happened?
    "surprise": str | None,   # Optional: What was unexpected? (required for falsified)
    "root_cause": {           # Optional: Why hypothesis was wrong (required for falsified)
        "category": str,      # One of: wrong-assumption, missing-knowledge, oversight, environment-issue, misleading-symptom, incomplete-fix, wrong-scope, test-isolation, timing-issue
        "description": str,   # Explanation
    } | None,
    "lesson": {               # Optional: What worked (recommended for confirmed/falsified)
        "what_worked": str,   # The actual fix or successful approach
        "takeaway": str | None, # Optional high-level lesson
    } | None,
}
```

**Output Schema**:
```python
{
    "id": str,                # GHAP entry ID
    "status": str,            # confirmed, falsified, abandoned
    "confidence_tier": str,   # gold, silver, bronze, abandoned
    "resolved_at": str,       # ISO timestamp (UTC)
}
```

**Behavior**:
1. Validate inputs (status enum, root_cause category, text length)
2. Check if there's an active GHAP entry
3. If no active entry, raise error
4. If status is "falsified", require surprise and root_cause
5. Delegate to ObservationCollector.resolve_ghap() (saves to local JSON immediately)
6. Trigger ObservationPersister to embed and store (awaited, with retry on failure)
7. Return resolution record with confidence tier

**Error Handling**:
- No active GHAP: Raise NotFoundError
- Invalid status: Raise ValidationError with valid options (confirmed, falsified, abandoned)
- Invalid root_cause category: Raise ValidationError with valid options
- Missing required fields (surprise/root_cause for falsified): Raise ValidationError
- Fields too long (>2000 chars): Raise ValidationError with limit
- Collector failure: Raise MCPError
- Persister failure: Retry up to 3 times with exponential backoff (1s, 2s, 4s). If all retries fail, raise MCPError with details. The local resolved state is preserved regardless.

#### get_active_ghap

**Purpose**: Get the current active GHAP entry.

**Input Schema**:
```python
{}
```

**Output Schema**:
```python
{
    "id": str | None,
    "domain": str | None,
    "strategy": str | None,
    "goal": str | None,
    "hypothesis": str | None,
    "action": str | None,
    "prediction": str | None,
    "iteration_count": int | None,
    "created_at": str | None,
    "has_active": bool,       # True if an active entry exists
}
```

**Behavior**:
1. Delegate to ObservationCollector.get_current()
2. If no active entry, return {"has_active": false} with null fields
3. Return current GHAP state

**Error Handling**:
- Collector failure: Raise MCPError

#### list_ghap_entries

**Purpose**: List recent GHAP entries with filters.

**Input Schema**:
```python
{
    "limit": int,             # Optional: Max results, default 20, max 100
    "domain": str | None,     # Optional: Filter by domain
    "outcome": str | None,    # Optional: Filter by outcome status
    "since": str | None,      # Optional: ISO date string (UTC)
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "id": str,
            "domain": str,
            "strategy": str,
            "goal": str,
            "outcome_status": str,  # confirmed, falsified, abandoned, or None (if not resolved)
            "confidence_tier": str | None,
            "created_at": str,
            "resolved_at": str | None,
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate inputs (limit range, domain enum, date format)
2. Query VectorStore collection `experiences_full` with filters
3. Return results sorted by created_at (newest first)

**Error Handling**:
- Invalid domain: Raise ValidationError with valid options
- Invalid outcome: Raise ValidationError with valid options (confirmed, falsified, abandoned)
- Invalid date format: Raise ValidationError with expected format (ISO 8601)
- Limit out of range: Raise ValidationError with valid range [1, 100]
- VectorStore failure: Raise MCPError

---

## Learning Tools

### Purpose

Enable agent-driven value formation through clustering, validation, and storage.

### Tool Definitions

#### get_clusters

**Purpose**: Get cluster information for a given axis.

**Input Schema**:
```python
{
    "axis": str,              # Required: One of: full, strategy, surprise, root_cause
}
```

**Output Schema**:
```python
{
    "axis": str,
    "clusters": [
        {
            "cluster_id": str,     # Format: "cluster_{axis}_{label}"
            "label": int,          # Cluster label (0, 1, 2, ...)
            "size": int,           # Number of members
            "avg_weight": float,   # Average confidence weight (0.0-1.0)
        }
    ],
    "count": int,
    "noise_count": int,       # Number of experiences labeled as noise (-1)
}
```

**Behavior**:
1. Validate axis (must be one of: full, strategy, surprise, root_cause)
2. Delegate to ExperienceClusterer.cluster_axis()
3. Map ClusterInfo to output format
4. Return cluster list sorted by size (descending)

**Error Handling**:
- Invalid axis: Raise ValidationError with valid options
- No experiences found for axis: Raise NotFoundError with message
- Clustering failure: Raise MCPError
- Minimum experiences not met (<20): Raise InsufficientDataError with count

#### get_cluster_members

**Purpose**: Get experiences in a specific cluster.

**Input Schema**:
```python
{
    "cluster_id": str,        # Required: Cluster ID (format: "cluster_{axis}_{label}")
    "limit": int,             # Optional: Max results, default 50, max 100
}
```

**Output Schema**:
```python
{
    "cluster_id": str,
    "axis": str,
    "members": [
        {
            "id": str,
            "ghap_id": str,
            "goal": str,
            "hypothesis": str,
            "action": str,
            "prediction": str,
            "outcome_status": str,
            "outcome_result": str,
            "surprise": str | None,
            "root_cause": {
                "category": str,
                "description": str,
            } | None,
            "lesson": {
                "what_worked": str,
                "takeaway": str | None,
            } | None,
            "confidence_tier": str,
            "created_at": str,
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Parse cluster_id to extract axis and label
2. Query VectorStore for experiences with matching cluster label
3. Return member experiences with full GHAP data

**Error Handling**:
- Invalid cluster_id format: Raise ValidationError with expected format
- Cluster not found: Raise NotFoundError
- Limit out of range: Raise ValidationError with valid range [1, 100]
- VectorStore failure: Raise MCPError

#### validate_value

**Purpose**: Validate a proposed value statement against a cluster centroid.

**Input Schema**:
```python
{
    "text": str,              # Required: Proposed value statement (max 500 chars)
    "cluster_id": str,        # Required: Target cluster ID
}
```

**Output Schema**:
```python
{
    "valid": bool,
    "similarity": float | None,  # Similarity to centroid (0.0-1.0) if valid
    "centroid_distance": float,  # Distance from centroid
    "threshold_distance": float, # Threshold (1 std dev above mean)
    "reason": str | None,        # Explanation if invalid
}
```

**Behavior**:
1. Validate inputs (text length, cluster_id format)
2. Generate embedding for value text via EmbeddingService
3. Delegate to ValueStore.validate_value_candidate()
4. Return validation result with similarity metrics

**Validation Logic** (per SPEC-001):
- Compute distance from value embedding to cluster centroid
- Compute distances from all members to centroid
- Threshold = mean + 1 standard deviation
- Valid if: candidate_distance <= threshold

**Error Handling**:
- Text too long (>500 chars): Raise ValidationError with limit
- Empty text: Raise ValidationError
- Invalid cluster_id format: Raise ValidationError
- Cluster not found: Raise NotFoundError
- Embedding failure: Raise MCPError

#### store_value

**Purpose**: Store a validated value statement.

**Input Schema**:
```python
{
    "text": str,              # Required: Value statement (max 500 chars)
    "cluster_id": str,        # Required: Associated cluster ID
    "axis": str,              # Required: Axis (full, strategy, surprise, root_cause)
}
```

**Output Schema**:
```python
{
    "id": str,                # Generated value ID
    "text": str,
    "axis": str,
    "cluster_id": str,
    "cluster_size": int,
    "similarity_to_centroid": float,
    "created_at": str,        # ISO timestamp (UTC)
}
```

**Behavior**:
1. Validate inputs (text length, cluster_id format, axis enum)
2. Validate value against cluster (must pass validation)
3. If validation fails, raise error (do NOT store invalid values)
4. Generate embedding via EmbeddingService
5. Delegate to ValueStore.store_value()
6. Return value record

**Error Handling**:
- Text too long (>500 chars): Raise ValidationError with limit
- Empty text: Raise ValidationError
- Invalid cluster_id format: Raise ValidationError
- Invalid axis: Raise ValidationError with valid options
- Cluster not found: Raise NotFoundError
- Validation failed: Raise ValidationError with reason (include similarity metrics)
- Embedding failure: Raise MCPError
- Storage failure: Raise MCPError

#### list_values

**Purpose**: List stored values with optional axis filter.

**Input Schema**:
```python
{
    "axis": str | None,       # Optional: Filter by axis
    "limit": int,             # Optional: Max results, default 20, max 100
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "id": str,
            "text": str,
            "axis": str,
            "cluster_id": str,
            "cluster_size": int,
            "similarity_to_centroid": float,
            "created_at": str,
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate inputs (axis enum, limit range)
2. Query VectorStore collection `values` with optional axis filter
3. Return results sorted by cluster_size (descending), then created_at (newest first)

**Error Handling**:
- Invalid axis: Raise ValidationError with valid options
- Limit out of range: Raise ValidationError with valid range [1, 100]
- VectorStore failure: Raise MCPError

---

## Search Tools

### Purpose

Enable semantic search across experiences for retrieval and context assembly.

### Tool Definitions

#### search_experiences

**Purpose**: Search experiences semantically across axes.

**Input Schema**:
```python
{
    "query": str,             # Required: Search query
    "axis": str,              # Optional: Axis to search (default: full)
    "domain": str | None,     # Optional: Filter by domain (metadata filter on experiences_full)
    "outcome": str | None,    # Optional: Filter by outcome status
    "limit": int,             # Optional: Max results, default 10, max 50
}
```

**Output Schema**:
```python
{
    "results": [
        {
            "id": str,
            "ghap_id": str,
            "goal": str,
            "hypothesis": str,
            "action": str,
            "prediction": str,
            "outcome_status": str,
            "outcome_result": str,
            "surprise": str | None,
            "root_cause": {
                "category": str,
                "description": str,
            } | None,
            "lesson": {
                "what_worked": str,
                "takeaway": str | None,
            } | None,
            "confidence_tier": str,
            "score": float,       # Similarity score (0.0-1.0)
            "created_at": str,
        }
    ],
    "count": int,
}
```

**Behavior**:
1. Validate inputs (axis enum, domain enum, outcome enum, limit)
2. Generate query embedding via EmbeddingService
3. Delegate to Searcher.search_experiences()
4. Return results sorted by score (descending)

**Error Handling**:
- Invalid axis: Raise ValidationError with valid options
- Invalid domain: Raise ValidationError with valid options
- Invalid outcome: Raise ValidationError with valid options
- Empty query: Return empty results (not an error)
- Limit out of range: Raise ValidationError with valid range [1, 50]
- Embedding failure: Raise MCPError
- Search failure: Raise MCPError

---

## Tool Registration

### Registration Pattern

Each tool module follows this pattern:

```python
def register_ghap_tools(server: Server, settings: ServerSettings) -> None:
    """Register GHAP tools with MCP server."""

    # Initialize services (shared instances via settings)
    observation_collector = get_observation_collector(settings)
    observation_persister = get_observation_persister(settings)

    @server.call_tool()
    async def start_ghap(
        domain: str,
        strategy: str,
        goal: str,
        hypothesis: str,
        action: str,
        prediction: str,
    ) -> dict:
        """Begin tracking a new GHAP entry."""
        # Implementation
        ...

    # Register other GHAP tools
    ...
```

### Service Initialization

Services are initialized once per server instance and shared across tool calls:

```python
# In server/tools/__init__.py

def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server."""

    # Initialize shared services (already done in SPEC-002-11)
    embedding_service = get_embedding_service(settings)
    vector_store = get_vector_store(settings)
    metadata_store = get_metadata_store(settings)

    # Initialize GHAP/learning services
    observation_collector = ObservationCollector(settings.journal_path)
    observation_persister = ObservationPersister(embedding_service, vector_store)
    clusterer = Clusterer(
        min_cluster_size=settings.min_cluster_size,
        min_samples=settings.min_samples,
    )
    experience_clusterer = ExperienceClusterer(vector_store, clusterer)
    value_store = ValueStore(embedding_service, vector_store, clusterer)
    searcher = Searcher(embedding_service, vector_store)

    # Store in server context for tool access
    server.request_context.observation_collector = observation_collector
    server.request_context.observation_persister = observation_persister
    server.request_context.experience_clusterer = experience_clusterer
    server.request_context.value_store = value_store
    server.request_context.searcher = searcher

    # Register tool modules
    register_memory_tools(server, settings)      # From SPEC-002-11
    register_code_tools(server, settings)        # From SPEC-002-11
    register_git_tools(server, settings)         # From SPEC-002-11
    register_ghap_tools(server, settings)        # This spec
    register_learning_tools(server, settings)    # This spec
    register_search_tools(server, settings)      # This spec
```

---

## Error Handling

### Error Types

All MCP tools use consistent error handling:

```python
class MCPError(Exception):
    """Base error for MCP tool failures."""
    pass

class ValidationError(MCPError):
    """Input validation failed."""
    pass

class NotFoundError(MCPError):
    """Resource not found."""
    pass

class InsufficientDataError(MCPError):
    """Not enough data for operation."""
    pass
```

### Error Response Format

All errors are caught and returned in MCP error format:

```python
try:
    # Tool implementation
    ...
except ValidationError as e:
    return {"error": {"type": "validation_error", "message": str(e)}}
except NotFoundError as e:
    return {"error": {"type": "not_found", "message": str(e)}}
except InsufficientDataError as e:
    return {"error": {"type": "insufficient_data", "message": str(e)}}
except Exception as e:
    logger.error("tool.unexpected_error", tool_name="...", error=str(e))
    return {"error": {"type": "internal_error", "message": "Internal server error"}}
```

---

## Domain and Strategy Enums

### Domain Values

```python
DOMAINS = [
    "debugging",
    "refactoring",
    "feature",
    "testing",
    "configuration",
    "documentation",
    "performance",
    "security",
    "integration",
]
```

### Strategy Values

```python
STRATEGIES = [
    "systematic-elimination",
    "trial-and-error",
    "research-first",
    "divide-and-conquer",
    "root-cause-analysis",
    "copy-from-similar",
    "check-assumptions",
    "read-the-error",
    "ask-user",
]
```

### Root Cause Categories

```python
ROOT_CAUSE_CATEGORIES = [
    "wrong-assumption",
    "missing-knowledge",
    "oversight",
    "environment-issue",
    "misleading-symptom",
    "incomplete-fix",
    "wrong-scope",
    "test-isolation",
    "timing-issue",
]
```

---

## Performance Requirements

### Latency Targets

Target latencies (P95) for typical operations:

| Operation | Target | Notes |
|-----------|--------|-------|
| start_ghap | <100ms | Local file write |
| update_ghap | <100ms | Local file write |
| resolve_ghap | <1s typical, <10s with retries | Includes embedding + storage (awaited) |
| get_active_ghap | <50ms | Local file read |
| list_ghap_entries | <200ms | VectorStore query with filters |
| get_clusters | <2s | Clustering computation |
| get_cluster_members | <300ms | VectorStore query |
| validate_value | <500ms | Includes embedding generation |
| store_value | <500ms | Includes validation + embedding + storage |
| list_values | <100ms | VectorStore query |
| search_experiences | <300ms | Includes embedding generation |

### Optimization Strategies

1. **Local GHAP storage**: ObservationCollector operates on local JSON files (no network latency for start/update)
2. **Retry with backoff**: Persistence retries use exponential backoff to avoid hammering failed services
3. **Cluster caching**: Clustering results could be cached (not in v1)
4. **Connection pooling**: VectorStore connections reused across calls
5. **Result limiting**: Enforce max result counts to prevent large payloads

---

## Testing Strategy

### Unit Tests

Each tool tested independently with mocked services:

```python
@pytest.mark.asyncio
async def test_start_ghap_success(mock_observation_collector):
    """Test successful GHAP creation."""
    result = await start_ghap(
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix auth timeout bug",
        hypothesis="Slow network responses exceed 30s timeout",
        action="Increasing timeout to 60s",
        prediction="Auth failures stop",
    )

    assert result["id"] is not None
    assert result["domain"] == "debugging"
    assert result["strategy"] == "systematic-elimination"

    # Verify service calls
    mock_observation_collector.create_ghap.assert_called_once()

@pytest.mark.asyncio
async def test_start_ghap_invalid_domain(mock_services):
    """Test validation error for invalid domain."""
    with pytest.raises(ValidationError, match="Invalid domain"):
        await start_ghap(
            domain="invalid",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )
```

### Integration Tests

Test tools with real services (in-memory implementations):

```python
@pytest.mark.asyncio
async def test_ghap_workflow_end_to_end():
    """Test full GHAP workflow: start, update, resolve."""
    # Setup
    observation_collector = ObservationCollector(tmp_path)
    observation_persister = MockObservationPersister()

    # Start
    result1 = await start_ghap(
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix flaky test",
        hypothesis="Timing issue",
        action="Adding sleep",
        prediction="Test passes consistently",
    )

    # Update
    result2 = await update_ghap(
        hypothesis="Test pollution - previous test leaves state",
        action="Adding teardown to previous test",
        prediction="Test passes consistently",
    )
    assert result2["iteration_count"] == 2

    # Resolve
    result3 = await resolve_ghap(
        status="confirmed",
        result="Test passed 3/3 runs",
        lesson={
            "what_worked": "Added proper teardown",
            "takeaway": "Flaky tests often isolation issues",
        },
    )
    assert result3["status"] == "confirmed"
    assert result3["confidence_tier"] == "gold"
```

### Test Coverage Requirements

- Unit tests: ≥90% coverage for all tool modules
- Integration tests: All happy paths and major error cases
- Error handling: Test all error types for each tool
- Input validation: Test boundary conditions for all parameters
- Enum validation: Test all domain, strategy, outcome values

---

## Acceptance Criteria

### Functional

1. All GHAP tools (start, update, resolve, get_active, list) work correctly
2. All learning tools (get_clusters, get_cluster_members, validate_value, store_value, list_values) work correctly
3. All search tools (search_experiences) work correctly
4. Tools registered with MCP server via @server.call_tool()
5. Service initialization occurs once per server instance
6. Input validation enforced for all parameters
7. Error handling returns MCP-compliant error format
8. All tools documented with docstrings
9. GHAP state persists across calls (local JSON)
10. Value validation rejects invalid values (do NOT store invalid values)

### GHAP Workflow

1. start_ghap creates new entry and returns ID
2. update_ghap updates current entry, increments iteration count
3. resolve_ghap marks entry resolved and triggers persistence
4. get_active_ghap returns current state or empty if none
5. list_ghap_entries filters by domain, outcome, date
6. Orphaned entries handled gracefully (warn but allow new entry)
7. Confidence tier assigned based on resolution quality

### Value Formation Workflow

1. get_clusters runs clustering and returns cluster info
2. get_cluster_members retrieves experiences in cluster
3. validate_value checks centroid distance with 1 std dev threshold
4. store_value only stores validated values (reject if invalid)
5. list_values returns values sorted by cluster size
6. Validation metrics (distance, threshold) included in response

### Search

1. search_experiences searches across specified axis
2. Results filtered by domain (metadata) and outcome
3. Results ordered by similarity score
4. Empty query returns empty results

### Quality

1. All tools handle edge cases gracefully (no active GHAP, empty clusters, invalid values)
2. Invalid inputs rejected with ValidationError and helpful messages
3. Text length limits enforced strictly
4. Enum values validated against allowed lists
5. Async operations never block event loop
6. Structured logging for all operations (success and failure)

### Performance

1. Latency targets met for typical operations
2. GHAP operations complete quickly (<100ms for local operations)
3. Clustering completes in <2s for typical dataset
4. No memory leaks with repeated tool calls

### Testing

1. Unit test coverage ≥90%
2. All error cases tested
3. Integration tests pass with real services
4. Type checking passes (mypy --strict)
5. Linting passes (ruff)

---

## Out of Scope

- Context assembly tools (ContextAssembler) - future work
- Premortem warnings - future work
- Hook integration (session_start, ghap_checkin, outcome_capture) - future work
- Cluster visualization - future work
- Value decay/weighting over time - future work
- Cross-project value transfer - future work
- Authentication/authorization
- Rate limiting
- Tool usage analytics

---

## Notes

- All tools use async/await consistently
- All timestamps are ISO 8601 format (UTC)
- GHAP state stored locally in `.claude/journal/` (no server dependency for collection)
- Persistence awaited after resolve_ghap with retry on failure (3 attempts, exponential backoff)
- Domain is a metadata filter on experiences_full, NOT a separate axis (4 axes: full, strategy, surprise, root_cause)
- Value validation uses 1 standard deviation threshold (stricter than median as originally proposed)
- Invalid values are REJECTED, not stored with warnings
- Logging via `structlog` following existing codebase patterns
- MCP SDK version: `mcp>=0.9.0`
