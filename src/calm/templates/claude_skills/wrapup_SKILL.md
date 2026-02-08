---
name: wrapup
description: End a CALM session with proper handoff. Archives session state, saves friction points, and creates continuation notes for the next session. Use /wrapup to archive or /wrapup continue for continuation handoff.
---

# Session Wrapup

You are ending a CALM session. Complete the following steps.

## Arguments

- `/wrapup` - Archive session (default, no continuation expected)
- `/wrapup continue` - Handoff for continuation (next session should pick this up)

Check if the user specified `continue` - this determines whether the next session should pick this up.

## 1. Check Current State

```bash
calm status
```

Review what tasks are in progress and their current phases.

## 2. Identify Friction Points

Reflect on this session and identify the **top 3-5 friction points**:
- Spec/proposal mismatches that required amendments
- Review cycles that took multiple rounds
- Type errors or test failures that blocked progress
- Missing artifacts or unclear requirements
- Process issues or workflow gaps

## 3. Create Session Summary

Write a handoff that includes:

```
# Session Handoff - [DATE]

## Session Summary
Brief description of what was accomplished.

## Active Tasks
For each task not in DONE:
- TASK-XXX: [phase] - [current status / next step needed]

## Blocked Items
- Any tasks blocked and why

## Friction Points This Session
1. [Issue] - [How it was resolved or what needs to change]
2. [Issue] - [Resolution/recommendation]
3. ...

## Recommendations for Next Session
- Process improvements to consider
- Workflow adjustments needed
- Technical debt to address

## Next Steps
1. [Immediate priority]
2. [Secondary priority]
3. ...
```

## 4. Save Session

```bash
# For /wrapup (no continuation expected)
calm session save

# For /wrapup continue (continuation expected)
calm session save --continue
```

## 5. Output Summary

Tell the human:
- What was accomplished this session
- What's pending
- Key friction points identified
- Recommended next steps
- Whether this session expects continuation
