# SPEC-061 Proposal: Beta Hardening

## Problem Statement

CALM has never been installed on a machine other than the development machine. Before beta testing, we need to verify and fix the installation flow, documentation, and functionality so a new user can set up and use the system without hand-holding.

## Proposed Solution

8 subtasks, ordered by dependency. Tasks 01-03 are preparatory (fix what's broken), tasks 04-08 are verification (confirm things work). Several tasks can be parallelized.

## Task Dependency Graph

```
SPEC-061-01 (Install Flow)     ─┐
SPEC-061-02 (Hardcoded Paths)   ├─► SPEC-061-04 (MCP Verification)
SPEC-061-03 (Documentation)    ─┘   SPEC-061-05 (CLI Verification)
                                     SPEC-061-06 (Hooks/Skills)
                                     SPEC-061-07 (Daemon Lifecycle)
                                     SPEC-061-08 (First-Run Experience)
```

- **Phase 1** (sequential, must complete first): 01, 02, 03 — these fix things that the verification tasks depend on
- **Phase 2** (parallelizable): 04, 05, 06, 07, 08 — independent verification tasks

## Subtask Implementation Approach

### SPEC-061-01: Installation Flow Smoke Test

**Approach:**
1. Back up `~/.calm/` directory, `~/.claude.json`, and `~/.claude/settings.json` before any changes
2. Run `scripts/uninstall.sh` and verify clean removal
3. Run `scripts/install.sh` and verify all 10 install steps complete
4. Run `scripts/verify_install.py` to confirm
5. Fix any issues found in the install/uninstall scripts
6. Test each `--skip-*` flag in isolation
7. Test `--dry-run` flag
8. Run install twice to verify idempotence
9. Review error messages for missing prerequisites (simulate by temporarily renaming binaries or using a subshell with modified PATH)
10. Restore original `~/.calm/` from backup after testing

**Files likely touched:**
- `scripts/install.sh`
- `scripts/uninstall.sh`
- `src/calm/install/steps.py`
- `scripts/verify_install.py`

**Backup strategy:** Before any destructive operations, create a tarball of `~/.calm/`, snapshot of `~/.claude.json`, and `~/.claude/settings.json`. Restore after testing.

### SPEC-061-02: Hardcoded Path Audit

**Approach:**
1. `grep -r "/Users/elliotmilco" src/ scripts/ src/calm/templates/` to find all hardcoded paths
2. `grep -r "yourusername\|your-repo" .` to find placeholder URLs
3. Review `.claude/settings.local.json` for machine-specific paths
4. Fix any findings (replace with dynamic path resolution or clear placeholder instructions)
5. Verify hook registrations use `python -m` (not absolute python paths)

**Files likely touched:**
- `.claude/settings.local.json` (if machine-specific)
- `README.md` (if placeholder URL is there — but fix goes in SPEC-061-03)
- Any `src/` or `scripts/` files with hardcoded paths

### SPEC-061-03: Documentation Cleanup

**Approach:**
1. Delete stale files: `.claude/HANDOFF.md`, `REVIEW_ISSUES.md`
2. Move `.claude/CLAMS_DESIGN.md` to `planning_docs/archive/`
3. Count actual MCP tools registered in `src/calm/server/app.py` and update `docs/SYSTEM_AUDIT.md`
4. Run `pytest --co -q | tail -1` to get current test count, update `docs/SYSTEM_AUDIT.md`
5. Update `scripts/verify_calm_setup.md` tool list
6. Consolidate `changelog.d/*.md` into `CHANGELOG.md`, delete fragments
7. Create `LICENSE` file (MIT)
8. Review and fix README.md (clone URL, prerequisites, troubleshooting)

**Files touched:**
- `.claude/HANDOFF.md` (delete)
- `.claude/CLAMS_DESIGN.md` (move)
- `REVIEW_ISSUES.md` (delete)
- `docs/SYSTEM_AUDIT.md` (update counts)
- `scripts/verify_calm_setup.md` (update tool list)
- `CHANGELOG.md` (consolidate)
- `changelog.d/*.md` (delete after consolidation)
- `LICENSE` (create)
- `README.md` (fix)

### SPEC-061-04: MCP Tool Functional Verification

**Approach:**
1. Extract the list of all registered tools from `src/calm/server/app.py`
2. Cross-reference against test files in `tests/server/tools/`
3. Run full test suite: `pytest -vvsx`
4. Grep source for any stub responses (`not_implemented`, placeholder returns)
5. Identify and document any coverage gaps
6. Write missing tests if any tool category lacks coverage

**Files likely touched:** Test files only, if gaps found.

### SPEC-061-05: CLI Functional Verification

**Approach:**
1. Run `calm --help` and every subcommand `--help`
2. Run CLI test suite: `pytest tests/calm/test_cli_*.py -v`
3. Test critical paths manually (task create/show/list, worktree create/list, etc.)
4. Verify error messages for invalid arguments
5. Fix any issues found

**Files likely touched:** `src/calm/cli/` files if error handling needs improvement.

### SPEC-061-06: Hooks and Skills Verification

**Approach:**
1. Verify hook registration JSON is syntactically valid
2. Run hook test suite: `pytest tests/calm/hooks/ -v`
3. Test each hook with fixture input via stdin
4. Verify error handling (malformed input → log, not crash)
5. Verify skill files exist and are valid
6. Verify `skill-rules.json` is valid JSON

**Files likely touched:** Hook files if issues found.

### SPEC-061-07: Daemon Lifecycle

**Approach:**
1. Test start → status → stop → restart cycle
2. Kill daemon with `kill -9`, then verify `calm server start` recovers
3. Stop Qdrant container, start daemon, attempt operations — verify graceful error messages
4. Check `~/.calm/server.log` for useful diagnostics
5. Fix any issues found

**Files likely touched:** `src/calm/server/daemon.py`, `src/calm/server/main.py` if issues found.

### SPEC-061-08: First-Run Experience

**Approach:**
1. Check what happens when embedding models are not cached (review code paths in `src/calm/embedding/`)
2. Verify SessionStart hook output on first session
3. Walk through GETTING_STARTED.md as a new user would
4. Check `~/.calm/server.log` and `~/.calm/hook_errors.log` for first-run errors
5. Document any issues and fix

**Files likely touched:** Documentation, possibly `src/calm/embedding/` if download UX needs improvement.

## Alternatives Considered

1. **Automated E2E install test in Docker**: Would give true clean-machine validation, but adds Docker-in-Docker complexity and is overkill for a first beta with one tester.
2. **Skip verification tasks (04-08) and just fix obvious issues**: Too risky — the SPEC-058 stub incident proved that "it compiles" doesn't mean "it works."

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Uninstall/reinstall loses user data | Back up `~/.calm/` as tarball before any destructive operations |
| Install script changes break working system | Test in isolation, restore from backup |
| Documentation fixes introduce errors | Review diffs carefully |

## Implementation Order

1. SPEC-061-02 first (hardcoded paths — quick, informs other tasks)
2. SPEC-061-03 next (documentation — independent, can be large)
3. SPEC-061-01 next (install flow — depends on path fixes being done)
4. SPEC-061-04 through 08 in parallel (independent verification tasks)
