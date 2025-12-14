# Bug Pattern Analysis: Themes and Recommendations

**Date**: 2024-12-14
**Analysis Method**: Four independent Opus agents reviewed 38 bug reports (BUG-001 through BUG-051) and session summaries
**Purpose**: Identify patterns to improve workflow, sharpen protocols, and add guardrails

---

## Summary Chart

### Identified Themes

| ID | Theme | Benefit | Complexity | Confidence | Analysts |
|----|-------|---------|------------|------------|----------|
| T1 | Schema/Type Inconsistency | High | Medium | Very High | 4/4 |
| T2 | Duplicate Type Definitions Without Inheritance | High | Medium | Very High | 3/4 |
| T3 | Missing Initialization Patterns | High | Low | Very High | 4/4 |
| T4 | Data Format/Parsing Mismatches | Medium | Low | Very High | 3/4 |
| T5 | Missing Input Validation | Medium | Low | Very High | 4/4 |
| T6 | Configuration/Path Issues | Medium | Medium | High | 3/4 |
| T7 | Test-Production Divergence | High | Medium | High | 3/4 |
| T8 | Import Order/Heavy Dependencies | High | Medium | Very High | 2/4 |
| T9 | Algorithm Parameter Tuning | Medium | Medium | Medium | 2/4 |
| T10 | Race Conditions/Concurrency | Medium | High | Medium | 1/4 |
| T11 | Documentation vs Implementation Drift | Medium | Low | High | 2/4 |
| T12 | Workflow/Gate Script Brittleness | Medium | Medium | High | 1/4 |
| T13 | API Response Bloat | Low | Low | High | 1/4 |
| T14 | Hash/Eq Contract Violations | Low | Low | Very High | 2/4 |

### Recommendations

| ID | Recommendation | Benefit | Complexity | Confidence | Addresses |
|----|----------------|---------|------------|------------|-----------|
| R1 | Single Source of Truth for Types | High | Medium | Very High | T1, T2, T7 |
| R2 | Schema Generation from Code | High | Low | Very High | T1, T11 |
| R3 | Mandatory Initialization Pattern | High | Low | Very High | T3 |
| R4 | Defensive Input Validation | Medium | Low | Very High | T5 |
| R5 | External API Schema Conformance Tests | High | Medium | Very High | T1, T11 |
| R6 | Test-Production Parity Verification | High | Medium | High | T7 |
| R7 | Lazy Import for Heavy Dependencies | High | Medium | Very High | T8 |
| R8 | Centralized Configuration Management | Medium | Medium | High | T6 |
| R9 | Cold-Start Testing Protocol | Medium | Low | Very High | T3, T7 |
| R10 | Cross-Component Integration Tests | High | Medium | High | T1, T7 |
| R11 | Type-Safe Datetime/Numeric Handling | Medium | Low | Very High | T4 |
| R12 | Platform-Specific Pre-Checks | Medium | Low | High | T6, T8 |
| R13 | Parameter Validation with Production Data | Medium | Medium | Medium | T9 |
| R14 | Gate Script Auto-Detection | Medium | Medium | High | T12 |
| R15 | Response Efficiency Tests | Low | Low | High | T13 |
| R16 | Data Structure Contract Tests | Low | Low | Very High | T14 |
| R17 | Reviewer Checklist Additions | Medium | Low | High | T3, T5, T7 |

### Legend

**Benefit**:
- **High**: Prevents >15% of bugs or addresses critical failures
- **Medium**: Prevents 5-15% of bugs or improves reliability
- **Low**: Prevents <5% of bugs or is nice-to-have

**Complexity**:
- **High**: Requires significant refactoring, multi-day effort
- **Medium**: Requires moderate changes, hours to implement
- **Low**: Simple fix, can be done quickly

**Confidence**:
- **Very High**: Multiple analysts identified, clear evidence, well-understood fix
- **High**: Strong evidence, straightforward fix
- **Medium**: Some evidence, fix approach less certain

---

## Part 1: Identified Themes

### T1: Schema/Type Inconsistency

**Analysts**: 4/4 (Root Causes, Process Gaps, Testing Gaps, Architecture)
**Benefit**: High
**Complexity**: Medium (to fix comprehensively)
**Confidence**: Very High

**Description**: Multiple locations define the same types, enums, or schemas with incompatible values. When the "advertised" contract differs from the "enforced" contract, API consumers receive confusing errors.

**Evidence**:
- **BUG-026**: JSON schema enum values in `tools/__init__.py` don't match validation enums in `tools/enums.py`. Schema advertises `"optimization"`, `"other"`, but validation only accepts `"configuration"`, `"performance"`, `"security"`, `"integration"`.
- **BUG-040**: `context/searcher_types.py` defines `CodeResult` with `start_line`/`end_line`, but `search/results.py` uses `line_start`/`line_end`.
- **BUG-050/BUG-051**: Hooks used custom JSON schema `{"type": ..., "content": ...}` instead of Claude Code's required `{"hookSpecificOutput": {"additionalContext": ...}}`.

**Frequency**: 7 bugs (18% of analyzed bugs)

**Root Pattern**: No single source of truth for type definitions. Parallel definitions evolved independently.

---

### T2: Duplicate Type Definitions Without Inheritance

**Analysts**: 3/4 (Root Causes, Process Gaps, Architecture)
**Benefit**: High
**Complexity**: Medium
**Confidence**: Very High

**Description**: The codebase has multiple parallel type hierarchies representing the same concepts but with incompatible implementations. Abstract base classes are defined but concrete implementations don't inherit from them.

**Evidence**:
- **BUG-041**: Abstract `Searcher` in `context/searcher_types.py` has 5 abstract methods, but concrete `Searcher` in `search/searcher.py` doesn't inherit from it. Method signatures differ.
- **BUG-040**: Result dataclasses duplicated between `search/results.py` and `context/searcher_types.py`. Field names differ (`start_line` vs `line_start`), nested types differ (`dict | None` vs `Lesson | None`).

**Frequency**: 4 bugs (11% of analyzed bugs)

**Root Pattern**: Similar functionality implemented twice without a shared base, violating DRY and type safety.

---

### T3: Missing Initialization Patterns

**Analysts**: 4/4 (Root Causes, Process Gaps, Testing Gaps, Architecture)
**Benefit**: High
**Complexity**: Low
**Confidence**: Very High

**Description**: Required resources (collections, configurations) are assumed to exist but never created, leading to 404 errors on first use. The `ensure_exists` pattern is applied in some places but not others.

**Evidence**:
- **BUG-043**: `memories`, `commits`, and `values` collections never created. Returns `404 (Not Found) - Collection 'memories' doesn't exist!`. Meanwhile `CodeIndexer` has `_ensure_collection()` and `ObservationPersister` has `ensure_collections()`.
- **BUG-016**: GHAP collections had same issue until `ensure_collections()` was added.

**Frequency**: 4 bugs (11% of analyzed bugs)

**Root Pattern**: Inconsistent application of known-good patterns. Some modules have it, others don't.

---

### T4: Data Format/Parsing Mismatches

**Analysts**: 3/4 (Root Causes, Process Gaps, Architecture)
**Benefit**: Medium
**Complexity**: Low
**Confidence**: Very High

**Description**: Data written in one format but read expecting another. Datetime handling and numeric conversions are particularly error-prone.

**Evidence**:
- **BUG-027**: `created_at` stored as ISO string (`entry.created_at.isoformat()`) but read expecting numeric timestamp (`datetime.fromtimestamp()`). Raises TypeError.
- **BUG-034**: Float timeout truncated via `int()` cast. `int(0.5)` returns `0`, changing semantic from 500ms timeout to infinite wait.

**Frequency**: 3 bugs (8% of analyzed bugs)

**Root Pattern**: No enforced contract between writer and reader. No round-trip tests.

---

### T5: Missing Input Validation

**Analysts**: 4/4 (Root Causes, Process Gaps, Testing Gaps, Architecture)
**Benefit**: Medium
**Complexity**: Low
**Confidence**: Very High

**Description**: Functions accept inputs without validation, leading to cryptic errors (KeyError, TypeError) deep in the call stack instead of descriptive messages at the boundary.

**Evidence**:
- **BUG-036**: `distribute_budget(context_types=["invalid_type"])` raises `KeyError: 'invalid_type'` because no validation against `SOURCE_WEIGHTS.keys()`.
- **BUG-029**: `start_ghap` with active GHAP entry returns generic `"internal_error"` instead of helpful message about existing entry.

**Frequency**: 3 bugs (8% of analyzed bugs)

**Root Pattern**: Trust callers to provide valid input. No defensive programming at module boundaries.

---

### T6: Configuration/Path Issues

**Analysts**: 3/4 (Root Causes, Process Gaps, Testing Gaps)
**Benefit**: Medium
**Complexity**: Medium
**Confidence**: High

**Description**: Hardcoded paths, incorrect entry points, or environment-specific configurations that break in different contexts.

**Evidence**:
- **BUG-033**: MCP client uses `["python", "-m", "clams"]` but no `__main__.py` exists; should use `.venv/bin/clams-server`.
- **BUG-042**: macOS-specific MPS fork() incompatibility.
- **BUG-037**: Timeout of 5 seconds insufficient for 4.6-6.2 second import times.

**Frequency**: 4 bugs (11% of analyzed bugs)

**Root Pattern**: Configuration scattered across multiple locations. Platform assumptions not validated.

---

### T7: Test-Production Divergence

**Analysts**: 3/4 (Root Causes, Process Gaps, Testing Gaps)
**Benefit**: High
**Complexity**: Medium
**Confidence**: High

**Description**: Code works in tests but fails in production due to different configurations, mocks that don't match production behavior, or test-specific parameter overrides.

**Evidence**:
- **BUG-033**: Integration tests use `.venv/bin/clams-server` successfully, but production hook uses incorrect `python -m clams`.
- **BUG-031**: Test suite uses `min_cluster_size=3` but production uses `min_cluster_size=5`.
- **BUG-040**: Tests use `MockSearcher` that doesn't match production `Searcher` interface.

**Frequency**: 4 bugs (11% of analyzed bugs)

**Root Pattern**: Test fixtures and mocks don't accurately represent production. Tests pass but code breaks in real use.

---

### T8: Import Order/Heavy Dependencies

**Analysts**: 2/4 (Process Gaps, Testing Gaps)
**Benefit**: High
**Complexity**: Medium
**Confidence**: Very High

**Description**: Python imports happen at module load time, causing side effects before application logic can intercede. Heavy dependencies (PyTorch, MPS, sentence-transformers) initialize during import.

**Evidence**:
- **BUG-042**: `daemonize()` uses `os.fork()`, but PyTorch has already initialized MPS via the import chain: `main.py` -> `clams.embedding` -> `nomic.py` -> `torch`. MPS doesn't support fork() after initialization.
- **BUG-037**: Import chain pulls in heavy libraries that take 3.2+ seconds to load, exceeding verification timeout.

**Frequency**: 2 bugs (5% of analyzed bugs, but both critical)

**Root Pattern**: Eager imports of heavy dependencies. Fork after initialization.

---

### T9: Algorithm Parameter Tuning

**Analysts**: 2/4 (Root Causes, Testing Gaps)
**Benefit**: Medium
**Complexity**: Medium
**Confidence**: Medium

**Description**: Algorithm parameters work in testing but fail with real-world data distributions. Parameters tuned for synthetic test data.

**Evidence**:
- **BUG-031**: HDBSCAN `min_cluster_size=5`, `min_samples=3` too conservative for 63 real entries. All points classified as noise. Test suite used different parameters.

**Frequency**: 2 bugs (5% of analyzed bugs)

**Root Pattern**: Parameters tuned for test cases, not validated against production data characteristics.

---

### T10: Race Conditions/Concurrency

**Analysts**: 1/4 (Root Causes)
**Benefit**: Medium
**Complexity**: High
**Confidence**: Medium

**Description**: Async operations, concurrent access, or timing-dependent code that fails under certain conditions.

**Evidence**:
- **BUG-001**: Race condition in GHAP state management with multiple agents.
- **BUG-002**: Concurrent vector store operations.
- **BUG-013**: Async context not properly propagated.

**Frequency**: 4 bugs (11% of analyzed bugs)

**Root Pattern**: Async code assumes sequential execution. Shared state not properly synchronized.

**Note**: Lower confidence because only one analyst focused on this and the evidence was less detailed in the bug reports reviewed.

---

### T11: Documentation vs Implementation Drift

**Analysts**: 2/4 (Process Gaps, Testing Gaps)
**Benefit**: Medium
**Complexity**: Low
**Confidence**: High

**Description**: External APIs implemented based on incomplete or incorrect documentation. Actual required format differs from implementation.

**Evidence**:
- **BUG-050/BUG-051**: Hooks output JSON in custom format; Claude Code expects specific schema with `hookSpecificOutput.additionalContext`.
- Session friction: Documentation mismatch between Claude Code examples and actual requirements.

**Frequency**: 2 bugs (5% of analyzed bugs)

**Root Pattern**: External API contracts not verified against authoritative documentation.

---

### T12: Workflow/Gate Script Brittleness

**Analysts**: 1/4 (Architecture, with session evidence)
**Benefit**: Medium
**Complexity**: Medium
**Confidence**: High

**Description**: CLAWS workflow infrastructure makes assumptions about project structure that break for non-standard changes (hooks-only, frontend-only).

**Evidence**:
- Session `64997087`: Gate didn't recognize `clams/` as valid implementation code.
- Session `df8f0602`: Gate hardcoded for Python projects, ran pytest/mypy for shell script changes.
- Session friction: Worktree copies of `.claude/bin` scripts are stale.

**Frequency**: 4 session friction points

**Root Pattern**: Gate scripts assume uniform project structure. No project-type detection.

---

### T13: API Response Bloat

**Analysts**: 1/4 (Testing Gaps)
**Benefit**: Low
**Complexity**: Low
**Confidence**: High

**Description**: APIs return excessive data in responses, wasting tokens/bandwidth. Tests verify functionality but not response efficiency.

**Evidence**:
- **BUG-030**: GHAP tools return full records on every operation. During bulk generation (100 entries), wastes ~50,000 tokens.

**Frequency**: 1 bug (3% of analyzed bugs)

**Root Pattern**: Verbose responses designed without considering actual usage patterns.

---

### T14: Hash/Eq Contract Violations

**Analysts**: 2/4 (Root Causes, Testing Gaps)
**Benefit**: Low
**Complexity**: Low
**Confidence**: Very High

**Description**: Classes implement hash/equality contracts incorrectly, leading to subtle bugs in set/dict operations.

**Evidence**:
- **BUG-028**: `ContextItem.__hash__` uses first 100 chars but `__eq__` uses full content. Two items with identical prefixes but different content have same hash but are not equal.

**Frequency**: 1 bug (3% of analyzed bugs)

**Root Pattern**: Hash/eq invariant not explicitly tested.

---

## Part 2: Recommendations

### R1: Single Source of Truth for Types

**Benefit**: High
**Complexity**: Medium
**Confidence**: Very High
**Addresses**: T1, T2, T7

**Description**: Consolidate duplicate type definitions into a single canonical module. All other modules must import from this source.

**Implementation**:
1. Create `src/clams/types/` module as canonical location for all shared types
2. Merge `context/searcher_types.py` result types into `search/results.py`
3. Make concrete `Searcher` inherit from abstract `Searcher` ABC
4. Delete duplicate definitions from `context/`
5. Add pre-commit hook or CI check that fails if type definitions exist outside `types/`

**Example**:
```python
# Before: Two incompatible definitions
# context/searcher_types.py
@dataclass
class CodeResult:
    start_line: int
    end_line: int

# search/results.py
@dataclass
class CodeResult:
    line_start: int
    line_end: int

# After: Single source
# search/results.py (canonical)
@dataclass
class CodeResult:
    line_start: int
    line_end: int

# context/searcher_types.py
from clams.search.results import CodeResult  # Import, don't redefine
```

**Verification**: `mypy --strict` should catch type mismatches. Add test that verifies `isinstance(Searcher(), SearcherABC)`.

---

### R2: Schema Generation from Code

**Benefit**: High
**Complexity**: Low
**Confidence**: Very High
**Addresses**: T1, T11

**Description**: Generate JSON schemas from Python enums/dataclasses rather than maintaining them manually. Schemas and validation can never drift.

**Implementation**:
1. In `tools/__init__.py`, generate enum values from Python enums:
   ```python
   "domain": {
       "type": "string",
       "enum": [e.value for e in GHAPDomain]  # Generated, not hardcoded
   }
   ```
2. Create schema generation utility in `tools/schema.py`
3. Add regression test that verifies schema enum values == validation enum values

**Example**:
```python
# tools/schema.py
from clams.server.tools.enums import GHAPDomain, GHAPStrategy

def get_domain_enum():
    return [e.value for e in GHAPDomain]

def get_strategy_enum():
    return [e.value for e in GHAPStrategy]
```

**Verification**: Test that programmatically compares schema values to enum values.

---

### R3: Mandatory Initialization Pattern

**Benefit**: High
**Complexity**: Low
**Confidence**: Very High
**Addresses**: T3

**Description**: Establish a standard `_ensure_collection()` pattern for all vector store consumers. No upsert without ensure.

**Implementation**:
1. Create base mixin or decorator that all collection-using classes use:
   ```python
   class CollectionMixin:
       _collection_ensured: bool = False

       async def _ensure_collection(self, name: str):
           if not self._collection_ensured:
               await self.vector_store.create_collection_if_not_exists(name)
               self._collection_ensured = True
   ```
2. Apply to `memory.py`, `git/analyzer.py`, `values/store.py`
3. Add integration test that starts with empty Qdrant and exercises all paths

**Verification**: Integration test with fresh Qdrant instance. No 404 errors on first use.

---

### R4: Defensive Input Validation

**Benefit**: Medium
**Complexity**: Low
**Confidence**: Very High
**Addresses**: T5

**Description**: Validate all inputs at public function boundaries with descriptive error messages that list valid options.

**Implementation**:
1. Add validation at the start of public functions:
   ```python
   def distribute_budget(context_types: list[str], ...):
       invalid = set(context_types) - SOURCE_WEIGHTS.keys()
       if invalid:
           valid = ", ".join(SOURCE_WEIGHTS.keys())
           raise ValueError(f"Invalid context types: {invalid}. Valid: {valid}")
   ```
2. For GHAP tools, return user-friendly errors instead of generic "internal_error"
3. Add negative test cases for invalid inputs

**Verification**: Tests that pass invalid inputs and verify error messages contain valid options.

---

### R5: External API Schema Conformance Tests

**Benefit**: High
**Complexity**: Medium
**Confidence**: Very High
**Addresses**: T1, T11

**Description**: Create explicit conformance tests for any external API integration. Verify output matches documented schemas.

**Implementation**:
1. For Claude Code hooks, add test that parses output and verifies against official schema:
   ```python
   def test_session_start_hook_schema():
       output = run_hook("session_start.sh")
       parsed = json.loads(output)
       assert "hookSpecificOutput" in parsed
       assert "additionalContext" in parsed["hookSpecificOutput"]
   ```
2. Store expected schema as test data with link to authoritative documentation
3. Add test for each external integration point

**Verification**: CI fails if hook output doesn't match expected schema.

---

### R6: Test-Production Parity Verification

**Benefit**: High
**Complexity**: Medium
**Confidence**: High
**Addresses**: T7

**Description**: Ensure tests use the same configurations, commands, and interfaces as production.

**Implementation**:
1. Add "production parity" integration tests that:
   - Use exact production commands (`.venv/bin/clams-server`, not `python -m`)
   - Use production configuration values (not test-specific overrides)
   - Verify mocks implement the same interface as production classes
2. Add to reviewer checklist: "Do tests use production configurations?"
3. Create test that verifies `MockSearcher` interface matches `Searcher`

**Example**:
```python
def test_mock_searcher_matches_production():
    mock_methods = set(dir(MockSearcher))
    prod_methods = set(dir(Searcher))
    # Verify mock has all production methods
    missing = prod_methods - mock_methods
    assert not missing, f"Mock missing: {missing}"
```

**Verification**: CI includes production-parity test suite.

---

### R7: Lazy Import for Heavy Dependencies

**Benefit**: High
**Complexity**: Medium
**Confidence**: Very High
**Addresses**: T8

**Description**: PyTorch, sentence-transformers, and other heavy dependencies must be lazy-imported to avoid import-time side effects.

**Implementation**:
1. Create import guidelines in CLAUDE.md:
   - Heavy packages (torch, sentence_transformers) must be imported inside functions
   - Never at module top level
2. Add pre-commit hook that detects top-level imports of heavy packages
3. Refactor `clams.embedding` to lazy-import torch:
   ```python
   # Before
   import torch  # At top level

   # After
   def get_embeddings():
       import torch  # Lazy import
       ...
   ```
4. Document fork/daemon constraint: "Do not fork() after importing torch"

**Verification**: Pre-commit hook. Test that measures import time of main module.

---

### R8: Centralized Configuration Management

**Benefit**: Medium
**Complexity**: Medium
**Confidence**: High
**Addresses**: T6

**Description**: Create a single source for all configuration values. No hardcoded paths scattered across files.

**Implementation**:
1. Create `src/clams/config.py` that exports all configuration:
   ```python
   SERVER_COMMAND = [".venv/bin/clams-server"]
   VERIFICATION_TIMEOUT = 15  # seconds, accounts for heavy imports
   DEFAULT_MIN_CLUSTER_SIZE = 3
   ```
2. Shell scripts read from this or a generated config file
3. Add CI check that greps for hardcoded paths outside config module

**Verification**: Grep-based CI check for hardcoded paths.

---

### R9: Cold-Start Testing Protocol

**Benefit**: Medium
**Complexity**: Low
**Confidence**: Very High
**Addresses**: T3, T7

**Description**: Test scenarios where resources don't exist yet. Every storage operation tested with empty collections.

**Implementation**:
1. Add "cold-start" test fixture that starts with no pre-existing resources
2. Test matrix includes: `{fresh_db, populated_db} x {all_operations}`
3. Add separate CI job that runs tests with empty Qdrant

**Example**:
```python
@pytest.fixture
def cold_start_db():
    """Database with no collections - simulates first use."""
    db = create_fresh_qdrant()
    yield db
    db.cleanup()

def test_store_memory_cold_start(cold_start_db):
    # Should not raise 404
    result = store_memory(cold_start_db, content="test")
    assert result.success
```

**Verification**: CI job with empty database.

---

### R10: Cross-Component Integration Tests

**Benefit**: High
**Complexity**: Medium
**Confidence**: High
**Addresses**: T1, T7

**Description**: Add tests that verify components work together, not just in isolation. Cover integration boundaries.

**Implementation**:
1. Add round-trip tests: store then retrieve, serialize then deserialize
2. Add schema validation tests: verify advertised enums match accepted values
3. Add E2E tests that use actual components, not mocks
4. Test data flows across module boundaries

**Example**:
```python
def test_ghap_round_trip():
    """Verify GHAP can be stored and retrieved with same data."""
    original = GHAPEntry(domain="debugging", ...)
    stored_id = start_ghap(original)
    retrieved = get_active_ghap()
    assert retrieved.domain == original.domain
    assert retrieved.created_at == original.created_at  # Datetime survives round-trip
```

**Verification**: Integration test suite in CI.

---

### R11: Type-Safe Datetime/Numeric Handling

**Benefit**: Medium
**Complexity**: Low
**Confidence**: Very High
**Addresses**: T4

**Description**: Establish standard serialization formats. Use consistent patterns for datetime and numeric conversions.

**Implementation**:
1. Create utility functions used consistently:
   ```python
   # utils/datetime.py
   def serialize_datetime(dt: datetime) -> str:
       return dt.isoformat()

   def deserialize_datetime(s: str) -> datetime:
       return datetime.fromisoformat(s)
   ```
2. Remove `int()` casts on timeout values - use `float` or `math.ceil()`
3. Add round-trip tests for all serialization

**Verification**: Property-based tests for round-trip serialization.

---

### R12: Platform-Specific Pre-Checks

**Benefit**: Medium
**Complexity**: Low
**Confidence**: High
**Addresses**: T6, T8

**Description**: Add explicit platform checks at startup that warn about known incompatibilities.

**Implementation**:
1. Add startup check for macOS + MPS + daemon mode:
   ```python
   def check_platform_compatibility():
       if sys.platform == "darwin" and daemon_mode:
           if torch.backends.mps.is_available():
               warnings.warn("MPS not compatible with daemon mode on macOS")
   ```
2. Create platform-specific test matrix in CI (macOS, Linux)
3. Document known platform issues in CLAUDE.md

**Verification**: CI runs on multiple platforms.

---

### R13: Parameter Validation with Production Data

**Benefit**: Medium
**Complexity**: Medium
**Confidence**: Medium
**Addresses**: T9

**Description**: Create data profiles describing expected production characteristics. Test algorithms against realistic data.

**Implementation**:
1. Document data profiles: "Expect 20-100 GHAP entries, mostly single-theme"
2. Generate synthetic data matching production profiles
3. Test algorithms work correctly across expected data ranges
4. Add benchmark tests that verify clustering produces reasonable results

**Example**:
```python
def test_clustering_with_production_data_profile():
    """Verify clustering works with realistic data distribution."""
    # Generate data matching production profile
    entries = generate_ghap_entries(count=63, themes=3, noise_ratio=0.2)

    clusters = run_clustering(entries)

    # Should produce at least some clusters, not all noise
    assert len(clusters) >= 1
    noise_count = sum(1 for e in entries if e.cluster == -1)
    assert noise_count < len(entries) * 0.9  # <90% noise
```

**Verification**: Benchmark tests with production-like data.

---

### R14: Gate Script Auto-Detection

**Benefit**: Medium
**Complexity**: Medium
**Confidence**: High
**Addresses**: T12

**Description**: Make gate scripts detect project type automatically and adjust checks accordingly.

**Implementation**:
1. Add project-type detection to `claws-gate`:
   ```bash
   detect_project_type() {
       if [[ -f "pyproject.toml" ]]; then
           echo "python"
       elif [[ -f "package.json" ]]; then
           echo "javascript"
       elif [[ -d "clams/hooks" ]]; then
           echo "hooks"
       fi
   }
   ```
2. Skip inapplicable checks (no pytest for shell-only changes)
3. Add `clams/` and `clams/hooks/` to valid implementation directories

**Verification**: Test gates with Python-only, frontend-only, and hooks-only changes.

---

### R15: Response Efficiency Tests

**Benefit**: Low
**Complexity**: Low
**Confidence**: High
**Addresses**: T13

**Description**: Add tests that verify API responses don't exceed expected sizes.

**Implementation**:
1. Add response size assertions:
   ```python
   def test_ghap_response_size():
       response = start_ghap(...)
       response_size = len(json.dumps(response))
       assert response_size < 500, f"Response too large: {response_size} bytes"
   ```
2. Track token usage in tests for LLM-facing APIs
3. Benchmark response generation

**Verification**: Tests with size assertions.

---

### R16: Data Structure Contract Tests

**Benefit**: Low
**Complexity**: Low
**Confidence**: Very High
**Addresses**: T14

**Description**: Add explicit tests for hash/eq consistency in all hashable classes.

**Implementation**:
1. Add contract tests:
   ```python
   def test_context_item_hash_eq_contract():
       """Verify hash/eq contract: equal objects must have equal hashes."""
       item1 = ContextItem(content="x" * 200)
       item2 = ContextItem(content="x" * 200)

       if item1 == item2:
           assert hash(item1) == hash(item2), "Equal items must have equal hashes"

       # Also test: same hash doesn't imply equality (allowed but test edge cases)
       item3 = ContextItem(content="x" * 100 + "a" * 100)
       item4 = ContextItem(content="x" * 100 + "b" * 100)
       # These might have same hash (first 100 chars) but should not be equal
       if hash(item3) == hash(item4):
           assert item3 != item4 or item3 == item4  # Just verify it doesn't crash
   ```
2. Use property-based testing (hypothesis) for thorough coverage

**Verification**: Contract tests in test suite.

---

### R17: Reviewer Checklist Additions

**Benefit**: Medium
**Complexity**: Low
**Confidence**: High
**Addresses**: T3, T5, T7

**Description**: Add specific items to the code review checklist to catch common patterns.

**Implementation**: Add to `.claude/roles/reviewer.md`:

```markdown
## Additional Checklist Items

### Initialization Patterns
- [ ] If adding a new collection/resource, does it have `ensure_exists` pattern?
- [ ] Does this code upsert without ensuring collection exists first?

### Input Validation
- [ ] Are all public function inputs validated with helpful error messages?
- [ ] Do error messages list valid options?

### Test-Production Parity
- [ ] Do tests use production configurations or explicitly justify test-specific values?
- [ ] Do mocks implement the same interface as production classes?

### Type Consistency
- [ ] If defining new types, are they in the canonical `types/` location?
- [ ] Are there duplicate type definitions that should be consolidated?
```

**Verification**: Reviewer checklist is followed.

---

## Part 3: Implementation Priority

Based on benefit, complexity, and confidence, here's the recommended implementation order:

### Tier 1: High Impact, Low Complexity (Do First)
1. **R3**: Mandatory Initialization Pattern
2. **R2**: Schema Generation from Code
3. **R4**: Defensive Input Validation
4. **R17**: Reviewer Checklist Additions
5. **R11**: Type-Safe Datetime/Numeric Handling

### Tier 2: High Impact, Medium Complexity (Do Soon)
6. **R1**: Single Source of Truth for Types
7. **R7**: Lazy Import for Heavy Dependencies
8. **R5**: External API Schema Conformance Tests
9. **R10**: Cross-Component Integration Tests
10. **R6**: Test-Production Parity Verification

### Tier 3: Medium Impact (Do When Convenient)
11. **R9**: Cold-Start Testing Protocol
12. **R8**: Centralized Configuration Management
13. **R12**: Platform-Specific Pre-Checks
14. **R14**: Gate Script Auto-Detection
15. **R13**: Parameter Validation with Production Data

### Tier 4: Low Impact (Nice to Have)
16. **R15**: Response Efficiency Tests
17. **R16**: Data Structure Contract Tests

---

## Appendix: Bug-to-Theme Mapping

| Bug ID | Themes | Description |
|--------|--------|-------------|
| BUG-001 | T10 | Race condition in GHAP state |
| BUG-002 | T10 | Concurrent vector store operations |
| BUG-006 | T6 | Path resolution in worktrees |
| BUG-011 | T6 | Entry point mismatch |
| BUG-013 | T10 | Async context not propagated |
| BUG-016 | T3 | GHAP collections not created |
| BUG-026 | T1, T4, T5 | Enum mismatch schema vs validation |
| BUG-027 | T4 | Datetime format mismatch |
| BUG-028 | T14 | Hash/eq contract violation |
| BUG-029 | T5 | GHAP start silent failure |
| BUG-030 | T13 | Response bloat |
| BUG-031 | T9, T7 | Clustering parameters |
| BUG-033 | T6, T7, T11 | Wrong server command |
| BUG-034 | T4 | Float timeout truncation |
| BUG-036 | T5 | KeyError on invalid input |
| BUG-037 | T6, T8 | Import timeout |
| BUG-040 | T1, T2, T7 | Duplicate result types |
| BUG-041 | T1, T2 | Abstract/concrete Searcher conflict |
| BUG-042 | T6, T8 | MPS fork crash |
| BUG-043 | T3 | Collections not created |
| BUG-050 | T1, T11 | Hook schema wrong |
| BUG-051 | T1, T11 | Hook schema wrong |
