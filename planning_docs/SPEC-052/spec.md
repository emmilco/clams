# SPEC-052: Reviewer Checklist - Test-Production Parity (R17-C)

## Summary

Add test-production parity checklist items to `.claude/roles/reviewer.md` to catch divergence between test and production configurations during code review.

## Background

BUG-031, BUG-033, and BUG-040 showed tests passing with mock/test configurations while production failed. Reviewers need explicit checklist items to catch these patterns.

**Reference**: See `planning_docs/tickets/recommendations-r14-r17.md` section R17-C for full context.

## Requirements

### 1. Add Test-Production Parity Section to reviewer.md

Add the following section to `.claude/roles/reviewer.md` under the "Bug Pattern Prevention" heading:

```markdown
### Test-Production Parity (T7)

_Rationale: BUG-031 used different clustering parameters in tests vs production. BUG-033 used different server commands. BUG-040 had mocks with different interfaces than production._

- [ ] **Production configurations in tests**: Do tests use production configuration values? If using test-specific values, is there explicit justification in comments?
- [ ] **Mocks match production interfaces**: If tests use mocks, do the mocks have the same method signatures as the production classes they replace?
- [ ] **Commands match production**: Are the commands run in tests (e.g., server startup) identical to production commands?
```

### 2. Placement

Insert this section after any existing "Bug Pattern Prevention" sections, alongside other T-theme checklist items.

### 3. Cross-Reference

Ensure the section references the bug pattern analysis document for full context.

## Acceptance Criteria

- [ ] `.claude/roles/reviewer.md` updated with test-production parity checklist section
- [ ] Section includes "Production configurations in tests" item
- [ ] Section includes "Mocks match production interfaces" item
- [ ] Section includes "Commands match production" item
- [ ] Each item references the bugs that motivated it (BUG-031, BUG-033, BUG-040)
- [ ] Section explains WHY these checks matter (tests pass but production fails)
- [ ] Checklist items are actionable (reviewer can apply them)

## Out of Scope

- Updating spec-reviewer.md or proposal-reviewer.md (covered by SPEC-054)
- Adding automated parity checks (this is documentation only)

## Dependencies

None.

## Testing Requirements

- Manual review: verify checklist items would have caught BUG-031, BUG-033, BUG-040
- Verify checklist items are clear and actionable
