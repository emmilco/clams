# SPEC-045: Response Size Assertions for Memory Tools (R15-B)

## Problem Statement

Memory tools (`store_memory`, `retrieve_memories`, `list_memories`) could return excessively verbose responses, echoing back full content or including unnecessary fields. This wastes tokens in LLM interactions.

No tests verify response efficiency for memory tools. Bloat can creep in without anyone noticing.

## Proposed Solution

Add tests that measure and assert on memory tool response sizes to ensure they stay within token-efficient limits.

## Acceptance Criteria

- [ ] Tests exist in `tests/server/test_response_efficiency.py` (same file as SPEC-044)
- [ ] Tests verify memory tool responses are under size limits:
  - `store_memory`: response < 500 bytes (confirmation, not echo of content)
  - `retrieve_memories`: response < 1000 bytes per memory (summaries)
  - `list_memories`: response < 500 bytes per entry
  - `delete_memory`: response < 300 bytes (simple confirmation)
- [ ] Tests verify responses don't echo back full content on store
- [ ] Tests use large content inputs to verify no content echo
- [ ] Clear assertion messages show actual vs expected size
- [ ] Test documents expected response structure in comments

## Implementation Notes

- Key insight: `store_memory` should NOT echo back the full content
- Test with large content to verify this:
  ```python
  class TestMemoryResponseEfficiency:
      """Verify memory tool responses stay within limits."""

      async def test_store_memory_response_size(self, memory_tools):
          """store_memory should return confirmation, not echo full content."""
          response = await memory_tools.store_memory(
              content="A" * 1000,  # Large content
              category="fact",
          )

          response_size = len(json.dumps(response))
          max_size = 500

          assert response_size < max_size, (
              f"store_memory response too large: {response_size} bytes. "
              "Should not echo back the full content."
          )

      async def test_retrieve_memories_response_size(self, memory_tools):
          """retrieve_memories should return summaries, not full content."""
          # Store some memories first
          for i in range(5):
              await memory_tools.store_memory(
                  content=f"Memory content {i}" * 100,
                  category="fact",
              )

          response = await memory_tools.retrieve_memories("Memory", limit=5)

          # Each result should be reasonably sized
          for result in response:
              result_size = len(json.dumps(result))
              assert result_size < 1000, (
                  f"Single memory result too large: {result_size} bytes"
              )
  ```

## Testing Requirements

- Test with large content inputs to catch echo-back bugs
- Verify responses don't include full content when not needed
- Document expected response structure in test comments
- Tests should use real memory tools with test database

## Out of Scope

- GHAP response sizes (covered by SPEC-044)
- Token counting utility (covered by SPEC-046)
- Truncation behavior for retrieve (may be separate spec)
