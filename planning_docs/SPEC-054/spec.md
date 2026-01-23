# SPEC-054: Update Spec and Proposal Reviewer Checklists (R17-E)

## Problem Statement

The bug pattern prevention items being added to the code reviewer checklist (SPEC-050 through SPEC-053) should also be caught during spec and proposal review. Earlier detection is cheaper - catching issues during spec review is better than catching them during code review or in production.

## Proposed Solution

Add adapted versions of the bug pattern prevention checklist items to spec-reviewer.md and proposal-reviewer.md.

## Theme Reference

The themes (T1-T7) come from SPEC-050 through SPEC-053:
- **T3 (Initialization Patterns)**: SPEC-050 - ensure_exists patterns for resources
- **T5 (Input Validation)**: SPEC-051 - validate inputs with helpful errors
- **T7 (Test-Production Parity)**: SPEC-052 - tests use production configs
- **T1, T2 (Type Consistency)**: SPEC-053 - types in canonical locations, no duplicates, inheritance respected

Not all themes apply at spec/proposal phase. Only themes that can be meaningfully checked before implementation are included.

## Acceptance Criteria

- [ ] `.claude/roles/spec-reviewer.md` updated with bug pattern prevention checklist section
- [ ] `.claude/roles/proposal-reviewer.md` updated with bug pattern prevention checklist section
- [ ] Spec reviewer items adapted for spec context (e.g., "Does spec mention initialization requirements?")
- [ ] Proposal reviewer items adapted for proposal context (e.g., "Does proposal describe initialization strategy?")
- [ ] Items reference applicable themes (T1, T2, T3, T5, T7) for traceability
- [ ] Each item includes the theme tag (e.g., "T3:" prefix)
- [ ] Cross-references to code reviewer checklist for implementation-phase checks

## Implementation Notes

- **Dependencies**: SPEC-050, SPEC-051, SPEC-052, SPEC-053 should be done first to establish patterns

- For `.claude/roles/spec-reviewer.md`, add after existing checklist:
  ```markdown
  ### Bug Pattern Prevention (from analysis)

  - [ ] **T3: Initialization requirements stated**: Does the spec mention what resources must be initialized? (e.g., "The feature requires a new Qdrant collection, which must be created on first use")
  - [ ] **T5: Input validation expectations**: Does the spec define valid input ranges and expected error behavior for invalid inputs?
  - [ ] **T7: Test requirements explicit**: Does the spec mention testing requirements, including whether test values should match production?
  ```

  **Note**: Spec-reviewer has 3 items because T1/T2 (type consistency) cannot be meaningfully checked at spec phase - type design decisions are made during proposal/implementation.

- For `.claude/roles/proposal-reviewer.md`, add after existing checklist:
  ```markdown
  ### Bug Pattern Prevention (from analysis)

  - [ ] **T3: Initialization strategy defined**: Does the proposal describe how resources will be initialized? (e.g., "Will use ensure_exists pattern like CodeIndexer")
  - [ ] **T5: Input validation strategy**: Does the proposal describe input validation approach?
  - [ ] **T1/T2: Type location decided**: If new types are needed, does the proposal specify where they'll be defined? Are there existing types that should be reused?
  - [ ] **T7: Test strategy covers production parity**: Does the testing approach mention using production configurations?
  ```

  **Note**: Proposal-reviewer has 4 items because it includes T1/T2 (type consistency) - proposals are where type design decisions are documented.

## Testing Requirements

- **Cross-reference with source specs**: Each item in spec-reviewer.md and proposal-reviewer.md must trace back to a specific theme (T1, T2, T3, T5, or T7) from SPEC-050-053
- **Verify theme tags present**: All items must have theme tags (e.g., "T3:", "T5:")
- **Check theme coverage**: Spec-reviewer should cover T3, T5, T7. Proposal-reviewer should cover T1/T2, T3, T5, T7
- **Verify cross-references**: Each file should include a note pointing to the code reviewer checklist for implementation-phase checks
- **Manual walkthrough**: Apply the updated checklists to one recent spec and one recent proposal to verify they're actionable

## Out of Scope

- Adding items beyond what was established in SPEC-050 through SPEC-053
- Automated enforcement of these checklist items
- Gate script changes
