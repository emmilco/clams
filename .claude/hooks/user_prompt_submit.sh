#!/bin/bash
# .claude/hooks/user_prompt_submit.sh
# Hook: UserPromptSubmit
# Purpose: Analyze prompt and inject rich context (v1: no domain detection)

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
# v1: No domain detection, just call assemble_context with the prompt
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
