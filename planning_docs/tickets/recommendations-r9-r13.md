# Recommendation Tickets: R9-R13

This file contains implementation tickets for workflow improvements based on bug pattern analysis. These recommendations are from Tier 3 (Medium Impact, Do When Convenient).

---

## R9: Cold-Start Testing Protocol

**Addresses Themes**: T3 (Missing Initialization Patterns), T7 (Test-Production Divergence)
**Overall Benefit**: Medium
**Overall Complexity**: Low
**Confidence**: Very High

**Problem Summary**: Tests often run against pre-populated databases or mocked resources, missing bugs that only manifest on first use when collections/resources don't exist yet. BUG-043 (collections never created, 404 errors) and BUG-016 (GHAP collections) demonstrate this pattern.

---

### R9-A: Create Cold-Start Fixture Infrastructure

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
No standardized test fixture exists to simulate first-use scenarios. BUG-043 showed that `memories`, `commits`, and `values` collections were never created, causing 404 errors. Tests passed because they used pre-populated fixtures.

**Acceptance Criteria**:
- [ ] Create `tests/fixtures/cold_start.py` with fixtures for empty Qdrant
- [ ] Create `cold_start_qdrant` pytest fixture that provides a clean Qdrant instance
- [ ] Create `cold_start_db` fixture for empty SQLite (if applicable)
- [ ] Fixtures clean up after themselves
- [ ] Fixtures can be parameterized for both cold-start and populated scenarios

**Implementation Notes**:
```python
# tests/fixtures/cold_start.py
import pytest
from qdrant_client import QdrantClient

@pytest.fixture
def cold_start_qdrant():
    """Qdrant instance with no pre-existing collections - simulates first use."""
    client = QdrantClient(":memory:")
    # Do NOT create any collections - that's the point
    yield client
    # Cleanup happens automatically with in-memory instance

@pytest.fixture(params=["cold_start", "populated"])
def db_state(request, cold_start_qdrant, populated_qdrant):
    """Parameterized fixture to test both cold-start and populated scenarios."""
    if request.param == "cold_start":
        return cold_start_qdrant
    return populated_qdrant
```

**Testing Requirements**:
- Verify fixture creates truly empty Qdrant (list_collections returns [])
- Verify fixture isolation (tests don't leak state)
- Verify parameterized version works with pytest markers

---

### R9-B: Add Cold-Start Tests for Memory Operations

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R9-A

**Problem Statement**:
BUG-043 specifically showed `store_memory()` fails on cold start because the `memories` collection doesn't exist. Need explicit tests that exercise memory storage from a completely fresh state.

**Acceptance Criteria**:
- [ ] Test `store_memory()` succeeds on cold start (no 404)
- [ ] Test `retrieve_memories()` returns empty on cold start (not error)
- [ ] Test `list_memories()` returns empty on cold start (not error)
- [ ] Test `delete_memory()` handles non-existent memory gracefully
- [ ] All tests use `cold_start_qdrant` fixture

**Implementation Notes**:
Add to `tests/integration/test_memory_cold_start.py`:
```python
import pytest
from clams.server.memory import MemoryStore

@pytest.mark.integration
class TestMemoryColdStart:
    async def test_store_memory_cold_start(self, cold_start_qdrant):
        """First memory storage should auto-create collection."""
        store = MemoryStore(client=cold_start_qdrant)
        result = await store.store(content="test", category="fact")
        assert result.success
        # Collection should now exist
        collections = cold_start_qdrant.get_collections()
        assert "memories" in [c.name for c in collections.collections]

    async def test_retrieve_empty_cold_start(self, cold_start_qdrant):
        """Query on empty collection returns empty, not error."""
        store = MemoryStore(client=cold_start_qdrant)
        results = await store.retrieve("anything")
        assert results == []  # Empty, not exception
```

**Testing Requirements**:
- Run tests with `pytest -m integration` to ensure they hit real Qdrant
- Verify no 404 errors in test output
- Verify `ensure_collection()` is called before first operation

---

### R9-C: Add Cold-Start Tests for Git/Commit Operations

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R9-A

**Problem Statement**:
BUG-043 showed `commits` collection was also never created. Git indexing and search operations need cold-start coverage.

**Acceptance Criteria**:
- [ ] Test `index_commits()` succeeds on cold start
- [ ] Test `search_commits()` returns empty on cold start (not error)
- [ ] Test `get_file_history()` returns empty on cold start (not error)
- [ ] Test `get_churn_hotspots()` returns empty on cold start (not error)

**Implementation Notes**:
Add to `tests/integration/test_git_cold_start.py`:
```python
@pytest.mark.integration
class TestGitColdStart:
    async def test_index_commits_cold_start(self, cold_start_qdrant, tmp_git_repo):
        """Indexing commits should auto-create collection."""
        analyzer = GitAnalyzer(client=cold_start_qdrant)
        result = await analyzer.index_commits()
        assert result.success

    async def test_search_empty_repo_cold_start(self, cold_start_qdrant):
        """Search on empty collection returns empty, not error."""
        analyzer = GitAnalyzer(client=cold_start_qdrant)
        results = await analyzer.search_commits("anything")
        assert results == []
```

**Testing Requirements**:
- Use `tmp_git_repo` fixture (existing) for git operations
- Verify collection creation happens automatically
- Verify no 404 errors

---

### R9-D: Add Cold-Start Tests for Values/GHAP Operations

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R9-A

**Problem Statement**:
BUG-043 showed `values` collection was never created. BUG-016 showed GHAP collections had the same issue (now fixed, but need regression tests).

**Acceptance Criteria**:
- [ ] Test `store_value()` succeeds on cold start
- [ ] Test `list_values()` returns empty on cold start (not error)
- [ ] Test `start_ghap()` succeeds on cold start
- [ ] Test `list_ghap_entries()` returns empty on cold start (not error)
- [ ] Test clustering operations handle empty data gracefully

**Implementation Notes**:
Add to `tests/integration/test_values_cold_start.py`:
```python
@pytest.mark.integration
class TestValuesColdStart:
    async def test_store_value_cold_start(self, cold_start_qdrant):
        """First value storage should auto-create collection."""
        store = ValueStore(client=cold_start_qdrant)
        result = await store.store(text="test value", cluster_id="full_0", axis="full")
        assert result.success

    async def test_clustering_empty_cold_start(self, cold_start_qdrant):
        """Clustering with no data should return empty, not error."""
        store = ValueStore(client=cold_start_qdrant)
        clusters = await store.get_clusters(axis="full")
        assert clusters == []
```

**Testing Requirements**:
- Verify all value-related operations work from cold start
- Verify GHAP regression test prevents BUG-016 from recurring

---

### R9-E: Create Cold-Start CI Job

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R9-A, R9-B, R9-C, R9-D

**Problem Statement**:
Cold-start tests need to run in CI to ensure they don't regress. A dedicated CI job ensures fresh environments.

**Acceptance Criteria**:
- [ ] Add `cold-start` marker to pytest
- [ ] Create GitHub Actions job that runs cold-start tests
- [ ] Job uses fresh Qdrant container (no persistent data)
- [ ] Job runs on every PR

**Implementation Notes**:
Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "cold_start: tests that verify behavior with no pre-existing data",
]
```

Add to `.github/workflows/ci.yml`:
```yaml
  cold-start-tests:
    runs-on: ubuntu-latest
    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333
    steps:
      - uses: actions/checkout@v4
      - name: Run cold-start tests
        run: pytest -m cold_start --tb=short
```

**Testing Requirements**:
- Verify CI job passes on main
- Verify job catches intentional cold-start failures

---

## R10: Cross-Component Integration Tests

**Addresses Themes**: T1 (Schema/Type Inconsistency), T7 (Test-Production Divergence)
**Overall Benefit**: High
**Overall Complexity**: Medium
**Confidence**: High

**Problem Summary**: Components are tested in isolation with mocks that don't match production interfaces. Data flows across module boundaries without validation. BUG-040 (duplicate result types), BUG-041 (abstract/concrete Searcher conflict), and BUG-027 (datetime round-trip) demonstrate these issues.

---

### R10-A: Add Round-Trip Serialization Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-027 showed datetime stored as ISO string but read expecting numeric timestamp. No tests verified data survives storage and retrieval intact.

**Acceptance Criteria**:
- [ ] Test GHAP entries survive round-trip (store then retrieve)
- [ ] Test memories survive round-trip
- [ ] Test values survive round-trip
- [ ] Test datetime fields specifically preserved across round-trip
- [ ] Test numeric fields (especially floats) preserved

**Implementation Notes**:
Add to `tests/integration/test_round_trip.py`:
```python
import pytest
from datetime import datetime

class TestRoundTrip:
    async def test_ghap_round_trip(self, qdrant_client):
        """Verify GHAP can be stored and retrieved with identical data."""
        original_created = datetime.now()
        original = {
            "domain": "debugging",
            "strategy": "root-cause-analysis",
            "goal": "Fix the bug",
            "hypothesis": "The cache is stale",
            "action": "Clear cache",
            "prediction": "Bug will resolve",
            "created_at": original_created,
        }

        stored_id = await start_ghap(**original)
        retrieved = await get_active_ghap()

        assert retrieved.domain == original["domain"]
        assert retrieved.created_at == original_created  # Datetime survives
        assert isinstance(retrieved.created_at, datetime)  # Type preserved

    async def test_memory_round_trip(self, qdrant_client):
        """Verify memory survives storage and retrieval."""
        original = {
            "content": "Test memory content",
            "category": "fact",
            "importance": 0.75,
            "tags": ["test", "round-trip"],
        }

        result = await store_memory(**original)
        retrieved = await retrieve_memories(original["content"], limit=1)

        assert len(retrieved) == 1
        assert retrieved[0].content == original["content"]
        assert retrieved[0].importance == original["importance"]  # Float preserved
```

**Testing Requirements**:
- Run against real Qdrant (not mock)
- Verify datetime types, not just values
- Verify floats don't lose precision

---

### R10-B: Add Mock-to-Production Interface Verification

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: none

**Problem Statement**:
BUG-040 showed `MockSearcher` doesn't match production `Searcher` interface. Tests pass with mock but code fails with real implementation.

**Acceptance Criteria**:
- [ ] Test that verifies `MockSearcher` has all methods of `Searcher`
- [ ] Test that verifies method signatures match (parameter names, types)
- [ ] Test that verifies return types match
- [ ] Generalize pattern for all mock classes

**Implementation Notes**:
Add to `tests/unit/test_mock_parity.py`:
```python
import inspect
from clams.search.searcher import Searcher
from tests.mocks.search import MockSearcher

def test_mock_searcher_matches_production():
    """Verify MockSearcher implements same interface as Searcher."""
    prod_methods = {
        name for name, method in inspect.getmembers(Searcher, predicate=inspect.isfunction)
        if not name.startswith('_')
    }
    mock_methods = {
        name for name, method in inspect.getmembers(MockSearcher, predicate=inspect.isfunction)
        if not name.startswith('_')
    }

    missing = prod_methods - mock_methods
    assert not missing, f"MockSearcher missing methods: {missing}"

    # Verify signatures match
    for method_name in prod_methods:
        prod_sig = inspect.signature(getattr(Searcher, method_name))
        mock_sig = inspect.signature(getattr(MockSearcher, method_name))
        assert prod_sig == mock_sig, f"{method_name} signature mismatch: {prod_sig} vs {mock_sig}"

def get_all_mock_production_pairs():
    """Return all mock/production class pairs for verification."""
    return [
        (MockSearcher, Searcher),
        # Add other mock/production pairs as they're identified
    ]

@pytest.mark.parametrize("mock_cls,prod_cls", get_all_mock_production_pairs())
def test_mock_matches_production(mock_cls, prod_cls):
    """Parameterized test for all mock/production pairs."""
    # Same logic as above, generalized
```

**Testing Requirements**:
- Verify test fails when mock is missing a method
- Verify test fails when signature differs
- Add new mock/production pairs as code is reviewed

---

### R10-C: Add Schema Enum Consistency Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-026 showed JSON schema enum values differ from validation enum values. Tests need to verify advertised values match accepted values.

**Acceptance Criteria**:
- [ ] Test that JSON schema enum values match Python enum values
- [ ] Test covers all enums: domain, strategy, category, outcome
- [ ] Test fails if schema advertises values that validation rejects

**Implementation Notes**:
Add to `tests/unit/test_schema_consistency.py`:
```python
from clams.server.tools import get_tool_definitions
from clams.server.tools.enums import GHAPDomain, GHAPStrategy, MemoryCategory

def test_domain_enum_consistency():
    """JSON schema domain values must match validation enum."""
    tools = get_tool_definitions()
    start_ghap_tool = next(t for t in tools if t["name"] == "start_ghap")
    schema_values = set(start_ghap_tool["inputSchema"]["properties"]["domain"]["enum"])
    enum_values = {e.value for e in GHAPDomain}

    assert schema_values == enum_values, (
        f"Schema/enum mismatch. Schema: {schema_values}, Enum: {enum_values}"
    )

def test_strategy_enum_consistency():
    """JSON schema strategy values must match validation enum."""
    tools = get_tool_definitions()
    start_ghap_tool = next(t for t in tools if t["name"] == "start_ghap")
    schema_values = set(start_ghap_tool["inputSchema"]["properties"]["strategy"]["enum"])
    enum_values = {e.value for e in GHAPStrategy}

    assert schema_values == enum_values

# Add similar tests for MemoryCategory, outcome status, etc.
```

**Testing Requirements**:
- Verify test catches intentional mismatches
- Run as part of regular test suite (not just CI)
- Cover all tools that use enums

---

### R10-D: Add Data Flow Integration Tests

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: R10-A

**Problem Statement**:
Data flows between modules (e.g., GHAP stored in one module, retrieved in another for clustering) without tests verifying the contracts are maintained.

**Acceptance Criteria**:
- [ ] Test GHAP flow: start_ghap -> update_ghap -> resolve_ghap -> search_experiences
- [ ] Test memory flow: store_memory -> retrieve_memories -> delete_memory
- [ ] Test code indexing flow: index_codebase -> search_code -> find_similar_code
- [ ] Test git flow: index_commits -> search_commits -> get_file_history
- [ ] All tests use real components (no mocks)

**Implementation Notes**:
Add to `tests/integration/test_data_flows.py`:
```python
class TestGHAPDataFlow:
    """Test complete GHAP lifecycle across components."""

    async def test_ghap_complete_lifecycle(self, qdrant_client):
        """Verify GHAP data flows correctly through entire lifecycle."""
        # 1. Start
        ghap_id = await start_ghap(
            domain="debugging",
            strategy="root-cause-analysis",
            goal="Test data flow",
            hypothesis="Data flows correctly",
            action="Run lifecycle test",
            prediction="All assertions pass",
        )

        # 2. Verify active
        active = await get_active_ghap()
        assert active.id == ghap_id

        # 3. Update
        await update_ghap(hypothesis="Updated hypothesis")
        updated = await get_active_ghap()
        assert updated.hypothesis == "Updated hypothesis"

        # 4. Resolve
        await resolve_ghap(status="confirmed", result="All passed")

        # 5. Search experiences (different module)
        experiences = await search_experiences("data flow")
        assert any(e.id == ghap_id for e in experiences)

        # 6. Get from cluster view (yet another module)
        clusters = await get_clusters(axis="full")
        # Should find in some cluster
```

**Testing Requirements**:
- Run against real Qdrant and SQLite
- Verify data integrity at each step
- Cover all major data flows in the system

---

### R10-E: Add Type Boundary Verification Tests

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: none

**Problem Statement**:
BUG-040 and BUG-041 showed type definitions duplicated between modules with different field names. Need tests that verify types match at module boundaries.

**Acceptance Criteria**:
- [ ] Test that `search/results.py` types match usage in `context/`
- [ ] Test that `Searcher` ABC methods match concrete implementation
- [ ] Test that all dataclass field names are consistent across modules
- [ ] Identify and test all module boundary type contracts

**Implementation Notes**:
Add to `tests/unit/test_type_boundaries.py`:
```python
from dataclasses import fields
from clams.search.results import CodeResult as SearchCodeResult
from clams.context.searcher_types import CodeResult as ContextCodeResult

def test_code_result_field_consistency():
    """Verify CodeResult has consistent fields across modules."""
    search_fields = {f.name: f.type for f in fields(SearchCodeResult)}
    context_fields = {f.name: f.type for f in fields(ContextCodeResult)}

    # After R1 implementation, these should be the same class
    # For now, verify fields match
    assert search_fields.keys() == context_fields.keys(), (
        f"Field name mismatch: search={search_fields.keys()}, context={context_fields.keys()}"
    )

def test_searcher_abc_implementation():
    """Verify concrete Searcher implements all ABC methods."""
    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.search.searcher import Searcher

    abc_methods = {
        name for name, method in inspect.getmembers(SearcherABC, predicate=inspect.isfunction)
        if getattr(method, '__isabstractmethod__', False)
    }

    concrete_methods = set(dir(Searcher))

    missing = abc_methods - concrete_methods
    assert not missing, f"Concrete Searcher missing ABC methods: {missing}"
```

**Testing Requirements**:
- Test should fail if types drift apart
- Run as part of regular test suite
- Update as type consolidation (R1) progresses

---

## R11: Type-Safe Datetime/Numeric Handling

**Addresses Themes**: T4 (Data Format/Parsing Mismatches)
**Overall Benefit**: Medium
**Overall Complexity**: Low
**Confidence**: Very High

**Problem Summary**: Data written in one format but read expecting another. BUG-027 (ISO string vs timestamp), BUG-034 (float truncation via int() cast) demonstrate this pattern.

---

### R11-A: Create Centralized Datetime Utilities

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-027 showed datetime stored as ISO string but read expecting numeric timestamp. No consistent serialization/deserialization pattern exists.

**Acceptance Criteria**:
- [ ] Create `src/clams/utils/datetime.py` with serialize/deserialize functions
- [ ] All datetime serialization uses these utilities
- [ ] All datetime deserialization uses these utilities
- [ ] Functions are type-annotated
- [ ] Include timezone handling (UTC by default)

**Implementation Notes**:
Create `src/clams/utils/datetime.py`:
```python
"""Centralized datetime handling for consistent serialization."""
from datetime import datetime, timezone
from typing import Union

def serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO 8601 string with UTC timezone.

    Args:
        dt: Datetime to serialize. If naive, assumes UTC.

    Returns:
        ISO 8601 formatted string (e.g., "2024-12-14T10:30:00+00:00")
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def deserialize_datetime(value: Union[str, float, int]) -> datetime:
    """Deserialize datetime from various formats.

    Args:
        value: ISO string, Unix timestamp (int/float), or None

    Returns:
        Timezone-aware datetime (UTC)

    Raises:
        ValueError: If value cannot be parsed
    """
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    elif isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    else:
        raise ValueError(f"Cannot deserialize datetime from {type(value)}: {value}")
```

**Testing Requirements**:
- Test round-trip: serialize then deserialize returns equivalent datetime
- Test handles ISO strings
- Test handles Unix timestamps (int and float)
- Test handles timezone-aware and naive datetimes
- Property-based tests with hypothesis

---

### R11-B: Create Safe Numeric Conversion Utilities

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-034 showed `int(0.5)` returns 0, changing timeout from 500ms to infinite. Need safe conversions that preserve semantics.

**Acceptance Criteria**:
- [ ] Create `src/clams/utils/numeric.py` with safe conversion functions
- [ ] `timeout_ms_to_seconds()` that preserves fractional seconds
- [ ] `safe_int()` that warns or errors on lossy conversion
- [ ] All timeout conversions use these utilities

**Implementation Notes**:
Create `src/clams/utils/numeric.py`:
```python
"""Safe numeric conversions to prevent semantic-changing truncation."""
import math
import warnings
from typing import Optional

def timeout_ms_to_seconds(ms: float) -> float:
    """Convert milliseconds to seconds without truncation.

    Args:
        ms: Timeout in milliseconds

    Returns:
        Timeout in seconds as float (not int)

    Example:
        >>> timeout_ms_to_seconds(500)
        0.5
        >>> timeout_ms_to_seconds(1500)
        1.5
    """
    return ms / 1000.0

def timeout_seconds_to_int(seconds: float, *, round_up: bool = True) -> int:
    """Convert seconds to integer, optionally rounding up.

    Args:
        seconds: Timeout in seconds
        round_up: If True, use ceil. If False, use floor.

    Returns:
        Integer seconds

    Note:
        Use round_up=True for timeouts to avoid premature expiry.
    """
    if round_up:
        return math.ceil(seconds)
    return math.floor(seconds)

def safe_int(value: float, *, name: str = "value") -> int:
    """Convert float to int with warning if lossy.

    Args:
        value: Float to convert
        name: Name for warning message

    Returns:
        Integer value

    Warns:
        If conversion loses precision (fractional part > 0.001)
    """
    if abs(value - round(value)) > 0.001:
        warnings.warn(
            f"Lossy conversion of {name}: {value} -> {int(value)}. "
            f"Consider using float or math.ceil().",
            UserWarning
        )
    return int(value)
```

**Testing Requirements**:
- Test timeout_ms_to_seconds(500) == 0.5
- Test timeout_seconds_to_int(0.5, round_up=True) == 1
- Test safe_int(0.5) warns and returns 0
- Test safe_int(5.0) does not warn

---

### R11-C: Migrate Existing Datetime Handling

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R11-A

**Problem Statement**:
Existing code uses ad-hoc datetime serialization. Need to migrate to centralized utilities.

**Acceptance Criteria**:
- [ ] Find all `datetime.isoformat()` calls and replace with `serialize_datetime()`
- [ ] Find all `datetime.fromisoformat()` calls and replace with `deserialize_datetime()`
- [ ] Find all `datetime.fromtimestamp()` calls and replace with `deserialize_datetime()`
- [ ] Verify no raw datetime serialization remains

**Implementation Notes**:
Use grep to find all occurrences:
```bash
# Find all datetime serialization patterns
grep -rn "\.isoformat()" src/clams/
grep -rn "fromisoformat" src/clams/
grep -rn "fromtimestamp" src/clams/
```

Replace patterns:
```python
# Before
entry.created_at.isoformat()

# After
from clams.utils.datetime import serialize_datetime
serialize_datetime(entry.created_at)

# Before
datetime.fromisoformat(data["created_at"])

# After
from clams.utils.datetime import deserialize_datetime
deserialize_datetime(data["created_at"])
```

**Testing Requirements**:
- Run full test suite after migration
- Verify round-trip tests pass
- No regressions in date handling

---

### R11-D: Migrate Existing Timeout Handling

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R11-B

**Problem Statement**:
BUG-034 showed int() cast on timeout values. Need to find and fix all such cases.

**Acceptance Criteria**:
- [ ] Find all `int(timeout)` or `int(seconds)` patterns
- [ ] Replace with appropriate safe conversion
- [ ] Verify timeout semantics preserved (0.5s stays 0.5s or rounds up)

**Implementation Notes**:
Search for patterns:
```bash
grep -rn "int(.*timeout" src/clams/
grep -rn "int(.*seconds" src/clams/
```

Known location from BUG-034: timeout conversion in MCP client.

**Testing Requirements**:
- Test that 500ms timeout actually waits ~500ms (not 0)
- Test that 1500ms timeout waits ~1500ms
- Verify no timeouts become 0 or infinite

---

### R11-E: Add Round-Trip Property Tests

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R11-A, R11-B

**Problem Statement**:
Need property-based tests to verify serialization/deserialization is consistent across all valid inputs.

**Acceptance Criteria**:
- [ ] Install hypothesis for property-based testing
- [ ] Add property test for datetime round-trip
- [ ] Add property test for numeric conversions
- [ ] Tests cover edge cases (timezones, negative numbers, extremes)

**Implementation Notes**:
Add to `tests/unit/test_utils_property.py`:
```python
from hypothesis import given, strategies as st
from datetime import datetime, timezone
from clams.utils.datetime import serialize_datetime, deserialize_datetime

@given(st.datetimes(timezones=st.just(timezone.utc) | st.none()))
def test_datetime_round_trip(dt):
    """Any datetime should survive round-trip serialization."""
    serialized = serialize_datetime(dt)
    deserialized = deserialize_datetime(serialized)

    # Compare with timezone normalization
    original = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    assert deserialized == original

@given(st.floats(min_value=0, max_value=3600, allow_nan=False))
def test_timeout_conversion_round_trip(seconds):
    """Timeout conversion should preserve value."""
    from clams.utils.numeric import timeout_ms_to_seconds

    ms = seconds * 1000
    back_to_seconds = timeout_ms_to_seconds(ms)
    assert abs(back_to_seconds - seconds) < 0.0001
```

**Testing Requirements**:
- Tests find edge cases automatically
- Run with `pytest --hypothesis-show-statistics`
- Cover all numeric conversion functions

---

## R12: Platform-Specific Pre-Checks

**Addresses Themes**: T6 (Configuration/Path Issues), T8 (Import Order/Heavy Dependencies)
**Overall Benefit**: Medium
**Overall Complexity**: Low
**Confidence**: High

**Problem Summary**: Platform-specific issues (macOS MPS, fork() incompatibility) cause crashes at runtime. BUG-042 (MPS fork crash) and BUG-037 (import timeout) demonstrate these issues.

---

### R12-A: Create Platform Compatibility Check Module

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-042 showed MPS doesn't support fork() after initialization, but code attempted to daemonize after importing PyTorch. No startup check warned about this incompatibility.

**Acceptance Criteria**:
- [ ] Create `src/clams/utils/platform.py` with compatibility checks
- [ ] Check for macOS + MPS + daemon mode conflict
- [ ] Check for heavy import + short timeout conflict
- [ ] Provide clear error messages with workarounds
- [ ] Checks can be called at startup

**Implementation Notes**:
Create `src/clams/utils/platform.py`:
```python
"""Platform compatibility checks for known issues."""
import sys
import warnings
from typing import List, Tuple

class PlatformIssue:
    """Represents a detected platform compatibility issue."""
    def __init__(self, code: str, message: str, severity: str, workaround: str):
        self.code = code
        self.message = message
        self.severity = severity  # "error", "warning", "info"
        self.workaround = workaround

def check_mps_fork_compatibility(daemon_mode: bool = False) -> List[PlatformIssue]:
    """Check for macOS MPS + fork() incompatibility.

    Issue: PyTorch MPS backend initializes on import and doesn't support fork().
    Reference: BUG-042
    """
    issues = []

    if sys.platform != "darwin":
        return issues

    if not daemon_mode:
        return issues

    # Check if MPS is available (implies PyTorch with MPS)
    try:
        import torch
        if torch.backends.mps.is_available():
            issues.append(PlatformIssue(
                code="MPS_FORK",
                message="MPS backend detected in daemon mode. fork() will crash.",
                severity="error",
                workaround=(
                    "Either disable daemon mode (--no-daemon) or set "
                    "PYTORCH_ENABLE_MPS_FALLBACK=1 before import."
                )
            ))
    except ImportError:
        pass

    return issues

def check_import_timeout_compatibility(timeout_seconds: float) -> List[PlatformIssue]:
    """Check if timeout is sufficient for heavy imports.

    Issue: PyTorch/sentence-transformers take 3-6 seconds to import.
    Reference: BUG-037
    """
    issues = []

    # Typical import times observed
    MIN_SAFE_TIMEOUT = 15.0

    if timeout_seconds < MIN_SAFE_TIMEOUT:
        issues.append(PlatformIssue(
            code="IMPORT_TIMEOUT",
            message=f"Timeout {timeout_seconds}s may be insufficient for heavy imports (need ~{MIN_SAFE_TIMEOUT}s).",
            severity="warning",
            workaround=f"Increase timeout to at least {MIN_SAFE_TIMEOUT} seconds."
        ))

    return issues

def run_all_checks(*, daemon_mode: bool = False, timeout_seconds: float = 30.0) -> List[PlatformIssue]:
    """Run all platform compatibility checks.

    Call this at startup to detect issues early.
    """
    issues = []
    issues.extend(check_mps_fork_compatibility(daemon_mode))
    issues.extend(check_import_timeout_compatibility(timeout_seconds))
    return issues

def report_issues(issues: List[PlatformIssue], *, fail_on_error: bool = True) -> None:
    """Report platform issues with appropriate logging.

    Args:
        issues: List of detected issues
        fail_on_error: If True, raise exception for error-severity issues
    """
    for issue in issues:
        msg = f"[{issue.code}] {issue.message}\nWorkaround: {issue.workaround}"

        if issue.severity == "error":
            if fail_on_error:
                raise RuntimeError(msg)
            else:
                warnings.warn(msg, RuntimeWarning)
        elif issue.severity == "warning":
            warnings.warn(msg, UserWarning)
        else:
            print(f"INFO: {msg}")
```

**Testing Requirements**:
- Test MPS check returns issue on macOS with MPS available + daemon mode
- Test MPS check returns empty on Linux
- Test timeout check returns issue for < 15s timeout
- Test report_issues raises on error severity

---

### R12-B: Integrate Platform Checks into Server Startup

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R12-A

**Problem Statement**:
Platform checks exist but aren't called at startup. Need to integrate into main entry points.

**Acceptance Criteria**:
- [ ] Call `run_all_checks()` in server main()
- [ ] Call `run_all_checks()` in CLI entry point
- [ ] Pass daemon_mode and timeout from actual configuration
- [ ] Report issues before starting server

**Implementation Notes**:
Add to `src/clams/server/main.py`:
```python
from clams.utils.platform import run_all_checks, report_issues

def main():
    args = parse_args()

    # Check platform compatibility before doing anything else
    issues = run_all_checks(
        daemon_mode=args.daemon,
        timeout_seconds=args.timeout
    )
    report_issues(issues, fail_on_error=True)

    # Continue with normal startup...
```

**Testing Requirements**:
- Test server fails to start with MPS + daemon on macOS (if applicable)
- Test server warns about short timeout
- Test checks don't block normal startup

---

### R12-C: Add Platform-Specific CI Matrix

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: none

**Problem Statement**:
CI only runs on one platform (likely Linux). Platform-specific bugs (BUG-042) only found in production on macOS.

**Acceptance Criteria**:
- [ ] Add macOS runner to GitHub Actions matrix
- [ ] Run full test suite on both Linux and macOS
- [ ] Consider adding Windows if applicable
- [ ] Platform-specific tests can be skipped with markers

**Implementation Notes**:
Update `.github/workflows/ci.yml`:
```yaml
jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        python-version: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest -v --tb=short
```

Add pytest markers for platform-specific tests:
```python
import pytest
import sys

macos_only = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="macOS-specific test"
)

@macos_only
def test_mps_detection():
    """Test MPS availability detection on macOS."""
    ...
```

**Testing Requirements**:
- Verify CI runs on both platforms
- Verify platform-specific tests skip appropriately
- Monitor for platform-specific failures

---

### R12-D: Document Known Platform Issues

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R12-A

**Problem Statement**:
Platform issues discovered in bugs need to be documented so developers are aware.

**Acceptance Criteria**:
- [ ] Add "Platform Compatibility" section to CLAUDE.md
- [ ] Document MPS + fork() incompatibility (BUG-042)
- [ ] Document import timeout requirements (BUG-037)
- [ ] Include workarounds for each issue

**Implementation Notes**:
Add to `CLAUDE.md`:
```markdown
## Platform Compatibility

### macOS with Apple Silicon (MPS)

**Issue**: PyTorch MPS backend doesn't support `fork()` after initialization.
**Impact**: Daemon mode crashes with "cannot fork() after MPS initialization".
**Reference**: BUG-042

**Workaround**:
1. Use `--no-daemon` mode, OR
2. Set `PYTORCH_ENABLE_MPS_FALLBACK=1` before starting, OR
3. Use CPU-only mode with `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0`

### Import Timeouts

**Issue**: Heavy dependencies (PyTorch, sentence-transformers) take 3-6 seconds to import.
**Impact**: Short verification timeouts cause false failures.
**Reference**: BUG-037

**Workaround**:
- Set verification timeout to at least 15 seconds
- Consider lazy imports for heavy dependencies (see R7)
```

**Testing Requirements**:
- Review documentation for accuracy
- Verify workarounds actually work

---

## R13: Parameter Validation with Production Data

**Addresses Themes**: T9 (Algorithm Parameter Tuning)
**Overall Benefit**: Medium
**Overall Complexity**: Medium
**Confidence**: Medium

**Problem Summary**: Algorithm parameters tuned for test data fail with production data distributions. BUG-031 showed HDBSCAN parameters too conservative for real data (all points classified as noise).

---

### R13-A: Create Production Data Profiles

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-031 showed HDBSCAN `min_cluster_size=5` too conservative for 63 entries. No documented expectations for production data characteristics.

**Acceptance Criteria**:
- [ ] Create `tests/data/production_profiles.py` with data characteristic definitions
- [ ] Document expected GHAP entry counts (20-200)
- [ ] Document expected theme distribution (3-10 themes)
- [ ] Document expected noise ratio (<30%)
- [ ] Document memory entry counts
- [ ] Document commit index sizes

**Implementation Notes**:
Create `tests/data/production_profiles.py`:
```python
"""Production data profiles for realistic testing.

These profiles document expected data characteristics based on actual usage.
Use these to generate synthetic test data that matches production.

Reference: BUG-031 - clustering failed because test data didn't match production.
"""
from dataclasses import dataclass
from typing import Tuple

@dataclass
class GHAPProfile:
    """Expected characteristics of GHAP entries in production."""
    # Entry counts
    entry_count_range: Tuple[int, int] = (20, 200)
    typical_entry_count: int = 63  # Based on BUG-031 evidence

    # Theme distribution
    theme_count_range: Tuple[int, int] = (3, 10)
    typical_theme_count: int = 5

    # Noise expectations
    max_acceptable_noise_ratio: float = 0.30  # 30% max noise
    typical_noise_ratio: float = 0.15

    # Domain distribution
    common_domains: list = None

    def __post_init__(self):
        if self.common_domains is None:
            self.common_domains = [
                "debugging",  # ~40%
                "feature",    # ~25%
                "refactoring",# ~15%
                "testing",    # ~10%
                "other",      # ~10%
            ]

@dataclass
class MemoryProfile:
    """Expected characteristics of memories in production."""
    entry_count_range: Tuple[int, int] = (50, 500)
    typical_entry_count: int = 150

    # Category distribution
    category_distribution: dict = None

    def __post_init__(self):
        if self.category_distribution is None:
            self.category_distribution = {
                "fact": 0.30,
                "preference": 0.25,
                "workflow": 0.20,
                "decision": 0.15,
                "context": 0.10,
            }

@dataclass
class CodeIndexProfile:
    """Expected characteristics of code indexes in production."""
    file_count_range: Tuple[int, int] = (50, 500)
    typical_file_count: int = 200

    # Language distribution (typical Python project)
    language_distribution: dict = None

    def __post_init__(self):
        if self.language_distribution is None:
            self.language_distribution = {
                "python": 0.70,
                "markdown": 0.15,
                "yaml": 0.10,
                "other": 0.05,
            }

# Default profiles
GHAP_PROFILE = GHAPProfile()
MEMORY_PROFILE = MemoryProfile()
CODE_INDEX_PROFILE = CodeIndexProfile()
```

**Testing Requirements**:
- Profiles are importable and have reasonable defaults
- Profiles match observed production data
- Update profiles as production usage evolves

---

### R13-B: Create Profile-Based Data Generators

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: R13-A

**Problem Statement**:
Need to generate synthetic test data that matches production profiles for realistic testing.

**Acceptance Criteria**:
- [ ] Create `tests/generators/ghap.py` with GHAP entry generators
- [ ] Generators use profiles from R13-A
- [ ] Support for controlling theme count, noise ratio
- [ ] Generate realistic embeddings (not random)
- [ ] Create similar generators for memories and code entries

**Implementation Notes**:
Create `tests/generators/ghap.py`:
```python
"""Generate synthetic GHAP entries matching production profiles."""
import random
from typing import List, Optional
from datetime import datetime, timedelta
import numpy as np

from tests.data.production_profiles import GHAPProfile, GHAP_PROFILE

def generate_ghap_entries(
    count: Optional[int] = None,
    theme_count: Optional[int] = None,
    noise_ratio: Optional[float] = None,
    profile: GHAPProfile = GHAP_PROFILE,
) -> List[dict]:
    """Generate GHAP entries matching production profile.

    Args:
        count: Number of entries. Defaults to typical from profile.
        theme_count: Number of distinct themes. Defaults to profile.
        noise_ratio: Fraction of entries that are noise. Defaults to profile.
        profile: Production profile to use.

    Returns:
        List of GHAP entry dicts ready for insertion.
    """
    count = count or profile.typical_entry_count
    theme_count = theme_count or profile.typical_theme_count
    noise_ratio = noise_ratio or profile.typical_noise_ratio

    entries = []
    themes = _generate_themes(theme_count)

    for i in range(count):
        is_noise = random.random() < noise_ratio

        if is_noise:
            # Noise entries have unique, random content
            entry = _generate_noise_entry(i)
        else:
            # Themed entries cluster around theme centroids
            theme = random.choice(themes)
            entry = _generate_themed_entry(i, theme)

        entries.append(entry)

    return entries

def _generate_themes(count: int) -> List[dict]:
    """Generate distinct themes for clustering."""
    theme_templates = [
        {"domain": "debugging", "keywords": ["bug", "fix", "error", "crash"]},
        {"domain": "feature", "keywords": ["add", "implement", "create", "new"]},
        {"domain": "refactoring", "keywords": ["clean", "refactor", "improve", "simplify"]},
        {"domain": "testing", "keywords": ["test", "verify", "assert", "coverage"]},
        {"domain": "performance", "keywords": ["optimize", "speed", "cache", "efficient"]},
    ]
    return random.sample(theme_templates, min(count, len(theme_templates)))

def _generate_themed_entry(index: int, theme: dict) -> dict:
    """Generate entry that clusters with theme."""
    keyword = random.choice(theme["keywords"])
    return {
        "id": f"ghap-{index}",
        "domain": theme["domain"],
        "strategy": random.choice(["root-cause-analysis", "systematic-elimination", "divide-and-conquer"]),
        "goal": f"{keyword.title()} the {random.choice(['module', 'component', 'system'])}",
        "hypothesis": f"The issue is related to {keyword}",
        "action": f"Investigate {keyword} patterns",
        "prediction": f"{keyword.title()} analysis will reveal cause",
        "created_at": datetime.now() - timedelta(days=random.randint(0, 30)),
    }

def _generate_noise_entry(index: int) -> dict:
    """Generate noise entry (doesn't cluster)."""
    return {
        "id": f"ghap-noise-{index}",
        "domain": random.choice(GHAP_PROFILE.common_domains),
        "strategy": "trial-and-error",
        "goal": f"Random goal {random.randint(1000, 9999)}",
        "hypothesis": f"Unique hypothesis {random.randint(1000, 9999)}",
        "action": f"Action {random.randint(1000, 9999)}",
        "prediction": f"Prediction {random.randint(1000, 9999)}",
        "created_at": datetime.now() - timedelta(days=random.randint(0, 30)),
    }
```

**Testing Requirements**:
- Verify generated data matches profile characteristics
- Verify theme clustering produces expected clusters
- Verify noise ratio is approximately correct

---

### R13-C: Add Clustering Benchmark Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: R13-A, R13-B

**Problem Statement**:
BUG-031 showed clustering classified all points as noise with production data. Need benchmark tests that verify clustering produces reasonable results.

**Acceptance Criteria**:
- [ ] Test clustering with production-profile data
- [ ] Verify at least 1 cluster is produced (not all noise)
- [ ] Verify noise ratio is below acceptable threshold
- [ ] Test across range of data sizes (20, 50, 100, 200 entries)
- [ ] Test parameter variations

**Implementation Notes**:
Add to `tests/benchmark/test_clustering.py`:
```python
import pytest
from tests.generators.ghap import generate_ghap_entries
from tests.data.production_profiles import GHAP_PROFILE
from clams.clustering.hdbscan_clusterer import cluster_ghap_entries

class TestClusteringWithProductionData:
    """Verify clustering works with production-like data distributions."""

    @pytest.mark.parametrize("count", [20, 50, 100, 200])
    def test_clustering_produces_clusters(self, count):
        """Verify clustering produces at least some clusters."""
        entries = generate_ghap_entries(
            count=count,
            theme_count=5,
            noise_ratio=0.15,
        )

        clusters = cluster_ghap_entries(entries)

        # Should produce at least 1 cluster
        cluster_ids = {e.cluster_id for e in clusters}
        non_noise_clusters = cluster_ids - {-1}
        assert len(non_noise_clusters) >= 1, (
            f"No clusters produced for {count} entries. "
            f"All {len(entries)} entries classified as noise."
        )

    def test_noise_ratio_acceptable(self):
        """Verify noise ratio doesn't exceed acceptable threshold."""
        entries = generate_ghap_entries(
            count=GHAP_PROFILE.typical_entry_count,
            noise_ratio=GHAP_PROFILE.typical_noise_ratio,
        )

        clusters = cluster_ghap_entries(entries)

        noise_count = sum(1 for e in clusters if e.cluster_id == -1)
        noise_ratio = noise_count / len(entries)

        assert noise_ratio < GHAP_PROFILE.max_acceptable_noise_ratio, (
            f"Noise ratio {noise_ratio:.2%} exceeds max acceptable "
            f"{GHAP_PROFILE.max_acceptable_noise_ratio:.2%}. "
            f"Clustering parameters may need tuning."
        )

    @pytest.mark.parametrize("min_cluster_size", [3, 5, 7])
    def test_parameter_sensitivity(self, min_cluster_size):
        """Test clustering behavior across parameter variations."""
        entries = generate_ghap_entries(count=63)  # BUG-031 exact count

        clusters = cluster_ghap_entries(
            entries,
            min_cluster_size=min_cluster_size,
        )

        noise_count = sum(1 for e in clusters if e.cluster_id == -1)
        noise_ratio = noise_count / len(entries)

        # Log for analysis
        print(f"min_cluster_size={min_cluster_size}: noise_ratio={noise_ratio:.2%}")

        # With proper parameters, should not be 100% noise
        assert noise_ratio < 0.9, f"90%+ noise with min_cluster_size={min_cluster_size}"
```

**Testing Requirements**:
- Run as part of benchmark suite (may be slower)
- Verify tests fail if all points become noise
- Use output for parameter tuning

---

### R13-D: Add Parameter Recommendation Logic

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: R13-A, R13-C

**Problem Statement**:
BUG-031 used hardcoded `min_cluster_size=5` which was too conservative. Parameters should adapt to data size.

**Acceptance Criteria**:
- [ ] Create function to recommend clustering parameters based on data size
- [ ] Recommendations based on production profile analysis
- [ ] Parameters validated against benchmark tests
- [ ] Document parameter selection rationale

**Implementation Notes**:
Add to `src/clams/clustering/parameters.py`:
```python
"""Adaptive parameter selection for clustering algorithms.

Reference: BUG-031 - hardcoded min_cluster_size=5 classified all 63 entries as noise.
"""
import math
from dataclasses import dataclass
from typing import Optional

@dataclass
class HDBSCANParams:
    """Recommended HDBSCAN parameters for a dataset."""
    min_cluster_size: int
    min_samples: int
    rationale: str

def recommend_hdbscan_params(
    entry_count: int,
    expected_clusters: Optional[int] = None,
) -> HDBSCANParams:
    """Recommend HDBSCAN parameters based on data characteristics.

    Args:
        entry_count: Number of entries to cluster
        expected_clusters: Expected number of clusters (if known)

    Returns:
        HDBSCANParams with recommended values and rationale.

    Notes:
        - min_cluster_size should be small enough to form clusters but large
          enough to be meaningful. Rule of thumb: 2-5% of data size, min 3.
        - min_samples controls noise sensitivity. Lower = more points assigned
          to clusters, higher = stricter clustering.
    """
    # Rule of thumb: min_cluster_size ~ sqrt(n) or 3% of n, whichever is smaller
    # But never less than 3 (need at least 3 points to form cluster)
    size_by_sqrt = int(math.sqrt(entry_count))
    size_by_pct = max(3, int(entry_count * 0.03))
    min_cluster_size = max(3, min(size_by_sqrt, size_by_pct))

    # min_samples: typically 1-3 for small datasets, can be higher for large
    # Lower values = more clusters, higher = more points as noise
    if entry_count < 50:
        min_samples = 1
    elif entry_count < 200:
        min_samples = 2
    else:
        min_samples = 3

    rationale = (
        f"For {entry_count} entries: min_cluster_size={min_cluster_size} "
        f"(sqrt={size_by_sqrt}, 3%={size_by_pct}), min_samples={min_samples}"
    )

    return HDBSCANParams(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        rationale=rationale,
    )
```

**Testing Requirements**:
- Test recommendations for various data sizes
- Verify recommended params don't produce all-noise on benchmark data
- Document parameter selection in code comments

---

### R13-E: Integrate Adaptive Parameters into Clustering

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R13-D

**Problem Statement**:
Clustering currently uses hardcoded parameters. Need to use adaptive recommendations.

**Acceptance Criteria**:
- [ ] Clustering functions use `recommend_hdbscan_params()` by default
- [ ] Parameters can still be overridden explicitly
- [ ] Rationale logged for debugging
- [ ] Tests verify adaptive behavior

**Implementation Notes**:
Update `src/clams/clustering/hdbscan_clusterer.py`:
```python
from clams.clustering.parameters import recommend_hdbscan_params

def cluster_ghap_entries(
    entries: List[GHAPEntry],
    min_cluster_size: Optional[int] = None,
    min_samples: Optional[int] = None,
) -> List[ClusteredEntry]:
    """Cluster GHAP entries using HDBSCAN.

    Args:
        entries: Entries to cluster
        min_cluster_size: Override recommended min_cluster_size
        min_samples: Override recommended min_samples

    If parameters not provided, uses adaptive recommendations based on data size.
    """
    if min_cluster_size is None or min_samples is None:
        recommended = recommend_hdbscan_params(len(entries))
        logger.info(f"Using adaptive clustering: {recommended.rationale}")
        min_cluster_size = min_cluster_size or recommended.min_cluster_size
        min_samples = min_samples or recommended.min_samples

    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )
    # ... rest of clustering logic
```

**Testing Requirements**:
- Verify adaptive parameters used when not specified
- Verify explicit parameters override recommendations
- Verify rationale is logged
- Run benchmark tests with adaptive parameters
