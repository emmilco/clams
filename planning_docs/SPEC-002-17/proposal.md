# SPEC-002-17: Documentation and E2E Testing - Technical Proposal

## Problem Statement

The Learning Memory Server is functionally complete but lacks:
1. **Navigation documentation** - AI agents need pointers to explore the codebase efficiently
2. **Verified docstrings** - 23 MCP tools + public classes must be documented for self-documenting code
3. **End-to-end validation** - Integration tests verify individual modules work, but full workflows need testing
4. **Performance baselines** - Performance targets exist in specs but lack measurement infrastructure

This task completes the project by adding minimal, anti-drift documentation and comprehensive E2E/performance validation.

## Proposed Solution

### 1. GETTING_STARTED.md

**Location**: `/Users/elliotmilco/Documents/GitHub/clams/GETTING_STARTED.md` (repo root)

**Content Structure**:
```markdown
# Learning Memory Server: Getting Started

## What Is This?

[2-3 sentence description of the LMS: MCP server providing semantic memory,
code indexing, git analysis, and GHAP learning loop for AI agents]

## Quick Start

### Starting the Server
[Command to start server, mention config via environment variables]

### Exploring the Codebase

**MCP Tools**: `src/learning_memory_server/server/tools/`
- `memory.py` - Memory storage and retrieval
- `code.py` - Code indexing and search
- `git.py` - Git commit analysis
- `ghap.py` - GHAP learning loop
- `learning.py` - Clustering and values
- `search.py` - Cross-collection search

**Configuration**: `src/learning_memory_server/server/config.py`
- ServerSettings class with all environment variable options

**Data Models**: `src/learning_memory_server/observation/models.py`
- GHAPEntry, ObservationState, etc.

**Storage**: `src/learning_memory_server/storage/`
- VectorStore interface + Qdrant/SQLite implementations
- Metadata store for relational data

**Embedding**: `src/learning_memory_server/embedding/`
- EmbeddingService interface + NomicEmbedding implementation

### Key Concepts

**GHAP (Goal-Hypothesis-Action-Prediction)**:
A structured observation format for AI learning. An agent sets a goal, forms
a hypothesis about how to achieve it, takes action, and records the prediction
outcome. These observations are embedded and clustered to extract patterns.

**Experience Axes**:
GHAP entries are projected onto 4 semantic axes (strategy, surprise, root_cause,
full) and stored in separate Qdrant collections for multi-perspective clustering.

**Confidence Tiers**:
Observations are weighted (gold=1.0, silver=0.7, bronze=0.4) based on outcome
confidence. Cluster centroids are weighted averages.

## Architecture

**Master Spec**: `planning_docs/SPEC-001-learning-memory-server.md`

**Module Layout**:
- `embedding/` - Embedding service interface and implementations
- `storage/` - Vector store and metadata store interfaces
- `indexers/` - Code parsing (TreeSitter) and git analysis
- `observation/` - GHAP state machine and persistence
- `clustering/` - HDBSCAN clustering for experience axes
- `values/` - Value extraction from clusters
- `context/` - Context assembly for rich agent prompts
- `search/` - Hybrid semantic search across collections
- `server/` - MCP server and tool implementations

## Testing

**Unit Tests**: `tests/<module>/` - Test each module in isolation
**Integration Tests**: `tests/integration/` - E2E workflows with real Qdrant
**Performance Tests**: `tests/performance/` - Benchmark critical operations

Run tests: `pytest -vvsx`

## Development

**Requirements**: Python 3.12+, Qdrant 1.8.0+
**Qdrant Setup**: `docker run -p 6333:6333 qdrant/qdrant`
**Install**: `pip install -e .`
```

**Design Rationale**:
- **Under 100 lines**: Focuses on navigation, not duplication
- **No version-specific info**: Points to code as source of truth
- **File paths, not content**: Agents use Glob/Grep to dive deeper
- **Concepts over details**: GHAP and axes explained briefly, implementation referenced

### 2. Docstring Audit

**Identification Strategy**:
1. **23 MCP tools** - Already counted via grep:
   ```bash
   grep -h "async def [a-z_]*(" src/learning_memory_server/server/tools/*.py | \
   grep -v "^def register" | sed 's/.*async def //' | sed 's/(.*//' | sort
   ```
   Tools: delete_memory, find_similar_code, get_active_ghap, get_churn_hotspots,
   get_cluster_members, get_clusters, get_code_authors, get_file_history,
   index_codebase, list_ghap_entries, list_memories, list_values, ping,
   resolve_ghap, retrieve_memories, search_code, search_commits,
   search_experiences, start_ghap, store_memory, store_value, update_ghap,
   validate_value

2. **Public classes** - Find all classes without leading underscore:
   ```bash
   grep -r "^class [A-Z]" src/learning_memory_server --include="*.py"
   ```

3. **Public functions** - Find module-level functions in `__init__.py` and public APIs

**Audit Checklist** (manual verification):
- [ ] All 23 MCP tools have complete docstrings (one-line + Args/Returns/Raises)
- [ ] ServiceContainer, ServerSettings, EmbeddingService, VectorStore docstrings
- [ ] ObservationCollector, ObservationPersister, GHAPEntry docstrings
- [ ] Clusterer, ExperienceClusterer, ClusterInfo docstrings
- [ ] Searcher, CodeIndexer, GitAnalyzer docstrings
- [ ] ContextAssembler and related classes docstrings

**Docstring Format** (Google style):
```python
async def tool_name(arg1: str, arg2: int = 5) -> dict[str, Any]:
    """One-line summary of what this tool does.

    Longer description if needed to explain behavior, constraints, or context.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2 (default: 5)

    Returns:
        Dictionary containing result fields

    Raises:
        ValidationError: If input validation fails
        MCPError: If operation fails
    """
```

**Verification Method**:
- Manual inspection during implementation (create checklist in proposal)
- Code reviewer verifies completeness (subjective, no automated enforcement)
- Focus on public APIs that agents will interact with

### 3. Integration Tests (`tests/integration/test_e2e.py`)

**File Structure**:
```python
"""End-to-end integration tests for Learning Memory Server.

These tests validate full workflows with real Qdrant at localhost:6333.
They use isolated test collections to avoid touching production data.

Failure Policy: Tests FAIL (not skip) if Qdrant unavailable.
"""

import pytest
from learning_memory_server.server.tools import ServiceContainer, initialize_services
from learning_memory_server.server.config import ServerSettings
# ... other imports
```

**Shared Fixtures**:
```python
@pytest.fixture
async def test_services() -> AsyncIterator[ServiceContainer]:
    """Initialize services with test collections."""
    settings = ServerSettings(
        qdrant_url="http://localhost:6333",
        sqlite_path=":memory:",  # In-memory SQLite for isolation
        journal_path=str(tmp_path / "journal"),  # Temp journal
    )

    services = initialize_services(settings)

    # Override AXIS_COLLECTIONS to use test collections
    from learning_memory_server.clustering import experience
    original_mapping = experience.AXIS_COLLECTIONS.copy()
    experience.AXIS_COLLECTIONS = {
        "full": "test_ghap_full",
        "strategy": "test_ghap_strategy",
        "surprise": "test_ghap_surprise",
        "root_cause": "test_ghap_root_cause",
    }

    # Create test collections
    for collection in experience.AXIS_COLLECTIONS.values():
        await services.vector_store.create_collection(
            name=collection,
            dimension=768,
            distance="cosine"
        )

    yield services

    # Cleanup
    experience.AXIS_COLLECTIONS = original_mapping
    for collection in ["test_ghap_full", "test_ghap_strategy", ...]:
        try:
            await services.vector_store.delete_collection(collection)
        except:
            pass
```

**Test Scenarios**:

**1. Memory Lifecycle** (`test_memory_lifecycle`):
```python
async def test_memory_lifecycle(test_services):
    """Test store → retrieve → delete workflow."""
    # Store memory
    result = await store_memory(
        content="Test memory content",
        category="fact",
        importance=0.8,
        tags=["test"]
    )
    memory_id = result["id"]

    # Retrieve by semantic search
    results = await retrieve_memories(query="test memory", limit=5)
    assert any(r["id"] == memory_id for r in results["memories"])

    # List memories by category
    results = await list_memories(category="fact")
    assert any(m["id"] == memory_id for m in results["memories"])

    # Delete memory
    result = await delete_memory(memory_id)
    assert result["deleted"] is True

    # Verify deletion
    results = await list_memories(category="fact")
    assert not any(m["id"] == memory_id for m in results["memories"])
```

**2. Code Indexing & Search** (`test_code_workflow`):
```python
async def test_code_workflow(test_services, tmp_path):
    """Test index → search → find_similar workflow."""
    # Create test Python files
    (tmp_path / "test.py").write_text(
        "def fibonacci(n):\n    return n if n < 2 else fib(n-1) + fib(n-2)"
    )

    # Index codebase
    result = await index_codebase(
        directory=str(tmp_path),
        project="test_project",
        recursive=True
    )
    assert result["indexed"] > 0

    # Search by semantic query
    results = await search_code(query="recursive function", project="test_project")
    assert results["count"] > 0

    # Find similar code
    results = await find_similar_code(
        snippet="def fib(n): return n",
        project="test_project"
    )
    assert len(results["results"]) > 0
```

**3. Git Analysis** (`test_git_workflow`):
```python
async def test_git_workflow(test_services, tmp_git_repo):
    """Test git indexing → search → churn → authors workflow."""
    # (tmp_git_repo fixture creates a repo with commits)

    # Search commits
    results = await search_commits(query="initial commit", limit=10)
    assert results["count"] > 0

    # Get file history
    results = await get_file_history(path="test.py", limit=5)
    assert len(results["commits"]) > 0

    # Get churn hotspots
    results = await get_churn_hotspots(days=90, limit=10)
    assert len(results["hotspots"]) >= 0

    # Get code authors
    results = await get_code_authors(path="test.py")
    assert len(results["authors"]) > 0
```

**4. GHAP Learning Loop** (`test_ghap_learning_loop`):
```python
async def test_ghap_learning_loop(test_services):
    """Test 20+ GHAP entries → clustering → value extraction."""
    # Start GHAP entry
    result = await start_ghap(
        domain="testing",
        goal="Validate GHAP workflow",
        hypothesis="Creating entries will enable clustering"
    )
    ghap_id = result["id"]

    # Update with action and prediction
    await update_ghap(
        action="Created test entries",
        prediction="Clustering will identify patterns"
    )

    # Resolve GHAP
    await resolve_ghap(status="success", reflection="Test succeeded")

    # Create 19 more entries (total 20+ for clustering threshold)
    for i in range(19):
        await start_ghap(domain="testing", goal=f"Goal {i}", hypothesis=f"Hyp {i}")
        await update_ghap(action=f"Action {i}", prediction=f"Pred {i}")
        await resolve_ghap(status="success", reflection=f"Reflect {i}")

    # Trigger clustering (called by tools at check_frequency)
    results = await get_clusters(axis="full")
    assert "clusters" in results

    # Validate value
    result = await validate_value(
        text="Pattern identified from testing",
        axis="strategy"
    )
    assert "valid" in result

    # Store value
    result = await store_value(
        text="Testing enables learning",
        axis="strategy",
        explanation="Observed pattern"
    )
    assert "id" in result

    # List values
    results = await list_values(axis="strategy")
    assert results["count"] > 0
```

**5. Context Assembly** (`test_context_assembly`):
```python
async def test_context_assembly(test_services):
    """Test populate → assemble_light → assemble_rich → premortem."""
    # Populate data: memories, code, experiences
    await store_memory(content="Important context", category="context", importance=0.9)

    # (Create code and GHAP entries as in previous tests)

    # Assemble light context (< 100 tokens)
    from learning_memory_server.context import ContextAssembler
    assembler = ContextAssembler(
        searcher=test_services.searcher,
        vector_store=test_services.vector_store
    )

    context = await assembler.assemble_light(query="test context", max_tokens=100)
    assert context.total_tokens < 100
    assert len(context.items) > 0

    # Assemble rich context (< 2000 tokens)
    context = await assembler.assemble_rich(query="test context", max_tokens=2000)
    assert context.total_tokens < 2000

    # Premortem analysis (analyze potential failures)
    result = await assembler.premortem(
        goal="Complete test",
        plan="Run all scenarios",
        max_tokens=500
    )
    assert "risks" in result or "context" in result
```

**Cleanup Strategy**:
- Use `AsyncIterator` fixtures with try/finally cleanup
- Delete test collections after each test
- Use in-memory SQLite (`:memory:`) for metadata isolation
- Temp directories for journal and git repos

**Qdrant Connection**:
```python
@pytest.fixture(scope="session", autouse=True)
def verify_qdrant():
    """Verify Qdrant is available before running tests."""
    import httpx
    try:
        response = httpx.get("http://localhost:6333/health", timeout=5)
        response.raise_for_status()
    except Exception as e:
        pytest.fail(f"Qdrant not available at localhost:6333: {e}")
```

### 4. Performance Benchmarks (`tests/performance/test_benchmarks.py`)

**File Structure**:
```python
"""Performance benchmarks for Learning Memory Server.

Benchmarks measure critical operations against HARD performance targets:
- Code search: p95 < 200ms
- Memory retrieval: p95 < 200ms
- Context assembly: p95 < 500ms
- Clustering: < 5s for 100 entries (4 axes)

Tests FAIL (not warn) if targets are missed.
Results logged to: tests/performance/benchmark_results.json
"""

import json
import time
from pathlib import Path
import numpy as np
import pytest
```

**Shared Fixtures**:
```python
@pytest.fixture(scope="module")
async def benchmark_data(test_services):
    """Populate test data for benchmarks (once per module)."""
    # Store 1000 memories
    for i in range(1000):
        await store_memory(
            content=f"Memory {i} about topic {i % 10}",
            category="fact",
            importance=0.5
        )

    # Index 100 code files
    # Store 100 GHAP entries
    # etc.

    yield test_services
```

**Benchmark Utilities**:
```python
def calculate_p95(measurements: list[float]) -> float:
    """Calculate 95th percentile from measurements."""
    return float(np.percentile(measurements, 95))

def log_benchmark_result(
    name: str,
    p95: float,
    target: float,
    passed: bool,
    iterations: int
):
    """Log benchmark result to JSON file."""
    results_file = Path(__file__).parent / "benchmark_results.json"

    # Load existing results
    if results_file.exists():
        results = json.loads(results_file.read_text())
    else:
        results = []

    # Append new result
    results.append({
        "name": name,
        "p95_ms": p95 * 1000,  # Convert to ms
        "target_ms": target * 1000,
        "passed": passed,
        "iterations": iterations,
        "timestamp": time.time(),
        "percentage_of_target": (p95 / target) * 100 if target > 0 else 0
    })

    # Write back
    results_file.write_text(json.dumps(results, indent=2))
```

**Benchmark Tests**:

**1. Code Search Benchmark** (`test_code_search_performance`):
```python
async def test_code_search_performance(benchmark_data):
    """Code search must have p95 < 200ms (100 iterations)."""
    measurements = []

    for i in range(100):
        start = time.perf_counter()
        await search_code(query=f"function test {i % 10}", project="test")
        elapsed = time.perf_counter() - start
        measurements.append(elapsed)

    p95 = calculate_p95(measurements)
    target = 0.2  # 200ms
    passed = p95 < target

    log_benchmark_result("code_search", p95, target, passed, 100)

    assert passed, (
        f"Code search p95 ({p95*1000:.1f}ms) exceeds target ({target*1000}ms). "
        f"Over by {((p95/target - 1) * 100):.1f}%"
    )
```

**2. Memory Retrieval Benchmark** (`test_memory_retrieval_performance`):
```python
async def test_memory_retrieval_performance(benchmark_data):
    """Memory retrieval must have p95 < 200ms (100 iterations)."""
    measurements = []

    for i in range(100):
        start = time.perf_counter()
        await retrieve_memories(query=f"topic {i % 10}", limit=10)
        elapsed = time.perf_counter() - start
        measurements.append(elapsed)

    p95 = calculate_p95(measurements)
    target = 0.2  # 200ms
    passed = p95 < target

    log_benchmark_result("memory_retrieval", p95, target, passed, 100)

    assert passed, (
        f"Memory retrieval p95 ({p95*1000:.1f}ms) exceeds target ({target*1000}ms). "
        f"Over by {((p95/target - 1) * 100):.1f}%"
    )
```

**3. Context Assembly Benchmark** (`test_context_assembly_performance`):
```python
async def test_context_assembly_performance(benchmark_data):
    """Context assembly must have p95 < 500ms (10 iterations)."""
    from learning_memory_server.context import ContextAssembler

    assembler = ContextAssembler(
        searcher=benchmark_data.searcher,
        vector_store=benchmark_data.vector_store
    )

    measurements = []

    for i in range(10):
        start = time.perf_counter()
        await assembler.assemble_rich(query=f"context {i}", max_tokens=2000)
        elapsed = time.perf_counter() - start
        measurements.append(elapsed)

    p95 = calculate_p95(measurements)
    target = 0.5  # 500ms
    passed = p95 < target

    log_benchmark_result("context_assembly", p95, target, passed, 10)

    assert passed, (
        f"Context assembly p95 ({p95*1000:.1f}ms) exceeds target ({target*1000}ms). "
        f"Over by {((p95/target - 1) * 100):.1f}%"
    )
```

**4. Clustering Benchmark** (`test_clustering_performance`):
```python
async def test_clustering_performance(benchmark_data):
    """Clustering must complete in < 5s for 100 entries (4 axes)."""
    # Store 100 GHAP entries across all test collections
    # (Populated in benchmark_data fixture)

    from learning_memory_server.clustering import ExperienceClusterer

    clusterer = ExperienceClusterer(
        vector_store=benchmark_data.vector_store,
        clusterer=None  # Will initialize HDBSCAN
    )

    start = time.perf_counter()
    await clusterer.cluster_all_axes()  # Clusters all 4 axes
    elapsed = time.perf_counter() - start

    target = 5.0  # 5 seconds
    passed = elapsed < target

    log_benchmark_result("clustering_4_axes", elapsed, target, passed, 1)

    assert passed, (
        f"Clustering ({elapsed:.2f}s) exceeds target ({target}s). "
        f"Over by {((elapsed/target - 1) * 100):.1f}%"
    )
```

**JSON Log Format** (`benchmark_results.json`):
```json
[
  {
    "name": "code_search",
    "p95_ms": 157.3,
    "target_ms": 200.0,
    "passed": true,
    "iterations": 100,
    "timestamp": 1701234567.89,
    "percentage_of_target": 78.65
  },
  {
    "name": "memory_retrieval",
    "p95_ms": 189.2,
    "target_ms": 200.0,
    "passed": true,
    "iterations": 100,
    "timestamp": 1701234568.12,
    "percentage_of_target": 94.6
  }
]
```

### 5. Test Infrastructure

**Collection Isolation**:
- Override `AXIS_COLLECTIONS` dict in `clustering/experience.py`
- Use test collection names: `test_ghap_full`, `test_ghap_strategy`, etc.
- Create collections in fixtures, delete in cleanup
- Pattern (from existing integration tests):
  ```python
  from learning_memory_server.clustering import experience
  original_mapping = experience.AXIS_COLLECTIONS.copy()
  experience.AXIS_COLLECTIONS = {"full": "test_ghap_full", ...}
  try:
      # Run test
  finally:
      experience.AXIS_COLLECTIONS = original_mapping
  ```

**Qdrant Connection Handling**:
- Session-scoped fixture verifies Qdrant availability
- Tests **fail immediately** if Qdrant unavailable (no skip markers)
- Use `httpx` to check health endpoint before tests run

**Shared Fixtures** (`tests/conftest.py` additions):
```python
@pytest.fixture(scope="session")
def verify_qdrant():
    """Fail fast if Qdrant unavailable."""
    import httpx
    try:
        httpx.get("http://localhost:6333/health", timeout=5).raise_for_status()
    except Exception as e:
        pytest.fail(f"Qdrant required at localhost:6333: {e}")

@pytest.fixture
async def test_vector_store():
    """Qdrant vector store for test collections."""
    from learning_memory_server.storage import QdrantVectorStore
    return QdrantVectorStore(url="http://localhost:6333")

@pytest.fixture
async def tmp_git_repo(tmp_path):
    """Create a temporary git repo with commits."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()

    # Initialize repo and create commits
    import subprocess
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_path)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path)

    # Create test file and commit
    (repo_path / "test.py").write_text("def foo(): pass")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

    yield repo_path
```

## Implementation Approach

### Phase 1: Documentation (Day 1)
1. Write GETTING_STARTED.md (60-80 lines)
2. Create docstring audit checklist
3. Verify all 23 MCP tools have docstrings
4. Add missing docstrings to public classes/functions
5. Commit documentation changes

### Phase 2: E2E Tests (Day 2)
1. Create `tests/integration/test_e2e.py`
2. Implement shared fixtures (test_services, tmp_git_repo)
3. Write 5 test scenarios (memory, code, git, GHAP, context)
4. Verify tests pass with real Qdrant
5. Commit E2E tests

### Phase 3: Performance Benchmarks (Day 3)
1. Create `tests/performance/test_benchmarks.py`
2. Implement benchmark utilities (p95 calculation, JSON logging)
3. Write 4 benchmark tests
4. Run benchmarks and verify targets are met
5. Commit performance tests and initial benchmark_results.json

### Phase 4: Integration (Day 4)
1. Run full test suite: `pytest -vvsx`
2. Fix any failing tests
3. Verify no regressions in existing tests
4. Run gate checks
5. Create changelog

## File Locations

```
learning-memory-server/
├── GETTING_STARTED.md                     # NEW: AI agent onboarding
├── tests/
│   ├── conftest.py                        # UPDATED: Add shared fixtures
│   ├── integration/
│   │   └── test_e2e.py                   # NEW: 5 E2E scenarios
│   └── performance/
│       ├── test_benchmarks.py            # NEW: 4 performance benchmarks
│       └── benchmark_results.json        # NEW: Benchmark logs (gitignored)
└── src/learning_memory_server/
    └── server/tools/*.py                  # UPDATED: Verify docstrings
```

## Risks and Mitigations

**Risk**: Performance targets may not be met initially
- **Mitigation**: Benchmarks identify bottlenecks; iterate on optimization

**Risk**: E2E tests may be flaky with timing-dependent operations
- **Mitigation**: Use deterministic test data; avoid time-based assertions

**Risk**: Docstring audit is subjective (what counts as "complete"?)
- **Mitigation**: Reviewers use judgment; focus on public APIs

**Risk**: Test collections may conflict with production data
- **Mitigation**: Use test-prefixed collection names; verify isolation in fixtures

## Success Criteria

1. **GETTING_STARTED.md** exists at repo root, under 100 lines, provides navigation
2. **All 23 MCP tools** have complete Google-style docstrings
3. **5 E2E test scenarios** pass with real Qdrant
4. **4 performance benchmarks** pass with targets met
5. **Test infrastructure** uses isolated collections, fails (not skips) on missing Qdrant
6. **Full test suite** passes: `pytest -vvsx`
7. **Gate checks** pass: linting, type checking, no untracked TODOs

## Open Questions

None. Proposal is comprehensive and ready for review.
