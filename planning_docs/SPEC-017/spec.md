# SPEC-017: Add Schema Conformance Tests for Enum Validation

## Problem Statement

BUG-026 showed that advertised enum values in MCP tool definitions can drift from actual validation in the codebase. The tool definitions in `src/clams/server/tools/__init__.py` declare enum values that must match the canonical sources in `src/clams/server/tools/enums.py`.

Currently there is no automated verification that:
1. Tool definitions use the correct enum values
2. Enum values in tool definitions match `enums.py`
3. New enum values added to `enums.py` are reflected in tool definitions

## Proposed Solution

Add tests that verify enum values declared in MCP tool definitions match the canonical enum definitions in `enums.py`.

## Acceptance Criteria

- [ ] Test file exists at `tests/server/test_enum_schema_conformance.py`
- [ ] Tests verify `domain` enum in tool definitions matches `DOMAINS` from `enums.py`
- [ ] Tests verify `strategy` enum in tool definitions matches `STRATEGIES` from `enums.py`
- [ ] Tests verify `outcome` enum in tool definitions matches `OUTCOME_STATUS_VALUES` from `enums.py`
- [ ] Tests verify `axis` enum in tool definitions matches `VALID_AXES` from `enums.py`
- [ ] Tests verify `root_cause.category` enum matches `ROOT_CAUSE_CATEGORIES` from `enums.py`
- [ ] Tests extract enum values from tool definitions programmatically (not hardcoded)
- [ ] Tests verify ALL tools that use enum properties (see complete list in Implementation Notes)
- [ ] Tests run in CI and fail if enums drift

## Implementation Notes

- Canonical enum sources in `src/clams/server/tools/enums.py`:
  - `DOMAINS`: domain values for GHAP
  - `STRATEGIES`: problem-solving strategy values
  - `OUTCOME_STATUS_VALUES`: confirmed, falsified, abandoned
  - `VALID_AXES`: full, strategy, surprise, root_cause
  - `ROOT_CAUSE_CATEGORIES`: root cause categorization values
- Tool definitions are in `src/clams/server/tools/__init__.py` (function `_get_all_tool_definitions()`)
- Tools with enums to verify (complete list):
  - `start_ghap`: domain, strategy
  - `update_ghap`: strategy
  - `resolve_ghap`: status (outcome), root_cause.category
  - `search_experiences`: axis, domain, outcome
  - `get_clusters`: axis
  - `get_cluster_members`: cluster_id is a string (format 'axis_label', e.g., 'full_0') - verify description documents axis prefix format
  - `list_ghap_entries`: domain, outcome
  - `store_value`: axis
  - `list_values`: axis
- Pattern for extracting enums from tool definitions:
  ```python
  from clams.server.tools import _get_all_tool_definitions
  from clams.server.tools.enums import DOMAINS, STRATEGIES

  def test_start_ghap_domain_enum_matches():
      tools = _get_all_tool_definitions()
      start_ghap = next(t for t in tools if t["name"] == "start_ghap")
      domain_enum = start_ghap["inputSchema"]["properties"]["domain"]["enum"]
      assert set(domain_enum) == set(DOMAINS)
  ```

## Testing Requirements

- Tests must fail if any enum value is added to `enums.py` but not to tool definitions
- Tests must fail if any enum value is added to tool definitions but not to `enums.py`
- Tests must be maintainable (extract values programmatically, don't hardcode)

## Out of Scope

- Testing that validation functions reject invalid enums (existing unit tests cover this)
- Testing MCP tool response schemas (covered by SPEC-021)
