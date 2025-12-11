# SPEC-008: Fast Hook Implementation with Direct File Access

## Background

SPEC-002-19 designed a hook system for automatic context injection and GHAP state management. The hooks were implemented as shell scripts that call MCP tools via `mcp_client.py`. However:

1. **The MCP tools were never implemented**: `start_session`, `get_orphaned_ghap`, `should_check_in`, `reset_tool_count`, `end_session`, and `assemble_context` don't exist in the MCP server
2. **The architecture is fundamentally slow**: Each MCP call spawns a new server process that loads embedding models (10+ seconds per call)
3. **The hooks silently fail**: They gracefully degrade to empty responses, so users don't know they're broken

This spec replaces the MCP-based hook implementation with direct file access, achieving < 200ms performance while delivering the functionality originally designed in SPEC-002-19.

## Problem Statement

The current hook implementation:
- Takes 10-15 seconds on session start (spawns 3 MCP servers sequentially)
- Never actually works (calls non-existent MCP tools)
- Wastes resources loading embedding models for simple file I/O operations

Users experience:
- Long delays when starting Claude Code sessions
- No context injection (hooks silently return empty data)
- No GHAP lifecycle management

## Goals

1. **Performance**: All hooks complete in < 200ms
2. **Functionality**: Hooks work as originally designed in SPEC-002-19
3. **Simplicity**: No MCP server dependency for hook operations
4. **Reliability**: Clear error messages when things fail (no silent degradation)

## Non-Goals

- Implementing the full `assemble_context` with semantic search (requires embeddings)
- HTTP-based MCP transport (future optimization)
- Domain-specific premortem (deferred in SPEC-002-19)

## Solution Overview

Replace `mcp_client.py` calls with a lightweight `direct_access.py` module that:
1. Reads/writes journal files directly (`.session_id`, `current_ghap.json`, `.tool_count`)
2. Queries Qdrant via HTTP for pre-stored values (no embedding generation needed)
3. Avoids importing heavy dependencies (torch, sentence_transformers)

## Detailed Design

### 1. New File: `.claude/hooks/direct_access.py`

A lightweight Python module (~100 lines) that provides:

```python
# Session management
start_session() -> {"session_id": str}
end_session() -> {"success": bool}

# GHAP lifecycle
get_orphaned_ghap() -> {"has_orphan": bool, "goal"?: str, "hypothesis"?: str}
get_active_ghap() -> {"has_active": bool, "goal"?: str, "hypothesis"?: str, "prediction"?: str}

# Tool counting for GHAP check-ins
should_check_in(frequency: int) -> {"should_check_in": bool}
increment_tool_count() -> {"count": int}
reset_tool_count() -> {"success": bool}

# Context retrieval (direct Qdrant HTTP, no embeddings)
get_values(limit: int) -> [{"text": str, "cluster_id": str, ...}, ...]
```

**Key constraint**: No imports from `clams.*` - this must be a standalone script that starts in < 50ms.

### 2. Updated Hook Scripts

#### `session_start.sh`
```bash
# Current (broken):
SESSION_RESULT=$(call_mcp "start_session" '{}')
ORPHAN_RESULT=$(call_mcp "get_orphaned_ghap" '{}')
CONTEXT_RESULT=$(call_mcp "assemble_context" '{"context_types": ["values"]}')

# New (working):
SESSION_RESULT=$(python3 "$SCRIPT_DIR/direct_access.py" start_session)
ORPHAN_RESULT=$(python3 "$SCRIPT_DIR/direct_access.py" get_orphaned_ghap)
VALUES=$(python3 "$SCRIPT_DIR/direct_access.py" get_values '{"limit": 5}')
```

#### `ghap_checkin.sh`
```bash
# Current (broken):
CHECKIN_RESULT=$(call_mcp "should_check_in" "{\"frequency\": $FREQUENCY}")
GHAP_RESULT=$(call_mcp "get_active_ghap" '{}')

# New (working):
CHECKIN_RESULT=$(python3 "$SCRIPT_DIR/direct_access.py" should_check_in "{\"frequency\": $FREQUENCY}")
GHAP_RESULT=$(python3 "$SCRIPT_DIR/direct_access.py" get_active_ghap)
```

#### `user_prompt_submit.sh`
For v1, this hook will inject values only (no semantic search). Rich context with experiences requires the MCP server and is out of scope.

```bash
# Simplified: just get top values relevant to any prompt
VALUES=$(python3 "$SCRIPT_DIR/direct_access.py" get_values '{"limit": 10}')
```

#### `outcome_capture.sh`
No changes needed - this hook only reads tool output and checks GHAP state.

### 3. Journal File Schema

Files in `.claude/journal/`:

| File | Format | Purpose |
|------|--------|---------|
| `.session_id` | Plain text | Current session ID |
| `current_ghap.json` | JSON | Active GHAP entry (if any) |
| `.tool_count` | Plain text (integer) | Tools since last GHAP check-in |
| `session_entries.jsonl` | JSONL | Historical session data |

### 4. Qdrant Direct Access

For `get_values()`, we query Qdrant's HTTP API directly:

```python
import httpx

def get_values(limit: int = 5) -> list[dict]:
    """Get top values from Qdrant without embeddings."""
    try:
        resp = httpx.post(
            "http://localhost:6333/collections/values/points/scroll",
            json={"limit": limit, "with_vectors": False, "with_payload": True},
            timeout=1.0,
        )
        if resp.status_code == 200:
            points = resp.json().get("result", {}).get("points", [])
            return [p.get("payload", {}) for p in points]
    except Exception:
        pass
    return []
```

This returns pre-stored values without generating embeddings, achieving < 100ms response time.

## Acceptance Criteria

### Performance (CRITICAL)
- [ ] `session_start.sh` completes in < 200ms
- [ ] `ghap_checkin.sh` completes in < 200ms
- [ ] `user_prompt_submit.sh` completes in < 200ms
- [ ] `outcome_capture.sh` completes in < 200ms
- [ ] Regression tests verify timing with assertions

### Functionality
- [ ] `session_start.sh` creates session ID and stores in `.session_id`
- [ ] `session_start.sh` detects orphaned GHAP from previous session
- [ ] `session_start.sh` injects top values as light context
- [ ] `ghap_checkin.sh` triggers reminder every N tool calls (configurable)
- [ ] `ghap_checkin.sh` shows current GHAP state in reminder
- [ ] `user_prompt_submit.sh` injects values as context
- [ ] `outcome_capture.sh` detects test pass/fail and prompts for GHAP resolution
- [ ] All hooks output valid JSON
- [ ] All hooks exit 0 (graceful degradation on errors)

### Code Quality
- [ ] `direct_access.py` has no imports from `clams.*`
- [ ] `direct_access.py` starts in < 50ms (measure with `time python3 -c "import direct_access"`)
- [ ] Type hints for all functions (mypy --strict)
- [ ] Error handling with clear messages (not silent failures)

### Testing
- [ ] Unit tests for `direct_access.py` functions
- [ ] Performance tests that assert < 200ms for each hook
- [ ] Integration test that runs full session lifecycle

## Migration

1. Keep `mcp_client.py` for tools that genuinely need MCP (future use)
2. Update all hook scripts to use `direct_access.py`
3. No changes to MCP server needed
4. No database migrations

## Future Work

- **SPEC-009**: Add `assemble_context` MCP tool with semantic search (for rich context when performance isn't critical)
- **SPEC-010**: HTTP-based MCP transport for lower-latency MCP calls
- **SPEC-011**: Domain-specific premortem (keyword detection + targeted context)

## Open Questions

1. Should `user_prompt_submit.sh` do any semantic search, or just return top values?
   - **Recommendation**: Top values only for v1. Semantic search requires embeddings which breaks the 200ms target.

2. Should we log timing metrics for hooks?
   - **Recommendation**: Yes, add optional timing to stderr for debugging.

3. What happens if Qdrant is unavailable?
   - **Recommendation**: Return empty values, log warning. Don't fail the hook.
