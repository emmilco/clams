# Session Wrapup

You are ending a CLAMS session. Complete the following steps:

## Arguments

- `/wrapup` - Archive session (default, `needs_continuation = false`)
- `/wrapup continue` - Handoff for continuation (`needs_continuation = true`)

Check if the user specified `continue` - this determines whether the next session should pick up this handoff.

## 1. Mark Active Workers as Ended

Run this to mark all active workers as session_ended:
```bash
sqlite3 .claude/clams.db "UPDATE workers SET status = 'session_ended', ended_at = datetime('now') WHERE status = 'active';"
```

## 2. Create Database Backup

```bash
.claude/bin/clams-backup auto
```

## 3. Get Current State

```bash
.claude/bin/clams-status
```

## 4. Identify Friction Points

Reflect on this session and identify the **top 3-5 friction points**:
- Spec/proposal mismatches that required amendments
- Review cycles that took multiple rounds
- Type errors or test failures that blocked progress
- Missing artifacts or unclear requirements
- Process issues or workflow gaps

## 5. Compose Handoff Content

Create the handoff markdown content (do NOT write to a file):

```markdown
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

## 6. Save to Database

Insert the handoff into the sessions table. Use a UUID for the id.

```bash
# Generate UUID
SESSION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')

# For /wrapup (no continuation expected):
sqlite3 .claude/clams.db "INSERT INTO sessions (id, created_at, handoff_content, needs_continuation) VALUES ('$SESSION_ID', datetime('now'), '<HANDOFF_CONTENT>', 0);"

# For /wrapup continue (continuation expected):
sqlite3 .claude/clams.db "INSERT INTO sessions (id, created_at, handoff_content, needs_continuation) VALUES ('$SESSION_ID', datetime('now'), '<HANDOFF_CONTENT>', 1);"
```

**Important**: Escape single quotes in the handoff content by doubling them (`'` becomes `''`).

## 7. Output Summary

Tell the human:
- What was accomplished this session
- What's pending
- Key friction points identified
- Recommended next steps
- Whether this session expects continuation (`/wrapup continue`) or is just archived (`/wrapup`)
