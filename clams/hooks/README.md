# CLAMS Integration Hooks

These hooks integrate CLAMS with Claude Code's event system, providing context
injection and GHAP (Goal-Hypothesis-Action-Prediction) tracking.

## Quick Reference

| Hook | Event | Blocking | Timeout | Purpose |
|------|-------|----------|---------|---------|
| `session_start.sh` | SessionStart | No | N/A | Initialize session, start daemon, inject GHAP instructions |
| `session_end.sh` | SessionEnd | N/A | N/A | **NOT SUPPORTED by Claude Code** - session cleanup |
| `user_prompt_submit.sh` | UserPromptSubmit | Yes | 30s | Assemble and inject relevant context |
| `ghap_checkin.sh` | PreToolCall | Yes | 1s | GHAP progress reminders |
| `outcome_capture.sh` | PostToolCall | Yes | 1s | Capture test/build outcomes for GHAP |

## Configuration

### Primary Configuration: `~/.clams/config.env`

Per SPEC-029, runtime configuration is sourced from `~/.clams/config.env`.
This file is written by the server on startup and contains:

| Variable | Default | Description | Used By |
|----------|---------|-------------|---------|
| `CLAMS_HTTP_HOST` | `127.0.0.1` | MCP server host | All hooks |
| `CLAMS_HTTP_PORT` | `6334` | MCP server port | All hooks |
| `CLAMS_PID_FILE` | `~/.clams/server.pid` | Server PID file path | session_start, user_prompt_submit |
| `CLAMS_STORAGE_PATH` | `~/.clams` | CLAMS data directory | session_start, user_prompt_submit |
| `CLAMS_GHAP_CHECK_FREQUENCY` | `10` | Tool calls between GHAP reminders | ghap_checkin |

### Derived Variables

These are computed within hooks based on primary configuration:

| Variable | Derivation | Description |
|----------|------------|-------------|
| `CLAMS_DIR` | `= CLAMS_STORAGE_PATH` | Alias for storage path |
| `JOURNAL_DIR` | `= CLAMS_DIR/journal` | Session state storage |
| `SERVER_URL` | `= http://HOST:PORT` | Full server URL |
| `SERVER_HOST` | `= CLAMS_HTTP_HOST` | Local alias for host |
| `SERVER_PORT` | `= CLAMS_HTTP_PORT` | Local alias for port |
| `PID_FILE` | `= CLAMS_PID_FILE` | Local alias for PID file |

### Legacy Configuration: `config.yaml`

The `config.yaml` file in this directory is a legacy configuration source.
Hooks prefer environment variables but fall back to config.yaml for:
- `hooks.ghap_checkin.frequency` - Falls back if `CLAMS_GHAP_CHECK_FREQUENCY` is unset

**Configuration Precedence**:
1. Environment variables (`CLAMS_*`)
2. `~/.clams/config.env` (sourced by hooks at startup)
3. `config.yaml` (legacy fallback, only for ghap_checkin.frequency)
4. Hardcoded defaults in scripts

**Note**: `config.yaml` will be deprecated in favor of `config.env`.

## Hook Details

### session_start.sh

**Event**: `SessionStart`
**Blocking**: No (spawns daemon if needed, returns immediately)
**Timeout**: N/A (non-blocking)

**Purpose**: Initialize a CLAMS session by:
1. Starting the MCP server daemon if not running
2. Generating and saving a new session ID
3. Checking for orphaned GHAPs from previous sessions
4. Injecting GHAP instructions and light context

**Input**: None (no stdin)

**Output**: JSON with `hookSpecificOutput`
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "## GHAP Learning System\n\n..."
  }
}
```

With orphaned GHAP from previous session:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "## Orphaned GHAP Detected\n\nFrom previous session:\n\n**Goal**: ...\n**Hypothesis**: ...\n\n**Options**:\n- Adopt and continue this work\n- Abandon with reason\n\n---\n\n## GHAP Learning System\n\n..."
  }
}
```

**Exit Codes**:
- `0`: Always (graceful degradation on errors)

**Configuration Used**:
- `CLAMS_HTTP_HOST`, `CLAMS_HTTP_PORT` (server connection)
- `CLAMS_PID_FILE` (daemon detection)
- `CLAMS_STORAGE_PATH` (session state storage in `journal/` subdirectory)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls
- `uuidgen` or Python for session ID generation

**Files Created/Modified**:
- `${JOURNAL_DIR}/.session_id` - Current session ID
- `${JOURNAL_DIR}/.tool_count` - Tool call counter (initialized to 0)

---

### session_end.sh

**Event**: `SessionEnd`
**Status**: **NOT SUPPORTED BY CLAUDE CODE**

**Purpose**: Would perform session cleanup (abandon unresolved GHAP).

**Note**: This hook exists for future compatibility when Claude Code adds
`SessionEnd` event support. Currently non-functional.

**Input**: None

**Output**: None (silent)

**Exit Codes**:
- `0`: Always

**Configuration Used**:
- Sources `~/.clams/config.env` but does not use any specific variables

---

### user_prompt_submit.sh

**Event**: `UserPromptSubmit`
**Blocking**: Yes
**Timeout**: 30 seconds (waits for server ready)

**Purpose**: Analyze the user's prompt and inject relevant context from:
- Past experiences (GHAP entries)
- Validated values

**Input**: User prompt via stdin

**Output**: JSON with `hookSpecificOutput`
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
- `0`: Always (graceful degradation)

**Configuration Used**:
- `CLAMS_HTTP_HOST`, `CLAMS_HTTP_PORT` (server connection)
- `CLAMS_PID_FILE` (server detection)
- `CLAMS_STORAGE_PATH` (storage path)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls

**MCP Tools Called**:
- `assemble_context` with `{"query": "<user_prompt>", "context_types": ["experiences", "values"], "limit": 10, "max_tokens": 1500}`

---

### ghap_checkin.sh

**Event**: `PreToolCall`
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
    "additionalContext": "## GHAP Check-in (10 tools since last update)\n\n**Current Goal**: ...\n**Current Hypothesis**: ...\n**Current Prediction**: ...\n\nIs your hypothesis still valid? If it changed, update your GHAP entry."
  }
}
```

Silent (no output) when check-in is not due.

**Exit Codes**:
- `0`: Always (silent if not due)

**Configuration Used**:
- `CLAMS_HTTP_HOST`, `CLAMS_HTTP_PORT` (server connection)
- `CLAMS_GHAP_CHECK_FREQUENCY` (check interval, default 10)
- Falls back to `config.yaml` `hooks.ghap_checkin.frequency` if env var unset

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls
- `python3` (for config.yaml fallback parsing only)

**MCP Tools Called**:
- `should_check_in` with `{"frequency": N}` - Checks if reminder is due
- `get_active_ghap` with `{}` - Gets current GHAP state
- `reset_tool_count` with `{}` - Resets counter after reminder

---

### outcome_capture.sh

**Event**: `PostToolCall`
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
    "additionalContext": "## Test FAILED\n\nConsider starting a GHAP to track your debugging approach and learn from the process.\n\nStart tracking with GHAP?"
  }
}
```

On test/build success with active GHAP:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolCall",
    "additionalContext": "## Test PASSED\n\nYour prediction was: \"...\"\n\nDoes this confirm your hypothesis? If yes, resolve GHAP as CONFIRMED."
  }
}
```

On test/build failure with active GHAP:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolCall",
    "additionalContext": "## Test FAILED\n\nYour prediction was: \"...\"\n\nActual: Test still fails.\n\nThis falsifies your hypothesis. Please:\n1. What surprised you?\n2. What was the root cause?\n3. What did you learn?"
  }
}
```

**Recognized Commands**:
- Tests: `pytest*`, `*npm test*`, `*cargo test*`, `*make test*`
- Builds: `*make build*`, `*npm build*`, `*cargo build*`

**Exit Codes**:
- `0`: Always (silent for non-matching commands)

**Configuration Used**:
- `CLAMS_HTTP_HOST`, `CLAMS_HTTP_PORT` (server connection)

**Dependencies**:
- `jq` for JSON processing
- `curl` for HTTP calls

**MCP Tools Called**:
- `get_active_ghap` with `{}` - Gets current GHAP state to determine response

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
- Empty `additionalContext` (`""`) is valid (hook runs but injects nothing)
- No output at all means hook completed silently (valid for conditional hooks like ghap_checkin and outcome_capture)

**Hook Output Behavior**:

| Hook | Always Outputs | Conditional Output |
|------|----------------|-------------------|
| `session_start.sh` | Yes | N/A |
| `session_end.sh` | No (silent) | N/A |
| `user_prompt_submit.sh` | Yes | Empty on failure |
| `ghap_checkin.sh` | No | Only when check-in is due |
| `outcome_capture.sh` | No | Only for test/build commands |

## Troubleshooting

### Hook not triggering
1. Check hook is registered in Claude Code settings (`.claude/settings.json` or global settings)
2. Verify script is executable: `chmod +x clams/hooks/*.sh`
3. Test manually: `./clams/hooks/session_start.sh`

### Server not starting
1. Check PID file: `cat ~/.clams/server.pid`
2. Check server logs: `cat ~/.clams/server.log`
3. Verify port not in use: `lsof -i :6334`
4. Try starting manually: `python -m clams.server.main --http --host 127.0.0.1 --port 6334`

### Empty context returned
1. Verify server is running: `curl http://127.0.0.1:6334/health`
2. Check config.env exists: `cat ~/.clams/config.env`
3. Run hook manually with debug output:
   ```bash
   echo "test prompt" | bash -x clams/hooks/user_prompt_submit.sh
   ```

### GHAP check-in not appearing
1. Verify frequency setting: `echo $CLAMS_GHAP_CHECK_FREQUENCY`
2. Check tool count: `curl http://127.0.0.1:6334/api/call -d '{"method":"tools/call","params":{"name":"should_check_in","arguments":{"frequency":10}}}'`

### Configuration precedence issues
Check which configuration is being used:
1. Environment variables take precedence: `echo $CLAMS_HTTP_PORT`
2. Then `~/.clams/config.env`: `cat ~/.clams/config.env`
3. Then `config.yaml` (for ghap_checkin.frequency only): `cat clams/hooks/config.yaml`
4. Finally hardcoded defaults in scripts

## Validation

Run the validation script to verify hook configuration:

```bash
./clams/hooks/validate_config.sh
```

The script checks:
- All hook scripts exist and are executable
- Hook scripts have valid bash syntax
- Required dependencies are available (curl, jq, bash)
- README.md exists and documents all hooks
- Documented environment variables are used in scripts

## Related Documentation

- **SPEC-008**: HTTP Transport - Describes the singleton MCP server architecture
- **SPEC-020**: Hook Schema Conformance Tests - Tests for hook JSON output format
- **SPEC-029**: Config Path Standardization - Established `~/.clams/config.env` as canonical config
- **Claude Code Hooks**: https://docs.anthropic.com/en/docs/claude-code/hooks
