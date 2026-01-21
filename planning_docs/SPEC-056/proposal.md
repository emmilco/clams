# SPEC-056: Hook Configuration Consolidation - Technical Proposal

## Problem Statement

Claude Code hooks are configured across multiple locations with no unified documentation:

1. **Integration hooks** (`clams/hooks/*.sh`) - Connect CLAMS to Claude Code events via shell scripts
2. **Linting hooks** (`.claude/hooks/*.py`) - Code quality checks (different purpose, out of scope)
3. **Configuration** (`clams/hooks/config.yaml`) - Local YAML config with redundant settings
4. **Runtime config** (`~/.clams/config.env`) - Per SPEC-029, the canonical configuration source

The fragmentation causes:
- Confusion about which config source takes precedence
- Difficulty debugging hook behavior (env var vs YAML vs defaults?)
- No single source of truth for hook documentation
- New contributors cannot easily understand the hook system

## Proposed Solution

Create two deliverables:

### 1. README.md Documentation

A comprehensive README at `clams/hooks/README.md` documenting all integration hooks with:
- Quick reference table
- Environment variable documentation
- Detailed per-hook documentation
- JSON output schema reference
- Troubleshooting guide

### 2. Validation Script

A bash script at `clams/hooks/validate_config.sh` that verifies:
- Hook scripts exist and are executable
- Hook scripts have valid bash syntax
- Required dependencies are available (curl, jq)
- Cross-references hooks against config.yaml

## README.md Structure

```markdown
# CLAMS Integration Hooks

These hooks integrate CLAMS with Claude Code's event system, providing context
injection and GHAP (Goal-Hypothesis-Action-Prediction) tracking.

## Quick Reference

| Hook | Event | Blocking | Purpose |
|------|-------|----------|---------|
| session_start.sh | SessionStart | No | Initialize session, start daemon, inject GHAP instructions |
| session_end.sh | SessionEnd | N/A | **NOT SUPPORTED by Claude Code** - session cleanup |
| user_prompt_submit.sh | UserPromptSubmit | Yes (30s) | Assemble and inject relevant context |
| ghap_checkin.sh | PreToolCall | Yes (1s) | GHAP progress reminders |
| outcome_capture.sh | PostToolCall | Yes (1s) | Capture test/build outcomes for GHAP |

## Configuration

### Primary Configuration: `~/.clams/config.env`

Per SPEC-029, runtime configuration is sourced from `~/.clams/config.env`.
This file is written by the server on startup and contains:

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| CLAMS_HTTP_HOST | 127.0.0.1 | MCP server host | All hooks |
| CLAMS_HTTP_PORT | 6334 | MCP server port | All hooks |
| CLAMS_PID_FILE | ~/.clams/server.pid | Server PID file path | session_start, user_prompt_submit |
| CLAMS_STORAGE_PATH | ~/.clams | CLAMS data directory | session_start, user_prompt_submit |
| CLAMS_GHAP_CHECK_FREQUENCY | 10 | Tool calls between GHAP reminders | ghap_checkin |

### Derived Variables

These are computed within hooks based on primary configuration:

| Variable | Derivation | Description |
|----------|------------|-------------|
| CLAMS_DIR | = CLAMS_STORAGE_PATH | Alias for storage path |
| JOURNAL_DIR | = CLAMS_DIR/journal | Session state storage |
| SERVER_URL | = http://HOST:PORT | Full server URL |

### Legacy Configuration: `config.yaml`

The `config.yaml` file in this directory is a legacy configuration source.
Hooks prefer environment variables but fall back to config.yaml for:
- `ghap_checkin.frequency` - Falls back if CLAMS_GHAP_CHECK_FREQUENCY is unset

**Note**: config.yaml will be deprecated in favor of config.env.

## Hook Details

### session_start.sh

**Event**: SessionStart
**Blocking**: No (spawns daemon if needed, returns immediately)
**Timeout**: N/A (non-blocking)

**Purpose**: Initialize a CLAMS session by:
1. Starting the MCP server daemon if not running
2. Generating and saving a new session ID
3. Checking for orphaned GHAPs from previous sessions
4. Injecting GHAP instructions and light context

**Input**: None (no stdin)

**Output**: JSON with hookSpecificOutput
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "## GHAP Learning System\n\n..."
  }
}
```

**Exit Codes**:
- 0: Always (graceful degradation on errors)

**Configuration Used**:
- CLAMS_HTTP_HOST, CLAMS_HTTP_PORT (server connection)
- CLAMS_PID_FILE (daemon detection)
- CLAMS_STORAGE_PATH (session state storage)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls
- `uuidgen` or Python for session ID generation

---

### session_end.sh

**Event**: SessionEnd
**Status**: **NOT SUPPORTED BY CLAUDE CODE**

**Purpose**: Would perform session cleanup (abandon unresolved GHAP).

**Note**: This hook exists for future compatibility when Claude Code adds
SessionEnd event support. Currently non-functional.

**Exit Codes**:
- 0: Always

---

### user_prompt_submit.sh

**Event**: UserPromptSubmit
**Blocking**: Yes
**Timeout**: 30 seconds (waits for server ready)

**Purpose**: Analyze the user's prompt and inject relevant context from:
- Past experiences (GHAP entries)
- Validated values

**Input**: User prompt via stdin

**Output**: JSON with hookSpecificOutput
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "## Relevant Context\n\n..."
  }
}
```

On failure/timeout, returns empty context (graceful degradation):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": ""
  }
}
```

**Exit Codes**:
- 0: Always (graceful degradation)

**Configuration Used**:
- CLAMS_HTTP_HOST, CLAMS_HTTP_PORT (server connection)
- CLAMS_PID_FILE (server detection)
- CLAMS_STORAGE_PATH (storage path)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls

---

### ghap_checkin.sh

**Event**: PreToolCall
**Blocking**: Yes
**Timeout**: 1 second

**Purpose**: Remind Claude to check GHAP progress after N tool calls.
Silent (no output) if check-in is not due.

**Input**: None

**Output**: JSON with GHAP reminder (only when due)
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolCall",
    "additionalContext": "## GHAP Check-in (10 tools since last update)\n\n**Current Goal**: ...\n**Current Hypothesis**: ...\n**Current Prediction**: ...\n\nIs your hypothesis still valid?"
  }
}
```

**Exit Codes**:
- 0: Always (silent if not due)

**Configuration Used**:
- CLAMS_HTTP_HOST, CLAMS_HTTP_PORT (server connection)
- CLAMS_GHAP_CHECK_FREQUENCY (check interval, default 10)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls

---

### outcome_capture.sh

**Event**: PostToolCall
**Blocking**: Yes
**Timeout**: 1 second

**Purpose**: Detect test/build outcomes and prompt for GHAP resolution.
Silent (no output) for non-test/build commands.

**Input**: Tool result JSON via stdin
```json
{
  "tool": "Bash",
  "command": "pytest tests/",
  "exit_code": 0,
  "stdout": "..."
}
```

**Output**: JSON with outcome prompt (only for test/build commands)

On test failure without active GHAP:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolCall",
    "additionalContext": "## Test FAILED\n\nConsider starting a GHAP..."
  }
}
```

On test success with active GHAP:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolCall",
    "additionalContext": "## Test PASSED\n\nYour prediction was: \"...\"\n\nDoes this confirm your hypothesis?"
  }
}
```

**Recognized Commands**:
- Tests: `pytest*`, `npm test*`, `cargo test*`, `make test*`
- Builds: `make build*`, `npm build*`, `cargo build*`

**Exit Codes**:
- 0: Always (silent for non-matching commands)

**Configuration Used**:
- CLAMS_HTTP_HOST, CLAMS_HTTP_PORT (server connection)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls

## JSON Output Schema

All hooks follow Claude Code's hook output schema:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart|UserPromptSubmit|PreToolCall|PostToolCall",
    "additionalContext": "Markdown content injected into Claude's context"
  }
}
```

**Schema Notes**:
- `hookEventName` must match the registered event type
- `additionalContext` is markdown-formatted text
- Empty `additionalContext` is valid (hook runs but injects nothing)
- No output at all means hook completed silently

## Troubleshooting

### Hook not triggering
1. Check hook is registered in Claude Code settings
2. Verify script is executable: `chmod +x clams/hooks/*.sh`
3. Test manually: `./clams/hooks/session_start.sh`

### Server not starting
1. Check PID file: `cat ~/.clams/server.pid`
2. Check server logs: `cat ~/.clams/server.log`
3. Verify port not in use: `lsof -i :6334`

### Empty context returned
1. Verify server is running: `curl http://127.0.0.1:6334/health`
2. Check config.env exists: `cat ~/.clams/config.env`
3. Run hook manually with debug output

### Configuration precedence
1. Environment variables (CLAMS_*)
2. ~/.clams/config.env (sourced by hooks)
3. config.yaml (legacy fallback)
4. Hardcoded defaults in scripts
```

## Validation Script Design

### validate_config.sh

```bash
#!/usr/bin/env bash
# clams/hooks/validate_config.sh
# Validate hook configuration consistency
#
# Usage: ./validate_config.sh
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PASS=true
CHECKS_RUN=0
CHECKS_FAILED=0

# Color output if terminal supports it
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    NC='\033[0m'
else
    RED='' GREEN='' YELLOW='' NC=''
fi

pass() { echo -e "${GREEN}PASS${NC}: $1"; ((CHECKS_RUN++)); }
fail() { echo -e "${RED}FAIL${NC}: $1"; PASS=false; ((CHECKS_RUN++)); ((CHECKS_FAILED++)); }
warn() { echo -e "${YELLOW}WARN${NC}: $1"; }

echo "=== CLAMS Hook Configuration Validation ==="
echo

# 1. Check each registered hook exists and is executable
echo "--- Hook Script Checks ---"
HOOKS=(session_start.sh session_end.sh user_prompt_submit.sh ghap_checkin.sh outcome_capture.sh)

for hook in "${HOOKS[@]}"; do
    hook_path="$SCRIPT_DIR/$hook"
    if [[ ! -f "$hook_path" ]]; then
        fail "$hook not found"
        continue
    fi

    if [[ ! -x "$hook_path" ]]; then
        fail "$hook not executable (run: chmod +x $hook_path)"
        continue
    fi

    if ! bash -n "$hook_path" 2>&1; then
        fail "$hook has syntax errors"
        continue
    fi

    pass "$hook"
done
echo

# 2. Check dependencies
echo "--- Dependency Checks ---"
DEPS=(curl jq bash)
for dep in "${DEPS[@]}"; do
    if command -v "$dep" &>/dev/null; then
        pass "$dep available"
    else
        fail "$dep not found in PATH"
    fi
done
echo

# 3. Check config.yaml exists (optional)
echo "--- Configuration Checks ---"
if [[ -f "$SCRIPT_DIR/config.yaml" ]]; then
    pass "config.yaml present"
else
    warn "config.yaml not found (using defaults)"
fi

# 4. Check documented env vars have defaults in scripts
echo
echo "--- Environment Variable Documentation ---"
ENV_VARS=(CLAMS_HTTP_HOST CLAMS_HTTP_PORT CLAMS_PID_FILE CLAMS_STORAGE_PATH CLAMS_GHAP_CHECK_FREQUENCY)
for var in "${ENV_VARS[@]}"; do
    # Check if variable is referenced in any hook
    if grep -q "$var" "$SCRIPT_DIR"/*.sh 2>/dev/null; then
        pass "$var documented and used"
    else
        warn "$var documented but not found in hooks"
    fi
done
echo

# 5. Check README exists
echo "--- Documentation Checks ---"
if [[ -f "$SCRIPT_DIR/README.md" ]]; then
    pass "README.md exists"
    # Check that README documents all hooks
    for hook in "${HOOKS[@]}"; do
        if grep -q "$hook" "$SCRIPT_DIR/README.md"; then
            pass "README documents $hook"
        else
            fail "README missing documentation for $hook"
        fi
    done
else
    fail "README.md not found"
fi
echo

# Summary
echo "=== Summary ==="
echo "Checks run: $CHECKS_RUN"
echo "Checks failed: $CHECKS_FAILED"

if $PASS; then
    echo -e "${GREEN}All checks passed${NC}"
    exit 0
else
    echo -e "${RED}Some checks failed${NC}"
    exit 1
fi
```

## Documentation Completeness Checklist

### README.md Must Include

- [x] Quick reference table with all hooks
- [x] Environment variable documentation with defaults
- [x] Per-hook documentation:
  - [x] Event type
  - [x] Blocking behavior and timeout
  - [x] Purpose description
  - [x] Input format (stdin)
  - [x] Output format (JSON schema)
  - [x] Exit codes
  - [x] Configuration used
  - [x] Dependencies
- [x] Note that session_end.sh is not supported
- [x] JSON output schema reference
- [x] Troubleshooting guide

### Validation Script Must Check

- [x] All hook scripts exist
- [x] All hook scripts are executable
- [x] All hook scripts have valid bash syntax
- [x] Required dependencies available (curl, jq, bash)
- [x] README.md exists and documents all hooks
- [x] Documented env vars are used in scripts

## Implementation Notes

### File Locations

| File | Purpose |
|------|---------|
| `clams/hooks/README.md` | Comprehensive hook documentation |
| `clams/hooks/validate_config.sh` | Configuration validation script |

### Testing Strategy

Tests should verify:
1. `validate_config.sh` passes on current configuration
2. `validate_config.sh` fails appropriately when:
   - Hook script is removed
   - Hook script is not executable
   - Hook script has syntax error
3. README documents all hooks in `clams/hooks/`
4. README env vars match actual usage (grep CLAMS_* in hooks)

### Dependencies

- **SPEC-020** (Hook Schema Conformance Tests) - Tests hook JSON output format
- **SPEC-029** (Config Path Standardization) - Established `~/.clams/config.env` as canonical config

### Out of Scope

- Linting hooks in `.claude/hooks/` (different system)
- Behavior changes to hooks
- Creating new hooks
- Renaming environment variables
