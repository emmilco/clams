# SPEC-043: Technical Proposal - Update Valid Implementation Directories

## Overview

This proposal details improvements to the "Implementation code exists" gate check error messages in `claws-gate`. When the check fails, the current error messages are unclear about what directories are valid and where the configuration comes from. This proposal adds clear, actionable error messages that reference the configuration source and list both valid and excluded directories.

## Implementation Details

### Files to Modify

1. **`.claude/bin/claws-gate`** - Update error messages in two locations:
   - `IMPLEMENT-CODE_REVIEW` transition (feature workflow)
   - `INVESTIGATED-FIXED` transition (bug workflow)

### Code Changes

#### 1. IMPLEMENT-CODE_REVIEW Transition (lines 434-445)

**Current code:**
```bash
if [[ -z "$code_changes" ]]; then
    echo "✗ Implementation code exists: FAIL"
    echo ""
    echo "No changes found in configured implementation directories: $all_impl_dirs"
    echo "The task appears to have only documentation changes."
    failed=1
else
    echo "✓ Implementation code exists: PASS"
    echo "Changed files:"
    echo "$code_changes" | sed 's/^/  /'
fi
```

**Updated code:**
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
else
    echo "✓ Implementation code exists: PASS"
    echo "Changed files:"
    echo "$code_changes" | sed 's/^/  /'
fi
```

#### 2. INVESTIGATED-FIXED Transition (lines 564-573)

**Current code:**
```bash
if [[ -z "$code_changes" ]]; then
    echo "✗ Implementation code exists: FAIL"
    echo ""
    echo "No changes found in configured directories: $all_impl_dirs"
    failed=1
else
    echo "✓ Implementation code exists: PASS"
    echo "Changed files:"
    echo "$code_changes" | sed 's/^/  /'
fi
```

**Updated code:**
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
    echo "Bug fixes must include implementation changes in valid directories."
    failed=1
else
    echo "✓ Implementation code exists: PASS"
    echo "Changed files:"
    echo "$code_changes" | sed 's/^/  /'
fi
```

### Key Design Decisions

1. **Reference `.claude/project.json` explicitly** - The error message tells users exactly where to look if they need to modify the configuration.

2. **Use existing helper functions** - `get_impl_dirs()` and `get_test_dirs()` already exist and handle configuration loading with fallbacks. Calling them in the error message ensures the displayed directories match what the check actually uses.

3. **List common excluded directories** - Rather than dynamically reading `doc_dirs` from config, we hardcode the common exclusions (`planning_docs/`, `bug_reports/`, `docs/`, `CLAUDE.md`). This is simpler and these are unlikely to change.

4. **Add extra context for bug workflow** - The INVESTIGATED-FIXED error includes an additional line reminding that bug fixes must include implementation changes, since this is a common mistake.

5. **Consistent formatting** - Both error messages use the same format for consistency. The extra blank line before the failure message improves readability.

### No Changes Needed to Detection Logic

The detection logic itself is correct and reads from `project.json`. Only the error messages need updating. The current directories in `project.json` are:
- `implementation_dirs`: `src/`, `clams-visualizer/`, `.claude/bin/`, `.claude/gates/`, `.claude/roles/`
- `test_dirs`: `tests/`

## Testing Strategy

### Manual Testing

1. **Test error message with documentation-only changes:**
   ```bash
   # In a worktree, make a change to planning_docs only
   echo "test" >> planning_docs/SPEC-XXX/spec.md
   git add -A && git commit -m "test doc change"

   # Run gate check - should fail with clear error message
   .claude/bin/claws-gate check SPEC-XXX IMPLEMENT-CODE_REVIEW
   ```

   Expected output should include:
   - "No implementation code found. Valid directories (from .claude/project.json):"
   - List of implementation dirs (src/, clams-visualizer/, etc.)
   - List of test dirs (tests/)
   - List of excluded directories
   - "Your changes appear to be documentation or configuration only."

2. **Test error message for bug workflow:**
   ```bash
   # In a bug worktree, make a doc-only change
   echo "test" >> bug_reports/BUG-XXX.md
   git add -A && git commit -m "test bug doc change"

   # Run gate check - should fail with clear error message
   .claude/bin/claws-gate check BUG-XXX INVESTIGATED-FIXED
   ```

3. **Test passing case still works:**
   ```bash
   # Make a change to src/ or tests/
   # Gate should pass with "Implementation code exists: PASS"
   ```

4. **Verify displayed directories match config:**
   - Check that the directories shown in error messages match `.claude/project.json`
   - If config is modified, error messages should reflect the changes

### Automated Testing

The gate check scripts are bash utilities that are difficult to unit test directly. The recommended approach is:

1. Create a test script that:
   - Sets up a mock worktree with only doc changes
   - Runs the gate check and captures output
   - Verifies expected strings appear in output

However, given the simplicity of this change (string formatting only), manual testing during implementation is sufficient.

## Risks and Mitigations

### Risk 1: Helper functions return unexpected format

**Risk:** `get_impl_dirs()` and `get_test_dirs()` could return empty strings or malformed output if `project.json` is missing or invalid.

**Mitigation:** These functions already have fallback defaults (`src/ tests/` and `tests/` respectively). Even if config is missing, the error message will display sensible defaults.

### Risk 2: Hardcoded excluded directories become stale

**Risk:** If `doc_dirs` in project.json changes, the error message's excluded directories list won't automatically update.

**Mitigation:**
- The excluded directories are conceptual guidance, not a strict list
- The important part is the valid directories (which come from config)
- If needed in the future, we could add a `get_doc_dirs()` helper

### Risk 3: Error message too verbose

**Risk:** The longer error message might be harder to scan quickly.

**Mitigation:**
- The message is structured with clear sections and indentation
- Key information (valid directories, config location) is at the top
- This verbosity is only shown on failure, when users need the detail

## Summary

This is a straightforward change that improves user experience when the "Implementation code exists" gate check fails. The changes are limited to error message formatting in two locations within `claws-gate`. No functional changes to the detection logic are needed.

Estimated implementation time: 15-30 minutes
