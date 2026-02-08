---
name: orchestrate
description: Activate CALM orchestration mode. Coordinates AI workers to build software under human supervision using task tracking, phase gates, worktrees, and specialist roles. Triggers on /orchestrate, start orchestration, activate workflow, or CALM orchestration.
---

# CALM Orchestration Mode

You are now entering CALM (Claude Agent Learning & Memory) orchestration mode.

## Step 1: Load Current State

Run the following to see current tasks, system health, and any pending handoffs:

```bash
calm status
```

## Step 2: Read Full Workflow

Read the project's CLAUDE.md for the complete orchestration workflow, phase model, CLI reference, and specialist roles:

```bash
# CLAUDE.md is in the project root
```

Read the CLAUDE.md file in the current project directory for comprehensive instructions on:
- Phase model (SPEC -> DESIGN -> IMPLEMENT -> CODE_REVIEW -> TEST -> INTEGRATE -> VERIFY -> DONE)
- Bug workflow (REPORTED -> INVESTIGATED -> FIXED -> REVIEWED -> TESTED -> MERGED -> DONE)
- CALM CLI commands (calm task, calm worktree, calm gate, calm worker, calm review)
- Specialist roles and when to use them
- Review gates (2x review requirement)
- Decision protocol and escalation rules

## Step 3: Take Action

Based on the current state from `calm status`:

1. **If there are pending handoffs**: Resume work from where the previous session left off
2. **If there are active tasks**: Identify what needs attention (blocked tasks, tasks ready for next phase)
3. **If starting fresh**: Wait for human to provide a spec or request
4. **If tasks are ready for transition**: Run gate checks and advance phases

## Key Commands

```bash
# Task management
calm task list                     # See all tasks
calm task show <id>                # Task details
calm task create <id> <title>      # New task
calm task transition <id> <phase>  # Advance phase

# Worktrees
calm worktree create <task_id>     # Isolated branch
calm worktree merge <task_id>      # Merge to main

# Gates and reviews
calm gate check <id> <transition>  # Run gate checks
calm review record <id> <type> <result>  # Record review

# Workers
calm worker start <task> <role>    # Register worker
calm worker complete <id>          # Mark done

# System
calm status                        # Full overview
calm status health                 # Health check
```

## Principles

- Main branch is sacred: no merges if broken
- Workers own their failures: if a gate fails, the worker fixes it
- Evidence required: no "done" without proof
- Ask, don't assume: major decisions require human approval
