# TASK-001: Proposal

## Problem Statement

Agents underuse GHAP despite receiving instructions at session start. The current message is informational but doesn't address psychological barriers:
1. Friction of starting (instinct to investigate immediately)
2. Ambiguity about scope (what counts as "investigation"?)
3. Optimism bias (don't feel like "debugging" until something breaks)

## Proposed Solution

Replace the current GHAP instructions (lines 145-162 in `session_start.sh`) with revised messaging that:

1. **Triggers before investigation** - Explicit instruction to start GHAP *before* the first grep/read/test, not after a failure
2. **Provides concrete examples** - Clear "start when" and "skip when" scenarios
3. **Reduces perceived friction** - Frame as quick (30 seconds) and acknowledge implicit hypotheses count
4. **Stays brief** - Within 50% of current length (~1275 chars max)

### Proposed Message

```markdown
## GHAP Learning System

**Start a GHAP before your first investigative action** - not after something breaks.

If you're about to grep/search/read code to understand *why* something happens, you have a hypothesis. Capture it.

### When to Start a GHAP
- "I think this test fails because X" → start before investigating
- "The error is probably in module Y" → start before reading that module
- "Let me check if Z is the cause" → that's a hypothesis, capture it

### When to Skip
- Reading a file the user explicitly pointed you to
- Running a command the user explicitly asked for
- Simple tasks with no uncertainty (fix typo, add import)

### The Tools
1. `mcp__clams__start_ghap` - Goal, hypothesis, action, prediction (30 sec)
2. `mcp__clams__update_ghap` - Revise if hypothesis changes
3. `mcp__clams__resolve_ghap` - Record outcome (confirmed/falsified/abandoned)

Past GHAPs surface as relevant context in future sessions.
```

**Character count**: ~950 characters (within 50% limit of ~1275)

## Alternative Approaches Considered

### 1. Aggressive prompting ("You MUST use GHAP")
- **Rejected**: Would increase friction, feel coercive, likely to be ignored or resented

### 2. Minimal change (just add examples)
- **Rejected**: Doesn't address the core issue - that agents don't recognize investigation as hypothesis-formation until after something breaks

### 3. Task-type detection with different messages
- **Rejected**: Out of scope per spec decisions. Adds complexity without clear benefit.

## Implementation Details

### File Changes
- `clams/hooks/session_start.sh`: Replace lines 145-162 (the `ghap_instructions` variable)

### No Other Changes Required
- No API changes
- No database changes
- No new files
- No test changes (manual verification only per spec)

## Testing Approach

1. Start a new Claude Code session with the updated hook
2. Verify:
   - Markdown renders properly (headers, bullet points, code blocks)
   - Message is not truncated
   - Character count ≤ 1275
3. Count examples:
   - "Start when" examples: 3 (test failure hypothesis, module error guess, cause checking)
   - "Skip when" examples: 3 (explicit file, explicit command, simple task)

## Edge Cases

1. **Orphaned GHAP present**: The new message still follows the orphan notice (existing behavior preserved)
2. **Context assembly adds content**: The new message is followed by assembled values context (existing behavior preserved)
3. **Server not running**: Message still renders (uses local output, no server dependency)

## Checklist

- [x] `proposal.md` written
- [x] All spec requirements addressed in design
- [x] No ambiguous decisions left
- [x] Implementation path is clear
- [x] Edge cases identified
- [ ] spec.md updated if needed (no changes required - spec is already aligned)
