# SPEC-044: Architecture Proposal

## Response Size Assertions for GHAP Tests (R15-A)

### Overview

This proposal describes the implementation of response size assertion tests for GHAP tools, building on the fix from BUG-030 to prevent token-wasting verbose responses from regressing.

### Technical Approach

The tests will measure serialized JSON response sizes using `json.dumps()` and assert they stay within specified byte limits. This approach:

1. Uses bytes as a reasonable proxy for tokens (avoids tokenizer dependency)
2. Catches egregious bloat (returning full entries instead of confirmations)
3. Provides clear, actionable error messages
4. Acts as regression tests that block CI/merges

### File Structure

```
tests/
  server/
    test_response_efficiency.py   # New file for response size tests
```

The tests belong in `tests/server/` rather than `tests/server/tools/` because they test a cross-cutting concern (response efficiency) rather than tool-specific functionality. However, following the spec's suggested path (`tests/server/test_response_efficiency.py`) keeps tests discoverable alongside other server-level tests.

### Test Implementation Details

#### Test Class Structure

```python
class TestGHAPResponseEfficiency:
    """Verify GHAP tool responses stay within token-efficient limits.

    Size limits are based on BUG-030 analysis:
    - 500 bytes for confirmations (start/update/resolve): UUID (36 chars) +
      status + JSON overhead fits in ~100-200 bytes. 500 bytes provides
      headroom while catching bloat like full entries (~2KB+).
    - 2000 bytes for get_active: Returns full entry with all fields.
      Typical entries are 800-1500 bytes.
    - 500 bytes per entry for list: Summaries only (ID, domain, status).
      Each summary should be ~100-200 bytes.
    """
```

#### Fixtures

The tests will reuse existing fixture patterns from `tests/server/tools/test_ghap.py`:

1. `temp_journal_path`: Creates temporary directory for GHAP journal
2. `observation_collector`: Creates `ObservationCollector` with temp path
3. `observation_persister`: Creates mock `ObservationPersister` with mocked vector store
4. `tools`: Gets GHAP tool dictionary from `get_ghap_tools()`

These fixtures are defined locally in the test file (not shared via conftest) to match the existing pattern in `test_ghap.py` and `test_bug_030_regression.py`.

#### Test Cases

| Test Method | Tool | Max Size | Rationale |
|-------------|------|----------|-----------|
| `test_start_ghap_response_size` | `start_ghap` | < 500 bytes | Returns `{ok: true, id: "ghap_..."}` - confirmation only |
| `test_update_ghap_response_size` | `update_ghap` | < 500 bytes | Returns `{success: true, iteration_count: N}` |
| `test_resolve_ghap_response_size` | `resolve_ghap` | < 500 bytes | Returns `{ok: true, id: "ghap_..."}` - confirmation only |
| `test_get_active_ghap_response_size_with_entry` | `get_active_ghap` | < 2000 bytes | Full entry expected |
| `test_get_active_ghap_response_size_no_entry` | `get_active_ghap` | < 500 bytes | Empty state response |
| `test_list_ghap_entries_response_size` | `list_ghap_entries` | < 500 bytes per entry | Summaries only |

#### Minimum Size Assertions

All tests will also verify responses are non-empty (minimum 10 bytes) to catch broken endpoints that return empty or minimal responses.

#### Assertion Message Pattern

```python
assert response_size < max_size, (
    f"start_ghap response too large: {response_size} bytes >= {max_size} byte limit. "
    f"Response should be minimal confirmation, not full entry. "
    f"See BUG-030 for context."
)
```

### Response Size Analysis

Current GHAP tool responses (post BUG-030 fix):

| Tool | Current Response | Typical Size |
|------|-----------------|--------------|
| `start_ghap` | `{ok: true, id: "ghap_..."}` | ~60-80 bytes |
| `update_ghap` | `{success: true, iteration_count: N}` | ~40-50 bytes |
| `resolve_ghap` | `{ok: true, id: "ghap_..."}` | ~60-80 bytes |
| `get_active_ghap` (with entry) | Full entry dict | ~800-1500 bytes |
| `get_active_ghap` (no entry) | Null-valued dict with `has_active: false` | ~200-300 bytes |
| `list_ghap_entries` | `{results: [...], count: N}` | ~200-400 bytes per entry |

The limits provide comfortable headroom (2-3x typical sizes) while still catching regressions to verbose responses (which would be 5-10x larger).

### Edge Cases

1. **Error responses**: Error responses (`{error: {type, message}}`) should also be small (<500 bytes). Tests will verify error responses don't exceed limits.

2. **Empty list**: `list_ghap_entries` with no results should return `{results: [], count: 0}` which is well under 500 bytes.

3. **Large content**: If a user stores very long hypothesis/action text (up to 1000 chars each), `get_active_ghap` could approach the 2000 byte limit. The limit accounts for this.

### Testing Strategy

The tests use the existing async test pattern with pytest-asyncio:

```python
@pytest.mark.asyncio
async def test_start_ghap_response_size(self, tools: dict[str, Any]) -> None:
    ...
```

Tests will run as part of the standard test suite (`pytest -vvsx`) and will FAIL (not warn) if limits are exceeded, ensuring they block CI/merges.

### Dependencies

No new dependencies required. The implementation uses:
- `json` (stdlib)
- `pytest` and `pytest-asyncio` (existing test dependencies)
- `tempfile` and `pathlib` (stdlib)
- `unittest.mock` (stdlib)

### Implementation Plan

1. Create `tests/server/test_response_efficiency.py`
2. Add fixtures matching existing patterns from `test_ghap.py`
3. Implement test class `TestGHAPResponseEfficiency` with:
   - Class docstring explaining rationale and size limits
   - Test methods for each GHAP tool
   - Clear assertion messages referencing BUG-030
   - Comments documenting why each limit was chosen
4. Verify tests pass against current implementation
5. Run full test suite to ensure no regressions

### Verification

To verify the implementation:

```bash
# Run just the new tests
pytest tests/server/test_response_efficiency.py -vvsx

# Run all server tests to ensure no conflicts
pytest tests/server/ -vvsx

# Run full test suite
pytest -vvsx
```

### Future Considerations

1. **SPEC-045**: Memory tool response sizes will follow a similar pattern
2. **SPEC-046**: Token counting utility could replace byte approximations if precise token counts become important
3. **Baseline tracking**: Could log response sizes to a results file (like `test_benchmarks.py`) for trend analysis
