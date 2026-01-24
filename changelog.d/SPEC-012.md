## SPEC-012: Add End-to-End Trace to Reviewer Checklist

### Summary
Added mandatory end-to-end trace requirements to the code reviewer checklist to prevent integration bugs from incomplete data flow analysis.

### Changes
- Added Step 3.5 "End-to-End Trace" section to `.claude/roles/reviewer.md` with:
  - Data flow trace checklist (entry points, transformations, return value usage)
  - Caller analysis checklist (all callers identified and verified)
  - Error path trace checklist (exception propagation, cleanup)
  - Integration point verification checklist
  - Helper grep commands for finding callers, imports, and exception handlers
  - Documentation template for trace summary
- Updated APPROVED report template to include Trace Summary section
- Added trace-related items to spec-reviewer.md and proposal-reviewer.md Bug Pattern Prevention sections
