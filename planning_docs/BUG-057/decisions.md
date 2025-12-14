# BUG-057: Design Decisions

## Decision 1: Soft Enforcement Over Hard Enforcement

**Context**: We need to decide how to enforce permission boundaries for workers.

**Options Considered**:

1. **Hard technical enforcement**: Use Claude Code sandbox configuration, per-directory settings, or custom tooling to technically prevent out-of-scope operations
2. **Soft prompt-based enforcement**: Document permissions explicitly in prompts and rely on worker compliance
3. **Hybrid approach**: Soft enforcement with post-hoc verification

**Decision**: **Hybrid approach (Option 3)**

**Rationale**:
- Claude Code's subagent sandbox is not configurable per-task - we cannot set custom restrictions
- Hard enforcement would require external tooling that doesn't exist
- Prompt-based enforcement is effective for well-designed agents (Opus)
- Post-hoc verification (code review) catches violations before they reach main
- The 2x review gate already provides a safety net

**Consequences**:
- Workers must self-report compliance
- Reviewers must verify worktree boundaries during code review
- Violations are caught at review time, not execution time
- Relies on Opus agents following instructions accurately

---

## Decision 2: Permission Categories Based on Role Type

**Context**: How granular should the permission model be?

**Options Considered**:

1. **Binary model**: Workers either have full access or read-only
2. **Directory-based model**: Permissions defined by directory (src/, tests/, etc.)
3. **Role-based model**: Each role has specific permissions based on their function
4. **Task-based model**: Permissions defined per-task in the spec

**Decision**: **Role-based model (Option 3)**

**Rationale**:
- Roles already exist and are well-understood
- Each role has a clear function (implementer writes code, reviewer reads code)
- Simpler to maintain than task-by-task permissions
- More granular than binary model, less complex than directory-based
- Aligns with existing CLAWS architecture

**Consequences**:
- Permission definitions live in role files (.claude/roles/*.md)
- All instances of a role have the same permissions
- Special cases must be documented as exceptions
- New roles require new permission definitions

---

## Decision 3: MCP Tool Limitation is Architectural, Not a Bug

**Context**: Subagent workers cannot access MCP tools like CLAMS memory functions.

**Options Considered**:

1. **Treat as bug to fix**: Investigate how to enable MCP tools for subagents
2. **Accept as constraint**: Design workflows around this limitation
3. **Workaround**: Have orchestrator execute MCP operations on behalf of workers

**Decision**: **Accept as constraint (Option 2) with workaround (Option 3)**

**Rationale**:
- MCP tool access for subagents is a Claude Code architecture decision, not a bug
- Changing this would require changes to Claude Code itself
- Most worker tasks don't require MCP tools anyway
- The orchestrator can handle MCP operations when needed (e.g., storing GHAP entries)
- Designing tasks within constraints is more sustainable than fighting the architecture

**Consequences**:
- Worker prompts explicitly state MCP tools are unavailable
- Tasks requiring MCP operations should be orchestrator tasks
- Fallback protocol includes escalating MCP-requiring operations to orchestrator
- Future CLAWS designs should not assume subagent MCP access

---

## Decision 4: Always Use Opus for Workers

**Context**: Different Claude models have different capability restrictions.

**Options Considered**:

1. **Use cheapest model that works**: Try Haiku, fall back to Sonnet, then Opus
2. **Match model to task complexity**: Simple tasks get Haiku, complex get Opus
3. **Always use Opus**: Consistent capability set across all workers

**Decision**: **Always use Opus (Option 3)**

**Rationale**:
- Retrospective shows Haiku and Sonnet frequently fail due to permission restrictions
- Wasted compute on failed attempts costs more than using Opus upfront
- Opus has the most consistent tool access across all scenarios
- Simplifies worker dispatch logic (no model selection)
- Quality of work is consistently higher with Opus

**Consequences**:
- Higher per-worker cost
- But fewer failed attempts, so lower total cost
- Consistent quality across all workers
- CLAUDE.md already specifies Opus for all workers (this decision codifies it)

---

## Decision 5: Fallback Protocol as First-Class Pattern

**Context**: When workers hit permission limitations, what should they do?

**Options Considered**:

1. **Fail the task**: Worker marks task as failed, orchestrator retries with different approach
2. **Retry with different tool**: Worker tries alternative approaches
3. **Fallback to orchestrator**: Worker provides analysis, orchestrator completes execution

**Decision**: **Fallback to orchestrator (Option 3)**

**Rationale**:
- Worker's analysis is still valuable even if they can't execute
- Failing the task wastes the work done so far
- Orchestrator has full permissions and can complete any operation
- This pattern is already used informally, we're just codifying it
- Preserves the value of parallel worker dispatch

**Consequences**:
- Workers must clearly document what they need the orchestrator to do
- Orchestrator must be prepared to complete partial work
- Worker completion reports include blocked operations
- Orchestrator time increases for tasks that hit limitations

---

## Decision 6: Permission Documentation in Role Files, Not Central Registry

**Context**: Where should permission definitions live?

**Options Considered**:

1. **Central registry**: Single file (e.g., `docs/worker-permissions.md`) with all permissions
2. **Per-role documentation**: Each role file contains its own permissions
3. **Database schema**: Store permissions in claws.db

**Decision**: **Per-role documentation (Option 2)**

**Rationale**:
- Permissions are read when dispatching workers (worker context command)
- Role files are already read for worker prompts
- Single source of truth for each role's behavior AND permissions
- No sync issues between central registry and role files
- Easier to maintain - update role file when role changes

**Consequences**:
- Each .claude/roles/*.md file gets a Permissions section
- claws-worker context includes permission constraints from role file
- No central permissions overview (could add generated summary doc if needed)
- Role additions require permission section in new role file

---

## Decision 7: Worktree Path Enforcement via Git Status Check

**Context**: How do we verify workers didn't modify files outside their worktree?

**Options Considered**:

1. **Pre-execution path validation**: Check paths before allowing write operations
2. **Post-execution git status check**: Verify all changes are in-scope after completion
3. **Git hook enforcement**: Pre-commit hook that rejects out-of-scope changes
4. **Review-time verification**: Reviewers check scope compliance during code review

**Decision**: **Post-execution git status check (Option 2) + Review-time verification (Option 4)**

**Rationale**:
- Pre-execution validation would require custom tooling
- Git hooks would prevent legitimate operations (orchestrator can modify anywhere)
- Git status check is simple and reliable
- Reviewers already examine the diff - adding scope check is low overhead
- Multiple verification points (self-check + review) provides defense in depth

**Consequences**:
- Workers run git status check before reporting completion
- Role files include verification commands
- Reviewers verify changes are within expected directories
- Out-of-scope changes caught at latest during code review

---

## Summary

| # | Decision | Chosen Option | Key Tradeoff |
|---|----------|---------------|--------------|
| 1 | Enforcement model | Hybrid (soft + verification) | Simplicity vs. security |
| 2 | Permission granularity | Role-based | Maintainability vs. flexibility |
| 3 | MCP tool access | Accept constraint | Work within limits vs. fight architecture |
| 4 | Worker model | Always Opus | Cost per worker vs. reliability |
| 5 | Permission failures | Fallback protocol | Orchestrator load vs. work preservation |
| 6 | Permission location | Per-role in .md files | Cohesion vs. central overview |
| 7 | Worktree enforcement | Git status + review | Multiple checks vs. single point |

All decisions prioritize **simplicity** and **working within Claude Code's architecture** over complex technical enforcement that would require external tooling or architectural changes.
