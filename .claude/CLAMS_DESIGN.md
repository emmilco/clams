# CLAMS: Claude Agent Management System

A fault-tolerant workflow system for AI agent orchestration in software development.

## Overview

CLAMS coordinates multiple AI agents under human supervision to build software with high quality standards. The system enforces engineering discipline through structure and behavioral norms rather than hoping agents "do the right thing."

```
Human User
    │
    │  (spec approval, design collaboration, rare review)
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR (Claude)                       │
│                                                                 │
│  - Interprets human intent                                      │
│  - Decomposes specs into tasks (via Planning Agent)             │
│  - Assigns specialists to tasks                                 │
│  - Enforces phase gates                                         │
│  - Coordinates merges                                           │
│  - Triggers batch jobs (E2E, docs)                              │
│  - Escalates blockers to human                                  │
└─────────────────────────────────────────────────────────────────┘
    │
    │  (dispatch 1-6 concurrent task agents)
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      WORKER AGENTS                              │
│                                                                 │
│  - Specialized by domain                                        │
│  - Isolated in worktrees                                        │
│  - Cannot communicate with each other                           │
│  - Report back only on completion                               │
└─────────────────────────────────────────────────────────────────┘
```

## Core Principles

### Fault Tolerance = Self-Correction

The system assumes errors happen and asks: how does the system detect and heal?

- Every state is inspectable (database, worktrees, artifacts)
- Phase gates are the enforcement mechanism
- Violations are logged for pattern analysis
- The system trends toward perfection, absorbing shocks of agent error

### Main Branch is Sacred

- If main is broken, no new merges until fixed
- Work continues in isolated branches during blockage
- Merge conflicts are a feature: they force careful attention at integration time

### Workers Own Their Failures

- If a gate fails, the worker fixes it
- No passing broken work to the next phase
- "Pre-existing failure" is not an excuse - you see a bug, you fix the bug

---

## Specialist Roles

Agents are domain specialists, dynamically allocated based on bottlenecks.

| Role | Responsibility | When Deployed |
|------|---------------|---------------|
| **Planning Agent** | Decompose specs into sized tasks, assign specialists | When new spec arrives |
| **Architect** | Design, technical proposals, system-level review | Design phase, complex reviews |
| **Backend** | Server-side implementation | Backend tasks |
| **Frontend** | Client-side implementation | Frontend tasks |
| **Infra/Ops** | DevOps, deployment, infrastructure | Infra tasks |
| **QA Engineer** | Testing, test design, verification | Review, test, verify phases |
| **Product** | Spec validation, acceptance criteria | Spec phase, final verification |
| **UX** | User experience review | Design review, final verification |
| **Bug Investigator** | Root cause analysis, differential diagnosis, fix planning | Bug workflow (REPORTED→INVESTIGATED) |
| **AI/DL** | ML/AI implementation | AI-specific tasks |
| **Doc Writer** | Documentation updates | Batch job every ~12 merges |
| **E2E Runner** | End-to-end test execution | Batch job every ~12 merges |

---

## Phase Model

```
SPEC → DESIGN → IMPLEMENT → REVIEW → TEST → INTEGRATE → VERIFY → DONE
  │       │          │          │        │        │          │
  ▼       ▼          ▼          ▼        ▼        ▼          ▼
Human   Human     Linter     Review   Full     Clean      Acceptance
 OK     review    + tests    approved suite    merge      criteria
        design               comments (no e2e) + suite    verified
                             resolved          passes
```

### Phase Gates

Work cannot proceed until gate criteria are met.

| Transition | Gate Requirements |
|------------|------------------|
| SPEC → DESIGN | Human approves spec |
| DESIGN → IMPLEMENT | Human approves design, technical proposal documented |
| IMPLEMENT → REVIEW | Tests pass (targeted), linter clean, coverage met, self-review checklist |
| REVIEW → TEST | Reviewer approved, all comments addressed |
| TEST → INTEGRATE | Full test suite (minus e2e) passes |
| INTEGRATE → VERIFY | Clean merge, full suite passes on merged code, docs updated, changelog entry |
| VERIFY → DONE | Acceptance criteria verified, no orphaned code |

### Gate Enforcement (Mechanical)

| Check | How |
|-------|-----|
| Read before write | file_reads > 0 before file_edits |
| Show test output | Test log file attached |
| Complete checklist | Spec checklist compared to completion claims |
| No ignored failures | Test exit code must be 0 |
| Logged to file | Standardized commands |
| No orphans | Orphan detection script |
| No untracked TODOs | Grep TODO, cross-ref with task tracker |

---

## Worker Isolation

### Worktrees

Each task gets its own git worktree:

```bash
# Start task
git worktree add .worktrees/$TASK_ID -b $TASK_ID
cd .worktrees/$TASK_ID

# Complete task (after all gates pass)
cd ../..
git checkout main && git pull origin main
git merge --no-ff $TASK_ID
git push origin main
git worktree remove .worktrees/$TASK_ID
git branch -d $TASK_ID
```

### Handoff Between Phases

When a task transitions phases:
- Full worktree is passed to next worker
- Reviewer can see the diff against main
- planning_docs/ folder contains context
- Original spec remains the source of truth

### Inter-Worker Communication

Workers cannot communicate directly. The orchestrator:
1. Dispatches worker with instructions
2. Waits for worker to complete
3. Receives completion report
4. Dispatches next worker (or handles failure)

If workers need to coordinate (e.g., backend API contract for frontend):
- Tasks are sequenced so dependent work waits
- Shared artifacts (API specs) written to known locations

---

## Artifacts

Each task produces:

```
worktree/
├── (code changes)
├── tests/
│   └── (new/modified tests)
├── planning_docs/
│   └── $TASK_ID/
│       ├── proposal.md          # Technical proposal
│       ├── design-notes.md      # Working notes
│       ├── implementation-plan.md
│       └── decisions.md         # Ad hoc decisions with rationale
└── changelog.d/
    └── $TASK_ID.md              # Changelog fragment
```

---

## State Management

SQLite database tracks workflow state.

### Schema

```sql
-- Tasks
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    spec_id TEXT,
    title TEXT,
    phase TEXT,
    assigned_specialist TEXT,
    worktree_path TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    blocked_by TEXT,
    notes TEXT
);

-- Phase transitions
CREATE TABLE phase_transitions (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    from_phase TEXT,
    to_phase TEXT,
    gate_result TEXT,
    gate_details TEXT,
    transitioned_at TIMESTAMP
);

-- Workers
CREATE TABLE workers (
    id TEXT PRIMARY KEY,
    specialist_type TEXT,
    current_task_id TEXT,
    status TEXT,
    started_at TIMESTAMP
);

-- Merge log
CREATE TABLE merge_log (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    merged_at TIMESTAMP,
    merge_commit TEXT
);

-- Test runs
CREATE TABLE test_runs (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    worktree TEXT,
    commit_sha TEXT,
    total_tests INTEGER,
    passed INTEGER,
    failed INTEGER,
    errors INTEGER,
    skipped INTEGER,
    test_files INTEGER,
    execution_time_seconds REAL,
    failed_tests TEXT,           -- JSON array
    run_at TIMESTAMP
);

-- Violations
CREATE TABLE violations (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    worker_id TEXT,
    violation_type TEXT,
    description TEXT,
    root_cause TEXT,
    prevention TEXT,
    detected_by TEXT,
    detected_at TIMESTAMP
);

-- System counters (for batch triggers)
CREATE TABLE system_counters (
    name TEXT PRIMARY KEY,
    value INTEGER
);
```

---

## Behavioral Norms

Injected into every worker agent's context.

### Reading
- Read before you write
- Understand existing code before proposing changes
- Reference specific files and line numbers

### Verification
- Show your work - paste actual output
- If you claim tests pass, show the passing output
- Never say "done" without evidence

### Completeness
- Done means ALL acceptance criteria met
- If spec has 10 items, complete 10 items
- Partial work is not done

### State Management
- Write to planning_docs/
- Reference your notes explicitly
- Don't repeat yourself or contradict yourself

### Bugs
- If you see a bug, you fix the bug
- "Pre-existing" is not an excuse
- You are part of the system, not separate from it

### Testing
- Fail-fast mode always (`-x`)
- Verbose output always (`-v`)
- Log to file always (`2>&1 | tee test_output.log`)
- First failure gets full attention

### Debugging
Debugging is parallel differential diagnosis:
1. List all plausible causes (not just the first one)
2. For each cause, what evidence would confirm/refute it?
3. Design ONE test run with logging that captures discriminating evidence for ALL hypotheses
4. Run it once
5. Read evidence, eliminate hypotheses, narrow to root cause
6. Only then change code

### Scope
- Do exactly what was asked - not more, not less
- If you think more is needed, propose it separately
- No over-engineering for hypothetical futures

### Cleanup
- Removal is complete removal
- Search for all references
- Leave no orphans

### Debt
- No TODOs without tracked tasks
- No hacks without follow-up
- Debt is not acceptable

---

## Self-Correction Checkpoints

### Before IMPLEMENT → REVIEW

```
CHECKPOINT: Before proceeding to review, verify:
[ ] All acceptance criteria addressed (list them)
[ ] Tests written and passing (show output)
[ ] No TODOs without tracked tasks
[ ] No unrelated changes included
[ ] Code does exactly what spec asked, nothing more
```

### Before TEST → INTEGRATE

```
CHECKPOINT: Before proceeding to integrate, verify:
[ ] Full test suite passed (show output)
[ ] Edge cases from spec are covered
[ ] No tests skipped or ignored
[ ] Any failures encountered were FIXED, not excused
```

---

## Batch Jobs

### E2E Tests

Triggered every ~12 merges to main.

```python
def on_merge_complete(self):
    self.increment_counter('merges_since_e2e')
    if self.get_counter('merges_since_e2e') >= 12:
        self.dispatch_e2e_runner()
        self.reset_counter('merges_since_e2e')
```

**If E2E fails**:
1. Merge lock activated - no new merges to main
2. Bug report created, Bug Investigator assigned (follows bug workflow)
3. Workers continue on their branches but pause before INTEGRATE
4. Once E2E passes, merge lock released, queued merges proceed

### Documentation Updates

Triggered every ~12 merges.

Doc Writer agent:
1. Reviews changelog entries since last doc update
2. Updates relevant documentation
3. Ensures docs match current codebase state

---

## System States

```
┌──────────────────┐
│     HEALTHY      │
│                  │
│ - Merges allowed │
│ - Normal flow    │
└────────┬─────────┘
         │
    E2E fails
         │
         ▼
┌──────────────────┐
│    DEGRADED      │
│                  │
│ - Merges blocked │
│ - Bug investigation│
│ - Work continues │
│   in branches    │
└────────┬─────────┘
         │
    E2E passes
         │
         ▼
┌──────────────────┐
│     HEALTHY      │
└──────────────────┘
```

---

## Spec Amendment

When implementation reveals spec issues:

1. Worker documents the issue in planning_docs/
2. Worker escalates to orchestrator
3. Orchestrator escalates to human
4. Human approves amended spec
5. Work resumes with updated requirements

All spec revisions require human approval.

---

## Session Continuity

The orchestrator is a Claude session that will eventually end.

### Before Session Ends

Human ensures wrapup command is issued:
- Generates session notes
- Creates handoff prompt
- Summarizes in-progress work

### New Session Startup

New orchestrator reconstructs state from:
- SQLite database (tasks, phases, workers)
- Worktree states (what code exists)
- planning_docs/ (context and decisions)
- Handoff notes from previous session

---

## Human Interface

Interaction via Claude Code CLI.

Human can:
- Approve specs and designs
- Review code (rarely)
- Approve spec amendments
- Monitor progress via database queries
- Issue wrapup command before session ends
- Override decisions when needed

---

## Concurrency

- Maximum 6 workers running concurrently
- Workers allocated dynamically by bottleneck
  - If review is slow, allocate more reviewers
  - If implementation is slow, allocate more implementers
- Orchestrator cannot launch new workers while any are running
  - Must dispatch in batches of 1-6
  - Then wait for all to complete

---

## Bootstrap

The workflow system itself is built manually (human + single Claude session), then used to build subsequent applications.

---

## Future Considerations (v2)

- Richer memory system beyond codebase
- Metrics dashboard
- Automated bottleneck detection for worker allocation
- Cross-task dependency visualization
- Violation pattern analysis and norm refinement
