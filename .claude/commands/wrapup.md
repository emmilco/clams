# Session Wrapup

You are ending a CLAMS session. Complete the following steps:

## Arguments

- `/wrapup` - Archive session (default, `needs_continuation = false`)
- `/wrapup continue` - Handoff for continuation (`needs_continuation = true`)

Check if the user specified `continue` - this determines whether the next session should pick this up.

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

## 5. Save Handoff to Database

Use `clams-session save` to store the handoff. This command reads from stdin and handles encoding automatically.

**For `/wrapup` (no continuation expected):**
```bash
cat <<'EOF' | .claude/bin/clams-session save
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
EOF
```

**For `/wrapup continue` (continuation expected):**
```bash
cat <<'EOF' | .claude/bin/clams-session save --continue
# Session Handoff - [DATE]
...
EOF
```

**IMPORTANT**: Use the `'EOF'` marker (with quotes) to prevent shell expansion. Replace the content between `cat <<'EOF'` and `EOF` with your actual handoff content.

## 6. Output Summary

Tell the human:
- What was accomplished this session
- What's pending
- Key friction points identified
- Recommended next steps
- Whether this session expects continuation (`/wrapup continue`) or is just archived (`/wrapup`)
