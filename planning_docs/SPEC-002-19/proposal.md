# SPEC-002-19: Hook Scripts and Context Injection - Technical Proposal

## Revision Summary

This proposal has been updated to address review feedback and simplify v1 implementation:

### Human Decision: Skip Domain-Specific Premortem for v1

**Rationale**: Domain-specific premortem adds complexity without proven value. For v1, we'll focus on generic context injection via `assemble_context()`. This simplifies the implementation and reduces performance concerns.

**Changes**:
- Removed keyword-based domain detection from `user_prompt_submit.sh`
- Removed `get_premortem_context()` MCP call
- Removed `.premortem_injected` flag file logic
- Simplified to just call `assemble_context(query=prompt)` without domain parameter
- Added domain-specific premortem to "Out of Scope" and "Future Enhancements"

### Blocking Issues Fixed

1. **Type Check Gate Requirement**: Added mypy --strict compliance requirement throughout. All Python code must use strict type hints.

2. **MCP Tool Interface**: Clarified that `result.content[0].text` returns a **JSON string**, not a dict. Updated `call_tool()` to parse JSON explicitly with error handling.

3. **Shell Script Error Handling**: Changed from `set -euo pipefail` to `set -uo pipefail` with explicit error handling. Added `call_mcp()` helper function in all hooks that validates results and returns empty dict on failure. All hooks now exit 0 (graceful degradation).

4. **Dependency Documentation**: Removed yq dependency. Use Python with PyYAML for config parsing (more portable). Added jq, Python 3.10+, and PyYAML to dependencies section.

5. **jq Dependency**: Documented jq requirement with installation instructions for macOS and Ubuntu.

### Should-Fix Issues Addressed

6. **Hook Output Format**: Added comprehensive "Hook Output Format" section documenting JSON schema and Claude Code integration expectations.

7. **Performance Requirements**: Added performance strategy notes for `user_prompt_submit.sh`. Reduced limits (10 results, 1500 tokens) and acknowledged potential latency on cold start. Acceptable tradeoff for rich context.

8. **Test Fixtures**: Removed placeholder fixtures from proposal (implementation detail, not architectural).

9. **chmod +x Responsibility**: Added "Installation and Setup" section documenting that hooks must be made executable during installation/setup.

## Problem Statement

The Learning Memory Server needs to integrate seamlessly with Claude Code agent sessions through automatic context injection and GHAP state management. Currently, agents must explicitly call MCP tools to interact with the memory system, creating friction and reducing adoption. We need a "magic layer" where the system automatically:

1. Injects relevant context at the right moments (session start, user prompts)
2. Reminds agents to update GHAP state periodically during work
3. Auto-captures test/build outcomes and prompts for resolution
4. Manages session lifecycle and orphaned GHAP entries

**Key Challenges**:
- Hook scripts must be fast (<500ms) to avoid disrupting agent workflow
- Must gracefully degrade when MCP server is unavailable
- Need clean separation between hook logic and MCP client communication
- Output must be formatted for Claude Code's injection mechanism
- Need to detect test/build outcomes reliably from tool results

## Proposed Solution

Implement 5 hook scripts as shell scripts that call Python MCP client utilities. Each hook runs at a specific conversation lifecycle point and outputs JSON for Claude Code to inject as context.

### Architecture Overview

```
Claude Code Session
    |
    +--> Hook Trigger (SessionStart, UserPromptSubmit, PreToolCall, PostToolCall)
            |
            +--> Shell Script (.claude/hooks/*.sh)
                    |
                    +--> Python MCP Client (mcp_client.py)
                            |
                            +--> MCP Server (stdio protocol)
                                    |
                                    +--> ObservationCollector, ContextAssembler, etc.
```

### Design Principles

1. **Hooks are disposable**: If a hook fails or times out, the session continues unaffected
2. **MCP client is resilient**: Connection failures return empty results, not errors
3. **Performance first**: Hooks use cached data when possible and limit query scopes
4. **Progressive disclosure**: Light context at session start, rich context on user prompts
5. **One-shot premortem**: Inject premortem warnings only once per GHAP cycle to reduce noise

## Dependencies

### System Requirements

All hook scripts require:
- **Python 3.10+**: For mcp_client.py
- **jq**: JSON parsing in shell scripts
  - Install: `brew install jq` (macOS), `apt-get install jq` (Ubuntu)
- **PyYAML**: For config parsing in Python
  - Install: `pip install pyyaml`

### Python Dependencies

```
# requirements.txt for hooks
structlog>=23.1.0
mcp>=0.1.0  # MCP SDK
pyyaml>=6.0
```

**Note**: yq is NOT required. We use Python with PyYAML for YAML parsing (more portable).

## File Structure

```
.claude/
├── hooks/
│   ├── config.yaml                  # Hook configuration
│   ├── mcp_client.py                # Python MCP client utility
│   ├── session_start.sh             # Hook 1: Session initialization
│   ├── user_prompt_submit.sh        # Hook 2: User prompt analysis
│   ├── ghap_checkin.sh              # Hook 3: GHAP reminder (PreToolCall)
│   ├── outcome_capture.sh           # Hook 4: Test/build capture (PostToolCall)
│   └── session_end.sh               # Hook 5: Session cleanup (future)
└── journal/                         # ObservationCollector data
    ├── current_ghap.json
    ├── session_entries.jsonl
    └── .session_id
```

## Component Design

### 1. MCP Client Utility (mcp_client.py)

**Purpose**: Provide a command-line interface for hooks to call MCP tools.

**Interface**:
```python
#!/usr/bin/env python3
"""MCP client utility for hook scripts."""

import asyncio
import json
import sys
from typing import Any

import structlog
from mcp import ClientSession
from mcp.client.stdio import stdio_client

logger = structlog.get_logger()

class MCPClient:
    """Resilient MCP client for hook scripts."""

    def __init__(self, server_command: list[str], timeout: float = 10.0):
        """
        Initialize MCP client.

        Args:
            server_command: Command to start MCP server (e.g., ["python", "-m", "learning_memory_server"])
            timeout: Maximum time to wait for responses (default: 10s)
        """
        self.server_command = server_command
        self.timeout = timeout
        self.session: ClientSession | None = None

    async def connect(self) -> bool:
        """
        Connect to MCP server.

        Returns:
            True if connected, False on failure
        """
        try:
            read, write = await asyncio.wait_for(
                stdio_client(self.server_command),
                timeout=self.timeout
            )
            self.session = ClientSession(read, write)
            await asyncio.wait_for(
                self.session.initialize(),
                timeout=self.timeout
            )
            return True
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("mcp_client.connect_failed", error=str(e))
            return False

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result as dict, or empty dict on failure
        """
        if self.session is None:
            logger.warning("mcp_client.not_connected")
            return {}

        try:
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=self.timeout
            )
            # MCP tools return JSON string in .text, must parse it
            if result.content:
                text = result.content[0].text
                return json.loads(text) if text else {}
            return {}
        except json.JSONDecodeError as e:
            logger.error("mcp_client.invalid_json", tool=tool_name, error=str(e))
            return {}
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("mcp_client.call_failed", tool=tool_name, error=str(e))
            return {}

    async def close(self) -> None:
        """Close the MCP session."""
        if self.session is not None:
            await self.session.close()

async def main():
    """
    CLI interface for calling MCP tools from hooks.

    Usage:
        mcp_client.py <tool_name> <arguments_json>

    Output:
        JSON result on stdout

    Exit codes:
        0: Success
        1: Connection failed
        2: Tool call failed
    """
    if len(sys.argv) != 3:
        print(json.dumps({"error": "Usage: mcp_client.py <tool_name> <arguments_json>"}))
        sys.exit(2)

    tool_name = sys.argv[1]
    try:
        arguments = json.loads(sys.argv[2])
    except json.JSONDecodeError:
        print(json.dumps({"error": "Invalid JSON arguments"}))
        sys.exit(2)

    # Create client
    client = MCPClient(
        server_command=["python", "-m", "learning_memory_server"],
        timeout=10.0
    )

    # Connect
    if not await client.connect():
        print(json.dumps({"error": "Failed to connect to MCP server"}))
        sys.exit(1)

    # Call tool
    result = await client.call_tool(tool_name, arguments)

    # Close
    await client.close()

    # Output result
    print(json.dumps(result))
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
```

**Type Annotations**:
- All code uses strict type hints (PEP 484)
- Mypy --strict compliance required
- No use of `Any` without justification

**MCP Tool Response Handling**:
- MCP tools return `CallToolResult` objects
- `result.content[0].text` contains **JSON string**, not dict
- Must parse JSON: `json.loads(result.content[0].text)`
- Example:
  ```python
  result = await self.session.call_tool(tool_name, arguments)
  # result.content[0].text is '{"session_id": "123"}', not {"session_id": "123"}
  data = json.loads(result.content[0].text) if result.content else {}
  return data
  ```

**Error Handling**:
- Connection timeout: Return empty result, exit code 1
- Tool call timeout: Return empty result, exit code 2
- Invalid arguments: Return error JSON, exit code 2
- Server unavailable: Log warning, return empty result

**Performance Optimizations**:
- Connection pooling not needed (hooks are one-shot)
- Aggressive timeouts (10s max) to prevent blocking
- Minimal logging (structlog to stderr)

### 2. Hook 1: session_start.sh

**Purpose**: Initialize session state and inject standing context.

**Implementation**:
```bash
#!/bin/bash
# .claude/hooks/session_start.sh
# Hook: SessionStart
# Purpose: Initialize session and inject light context

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"

# Helper: Call MCP with error handling
call_mcp() {
  local tool_name="$1"
  local args="$2"
  local result

  if ! result=$(python3 "$MCP_CLIENT" "$tool_name" "$args" 2>/dev/null); then
    echo '{}'
    return 1
  fi

  # Validate JSON
  if ! echo "$result" | jq empty 2>/dev/null; then
    echo '{}'
    return 1
  fi

  echo "$result"
  return 0
}

# 1. Start session (optional, graceful degradation if fails)
SESSION_RESULT=$(call_mcp "start_session" '{}')
SESSION_ID=$(echo "$SESSION_RESULT" | jq -r '.session_id // empty')

# 2. Check for orphaned GHAP
ORPHAN_RESULT=$(call_mcp "get_orphaned_ghap" '{}')
HAS_ORPHAN=$(echo "$ORPHAN_RESULT" | jq -r '.has_orphan // false')

# 3. Get light context (top values only)
CONTEXT_RESULT=$(call_mcp "assemble_context" '{
  "query": "",
  "context_types": ["values"],
  "limit": 5,
  "max_tokens": 500
}')

# 4. Build output (always succeed, even if context is empty)
if [ "$HAS_ORPHAN" = "true" ]; then
  GOAL=$(echo "$ORPHAN_RESULT" | jq -r '.goal // "Unknown"')
  HYPOTHESIS=$(echo "$ORPHAN_RESULT" | jq -r '.hypothesis // "Unknown"')

  cat <<EOF
{
  "type": "orphan_detected",
  "content": "## Orphaned GHAP Detected\n\nFrom previous session:\n\n**Goal**: $GOAL\n**Hypothesis**: $HYPOTHESIS\n\n**Options**:\n- Adopt and continue this work\n- Abandon with reason\n\n---\n\n$(echo "$CONTEXT_RESULT" | jq -r '.markdown // ""')"
}
EOF
else
  cat <<EOF
{
  "type": "light",
  "content": $(echo "$CONTEXT_RESULT" | jq -r '.markdown // ""' | jq -Rs .)
}
EOF
fi

# Always exit successfully (graceful degradation)
exit 0
```

**Output Format**:
- With orphan: Prompt to adopt/abandon + light context
- Without orphan: Light context only (top values)

**Performance**: <500ms (session start + light context query)

### 3. Hook 2: user_prompt_submit.sh

**Purpose**: Analyze user prompt and inject rich context.

**Implementation**:
```bash
#!/bin/bash
# .claude/hooks/user_prompt_submit.sh
# Hook: UserPromptSubmit
# Purpose: Analyze prompt and inject rich context

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"

# Helper: Call MCP with error handling
call_mcp() {
  local tool_name="$1"
  local args="$2"
  local result

  if ! result=$(python3 "$MCP_CLIENT" "$tool_name" "$args" 2>/dev/null); then
    echo '{}'
    return 1
  fi

  if ! echo "$result" | jq empty 2>/dev/null; then
    echo '{}'
    return 1
  fi

  echo "$result"
  return 0
}

# Read user prompt from stdin
USER_PROMPT=$(cat)

# Get rich context (with limited results for performance)
CONTEXT_RESULT=$(call_mcp "assemble_context" "{
  \"query\": $(echo "$USER_PROMPT" | jq -Rs .),
  \"context_types\": [\"experiences\", \"values\"],
  \"limit\": 10,
  \"max_tokens\": 1500
}")

# Build output
CONTEXT_MD=$(echo "$CONTEXT_RESULT" | jq -r '.markdown // ""')

cat <<EOF
{
  "type": "rich",
  "content": $(echo "$CONTEXT_MD" | jq -Rs .),
  "token_count": $(echo "$CONTEXT_RESULT" | jq -r '.token_count // 0')
}
EOF

exit 0
```

**Performance Target**: <500ms (p95)

**Performance Strategy**:
- Reduced limits vs original spec (10 results vs 20, 1500 tokens vs 2000)
- Skip code search (only experiences + values for speed)
- Parallel MCP calls when possible (future optimization)
- May exceed 500ms on cold start; acceptable tradeoff for rich context

### 4. Hook 3: ghap_checkin.sh (PreToolCall)

**Purpose**: Remind agent to update GHAP state every N tool calls.

**Implementation**:
```bash
#!/bin/bash
# .claude/hooks/ghap_checkin.sh
# Hook: PreToolCall
# Purpose: GHAP check-in reminder

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

# Helper: Call MCP with error handling
call_mcp() {
  local tool_name="$1"
  local args="$2"
  local result

  if ! result=$(python3 "$MCP_CLIENT" "$tool_name" "$args" 2>/dev/null); then
    echo '{}'
    return 1
  fi

  if ! echo "$result" | jq empty 2>/dev/null; then
    echo '{}'
    return 1
  fi

  echo "$result"
  return 0
}

# Load configuration (with fallback if missing or invalid)
FREQUENCY=10
if [ -f "$CONFIG_FILE" ]; then
  # Try to parse with Python fallback (more portable than yq)
  FREQUENCY=$(python3 -c "
import yaml, sys
try:
    with open('$CONFIG_FILE') as f:
        cfg = yaml.safe_load(f)
    print(cfg.get('hooks', {}).get('ghap_checkin', {}).get('frequency', 10))
except:
    print(10)
" 2>/dev/null || echo "10")
fi

# Check if check-in is due
CHECKIN_RESULT=$(call_mcp "should_check_in" "{\"frequency\": $FREQUENCY}")
SHOULD_CHECKIN=$(echo "$CHECKIN_RESULT" | jq -r '.should_check_in // false')

# If not time for check-in, exit silently (no output)
if [ "$SHOULD_CHECKIN" != "true" ]; then
  exit 0
fi

# Get current GHAP state
GHAP_RESULT=$(call_mcp "get_active_ghap" '{}')
GOAL=$(echo "$GHAP_RESULT" | jq -r '.goal // "Unknown"')
HYPOTHESIS=$(echo "$GHAP_RESULT" | jq -r '.hypothesis // "Unknown"')
PREDICTION=$(echo "$GHAP_RESULT" | jq -r '.prediction // "Unknown"')

# Reset tool counter (fire and forget)
call_mcp "reset_tool_count" '{}' >/dev/null 2>&1 || true

# Output reminder
cat <<EOF
{
  "type": "reminder",
  "content": "## GHAP Check-in ($FREQUENCY tools since last update)\n\n**Current Goal**: $GOAL\n**Current Hypothesis**: $HYPOTHESIS\n**Current Prediction**: $PREDICTION\n\nIs your hypothesis still valid? If it changed, update your GHAP entry."
}
EOF

exit 0
```

**Performance**: <100ms (local file reads + simple check)

**Frequency Configuration**: Loaded from config.yaml, default 10 tools

### 5. Hook 4: outcome_capture.sh (PostToolCall)

**Purpose**: Auto-capture test/build outcomes and prompt for GHAP resolution.

**Implementation**:
```bash
#!/bin/bash
# .claude/hooks/outcome_capture.sh
# Hook: PostToolCall
# Purpose: Capture test/build outcomes

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"

# Helper: Call MCP with error handling
call_mcp() {
  local tool_name="$1"
  local args="$2"
  local result

  if ! result=$(python3 "$MCP_CLIENT" "$tool_name" "$args" 2>/dev/null); then
    echo '{}'
    return 1
  fi

  if ! echo "$result" | jq empty 2>/dev/null; then
    echo '{}'
    return 1
  fi

  echo "$result"
  return 0
}

# Read tool result from stdin
TOOL_RESULT=$(cat)

# Parse tool details (with validation)
if ! echo "$TOOL_RESULT" | jq empty 2>/dev/null; then
  # Invalid JSON, exit silently
  exit 0
fi

TOOL_NAME=$(echo "$TOOL_RESULT" | jq -r '.tool // ""')
COMMAND=$(echo "$TOOL_RESULT" | jq -r '.command // ""')
EXIT_CODE=$(echo "$TOOL_RESULT" | jq -r '.exit_code // 999')
STDOUT=$(echo "$TOOL_RESULT" | jq -r '.stdout // ""')

# Check if this is an outcome-triggering tool
IS_TEST=false
IS_BUILD=false

case "$COMMAND" in
  pytest*|*"npm test"*|*"cargo test"*|*"make test"*)
    IS_TEST=true
    ;;
  *"make build"*|*"npm build"*|*"cargo build"*)
    IS_BUILD=true
    ;;
esac

# If not outcome-triggering, exit silently
if [ "$IS_TEST" = "false" ] && [ "$IS_BUILD" = "false" ]; then
  exit 0
fi

# Determine outcome
OUTCOME_STATUS="unknown"
if [ "$EXIT_CODE" -eq 0 ]; then
  OUTCOME_STATUS="success"
else
  OUTCOME_STATUS="failure"
fi

# Get current GHAP state
GHAP_RESULT=$(call_mcp "get_active_ghap" '{}')
HAS_ACTIVE=$(echo "$GHAP_RESULT" | jq -r '.has_active // false')
PREDICTION=$(echo "$GHAP_RESULT" | jq -r '.prediction // ""')

# If failure and NO active GHAP, suggest starting GHAP
if [ "$OUTCOME_STATUS" = "failure" ] && [ "$HAS_ACTIVE" = "false" ]; then
  cat <<EOF
{
  "type": "suggestion",
  "content": "## Test FAILED\n\nConsider starting a GHAP to track your debugging approach and learn from the process.",
  "prompt": "Start tracking with GHAP?"
}
EOF
  exit 0
fi

# If GHAP active, compare prediction to outcome
if [ "$HAS_ACTIVE" = "true" ]; then
  if [ "$IS_TEST" = "true" ]; then
    OUTCOME_TYPE="Test"
  else
    OUTCOME_TYPE="Build"
  fi

  if [ "$OUTCOME_STATUS" = "success" ]; then
    cat <<EOF
{
  "type": "outcome",
  "content": "## $OUTCOME_TYPE PASSED\n\nYour prediction was: \"$PREDICTION\"\n\nDoes this confirm your hypothesis? If yes, resolve GHAP as CONFIRMED.",
  "suggested_action": "resolve_confirmed",
  "auto_captured": true
}
EOF
  else
    cat <<EOF
{
  "type": "outcome",
  "content": "## $OUTCOME_TYPE FAILED\n\nYour prediction was: \"$PREDICTION\"\n\nActual: Test still fails.\n\nThis falsifies your hypothesis. Please:\n1. What surprised you?\n2. What was the root cause?\n3. What did you learn?",
  "suggested_action": "resolve_falsified",
  "auto_captured": true
}
EOF
  fi
fi

exit 0
```

**Outcome Detection**:
- Test tools: pytest, npm test, cargo test, make test
- Build tools: make build, npm build, cargo build
- Exit code 0 = success, non-zero = failure

**Note**: Domain-specific premortem is deferred to v2. For v1, we focus on outcome detection and GHAP resolution prompts only.

**Performance**: <200ms (local file reads only, no premortem query)

### 6. Hook 5: session_end.sh (Future)

**Purpose**: Cleanup session state.

**Implementation**:
```bash
#!/bin/bash
# .claude/hooks/session_end.sh
# Hook: SessionEnd (NOT YET SUPPORTED BY CLAUDE CODE)
# Purpose: Session cleanup

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"

# Helper: Call MCP with error handling
call_mcp() {
  local tool_name="$1"
  local args="$2"
  local result

  if ! result=$(python3 "$MCP_CLIENT" "$tool_name" "$args" 2>/dev/null); then
    echo '{}'
    return 1
  fi

  if ! echo "$result" | jq empty 2>/dev/null; then
    echo '{}'
    return 1
  fi

  echo "$result"
  return 0
}

# End session (abandons unresolved GHAP)
SESSION_RESULT=$(call_mcp "end_session" '{}')

# No output needed
exit 0
```

**Note**: SessionEnd hooks not yet supported by Claude Code. Script is implemented but won't run until Claude Code adds this hook type.

## Configuration Schema

**File**: `.claude/hooks/config.yaml`

```yaml
# Hook configuration for Learning Memory Server
hooks:
  # Session lifecycle
  session_start:
    enabled: true
    script: .claude/hooks/session_start.sh
    timeout_ms: 5000
    inject_light_context: true

  # User prompts
  user_prompt_submit:
    enabled: true
    script: .claude/hooks/user_prompt_submit.sh
    timeout_ms: 500
    context_depth: rich  # light | rich
    token_budget: 2000
    include_code: true
    include_premortem: true

  # Tool lifecycle
  ghap_checkin:
    enabled: true
    script: .claude/hooks/ghap_checkin.sh
    frequency: 10  # Every N tool calls
    timeout_ms: 100

  outcome_capture:
    enabled: true
    script: .claude/hooks/outcome_capture.sh
    timeout_ms: 200
    matchers:
      - "pytest"
      - "npm test"
      - "cargo test"
      - "make test"
      - "make build"
    auto_capture: true

  session_end:
    enabled: false  # Not yet supported by Claude Code
    script: .claude/hooks/session_end.sh
    timeout_ms: 1000

# MCP server settings
mcp:
  server_command: ["python", "-m", "learning_memory_server"]
  connection_timeout: 10
  tool_timeout: 10

# Performance settings
performance:
  max_context_tokens: 2000
  max_premortem_tokens: 1500
  embedding_cache_ttl: 3600  # 1 hour
```

## MCP Tool Extensions

To support hooks, we need to add these MCP tools:

### 1. start_session

```python
@server.call_tool()
async def start_session() -> dict:
    """Start a new session and return session ID."""
    session_id = await observation_collector.start_session()
    return {"session_id": session_id}
```

### 2. get_orphaned_ghap

```python
@server.call_tool()
async def get_orphaned_ghap() -> dict:
    """Get orphaned GHAP from previous session."""
    orphan = await observation_collector.get_orphaned_entry()
    if orphan is None:
        return {"has_orphan": False}
    return {
        "has_orphan": True,
        "goal": orphan.goal,
        "hypothesis": orphan.hypothesis,
        "domain": orphan.domain.value,
        "strategy": orphan.strategy.value,
    }
```

### 3. should_check_in

```python
@server.call_tool()
async def should_check_in(frequency: int = 10) -> dict:
    """Check if GHAP check-in is due."""
    should = await observation_collector.should_check_in(frequency)
    return {"should_check_in": should}
```

### 4. reset_tool_count

```python
@server.call_tool()
async def reset_tool_count() -> dict:
    """Reset tool counter after check-in."""
    await observation_collector.reset_tool_count()
    return {"success": True}
```

### 5. end_session

```python
@server.call_tool()
async def end_session() -> dict:
    """End current session and cleanup."""
    entries = await observation_collector.end_session()
    return {"entries_count": len(entries)}
```

### 6. assemble_context (from SPEC-002-18)

Already defined in ContextAssembler spec. Hooks call this for context injection.


## Hook Output Format

All hooks output JSON to stdout for Claude Code to parse and inject. The format is:

```json
{
  "type": "light|rich|reminder|outcome|premortem",
  "content": "Markdown-formatted text",
  "token_count": 123,  // Optional
  "suggested_action": "resolve_confirmed|resolve_falsified",  // Optional
  "auto_captured": true  // Optional
}
```

**Claude Code Integration**: Claude Code reads the hook's stdout, parses the JSON, and injects `content` as a system message in the conversation. The agent sees this as additional context when generating responses.

**Expected Hook Behavior**:
- Exit code 0 = success (even if hook degrades gracefully)
- Exit code non-zero = hook failure (Claude Code logs error, continues session)
- No stdout = no injection (silent operation)
- Invalid JSON = ignored by Claude Code

## Installation and Setup

### Making Hooks Executable

All hook scripts must be executable. During installation or setup:

```bash
chmod +x .claude/hooks/*.sh
```

**Who runs this**: Installation script or manual setup step in README. Users must ensure hooks are executable before Claude Code can run them.

### Hook Registration

Hooks are registered in Claude Code's configuration. The exact mechanism depends on Claude Code's hook system (not yet fully documented). Expected format:

```yaml
# .claude/hooks/hooks.yaml or Claude Code config
hooks:
  - trigger: SessionStart
    script: .claude/hooks/session_start.sh
    timeout: 5000
  - trigger: UserPromptSubmit
    script: .claude/hooks/user_prompt_submit.sh
    timeout: 500
  - trigger: PreToolCall
    script: .claude/hooks/ghap_checkin.sh
    timeout: 100
  - trigger: PostToolCall
    script: .claude/hooks/outcome_capture.sh
    timeout: 200
```

## Alternative Approaches Considered

### Alternative 1: Direct Python Hooks

**Approach**: Implement hooks directly in Python instead of shell scripts.

**Pros**:
- Cleaner code (no shell scripting)
- Easier error handling
- Better testability

**Cons**:
- Requires Claude Code to support Python hooks (currently shell only)
- Harder to customize for users
- More complex deployment (Python dependencies)

**Decision**: Rejected. Shell scripts are the current Claude Code standard and easier for users to modify.

### Alternative 2: Embedded MCP Client

**Approach**: Embed MCP client logic directly in each hook script (no mcp_client.py).

**Pros**:
- No shared utility file
- Each hook is self-contained

**Cons**:
- Duplicated connection logic across hooks
- Harder to maintain consistency
- Larger file sizes

**Decision**: Rejected. Shared mcp_client.py keeps hooks DRY and maintainable.

### Alternative 3: HTTP-based MCP Connection

**Approach**: Use HTTP transport instead of stdio for MCP communication.

**Pros**:
- Server stays running (no startup latency per hook)
- Connection pooling possible

**Cons**:
- Requires server daemon management
- More complex error handling (connection refused, timeouts)
- Port conflicts

**Decision**: Rejected for v1. Stdio is simpler and matches existing MCP server design. HTTP can be added later if performance demands it.

### Alternative 4: Continuous GHAP Monitoring

**Approach**: Run background process that monitors GHAP state and triggers prompts automatically.

**Pros**:
- More proactive reminders
- Can detect stale GHAP entries

**Cons**:
- Complex process management
- Polling overhead
- Unclear when to prompt (interrupt agent?)

**Decision**: Rejected. Hook-based approach is simpler and less invasive. Agent controls when to engage with GHAP.

## Implementation Plan

### Phase 1: MCP Client Utility (Week 1)
1. Implement mcp_client.py with stdio transport
2. Add connection timeout and retry logic
3. Add structured logging (stderr only)
4. Write unit tests for client connection and tool calls
5. Test with existing MCP server (ping tool)

### Phase 2: Session Hooks (Week 1)
1. Implement session_start.sh
2. Implement session_end.sh (for future)
3. Add MCP tools: start_session, end_session, get_orphaned_ghap
4. Test orphan detection and adoption flow
5. Test light context injection

### Phase 3: Prompt Hook (Week 2)
1. Implement user_prompt_submit.sh
2. Add domain detection logic
3. Test rich context assembly
4. Test premortem injection
5. Verify performance (<500ms)

### Phase 4: Tool Hooks (Week 2)
1. Implement ghap_checkin.sh
2. Add MCP tools: should_check_in, reset_tool_count
3. Test frequency logic with tool counter
4. Implement outcome_capture.sh
5. Add outcome detection matchers (pytest, npm test, etc.)
6. Test auto-capture flow with GHAP resolution

### Phase 5: Configuration and Integration (Week 3)
1. Create config.yaml schema
2. Add configuration loading to hooks
3. Write integration tests for end-to-end flows
4. Document hook behavior and configuration
5. Add performance profiling and optimization

### Phase 6: Polish and Documentation (Week 3)
1. Add error recovery for all failure modes
2. Optimize hook scripts for performance
3. Write user documentation (README.md)
4. Add troubleshooting guide
5. Final integration testing with Claude Code

## Testing Strategy

### Unit Tests

**mcp_client.py**:
```python
@pytest.mark.asyncio
async def test_connect_success(mock_server):
    """Test successful connection to MCP server."""
    client = MCPClient(["mock-server"], timeout=5.0)
    assert await client.connect() is True

@pytest.mark.asyncio
async def test_connect_timeout():
    """Test connection timeout handling."""
    client = MCPClient(["sleep", "100"], timeout=0.1)
    assert await client.connect() is False

@pytest.mark.asyncio
async def test_call_tool_success(mock_server):
    """Test successful tool call."""
    client = MCPClient(["mock-server"], timeout=5.0)
    await client.connect()
    result = await client.call_tool("ping", {})
    assert result == {"message": "pong"}

@pytest.mark.asyncio
async def test_call_tool_timeout(mock_server):
    """Test tool call timeout."""
    client = MCPClient(["mock-server"], timeout=0.1)
    await client.connect()
    result = await client.call_tool("slow_tool", {})
    assert result == {}  # Empty on timeout
```

**Hook Scripts**:
```bash
# Test session_start.sh with mock MCP client
test_session_start_no_orphan() {
  # Mock MCP client to return no orphan
  export MCP_CLIENT="./test/mock_mcp_client.sh"

  result=$(./session_start.sh)

  # Verify output format
  assert_json "$result"
  assert_equals "$(echo "$result" | jq -r .type)" "light"
}

test_session_start_with_orphan() {
  # Mock MCP client to return orphan
  export MCP_CLIENT="./test/mock_mcp_client_with_orphan.sh"

  result=$(./session_start.sh)

  # Verify orphan prompt
  assert_json "$result"
  assert_equals "$(echo "$result" | jq -r .type)" "orphan_detected"
  assert_contains "$(echo "$result" | jq -r .content)" "Orphaned GHAP"
}
```

### Integration Tests

**End-to-End Session Flow**:
```python
@pytest.mark.integration
async def test_full_session_flow(running_mcp_server):
    """Test complete session flow with hooks."""
    # 1. SessionStart hook
    result = subprocess.run(
        ["./session_start.sh"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["type"] == "light"

    # 2. UserPromptSubmit hook
    result = subprocess.run(
        ["./user_prompt_submit.sh"],
        input="Fix the failing auth test",
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["type"] == "rich"
    assert "debugging" in output["content"].lower()

    # 3. GHAP check-in (after 10 tools)
    for i in range(10):
        await observation_collector.increment_tool_count()

    result = subprocess.run(
        ["./ghap_checkin.sh"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["type"] == "reminder"
```

**Outcome Capture Flow**:
```python
@pytest.mark.integration
async def test_outcome_capture_with_ghap():
    """Test outcome capture with active GHAP."""
    # Create active GHAP
    await observation_collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix flaky test",
        hypothesis="Timing issue",
        action="Adding sleep",
        prediction="Test passes consistently"
    )

    # Simulate test failure
    tool_result = json.dumps({
        "tool": "Bash",
        "command": "pytest test_auth.py",
        "exit_code": 1,
        "stdout": "test_auth.py::test_login FAILED"
    })

    result = subprocess.run(
        ["./outcome_capture.sh"],
        input=tool_result,
        capture_output=True,
        text=True
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["type"] == "outcome"
    assert "FAILED" in output["content"]
    assert output["suggested_action"] == "resolve_falsified"
```

### Performance Tests

```python
@pytest.mark.performance
async def test_hook_latency():
    """Verify hooks meet performance targets."""
    # SessionStart: <5s
    start = time.time()
    subprocess.run(["./session_start.sh"], capture_output=True)
    assert time.time() - start < 5.0

    # UserPromptSubmit: <500ms
    start = time.time()
    subprocess.run(
        ["./user_prompt_submit.sh"],
        input="Test prompt",
        capture_output=True
    )
    assert time.time() - start < 0.5

    # GHAP check-in: <100ms
    start = time.time()
    subprocess.run(["./ghap_checkin.sh"], capture_output=True)
    assert time.time() - start < 0.1

    # Outcome capture: <200ms
    start = time.time()
    subprocess.run(
        ["./outcome_capture.sh"],
        input='{"tool": "Bash", "command": "pytest", "exit_code": 0}',
        capture_output=True
    )
    assert time.time() - start < 0.2
```

## Performance Requirements

| Hook | Target (p50) | Max (p95) | Notes |
|------|--------------|-----------|-------|
| session_start | 500ms | 5s | Includes session init + light context |
| user_prompt_submit | 200ms | 500ms | Rich context + optional premortem |
| ghap_checkin | 50ms | 100ms | Local file reads only |
| outcome_capture | 100ms | 200ms | Conditional premortem query |

**Optimization Strategies**:
1. **Parallel MCP calls**: When multiple tools needed, call in parallel
2. **Local-first**: Read from journal files when possible (no MCP call)
3. **Aggressive timeouts**: Fail fast if MCP server is slow
4. **Caching**: Cache embeddings for common phrases (future enhancement)
5. **Lazy loading**: Only query premortem when needed

## Error Handling

### Connection Failures

**Scenario**: MCP server is not running or unreachable.

**Behavior**:
- mcp_client.py returns empty JSON: `{}`
- Hook scripts detect empty result and skip injection
- No error message shown to user (graceful degradation)
- Log warning to stderr for debugging

**Example**:
```bash
# In hook script
RESULT=$(python3 "$MCP_CLIENT" "assemble_context" '{}' 2>/dev/null || echo '{}')
if [ "$RESULT" = "{}" ]; then
  # Server unavailable, exit silently
  exit 0
fi
```

### Tool Call Timeouts

**Scenario**: MCP tool takes too long to respond.

**Behavior**:
- mcp_client.py aborts after timeout (10s default)
- Returns empty result
- Hook continues with degraded output

**Example**:
```python
# In mcp_client.py
try:
    result = await asyncio.wait_for(
        self.session.call_tool(tool_name, arguments),
        timeout=self.timeout
    )
except asyncio.TimeoutError:
    logger.warning("tool_call_timeout", tool=tool_name)
    return {}
```

### Invalid JSON

**Scenario**: MCP server returns malformed JSON.

**Behavior**:
- mcp_client.py catches JSONDecodeError
- Returns empty result
- Logs error to stderr

**Example**:
```python
try:
    return json.loads(result.content[0].text)
except json.JSONDecodeError:
    logger.error("invalid_json_from_tool", tool=tool_name)
    return {}
```

### Missing Configuration

**Scenario**: config.yaml doesn't exist or is malformed.

**Behavior**:
- Hooks use sensible defaults (hardcoded)
- Log warning about missing config
- Continue with default behavior

**Example**:
```bash
# In hook script
if [ ! -f "$CONFIG_FILE" ]; then
  FREQUENCY=10  # Default
else
  FREQUENCY=$(yq '.hooks.ghap_checkin.frequency // 10' "$CONFIG_FILE")
fi
```

## Acceptance Criteria

### Functional Requirements

1. All 5 hook scripts implemented and executable
2. mcp_client.py connects to MCP server via stdio
3. session_start.sh injects light context on first prompt
4. session_start.sh detects and prompts for orphaned GHAP
5. user_prompt_submit.sh injects rich context based on prompt
6. ghap_checkin.sh triggers every N tool calls (configurable)
7. outcome_capture.sh detects test/build outcomes from tool results
8. outcome_capture.sh prompts for GHAP resolution on outcomes
9. Hooks output valid JSON for Claude Code to parse
10. Configuration loaded from config.yaml
11. Hooks degrade gracefully when MCP server unavailable

### Quality Requirements

1. All hooks meet performance targets (p95 latency)
2. **Type hints for all Python code (mypy --strict compliance)**
3. Docstrings for all classes and methods
4. Structured logging via structlog (stderr only)
5. **Shell scripts use `set -uo pipefail` with explicit error handling**
6. Error messages are clear and actionable
7. No sensitive data logged or exposed
8. **Dependencies documented: jq, Python 3.10+, PyYAML**

### Testing Requirements

1. Unit test coverage ≥ 90% for mcp_client.py
2. Integration tests for all end-to-end flows
3. Performance tests verify latency targets
4. Shell script tests use bats or shunit2
5. All error cases tested (connection failure, timeout, invalid JSON)
6. Type checking passes (mypy --strict)
7. Linting passes (ruff, shellcheck)

### Documentation Requirements

1. README.md explains hook behavior and configuration
2. config.yaml has inline comments for all options
3. Troubleshooting guide for common issues
4. Examples of hook output for each type
5. Architecture diagram showing hook flow

## Out of Scope

- Custom user-defined hooks (v1 uses predefined hooks only)
- Hook chaining (one hook calling another)
- Conditional hooks based on project type
- Advanced pattern matching for outcome detection (regex, glob)
- Hook state sharing (hooks are independent)
- Web-based configuration UI
- Hook telemetry dashboard
- **Domain-specific premortem warnings** (deferred to v2)
- **Keyword-based domain detection** (deferred to v2)

## Future Enhancements

### Phase 2 Enhancements

1. **SessionEnd hook support**: When Claude Code adds this hook type, activate session_end.sh
2. **HTTP-based MCP transport**: Keep server running for reduced startup latency
3. **Embedding cache**: Cache embeddings for common phrases to speed up context assembly
4. **Conditional hooks**: Enable/disable hooks based on file types or project markers
5. **Hook telemetry**: Track hook latency, cache hit rates, and usage patterns

### Phase 3 Enhancements

1. **Domain-specific premortem warnings**: Keyword-based domain detection and targeted premortem context
2. **Multi-language domain detection**: Support non-English prompts
3. **Advanced outcome matchers**: Regex and glob patterns for custom tools
4. **Richer premortem context**: Include file history, churn analysis, and blame data
5. **Hook composition**: Allow hooks to call other hooks or share state
6. **User-configurable hooks**: Let users write custom hook scripts

## Notes

- All hook scripts must be executable (`chmod +x`)
- All Python async operations use `await` consistently
- All timestamps are ISO 8601 format (UTC)
- Hook output is JSON only (no plain text)
- Hooks never block agent workflow (graceful degradation)
- MCP client logs to stderr (stdout is for JSON output)
- Configuration changes require hook restart (no hot reload in v1)
- Orphan detection runs once at session start only
- Domain-specific premortem is deferred to v2 for simplicity
