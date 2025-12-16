# SPEC-040: Gate Type-Specific Routing - Technical Proposal

## Problem Statement

The current CLAWS gate system has duplicated project type detection logic. While `claws-common.sh` provides a centralized `detect_project_type()` function (added in BUG-062), the actual check scripts (`check_tests.sh`, `check_linter.sh`, `check_types.sh`) each re-implement their own detection via inline conditionals. Additionally, `claws-gate` itself contains large case statements that route to the same generic check scripts regardless of project type.

This causes:
1. **Code duplication**: Each script duplicates detection and language-specific logic
2. **Maintenance burden**: Adding a new language requires modifying 5+ files
3. **No extensibility path**: Shell scripts and frontends have no dedicated checks
4. **Mixed concerns**: Routing logic is interleaved with check execution

## Proposed Solution

Introduce a **dispatcher pattern** with a JSON registry that maps `(category, project_type)` pairs to type-specific check scripts. The dispatcher uses the centralized `detect_project_type()` function and looks up the appropriate script from the registry.

### Architecture Overview

```
claws-gate
    |
    v
claws-gate-dispatch <category> <worktree> [type]
    |
    +--> reads registry.json
    +--> calls detect_project_type() if type not provided
    +--> looks up: checks[category][type] or checks[category][default]
    +--> executes: .claude/gates/check_<category>_<type>.sh <worktree>
    |
    v
Type-specific script (e.g., check_tests_python.sh)
```

### Key Design Decisions

1. **JSON Registry over code-based routing**: A declarative registry is easier to maintain, extend, and reason about than nested case statements.

2. **jq as required dependency**: The spec raised this as an open question. We will require `jq` because:
   - Robust JSON parsing in pure bash is error-prone
   - `jq` is available in most CI environments
   - We can provide a clear error message if missing

3. **Explicit composite configuration**: The spec asked whether composite detection should be automatic or explicit. We choose explicit configuration via `gate_config.composite_types` in `project.json` to avoid surprises and keep behavior predictable.

4. **Preserve existing scripts**: Type-specific scripts are extracted from existing logic, not rewritten. This minimizes risk and ensures behavioral continuity.

5. **Progressive migration**: `claws-gate` will be updated incrementally. Initially, it can call the dispatcher alongside existing logic, allowing validation before full cutover.

## Alternative Approaches Considered

### Alternative 1: Symlink-based Routing

Use symlinks to map generic names to type-specific scripts:
```
check_tests.sh -> check_tests_python.sh  (based on project type)
```

**Rejected because**:
- Requires modifying symlinks dynamically at runtime
- Complex worktree handling (each worktree would need different symlinks)
- Difficult to support composite projects
- Less explicit and harder to debug

### Alternative 2: Single Unified Script with Functions

One large script with type-specific functions:
```bash
run_tests_python() { ... }
run_tests_javascript() { ... }
# etc.
```

**Rejected because**:
- Creates a monolithic script that's hard to maintain
- No clear ownership or separation of concerns
- Difficult to test individual components
- Doesn't scale well as languages are added

### Alternative 3: Plugin Directory Convention

Scripts in `gates/plugins/<type>/` auto-discovered at runtime:
```
gates/plugins/python/tests.sh
gates/plugins/python/linter.sh
gates/plugins/javascript/tests.sh
```

**Rejected because**:
- More complex directory structure
- No central registry means no explicit fallback handling
- Harder to see at a glance what checks exist
- Complicates the "skip this check" use case (null in registry)

## File/Module Structure

### New Files

```
.claude/
  gates/
    registry.json                    # Check script mappings

    # Python checks (extracted from existing scripts)
    check_tests_python.sh           # pytest runner with result logging
    check_linter_python.sh          # ruff/flake8
    check_types_python.sh           # mypy --strict
    check_orphans_python.sh         # ruff F401/F841

    # JavaScript/TypeScript checks
    check_tests_javascript.sh       # npm test / jest / vitest
    check_linter_javascript.sh      # eslint
    check_types_javascript.sh       # tsc --noEmit

    # Rust checks
    check_tests_rust.sh             # cargo test
    check_linter_rust.sh            # cargo clippy

    # Go checks
    check_tests_go.sh               # go test ./...
    check_linter_go.sh              # go vet + staticcheck

    # Shell checks (NEW - unblocks SPEC-041)
    check_linter_shell.sh           # shellcheck

    # Generic fallbacks
    check_tests_generic.sh          # Try common runners
    check_linter_generic.sh         # Skip with warning
    check_orphans_generic.sh        # Basic file checks

    # Language-agnostic (unchanged)
    check_todos.sh                  # TODO pattern matching

  bin/
    claws-gate-dispatch             # NEW: routing script
```

### Modified Files

```
.claude/
  bin/
    claws-gate                      # Simplified to use dispatcher
  project.json                      # Add gate_config section
```

### Registry Format

```json
{
  "$schema": "registry-schema.json",
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

### project.json Extension

```json
{
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

## Check Script Interface

All type-specific scripts follow a standard interface:

```bash
#!/usr/bin/env bash
#
# check_<category>_<type>.sh: <description>
#
# Usage: check_<category>_<type>.sh <worktree_path> [task_id]
#
# Arguments:
#   worktree_path - Path to the worktree (required)
#   task_id       - Task ID for logging (optional, inferred from worktree)
#
# Exit codes:
#   0 - Check passed
#   1 - Check failed (issues found)
#   2 - Check skipped (tool not available, warning printed)
#
# Output:
#   stdout - Human-readable progress and results
#   stderr - Error messages and warnings
#
# Expected behavior:
#   - Must cd to worktree_path before running checks
#   - Must source claws-common.sh for shared configuration
#   - Should log results to database if applicable (test_runs table)
#   - Must print clear PASS/FAIL/SKIP status at end

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$(dirname "$SCRIPT_DIR")/bin/claws-common.sh"

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

# ... check implementation ...

if [[ $passed ]]; then
    echo "PASS: <check name>"
    exit 0
else
    echo "FAIL: <check name>"
    exit 1
fi
```

## Dispatcher Implementation

```bash
#!/usr/bin/env bash
#
# claws-gate-dispatch: Route gate checks to type-specific scripts
#
# Usage: claws-gate-dispatch <category> <worktree_path> [project_type]
#
# Arguments:
#   category     - Check category (tests, linter, types, todos, orphans)
#   worktree_path - Path to the worktree
#   project_type  - Optional override (auto-detected if not provided)
#
# Exit codes:
#   Returns the exit code from the type-specific script
#   Returns 0 if check is configured as null (skip)
#   Returns 1 if category not found or script missing

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/claws-common.sh"

usage() {
    echo "Usage: claws-gate-dispatch <category> <worktree_path> [project_type]"
    echo ""
    echo "Categories: tests, linter, types, todos, orphans"
    exit 1
}

[[ $# -lt 2 ]] && usage

CATEGORY="$1"
WORKTREE="$2"
PROJECT_TYPE="${3:-}"

# Verify jq is available
if ! command -v jq &>/dev/null; then
    echo "Error: jq is required for gate dispatch" >&2
    echo "Install with: brew install jq (macOS) or apt install jq (Linux)" >&2
    exit 1
fi

REGISTRY="$GATES_DIR/registry.json"

if [[ ! -f "$REGISTRY" ]]; then
    echo "Error: Registry not found at $REGISTRY" >&2
    exit 1
fi

# Auto-detect project type if not provided
if [[ -z "$PROJECT_TYPE" ]]; then
    PROJECT_TYPE=$(detect_project_type "$WORKTREE")
fi

echo "Dispatching: category=$CATEGORY type=$PROJECT_TYPE"

# Look up script in registry: checks[category][type] or checks[category][default]
SCRIPT=$(jq -r --arg cat "$CATEGORY" --arg type "$PROJECT_TYPE" \
    '.checks[$cat][$type] // .checks[$cat]["default"] // "NOTFOUND"' \
    "$REGISTRY")

if [[ "$SCRIPT" == "null" ]]; then
    echo "Skip: $CATEGORY check not applicable for $PROJECT_TYPE"
    exit 0
fi

if [[ "$SCRIPT" == "NOTFOUND" || -z "$SCRIPT" ]]; then
    echo "Error: No script configured for category=$CATEGORY type=$PROJECT_TYPE" >&2
    exit 1
fi

SCRIPT_PATH="$GATES_DIR/$SCRIPT"

if [[ ! -x "$SCRIPT_PATH" ]]; then
    echo "Error: Script not found or not executable: $SCRIPT_PATH" >&2
    exit 1
fi

# Execute the type-specific script
exec "$SCRIPT_PATH" "$WORKTREE"
```

## Composite Project Handling

For projects with multiple languages (e.g., Python backend + TypeScript frontend), the dispatcher is called multiple times:

```bash
# In claws-gate, after detecting composite configuration:

# Run checks for primary type (detected at root)
claws-gate-dispatch tests "$worktree"
claws-gate-dispatch linter "$worktree"
claws-gate-dispatch types "$worktree"

# Run checks for composite subdirectories
for subdir in $(jq -r '.gate_config.composite_types | keys[]' "$PROJECT_CONFIG"); do
    subtype=$(jq -r --arg d "$subdir" '.gate_config.composite_types[$d]' "$PROJECT_CONFIG")
    subpath="$worktree/$subdir"

    if [[ -d "$subpath" ]]; then
        echo "=== Checking composite subdir: $subdir ($subtype) ==="
        claws-gate-dispatch tests "$subpath" "$subtype"
        claws-gate-dispatch linter "$subpath" "$subtype"
        claws-gate-dispatch types "$subpath" "$subtype"
    fi
done
```

## Test Strategy

### Unit Tests

1. **Dispatcher logic**: Test registry lookup with various category/type combinations
2. **Registry validation**: Test that all referenced scripts exist and are executable
3. **Project type detection**: Test `detect_project_type()` with various marker files

### Integration Tests

1. **Python project**: Full gate check on a Python worktree
2. **JavaScript project**: Full gate check on a JavaScript worktree
3. **Composite project**: Gate check on project with Python + TypeScript subdirectory
4. **Unknown type**: Verify fallback behavior with no marker files
5. **Shell scripts**: Verify shellcheck runs on `.claude/bin/` scripts

### Test Implementation

```python
# tests/test_gate_dispatch.py

import subprocess
import tempfile
import json
from pathlib import Path

def test_dispatcher_python_detection(tmp_path):
    """Dispatcher routes Python project to Python scripts."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
    result = subprocess.run(
        [".claude/bin/claws-gate-dispatch", "linter", str(tmp_path)],
        capture_output=True, text=True
    )
    assert "check_linter_python.sh" in result.stdout or result.returncode == 0

def test_dispatcher_javascript_detection(tmp_path):
    """Dispatcher routes JavaScript project to JS scripts."""
    (tmp_path / "package.json").write_text('{"name": "test"}')
    result = subprocess.run(
        [".claude/bin/claws-gate-dispatch", "linter", str(tmp_path)],
        capture_output=True, text=True
    )
    assert "check_linter_javascript.sh" in result.stdout or result.returncode == 0

def test_dispatcher_null_skip():
    """Dispatcher returns 0 for null-configured checks."""
    # Types check for Go is null (Go has built-in type checking)
    # Create a Go project and verify types check is skipped
    ...

def test_registry_scripts_exist():
    """All scripts referenced in registry.json exist and are executable."""
    registry = json.loads(Path(".claude/gates/registry.json").read_text())
    for category, mappings in registry["checks"].items():
        for project_type, script in mappings.items():
            if script is not None:
                script_path = Path(".claude/gates") / script
                assert script_path.exists(), f"Missing: {script_path}"
                assert script_path.stat().st_mode & 0o111, f"Not executable: {script_path}"
```

## Migration Plan

### Phase 1: Foundation (This Spec)

1. Create `registry.json` with mappings for existing project types
2. Create `claws-gate-dispatch` script
3. Extract Python-specific logic into `check_*_python.sh` scripts
4. Create generic fallback scripts
5. Update `claws-gate` to use dispatcher (with validation against existing behavior)

### Phase 2: Additional Languages

1. Extract JavaScript/TypeScript logic into `check_*_javascript.sh`
2. Extract Rust logic into `check_*_rust.sh`
3. Extract Go logic into `check_*_go.sh`
4. Update registry with new mappings

### Phase 3: Shell Support (SPEC-041)

1. Create `check_linter_shell.sh` (shellcheck wrapper)
2. Add `shell` mappings to registry
3. Update `detect_project_type()` to detect shell projects
4. Document shell project configuration

### Phase 4: Frontend Support (SPEC-042)

1. Enhance JavaScript checks for frontend patterns
2. Add composite detection for frontend subdirectories
3. Document frontend project configuration

### Backwards Compatibility

During migration:
- Existing `check_*.sh` scripts remain functional (can be called directly)
- `claws-gate` continues to work with or without dispatcher
- No changes to external interfaces (gate check command syntax unchanged)

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| jq not available in all environments | Medium | Low | Clear error message with install instructions; could add pure-bash fallback for simple lookups |
| Breaking existing gate behavior | High | Low | Extensive testing; phased rollout; keep old logic as fallback |
| Registry JSON becomes complex | Low | Low | Schema validation; documentation; keep structure flat |
| Performance overhead from dispatcher | Low | Very Low | Single jq call + exec; negligible compared to actual checks |

## Open Questions Resolved

1. **Q**: Should jq be a required dependency?
   **A**: Yes. Added with clear error message and install instructions.

2. **Q**: Should composite detection be automatic or explicit?
   **A**: Explicit via `gate_config.composite_types` in project.json.

3. **Q**: How should check failures in composite projects be reported?
   **A**: Run all checks, collect all failures, report aggregated results. This is handled in `claws-gate`, not the dispatcher.

## Success Criteria

1. `claws-gate-dispatch` correctly routes to type-specific scripts
2. All existing gate check functionality preserved (no regressions)
3. Adding a new project type requires only:
   - Creating type-specific scripts
   - Adding entries to registry.json
   - Updating `detect_project_type()` if needed
4. Shell linting (`check_linter_shell.sh`) works for `.claude/bin/` scripts
5. Composite project support works for CLAMS (Python + TypeScript visualizer)
