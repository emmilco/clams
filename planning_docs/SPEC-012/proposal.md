# SPEC-012: Technical Proposal

## Problem Statement

Code reviewers currently lack explicit guidance to trace execution paths through code changes. This results in:
- Approved code with incomplete data flow understanding
- Missed edge cases visible only through full execution tracing
- Unverified integration points where changes break downstream callers
- Untested error paths and exception handling
- Shared code changes that silently break dependent modules

The root cause is that the reviewer checklist focuses on surface-level correctness without requiring systematic execution path analysis.

## Proposed Solution

Add an "End-to-End Trace" section to `.claude/roles/reviewer.md` containing:
1. A checklist requiring trace verification before approval
2. Helper grep commands for caller discovery
3. A documentation template for trace evidence
4. Mandatory questions that cannot be answered without tracing

Additionally, add lighter-weight trace requirements to spec-reviewer.md and proposal-reviewer.md to catch trace-related gaps earlier in the workflow.

## Detailed Design

### 1. Changes to `.claude/roles/reviewer.md`

#### 1.1 New Section: "Step 3.5: End-to-End Trace"

**Location**: Insert after line 54 (end of "### Step 3: Review the Diff" content) and before line 56 (start of "### Step 4: Run Tests").

**Rationale**: The spec requires this section be positioned "between current Step 3 (Review the Diff) and Step 4 (Run Tests)" and to use "Step 3.5" literally to preserve existing references.

**Content to insert**:

```markdown
### Step 3.5: End-to-End Trace

Before running tests, trace the execution paths of the changed code. This reveals test gaps and integration issues that surface-level review misses.

#### Data Flow Trace

- [ ] Traced all entry points for the changed code (API endpoints, tool handlers, CLI commands)
- [ ] Traced data transformations from input to output
- [ ] Verified return values are used correctly by callers
- [ ] Checked for data validation at trust boundaries

#### Caller Analysis

- [ ] Identified ALL callers of modified functions/methods (using grep/search)
- [ ] Verified each caller handles the modified interface correctly
- [ ] Checked for callers in tests that may need updates
- [ ] Verified no callers make assumptions that the change invalidates

#### Error Path Trace

- [ ] Traced what happens when the function raises an exception
- [ ] Verified error propagation to appropriate handlers
- [ ] Checked that error messages are informative
- [ ] Verified cleanup/rollback occurs on failure paths

#### Integration Point Verification

- [ ] Identified components that this code integrates with
- [ ] Verified contracts with each integration point are maintained
- [ ] Checked for implicit assumptions about order of operations
- [ ] Verified async/await usage is correct through the call chain

#### Mandatory Trace Questions

Answer these questions before proceeding to tests. They cannot be answered without actually tracing the code:

1. **Data Flow**: "If I pass X as input at the entry point, what is the complete path to the output?"
2. **Failure Mode**: "If component Y fails, what happens to this operation?"
3. **Caller Impact**: "Function Z was modified. Who calls Z, and do they all still work correctly?"
4. **State Changes**: "What shared state does this code read or modify, and who else depends on that state?"

#### Helper Commands

```bash
# Find all callers of a function
grep -rn "function_name(" src/ tests/

# Find all imports of a module
grep -rn "from module import\|import module" src/

# Find all exception handlers for a type
grep -rn "except.*ErrorType" src/
```

#### Trace Documentation

Document your trace findings in the Trace Summary section of your APPROVED report (see Reporting Results).
```

#### 1.2 New Subsection: "End-to-End Trace" in Bug Pattern Prevention

**Location**: Insert after line 122 (end of "### Type Consistency (T1, T2)" subsection) and before line 124 (start of "## Recording Your Review (REQUIRED)").

**Rationale**: The spec requires adding summary trace items to the "Bug Pattern Prevention" checklist as condensed reminders of the Part 1 detailed requirements.

**Content to insert**:

```markdown
### End-to-End Trace (from SPEC-012)

_Rationale: Retrospective analysis of 44 session handoffs showed reviewers approving code without tracing execution paths, leading to missed integration issues and caller breakages._

- [ ] **Entry points traced and documented**: Have you traced all entry points for the changed code?
- [ ] **All callers of modified functions verified**: Did you grep for callers and verify each handles the change correctly?
- [ ] **Error paths traced to handlers**: Have you followed what happens when the function throws?
- [ ] **Integration points verified**: Did you check contracts with components this code integrates with?
```

#### 1.3 Update: Reporting Results - APPROVED Template

**Location**: Replace lines 147-156 (the "If APPROVED:" template block).

**Rationale**: The spec requires the APPROVED template to include a Trace Summary section as evidence that tracing was performed.

**Replace existing template with**:

```markdown
**If APPROVED:**
```
REVIEW RESULT: APPROVED

Summary: [Brief description of what was reviewed]
Files reviewed: [count]
Tests verified: [pass/fail status]

## Trace Summary
- Entry points: [list entry points traced]
- Callers verified: [list callers of modified functions and verification status]
- Error paths: [list error conditions and how they propagate]
- Integration points: [list integration points and verification status]

No blocking issues found.

Review recorded: .claude/bin/claws-review record {TASK_ID} code approved --worker {WORKER_ID}
```
```

### 2. Changes to `.claude/roles/spec-reviewer.md`

#### 2.1 Add Trace-Related Items to Bug Pattern Prevention

**Location**: Insert after line 59 (the T7 item ending with "production?") and before line 61 (start of "### Step 3: Document Issues").

**Rationale**: The spec requires these items be added to the "Bug Pattern Prevention (from analysis)" section, not the general Completeness section.

**Content to insert**:

```markdown
- [ ] **Data flow is described**: Does the spec identify entry points, data transformations, and outputs?
- [ ] **Error handling strategy is documented**: Does the spec describe expected behavior for identified failure modes?
- [ ] **Integration points are identified**: Does the spec list external components and their contracts?
```

### 3. Changes to `.claude/roles/proposal-reviewer.md`

#### 3.1 Add Trace-Related Items to Bug Pattern Prevention

**Location**: Insert after line 65 (the T7 item ending with "configurations?") and before line 67 (start of "### Step 3: Document Issues").

**Rationale**: The spec requires these items be added to the "Bug Pattern Prevention (from analysis)" section, not the general Technical Soundness section.

**Content to insert**:

```markdown
- [ ] **Data flow design is complete**: Are all data paths documented from entry to exit?
- [ ] **Error propagation is defined**: Does the proposal specify what happens on failure at each stage?
- [ ] **Integration contracts are specified**: Are input/output types explicitly defined at boundaries?
```

## File-by-File Change Summary

| File | Section | Change Type | Line Location | Description |
|------|---------|-------------|---------------|-------------|
| `.claude/roles/reviewer.md` | Step 3.5 | New section | After line 54 | End-to-End Trace with 4 checklists, questions, helper commands |
| `.claude/roles/reviewer.md` | Bug Pattern Prevention | New subsection | After line 122 | 4 summary trace items |
| `.claude/roles/reviewer.md` | Reporting Results | Modify template | Lines 147-156 | Add Trace Summary to APPROVED output |
| `.claude/roles/spec-reviewer.md` | Bug Pattern Prevention | Add items | After line 59 | 3 new trace-related items |
| `.claude/roles/proposal-reviewer.md` | Bug Pattern Prevention | Add items | After line 65 | 3 new trace-related items |

## Implementation Notes

1. **Position matters**: The trace section goes BEFORE test verification (Step 4) because traces may reveal test gaps that the reviewer should flag.

2. **Step numbering**: Use "Step 3.5" literally. Do NOT renumber Steps 4, 5, and 6. This preserves existing references and makes the insertion clear.

3. **Helper commands are examples**: The grep patterns serve as reminders; reviewers may need to adapt them to specific function names.

4. **Trace Summary is evidence**: Requiring written documentation of traces ensures reviewers actually perform them rather than claiming to.

5. **Questions cannot be skipped**: The mandatory questions are designed to be unanswerable without actually tracing the code.

6. **Lighter requirements for specs/proposals**: These catch trace-related gaps early but don't require the full rigor of code review (since there's no code to trace yet).

7. **Match existing formatting**: Follow the same markdown style used in each file:
   - Use `- [ ]` for checklist items
   - Use `_Rationale: ..._` format for the Bug Pattern Prevention subsection
   - Use `####` for sub-subsections within Step 3.5

## Testing Strategy

Since this is a documentation-only change, testing focuses on manual verification:

### Structural Verification

1. **reviewer.md structure**:
   - [ ] Step 3.5 exists between Step 3 and Step 4
   - [ ] Step 4, 5, 6 retain original numbering
   - [ ] New Bug Pattern Prevention subsection exists after Type Consistency
   - [ ] APPROVED template contains Trace Summary section

2. **reviewer.md content**:
   - [ ] Step 3.5 has 4 checklist subsections (Data Flow, Caller Analysis, Error Path, Integration Point)
   - [ ] Each checklist subsection has 4 items
   - [ ] Mandatory Trace Questions has 4 questions
   - [ ] Helper Commands has 3 grep patterns
   - [ ] Bug Pattern Prevention subsection has 4 items with rationale

3. **spec-reviewer.md**:
   - [ ] Bug Pattern Prevention has 3 new trace items (data flow, error handling, integration)

4. **proposal-reviewer.md**:
   - [ ] Bug Pattern Prevention has 3 new trace items (data flow design, error propagation, integration contracts)

### Functional Verification

1. Read through the modified reviewer.md and verify the trace workflow is logical
2. Verify helper grep commands produce valid output
3. Confirm the 4 mandatory questions cannot be answered without actually tracing code
4. Verify the Trace Summary template is easy to fill out during review

## Acceptance Criteria Mapping

| Spec Criterion | Addressed By |
|----------------|--------------|
| AC1: reviewer.md has E2E Trace section with all checklists | Section 1.1 - Step 3.5 with Data Flow, Caller Analysis, Error Path, Integration Point checklists |
| AC2: Main Review Checklist includes trace items | Section 1.2 - Bug Pattern Prevention subsection with 4 items |
| AC3: APPROVED template includes trace summary | Section 1.3 - Updated template with Trace Summary section |
| AC4: spec-reviewer.md has trace items | Section 2.1 - 3 items in Bug Pattern Prevention |
| AC5: proposal-reviewer.md has trace items | Section 3.1 - 3 items in Bug Pattern Prevention |
| AC6: Helper grep patterns documented | Section 1.1 - Helper Commands with 3 patterns |
| AC7: Trace before test verification | Section 1.1 - Step 3.5 positioned before Step 4 (Run Tests) |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Reviewers skip trace documentation | Trace Summary is mandatory in APPROVED output; orchestrator can verify |
| Trace overhead slows reviews | Trace is focused on modified functions only; grep commands make caller discovery fast |
| Unclear when trace is "complete enough" | Mandatory questions provide concrete completeness criteria |
| Line numbers change before implementation | Proposal describes content-based locations, not just line numbers |

## Alternatives Considered

### Alternative 1: Separate Trace Checklist File

**Approach**: Create a new file `.claude/roles/trace-checklist.md` and reference it from reviewer.md.

**Rejected because**: This adds indirection and makes the review workflow less streamlined. The trace is an integral part of code review, not a separate activity.

### Alternative 2: Automated Trace Tooling

**Approach**: Build call-graph analysis tools that automatically trace execution paths.

**Rejected because**: Explicitly out of scope per the spec. This is a process improvement, not a tooling project.

### Alternative 3: Renumber Steps 4-6 to 5-7

**Approach**: Instead of "Step 3.5", renumber all subsequent steps.

**Rejected because**: The spec explicitly states to use "Step 3.5" to preserve existing references and make the insertion clear.

### Alternative 4: Add trace items to general checklist sections

**Approach**: Add trace items to Completeness (spec-reviewer) and Technical Soundness (proposal-reviewer).

**Rejected because**: The spec explicitly requires these items go in the "Bug Pattern Prevention" subsection of each file to maintain consistency with existing bug-pattern-based items.
