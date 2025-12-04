# SPEC-002-19: Hook Scripts and Context Injection

## Overview

Implement Claude Code hook scripts that integrate the Learning Memory Server with agent sessions. Hooks run at specific conversation lifecycle points (session start, user prompt, tool calls) to inject context, check GHAP state, and auto-capture outcomes.

This creates the "magic" layer where the memory system becomes automatically engaged without requiring explicit agent calls to MCP tools.

## Goals

1. Inject relevant context automatically based on user prompts
2. Periodically remind agent to update GHAP state
3. Auto-capture test/build outcomes and prompt for GHAP resolution
4. Manage session lifecycle (start/end)
5. Keep hooks fast (<100ms typically, <500ms worst case)
6. Provide clear configuration for hook behavior

## Hook Types and Implementation

Claude Code supports these hook types:

| Hook | When It Runs | Input | Output |
|------|--------------|-------|--------|
| SessionStart | First user prompt in session | Session metadata | Context to inject |
| UserPromptSubmit | User submits a prompt | User prompt text | Additional context |
| PreToolCall | Before tool executes | Tool name, args | Warning/context |
| PostToolCall | After tool completes | Tool name, result | GHAP prompts |
| SessionEnd | Session terminates | Session metadata | Cleanup actions |

### Hook 1: SessionStart

**Purpose**: Initialize session state and inject standing context.

**Location**: `.claude/hooks/session_start.sh`

**Behavior**:
1. Call ObservationCollector's `start_session()` via MCP
2. Check for orphaned GHAP from previous session
3. If orphan exists, prompt agent:
   ```
   Orphaned GHAP detected from previous session:
   Goal: {goal}
   Hypothesis: {hypothesis}

   Options:
   - Adopt and continue this work
   - Abandon with reason
   ```
4. Inject light context via ContextAssembler:
   ```python
   assemble_context(
       query="",  # No query at session start
       context_types=["values"],  # Just top values
       limit=5,
       max_tokens=500,
   )
   ```
5. Output injected context to stdout (Claude Code will prepend it)

**Configuration**:
```yaml
hooks:
  SessionStart:
    - command: .claude/hooks/session_start.sh
      timeout: 5000
      once: true  # Only run once per session
```

### Hook 2: UserPromptSubmit

**Purpose**: Analyze user intent and inject relevant context.

**Location**: `.claude/hooks/user_prompt_submit.sh`

**Behavior**:
1. Receive user prompt via stdin as JSON:
   ```json
   {
     "prompt": "Fix the failing auth test",
     "context": {
       "cwd": "/path/to/project",
       "files": ["test_auth.py"]
     }
   }
   ```
2. Call ContextAssembler with rich parameters:
   ```python
   assemble_context(
       query=user_prompt,
       context_types=["experiences", "values", "code"],
       limit=20,
       max_tokens=2000,
   )
   ```
3. Output context JSON:
   ```json
   {
     "context": "Relevant past experiences:\n..."
   }
   ```

**Configuration**:
```yaml
hooks:
  UserPromptSubmit:
    - command: .claude/hooks/user_prompt_submit.sh
      timeout: 500
      enabled: true
```

### Hook 3: PreToolCall (GHAP Check-in)

**Purpose**: Remind agent to update GHAP state periodically.

**Location**: `.claude/hooks/ghap_checkin.sh`

**Behavior**:
1. Check tool count via ObservationCollector's `should_check_in(frequency=10)`
2. If not time for check-in, exit immediately (no output)
3. If check-in due:
   - Get current GHAP state
   - Reset tool counter
   - Output reminder:
     ```
     GHAP Check-in (10 tools since last update):

     Current Goal: {goal}
     Current Hypothesis: {hypothesis}
     Current Prediction: {prediction}

     Is your hypothesis still valid? If it changed, update your GHAP entry.
     ```

**Configuration**:
```yaml
hooks:
  PreToolCall:
    - matcher: "*"  # All tools
      command: .claude/hooks/ghap_checkin.sh
      timeout: 100
      frequency: 10  # Every 10 tool calls
```

### Hook 4: PostToolCall (Outcome Capture)

**Purpose**: Auto-capture test/build results and prompt for GHAP resolution.

**Location**: `.claude/hooks/outcome_capture.sh`

**Behavior**:
1. Receive tool result via stdin:
   ```json
   {
     "tool": "Bash",
     "command": "pytest test_auth.py",
     "exit_code": 0,
     "stdout": "test_auth.py::test_login PASSED",
     "stderr": ""
   }
   ```
2. Detect outcome-triggering tools:
   - `pytest`, `npm test`, `cargo test`, `make test` → test results
   - `make build`, `npm build`, `cargo build` → build results
3. Parse exit code and output to determine success/failure
4. Get current GHAP state
5. **If failure and NO active GHAP**:
   - Inject premortem context (once per GHAP cycle)
   - Prompt agent to start tracking with GHAP
   ```json
   {
     "type": "premortem",
     "content": "Test FAILED.\n\n## Premortem: What went wrong before in debugging\n...",
     "prompt": "Consider starting a GHAP to track your debugging approach."
   }
   ```
6. **If GHAP active**, compare prediction to actual outcome:
   - Match → prompt for confirmation
   - Mismatch → prompt for falsification
   ```json
   {
     "type": "outcome",
     "prompt": "Test PASSED. Your prediction was: 'Test will pass after fixing isolation'.\n\nDoes this confirm your hypothesis? If yes, resolve GHAP as CONFIRMED.",
     "suggested_action": "resolve_confirmed"
   }
   ```

**Premortem injection**: Only injected once when failure occurs with no active GHAP. Once agent starts a GHAP, they're engaged and don't need repeated premortem prompts. This avoids noise on retry failures.

**Auto-capture flag**: When prompting resolution, include `auto_captured=true` to mark as gold-tier confidence.

**Configuration**:
```yaml
hooks:
  PostToolCall:
    - matcher: "Bash(pytest|npm test|cargo test|make test|make build)"
      command: .claude/hooks/outcome_capture.sh
      timeout: 200
      auto_capture: true
```

### Hook 5: SessionEnd (Future)

**Purpose**: Persist unresolved GHAP entries and cleanup.

**Location**: `.claude/hooks/session_end.sh`

**Behavior**:
1. Call ObservationCollector's `end_session()`
2. If unresolved GHAP exists, abandon with reason "session ended"
3. Trigger ObservationPersister to batch-persist resolved entries
4. Log session summary

**Note**: SessionEnd hooks are not yet supported by Claude Code. Implement the script but document that it won't run until Claude Code adds this hook type.

## Context Injection Format

Hooks output JSON to stdout. Claude Code parses this and injects content into the conversation.

### Light Context (SessionStart)

```json
{
  "type": "light",
  "content": "## Session Context\n\nTop Values:\n- Flaky tests are often isolation issues, not timing issues\n- Check assumptions before implementing\n\nRecent Work:\n- Fixed auth timeout bug (2 hours ago)\n- Refactored cache module (yesterday)"
}
```

### Rich Context (UserPromptSubmit)

```json
{
  "type": "rich",
  "content": "## Relevant Context\n\n### Similar Past Experience\nGoal: Fix auth test timeout\nLesson: Increasing timeout didn't work, root cause was test isolation\n\n### Relevant Values\n- Always verify assumptions before implementing\n- Check test isolation when debugging flaky tests",
  "token_count": 385
}
```

### GHAP Check-in (PreToolCall)

```json
{
  "type": "reminder",
  "content": "GHAP Check-in: Has your hypothesis changed?\n\nCurrent: 'Timeout is caused by slow network'\nCurrent Prediction: 'Increasing timeout to 60s will fix it'\n\nIf your understanding evolved, update your GHAP."
}
```

### Outcome Prompt (PostToolCall)

```json
{
  "type": "outcome",
  "content": "Test FAILED. Your prediction: 'Test will pass after timeout increase'.\n\nActual: Test still fails with timeout.\n\nThis falsifies your hypothesis. Please:\n1. What surprised you?\n2. What was the root cause?\n3. What did you learn?",
  "auto_captured": true
}
```

## Configuration Schema

Hooks are configured in `.claude/hooks/config.yaml`:

```yaml
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
```

## Integration with ContextAssembler

Hooks call ContextAssembler via MCP tools:

```python
# In hook script (pseudocode)
user_prompt = sys.stdin.read()

# Call MCP tool for rich context
context = mcp_call("assemble_context", {
    "query": user_prompt,
    "context_types": ["experiences", "values", "code"],
    "limit": 20,
    "max_tokens": 2000
})

# Output for injection
print(json.dumps({
    "type": "rich",
    "content": context["markdown"],
    "token_count": context["token_count"]
}))
```

ContextAssembler's `assemble_context()` returns:
- Semantically similar experiences (via Searcher)
- Relevant values
- Relevant code snippets (if requested)

## Performance Requirements

| Hook | Target | Max |
|------|--------|-----|
| SessionStart | 500ms | 5s |
| UserPromptSubmit | 200ms | 500ms |
| PreToolCall | 50ms | 100ms |
| PostToolCall | 100ms | 200ms |

**Strategies for speed**:
- Cache embeddings for common phrases
- Limit search results (top 5 by default)
- Skip hooks if no GHAP active (for check-in)
- Use async I/O throughout
- Profile and optimize hot paths

## Error Handling

Hooks must be resilient:

1. **MCP server down**: Skip injection, log warning, continue session
2. **Timeout**: Kill hook subprocess, log error, continue
3. **Invalid JSON output**: Ignore output, log error, continue
4. **Embedding service slow**: Use cached or skip, don't block

**Principle**: Hook failures should never break the agent session. Degraded operation is acceptable.

## Testing Strategy

### Unit Tests

1. **Hook script parsing**: Test stdin JSON → behavior logic
2. **Context formatting**: Test output JSON structure
3. **Pattern matching**: Test tool name matchers
4. **Frequency logic**: Test check-in counter logic

### Integration Tests

1. **End-to-end hook flow**: Mock Claude Code, trigger hooks, verify injection
2. **MCP tool calls**: Verify hooks call correct MCP tools with correct args
3. **Performance**: Measure hook latency under load
4. **Failure recovery**: Test behavior when MCP server is down

### Test Fixtures

```python
@pytest.fixture
def mock_claude_code():
    """Mock Claude Code hook environment (stdin, env vars)."""
    pass

@pytest.fixture
def active_ghap():
    """Create active GHAP state for testing."""
    pass

@pytest.fixture
def test_tool_result():
    """Mock tool result from PostToolCall hook."""
    pass
```

## Dependencies

- **ObservationCollector** (SPEC-002-08): Session and GHAP state management
- **ContextAssembler** (SPEC-002-18): Context retrieval and formatting
- **Searcher** (SPEC-002-09): Semantic search for experiences
- **MCP Server** (SPEC-002-05): Tool interface for calling memory operations
- **Claude Code**: Hook infrastructure (reads config, runs scripts)

## Implementation Notes

### Hook Scripts in Bash

Hooks are shell scripts for simplicity and performance. They:
- Read JSON from stdin
- Call Python MCP client to invoke tools
- Output JSON to stdout
- Must be executable (`chmod +x`)

### MCP Client Utility

Provide a Python utility for hooks to call MCP tools:

```bash
# In hook script
result=$(python .claude/hooks/mcp_client.py get_context '{
  "situation": "Fix auth test",
  "depth": "rich"
}')
```

The `mcp_client.py` script:
- Connects to MCP server via stdio or HTTP
- Invokes named tool with JSON args
- Returns JSON result
- Handles connection failures gracefully

### State Persistence

Hooks are stateless. All state lives in:
- `.claude/journal/` (ObservationCollector's local files)
- Vector store (experiences, values)
- Claude Code's internal state (tool count, session ID)

## Acceptance Criteria

1. All 5 hook scripts implemented and executable
2. SessionStart injects light context on first prompt
3. UserPromptSubmit analyzes prompt and injects rich context
4. PreToolCall reminds agent every N tool calls (configurable)
5. PostToolCall detects test/build results and prompts resolution
6. Hooks output valid JSON for Claude Code to parse
7. Configuration schema supports all hook settings
8. Hooks meet performance targets (p95 latency)
9. Hooks degrade gracefully when MCP server unavailable
10. Integration tests verify end-to-end flow
11. Documentation explains hook behavior and configuration

## Out of Scope

- Custom user-defined hooks (v1 uses predefined hooks only)
- Hook chaining (one hook calling another)
- Conditional hook execution based on project type
- Advanced pattern matching (regex, glob patterns)
- Hook state sharing (hooks are independent)
- Web-based hook configuration UI
- **Domain-specific premortem warnings** (deferred to v2)

## Future Enhancements

- SessionEnd hook when Claude Code supports it
- Conditional hooks based on file types (e.g., only Python projects)
- Hook telemetry (latency, cache hit rates)
- User-configurable hook scripts
- **Domain-specific premortem logic** with keyword detection (file history, churn analysis)

## Example Session Flow

```
[Session starts]
→ SessionStart hook runs
  - Starts session: session_20251203_140000_abc123
  - No orphan detected
  - Injects light context (top values, recent work)

[User: "Fix the flaky cache test"]
→ UserPromptSubmit hook runs
  - Calls assemble_context("Fix the flaky cache test")
  - Finds similar past experience: "Flaky tests are isolation issues"
  - Injects context

[Agent creates GHAP, works, calls tools...]

[After 10 tool calls]
→ PreToolCall hook runs
  - Checks: should_check_in(10) → True
  - Injects GHAP check-in reminder
  - Agent reviews, updates hypothesis

[Agent runs: pytest test_cache.py → FAILED]
→ PostToolCall hook runs
  - Detects test failure
  - Compares to prediction: "Test will pass after timeout fix"
  - Injects outcome prompt: "Test FAILED. Falsified. Why?"
  - Agent annotates surprise, root cause, lesson

[Agent resolves GHAP as FALSIFIED]
→ ObservationPersister embeds and stores entry
→ Entry becomes searchable for future sessions
```

## Notes

- Hooks are optional. System works without them, but less automatically.
- Hook latency impacts user experience. Keep fast.
- Context injection can be verbose. Respect token budgets.
- Auto-capture is powerful but must be accurate. Test thoroughly.
- Hooks enable the "learning loop" to close automatically.
