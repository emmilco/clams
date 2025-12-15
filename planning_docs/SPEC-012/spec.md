# SPEC-012: Add End-to-End Trace to Reviewer Checklist

## Problem Statement

Retrospective analysis of 44 session handoffs revealed that code reviewers do not consistently trace through the complete execution path of changes. This leads to several failure modes:

1. **Incomplete data flow understanding**: Reviewers approve code without tracing how data moves from entry points through transformations to final outputs
2. **Missed edge cases**: Reviewers focus on happy paths, missing error conditions and boundary cases that only appear when tracing full execution
3. **Unverified integration points**: Changes to one component may break callers or downstream consumers that reviewers do not check
4. **Untested error paths**: Exception handling and error recovery paths are not systematically traced
5. **Shared code blind spots**: Changes to shared utilities or base classes do not trigger review of all dependent code

The current reviewer checklist (in `.claude/roles/reviewer.md`) focuses on surface-level correctness but lacks explicit requirements for systematic execution path tracing.

## Proposed Solution

Add a mandatory "End-to-End Trace" section to the code reviewer checklist that requires reviewers to explicitly trace and document execution paths before approving code.

### Part 1: Trace Requirements Checklist

Add the following trace requirements to the reviewer checklist:

**Data Flow Trace**
- [ ] Traced all entry points for the changed code (API endpoints, tool handlers, CLI commands)
- [ ] Traced data transformations from input to output
- [ ] Verified return values are used correctly by callers
- [ ] Checked for data validation at trust boundaries

**Caller Analysis**
- [ ] Identified ALL callers of modified functions/methods (using grep/search)
- [ ] Verified each caller handles the modified interface correctly
- [ ] Checked for callers in tests that may need updates
- [ ] Verified no callers make assumptions that the change invalidates

**Error Path Trace**
- [ ] Traced what happens when the function raises an exception
- [ ] Verified error propagation to appropriate handlers
- [ ] Checked that error messages are informative
- [ ] Verified cleanup/rollback occurs on failure paths

**Integration Point Verification**
- [ ] Identified components that this code integrates with
- [ ] Verified contracts with each integration point are maintained
- [ ] Checked for implicit assumptions about order of operations
- [ ] Verified async/await usage is correct through the call chain

### Part 2: Trace Documentation Requirements

Reviewers must include trace documentation in their review output:

```
## End-to-End Trace Summary

### Entry Points Analyzed
- [List each entry point traced]

### Callers Verified
- [List callers of modified functions and verification status]

### Error Paths Traced
- [List error conditions and how they propagate]

### Integration Points Checked
- [List integration points and verification status]
```

This documentation serves as evidence that the trace was performed and provides context for future reviewers.

### Part 3: Trace-Specific Questions

Add mandatory questions reviewers must answer:

1. **Data Flow**: "If I pass X as input at the entry point, what is the complete path to the output?"
2. **Failure Mode**: "If component Y fails, what happens to this operation?"
3. **Caller Impact**: "Function Z was modified. Who calls Z, and do they all still work correctly?"
4. **State Changes**: "What shared state does this code read or modify, and who else depends on that state?"

These questions cannot be answered without actually tracing the code.

## Technical Approach

### File Modifications

**Primary file: `.claude/roles/reviewer.md`**

Add new section "Step 3.5: End-to-End Trace" between current Step 3 (Review the Diff) and Step 4 (Run Tests). This section will contain:
- The trace requirements checklist
- Commands to find callers (grep patterns)
- Documentation template for trace summary
- Mandatory trace questions

**Update: Review Checklist section**

Add trace items to the existing checklist:
- [ ] Entry points traced and documented
- [ ] All callers of modified functions verified
- [ ] Error paths traced to handlers
- [ ] Integration points verified

**Update: Reporting Results section**

Modify the APPROVED template to include trace summary:
```
REVIEW RESULT: APPROVED

Summary: [Brief description of what was reviewed]
Files reviewed: [count]
Tests verified: [pass/fail status]

## Trace Summary
- Entry points: [list]
- Callers verified: [list]
- Error paths: [list]
- Integration points: [list]

No blocking issues found.
```

### Secondary Updates

**`.claude/roles/spec-reviewer.md`** and **`.claude/roles/proposal-reviewer.md`**

Add a lighter-weight trace requirement for specs and proposals:
- Verify that data flow is described
- Check that error handling strategy covers identified paths
- Ensure integration points are documented

This catches trace-related gaps earlier in the workflow.

### Helper Commands

Document grep/search patterns for common trace operations:

```bash
# Find all callers of a function
grep -rn "function_name(" src/ tests/

# Find all imports of a module
grep -rn "from module import\|import module" src/

# Find all exception handlers for a type
grep -rn "except.*ErrorType" src/
```

## Acceptance Criteria

1. `.claude/roles/reviewer.md` contains a new "End-to-End Trace" section with:
   - Data flow trace checklist items
   - Caller analysis checklist items
   - Error path trace checklist items
   - Integration point checklist items
   - Documentation template for trace summary
   - Mandatory trace questions

2. The main Review Checklist in `reviewer.md` includes trace verification items

3. The APPROVED report template includes trace summary documentation

4. `.claude/roles/spec-reviewer.md` includes trace-related review items for specs:
   - Data flow described
   - Error handling strategy documented
   - Integration points identified

5. `.claude/roles/proposal-reviewer.md` includes trace-related review items for proposals:
   - Data flow design is complete
   - Error propagation is defined
   - Integration contracts are specified

6. Helper grep/search patterns are documented for finding:
   - Function callers
   - Module imports
   - Exception handlers

7. The trace requirements are positioned in the workflow such that they occur BEFORE test verification (since traces may reveal test gaps)

## Out of Scope

- Automated tooling to perform traces (this is a process/checklist improvement, not a tool)
- Static analysis integration (e.g., call graph generators)
- Formal verification or theorem proving
- Changes to gate check automation (traces are reviewer responsibility, not automated)
- Trace requirements for non-code reviews (bug reports, changelogs)
- Training materials or tutorials (the checklist itself serves as guidance)
