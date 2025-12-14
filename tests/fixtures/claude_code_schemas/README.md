# Claude Code Hook Schemas

This directory contains JSON Schema definitions for Claude Code hook output formats.

## Documentation Source

- Official documentation: https://docs.anthropic.com/en/docs/claude-code/hooks
- These schemas were derived from the official Claude Code hooks documentation

## Schema Files

| File | Hook Event | Status |
|------|------------|--------|
| `session_start.json` | SessionStart | Supported |
| `user_prompt_submit.json` | UserPromptSubmit | Supported |
| `session_end.json` | SessionEnd | NOT YET SUPPORTED |

## Expected Output Format

All hooks that inject context must output JSON in this format:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "<EventName>",
    "additionalContext": "<string to inject>"
  }
}
```

## Bug References

- **BUG-050**: SessionStart hook was using incorrect `{"type": ..., "content": ...}` format
- **BUG-051**: UserPromptSubmit hook was using incorrect `{"type": ..., "content": ...}` format

## Usage in Tests

These schemas are used by `tests/hooks/test_hook_schemas.py` to validate that
hook scripts output correctly formatted JSON that Claude Code will recognize.

```python
from tests.fixtures.claude_code_schemas import load_schema

schema = load_schema("session_start")
# Use with jsonschema library to validate hook output
```
