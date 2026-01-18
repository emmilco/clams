# SPEC-030: Cold-Start Testing Protocol

## Problem Statement

Tests often run against pre-populated databases or mocked resources, missing bugs that only manifest on first use when collections/resources don't exist yet. BUG-043 showed that `memories`, `commits`, and `values` collections were never created, causing 404 errors on first use. BUG-016 showed GHAP collections had the same issue.

When cold-start scenarios aren't tested:
1. Collection creation bugs are missed
2. First-use errors only appear in production
3. ensure_exists patterns aren't verified

## Proposed Solution

Create a cold-start testing infrastructure with fixtures that simulate completely fresh environments, and add tests that verify all major operations work from a cold start.

## Acceptance Criteria

### Part 1: Fixture Infrastructure
- [ ] Create `tests/fixtures/cold_start.py` with fixtures for empty Qdrant
- [ ] `cold_start_qdrant` pytest fixture provides a clean Qdrant instance with no collections
- [ ] `cold_start_db` fixture provides empty SQLite database
- [ ] Fixtures clean up after themselves
- [ ] Fixtures can be parameterized for both cold-start and populated scenarios

### Part 2: Memory Operations Tests
- [ ] Test `store_memory()` on cold start: returns dict with `memory_id` key, no exception raised, collection exists after call
- [ ] Test `retrieve_memories()` on cold start: returns empty list `[]`, no 404 error, no exception raised
- [ ] Test `list_memories()` on cold start: returns empty list `[]`, no 404 error, no exception raised
- [ ] Test `delete_memory()` with non-existent ID: returns error dict with `error` key (not exception), HTTP 200 or 404 as appropriate

### Part 3: Git/Commit Operations Tests
- [ ] Test `index_commits()` on cold start: returns dict with indexed count (may be 0), no exception raised, collection exists after call
- [ ] Test `search_commits()` on cold start: returns empty list `[]`, no 404 error, no exception raised
- [ ] Test `get_file_history()` on cold start: returns empty list `[]`, no 404 error, no exception raised

### Part 4: Values/GHAP Operations Tests
- [ ] Test `store_value()` on cold start: returns dict with `value_id` key, no exception raised, collection exists after call
- [ ] Test `list_values()` on cold start: returns empty list `[]`, no 404 error, no exception raised
- [ ] Test `start_ghap()` on cold start: returns dict with `ghap_id` key, no exception raised
- [ ] Test `list_ghap_entries()` on cold start: returns empty list `[]` or dict with empty `entries`, no exception raised
- [ ] Test `get_clusters()` on cold start: returns dict with `clusters` key (may be empty list), no exception raised

### Part 5: Test Markers
- [ ] Add `cold_start` pytest marker
- [ ] Cold-start tests are clearly identified and can be run separately

## Implementation Notes

- Qdrant fixture example:
  ```python
  @pytest.fixture
  def cold_start_qdrant():
      """Qdrant instance with no pre-existing collections - simulates first use."""
      client = QdrantClient(":memory:")
      # Do NOT create any collections - that's the point
      yield client
      # Cleanup happens automatically with in-memory instance
  ```
- SQLite fixture example:
  ```python
  @pytest.fixture
  def cold_start_db(tmp_path):
      """Empty SQLite database - simulates first use."""
      db_path = tmp_path / "test_cold_start.db"
      # Create empty database file (no tables)
      conn = sqlite3.connect(db_path)
      conn.close()
      yield db_path
      # tmp_path handles cleanup automatically
  ```
- Test pattern:
  ```python
  @pytest.mark.cold_start
  async def test_store_memory_cold_start(cold_start_qdrant):
      """First memory storage should auto-create collection."""
      store = MemoryStore(client=cold_start_qdrant)
      result = await store.store(content="test", category="fact")
      assert result.success
      # Collection should now exist
      collections = cold_start_qdrant.get_collections()
      assert "memories" in [c.name for c in collections.collections]
  ```
- Add to `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "cold_start: tests that verify behavior with no pre-existing data",
  ]
  ```

## Testing Requirements

- Verify fixtures create truly empty instances (list_collections returns [])
- Verify fixture isolation (tests don't leak state)
- Run tests against real Qdrant (in-memory mode)
- Verify no 404 errors in test output
- Verify `ensure_collection()` patterns work correctly

## Dependencies

- **pytest**: Testing framework
- **qdrant-client**: QdrantClient for vector storage (supports in-memory mode)
- **sqlite3**: Standard library for SQLite database
- **Existing store classes**: MemoryStore, CommitStore, ValueStore, GHAPStore from `clams.server.tools.*`

## Out of Scope

- CI job for cold-start tests (can be added later)
- Cold-start tests for code indexing (complex setup required)
- Performance testing of cold-start scenarios
