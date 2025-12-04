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
