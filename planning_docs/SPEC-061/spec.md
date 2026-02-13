# SPEC-061: Beta Hardening — Installation, Documentation, and Functional Verification

## Summary

Prepare CALM for first beta installation on a fresh machine. No new features — focus entirely on ensuring everything that exists actually works, is well documented, and provides a good setup and user experience.

## Motivation

CALM has never been installed on a machine other than the development machine. Before beta testing, we need to:
1. Verify the installation flow works end-to-end from a clean state
2. Remove hardcoded paths and stale artifacts that would break or confuse a new user
3. Ensure documentation is accurate and sufficient for self-service setup
4. Confirm all advertised functionality actually works (not stubs)

## Scope

**In scope:**
- Installation flow verification and fixes
- Hardcoded path audit and remediation
- Stale documentation cleanup and accuracy updates
- Functional verification of MCP tools, CLI, hooks, skills, daemon
- Cross-machine portability checks
- Error message quality for common failure modes

**Out of scope:**
- New features or enhancements
- CI/CD setup (GitHub Actions, etc.)
- Performance optimization
- Multi-platform testing (Linux) — focus is macOS for now
- Contributing guide or external contributor workflows

## Subtasks

### SPEC-061-01: Installation Flow Smoke Test

**Goal:** Verify `scripts/install.sh` and `scripts/uninstall.sh` work end-to-end from a clean state.

**Acceptance Criteria:**
1. After running `uninstall.sh` followed by `install.sh`, the system is fully functional:
   - `~/.calm/` directory exists with all expected subdirs and files
   - `~/.calm/metadata.db` is initialized with schema
   - Qdrant Docker container is running on port 6333
   - MCP server entry exists in `~/.claude.json`
   - Hooks are registered in `~/.claude/settings.json`
   - Skills are installed in `~/.claude/skills/`
   - Daemon is running and `/health` responds
2. `scripts/verify_install.py` passes all checks
3. The install script provides clear, actionable error messages when prerequisites are missing:
   - Missing `uv`: prints install command (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
   - Missing Docker: prints install guidance and mentions `--skip-qdrant` option
   - Wrong Python version: prints required version (3.12+) and current version
4. The `--dry-run` flag accurately previews all steps without side effects
5. The `--skip-qdrant`, `--skip-hooks`, `--skip-mcp`, `--skip-server` flags each work correctly in isolation
6. Idempotent: running `install.sh` twice in a row does not corrupt state

**Verification Method:** Actually run uninstall → install cycle, inspect results.

### SPEC-061-02: Hardcoded Path and Machine-Specific Audit

**Goal:** Ensure no paths, usernames, or machine-specific values are baked into source, config, templates, or scripts.

**Acceptance Criteria:**
1. Zero occurrences of `/Users/elliotmilco` in any file under `src/`, `scripts/`, or template files
2. Zero occurrences of hardcoded home directories in shipped config templates (`src/calm/templates/`)
3. All paths in hook registrations (written by the installer) use the correct Python interpreter resolution, not a hardcoded path
4. `.claude/settings.local.json` (if shipped) does not contain machine-specific paths that would break on another machine

**Verification Method:** `grep -r` for hardcoded paths; review installer output for path correctness.

### SPEC-061-03: Documentation Cleanup and Accuracy

**Goal:** Remove stale docs, fix inaccuracies, and ensure a new user can self-service from README → GETTING_STARTED.

**Acceptance Criteria:**
1. Stale files removed or archived:
   - `.claude/HANDOFF.md` (Dec 2025 handoff) — deleted
   - `.claude/CLAMS_DESIGN.md` (old branding, deprecated bash refs) — moved to `planning_docs/archive/`
   - `REVIEW_ISSUES.md` (completed migration checklist) — deleted
2. `docs/SYSTEM_AUDIT.md` updated:
   - MCP tool count corrected (was 42, should reflect actual count after BUG-080 removed 5)
   - Test count updated to current
3. `scripts/verify_calm_setup.md` updated:
   - MCP tool list matches actual registered tools (remove references to deleted session tools)
4. `changelog.d/` fragments consolidated into `CHANGELOG.md`, fragments removed
5. `LICENSE` file created at repo root (MIT, matching README claim)
6. README.md reviewed for accuracy:
   - Clone URL fixed
   - Prerequisites section is correct and complete
   - Feature descriptions match actual functionality
   - Troubleshooting section covers the most common first-install issues

**Verification Method:** Read each updated document; verify tool count against actual server registration; confirm LICENSE exists.

### SPEC-061-04: MCP Tool Functional Verification

**Goal:** Confirm every registered MCP tool returns real results, not stubs or "not_implemented" responses.

**Acceptance Criteria:**
1. The full test suite passes with 0 failures, and test coverage exists for every tool category listed in AC2
2. The test suite covers the happy path for each tool category:
   - Memory tools: store, retrieve, list, delete
   - GHAP tools: start, update, resolve, get_active, list, search_experiences
   - Code tools: index_codebase, search_code, find_similar_code
   - Git tools: index_commits, search_commits, get_file_history, get_churn_hotspots, get_code_authors
   - Search tools: search (unified)
   - Clustering tools: get_clusters, get_cluster_members
   - Context tools: assemble_context
   - Value tools: validate_value, store_value, list_values
   - Journal tools: store_journal_entry, list_journal_entries, get_journal_entry, mark_entries_reflected
   - Health: ping
3. No tool returns `{"status": "not_implemented"}` or similar stub response
4. Full test suite passes: `pytest -vvsx` with 0 failures

**Verification Method:** Run full test suite; grep source for stub responses; spot-check MCP tool registration against test coverage.

### SPEC-061-05: CLI Functional Verification

**Goal:** Confirm every `calm` CLI subcommand works correctly.

**Acceptance Criteria:**
1. Every CLI subcommand listed in CLAUDE.md executes without errors:
   - `calm status`, `calm status health`, `calm status worktrees`
   - `calm task create/list/show/update/transition/delete/next-id`
   - `calm worktree create/list/path/merge/remove`
   - `calm gate check/list`
   - `calm worker start/complete/fail/list`
   - `calm review record/list/check/clear`
   - `calm counter list/get/set/increment`
   - `calm backup create/list/restore`
   - `calm session list/show`
   - `calm server start/stop/status/restart`
   - `calm init`, `calm install --dry-run`
2. `--help` works for every subcommand and subgroup
3. Error messages for invalid arguments are clear (not raw Python tracebacks)
4. Tests exist covering CLI commands (in `tests/calm/test_cli_*.py`)

**Verification Method:** Run each command with `--help`; run the CLI test suite; manually test critical paths.

### SPEC-061-06: Hooks and Skills Verification

**Goal:** Confirm hooks fire correctly and skills load in a Claude Code session.

**Acceptance Criteria:**
1. Hook registration in `~/.claude/settings.json` is syntactically correct and matches the expected schema
2. Each hook can be invoked standalone without errors:
   - `python -m calm.hooks.session_start` (with appropriate stdin)
   - `python -m calm.hooks.user_prompt_submit`
   - `python -m calm.hooks.pre_tool_use`
   - `python -m calm.hooks.post_tool_use`
3. Hook error handling works: malformed input produces a log entry in `~/.calm/hook_errors.log`, not a crash
4. Skill files exist and are syntactically valid:
   - `~/.claude/skills/orchestrate/SKILL.md`
   - `~/.claude/skills/wrapup/SKILL.md`
   - `~/.claude/skills/reflection/SKILL.md`
5. `~/.claude/skills/skill-rules.json` is valid JSON with correct trigger patterns
6. All hook tests pass: `pytest tests/calm/hooks/ -v`

**Verification Method:** Run hook test suite; invoke hooks with test fixtures; verify skill file existence and JSON validity.

### SPEC-061-07: Daemon Lifecycle and Error Recovery

**Goal:** Confirm the daemon starts, stops, restarts cleanly and recovers from common failure modes.

**Acceptance Criteria:**
1. `calm server start` → `calm server status` shows running → `calm server stop` cleanly terminates
2. `calm server restart` works (stop + start cycle)
3. After daemon crash (kill -9), `calm server start` recovers:
   - Stale PID file is detected and cleaned up
   - New daemon starts successfully
4. When Qdrant is not running, the daemon starts but operations that need Qdrant fail with actionable error messages (not silent failures or cryptic stack traces)
5. The SessionStart hook auto-start works: if daemon is not running, hook starts it and waits (up to 5s timeout)
6. `~/.calm/server.log` contains useful diagnostic information on startup and errors

**Verification Method:** Manual daemon lifecycle test; kill -9 recovery test; stop Qdrant and observe behavior.

### SPEC-061-08: First-Run Experience

**Goal:** Ensure the very first run after installation provides a smooth experience, including model downloads.

**Acceptance Criteria:**
1. First-time embedding model download:
   - MiniLM and Nomic models download successfully on first use
   - The user gets some indication that models are downloading (not a hung terminal)
   - If download fails (network issue), the error message is clear
2. First Claude Code session after install:
   - SessionStart hook fires and prints "CALM is available" message
   - MCP tools are accessible (test with a simple `ping`)
   - Skills appear in the skill list
3. The GETTING_STARTED.md accurately describes what a new user will see and should do first
4. No first-run errors in `~/.calm/server.log` or `~/.calm/hook_errors.log`

**Verification Method:** Simulate first-run by clearing model cache; open fresh Claude Code session; follow GETTING_STARTED.md.

## Non-Goals

- Adding GitHub Actions CI/CD
- Linux or Windows compatibility testing
- Performance benchmarks
- New user onboarding tutorial or video
- Contributing guide

## Risk

- **Uninstall/reinstall cycle may lose data**: The uninstall script should warn about `~/.calm/metadata.db` before deleting
- **Model downloads require internet**: Beta tester needs internet on first run; no offline mode
- **Docker Desktop requirement**: Some users may not have Docker; `--skip-qdrant` path needs to work cleanly but vector search won't function
