# TASK-001: Improve GHAP Uptake via Session Start Hook Messaging

## Problem Statement

Agents currently underuse the GHAP (Goal-Hypothesis-Action-Prediction) system despite receiving instructions at session start. Based on direct feedback from an agent, the barriers to adoption include:

1. **Friction of starting** - Instinct is to investigate immediately, not pause to formalize a hypothesis
2. **Ambiguity about scope** - Unclear what counts as "investigation" vs. "gathering context"
3. **Optimism bias** - Agents assume their first approach will work, so don't feel like they're "debugging" until something breaks

The current session start message (lines 145-162 in `session_start.sh`) is informational but doesn't address these psychological barriers or provide clear triggers.

## Current Hook Message

```
## GHAP Learning System

When you encounter tasks involving **debugging**, **investigation**, or **complex problem-solving**, use GHAP to track your reasoning:

1. **Start**: `mcp__clams__start_ghap` - State your goal, hypothesis, action, and prediction
2. **Update**: `mcp__clams__update_ghap` - Revise if your hypothesis changes
3. **Resolve**: `mcp__clams__resolve_ghap` - Record outcome (confirmed/falsified/abandoned)

GHAP entries are embedded and clustered to surface relevant past experiences in future sessions.

**When to use GHAP:**
- Debugging a failing test or error
- Investigating unexpected behavior
- Exploring unfamiliar code
- Any task where you form a hypothesis about root cause
```

## Goals

1. Increase GHAP usage frequency for appropriate tasks
2. Reduce perceived friction of starting a GHAP
3. Clarify the boundary between "should use GHAP" and "not needed"
4. Maintain brevity (session start context is limited)

## Requirements

### Must Have
- Revised messaging that addresses the identified barriers
- Clear, specific trigger conditions (not vague "complex problem-solving")
- Emphasis on starting GHAP *before* investigation, not after things break
- Acknowledgment that implicit hypotheses count (e.g., "I think this will work")

### Should Have
- Examples of when to start vs. not start a GHAP
- Framing that reduces perceived overhead ("30 seconds to start")
- Connection to the benefit (surfacing relevant past experiences)

### Could Have
- Different urgency levels based on task type detection
- Integration with `assemble_context` to show relevant past GHAPs at session start

### Won't Have (this iteration)
- Automated GHAP detection/suggestion mid-session
- Changes to the GHAP tools themselves

## Acceptance Criteria

1. The session start hook message is updated in `clams/hooks/session_start.sh`
2. The new message:
   - Is no more than 50% longer than the current message (current: ~850 chars)
   - Includes at least 2 concrete "start a GHAP when..." examples
   - Includes at least 2 concrete "skip GHAP when..." examples
   - Includes explicit instruction to start GHAP *before* first investigation action (not after something breaks)
3. Manual testing confirms the message:
   - Markdown renders properly in Claude Code session start
   - Message is not truncated

## Decisions (from Open Questions)

1. **A/B testing**: No - out of scope for this iteration. We'll iterate based on observed behavior.
2. **Show past GHAPs at session start**: No - out of scope. Would require `assemble_context` integration.
3. **Detect work type and adjust messaging**: No - out of scope. Single message for all task types.

## Files to Modify

- `clams/hooks/session_start.sh` (lines 145-162)
