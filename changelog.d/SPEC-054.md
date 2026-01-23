## SPEC-054: Update spec and proposal reviewer checklists (R17-E)

### Summary

Added bug pattern prevention checklist items to spec-reviewer.md and proposal-reviewer.md, enabling earlier detection of issues that have caused recurring bugs.

### Changes

- Added "Bug Pattern Prevention (from analysis)" section to `.claude/roles/spec-reviewer.md`:
  - T3: Initialization requirements stated
  - T5: Input validation expectations
  - T7: Test requirements explicit

- Added "Bug Pattern Prevention (from analysis)" section to `.claude/roles/proposal-reviewer.md`:
  - T3: Initialization strategy defined
  - T5: Input validation strategy
  - T1/T2: Type location decided
  - T7: Test strategy covers production parity

- Cross-references to code reviewer checklist for implementation-phase checks
