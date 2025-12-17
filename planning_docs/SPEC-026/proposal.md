# Technical Proposal: Pre-commit Hook for Heavy Import Detection

## Problem Statement

CLAMS uses PyTorch-based embedding models that initialize GPU backends (MPS on macOS, CUDA on Linux) at import time. This causes two critical issues:

1. **Startup Latency (BUG-037)**: Importing PyTorch takes 4-6 seconds, making CLI tools feel sluggish
2. **Fork Safety (BUG-042)**: On macOS with Apple Silicon, MPS cannot be forked after initialization, causing daemon crashes

The codebase uses lazy imports to mitigate this, but without automated enforcement, developers may accidentally reintroduce these bugs.

## Proposed Solution

Implement a pre-commit hook using AST (Abstract Syntax Tree) analysis to detect forbidden top-level imports before code is committed.

### Implementation Approach

#### Core Design

The hook follows the existing pattern established by `check_subprocess.py`:

1. **AST-Based Analysis**: Parse Python files with `ast.parse()` and walk the tree to find import statements
2. **Scope Tracking**: Use an `ast.NodeVisitor` subclass that tracks whether we're inside a function/method
3. **Package Allowlist**: Define heavy packages that trigger violations (`torch`, `sentence_transformers`, `transformers`, `nomic`)
4. **Exception Handling**: Allow specific modules and test files to bypass the check

#### Key Components

```
.claude/hooks/check_heavy_imports.py   # Main hook implementation
tests/hooks/test_heavy_imports.py       # Comprehensive test suite
.pre-commit-config.yaml                 # Hook registration
```

### Detection Logic

The `HeavyImportChecker` class tracks function scope and TYPE_CHECKING guards:

1. **Function Entry**: Set `_in_function = True` when visiting `FunctionDef` or `AsyncFunctionDef`
2. **Function Exit**: Restore previous state after visiting children
3. **TYPE_CHECKING Detection**: When visiting an `If` node, check if the test is a `Name` node with id `TYPE_CHECKING`, and set `_in_type_checking = True`
4. **Import Check**: Only flag `Import` and `ImportFrom` nodes when both `_in_function = False` and `_in_type_checking = False`

This allows:
- Lazy imports inside functions (runtime deferred execution)
- TYPE_CHECKING imports (only execute during static analysis, never at runtime)

### Exception Rules

| Exception Type | Detection Method |
|---------------|------------------|
| Test files | Path contains `/tests/`, starts with `test_`, ends with `_test.py`, or is `conftest.py` |
| Allowed modules | Path ends with an entry from `ALLOWED_MODULES` set |
| Syntax errors | Silently skip (fail elsewhere) |

#### Allowed Modules List

```python
ALLOWED_MODULES = frozenset({
    "src/clams/embedding/minilm.py",
    "src/clams/embedding/nomic.py",
    "clams/embedding/minilm.py",    # For different path formats
    "clams/embedding/nomic.py",
})
```

These are "leaf" modules that are themselves lazily imported by `registry.py`.

### Error Output

The hook produces actionable error messages:

```
ERROR: Top-level imports of heavy packages detected!

These packages initialize GPU backends at import time, which causes:
  - 4-6 second startup delays
  - Fork failures when daemonizing (os.fork() after PyTorch init fails)

Violations found:
  src/clams/server/tools/search.py:5:0: import torch

To fix, move imports inside functions (lazy import pattern):

  # WRONG - top-level import
  import torch

  def get_embeddings():
      return torch.tensor(...)

  # CORRECT - lazy import inside function
  def get_embeddings():
      import torch  # Only loaded when function is called
      return torch.tensor(...)

See BUG-042, BUG-037 for context.
See src/clams/embedding/registry.py for the correct pattern.
```

## Alternative Approaches Considered

### 1. Runtime Import Monitoring

**Approach**: Instrument the import system at runtime to detect heavy imports before fork.

**Rejection Rationale**:
- Adds complexity to the daemon startup path
- Detection happens too late (after code is written/committed)
- Runtime overhead on every startup
- Pre-commit detection is simpler and catches issues earlier in the development cycle

### 2. Module-Level `__all__` Enforcement

**Approach**: Require all embedding modules to explicitly declare `__all__` and validate imports at test time.

**Rejection Rationale**:
- Doesn't prevent the actual import problem
- `__all__` controls what's exported, not what's imported
- Still allows top-level imports that cause the fork issue

### 3. Require TYPE_CHECKING for All Heavy Imports

**Approach**: Require ALL heavy imports (even in allowed modules) to be inside `if TYPE_CHECKING:` blocks.

**Rejection Rationale**:
- `TYPE_CHECKING` imports don't execute at runtime - the embedding modules need actual runtime imports
- Would break the existing lazy import pattern in minilm.py and nomic.py
- More restrictive than necessary - lazy imports inside functions are the correct pattern for runtime use
- We DO support TYPE_CHECKING as an allowed pattern (for type hints), but don't require it everywhere

### 4. Dynamic Import Analysis (importlib)

**Approach**: Use `importlib.util.find_spec` to trace import chains dynamically.

**Rejection Rationale**:
- Much slower than AST analysis (needs to actually load modules)
- Can have side effects
- AST analysis is sufficient for detecting direct imports

## File/Module Structure

### Hook Location

```
.claude/
  hooks/
    check_heavy_imports.py    # New file - main implementation
    check_subprocess.py       # Existing reference implementation
```

### Test Location

```
tests/
  hooks/
    test_heavy_imports.py     # Comprehensive test suite
```

### Configuration

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: check-heavy-imports
        name: Check for top-level heavy imports
        description: >
          Detects top-level imports of heavy packages (torch, sentence_transformers,
          transformers, nomic) that cause startup delays and fork failures.
          See BUG-037, BUG-042.
        entry: python .claude/hooks/check_heavy_imports.py
        language: python
        types: [python]
        pass_filenames: true
```

## Test Strategy

### Unit Tests

1. **Package Detection**
   - `test_detects_import_torch` - Basic `import torch`
   - `test_detects_from_torch_import` - `from torch import nn`
   - `test_detects_from_torch_submodule` - `from torch.nn import Module`
   - `test_detects_sentence_transformers` - sentence_transformers package
   - `test_detects_transformers` - transformers package
   - `test_detects_nomic` - nomic package

2. **Allowed Patterns**
   - `test_allows_lazy_import_in_function` - Imports inside regular functions
   - `test_allows_lazy_import_in_async_function` - Imports inside async functions
   - `test_allows_lazy_import_in_method` - Imports inside class methods
   - `test_allows_type_checking_import` - Imports inside `if TYPE_CHECKING:` blocks
   - `test_allows_other_imports` - Non-heavy packages (numpy, structlog, etc.)

3. **File Exclusions**
   - `test_test_directory_detected` - Files in `tests/` directory
   - `test_test_prefix_detected` - Files matching `test_*.py`
   - `test_test_suffix_detected` - Files matching `*_test.py`
   - `test_conftest_detected` - `conftest.py` files

4. **Module Exclusions**
   - `test_minilm_is_allowed` - `minilm.py` allowed heavy imports
   - `test_nomic_is_allowed` - `nomic.py` allowed heavy imports
   - `test_registry_not_allowed` - `registry.py` NOT allowed (must use lazy)

### Integration Tests

1. **Actual Source Verification**
   - `test_embedding_registry_passes` - Verify registry.py uses lazy imports correctly
   - `test_embedding_init_passes` - Verify __init__.py is clean
   - `test_minilm_is_allowed` - Verify allowlist works for minilm.py
   - `test_nomic_is_allowed` - Verify allowlist works for nomic.py

2. **Error Handling**
   - `test_skips_syntax_errors` - Files with syntax errors are skipped gracefully
   - `test_skips_test_files` - Test files are completely bypassed

## Migration/Rollout Plan

### Phase 1: Implementation (This Spec)

1. Implement `check_heavy_imports.py` following the existing hook pattern
2. Add comprehensive test suite
3. Register in `.pre-commit-config.yaml`

### Phase 2: Validation

1. Run hook against entire codebase: `pre-commit run check-heavy-imports --all-files`
2. Verify no false positives on existing lazy import patterns
3. Verify allowed modules (minilm.py, nomic.py) pass

### Phase 3: Documentation (SPEC-028)

1. Add developer documentation explaining the constraint
2. Reference this hook in the documentation
3. Update onboarding materials

### Rollback Plan

If issues arise:
1. Remove hook entry from `.pre-commit-config.yaml`
2. Developers can continue working while hook is debugged
3. No changes to source code required - hook is purely defensive

## Non-Functional Requirements

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| Execution time | <1 second for typical commits | Pre-commit hooks must be fast |
| Dependencies | Standard library only | No additional dependencies to manage |
| Python version | 3.10+ | Match project requirements |

## Dependencies

- **Blocks**: SPEC-028 (Document Fork/Daemon Constraint) - This enforcement mechanism needs documentation
- **References**: BUG-037, BUG-042 - The issues this hook prevents

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| AST analysis over regex | Accurate parsing, handles edge cases, matches existing hook pattern |
| Scope tracking with visitor state | Simple, efficient, handles nested functions correctly |
| Allowlist over denylist | Explicit control, safer default behavior |
| Standard library only | Minimizes dependencies, faster execution |
| Graceful syntax error handling | Don't block commits due to other files' issues |
| Test file exclusion | Test startup latency is acceptable, fork safety not relevant |
