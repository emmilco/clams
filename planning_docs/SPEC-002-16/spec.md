# SPEC-002-16: Full Integration and Performance Tuning

## Summary

Complete the Learning Memory Server by integrating all modules into a working, performant system. This is the critical integration task that transforms independent modules into a functional MCP server ready for real-world usage. No partial work—everything must be connected, tested, and verified end-to-end.

## Background

### What's Already Implemented

**Core Infrastructure (DONE)**:
- EmbeddingService (NomicEmbedding, MockEmbedding)
- VectorStore (QdrantVectorStore, InMemoryVectorStore)
- MetadataStore (SQLite with async support)
- MCP server skeleton with stdio transport

**Indexing & Analysis (DONE)**:
- CodeParser (TreeSitter) + CodeIndexer
- GitReader (GitPython) + GitAnalyzer
- ObservationCollector (local GHAP state machine)

**Search & Clustering (DONE)**:
- Searcher (unified query interface)
- Clusterer (HDBSCAN-based)
- ExperienceClusterer (multi-axis clustering)
- ValueStore (centroid-based validation)

**MCP Tools (DONE)**:
- Memory tools (store, retrieve, list, delete)
- Code tools (index, search, find_similar)
- Git tools (search_commits, file_history, churn_hotspots, code_authors)
- GHAP tools (start, update, resolve, get_active, list)
- Learning tools (get_clusters, get_cluster_members, validate_value, store_value, list_values)
- Search tools (all collection searches via Searcher)

**Context Assembly (DONE)**:
- ContextAssembler (light/rich/premortem contexts)
- Token management and deduplication
- Markdown formatting

**Hook Scripts (DONE)**:
- session_start.sh, session_end.sh
- ghap_checkin.sh, outcome_capture.sh
- user_prompt_submit.sh
- MCP client (mcp_client.py)

### What's Missing

**Critical Integration Bugs** (found via code audit 2025-12-05):
1. **Stub class shadows real ObservationPersister** - `observation/__init__.py` lines 26-51 defines a stub class that shadows the real implementation imported from `persister.py`. Any code importing from package level gets the stub.
2. **Wrong API call in GHAP tools** - `server/tools/ghap.py` line 374 calls `persister.persist(resolved.to_dict())` but the real persister expects `GHAPEntry` directly, not a dict.
3. **search_experiences passes empty embedding** - `server/tools/search.py` line 88 passes `query_embedding=[]` which produces no meaningful results.

**Stub MCP Tools** (return empty results instead of querying VectorStore):
- `list_ghap_entries()` - ghap.py:519 - Returns empty list
- `get_cluster_members()` - learning.py:163 - Returns empty list
- `list_values()` - learning.py:367 - Returns empty list

**Other Gaps**:
1. **Code/Git services not initialized** - Commented out in `server/tools/__init__.py`
2. **No end-to-end integration tests** - Individual modules tested, but not wired together
3. **No installation/deployment verification** - Can it actually be installed and run?
4. **No performance benchmarks** - Latency targets from master spec unverified
5. **Missing collections initialization** - VectorStore collections may not exist on fresh install
6. **Configuration not validated** - Settings may reference incorrect paths or models

## Requirements

### 1. Fix ObservationPersister Integration Bugs

**Why**: SPEC-002-14 implemented ObservationPersister, but integration bugs prevent it from working:
1. The stub class in `__init__.py` shadows the real implementation
2. GHAP tools call the wrong API (`.to_dict()` instead of direct object)

**What**:
- Remove stub class from `observation/__init__.py` (lines 26-51)
- Import real `ObservationPersister` from `persister.py`
- Fix `server/tools/ghap.py` line 374: change `persister.persist(resolved.to_dict())` to `persister.persist(resolved)`
- Verify the 4-axis embedding works (full, strategy, surprise, root_cause - domain is metadata filter)

**Acceptance Criteria**:
- `from learning_memory_server.observation import ObservationPersister` returns real implementation
- resolve_ghap() successfully persists to all 4 axis collections (ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause)
- Persisted entries include all required payload fields (domain, strategy, confidence_tier, etc.)
- Integration test: start_ghap() → resolve_ghap() → search_experiences() returns the entry

### 2. Enable Code and Git Services

**Why**: MCP tools currently raise "service not initialized" errors. Services are commented out in `register_all_tools()`.

**What**:
- Uncomment and fix CodeIndexer initialization in `initialize_services()`
- Uncomment and fix GitAnalyzer initialization
- Handle initialization failures gracefully (log warning, continue without feature)
- Validate TreeSitter grammars are available

**Acceptance Criteria**:
- index_codebase() works without "service not initialized" error
- search_code() returns real results from indexed code
- search_commits() works in a git repository
- Server starts successfully even if optional services fail (e.g., no git repo)

### 3. Collection Lifecycle Management

**Why**: Fresh installs fail because collections don't exist. Current code only creates collections lazily on first use, which may fail silently.

**What**:
- Create all required collections on server startup
- Collections: memories, code, commits, ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause, values
- Handle "collection already exists" gracefully (this is normal after first run)
- Verify dimension matches embedding_service.dimension
- Note: Collection names use "ghap_" prefix per SPEC-002-14 ObservationPersister implementation

**Acceptance Criteria**:
- Server startup creates all collections if they don't exist
- Server startup succeeds if collections already exist
- Integration test: fresh Qdrant instance → start server → all collections exist

### 4. Implement Stub MCP Tools

**Why**: Four MCP tools return empty results or pass invalid data instead of working correctly.

**What**:
- `list_ghap_entries()` (ghap.py:519): Query ghap_full collection with filters (domain, outcome, since)
- `get_cluster_members()` (learning.py:163): Parse cluster_id, query correct axis collection, filter by cluster label
- `list_values()` (learning.py:367): Query values collection with optional axis filter
- `search_experiences()` (search.py:88): Generate query embedding from text, then call searcher

**Specific Fixes**:
```python
# search.py:88 - BEFORE (broken):
results = await searcher.search_experiences(
    query_embedding=[],  # Empty embedding!
    ...
)

# search.py:88 - AFTER (fixed):
query_embedding = await embedding_service.embed(query)
results = await searcher.search_experiences(
    query_embedding=query_embedding,
    ...
)
```

**Acceptance Criteria**:
- list_ghap_entries() returns actual GHAP entries from VectorStore
- get_cluster_members() returns experiences in a specific cluster
- list_values() returns stored values
- search_experiences() generates real embeddings and returns semantically relevant results

### 5. End-to-End Integration Tests

**Why**: No tests verify the full system works together. Individual modules pass tests but may fail when integrated.

**What**: Create `tests/integration/test_e2e.py` with scenarios:

**Scenario 1: Memory Lifecycle**
- store_memory() → retrieve_memories() → delete_memory()
- Verify semantic search works (query different from stored text)

**Scenario 2: Code Indexing & Search**
- index_codebase() on small test directory
- search_code() returns indexed functions
- find_similar_code() with code snippet

**Scenario 3: Git Analysis**
- index_commits() on test repository
- search_commits() returns relevant commits
- get_churn_hotspots() returns frequently changed files

**Scenario 4: GHAP Learning Loop** (single comprehensive test)
- Create 20+ GHAP entries with varied domains/strategies to enable clustering
- start_ghap() → update_ghap() → resolve_ghap() cycle for each
- Verify persisted to all 4 axis collections (ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause)
- get_clusters() returns clusters from the 20+ entries
- validate_value() against cluster centroid
- store_value() → list_values()
- NOTE: This is intentionally ONE test with 20+ entries to test real clustering

**Scenario 5: Context Assembly**
- Store memories, code, experiences, values
- assemble() retrieves and formats markdown context
- premortem() returns warnings from past failures

**Acceptance Criteria**:
- All 5 scenarios pass with real Qdrant instance
- Tests run in <60 seconds total
- Tests clean up after themselves (delete collections)

### 6. Installation & Deployment Verification

**Why**: Package may not be installable or runnable in a clean environment.

**What**:
- Test installation: `uv venv && uv pip install -e ".[dev]"`
- Test CLI entry point: `learning-memory-server` starts without errors
- Test configuration override via environment variables
- Verify all dependencies resolve (no version conflicts)

**Acceptance Criteria**:
- Fresh venv installation succeeds
- `learning-memory-server --help` works (or server starts and responds to ping)
- LMS_QDRANT_URL, LMS_EMBEDDING_MODEL env vars are respected
- No import errors on startup

### 7. Performance Benchmarking

**Why**: Master spec defines latency targets (<200ms search, <500ms context assembly). These are unverified.

**What**: Create `tests/performance/test_benchmarks.py` with:

**Benchmark 1: Code Search**
- Index 100 Python functions
- Run search_code() 100 times
- Measure p50, p95, p99 latency

**Benchmark 2: Memory Retrieval**
- Store 1000 memories
- Run retrieve_memories() 100 times
- Measure p50, p95, p99 latency

**Benchmark 3: Context Assembly**
- Prepopulate all collections (memories, code, experiences, values)
- Run assemble() with rich context
- Measure p50, p95, p99 latency

**Benchmark 4: Clustering**
- Store 100 GHAP entries (persisted to ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause collections)
- Run cluster_axis() for all 4 axes (full, strategy, surprise, root_cause)
- Domain is a metadata filter, not a clustered axis
- Measure total time

**Acceptance Criteria** (HARD REQUIREMENTS - failure is a blocker):
- Code search: p95 < 200ms
- Memory retrieval: p95 < 200ms
- Context assembly: p95 < 500ms
- Clustering: completes in < 5s for 100 entries
- Benchmark results logged to JSON for tracking
- If any benchmark fails, escalate to human before proceeding

### 8. Configuration Validation

**Why**: Invalid configuration causes runtime failures. Better to fail fast on startup.

**What**:
- Validate qdrant_url is reachable (warn if not, don't crash)
- Validate embedding_model exists and can load
- Validate paths (storage_path, sqlite_path, journal_path) are writable
- Validate git repo_path if provided

**Acceptance Criteria**:
- Invalid/unreachable Qdrant URL fails fast with clear error (no tolerance for broken storage)
- Invalid embedding model fails fast with clear error
- Invalid paths fail fast with clear error
- Valid configuration starts successfully

### 9. Error Handling & Observability

**Why**: Failures must be debuggable. Current logging may be insufficient for production use.

**What**:
- Add structured logging to all tool calls (request ID, duration, error details)
- Add error context to exceptions (which tool, which operation, what parameters)
- Add health check endpoint (ping tool already exists, verify it works)
- Add metrics endpoint (optional, for observability): collection counts, index stats

**Acceptance Criteria**:
- Every MCP tool logs start and completion
- Errors include full context (tool name, parameters, stack trace)
- ping tool returns "pong" successfully
- Logs are valid JSON (for log aggregation)

### 10. Minimal README Update

**Why**: README is minimal. Need basic installation/usage info.

**What**: Update README.md with ONLY:
- Brief description (what it is)
- Installation command (`uv pip install -e .`)
- How to start server
- Link to source files for tool discovery (e.g., "See `server/tools/` for available MCP tools")
- System requirements (Python, Qdrant)

**What NOT to include** (avoid brittle info):
- Detailed tool parameter documentation (changes frequently)
- Exhaustive configuration reference (see code)
- Version-specific information

**Acceptance Criteria**:
- README is under 100 lines
- No brittle information that will drift from code
- Directs users to source code as the source of truth

## Integration Checklist

Every module pair must be verified to work together:

### EmbeddingService ↔ VectorStore
- [x] Dimension matches (tested in existing tests)
- [ ] Fresh install creates collections with correct dimension

### EmbeddingService ↔ CodeIndexer
- [x] Code units embed successfully (tested)
- [ ] Batch embedding optimized (not creating embeddings one-by-one)

### EmbeddingService ↔ GitAnalyzer
- [x] Commit messages embed successfully (tested)
- [ ] Incremental indexing preserves existing embeddings

### EmbeddingService ↔ ObservationPersister
- [ ] Multi-axis embedding generates 4 embeddings per entry
- [ ] Confidence tier weights propagate to payload

### EmbeddingService ↔ Searcher
- [ ] Query embeddings match stored embedding format
- [ ] Search results have correct scores (cosine similarity)

### VectorStore ↔ CodeIndexer
- [ ] Upsert successful for code_units collection
- [ ] Search filters by project/language work
- [ ] File deletion removes orphaned units

### VectorStore ↔ GitAnalyzer
- [ ] Commits stored in correct collection
- [ ] Incremental indexing doesn't duplicate commits
- [ ] Churn calculations query commits correctly

### VectorStore ↔ ObservationPersister
- [ ] All 4 axis collections store entries (ghap_full, ghap_strategy, ghap_surprise, ghap_root_cause)
- [ ] Payload schema matches Clusterer expectations
- [ ] Domain is stored as metadata, not a separate collection

### VectorStore ↔ Clusterer
- [ ] Scroll retrieves all entries (no pagination issues)
- [ ] Weights extracted from payload correctly
- [ ] Centroids computed correctly

### VectorStore ↔ ValueStore
- [ ] Values stored with embeddings
- [ ] Validation queries cluster centroids
- [ ] List queries values collection

### VectorStore ↔ Searcher
- [ ] All collections searchable
- [ ] Filters work correctly (category, project, language, domain, outcome, axis)
- [ ] Limit parameter respected

### Searcher ↔ ContextAssembler
- [ ] Multi-collection queries return correct results
- [ ] Deduplication works across collections
- [ ] Token budgeting distributes correctly

### ObservationCollector ↔ ObservationPersister
- [ ] Resolved entries serialize correctly to dict
- [ ] Persister handles all outcome types (confirmed, falsified, abandoned)

### Clusterer ↔ ExperienceClusterer
- [ ] Multi-axis clustering queries correct collections
- [ ] Cluster labels stored correctly
- [ ] Noise filtering works

### ExperienceClusterer ↔ ValueStore
- [ ] Cluster centroids accessible for validation
- [ ] Member distances computed correctly
- [ ] Median distance threshold works

### MCP Server ↔ All Services
- [ ] ServiceContainer initializes all dependencies
- [ ] Tools have access to required services
- [ ] Errors propagate to MCP responses correctly

## Performance Requirements

Based on master spec, the system must meet:

| Operation | Target (p95) | Measurement |
|-----------|--------------|-------------|
| Code search | < 200ms | search_code() with 100 indexed functions |
| Memory retrieval | < 200ms | retrieve_memories() from 1000 memories |
| Commit search | < 200ms | search_commits() from 500 commits |
| Context assembly | < 500ms | assemble() with rich context |
| Clustering | < 5s | cluster_axis() on 100 experiences (4 axes total) |
| Embedding (single) | < 100ms | embed() single text |
| Embedding (batch) | < 2s | embed_batch() 100 texts |

**Performance Tuning Strategies**:
- Use batch embedding where possible (CodeIndexer, GitAnalyzer, ObservationPersister)
- Optimize Qdrant filters (use indexed fields)
- Limit scroll() operations (don't retrieve all vectors unless needed)
- Cache embeddings (don't re-embed unchanged code)
- Use async/await correctly (don't block event loop)

## File Structure

Files to modify/create:

```
tests/
  integration/
    __init__.py           # NEW
    test_e2e.py           # NEW: End-to-end scenarios
    conftest.py           # NEW: Integration test fixtures
  performance/
    __init__.py           # NEW
    test_benchmarks.py    # NEW: Performance benchmarks
    conftest.py           # NEW: Performance test fixtures

src/learning_memory_server/
  observation/
    __init__.py           # MODIFY: Remove stub class (lines 26-51), keep real import
  server/
    tools/
      __init__.py         # MODIFY: Uncomment code/git initialization
      ghap.py             # MODIFY: Fix line 374 (.to_dict() → direct), implement list_ghap_entries
      learning.py         # MODIFY: Implement get_cluster_members, list_values
      search.py           # MODIFY: Fix search_experiences to generate real embeddings
    main.py               # MODIFY: Add collection initialization on startup

README.md                 # MODIFY: Complete documentation
```

## Acceptance Criteria

### Functional

1. **ObservationPersister works**:
   - resolve_ghap() persists to all 4 axis collections
   - get_clusters() returns clusters from real data
   - get_cluster_members() returns experiences

2. **Code indexing works**:
   - index_codebase() indexes a Python project
   - search_code() returns relevant functions
   - Results include file path, function name, docstring

3. **Git analysis works**:
   - index_commits() indexes repository history
   - search_commits() finds relevant commits
   - get_churn_hotspots() identifies frequently changed files

4. **Learning loop works**:
   - start_ghap() → resolve_ghap() → stored in VectorStore
   - After 20+ entries, get_clusters() returns clusters
   - validate_value() enforces centroid distance
   - store_value() → list_values() returns stored values

5. **Context assembly works**:
   - assemble() returns markdown with memories, code, experiences, values
   - premortem() returns warnings from past failures in domain/strategy

6. **Installation works**:
   - Fresh venv installation succeeds
   - learning-memory-server CLI starts
   - Configuration via env vars works

### Performance

1. **Search latency**: p95 < 200ms for code/memory/commit search
2. **Context assembly**: p95 < 500ms for rich context
3. **Clustering**: < 5s for 100 experiences on all axes
4. **Embedding**: < 100ms per text, < 2s for 100 texts

### Quality

1. **No stub implementations**: All MCP tools functional
2. **End-to-end tests pass**: All 5 scenarios in test_e2e.py pass
3. **Performance benchmarks pass**: All targets met in test_benchmarks.py
4. **Error handling complete**: All errors logged with context
5. **Documentation complete**: README covers installation, configuration, usage, troubleshooting

## Test Requirements

### Integration Tests (`tests/integration/test_e2e.py`)

**Setup**:
- Requires Qdrant at localhost:6333 (Docker: `docker run -p 6333:6333 qdrant/qdrant`)
- Creates fresh collections for each test
- Cleans up after each test

**Scenarios** (5 total, must all pass):
1. Memory lifecycle (store → retrieve → delete)
2. Code indexing & search (index → search → find_similar)
3. Git analysis (index → search → churn → authors)
4. GHAP learning loop (start → update → resolve → cluster → validate → store value)
5. Context assembly (populate → assemble light → assemble rich → premortem)

**Assertions**:
- All operations succeed without errors
- Results are semantically correct (not just empty lists)
- Filters work (category, project, language, domain, outcome, axis)
- Pagination works (limit, offset)

### Performance Tests (`tests/performance/test_benchmarks.py`)

**Setup**:
- Populate collections with realistic data (100 code units, 1000 memories, 500 commits, 100 experiences)
- Use real Qdrant (not in-memory mock)

**Benchmarks** (4 total):
1. Code search (100 iterations, measure p50/p95/p99)
2. Memory retrieval (100 iterations, measure p50/p95/p99)
3. Context assembly (10 iterations, measure p50/p95/p99)
4. Clustering (5 axes, measure total time)

**Outputs**:
- JSON file with results (for tracking over time)
- Pass/fail based on targets (p95 < 200ms for search, p95 < 500ms for context)

### Unit Tests (existing, verify no regressions)

**Run full suite**: `uv run pytest -vvsx`

**Expected**:
- All existing tests still pass (no regressions)
- Coverage > 80% (check with `uv run pytest --cov`)

## Success Metrics

This integration task is successful when:

1. **All MCP tools work end-to-end** (no stubs, no "service not initialized" errors)
2. **Fresh installation succeeds** (uv venv → install → start server → ping returns pong)
3. **All integration tests pass** (5 scenarios in test_e2e.py)
4. **All performance benchmarks pass** (targets met in test_benchmarks.py)
5. **Documentation is complete** (README covers installation, configuration, usage)
6. **No regressions** (existing unit tests still pass)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ObservationPersister complex | High - blocks learning loop | Start with single-axis, then expand to multi-axis |
| Performance targets too aggressive | Medium - may need spec amendment | Measure first, optimize if needed, escalate if targets unrealistic |
| Qdrant version incompatibility | Medium - tests may fail | Pin qdrant-client version, test with Docker image |
| TreeSitter grammar loading fails | Low - code indexing breaks | Verify grammars bundled, add graceful fallback |
| Fresh install missing dependencies | Low - poor UX | Add installation test to CI (if exists) |

## Dependencies

**Blocked By**:
- None - SPEC-002-14 (ObservationPersister) is now DONE

**Blocks**:
- SPEC-002-17 (Documentation) - needs working system to document

**Related**:
- All completed tasks (SPEC-002-01 through SPEC-002-15, 18, 19)
- SPEC-002-14 provides the real ObservationPersister that this task wires up

## Timeline Estimate

**Total**: 2-3 days (assuming single developer, full-time focus)

**Breakdown**:
- ObservationPersister implementation: 4-6 hours
- Enable code/git services: 2-3 hours
- Collection lifecycle: 1-2 hours
- Implement stub tools: 2-3 hours
- Integration tests: 4-6 hours
- Performance tests: 2-3 hours
- Installation verification: 1-2 hours
- Configuration validation: 1-2 hours
- Error handling & logging: 2-3 hours
- Documentation: 2-3 hours
- Debugging & fixes: 4-6 hours (buffer)

## Notes

**This is the make-or-break task.** If this succeeds, the Learning Memory Server is a working product. If this fails, the project is a collection of disconnected modules.

**Quality bar**: No shortcuts. Every integration point must be verified. Every MCP tool must work with real data. Performance targets must be met or explicitly waived with human approval.

**Testing philosophy**: Integration tests are more valuable than unit tests for this task. Focus on end-to-end scenarios that prove the system works.

**Performance philosophy**: Measure first, optimize second. Don't prematurely optimize. If benchmarks fail, profile to find bottlenecks, then optimize the slowest operations.

## Changelog

### Version 1.0 (2025-12-04)
- Initial spec for SPEC-002-16
- Comprehensive integration requirements
- Performance benchmarking plan
- End-to-end test scenarios
