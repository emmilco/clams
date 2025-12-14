# Recommendation Tickets: R14-R17

These tickets implement workflow and testing improvements identified in the bug pattern analysis. See `planning_docs/bug-pattern-analysis.md` for full context.

---

## R14: Gate Script Auto-Detection

**Context**: Gate scripts currently assume a Python project structure and run pytest/mypy for all changes. This fails for hooks-only changes (shell scripts) and frontend-only changes (clams-visualizer). Session evidence shows gates didn't recognize `clams/` as valid implementation code and ran Python checks for shell script changes.

**Evidence**:
- Session `64997087`: Gate didn't recognize `clams/` as valid implementation code
- Session `df8f0602`: Gate hardcoded for Python projects, ran pytest/mypy for shell script changes
- Theme T12: Workflow/Gate Script Brittleness

---

### R14-A: Implement Project Type Detection Function

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
The `claws-gate` script has no mechanism to detect what type of project/changes are being gated. It runs Python checks (pytest, mypy, ruff) unconditionally, which is wasteful for non-Python changes and can produce misleading failures.

**Acceptance Criteria**:
- [ ] New function `detect_project_type()` added to `.claude/bin/claws-gate`
- [ ] Function detects: `python`, `frontend`, `hooks`, `shell`, `mixed`
- [ ] Detection based on changed files in `git diff main...HEAD --name-only`
- [ ] Python detected when `src/*.py` or `tests/*.py` files changed
- [ ] Frontend detected when `clams-visualizer/` files changed
- [ ] Hooks detected when `clams/hooks/` files changed
- [ ] Shell detected when only `.sh` files changed
- [ ] Mixed detected when multiple types are present
- [ ] Function is unit-testable (can be sourced and called independently)

**Implementation Notes**:

File: `.claude/bin/claws-gate`

Add after line 18 (after sourcing common):
```bash
# Detect project type based on changed files
detect_project_type() {
    local worktree="${1:-.}"
    local changes
    changes=$(cd "$worktree" && git diff main...HEAD --name-only 2>/dev/null || echo "")

    local has_python=0
    local has_frontend=0
    local has_hooks=0
    local has_shell=0

    while IFS= read -r file; do
        [[ -z "$file" ]] && continue
        case "$file" in
            src/*.py|tests/*.py) has_python=1 ;;
            clams-visualizer/*) has_frontend=1 ;;
            clams/hooks/*) has_hooks=1 ;;
            *.sh) has_shell=1 ;;
        esac
    done <<< "$changes"

    local types=0
    [[ $has_python -eq 1 ]] && ((types++))
    [[ $has_frontend -eq 1 ]] && ((types++))
    [[ $has_hooks -eq 1 ]] && ((types++))
    [[ $has_shell -eq 1 && $has_python -eq 0 && $has_frontend -eq 0 && $has_hooks -eq 0 ]] && ((types++))

    if [[ $types -gt 1 ]]; then
        echo "mixed"
    elif [[ $has_python -eq 1 ]]; then
        echo "python"
    elif [[ $has_frontend -eq 1 ]]; then
        echo "frontend"
    elif [[ $has_hooks -eq 1 ]]; then
        echo "hooks"
    elif [[ $has_shell -eq 1 ]]; then
        echo "shell"
    else
        echo "unknown"
    fi
}
```

**Testing Requirements**:
- Create test script `.claude/tests/test_gate_detection.sh` that:
  - Sources `claws-gate` to get the function
  - Mocks `git diff` output for various scenarios
  - Verifies correct type detection for each case
- Manual verification: create a hooks-only change and verify detection

---

### R14-B: Add Type-Specific Gate Routing

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: R14-A

**Problem Statement**:
Even with project type detection, the gate script needs to route to appropriate checks based on the detected type. Currently the `IMPLEMENT-CODE_REVIEW` transition always runs Python checks.

**Acceptance Criteria**:
- [ ] `IMPLEMENT-CODE_REVIEW` transition uses `detect_project_type()` result
- [ ] Python projects run: pytest, mypy, ruff, TODO check
- [ ] Frontend projects run: npm lint, npm test (if applicable)
- [ ] Hooks projects run: shellcheck, basic syntax validation
- [ ] Shell projects run: shellcheck
- [ ] Mixed projects run all applicable checks
- [ ] Each check type has clear skip message when not applicable
- [ ] Gate output clearly states which checks were run and why

**Implementation Notes**:

File: `.claude/bin/claws-gate`

Refactor the `IMPLEMENT-CODE_REVIEW` case (lines 267-331) to:

```bash
IMPLEMENT-CODE_REVIEW)
    echo ""
    # Check for actual implementation code (keep existing logic)
    # ...

    local project_type
    project_type=$(detect_project_type "$worktree")
    echo ""
    echo "Detected project type: $project_type"
    echo ""

    case "$project_type" in
        python|mixed)
            if ! run_gate "Tests pass" "check_tests.sh" "$worktree"; then
                failed=1
            fi
            echo ""
            if ! run_gate "Linter clean" "check_linter.sh" "$worktree"; then
                failed=1
            fi
            echo ""
            if ! run_gate "Type check clean" "check_types.sh" "$worktree"; then
                failed=1
            fi
            echo ""
            if ! run_gate "No untracked TODOs" "check_todos.sh" "$worktree"; then
                failed=1
            fi
            ;;
        frontend)
            echo "--- Frontend checks ---"
            if ! run_gate "Frontend lint" "check_frontend.sh" "$worktree"; then
                failed=1
            fi
            ;;
        hooks|shell)
            echo "--- Shell checks ---"
            if ! run_gate "Shellcheck" "check_shell.sh" "$worktree"; then
                failed=1
            fi
            ;;
        *)
            echo "Warning: Unknown project type '$project_type', running Python checks as default"
            # ... run Python checks
            ;;
    esac
    ;;
```

**Testing Requirements**:
- Integration test with real worktree containing hooks-only changes
- Verify Python checks are skipped for hooks-only changes
- Verify shellcheck runs for hooks-only changes
- Test mixed project runs both check types

---

### R14-C: Create Shell/Hooks Check Script

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R14-B

**Problem Statement**:
No gate check script exists for shell scripts or hooks. Without this, R14-B cannot properly gate hooks-only changes.

**Acceptance Criteria**:
- [ ] New script `.claude/gates/check_shell.sh` created
- [ ] Script runs `shellcheck` on changed `.sh` files
- [ ] Script validates bash syntax with `bash -n`
- [ ] Script checks for common issues (unquoted variables, etc.)
- [ ] Script returns 0 on success, 1 on failure
- [ ] Script handles case where shellcheck is not installed (warn, not fail)
- [ ] Script outputs clear results for each file checked

**Implementation Notes**:

Create file: `.claude/gates/check_shell.sh`

```bash
#!/usr/bin/env bash
#
# check_shell.sh: Validate shell scripts
#
# Usage: check_shell.sh <worktree_path>

set -euo pipefail

WORKTREE="${1:-.}"
cd "$WORKTREE"

# Get changed shell files
SHELL_FILES=$(git diff main...HEAD --name-only -- '*.sh' 'clams/hooks/*' 2>/dev/null | grep -E '\.(sh|bash)$|^clams/hooks/' || true)

if [[ -z "$SHELL_FILES" ]]; then
    echo "No shell files changed."
    exit 0
fi

echo "Checking shell files:"
echo "$SHELL_FILES" | sed 's/^/  /'
echo ""

FAILED=0

# Check if shellcheck is available
if command -v shellcheck &>/dev/null; then
    echo "Running shellcheck..."
    for file in $SHELL_FILES; do
        if [[ -f "$file" ]]; then
            if ! shellcheck -S warning "$file"; then
                echo "  FAIL: $file"
                FAILED=1
            else
                echo "  PASS: $file"
            fi
        fi
    done
else
    echo "Warning: shellcheck not installed, skipping static analysis"
fi

echo ""
echo "Running bash syntax check..."
for file in $SHELL_FILES; do
    if [[ -f "$file" && "$file" == *.sh ]]; then
        if ! bash -n "$file" 2>&1; then
            echo "  SYNTAX ERROR: $file"
            FAILED=1
        else
            echo "  SYNTAX OK: $file"
        fi
    fi
done

exit $FAILED
```

**Testing Requirements**:
- Create test shell script with intentional shellcheck warnings
- Verify script catches the warnings
- Verify script passes for clean shell scripts
- Test with shellcheck unavailable (should warn but not fail)

---

### R14-D: Create Frontend Check Script

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R14-B

**Problem Statement**:
No gate check script exists for frontend (clams-visualizer) changes. Frontend changes currently skip all checks or run irrelevant Python checks.

**Acceptance Criteria**:
- [ ] New script `.claude/gates/check_frontend.sh` created
- [ ] Script runs `npm run lint` if lint script exists in package.json
- [ ] Script runs `npm run typecheck` if typecheck script exists
- [ ] Script validates that `npm install` has been run (node_modules exists)
- [ ] Script returns 0 on success, 1 on failure
- [ ] Script handles missing npm gracefully

**Implementation Notes**:

Create file: `.claude/gates/check_frontend.sh`

```bash
#!/usr/bin/env bash
#
# check_frontend.sh: Validate frontend (clams-visualizer) changes
#
# Usage: check_frontend.sh <worktree_path>

set -euo pipefail

WORKTREE="${1:-.}"
FRONTEND_DIR="$WORKTREE/clams-visualizer"

if [[ ! -d "$FRONTEND_DIR" ]]; then
    echo "No clams-visualizer directory found."
    exit 0
fi

cd "$FRONTEND_DIR"

FAILED=0

# Check node_modules exists
if [[ ! -d "node_modules" ]]; then
    echo "Warning: node_modules not found. Running npm install..."
    npm install || { echo "npm install failed"; exit 1; }
fi

# Check if lint script exists and run it
if grep -q '"lint"' package.json 2>/dev/null; then
    echo "Running npm run lint..."
    if ! npm run lint; then
        echo "Lint check failed"
        FAILED=1
    fi
else
    echo "No lint script in package.json, skipping"
fi

# Check if typecheck script exists and run it
if grep -q '"typecheck"' package.json 2>/dev/null; then
    echo "Running npm run typecheck..."
    if ! npm run typecheck; then
        echo "Type check failed"
        FAILED=1
    fi
else
    echo "No typecheck script in package.json, skipping"
fi

exit $FAILED
```

**Testing Requirements**:
- Test with clams-visualizer changes
- Verify lint runs if configured
- Verify graceful handling when scripts not configured

---

### R14-E: Update Valid Implementation Directories

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none (can run in parallel with R14-A)

**Problem Statement**:
The gate script's "Implementation code exists" check (line 273) only looks in `src/`, `tests/`, `clams/`, and `clams-visualizer/`. This is mostly correct but the check should be project-type aware.

**Acceptance Criteria**:
- [ ] Implementation code check considers project type
- [ ] For Python: `src/`, `tests/` are valid
- [ ] For hooks: `clams/hooks/` is valid (already included via `clams/`)
- [ ] For frontend: `clams-visualizer/` is valid
- [ ] Clear error message when no implementation code found, with valid paths listed
- [ ] Bug fix transition (INVESTIGATED-FIXED) also updated

**Implementation Notes**:

File: `.claude/bin/claws-gate`, line 271-284

The current implementation already includes `clams/` and `clams-visualizer/` but could be clearer. Update the error message to list valid directories based on project type.

**Testing Requirements**:
- Verify hooks-only changes pass the "implementation code exists" check
- Verify changes to unrelated directories (docs/, planning_docs/) fail the check

---

## R15: Response Efficiency Tests

**Context**: API responses can be excessively verbose, wasting tokens in LLM-facing APIs. BUG-030 showed GHAP tools returning full records on every operation, wasting approximately 50,000 tokens during bulk generation of 100 entries.

**Evidence**:
- BUG-030: GHAP tools return full records on every operation
- Theme T13: API Response Bloat

---

### R15-A: Add Response Size Assertions to GHAP Tests

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
No tests verify that API responses are appropriately sized. Verbose responses waste tokens in LLM interactions, and bloat can creep in without anyone noticing.

**Acceptance Criteria**:
- [ ] New test file `tests/test_response_efficiency.py` created
- [ ] Tests verify GHAP tool responses are under size limits:
  - `start_ghap`: response < 500 bytes
  - `update_ghap`: response < 500 bytes
  - `resolve_ghap`: response < 500 bytes
  - `get_active_ghap`: response < 2000 bytes (full entry ok)
  - `list_ghap_entries`: response < 500 bytes per entry
- [ ] Tests use `json.dumps()` to measure actual serialized size
- [ ] Clear assertion messages show actual vs expected size
- [ ] Test documents why each limit was chosen (in comments)

**Implementation Notes**:

Create file: `tests/test_response_efficiency.py`

```python
"""
Tests for API response efficiency.

These tests ensure responses don't bloat over time, wasting tokens in LLM interactions.
Size limits are based on:
- start/update/resolve: Should return minimal confirmation, not full entry
- get_active: Full entry is expected, but shouldn't exceed reasonable size
- list: Should be summaries, not full entries

Reference: BUG-030 - GHAP tools wasted ~50k tokens during bulk generation
"""
import json
import pytest
from clams.server.tools.ghap import GHAPTools


class TestGHAPResponseEfficiency:
    """Verify GHAP responses stay within token-efficient limits."""

    @pytest.fixture
    def ghap_tools(self):
        # Setup with test database
        return GHAPTools(db_path=":memory:")

    def test_start_ghap_response_size(self, ghap_tools):
        """start_ghap should return minimal confirmation, not full entry."""
        response = ghap_tools.start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test goal",
            hypothesis="Test hypothesis",
            action="Test action",
            prediction="Test prediction",
        )

        response_size = len(json.dumps(response))
        max_size = 500  # Confirmation + ID only

        assert response_size < max_size, (
            f"start_ghap response too large: {response_size} bytes > {max_size} bytes. "
            "Response should be minimal confirmation, not full entry."
        )

    def test_update_ghap_response_size(self, ghap_tools):
        """update_ghap should return minimal confirmation."""
        # First create an entry
        ghap_tools.start_ghap(
            domain="debugging",
            strategy="systematic-elimination",
            goal="Test",
            hypothesis="Test",
            action="Test",
            prediction="Test",
        )

        response = ghap_tools.update_ghap(note="Updated note")

        response_size = len(json.dumps(response))
        max_size = 500

        assert response_size < max_size, (
            f"update_ghap response too large: {response_size} bytes > {max_size} bytes"
        )

    # ... similar tests for resolve_ghap, get_active_ghap, list_ghap_entries
```

**Testing Requirements**:
- Run tests against current implementation
- If any fail, document in test comments that fix is needed
- Tests should pass after BUG-030 was fixed (verify this)

---

### R15-B: Add Response Size Assertions to Memory Tools

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: none (can run in parallel with R15-A)

**Problem Statement**:
Memory tools (`store_memory`, `retrieve_memories`) could also return excessively verbose responses. No tests verify response efficiency.

**Acceptance Criteria**:
- [ ] Tests added to `tests/test_response_efficiency.py` for memory tools
- [ ] `store_memory` response < 500 bytes
- [ ] `retrieve_memories` response < 1000 bytes per memory (summaries, not full content)
- [ ] `list_memories` response < 500 bytes per entry

**Implementation Notes**:

Add to `tests/test_response_efficiency.py`:

```python
class TestMemoryResponseEfficiency:
    """Verify memory tool responses stay within limits."""

    def test_store_memory_response_size(self, memory_tools):
        """store_memory should return confirmation, not echo full content."""
        response = memory_tools.store_memory(
            content="A" * 1000,  # Large content
            category="fact",
        )

        response_size = len(json.dumps(response))
        max_size = 500

        assert response_size < max_size, (
            f"store_memory response too large: {response_size} bytes. "
            "Should not echo back the full content."
        )
```

**Testing Requirements**:
- Test with large content inputs
- Verify responses don't echo back full content
- Document expected response structure in test comments

---

### R15-C: Add Token Counting Utility

**Type**: feature
**Priority**: P3
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
Measuring response size in bytes is a proxy for token usage. For more accurate LLM cost estimation, we should have a token counting utility.

**Acceptance Criteria**:
- [ ] New utility function `estimate_tokens(text: str) -> int`
- [ ] Uses simple heuristic: `len(text) / 4` (approximate for English text)
- [ ] Optional: integrate `tiktoken` for accurate counting (if available)
- [ ] Utility documented with accuracy expectations
- [ ] Tests can use token counts instead of byte counts

**Implementation Notes**:

Create file: `src/clams/utils/tokens.py`

```python
"""Token estimation utilities for response efficiency testing."""

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses a simple heuristic of ~4 characters per token, which is
    reasonably accurate for English text with Claude's tokenizer.

    For more accurate counts, install tiktoken and use count_tokens().
    """
    return len(text) // 4


def count_tokens(text: str, model: str = "claude-3") -> int:
    """
    Count tokens accurately using tiktoken.

    Falls back to estimate_tokens if tiktoken not available.
    """
    try:
        import tiktoken
        # Claude uses cl100k_base encoding
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return estimate_tokens(text)
```

**Testing Requirements**:
- Unit tests for estimate_tokens
- Verify reasonable accuracy compared to tiktoken (if available)
- Document accuracy expectations in docstrings

---

## R16: Data Structure Contract Tests

**Context**: BUG-028 showed `ContextItem.__hash__` using first 100 chars but `__eq__` using full content. This violates the hash/eq contract: equal objects must have equal hashes. This causes subtle bugs in set/dict operations.

**Evidence**:
- BUG-028: `ContextItem.__hash__` uses first 100 chars but `__eq__` uses full content
- Theme T14: Hash/Eq Contract Violations

---

### R16-A: Add Hash/Eq Contract Tests for ContextItem

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
The `ContextItem` class violates the hash/eq contract. No tests verify this fundamental invariant. Equal objects must have equal hashes, but the current implementation can have two items with identical first 100 characters but different content - they'd have the same hash but not be equal.

**Acceptance Criteria**:
- [ ] New test file `tests/test_data_contracts.py` created
- [ ] Test verifies: `if a == b then hash(a) == hash(b)`
- [ ] Test covers edge cases:
  - Items with identical first 100 chars, different suffix
  - Items with identical content
  - Items shorter than 100 chars
  - Items with only whitespace differences
- [ ] Test uses property-based testing (hypothesis) if available
- [ ] Test documents the contract requirement in docstring

**Implementation Notes**:

Create file: `tests/test_data_contracts.py`

```python
"""
Tests for data structure contracts (hash/eq invariants).

Python's hash/eq contract requires:
- If a == b, then hash(a) == hash(b)
- If hash(a) != hash(b), then a != b

Violations cause silent bugs in set/dict operations.

Reference: BUG-028 - ContextItem hash/eq contract violation
"""
import pytest
from clams.context.types import ContextItem  # Adjust import path


class TestContextItemContract:
    """Verify ContextItem maintains hash/eq contract."""

    def test_equal_items_have_equal_hashes(self):
        """INVARIANT: if a == b then hash(a) == hash(b)"""
        item1 = ContextItem(content="identical content", source="test")
        item2 = ContextItem(content="identical content", source="test")

        if item1 == item2:
            assert hash(item1) == hash(item2), (
                "Contract violation: equal items must have equal hashes"
            )

    def test_prefix_collision_does_not_imply_equality(self):
        """
        Items with same first 100 chars but different content should:
        - Have same hash (acceptable - hash collisions are allowed)
        - NOT be equal (they have different content)
        """
        prefix = "x" * 100
        item1 = ContextItem(content=prefix + "suffix_a", source="test")
        item2 = ContextItem(content=prefix + "suffix_b", source="test")

        # These may have the same hash (depending on implementation)
        # But they must NOT be equal
        assert item1 != item2, "Items with different content must not be equal"

        # If they ARE equal (bug), then hashes must match
        # This test will fail if hash uses prefix but eq uses full content
        if item1 == item2:
            assert hash(item1) == hash(item2), "Contract violation detected"

    def test_short_items_maintain_contract(self):
        """Items shorter than 100 chars should work correctly."""
        item1 = ContextItem(content="short", source="test")
        item2 = ContextItem(content="short", source="test")

        assert item1 == item2
        assert hash(item1) == hash(item2)

    def test_set_membership_consistent(self):
        """
        Items that are equal should have consistent set membership.

        This is the practical consequence of hash/eq contract violations:
        set operations become unpredictable.
        """
        items = set()
        item1 = ContextItem(content="test content", source="test")
        item2 = ContextItem(content="test content", source="test")

        items.add(item1)

        # If contract holds, item2 should be "in" the set
        # because item1 == item2 and hash(item1) == hash(item2)
        assert item2 in items, "Equal item not found in set (contract violation)"

    def test_dict_key_lookup_consistent(self):
        """
        Items that are equal should work as dict keys consistently.
        """
        d = {}
        item1 = ContextItem(content="test content", source="test")
        item2 = ContextItem(content="test content", source="test")

        d[item1] = "value"

        # If contract holds, item2 should find the same entry
        assert d.get(item2) == "value", (
            "Equal item cannot find dict entry (contract violation)"
        )


# Optional: Property-based tests with hypothesis
try:
    from hypothesis import given, strategies as st

    class TestContextItemContractPropertyBased:
        """Property-based tests for hash/eq contract."""

        @given(st.text(min_size=0, max_size=500))
        def test_equal_items_equal_hashes(self, content):
            """For any content, equal items must have equal hashes."""
            item1 = ContextItem(content=content, source="test")
            item2 = ContextItem(content=content, source="test")

            if item1 == item2:
                assert hash(item1) == hash(item2)

except ImportError:
    pass  # hypothesis not available, skip property-based tests
```

**Testing Requirements**:
- Run tests against current implementation
- Tests should catch BUG-028 style violations
- If ContextItem is already fixed, tests should pass
- If not fixed, document that fix is needed

---

### R16-B: Add Hash/Eq Contract Tests for Other Hashable Classes

**Type**: feature
**Priority**: P3
**Estimated Complexity**: Low
**Dependencies**: R16-A

**Problem Statement**:
Other classes in the codebase may also implement `__hash__` and `__eq__`. All should be tested for contract compliance.

**Acceptance Criteria**:
- [ ] Audit codebase for classes with `__hash__` or `__eq__` methods
- [ ] Add contract tests for each hashable class found
- [ ] Document which classes are tested
- [ ] Create reusable test helper for contract verification

**Implementation Notes**:

Add to `tests/test_data_contracts.py`:

```python
def verify_hash_eq_contract(cls, *args, **kwargs):
    """
    Reusable helper to verify hash/eq contract for any class.

    Usage:
        verify_hash_eq_contract(MyClass, arg1, arg2, kwarg1=value)
    """
    obj1 = cls(*args, **kwargs)
    obj2 = cls(*args, **kwargs)

    # Equal objects must have equal hashes
    if obj1 == obj2:
        assert hash(obj1) == hash(obj2), (
            f"{cls.__name__} violates hash/eq contract: "
            f"equal objects have different hashes"
        )


# Find all hashable classes
# grep -r "__hash__" src/clams/ --include="*.py"
```

First, search for hashable classes:
```bash
grep -r "__hash__" src/clams/ --include="*.py"
```

**Testing Requirements**:
- Run audit to find all hashable classes
- Add tests for each discovered class
- Document audit results in test file

---

### R16-C: Add Pre-commit Hook for Hash/Eq Contract

**Type**: chore
**Priority**: P3
**Estimated Complexity**: Low
**Dependencies**: R16-A

**Problem Statement**:
New `__hash__` or `__eq__` implementations might be added without corresponding contract tests. A pre-commit check could warn about this.

**Acceptance Criteria**:
- [ ] Pre-commit hook detects new `__hash__` or `__eq__` methods
- [ ] Hook warns if no corresponding test exists in `test_data_contracts.py`
- [ ] Hook is advisory (warning, not blocking)
- [ ] Hook documented in `.pre-commit-config.yaml`

**Implementation Notes**:

This could be a simple grep-based check or a custom Python script. The advisory nature (warn, don't block) is important because not all hash/eq implementations need tests immediately.

**Testing Requirements**:
- Add a new `__hash__` method and verify hook warns
- Verify hook doesn't false-positive on existing implementations with tests

---

## R17: Reviewer Checklist Additions

**Context**: Common bug patterns (missing initialization, missing validation, test-production divergence) could be caught earlier if reviewers had explicit checklist items for them.

**Evidence**:
- Theme T3: Missing Initialization Patterns (BUG-016, BUG-043)
- Theme T5: Missing Input Validation (BUG-029, BUG-036)
- Theme T7: Test-Production Divergence (BUG-031, BUG-033, BUG-040)

---

### R17-A: Add Initialization Pattern Checklist Items

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
Reviewers don't have explicit checklist items for initialization patterns. BUG-016 and BUG-043 showed collections being used without `ensure_exists` calls, causing 404 errors on first use.

**Acceptance Criteria**:
- [ ] `.claude/roles/reviewer.md` updated with initialization checklist section
- [ ] Checklist includes:
  - "If adding a new collection/resource, does it have `ensure_exists` pattern?"
  - "Does this code upsert to a collection without ensuring it exists first?"
  - "Are there any assumptions about pre-existing state that should be validated?"
- [ ] Each item references the bug that motivated it
- [ ] Section explains WHY these checks matter (404 errors on first use)

**Implementation Notes**:

Add to `.claude/roles/reviewer.md` after line 86 (after existing checklist):

```markdown
## Additional Checklist Items (Bug Pattern Prevention)

These items are based on recurring bug patterns. See `planning_docs/bug-pattern-analysis.md` for details.

### Initialization Patterns (T3)

_Rationale: BUG-016 and BUG-043 showed collections being used without ensure_exists calls, causing 404 errors on first use._

- [ ] **New collections have ensure_exists**: If adding a new Qdrant collection, does the code call `_ensure_collection()` or equivalent before first use?
- [ ] **No upsert without ensure**: Does this code upsert to a collection? If so, is there an ensure step somewhere in the initialization path?
- [ ] **Pre-existing state assumptions documented**: Are there assumptions about state that must exist? Are they validated or documented?
```

**Testing Requirements**:
- Manual review: verify checklist items are actionable
- Verify checklist items would have caught BUG-016 and BUG-043

---

### R17-B: Add Input Validation Checklist Items

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none (can run in parallel with R17-A)

**Problem Statement**:
Reviewers don't have explicit checklist items for input validation. BUG-029 and BUG-036 showed functions accepting invalid inputs and raising cryptic errors deep in the call stack.

**Acceptance Criteria**:
- [ ] `.claude/roles/reviewer.md` updated with input validation checklist section
- [ ] Checklist includes:
  - "Are all public function inputs validated with helpful error messages?"
  - "Do error messages list valid options when input is invalid?"
  - "Are there any bare `dict[]` accesses that could raise KeyError?"
- [ ] Each item references the bug that motivated it

**Implementation Notes**:

Add to `.claude/roles/reviewer.md`:

```markdown
### Input Validation (T5)

_Rationale: BUG-029 and BUG-036 showed functions raising cryptic KeyError deep in the stack instead of helpful validation errors at the boundary._

- [ ] **Public functions validate inputs**: Do public functions validate their inputs at the start, before processing?
- [ ] **Error messages are helpful**: When validation fails, does the error message list valid options? (e.g., "Invalid type 'foo'. Valid types: bar, baz, qux")
- [ ] **No bare dict access**: Are there any `dict[key]` accesses that could raise KeyError? Should they use `.get()` with default or explicit validation?
```

**Testing Requirements**:
- Manual review: verify checklist items are actionable
- Verify checklist items would have caught BUG-029 and BUG-036

---

### R17-C: Add Test-Production Parity Checklist Items

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none (can run in parallel with R17-A, R17-B)

**Problem Statement**:
Reviewers don't have explicit checklist items for test-production parity. BUG-031, BUG-033, and BUG-040 showed tests passing with mock/test configurations while production failed.

**Acceptance Criteria**:
- [ ] `.claude/roles/reviewer.md` updated with test-production parity checklist section
- [ ] Checklist includes:
  - "Do tests use production configurations or explicitly justify test-specific values?"
  - "Do mocks implement the same interface as production classes?"
  - "Are test commands identical to production commands?"
- [ ] Each item references the bug that motivated it

**Implementation Notes**:

Add to `.claude/roles/reviewer.md`:

```markdown
### Test-Production Parity (T7)

_Rationale: BUG-031 used different clustering parameters in tests vs production. BUG-033 used different server commands. BUG-040 had mocks with different interfaces than production._

- [ ] **Production configurations in tests**: Do tests use production configuration values? If using test-specific values, is there explicit justification in comments?
- [ ] **Mocks match production interfaces**: If tests use mocks, do the mocks have the same method signatures as the production classes they replace?
- [ ] **Commands match production**: Are the commands run in tests (e.g., server startup) identical to production commands?
```

**Testing Requirements**:
- Manual review: verify checklist items are actionable
- Verify checklist items would have caught BUG-031, BUG-033, BUG-040

---

### R17-D: Add Type Consistency Checklist Items

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
Reviewers should check for duplicate type definitions. BUG-040 and BUG-041 showed parallel type hierarchies with incompatible implementations.

**Acceptance Criteria**:
- [ ] `.claude/roles/reviewer.md` updated with type consistency checklist section
- [ ] Checklist includes:
  - "If defining new types, are they in the canonical location?"
  - "Are there duplicate type definitions that should be consolidated?"
  - "Do concrete classes inherit from their abstract base classes?"
- [ ] Each item references the bug that motivated it

**Implementation Notes**:

Add to `.claude/roles/reviewer.md`:

```markdown
### Type Consistency (T1, T2)

_Rationale: BUG-040 had duplicate CodeResult types with different field names. BUG-041 had concrete Searcher not inheriting from abstract Searcher._

- [ ] **Types in canonical location**: If defining new shared types, are they in the canonical `types/` module (or equivalent central location)?
- [ ] **No duplicate definitions**: Is this type already defined elsewhere? Should this use an import instead of a new definition?
- [ ] **Inheritance respected**: If there's an abstract base class, does the concrete implementation inherit from it?
```

**Testing Requirements**:
- Manual review: verify checklist items are actionable
- Verify checklist items would have caught BUG-040 and BUG-041

---

### R17-E: Update Spec and Proposal Reviewer Checklists

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R17-A through R17-D

**Problem Statement**:
The same patterns should be caught during spec and proposal review, not just code review. Earlier detection is cheaper.

**Acceptance Criteria**:
- [ ] `.claude/roles/spec-reviewer.md` updated with relevant items from R17-A through R17-D
- [ ] `.claude/roles/proposal-reviewer.md` updated with relevant items from R17-A through R17-D
- [ ] Items adapted for spec/proposal context (e.g., "Does spec mention initialization requirements?" rather than "Does code have ensure_exists?")
- [ ] Cross-references to code reviewer checklist for implementation-phase checks

**Implementation Notes**:

For `.claude/roles/spec-reviewer.md`, add:

```markdown
### Bug Pattern Prevention (from analysis)

- [ ] **Initialization requirements stated**: Does the spec mention what resources must be initialized? (e.g., "The feature requires a new Qdrant collection, which must be created on first use")
- [ ] **Input validation expectations**: Does the spec define valid input ranges and expected error behavior for invalid inputs?
- [ ] **Test requirements explicit**: Does the spec mention testing requirements, including whether test values should match production?
```

For `.claude/roles/proposal-reviewer.md`, add:

```markdown
### Bug Pattern Prevention (from analysis)

- [ ] **Initialization strategy defined**: Does the proposal describe how resources will be initialized? (e.g., "Will use ensure_exists pattern like CodeIndexer")
- [ ] **Input validation strategy**: Does the proposal describe input validation approach?
- [ ] **Type location decided**: If new types are needed, does the proposal specify where they'll be defined?
- [ ] **Test strategy covers production parity**: Does the testing approach mention using production configurations?
```

**Testing Requirements**:
- Review updated checklists for consistency across all three reviewer roles
- Verify no important items are missing from any checklist

---

## Summary

| Ticket | Type | Priority | Complexity | Dependencies |
|--------|------|----------|------------|--------------|
| R14-A | feature | P1 | Low | none |
| R14-B | feature | P1 | Medium | R14-A |
| R14-C | feature | P1 | Low | R14-B |
| R14-D | feature | P2 | Low | R14-B |
| R14-E | chore | P1 | Low | none |
| R15-A | feature | P2 | Low | none |
| R15-B | feature | P2 | Low | none |
| R15-C | feature | P3 | Low | none |
| R16-A | feature | P2 | Low | none |
| R16-B | feature | P3 | Low | R16-A |
| R16-C | chore | P3 | Low | R16-A |
| R17-A | chore | P1 | Low | none |
| R17-B | chore | P1 | Low | none |
| R17-C | chore | P1 | Low | none |
| R17-D | chore | P2 | Low | none |
| R17-E | chore | P2 | Low | R17-A, R17-B, R17-C, R17-D |

### Parallelization Opportunities

**Fully parallel (no dependencies)**:
- R14-A, R14-E, R15-A, R15-B, R15-C, R16-A, R17-A, R17-B, R17-C, R17-D

**Sequential chains**:
- R14-A -> R14-B -> R14-C
- R14-A -> R14-B -> R14-D
- R16-A -> R16-B
- R16-A -> R16-C
- R17-A, R17-B, R17-C, R17-D -> R17-E
