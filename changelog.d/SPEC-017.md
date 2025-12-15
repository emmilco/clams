## SPEC-017: Add Schema Conformance Tests for Enum Validation

### Summary
Added tests that verify MCP tool definition enum values match the canonical enum definitions in `enums.py`, preventing drift between advertised schemas and actual validation.

### Changes
- Added `tests/server/test_enum_schema_conformance.py` with 14 parameterized tests
- Tests cover all 5 enum types: domain, strategy, outcome, axis, root_cause.category
- Tests cover all 9 tools with enum properties
- Helper functions extract enums programmatically (not hardcoded)
- Tests fail bidirectionally if enums drift
