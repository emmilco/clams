# SPEC-041: Shell/Hooks Gate Check Script

## Problem Statement

The gate check system currently runs Python checks (pytest, mypy, ruff) unconditionally, even for shell-only or hooks-only changes. This causes:
1. Wasted CI time running irrelevant checks
2. Misleading failures when Python checks don't apply
3. No actual validation of shell script quality

Session evidence shows gates ran Python checks for shell script changes in `clams/hooks/`, missing the opportunity to catch shellcheck warnings.

**Reference**: R14-C from bug pattern analysis (Theme T12: Workflow/Gate Script Brittleness)

## Proposed Solution

Create a dedicated shell/hooks gate check script that:
1. Runs `shellcheck` on changed shell scripts
2. Validates bash syntax with `bash -n`
3. Integrates with the gate dispatcher (SPEC-040) for automatic routing

## Acceptance Criteria

- [ ] New script `.claude/gates/check_linter_shell.sh` created
- [ ] Script runs `shellcheck -S warning` on changed `.sh` files
- [ ] Script runs `bash -n` syntax check on all shell files
- [ ] Script detects changed files via `git diff main...HEAD --name-only`
- [ ] Script handles `clams/hooks/*` files (even without `.sh` extension)
- [ ] Script returns 0 on success, 1 on failure
- [ ] Script handles case where shellcheck is not installed (warn, not fail)
- [ ] Script outputs clear results for each file checked
- [ ] Script is registered in `.claude/gates/registry.json` under `shell` type
- [ ] Gate dispatcher routes shell-type changes to this script

## Implementation Notes

File location: `.claude/gates/check_linter_shell.sh`

Key behaviors:
- Get changed files: `git diff main...HEAD --name-only -- '*.sh' 'clams/hooks/*'`
- Run shellcheck with warning severity: `shellcheck -S warning "$file"`
- Run bash syntax check: `bash -n "$file"`
- Graceful degradation if shellcheck unavailable

Shell files to check:
- Any `*.sh` file in the repository
- All files in `clams/hooks/` (even without extension)
- Files in `.claude/bin/` and `.claude/gates/`

## Testing Requirements

- Test with intentional shellcheck warnings (verify detection)
- Test with clean shell scripts (verify pass)
- Test with shellcheck unavailable (verify graceful warning)
- Test bash syntax errors are detected
- Integration test: create hooks-only worktree, run gate check

## Out of Scope

- Project type detection (covered by SPEC-040)
- Gate routing logic (covered by SPEC-040)
- Frontend check script (covered by SPEC-042)
