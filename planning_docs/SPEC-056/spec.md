# SPEC-056: Hook Configuration Consolidation

## Problem Statement

Claude Code hooks are configured across multiple locations with inconsistent documentation:
- `.claude/settings.json` - Claude Code hook registration
- `clams/hooks/*.sh` - Shell integration hooks for MCP/CLAMS
- `.claude/hooks/*.py` - Python linting hooks (different purpose)
- `~/.clams/config.env` - Runtime configuration (per SPEC-029)

This fragmentation makes it hard to:
1. Understand which hooks exist and what they do
2. Know what configuration affects each hook
3. Debug hook issues
4. Add new hooks following existing patterns

**Clarification**: There are TWO types of hooks in this project:
- **Integration hooks** (`clams/hooks/*.sh`): Connect CLAMS to Claude Code events
- **Linting hooks** (`.claude/hooks/*.py`): Check code quality during development

This spec focuses on documenting the **integration hooks** in `clams/hooks/`.

## Proposed Solution

Create comprehensive documentation and a validation script for the integration hooks:
1. Central documentation file documenting all hooks
2. Validation script to verify hook configuration consistency
3. Formalize the existing environment variable patterns

## Acceptance Criteria

### Documentation

- [ ] Central documentation at `clams/hooks/README.md`
- [ ] For each hook, documentation includes:
  - Hook filename and Claude Code event type
  - Purpose and when it triggers
  - Input: environment variables read, stdin format (if any)
  - Output: JSON schema (hookSpecificOutput format), exit codes
  - Blocking behavior: synchronous/timeout/daemon
  - Configuration: which env vars control behavior
- [ ] Note that `session_end.sh` is not currently supported by Claude Code

### Hook Documentation Details

Document each hook with these specific details:

| Hook | Event | Blocking | Timeout | Notes |
|------|-------|----------|---------|-------|
| `session_start.sh` | SessionStart | No (spawns daemon) | N/A | Starts server if needed |
| `session_end.sh` | SessionEnd | N/A | N/A | **NOT SUPPORTED by Claude Code yet** |
| `user_prompt_submit.sh` | UserPromptSubmit | Yes | 30s | Assembles context |
| `ghap_checkin.sh` | PreToolCall | Yes | 1s | GHAP reminders |
| `outcome_capture.sh` | PostToolCall | Yes | 1s | Captures GHAP resolutions |

### Environment Variable Documentation

- [ ] Document existing `CLAMS_*` variables (don't rename to `CLAMS_HOOK_*`)
- [ ] Current variables to document:
  - `CLAMS_HTTP_HOST` - Server host (default: 127.0.0.1)
  - `CLAMS_HTTP_PORT` - Server port (default: 8765)
  - `CLAMS_GHAP_CHECK_FREQUENCY` - Tool calls between GHAP reminders
  - `CLAMS_DIR` - Path to CLAMS installation
- [ ] Note: config loaded from `~/.clams/config.env` per SPEC-029

### JSON Output Schema Documentation

- [ ] Document the Claude Code hook output schema:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart|UserPromptSubmit|PreToolCall|PostToolCall",
    "additionalContext": "string content for Claude"
  }
}
```
- [ ] Note which hooks produce output vs silent completion

### Validation Script

- [ ] Script `clams/hooks/validate_config.sh` created
- [ ] Validation checks:
  - All hook scripts referenced in `.claude/settings.json` exist
  - All hook scripts are executable
  - Hook scripts have valid bash syntax (`bash -n`)
  - Required environment variables are documented in README
- [ ] Script exits 0 if valid, 1 if issues found
- [ ] Clear output listing each check and result

### Settings Consistency

- [ ] `.claude/settings.json` hook paths match actual files in `clams/hooks/`
- [ ] Any hooks in `clams/hooks/` but not in settings are documented as "available but not registered"

## Implementation Notes

**README structure** (`clams/hooks/README.md`):
```markdown
# CLAMS Integration Hooks

These hooks integrate CLAMS with Claude Code's event system.

## Quick Reference

| Hook | Event | Purpose |
|------|-------|---------|
| session_start.sh | SessionStart | Initialize session, check orphaned GHAPs |
| ... | ... | ... |

## Environment Variables

All hooks read configuration from `~/.clams/config.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| CLAMS_HTTP_HOST | 127.0.0.1 | MCP server host |
| ... | ... | ... |

## Hook Details

### session_start.sh
**Event**: SessionStart
**Blocking**: No (spawns daemon if needed)
**Output**: JSON with orphaned GHAP context
...
```

**Validation script** approach:
```bash
#!/usr/bin/env bash
# Validate hook configuration

PASS=true

# Check each registered hook exists and is executable
# Parse .claude/settings.json for hook paths
# Run bash -n on each
# Report results
```

## Testing Requirements

All tests automated:

- [ ] Test: validation passes on current configuration
- [ ] Test: validation fails when hook script is missing (mock removal)
- [ ] Test: validation fails when hook script not executable
- [ ] Test: validation fails when hook has syntax error
- [ ] Test: README documents all hooks in `clams/hooks/`
- [ ] Test: README env vars match actual usage in hook scripts

## Dependencies

- **SPEC-020** (Hook Schema Conformance Tests) - Tests hook JSON output
- **SPEC-029** (Config Path Standardization) - Established `~/.clams/config.env`

## Out of Scope

- Linting hooks in `.claude/hooks/` (different system, different purpose)
- Changing hook behavior (documentation only)
- Creating new hooks
- Changing environment variable naming (document existing patterns)
- Hook testing infrastructure beyond validation (covered by SPEC-020)
