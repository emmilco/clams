# SPEC-054 Proposal: Update Spec and Proposal Reviewer Checklists

## Summary

Add bug pattern prevention checklist items to `spec-reviewer.md` and `proposal-reviewer.md`, adapted from the code reviewer checklist items added in SPEC-050.

## Background

SPEC-050 through SPEC-053 added bug pattern prevention checklist items to the code reviewer role. These items catch issues during code review, but earlier detection is better - catching issues during spec or proposal review prevents wasted implementation effort.

## Design

### Spec Reviewer Additions

Add a new section "Bug Pattern Prevention (from analysis)" after the existing "Consistency" section. Include 3 items (T3, T5, T7 only - T1/T2 type decisions aren't made at spec phase):

```markdown
### Bug Pattern Prevention (from analysis)

These items catch patterns that have caused recurring bugs. See `.claude/roles/reviewer.md` for implementation-phase checks.

- [ ] **T3: Initialization requirements stated**: Does the spec mention what resources must be initialized? (e.g., "The feature requires a new Qdrant collection, which must be created on first use")
- [ ] **T5: Input validation expectations**: Does the spec define valid input ranges and expected error behavior for invalid inputs?
- [ ] **T7: Test requirements explicit**: Does the spec mention testing requirements, including whether test values should match production?
```

### Proposal Reviewer Additions

Add a new section "Bug Pattern Prevention (from analysis)" after the existing "Simplicity" section. Include 4 items (all themes - proposals are where type decisions are made):

```markdown
### Bug Pattern Prevention (from analysis)

These items catch patterns that have caused recurring bugs. See `.claude/roles/reviewer.md` for implementation-phase checks.

- [ ] **T3: Initialization strategy defined**: Does the proposal describe how resources will be initialized? (e.g., "Will use ensure_exists pattern like CodeIndexer")
- [ ] **T5: Input validation strategy**: Does the proposal describe input validation approach?
- [ ] **T1/T2: Type location decided**: If new types are needed, does the proposal specify where they'll be defined? Are there existing types that should be reused?
- [ ] **T7: Test strategy covers production parity**: Does the testing approach mention using production configurations?
```

## Implementation Steps

1. Read current `spec-reviewer.md`
2. Add "Bug Pattern Prevention" section after "Consistency" section
3. Read current `proposal-reviewer.md`
4. Add "Bug Pattern Prevention" section after "Simplicity" section
5. Verify theme tags (T1, T2, T3, T5, T7) are present on all items
6. Verify cross-reference to code reviewer checklist is included

## Testing

- Manual review: Verify checklist items are actionable at spec/proposal phase
- Verify all theme tags are present
- Verify cross-references exist
- Apply updated checklists mentally to a recent spec/proposal to confirm utility

## Files Modified

- `.claude/roles/spec-reviewer.md`
- `.claude/roles/proposal-reviewer.md`
