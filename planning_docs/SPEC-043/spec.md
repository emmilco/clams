# SPEC-043: Update Valid Implementation Directories (R14-E)

## Background

The gate script's "Implementation code exists" check validates that changes include actual implementation code, not just configuration or documentation. The valid directories are configured in `.claude/project.json`, but when the check fails, the error message doesn't clearly communicate what directories are valid or where the configuration comes from.

## Problem Statement

The "Implementation code exists" check in `claws-gate`:
1. Reads directories from `.claude/project.json` configuration
2. Provides unclear error messages when check fails
3. Doesn't explain the directory configuration source
4. Same error message used regardless of why check failed

When developers make changes only to documentation or configuration, the error message doesn't clearly explain what counts as implementation code or how to check the configuration.

## Goals

1. Update error messages to clearly list valid implementation directories from config
2. Reference the configuration file in error messages
3. Provide helpful guidance for common scenarios
4. Update both feature (IMPLEMENT-CODE_REVIEW) and bug (INVESTIGATED-FIXED) transitions

## Non-Goals

- Changing which directories are valid (configured in project.json)
- Changing the detection logic (already works correctly)
- Modifying project type detection (done in SPEC-040)

## Current Configuration

From `.claude/project.json`:
```json
{
  "implementation_dirs": ["src/", "clams-visualizer/", ".claude/bin/", ".claude/gates/", ".claude/roles/"],
  "test_dirs": ["tests/"],
  "script_dirs": [".claude/bin/", "scripts/"],
  "doc_dirs": ["docs/", "planning_docs/", "bug_reports/"],
  "frontend_dirs": ["clams-visualizer/"]
}
```

## Solution Overview

### Error Message Updates

Update the "Implementation code exists" check to provide clearer error messages:

**Current:**
```bash
if [[ -z "$code_changes" ]]; then
    echo "✗ Implementation code exists: FAIL"
    echo ""
    echo "No changes found in configured implementation directories: $all_impl_dirs"
    echo "The task appears to have only documentation changes."
    failed=1
fi
```

**Updated:**
```bash
if [[ -z "$code_changes" ]]; then
    echo ""
    echo "✗ Implementation code exists: FAIL"
    echo ""
    echo "No implementation code found. Valid directories (from .claude/project.json):"
    echo ""
    echo "  Implementation: $(get_impl_dirs)"
    echo "  Tests:          $(get_test_dirs)"
    echo ""
    echo "Excluded directories (docs/config only):"
    echo "  - planning_docs/"
    echo "  - bug_reports/"
    echo "  - docs/"
    echo "  - CLAUDE.md, README.md, etc."
    echo ""
    echo "Your changes appear to be documentation or configuration only."
    failed=1
fi
```

### Bug Transition Updates

The INVESTIGATED-FIXED transition has similar check logic. Update it with the same improved error messages.

## Acceptance Criteria

- [ ] IMPLEMENT-CODE_REVIEW check has clear error message listing valid directories
- [ ] Error message references `.claude/project.json` as configuration source
- [ ] Error message shows both implementation and test directories
- [ ] Error message lists common excluded directories
- [ ] INVESTIGATED-FIXED check has matching improved error message
- [ ] Changes to `src/`, `tests/`, `.claude/bin/` pass the check
- [ ] Changes to only `planning_docs/` or `CLAUDE.md` correctly fail the check

## Testing Requirements

- Verify implementation-only changes pass the check
- Verify documentation-only changes fail with clear error message
- Verify error message accurately reflects project.json configuration
- Test that changes to `.claude/bin/` and `.claude/gates/` pass (they're in implementation_dirs)

## Dependencies

- SPEC-040 (Gate type-specific routing) - DONE (provides detect_project_type)

## References

- Session evidence showing unclear gate errors
- R14-E in `planning_docs/tickets/recommendations-r14-r17.md`
