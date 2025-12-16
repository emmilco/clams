# SPEC-021: MCP Tool Response Schema Tests

## Problem Statement

MCP tool responses contain enum values and structured data that must remain consistent with the canonical definitions in `src/clams/server/tools/enums.py`. BUG-026 showed that advertised enums can drift from actual validation. Tests should verify that tool responses contain valid enum values and consistent structure.

**Note**: MCP tool definitions only specify input schemas, not output schemas. This spec tests response consistency (valid enums, expected field presence) rather than formal output schema validation.

When tool responses become inconsistent:
1. Clients may fail to parse responses correctly
2. Documentation becomes inaccurate
3. Type-safe clients get incorrect type information

## Proposed Solution

Add integration tests that invoke MCP tools and verify their response structure is consistent and contains valid enum values from canonical sources.

## Acceptance Criteria

- [ ] Test file exists at `tests/server/test_tool_response_schemas.py`
- [ ] For each MCP tool, tests verify response contains expected fields for that tool category
- [ ] Tests exercise at least one success case per tool
- [ ] Tests exercise at least one error case per tool (where applicable)
- [ ] Tests validate that enum values in responses match canonical enums in `enums.py` (e.g., domain, strategy, axis values)
- [ ] Tests verify required fields are present in responses (e.g., `ghap_id` for start_ghap, `memory_id` for store_memory)
- [ ] Tests run in CI and fail if response structure drifts

## Implementation Notes

- Tool definitions are in `src/clams/server/tools/__init__.py` (function `_get_all_tool_definitions()`)
- Focus on tools with structured output:
  - GHAP tools: `start_ghap`, `update_ghap`, `resolve_ghap`, `get_active_ghap`, `list_ghap_entries`
  - Memory tools: `store_memory`, `retrieve_memories`, `list_memories`, `delete_memory`
  - Search tools: `search_code`, `search_commits`, `search_experiences`
  - Value tools: `get_clusters`, `get_cluster_members`, `validate_value`, `store_value`, `list_values`
  - Context tools: `assemble_context`
  - Session tools: `start_session`, `get_orphaned_ghap`
- Enum values are imported from `src/clams/server/tools/enums.py`
- Example validation pattern:
  ```python
  async def test_start_ghap_response_schema():
      # Call tool through test fixture
      response = await call_tool("start_ghap", {
          "domain": "debugging",
          "strategy": "root-cause-analysis",
          "goal": "Test goal",
          "hypothesis": "Test hypothesis",
          "action": "Test action",
          "prediction": "Test prediction"
      })
      # Verify response contains expected fields
      assert "ghap_id" in response
      # Verify enum values are valid
      assert response.get("domain") in DOMAINS or "domain" not in response
  ```
- Use existing test fixtures for server setup

## Testing Requirements

- Use integration test fixtures with real services (or mocked stores)
- Validate enum fields against canonical sources in `enums.py`
- Test both successful operations and expected error responses
- Document any schema constraints not captured in the MCP definition
- Tests should be maintainable and not duplicate tool definition parsing

## Out of Scope

- Testing tool business logic (covered by existing unit tests)
- Testing enum definitions match (covered by SPEC-017)
- Testing HTTP API schema (covered by SPEC-022)
