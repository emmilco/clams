# SPEC-044: Response Size Assertions for GHAP Tests (R15-A)

## Problem Statement

BUG-030 showed GHAP tools returning full records on every operation, wasting approximately 50,000 tokens during bulk generation of 100 entries. API responses can be excessively verbose, wasting tokens in LLM-facing APIs.

No tests verify that API responses are appropriately sized. Verbose responses waste tokens in LLM interactions, and bloat can creep in without anyone noticing.

## Proposed Solution

Add tests that measure and assert on GHAP tool response sizes to ensure they stay within token-efficient limits.

## Acceptance Criteria

- [ ] Tests exist in `tests/server/test_response_efficiency.py` or similar
- [ ] Tests verify GHAP tool responses are under size limits (exclusive, i.e., `<`):
  - `start_ghap`: response < 500 bytes (confirmation + ID only)
  - `update_ghap`: response < 500 bytes (minimal confirmation)
  - `resolve_ghap`: response < 500 bytes (minimal confirmation)
  - `get_active_ghap`: response < 2000 bytes (full entry is expected)
  - `list_ghap_entries`: response < 500 bytes per entry (summaries, not full)
- [ ] Tests verify responses are non-empty (minimum 10 bytes to catch broken endpoints)
- [ ] Tests use `json.dumps()` to measure actual serialized size
- [ ] Clear assertion messages show actual vs expected size
- [ ] Test documents why each limit was chosen (in comments)
- [ ] Tests are regression tests - failures block CI/merges (not just informational)
- [ ] Tests fail if responses exceed limits

## Implementation Notes

- Size limits rationale (based on BUG-030 analysis):
  - **500 bytes for start/update/resolve**: These operations need only return a confirmation message and GHAP ID (UUID is 36 chars). A UUID + status + minimal JSON overhead fits comfortably in ~100-200 bytes. 500 bytes provides headroom while catching egregious bloat like returning full entries (~2KB+ each).
  - **2000 bytes for get_active**: Returns full entry with goal, hypothesis, action, prediction, history. Typical entries are 800-1500 bytes. 2000 bytes allows reasonable content while catching bloat.
  - **500 bytes per entry for list**: List should return summaries (ID, domain, status, created_at), not full entries. Each summary should be ~100-200 bytes.
- Reference: BUG-030 - GHAP tools wasted ~50k tokens during bulk generation (returned full entries instead of confirmations)
- Example test pattern:
  ```python
  class TestGHAPResponseEfficiency:
      """Verify GHAP responses stay within token-efficient limits."""

      async def test_start_ghap_response_size(self, ghap_tools):
          """start_ghap should return minimal confirmation, not full entry."""
          response = await ghap_tools.start_ghap(
              domain="debugging",
              strategy="systematic-elimination",
              goal="Test goal",
              hypothesis="Test hypothesis",
              action="Test action",
              prediction="Test prediction",
          )

          response_size = len(json.dumps(response))
          max_size = 500  # Confirmation + ID only

          assert response_size < max_size, (
              f"start_ghap response too large: {response_size} bytes > {max_size} bytes. "
              "Response should be minimal confirmation, not full entry."
          )
  ```

## Testing Requirements

- Run tests against current implementation
- If tests fail, it indicates the fix from BUG-030 may have regressed
- Tests should use real GHAP tools with test database
- Document expected response structure in test comments

## Out of Scope

- Memory tool response sizes (covered by SPEC-045)
- Token counting utility (covered by SPEC-046)
- Actual token counts (bytes are a reasonable proxy)
