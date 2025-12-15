## SPEC-020: Claude Code Hook Schema Conformance Tests

### Summary
Added tests for hook schema conformance and fixed `ghap_checkin.sh` and `outcome_capture.sh` hooks to use the correct Claude Code schema format.

### Changes
- Fixed `clams/hooks/ghap_checkin.sh` to use `hookSpecificOutput` schema
- Fixed `clams/hooks/outcome_capture.sh` to use `hookSpecificOutput` schema (3 locations)
- Added `tests/fixtures/claude_code_schemas/pre_tool_call.json` schema definition
- Added `tests/fixtures/claude_code_schemas/post_tool_call.json` schema definition
- Added `TestPreToolCallSchema` and `TestPostToolCallSchema` test classes
- Updated `tests/fixtures/claude_code_schemas/__init__.py` with new constants
