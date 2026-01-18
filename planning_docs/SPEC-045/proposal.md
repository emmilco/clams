# SPEC-045: Technical Proposal - Response Size Assertions for Memory Tools

## Overview

This proposal describes the implementation of response size assertion tests for memory tools (`store_memory`, `retrieve_memories`, `list_memories`, `delete_memory`). These tests ensure responses remain token-efficient and catch regressions where tools echo back full content unnecessarily.

## Technical Approach

### Test Location

Tests will be placed in `tests/server/test_response_efficiency.py`. This file is shared with SPEC-044 (GHAP response size tests) to keep all response efficiency regression tests in one location.

If SPEC-044 merges first, we add a new test class to the existing file. If SPEC-045 merges first, we create the file with memory tests, and SPEC-044 adds GHAP tests later.

### Test Structure

```
tests/server/test_response_efficiency.py
    class TestMemoryResponseEfficiency:
        test_store_memory_response_size()
        test_store_memory_no_content_echo()
        test_retrieve_memories_response_size_per_entry()
        test_list_memories_response_size_per_entry()
        test_delete_memory_response_size()
        test_memory_responses_non_empty()
```

### Size Limits and Rationale

| Tool | Max Size | Rationale |
|------|----------|-----------|
| `store_memory` | < 500 bytes | Returns confirmation + UUID (36 chars) + metadata. Should NOT echo content. Typical: ~150-200 bytes. |
| `retrieve_memories` | < 1000 bytes/entry | Returns content for search context, but should be bounded. Allows ~500 char content + metadata. |
| `list_memories` | < 500 bytes/entry | Metadata only (id, category, importance, created_at). No content. Typical: ~150 bytes. |
| `delete_memory` | < 300 bytes | Simplest operation - just `{"deleted": true}`. Typical: ~20 bytes. |

All limits use exclusive comparison (`<`) per spec.

### Current Implementation Analysis

Examining `src/clams/server/tools/memory.py`:

1. **`store_memory`** (lines 71-138):
   - Currently returns full `payload` including `content` (line 134)
   - **This is the bug** - storing 1000 chars echoes back 1000+ bytes
   - Response should return only: `{id, category, importance, tags, created_at}` or minimal confirmation

2. **`retrieve_memories`** (lines 140-203):
   - Returns `{"results": [...], "count": N}` where each result includes full payload + score
   - Per-entry size depends on stored content length
   - For semantic search, returning content is intentional (LLM needs context)
   - Test will verify per-entry size is bounded

3. **`list_memories`** (lines 205-280):
   - Returns `{"results": [...], "count": N, "total": N}`
   - Currently returns full payload including content (line 268)
   - **Potential issue** - list is for browsing, not search context
   - Should return metadata only, not content

4. **`delete_memory`** (lines 282-298):
   - Returns `{"deleted": True/False}`
   - Already minimal (~20 bytes) - this is correct

### Implementation Strategy

The tests will be implemented to:

1. **Detect current behavior**: Tests will initially fail if `store_memory` or `list_memories` return content
2. **Drive implementation fix**: Failing tests indicate the need to modify response structures
3. **Prevent regression**: Once fixed, tests ensure bloat doesn't creep back

### Test Implementation Details

```python
"""Response size efficiency tests for memory tools.

R15-B: Verify memory tool responses stay within token-efficient limits.

Reference: SPEC-045 - Add response size assertions for memory tools.
These tests are regression tests that block CI/merges if responses exceed limits.
"""

import json

import pytest

from clams.server.tools.memory import get_memory_tools


class TestMemoryResponseEfficiency:
    """Verify memory tool responses stay within token-efficient limits.

    These tests ensure memory tools don't waste tokens by echoing back
    full content or including unnecessary fields in responses.
    """

    @pytest.mark.asyncio
    async def test_store_memory_response_size(self, mock_services):
        """store_memory should return confirmation, not echo full content.

        Size limit: < 500 bytes

        Rationale: Store operations need only return confirmation + memory ID.
        A UUID (36 chars) + status + category + timestamps fits in ~150-200 bytes.
        500 bytes provides headroom while catching content echo-back bugs
        where storing 1000+ chars would return 1000+ bytes.
        """
        tools = get_memory_tools(mock_services)
        store_memory = tools["store_memory"]

        # Use large content to detect echo-back bugs
        large_content = "A" * 1000  # 1KB content

        response = await store_memory(
            content=large_content,
            category="fact",
            importance=0.8,
            tags=["test"],
        )

        response_size = len(json.dumps(response))
        max_size = 500

        assert response_size < max_size, (
            f"store_memory response too large: {response_size} bytes >= {max_size} bytes. "
            f"Response should not echo back the full content. "
            f"Stored 1000 char content but response should be ~150-200 bytes."
        )

    @pytest.mark.asyncio
    async def test_store_memory_no_content_echo(self, mock_services):
        """store_memory response should not include the stored content.

        The content field is only needed on retrieval, not on store confirmation.
        Including it wastes tokens proportional to content size.
        """
        tools = get_memory_tools(mock_services)
        store_memory = tools["store_memory"]

        test_content = "This is test content that should not be echoed"

        response = await store_memory(
            content=test_content,
            category="fact",
        )

        # Response should not contain the content
        response_str = json.dumps(response)
        assert test_content not in response_str, (
            f"store_memory echoed back content in response. "
            f"Response should be confirmation only, not include: '{test_content}'"
        )

    @pytest.mark.asyncio
    async def test_retrieve_memories_response_size_per_entry(
        self, mock_services, mock_search_result
    ):
        """retrieve_memories entries should stay under size limit.

        Size limit: < 1000 bytes per entry

        Rationale: Retrieved memories include content (for search context) but
        should have bounded content. 1000 bytes allows ~500 char useful content
        plus metadata while preventing unbounded bloat.
        """
        tools = get_memory_tools(mock_services)
        retrieve_memories = tools["retrieve_memories"]

        # Create mock result with moderate content
        mock_result = mock_search_result(
            id="test-id",
            payload={
                "id": "test-id",
                "content": "Test content " * 20,  # ~260 chars
                "category": "fact",
                "importance": 0.8,
                "tags": ["test"],
                "created_at": "2025-01-01T00:00:00Z",
            },
        )
        mock_services.vector_store.search.return_value = [mock_result]

        response = await retrieve_memories(query="test", limit=5)

        # Check each result individually
        for i, result in enumerate(response["results"]):
            result_size = len(json.dumps(result))
            max_size = 1000

            assert result_size < max_size, (
                f"retrieve_memories result[{i}] too large: {result_size} bytes >= {max_size} bytes. "
                f"Each result should stay under {max_size} bytes."
            )

    @pytest.mark.asyncio
    async def test_list_memories_response_size_per_entry(
        self, mock_services, mock_search_result
    ):
        """list_memories entries should return metadata only, under size limit.

        Size limit: < 500 bytes per entry

        Rationale: List operations return metadata only (id, category, importance,
        created_at). No content needed for browsing/filtering. Each entry should
        be ~100-200 bytes of pure metadata.
        """
        tools = get_memory_tools(mock_services)
        list_memories = tools["list_memories"]

        # Create mock result - content should NOT be in response
        mock_result = mock_search_result(
            id="test-id",
            payload={
                "id": "test-id",
                "content": "This content should not appear in list response " * 10,
                "category": "fact",
                "importance": 0.8,
                "tags": ["test"],
                "created_at": "2025-01-01T00:00:00Z",
            },
        )
        mock_services.vector_store.scroll.return_value = [mock_result]
        mock_services.vector_store.count.return_value = 1

        response = await list_memories(limit=10)

        for i, result in enumerate(response["results"]):
            result_size = len(json.dumps(result))
            max_size = 500

            assert result_size < max_size, (
                f"list_memories result[{i}] too large: {result_size} bytes >= {max_size} bytes. "
                f"List should return metadata only (no content). Each entry ~100-200 bytes."
            )

    @pytest.mark.asyncio
    async def test_delete_memory_response_size(self, mock_services):
        """delete_memory should return minimal confirmation.

        Size limit: < 300 bytes

        Rationale: Simplest operation - just needs {"deleted": true/false}.
        Actual response is typically ~20 bytes.
        """
        tools = get_memory_tools(mock_services)
        delete_memory = tools["delete_memory"]

        response = await delete_memory(memory_id="test-id")

        response_size = len(json.dumps(response))
        max_size = 300

        assert response_size < max_size, (
            f"delete_memory response too large: {response_size} bytes >= {max_size} bytes. "
            f"Should be simple confirmation like {{'deleted': true}}."
        )

    @pytest.mark.asyncio
    async def test_memory_responses_non_empty(self, mock_services):
        """All memory tool responses should be non-empty (minimum 10 bytes).

        This catches broken endpoints that return empty responses.
        """
        tools = get_memory_tools(mock_services)
        min_size = 10

        # Test store_memory
        store_response = await tools["store_memory"](
            content="Test", category="fact"
        )
        store_size = len(json.dumps(store_response))
        assert store_size >= min_size, (
            f"store_memory response too small: {store_size} bytes < {min_size} bytes"
        )

        # Test retrieve_memories (empty result is valid, but response structure exists)
        retrieve_response = await tools["retrieve_memories"](query="test", limit=5)
        retrieve_size = len(json.dumps(retrieve_response))
        assert retrieve_size >= min_size, (
            f"retrieve_memories response too small: {retrieve_size} bytes < {min_size} bytes"
        )

        # Test list_memories
        list_response = await tools["list_memories"](limit=10)
        list_size = len(json.dumps(list_response))
        assert list_size >= min_size, (
            f"list_memories response too small: {list_size} bytes < {min_size} bytes"
        )

        # Test delete_memory
        delete_response = await tools["delete_memory"](memory_id="test-id")
        delete_size = len(json.dumps(delete_response))
        assert delete_size >= min_size, (
            f"delete_memory response too small: {delete_size} bytes < {min_size} bytes"
        )
```

### Fixtures

Tests will use existing fixtures from `tests/server/tools/conftest.py`:
- `mock_services`: Provides mock ServiceContainer
- `mock_search_result`: Creates mock SearchResult objects

No new fixtures required.

### Expected Test Failures

Based on current implementation analysis:

1. **`test_store_memory_response_size`**: Will FAIL
   - Current implementation returns full payload including content
   - Storing 1000 chars will return ~1100+ bytes

2. **`test_store_memory_no_content_echo`**: Will FAIL
   - Content is explicitly included in response (line 134)

3. **`test_list_memories_response_size_per_entry`**: May FAIL
   - Returns full payload including content
   - If content is large, entries exceed 500 bytes

4. **`test_retrieve_memories_response_size_per_entry`**: Should PASS
   - Content is expected in retrieve results
   - Test uses moderate content size

5. **`test_delete_memory_response_size`**: Should PASS
   - Already returns minimal `{"deleted": true/false}`

6. **`test_memory_responses_non_empty`**: Should PASS
   - All tools return non-empty responses

### Required Implementation Changes

To make tests pass, `memory.py` needs modifications:

1. **`store_memory`** (line 134):
   ```python
   # Current (BAD):
   return payload

   # Proposed (GOOD):
   return {
       "id": memory_id,
       "status": "stored",
       "category": category,
       "importance": importance,
       "created_at": created_at.isoformat(),
   }
   ```

2. **`list_memories`** (line 268):
   ```python
   # Current (BAD):
   formatted = [r.payload for r in sorted_results]

   # Proposed (GOOD):
   formatted = [
       {
           "id": r.payload["id"],
           "category": r.payload["category"],
           "importance": r.payload["importance"],
           "tags": r.payload.get("tags", []),
           "created_at": r.payload["created_at"],
       }
       for r in sorted_results
   ]
   ```

**Note**: These implementation changes are out of scope for this spec. This spec only adds the tests. The failing tests will drive a follow-up fix or can be addressed in the same PR.

## File Structure

```
tests/
  server/
    test_response_efficiency.py   # NEW - Shared with SPEC-044
      class TestMemoryResponseEfficiency  # SPEC-045
      class TestGHAPResponseEfficiency    # SPEC-044 (separate spec)
```

## Interface Considerations

### Response Schema Changes

The proposed implementation changes will modify the response schemas for `store_memory` and `list_memories`. This is a **breaking change** for any consumers that rely on:

1. `store_memory` returning the stored content
2. `list_memories` returning content in each entry

However, per the CLAUDE.md principles: "Greenfield codebase: No external users, no backwards compatibility concerns."

### MCP Schema Updates

If MCP tool schemas are auto-generated from response types, ensure:
1. Schema definitions match new response structures
2. No drift between advertised and actual schemas

## Testing Requirements

1. **Tests are regression tests**: Failures block CI/merges
2. **Use real memory tools**: Tests call actual tool functions with mock services
3. **Document limits**: Each test includes comments explaining the rationale
4. **Clear assertions**: Messages show actual vs expected size

## Acceptance Verification

The implementation will be verified by:

1. All tests in `TestMemoryResponseEfficiency` pass
2. Tests use exclusive comparison (`<`) for upper bounds
3. Tests verify minimum 10 bytes for non-empty responses
4. Test comments document size limit rationale
5. Tests fail if responses exceed limits (regression protection)

## Dependencies

- SPEC-044 (GHAP response size tests) - Same test file, different class
- No blocking dependencies - can be implemented independently

## Out of Scope

- GHAP response sizes (SPEC-044)
- Token counting utility (SPEC-046)
- Content truncation behavior for retrieve (separate concern)
- Implementation fixes to memory tools (tests drive future fix)
