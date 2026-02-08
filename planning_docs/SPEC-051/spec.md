# SPEC-051: Reviewer Checklist - Input Validation (R17-B)

## Summary

Add input validation checklist items to `.claude/roles/reviewer.md` to catch missing validation patterns during code review.

## Background

BUG-029 and BUG-036 showed functions accepting invalid inputs and raising cryptic errors deep in the call stack instead of helpful validation errors at the boundary. Reviewers need explicit checklist items to catch these patterns.

**Reference**: See `planning_docs/tickets/recommendations-r14-r17.md` section R17-B for full context.

## Requirements

### 1. Add Input Validation Section to reviewer.md

Add the following section to `.claude/roles/reviewer.md` under the "Bug Pattern Prevention" heading:

```markdown
### Input Validation (T5)

_Rationale: BUG-029 and BUG-036 showed functions raising cryptic KeyError deep in the stack instead of helpful validation errors at the boundary._

- [ ] **Public functions validate inputs**: Do public functions validate their inputs at the start, before processing?
- [ ] **Error messages are helpful**: When validation fails, does the error message list valid options? (e.g., "Invalid type 'foo'. Valid types: bar, baz, qux")
- [ ] **No bare dict access**: Are there any `dict[key]` accesses that could raise KeyError? Should they use `.get()` with default or explicit validation?
```

### 2. Placement

Insert this section after any existing "Bug Pattern Prevention" sections, or create the "Bug Pattern Prevention" heading if it doesn't exist.

### 3. Cross-Reference

Ensure the section references the bug pattern analysis document for full context.

## Acceptance Criteria

- [ ] `.claude/roles/reviewer.md` updated with input validation checklist section
- [ ] Section includes "Public functions validate inputs" item
- [ ] Section includes "Error messages are helpful" item
- [ ] Section includes "No bare dict access" item
- [ ] Each item references the bugs that motivated it (BUG-029, BUG-036)
- [ ] Section explains WHY these checks matter (cryptic errors vs helpful validation)
- [ ] Checklist items are actionable (reviewer can apply them)

## Out of Scope

- Updating spec-reviewer.md or proposal-reviewer.md (covered by SPEC-054)
- Adding automated validation checks (this is documentation only)

## Dependencies

None.

## Testing Requirements

- Manual review: verify checklist items would have caught BUG-029 and BUG-036
- Verify checklist items are clear and actionable
