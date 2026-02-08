# SPEC-053: Reviewer Checklist - Type Consistency (R17-D)

## Summary

Add type consistency checklist items to `.claude/roles/reviewer.md` to catch duplicate type definitions and inheritance violations during code review.

## Background

BUG-040 and BUG-041 showed parallel type hierarchies with incompatible implementations. Reviewers need explicit checklist items to catch these patterns before they cause runtime errors.

**Reference**: See `planning_docs/tickets/recommendations-r14-r17.md` section R17-D for full context.

## Requirements

### 1. Add Type Consistency Section to reviewer.md

Add the following section to `.claude/roles/reviewer.md` under the "Bug Pattern Prevention" heading:

```markdown
### Type Consistency (T1, T2)

_Rationale: BUG-040 had duplicate CodeResult types with different field names. BUG-041 had concrete Searcher not inheriting from abstract Searcher._

- [ ] **Types in canonical location**: If defining new shared types, are they in the canonical `types/` module (or equivalent central location)?
- [ ] **No duplicate definitions**: Is this type already defined elsewhere? Should this use an import instead of a new definition?
- [ ] **Inheritance respected**: If there's an abstract base class, does the concrete implementation inherit from it?
```

### 2. Placement

Insert this section after any existing "Bug Pattern Prevention" sections, alongside other T-theme checklist items.

### 3. Cross-Reference

Ensure the section references the bug pattern analysis document for full context.

## Acceptance Criteria

- [ ] `.claude/roles/reviewer.md` updated with type consistency checklist section
- [ ] Section includes "Types in canonical location" item
- [ ] Section includes "No duplicate definitions" item
- [ ] Section includes "Inheritance respected" item
- [ ] Each item references the bugs that motivated it (BUG-040, BUG-041)
- [ ] Section explains WHY these checks matter (incompatible parallel implementations)
- [ ] Checklist items are actionable (reviewer can apply them)

## Out of Scope

- Updating spec-reviewer.md or proposal-reviewer.md (covered by SPEC-054)
- Adding automated type consistency checks (this is documentation only)

## Dependencies

None.

## Testing Requirements

- Manual review: verify checklist items would have caught BUG-040 and BUG-041
- Verify checklist items are clear and actionable
