# SPEC-020: Claude Code Hook Schema Conformance Tests

## Problem Statement

BUG-050 and BUG-051 were caused by hooks outputting JSON in a custom format (`{"type": ..., "content": ...}`) instead of Claude Code's required schema (`{"hookSpecificOutput": {"additionalContext": ...}}`). This was caught only after deployment.

Claude Code hooks have a specific JSON schema requirement for their output. When hooks don't conform to this schema, Claude Code silently ignores the hook output or fails unexpectedly. Conformance tests would catch schema mismatches before they reach production.

## Proposed Solution

Add tests that execute hook scripts with mocked dependencies and validate their JSON output against Claude Code's expected schema.

## Acceptance Criteria

- [ ] Test file exists at `tests/hooks/test_hook_schemas.py` (extends existing file)
- [ ] Tests verify `session_start.sh` output matches Claude Code SessionStart schema
- [ ] Tests verify `session_end.sh` produces no output (correct behavior - no schema validation needed)
- [ ] Tests verify `user_prompt_submit.sh` output matches Claude Code UserPromptSubmit schema
- [ ] Tests verify `ghap_checkin.sh` output matches Claude Code PreToolCall schema
- [ ] Tests verify `outcome_capture.sh` output matches Claude Code PostToolCall schema
- [ ] Expected schemas documented in JSON files at `tests/fixtures/claude_code_schemas/` with doc links
- [ ] Tests run hooks with mocked server (no real MCP server required)
- [ ] Tests validate that success paths produce schema-conformant JSON or no output (silent skip is valid)
- [ ] Tests validate that error paths produce schema-conformant JSON, no output, or exit silently
- [ ] Tests run in CI and fail if hook output doesn't match expected schema
- [ ] Hook scripts `ghap_checkin.sh` and `outcome_capture.sh` are fixed to use correct schema

## Implementation Notes

- Hook scripts are located at `clams/hooks/*.sh`
- Complete list of hooks and their expected event types:
  - `session_start.sh` -> SessionStart (produces JSON output)
  - `session_end.sh` -> SessionEnd (produces no output - correct behavior)
  - `user_prompt_submit.sh` -> UserPromptSubmit (produces JSON output)
  - `ghap_checkin.sh` -> PreToolCall (produces JSON output)
  - `outcome_capture.sh` -> PostToolCall (produces JSON output)
- Current correct schema structure (from `clams/hooks/session_start.sh`):
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": "<string>"
    }
  }
  ```
- **Note**: `ghap_checkin.sh` and `outcome_capture.sh` currently use a non-conformant `{"type": ..., "content": ...}` format. The tests should detect this and these hooks will need to be fixed as part of implementation.
- Schema source: https://docs.anthropic.com/en/docs/claude-code/hooks
- Testing approach:
  1. Set up mock environment variables (CLAMS_DIR, etc.)
  2. Create mock server response or stub curl calls
  3. Execute hook script and capture stdout
  4. Parse output as JSON
  5. Validate against expected schema structure
- Use `subprocess.run()` to execute hooks in test environment
- Consider using `jsonschema` library for strict validation

## Testing Requirements

- Run each hook script in isolation with mocked dependencies
- Parse output as JSON and validate against schema
- Test both success paths (server responds) and error paths (server unavailable)
- Verify hooks handle missing dependencies gracefully with valid JSON output
- Test must fail if hook outputs invalid JSON or wrong schema structure

## Out of Scope

- Testing hook behavior/functionality (e.g., what context is assembled)
- Testing MCP server responses (covered by SPEC-021)
- Testing HTTP API schema (covered by SPEC-022)
