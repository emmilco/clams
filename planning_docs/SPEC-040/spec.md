# SPEC-040: Gate Type-Specific Routing

## Problem Statement

The CLAWS gate check system currently uses a monolithic routing approach embedded directly in `claws-gate`. While BUG-062 added project type auto-detection via `detect_project_type()` in `claws-common.sh`, the actual check scripts (e.g., `check_tests.sh`, `check_linter.sh`, `check_types.sh`) each implement their own internal detection logic with inline handlers for different project types.

This creates several issues:

1. **Code duplication**: Each check script re-implements project type detection and language-specific handling
2. **Inconsistent behavior**: Different scripts may detect project types differently or miss edge cases
3. **Difficult extensibility**: Adding support for a new language/framework requires modifying multiple scripts
4. **No modularity**: Shell scripts, CLAWS hooks, and frontend projects have no dedicated check scripts
5. **Mixed concerns**: Business logic (what to check) is mixed with routing logic (which tool to use)

### Current State

The existing check scripts have project type detection embedded:

- **check_tests.sh**: Detects Python/Node.js/Rust/Go via marker files, runs appropriate test command
- **check_linter.sh**: Detects Python/Node.js/Rust/Go, runs ruff/eslint/clippy/go vet
- **check_types.sh**: Detects Python/TypeScript, runs mypy/tsc
- **check_todos.sh**: Language-agnostic (searches common file extensions)
- **check_orphans.sh**: Primarily Python-focused (uses ruff)

Meanwhile, `claws-gate` already uses `detect_project_type()` for routing but duplicates the language-specific check invocation logic in large case statements.

## Goals

1. **Centralize routing logic**: Single point of truth for mapping project types to check scripts
2. **Enable type-specific check scripts**: Allow dedicated scripts for each project type
3. **Support composite projects**: Handle projects with multiple languages (e.g., Python backend + TypeScript frontend)
4. **Graceful fallbacks**: Provide sensible defaults when project type is unknown
5. **Easy extensibility**: Adding new project types should require minimal code changes
6. **Unblock shell/hooks and frontend support**: Enable SPEC-041 and SPEC-042

## Design

### 1. Check Script Interface

Each type-specific check script follows a standard interface:

```bash
# Usage: check_<category>_<type>.sh <worktree_path> [task_id]
# Returns: 0 on success, 1 on failure, 2 on skip (tool not available)
# Output: Human-readable progress and results to stdout
# Errors: Error messages to stderr
```

**Categories**:
- `tests` - Run test suite
- `linter` - Run linting/style checks
- `types` - Run type checking
- `todos` - Check for untracked TODOs
- `orphans` - Check for dead code

**Types** (detected by `detect_project_type()`):
- `python` - Python projects (pyproject.toml, setup.py, requirements.txt)
- `javascript` - JavaScript/TypeScript projects (package.json)
- `rust` - Rust projects (Cargo.toml)
- `go` - Go projects (go.mod)
- `shell` - Shell scripts (shebang detection or .sh files)
- `unknown` - Fallback for undetected types

### 2. Check Script Registry

A new configuration file defines the mapping from (category, type) to scripts:

**File**: `.claude/gates/registry.json`

```json
{
  "version": "1.0",
  "checks": {
    "tests": {
      "python": "check_tests_python.sh",
      "javascript": "check_tests_javascript.sh",
      "rust": "check_tests_rust.sh",
      "go": "check_tests_go.sh",
      "default": "check_tests_generic.sh"
    },
    "linter": {
      "python": "check_linter_python.sh",
      "javascript": "check_linter_javascript.sh",
      "rust": "check_linter_rust.sh",
      "go": "check_linter_go.sh",
      "shell": "check_linter_shell.sh",
      "default": "check_linter_generic.sh"
    },
    "types": {
      "python": "check_types_python.sh",
      "javascript": "check_types_javascript.sh",
      "rust": null,
      "go": null,
      "default": null
    },
    "todos": {
      "default": "check_todos.sh"
    },
    "orphans": {
      "python": "check_orphans_python.sh",
      "default": "check_orphans_generic.sh"
    }
  }
}
```

Note: Composite project detection is configured in `project.json` under `gate_config.composite_types`, not in the registry. This keeps project-specific configuration separate from the global check script registry.

**Key features**:
- `"default"` key provides fallback when no type-specific script exists
- `null` value means "skip this check for this type" (e.g., Rust/Go have built-in type checking)

### 3. Routing Logic

A new routing script handles the dispatch:

**File**: `.claude/bin/claws-gate-dispatch`

```bash
#!/usr/bin/env bash
#
# claws-gate-dispatch: Route gate checks to type-specific scripts
#
# Usage: claws-gate-dispatch <category> <worktree_path> [project_type]
#
# If project_type is not provided, auto-detects from worktree.
# Returns the exit code from the type-specific script.

# Implementation:
# 1. Load registry.json
# 2. Determine project type (provided or auto-detect)
# 3. Look up script: checks[category][type] or checks[category][default]
# 4. If null, return 0 (skip)
# 5. Execute script with worktree_path argument
# 6. Return script's exit code
```

### 4. Composite Project Handling

For projects with multiple languages (e.g., Python backend + TypeScript frontend):

1. **Primary type**: Detected at worktree root via `detect_project_type()`
2. **Secondary types**: Detected via `composite_detection.subdirs` in registry
3. **Check execution**: Run checks for each detected type
4. **Aggregation**: All checks must pass; run all checks regardless of individual failures, report aggregated results at the end

Example flow for CLAMS (Python + TypeScript):
```
claws-gate check TASK-001 IMPLEMENT-CODE_REVIEW
  -> detect_project_type: "python" (pyproject.toml found)
  -> check composite_detection.subdirs: clams-visualizer -> "javascript"
  -> Run python checks on worktree root
  -> Run javascript checks on clams-visualizer/
  -> Aggregate results
```

### 5. Shell Script Detection

Since shell scripts don't have a standard marker file, detection uses:

1. **Explicit configuration**: `project.json` with `"project_type": "shell"`
2. **Directory-based**: Configured `script_dirs` in `project.json` (e.g., `.claude/bin/`)
3. **Shebang detection**: Files with `#!/bin/bash` or `#!/usr/bin/env bash`

For CLAWS, the `.claude/bin/` and `scripts/` directories should be checked with `shellcheck`.

### 6. Updated claws-gate

The main `claws-gate` script is simplified to use the dispatcher:

```bash
# Before (current implementation):
case "$project_type" in
    python)
        run_gate "Tests pass" "check_tests.sh" "$worktree"
        run_gate "Linter clean" "check_linter.sh" "$worktree"
        run_gate "Type check" "check_types.sh" "$worktree"
        ;;
    javascript)
        # ... similar block ...
        ;;
esac

# After (new implementation):
claws-gate-dispatch tests "$worktree"
claws-gate-dispatch linter "$worktree"
claws-gate-dispatch types "$worktree"
```

### 7. Fallback Behavior

When project type is `unknown`:

1. **Tests**: Run generic script that tries common test runners (pytest, npm test, cargo test, go test)
2. **Linter**: Skip with warning
3. **Types**: Skip with warning
4. **TODOs**: Run generic TODO check (language-agnostic)
5. **Orphans**: Skip with warning

This ensures gates don't block on truly unknown project types while encouraging explicit configuration.

## File Structure

After implementation:

```
.claude/
  gates/
    registry.json              # Check script registry
    # Type-specific scripts
    check_tests_python.sh
    check_tests_javascript.sh
    check_tests_rust.sh
    check_tests_go.sh
    check_tests_generic.sh
    check_linter_python.sh
    check_linter_javascript.sh
    check_linter_rust.sh
    check_linter_go.sh
    check_linter_shell.sh
    check_linter_generic.sh
    check_types_python.sh
    check_types_javascript.sh
    check_todos.sh             # Language-agnostic
    check_orphans_python.sh
    check_orphans_generic.sh
  bin/
    claws-gate                 # Simplified, uses dispatcher
    claws-gate-dispatch        # New routing script
```

## Migration Path

1. **Phase 1**: Create `claws-gate-dispatch` and `registry.json`
2. **Phase 2**: Extract existing logic from check scripts into type-specific scripts
3. **Phase 3**: Update `claws-gate` to use dispatcher
4. **Phase 4**: Add shell/hooks support (SPEC-041)
5. **Phase 5**: Add frontend support (SPEC-042)

Existing scripts remain functional during migration for backwards compatibility.

## Configuration

### project.json Updates

Extend `.claude/project.json` to support explicit type configuration:

```json
{
  "project_type": "python",
  "implementation_dirs": ["src/", "clams-visualizer/"],
  "test_dirs": ["tests/"],
  "script_dirs": [".claude/bin/", "scripts/"],
  "frontend_dirs": ["clams-visualizer/"],
  "gate_config": {
    "composite_types": {
      "clams-visualizer": "javascript"
    },
    "skip_checks": [],
    "extra_checks": []
  }
}
```

**New fields**:
- `gate_config.composite_types`: Override automatic subdir type detection
- `gate_config.skip_checks`: Explicitly skip certain checks (e.g., `["types"]` for JS-only projects)
- `gate_config.extra_checks`: Additional custom check scripts to run

## Acceptance Criteria

### Must Have

1. [ ] `claws-gate-dispatch` script exists and routes to type-specific scripts
2. [ ] `registry.json` defines check script mappings for all categories and types
3. [ ] Type-specific scripts exist for Python, JavaScript, Rust, Go
4. [ ] Shell script linting is supported via `check_linter_shell.sh`
5. [ ] Unknown project types get sensible fallback behavior
6. [ ] `claws-gate` uses the new dispatcher for all automated checks
7. [ ] Existing functionality is preserved (no regression)
8. [ ] Composite project support works for CLAMS (Python + TypeScript frontend)

### Should Have

9. [ ] Documentation in `CLAUDE.md` updated to reflect new architecture
10. [ ] Migration is backwards-compatible (old scripts still work if called directly)
11. [ ] Check scripts follow consistent interface (exit codes, output format)

### Nice to Have

12. [ ] Per-task check overrides via task metadata
13. [ ] Parallel execution of independent checks
14. [ ] Check result caching (skip re-running if no relevant files changed)

## Dependencies

- **BUG-062** (completed): Project type auto-detection in `claws-common.sh`

## Blocked By

None.

## Unblocks

- **SPEC-041**: Shell/hooks gate check (can create `check_linter_shell.sh`)
- **SPEC-042**: Frontend gate check (can create JavaScript/TypeScript specific checks)

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Registry JSON parsing in bash is complex | Medium | Use simple grep/sed patterns or require jq dependency |
| Composite detection adds complexity | Low | Make it opt-in via configuration |
| Migration breaks existing gates | High | Phased rollout with backwards compatibility |
| Too many small scripts to maintain | Medium | Keep scripts focused; share common functions via sourcing |

## Open Questions (Resolved)

1. **Q**: Should `jq` be a required dependency for registry parsing?
   **Decision**: Yes. `jq` is required for robust JSON handling. The dispatcher will check for `jq` availability and provide a helpful error message with install instructions if missing.

2. **Q**: Should composite detection be automatic or require explicit configuration?
   **Decision**: Explicit configuration via `gate_config.composite_types` in `project.json`. This keeps behavior predictable and avoids surprises from automatic detection.

3. **Q**: How should check failures in composite projects be reported?
   **Decision**: Run all checks for all detected types, collect all failures, and report aggregated results at the end. This ensures all issues are surfaced in a single gate run.
