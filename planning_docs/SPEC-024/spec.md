# SPEC-024: Configuration Parity Verification

## Problem Statement

Test/production configuration divergence is a persistent source of bugs in CLAMS. When test fixtures, mocks, or integration tests use different configuration values than production code, tests pass but production fails. This problem manifests in several forms:

### Historical Examples

1. **BUG-031 (Clustering Configuration)**: Tests used `min_cluster_size=3` while production used `min_cluster_size=5`. Clustering behavior differed between test and production, causing unexpected results.

2. **BUG-033 (Server Command)**: Tests correctly used `.venv/bin/clams-server` but hooks used `python -m clams` (module invocation). This caused import path issues in production that tests never caught.

3. **BUG-040/BUG-041 (Mock Interface Drift)**: MockSearcher implemented methods with different signatures than the production Searcher, causing tests to pass with incorrect call patterns.

### Why This Matters

- **Silent failures**: Configuration mismatches often don't cause immediate errors - they cause subtle behavior differences
- **False confidence**: Passing tests give false confidence that code works correctly
- **Debugging cost**: These bugs are hard to diagnose because "but it works in tests!"
- **Regression risk**: Fixed once, these patterns can easily regress

### Current State

The codebase has two partial solutions:

1. **`tests/infrastructure/test_config_parity.py`**: Verifies clustering and server command configuration matches between hooks, tests, and `ServerSettings`

2. **`tests/infrastructure/test_mock_parity.py`**: Verifies mock classes implement the same interface as production classes

These are reactive solutions created after bugs were discovered. This spec defines a systematic, proactive approach to prevent configuration drift.

## Proposed Solution

Implement a comprehensive Configuration Parity Verification framework that:

1. **Enforces Single Source of Truth**: All configuration values flow from `ServerSettings` (the canonical source)
2. **Detects Drift Automatically**: Tests fail when any component uses hardcoded values that differ from `ServerSettings`
3. **Validates Mock Fidelity**: Mocks must match production interfaces exactly
4. **Covers All Configuration Surfaces**: Hooks, fixtures, integration tests, and shell scripts

This specification unblocks **SPEC-025 (Production Command Verification)**, which will verify that shell commands used in hooks match integration test commands.

## Requirements

### Functional Requirements

#### F1: Configuration Value Verification

Tests must verify that the following configuration surfaces use values from `ServerSettings`:

| Surface | Configuration Areas |
|---------|-------------------|
| `clams/hooks/config.yaml` | server_command, ghap_frequency, timeouts |
| `clams/hooks/session_start.sh` | server paths, port, host |
| `tests/integration/test_*.py` | clusterer params, server paths, timeouts |
| `tests/server/tools/conftest.py` | mock dimensions, mock return values |
| `tests/performance/test_benchmarks.py` | clusterer params (must match production) |

#### F2: Mock Interface Verification

All mock classes must implement the same interface as their production counterparts:

| Mock Class | Production Class | ABC (if applicable) |
|------------|-----------------|---------------------|
| `MockSearcher` | `clams.search.searcher.Searcher` | `clams.context.searcher_types.Searcher` |
| `MockEmbedder` | `clams.embedding.base.EmbeddingService` | n/a (is ABC) |
| `mock_code_embedder` (fixture) | `clams.embedding.base.EmbeddingService` | n/a |
| `mock_semantic_embedder` (fixture) | `clams.embedding.base.EmbeddingService` | n/a |
| `mock_vector_store` (fixture) | `clams.storage.base.VectorStore` | n/a |

Verification includes:
- All public methods present
- Method signatures match (parameter names, types, defaults)
- Return type annotations match
- Properties match (e.g., `dimension`)

#### F3: Embedding Dimension Consistency

Test fixtures must use production embedding dimensions:

| Embedder Type | Production Dimension | Source |
|--------------|---------------------|--------|
| Code (MiniLM) | 384 | Fixed constant (MiniLM model output dimension, not configurable) |
| Semantic (Nomic) | 768 | `ServerSettings.embedding_dimension` |

The `conftest.py` fixtures currently use hardcoded values (384, 768). These should reference `ServerSettings` or be validated against it.

#### F4: Shell Script Configuration Parity

Shell scripts must source configuration from a canonical location:

1. `session_start.sh` constructs paths using `REPO_ROOT`
2. Server port/host must come from exported `ServerSettings` (via `config.env`)
3. Timeouts must match `ServerSettings` values

#### F5: Intentional Differences Documentation

Some tests intentionally use different configuration for edge case testing. These must be:

1. **Documented**: A comment explaining why the difference is intentional
2. **Isolated**: Only in unit tests, never in integration tests
3. **Verified**: A test ensures the difference only exists in allowed files

Current allowed intentional differences:
- `tests/clustering/test_bug_031_regression.py`: Uses `min_cluster_size=3` to test the BUG-031 fix behavior
- `tests/clustering/test_experience.py`: Uses `min_cluster_size=3` for faster unit tests
- `tests/clustering/test_clusterer.py`: Uses `min_cluster_size=3` for basic unit tests

### Non-Functional Requirements

#### NF1: Test Execution Time

Parity verification tests should complete in <5 seconds (file reading and regex matching only, no heavy imports).

#### NF2: Clear Error Messages

When parity violations are detected, error messages must include:
- The file with the violation
- The expected value (from `ServerSettings`)
- The actual value found
- A reference to this spec or relevant bug

Example:
```
test_hooks_config.yaml uses ghap_frequency=5 but ServerSettings.ghap_check_frequency is 10.
These should match. See SPEC-024 and BUG-033.
```

#### NF3: Maintainability

The parity verification system should be:
- Easy to extend when new configuration surfaces are added
- Self-documenting (tests explain what they verify and why)
- Fail-fast (violations caught at test time, not runtime)

### Error Handling Requirements

#### E1: Missing Files

If a file to be verified doesn't exist (e.g., integration test file removed):
- Test should fail with clear message about missing file
- Exception: Optional files can be skipped with a warning

#### E2: Parse Errors

If a configuration file (YAML, Python) can't be parsed:
- Test should fail with parse error details
- Never silently skip malformed files

#### E3: New Configuration Values

When `ServerSettings` gains new fields:
- Tests should not break (we verify specific known fields)
- A separate test should track which fields are verified vs. not

## Design

### Architecture

```
tests/infrastructure/
    __init__.py
    test_config_parity.py      # Existing: clustering, server command
    test_mock_parity.py        # Existing: mock interface verification
    test_fixture_parity.py     # NEW: fixture value verification
    test_shell_parity.py       # NEW: shell script verification
    conftest.py                # NEW: shared utilities for parity tests

src/clams/server/config.py     # Canonical source: ServerSettings
```

### Configuration Registry Pattern

The `ServerSettings` class is the single source of truth. All verification tests:

1. Instantiate `ServerSettings()` to get production defaults
2. Extract the value being verified
3. Read the target file/fixture
4. Compare and assert equality

```python
def test_hooks_use_production_ghap_frequency() -> None:
    """Verify hooks/config.yaml ghap frequency matches ServerSettings."""
    settings = ServerSettings()
    prod_frequency = settings.ghap_check_frequency  # Canonical source

    with open("clams/hooks/config.yaml") as f:
        config = yaml.safe_load(f)

    hook_frequency = config.get("hooks", {}).get("ghap_checkin", {}).get("frequency")

    assert hook_frequency == prod_frequency, (
        f"hooks/config.yaml ghap_checkin.frequency is {hook_frequency}, "
        f"but ServerSettings.ghap_check_frequency is {prod_frequency}. "
        "These should match. See SPEC-024."
    )
```

### Mock Verification Pattern

The mock parity tests use introspection to compare interfaces:

```python
def verify_mock_interface(
    prod_cls: type,
    mock_cls: type,
    exclude_methods: set[str] | None = None,
) -> dict[str, Any]:
    """Compare mock class interface against production class."""
    exclude = exclude_methods or {"register"}

    prod_methods = get_public_methods(prod_cls) - exclude
    mock_methods = get_public_methods(mock_cls) - exclude

    missing = prod_methods - mock_methods

    signature_diffs = {}
    for method_name in prod_methods & mock_methods:
        diffs = compare_signatures(prod_cls, mock_cls, method_name)
        if diffs:
            signature_diffs[method_name] = diffs

    return {
        "passed": not missing and not signature_diffs,
        "missing_methods": missing,
        "signature_differences": signature_diffs,
    }
```

### File Verification Patterns

Different file types require different verification strategies:

| File Type | Strategy |
|-----------|----------|
| YAML (`config.yaml`) | Parse with `yaml.safe_load()`, access keys |
| Python (tests, fixtures) | Regex matching for hardcoded values |
| Shell scripts | Regex matching for variable assignments |

### Fixture Value Registry (NEW)

Create a registry that maps fixture names to expected production values:

```python
# tests/infrastructure/conftest.py

from clams.server.config import ServerSettings

def get_fixture_expectations() -> dict[str, dict[str, Any]]:
    """Return expected fixture values based on ServerSettings."""
    settings = ServerSettings()
    return {
        "mock_code_embedder": {
            # 384 is a fixed constant - MiniLM model output dimension
            # This is NOT from ServerSettings because it's model-intrinsic
            "dimension": 384,
            "embed_return_length": 384,
        },
        "mock_semantic_embedder": {
            "dimension": settings.embedding_dimension,  # 768
            "embed_return_length": settings.embedding_dimension,
        },
        "clustering": {
            "min_cluster_size": settings.hdbscan_min_cluster_size,
            "min_samples": settings.hdbscan_min_samples,
        },
        "timeouts": {
            "verification": settings.verification_timeout,
            "http_call": settings.http_call_timeout,
            "qdrant": settings.qdrant_timeout,
        },
    }
```

### Shell Script Verification (NEW)

Shell scripts should source configuration from `~/.clams/config.env`:

```python
def test_session_start_uses_exported_config() -> None:
    """Verify session_start.sh can use exported config values."""
    settings = ServerSettings()

    # Verify config can be exported
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.env"
        settings.export_for_shell(config_path)

        content = config_path.read_text()

        # Verify key values are exported
        assert f"CLAMS_HTTP_PORT={settings.http_port}" in content
        assert f"CLAMS_VERIFICATION_TIMEOUT={settings.verification_timeout}" in content
```

## Acceptance Criteria

### Configuration Parity

1. [ ] Test verifies `clams/hooks/config.yaml` server_command matches `ServerSettings.server_command`
2. [ ] Test verifies `clams/hooks/config.yaml` ghap_checkin.frequency matches `ServerSettings.ghap_check_frequency`
3. [ ] Test verifies `clams/hooks/config.yaml` mcp.connection_timeout is compatible with `ServerSettings.verification_timeout`
4. [ ] Test verifies integration tests use production clustering defaults
5. [ ] Test verifies performance benchmarks use production clustering defaults

### Mock Parity

6. [ ] Test verifies MockSearcher has all methods from Searcher ABC
7. [ ] Test verifies MockSearcher method signatures match Searcher ABC
8. [ ] Test verifies MockSearcher has all methods from concrete Searcher
9. [ ] Test verifies MockEmbedder has all methods from EmbeddingService
10. [ ] Test verifies conftest.py mock fixtures use correct dimensions

### Fixture Parity

11. [ ] Test verifies `mock_code_embedder.dimension` is 384
12. [ ] Test verifies `mock_semantic_embedder.dimension` is 768
13. [ ] Test documents which tests intentionally use non-production values
14. [ ] Test ensures intentional differences only exist in allowed unit test files

### Shell Parity

15. [ ] Test verifies `session_start.sh` server path construction is correct
16. [ ] Test verifies `ServerSettings.export_for_shell()` exports all required values
17. [ ] Test verifies exported config matches `ServerSettings` defaults

### Error Handling

18. [ ] Test produces clear error message when parity violation detected
19. [ ] Test fails (not skips) when required file is missing
20. [ ] Test fails with parse error details when config file is malformed

### Integration with SPEC-025

21. [ ] Design supports adding production command verification (shell commands used in hooks match test commands)
22. [ ] Parity test infrastructure can be extended for command verification

## Out of Scope

- **Runtime configuration validation**: This spec covers test-time verification only
- **Automatic configuration synchronization**: We detect drift, not fix it automatically
- **Configuration migration tools**: Out of scope for this spec
- **Environment-specific configuration**: We verify defaults, not environment overrides

## Risks

1. **False positives from intentional differences**: Mitigated by explicit allowlist of files with intentional differences

2. **Regex fragility for Python parsing**: Mitigated by using simple, specific patterns and clear test names that explain what's being matched

3. **Maintenance burden**: Mitigated by:
   - Tests are self-documenting
   - Adding new verifications is straightforward (follow existing patterns)
   - Single source of truth (`ServerSettings`) minimizes update points

4. **Test execution time**: Mitigated by keeping tests lightweight (file I/O and regex only, no heavy imports)

## Implementation Notes

### Relationship to Existing Tests

This spec formalizes and extends the existing tests in `tests/infrastructure/`:

- `test_config_parity.py`: Already covers clustering and server command parity
- `test_mock_parity.py`: Already covers mock interface verification

The implementation should:
1. Keep existing tests as-is (they work and provide value)
2. Add new tests for fixture and shell parity
3. Improve error messages to reference this spec

### Relationship to SPEC-025

SPEC-025 (Production Command Verification) will:
1. Depend on the infrastructure created here
2. Add command-specific verification (exact command strings, arguments)
3. Verify that test helper functions produce the same commands as production hooks

This spec provides the foundation; SPEC-025 builds on it.

### Test Organization

```
tests/infrastructure/
    test_config_parity.py
        TestClusteringConfiguration
        TestServerCommandConfiguration
        TestSessionStartHookConfiguration
        TestGHAPFrequencyConfiguration
        TestDocumentedDifferences

    test_mock_parity.py
        TestMockSearcherParityWithABC
        TestMockSearcherParityWithConcrete
        TestConcreteMatchesABC
        TestMockEmbedderParity
        TestParameterizedMockParity

    test_fixture_parity.py  # NEW
        TestEmbeddingDimensionParity
        TestMockReturnValueParity

    test_shell_parity.py    # NEW
        TestConfigExport
        TestShellScriptConfiguration
```
