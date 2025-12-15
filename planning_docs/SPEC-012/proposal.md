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

Insert after "Step 3: Review the Diff" and before "Step 4: Run Tests":

```markdown
### Step 3.5: End-to-End Trace

Before approving code, you MUST trace execution paths through all changes. Tracing catches issues invisible in isolated code review.

#### Find All Callers

For EACH modified function/method, identify every caller:

```bash
# Find callers of a function (replace function_name with actual name)
grep -rn "function_name(" src/ tests/

# Find imports of a modified module
grep -rn "from module_name import\|import module_name" src/ tests/

# Find exception handlers (if you modified exceptions)
grep -rn "except.*ExceptionType" src/
```

**Stop and investigate** if any caller:
- Makes assumptions your change invalidates
- Doesn't handle new return values or exceptions
- Uses the function in an unexpected way

#### Trace Data Flow

Starting from each entry point (API endpoint, CLI command, tool handler):
1. What data enters the modified code?
2. How is it transformed?
3. Where does output go?
4. Who consumes that output?

#### Trace Error Paths

For each way the modified code can fail:
1. What exception is raised?
2. Where is it caught?
3. What cleanup/rollback happens?
4. What does the user see?

#### Trace Integration Points

Identify all components the modified code connects to:
1. What contracts (input/output formats, timing, ordering) exist?
2. Does your change maintain those contracts?
3. Are there implicit assumptions you might break?

#### Answer These Questions

You CANNOT approve code without answering:

1. **Data Flow**: "If I call this with X input, what is the complete path to the output?"
2. **Failure Mode**: "If this operation fails at step Y, what happens?"
3. **Caller Impact**: "Who calls this function, and do they all still work correctly?"
4. **State Changes**: "What shared state does this read/modify, and who else depends on it?"

If you cannot answer these questions from your trace, request changes.
```

#### 1.2 Update: Review Checklist

Add trace items to the existing checklist (after "Changes are focused (no scope creep)"):

```markdown
- [ ] **All callers verified** (grep for function_name, verify each handles changes)
- [ ] **Data flow traced** from entry point to output
- [ ] **Error paths traced** to handlers with proper cleanup
- [ ] **Integration contracts maintained** (no broken assumptions)
```

#### 1.3 Update: Reporting Results - APPROVED Template

Replace the existing APPROVED template with:

```markdown
**If APPROVED:**
```
REVIEW RESULT: APPROVED

Summary: [Brief description of what was reviewed]
Files reviewed: [count]
Tests verified: [pass/fail status]

## Trace Summary
- Entry points traced: [list entry points analyzed]
- Callers verified: [list modified functions and their callers]
- Error paths: [list error conditions and their handlers]
- Integration points: [list integration contracts verified]

No blocking issues found.

Review recorded: .claude/bin/claws-review record {TASK_ID} code approved --worker {WORKER_ID}
```
```

### 2. Changes to `.claude/roles/spec-reviewer.md`

#### 2.1 Add Trace-Related Items to Completeness Checklist

Add to the **Completeness** section:

```markdown
- [ ] Data flow is described (inputs, transformations, outputs)
- [ ] Error handling expectations define what happens when operations fail
- [ ] Integration points are identified with their contracts
```

### 3. Changes to `.claude/roles/proposal-reviewer.md`

#### 3.1 Add Trace-Related Items to Technical Soundness Checklist

Add to the **Technical Soundness** section:

```markdown
- [ ] Data flow design is complete (entry to exit traced)
- [ ] Error propagation paths are defined
- [ ] Integration contracts are specified (inputs, outputs, timing)
```

## File-by-File Change Summary

| File | Section | Change Type | Description |
|------|---------|-------------|-------------|
| `.claude/roles/reviewer.md` | Step 3.5 | New section | End-to-End Trace requirements |
| `.claude/roles/reviewer.md` | Review Checklist | Add items | 4 new trace verification items |
| `.claude/roles/reviewer.md` | Reporting Results | Modify template | Add Trace Summary to APPROVED output |
| `.claude/roles/spec-reviewer.md` | Completeness checklist | Add items | 3 new trace-related items |
| `.claude/roles/proposal-reviewer.md` | Technical Soundness | Add items | 3 new trace-related items |

## Implementation Notes

1. **Position matters**: The trace section goes BEFORE test verification because traces may reveal test gaps that the reviewer should flag.

2. **Helper commands are examples**: The grep patterns serve as reminders; reviewers may need to adapt them to specific function names.

3. **Trace Summary is evidence**: Requiring written documentation of traces ensures reviewers actually perform them rather than claiming to.

4. **Questions cannot be skipped**: The mandatory questions are designed to be unanswerable without actually tracing the code.

5. **Lighter requirements for specs/proposals**: These catch trace-related gaps early but don't require the full rigor of code review (since there's no code to trace yet).

## Acceptance Criteria Mapping

| Spec Criterion | Addressed By |
|----------------|--------------|
| AC1: reviewer.md has E2E Trace section with all checklists | Section 1.1 adds complete trace section |
| AC2: Main checklist includes trace items | Section 1.2 adds 4 trace items |
| AC3: APPROVED template includes trace summary | Section 1.3 updates template |
| AC4: spec-reviewer.md has trace items | Section 2.1 adds 3 items |
| AC5: proposal-reviewer.md has trace items | Section 3.1 adds 3 items |
| AC6: Helper grep patterns documented | Section 1.1 includes grep examples |
| AC7: Trace before test verification | Section positioned as Step 3.5 (before Step 4: Run Tests) |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Reviewers skip trace documentation | Trace Summary is mandatory in APPROVED output; orchestrator can verify |
| Trace overhead slows reviews | Trace is focused on modified functions only; grep commands make caller discovery fast |
| Unclear when trace is "complete enough" | Mandatory questions provide concrete completeness criteria |
