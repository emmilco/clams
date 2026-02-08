# SPEC-056: Hook Configuration Consolidation

## Problem Statement

Claude Code hooks are configured across multiple locations with inconsistent documentation:
- `clams_scripts/hooks/*.sh` - Shell integration hooks for MCP/CLAMS
- `clams_scripts/hooks/config.yaml` - Legacy hook configuration (partially duplicates config.env)
- `.claude/hooks/*.py` - Python linting hooks (different purpose)
- `~/.clams/config.env` - Runtime configuration (per SPEC-029)

This fragmentation makes it hard to:
1. Understand which hooks exist and what they do
2. Know what configuration affects each hook
3. Debug hook issues
4. Add new hooks following existing patterns

**Clarification**: There are TWO types of hooks in this project:
- **Integration hooks** (`clams_scripts/hooks/*.sh`): Connect CLAMS to Claude Code events
- **Linting hooks** (`.claude/hooks/*.py`): Check code quality during development

This spec focuses on documenting the **integration hooks** in `clams_scripts/hooks/`.

**Note**: README.md and validate_config.sh already exist at `clams_scripts/hooks/`. This spec verifies and updates existing documentation to ensure completeness against these acceptance criteria.

## Proposed Solution

Create comprehensive documentation and a validation script for the integration hooks:
1. Central documentation file documenting all hooks
2. Validation script to verify hook configuration consistency
3. Formalize the existing environment variable patterns

## Acceptance Criteria

### Documentation

- [ ] Central documentation at `clams_scripts/hooks/README.md`
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
- [ ] Complete list of variables used by hooks:
  - `CLAMS_HTTP_HOST` - Server host (default: 127.0.0.1)
  - `CLAMS_HTTP_PORT` - Server port (default: 6334)
  - `CLAMS_PID_FILE` - Path to server PID file (default: ~/.clams/server.pid)
  - `CLAMS_STORAGE_PATH` - Path to CLAMS storage directory (default: ~/.clams)
  - `CLAMS_DIR` - Derived from CLAMS_STORAGE_PATH in hooks
  - `CLAMS_GHAP_CHECK_FREQUENCY` - Tool calls between GHAP reminders
- [ ] Note: config loaded from `~/.clams/config.env` per SPEC-029
- [ ] Document derived variables (CLAMS_DIR, JOURNAL_DIR, SERVER_URL) computed within hooks

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
- [ ] Note which hooks produce output vs silent completion:
  - `session_start.sh` - Produces JSON with orphaned GHAP context
  - `session_end.sh` - No output (not supported)
  - `user_prompt_submit.sh` - Produces JSON with assembled context
  - `ghap_checkin.sh` - Produces JSON with GHAP reminder (or silent if not due)
  - `outcome_capture.sh` - Produces JSON with capture prompt (or silent if no resolution)

### Validation Script

- [ ] Script `clams_scripts/hooks/validate_config.sh` exists and passes
- [ ] Validation checks:
  - All hook scripts in `clams_scripts/hooks/` exist
  - All hook scripts are executable
  - Hook scripts have valid bash syntax (`bash -n`)
  - Required dependencies are available (curl, jq, bash)
  - README.md exists and documents all hooks
  - Documented env vars are actually used in hook scripts
- [ ] Script exits 0 if valid, 1 if issues found
- [ ] Clear output listing each check and result with colored pass/fail indicators

### Legacy Configuration

- [ ] Document that `config.yaml` is a legacy configuration source
- [ ] Note that hooks prefer environment variables from `~/.clams/config.env`
- [ ] Document fallback behavior: env var -> config.env -> config.yaml -> defaults

## Implementation Notes

**README structure** (`clams_scripts/hooks/README.md`):
```markdown
# CLAMS Integration Hooks

These hooks integrate CLAMS with Claude Code's event system.

## Quick Reference

| Hook | Event | Purpose |
|------|-------|---------|
| session_start.sh | SessionStart | Initialize session, check orphaned GHAPs |
| session_end.sh | SessionEnd | (Not supported by Claude Code yet) |
| user_prompt_submit.sh | UserPromptSubmit | Assemble context for prompts |
| ghap_checkin.sh | PreToolCall | GHAP progress reminders |
| outcome_capture.sh | PostToolCall | Capture GHAP resolutions |

## Environment Variables

All hooks read configuration from `~/.clams/config.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| CLAMS_HTTP_HOST | 127.0.0.1 | MCP server host |
| CLAMS_HTTP_PORT | 6334 | MCP server port |
| CLAMS_PID_FILE | ~/.clams/server.pid | Server PID file path |
| CLAMS_STORAGE_PATH | ~/.clams | CLAMS data directory |
| CLAMS_GHAP_CHECK_FREQUENCY | 10 | Tool calls between GHAP reminders |

## Hook Details

### session_start.sh
**Event**: SessionStart
**Blocking**: No (spawns daemon if needed)
**Output**: JSON with orphaned GHAP context
**Exit codes**: 0 (success), non-zero (failure, but hook doesn't block)
...
```

**Validation script** approach:
```bash
#!/usr/bin/env bash
# Validate hook configuration

PASS=true
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Hook Configuration Validation ==="

# Check each registered hook exists and is executable
for hook in session_start.sh user_prompt_submit.sh ghap_checkin.sh outcome_capture.sh; do
    if [[ ! -f "$SCRIPT_DIR/$hook" ]]; then
        echo "FAIL: $hook not found"
        PASS=false
    elif [[ ! -x "$SCRIPT_DIR/$hook" ]]; then
        echo "FAIL: $hook not executable"
        PASS=false
    elif ! bash -n "$SCRIPT_DIR/$hook" 2>&1; then
        echo "FAIL: $hook has syntax errors"
        PASS=false
    else
        echo "PASS: $hook"
    fi
done

$PASS && exit 0 || exit 1
```

## Testing Requirements

All tests automated:

- [ ] Test: validation passes on current configuration
- [ ] Test: validation fails when hook script is missing (mock removal)
- [ ] Test: validation fails when hook script not executable
- [ ] Test: validation fails when hook has syntax error
- [ ] Test: README documents all hooks in `clams_scripts/hooks/`
- [ ] Test: README env vars match actual usage in hook scripts (grep for CLAMS_* in hooks)
- [ ] Test: validation detects missing dependencies

## Dependencies

- **SPEC-020** (Hook Schema Conformance Tests) - Tests hook JSON output
- **SPEC-029** (Config Path Standardization) - Established `~/.clams/config.env`

## Out of Scope

- Linting hooks in `.claude/hooks/` (different system, different purpose)
- Changing hook behavior (documentation only)
- Creating new hooks
- Changing environment variable naming (document existing patterns)
- Hook testing infrastructure beyond validation (covered by SPEC-020)
