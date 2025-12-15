# SPEC-027: Import Time Measurement Test

## Summary

Add comprehensive tests to measure and enforce import time limits for CLAMS modules, preventing slow startup due to heavy imports. This spec consolidates and extends existing import time tests to ensure consistent, reliable detection of import time regressions.

## Background

BUG-037 and BUG-042 demonstrated the critical importance of controlling import time:

- **BUG-037**: Install script verification timed out because `clams.server.main` importing PyTorch took 4-6+ seconds
- **BUG-042**: Daemon crashed on macOS because PyTorch MPS was initialized before `os.fork()`

Both bugs were caused by heavy imports (PyTorch, sentence_transformers) being loaded eagerly instead of lazily. The codebase now uses lazy imports, but we need tests to prevent regressions.

### Existing Safeguards

1. **`tests/performance/test_import_time.py`**: Tests import time for `clams` and `clams.embedding` modules
2. **`tests/hooks/test_heavy_imports.py`**: Tests the AST-based pre-commit hook
3. **`.claude/hooks/check_heavy_imports.py`**: Pre-commit hook that detects top-level heavy imports

This spec focuses on **runtime import time measurement tests** - the pre-commit hook catches obvious violations at commit time, but runtime tests catch subtle regressions that slip through (e.g., a "safe" dependency that now imports torch transitively).

## Test Approach

### Methodology

Tests will use **subprocess isolation** to measure cold-start import time:

1. Run `python -c "import <module>"` in a subprocess
2. Measure wall-clock time from subprocess start to exit
3. Compare against threshold
4. Fail with actionable error message if threshold exceeded

Subprocess isolation ensures:
- No module caching from the test runner
- Fresh Python interpreter state
- Realistic cold-start measurement

### Test Categories

#### 1. Core Module Import Tests

| Module | Threshold | Rationale |
|--------|-----------|-----------|
| `clams` | < 1.0s | Top-level package, version info only |
| `clams.server` | < 1.0s | Server subpackage, no heavy deps |
| `clams.server.main` | < 1.0s | Entry point, must be fast for CLI |
| `clams.embedding` | < 1.0s | Registry only, not model implementations |
| `clams.server.http` | < 1.0s | HTTP transport, used for daemon checks |

These thresholds are strict to catch regressions early. Expected times are 0.1-0.5 seconds.

#### 2. Server Entry Point Tests

The server entry point (`clams.server.main`) is critical because:
- It's invoked on every server start
- `--stop` and `--daemon` commands must parse args quickly
- Heavy imports block daemon forking on macOS

Test cases:
- Import `clams.server.main` in < 1.0s
- Verify `parse_args()` can be called without heavy imports
- Verify `main()` can reach argument parsing without heavy imports

#### 3. Lazy Import Verification Tests

Verify that heavy modules (torch, sentence_transformers) are NOT loaded by light imports:

```python
# After importing clams.embedding:
assert 'torch' not in sys.modules
assert 'sentence_transformers' not in sys.modules
```

This catches transitive dependencies that accidentally import heavy packages.

#### 4. Heavy Import Baseline Tests (marked slow)

For documentation and regression baseline:
- Measure actual import time of `torch` (baseline: 2-4s)
- Measure actual import time when loading models (baseline: 4-6s)

These tests are marked `@pytest.mark.slow` and run only in CI or explicitly.

## Modules to Test

### Critical Paths (< 1.0s threshold)

1. **`clams`** - Top-level package
2. **`clams.server`** - Server subpackage
3. **`clams.server.main`** - CLI entry point
4. **`clams.server.http`** - HTTP transport (daemon management)
5. **`clams.server.config`** - Configuration loading
6. **`clams.embedding`** - Embedding registry (not models)
7. **`clams.storage`** - Storage backends
8. **`clams.search`** - Search functionality

### Allowed Heavy Imports (leaf modules)

These modules are explicitly allowed to have heavy imports because they are lazily imported by the registry:

1. **`clams.embedding.minilm`** - MiniLM implementation (imports torch)
2. **`clams.embedding.nomic`** - Nomic implementation (imports torch)

### Not Tested (internal implementation)

- `clams.clustering` - Internal implementation detail
- `clams.indexers` - Internal implementation detail
- Other submodules that don't have public entry points

## Thresholds

| Category | Threshold | Notes |
|----------|-----------|-------|
| Core modules | < 1.0s | Strict limit for all public modules |
| Server entry | < 1.0s | Critical for CLI responsiveness |
| Embedding registry | < 1.0s | Must NOT load models |
| Model loading | No limit | Marked @slow, baseline only |

### Threshold Rationale

- **1.0 second**: Conservative limit that provides ~0.5s buffer above expected 0.1-0.5s import time
- Failing at 1.0s catches PyTorch loads (~3-4s) with margin
- Lower threshold (e.g., 0.5s) risks CI flakiness on slow runners

## Error Messages

Test failures must include actionable guidance:

```
FAILED: Import of clams.embedding took 4.2s, expected < 1.0s

This likely means a heavy dependency (torch, sentence_transformers) is
being imported at module level instead of lazily.

To diagnose:
  python -c "import sys; import clams.embedding; print([m for m in sys.modules if 'torch' in m])"

Common causes:
  1. Top-level import of torch or sentence_transformers
  2. Importing model class instead of using registry
  3. Transitive dependency that imports torch

See BUG-037 and BUG-042 for context.
```

## Implementation

### File Structure

```
tests/performance/
  test_import_time.py        # Core import time tests (extend existing)
tests/integration/
  test_import_isolation.py   # Lazy import verification tests
```

### Test Functions

```python
class TestCoreModuleImportTime:
    """Import time tests for core modules."""

    @pytest.mark.parametrize("module", [
        "clams",
        "clams.server",
        "clams.server.main",
        "clams.server.http",
        "clams.server.config",
        "clams.embedding",
        "clams.storage",
        "clams.search",
    ])
    def test_module_import_under_threshold(self, module: str) -> None:
        """Each core module must import in < 1.0s."""
        ...

class TestLazyImportIsolation:
    """Verify heavy packages are not loaded by light imports."""

    def test_clams_does_not_load_torch(self) -> None:
        """import clams must not load torch."""
        ...

    def test_clams_embedding_does_not_load_torch(self) -> None:
        """import clams.embedding must not load torch."""
        ...

    def test_clams_server_main_does_not_load_torch(self) -> None:
        """import clams.server.main must not load torch."""
        ...

class TestHeavyImportBaseline:
    """Baseline measurements for heavy imports (documentation only)."""

    @pytest.mark.slow
    def test_torch_import_baseline(self) -> None:
        """Document torch import time (not enforced)."""
        ...
```

## Acceptance Criteria

1. **Test coverage**: All critical modules listed above have import time tests
2. **Threshold enforcement**: Tests fail if any module exceeds 1.0s threshold
3. **Lazy import verification**: Tests verify torch is NOT loaded by light imports
4. **Error messages**: Failures include actionable diagnosis guidance
5. **CI integration**: Tests run in normal test suite (except @slow tests)
6. **Existing tests preserved**: Extend, don't replace, existing test_import_time.py
7. **Documentation**: Test docstrings explain the purpose and reference BUG-037/BUG-042

## Out of Scope

- Modifying the pre-commit hook (check_heavy_imports.py) - covered by existing tests
- Measuring import time of heavy modules (torch, models) - these are allowed to be slow
- Profiling/tracing import chains - useful for debugging but not testing

## References

- BUG-037: Install script verification timeout due to model loading
- BUG-042: Daemon crashes on macOS due to MPS fork safety
- tests/performance/test_import_time.py: Existing import time tests
- tests/hooks/test_heavy_imports.py: Tests for pre-commit hook
- .claude/hooks/check_heavy_imports.py: Pre-commit hook implementation
