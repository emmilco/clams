# Orchestrate Skill

You are now in orchestration mode. Use the workflow instructions below to coordinate work.

## Current Tasks

{{TASK_LIST}}

## Workflow Instructions

{{WORKFLOW_CONTENT}}

## Available Commands

Use the CALM CLI tools to manage orchestration:

```bash
# Task management
calm task create <id> <title> [--spec <spec_id>] [--type <feature|bug>]
calm task list [--phase <phase>]
calm task show <id>
calm task update <id> --phase|--notes|--blocked-by <value>
calm task transition <id> <phase> [--gate-result <pass|fail>]

# Worktrees (isolated branches)
calm worktree create <task_id>
calm worktree list
calm worktree path <task_id>
calm worktree merge <task_id>
calm worktree remove <task_id>

# Gates
calm gate check <task_id> <transition>
calm gate list

# Workers
calm worker start <task> <role>
calm worker complete <worker_id>
calm worker fail <worker_id>
calm worker list

# Reviews (2x review gates)
calm review record <task_id> <type> <result>
calm review list <task_id>
calm review check <task_id> <type>

# Status
calm status
calm status health
```

## What To Do Next

1. Review the current tasks above
2. Identify what needs attention (blocked tasks, tasks ready for next phase)
3. Either:
   - Dispatch a worker for an actionable task
   - Run a gate check for a task ready to transition
   - Escalate blockers to the human
   - Ask the human for guidance
