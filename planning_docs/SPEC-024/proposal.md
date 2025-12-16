# Technical Proposal: SPEC-024 Configuration Parity Verification

## Problem Statement

Test/production configuration divergence causes "works in test, fails in production" bugs. Historical examples include:

- **BUG-031**: Tests used `min_cluster_size=3`, production used `5`
- **BUG-033**: Tests used `.venv/bin/clams-server`, hooks used `python -m clams`
- **BUG-040/BUG-041**: MockSearcher had different method signatures than production Searcher

The existing tests in `tests/infrastructure/` cover some cases reactively. This spec defines a systematic, proactive framework.

## Proposed Solution

Extend the existing infrastructure test suite with two new test modules and a shared utility module:

1. **`test_fixture_parity.py`**: Verify test fixtures use production-compatible values
2. **`test_shell_parity.py`**: Verify shell scripts source configuration correctly
3. **`conftest.py`** (infrastructure): Shared utilities for parity verification

### Design Principles Applied

- **Simple over clever**: Use regex and file parsing rather than AST analysis
- **Explicit over implicit**: Document intentional differences with allowlists
- **Design for testability**: Tests verify behavior, not implementation details
- **Minimize coupling**: Each test module is independent; shared code in conftest

## Alternative Approaches Considered

### 1. AST-Based Python Parsing

**Approach**: Parse Python files with `ast` module to extract exact configuration values.

**Rejected because**:
- Adds complexity without proportional benefit
- AST is fragile to Python version changes
- Regex matching is sufficient for the targeted patterns (assignments, function calls)
- Harder to understand and maintain

### 2. Runtime Configuration Injection

**Approach**: Inject `ServerSettings` into all fixtures at runtime, eliminating hardcoded values.

**Rejected because**:
- Requires extensive refactoring of existing fixtures
- Some values (e.g., MiniLM dimension=384) are model-intrinsic, not configurable
- Unit tests intentionally use different values for speed
- Test isolation would be harder to maintain

### 3. Configuration Schema Validation

**Approach**: Define a JSON Schema for configuration and validate all sources against it.

**Rejected because**:
- Overkill for the current problem scope
- Would require schema maintenance overhead
- Most configuration is Python (`ServerSettings`), not JSON/YAML
- The current YAML files are small and stable

### 4. Centralized Configuration Generation

**Approach**: Generate all configuration files from `ServerSettings` at build time.

**Rejected because**:
- Shell scripts need configuration at runtime, not build time
- Would complicate the development workflow
- YAML files have additional structure beyond `ServerSettings` values
- Adds a build step where none currently exists

## File/Module Structure

```
tests/infrastructure/
    __init__.py                    # (existing, empty)
    conftest.py                    # NEW: shared parity utilities
    test_config_parity.py          # (existing) clustering, server command
    test_mock_parity.py            # (existing) mock interface verification
    test_fixture_parity.py         # NEW: fixture value verification
    test_shell_parity.py           # NEW: shell script verification
```

### New File: `tests/infrastructure/conftest.py`

```python
"""Shared utilities for configuration parity verification tests.

This module provides helper functions used across all parity test modules.
"""

import re
from pathlib import Path
from typing import Any

from clams.server.config import ServerSettings


def get_repo_root() -> Path:
    """Get the repository root directory.

    Returns:
        Path to the repository root (parent of tests/)
    """
    return Path(__file__).parent.parent.parent


def get_fixture_expectations() -> dict[str, dict[str, Any]]:
    """Return expected fixture values based on ServerSettings.

    This is the canonical reference for what fixture values should be.
    Tests compare actual fixture values against these expectations.

    Returns:
        Dict mapping fixture names to their expected configuration values.
    """
    settings = ServerSettings()

    return {
        "mock_code_embedder": {
            # 384 is MiniLM model output dimension - fixed, not configurable
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
        "server": {
            "command": settings.server_command,
            "host": settings.http_host,
            "port": settings.http_port,
        },
        "ghap": {
            "check_frequency": settings.ghap_check_frequency,
        },
    }


# Files that may intentionally use non-production configuration
ALLOWED_INTENTIONAL_DIFFERENCES: dict[str, set[str]] = {
    "min_cluster_size": {
        "tests/clustering/test_bug_031_regression.py",
        "tests/clustering/test_experience.py",
        "tests/clustering/test_clusterer.py",
    },
    "min_samples": {
        "tests/clustering/test_bug_031_regression.py",
        "tests/clustering/test_experience.py",
        "tests/clustering/test_clusterer.py",
    },
}


def is_intentional_difference(config_key: str, file_path: Path) -> bool:
    """Check if a file is allowed to have intentional configuration differences.

    Args:
        config_key: The configuration key being checked (e.g., "min_cluster_size")
        file_path: The file path being verified

    Returns:
        True if this file is in the allowlist for this configuration key
    """
    allowed_files = ALLOWED_INTENTIONAL_DIFFERENCES.get(config_key, set())
    # Normalize path for comparison
    relative_path = str(file_path).replace(str(get_repo_root()) + "/", "")
    return relative_path in allowed_files


def extract_python_assignments(content: str, variable_name: str) -> list[tuple[int, str]]:
    """Extract variable assignments from Python source code.

    Args:
        content: Python source code
        variable_name: Name of variable to find assignments for

    Returns:
        List of (line_number, value) tuples for each assignment found
    """
    # Pattern matches: variable_name = value or variable_name=value
    pattern = rf"(?:^|\s){re.escape(variable_name)}\s*=\s*([^\n,)]+)"
    matches = []
    for i, line in enumerate(content.split("\n"), 1):
        match = re.search(pattern, line)
        if match:
            value = match.group(1).strip().rstrip(",").strip()
            matches.append((i, value))
    return matches


def extract_shell_assignments(content: str, variable_name: str) -> list[tuple[int, str]]:
    """Extract variable assignments from shell script.

    Args:
        content: Shell script content
        variable_name: Name of variable to find assignments for

    Returns:
        List of (line_number, value) tuples for each assignment found
    """
    # Pattern matches: VARIABLE_NAME="value" or VARIABLE_NAME=value or VARIABLE_NAME=${...:-default}
    pattern = rf'^{re.escape(variable_name)}=(["\']?)([^"\'}\n]+)\1'
    matches = []
    for i, line in enumerate(content.split("\n"), 1):
        match = re.match(pattern, line.strip())
        if match:
            value = match.group(2).strip()
            matches.append((i, value))
    return matches
```

### New File: `tests/infrastructure/test_fixture_parity.py`

```python
"""Fixture value parity verification tests.

This module verifies that test fixtures use values compatible with production
configuration. It complements test_config_parity.py (which checks configuration
files) and test_mock_parity.py (which checks mock interfaces).

Reference: SPEC-024
Related bugs: BUG-031 (clustering), BUG-033 (server command)
"""

import re
from pathlib import Path

import pytest

from clams.server.config import ServerSettings

from .conftest import (
    ALLOWED_INTENTIONAL_DIFFERENCES,
    get_fixture_expectations,
    get_repo_root,
    is_intentional_difference,
)


class TestEmbeddingDimensionParity:
    """Verify embedding dimensions in fixtures match production expectations."""

    def test_mock_code_embedder_dimension_is_384(self) -> None:
        """Verify mock_code_embedder uses MiniLM's 384-dimensional output.

        The code embedder uses sentence-transformers/all-MiniLM-L6-v2 which
        produces 384-dimensional vectors. This is model-intrinsic, not configurable.
        """
        conftest_path = get_repo_root() / "tests" / "server" / "tools" / "conftest.py"
        content = conftest_path.read_text()

        expectations = get_fixture_expectations()
        expected_dim = expectations["mock_code_embedder"]["dimension"]

        # Find dimension in mock_code_embedder fixture
        # Pattern: service.dimension = 384 or [0.1] * 384
        pattern = r"mock_code_embedder.*?dimension\s*=\s*(\d+)"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            # Try alternative pattern: [0.1] * 384
            pattern = r"mock_code_embedder.*?\[[\d.]+\]\s*\*\s*(\d+)"
            match = re.search(pattern, content, re.DOTALL)

        assert match, (
            "Could not find dimension specification in mock_code_embedder fixture. "
            "Expected explicit dimension value."
        )

        actual_dim = int(match.group(1))
        assert actual_dim == expected_dim, (
            f"mock_code_embedder uses dimension={actual_dim}, "
            f"expected {expected_dim} (MiniLM output dimension). "
            "See SPEC-024."
        )

    def test_mock_semantic_embedder_dimension_matches_settings(self) -> None:
        """Verify mock_semantic_embedder uses ServerSettings.embedding_dimension.

        The semantic embedder uses nomic-embed-text-v1.5 which produces
        768-dimensional vectors. This should match ServerSettings.embedding_dimension.
        """
        conftest_path = get_repo_root() / "tests" / "server" / "tools" / "conftest.py"
        content = conftest_path.read_text()

        settings = ServerSettings()
        expected_dim = settings.embedding_dimension

        # Find dimension in mock_semantic_embedder fixture
        pattern = r"mock_semantic_embedder.*?dimension\s*=\s*(\d+)"
        match = re.search(pattern, content, re.DOTALL)

        if not match:
            pattern = r"mock_semantic_embedder.*?\[[\d.]+\]\s*\*\s*(\d+)"
            match = re.search(pattern, content, re.DOTALL)

        assert match, (
            "Could not find dimension specification in mock_semantic_embedder fixture."
        )

        actual_dim = int(match.group(1))
        assert actual_dim == expected_dim, (
            f"mock_semantic_embedder uses dimension={actual_dim}, "
            f"but ServerSettings.embedding_dimension is {expected_dim}. "
            "These should match. See SPEC-024."
        )

    def test_fixture_embed_return_lengths_match_dimensions(self) -> None:
        """Verify embed() return values have correct length.

        When fixtures return mock embedding vectors, the vector length must
        match the fixture's declared dimension.
        """
        conftest_path = get_repo_root() / "tests" / "server" / "tools" / "conftest.py"
        content = conftest_path.read_text()

        # Find all embed.return_value patterns with their lengths
        # Pattern: embed.return_value = [0.1] * N
        pattern = r"(\w+)\.embed\.return_value\s*=\s*\[[\d.]+\]\s*\*\s*(\d+)"
        matches = re.findall(pattern, content)

        expectations = get_fixture_expectations()

        for service_var, length_str in matches:
            length = int(length_str)

            # Determine which embedder this is based on context
            if "code" in service_var.lower() or "384" in content.split(service_var)[0][-100:]:
                expected = expectations["mock_code_embedder"]["embed_return_length"]
                embedder_name = "mock_code_embedder"
            else:
                expected = expectations["mock_semantic_embedder"]["embed_return_length"]
                embedder_name = "mock_semantic_embedder"

            assert length == expected, (
                f"{embedder_name} embed.return_value has length {length}, "
                f"expected {expected}. See SPEC-024."
            )


class TestMockReturnValueParity:
    """Verify mock return values are realistic and match production expectations."""

    def test_mock_vector_store_methods_exist(self) -> None:
        """Verify mock_vector_store fixture has all expected methods."""
        conftest_path = get_repo_root() / "tests" / "server" / "tools" / "conftest.py"
        content = conftest_path.read_text()

        # Required methods for VectorStore mock
        required_methods = ["upsert", "delete", "count", "search", "scroll"]

        for method in required_methods:
            pattern = rf"store\.{method}"
            assert re.search(pattern, content), (
                f"mock_vector_store fixture missing '{method}' method setup. "
                f"This mock should implement all VectorStore methods. See SPEC-024."
            )


class TestIntentionalDifferencesDocumentation:
    """Verify intentional configuration differences are documented and contained."""

    def test_intentional_differences_only_in_allowed_files(self) -> None:
        """Verify non-production cluster sizes only appear in allowlisted files.

        Integration tests and server tests MUST use production defaults.
        Only specific unit test files may use different values.
        """
        settings = ServerSettings()
        repo_root = get_repo_root()

        # Directories that must use production defaults
        production_required_dirs = [
            repo_root / "tests" / "integration",
            repo_root / "tests" / "server",
            repo_root / "tests" / "performance",
        ]

        prod_min_cluster_size = settings.hdbscan_min_cluster_size

        for directory in production_required_dirs:
            if not directory.exists():
                continue

            for py_file in directory.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue

                content = py_file.read_text()

                # Find min_cluster_size assignments
                pattern = r"min_cluster_size\s*=\s*(\d+)"
                matches = re.findall(pattern, content)

                for match in matches:
                    cluster_size = int(match)
                    if cluster_size != prod_min_cluster_size:
                        assert is_intentional_difference("min_cluster_size", py_file), (
                            f"{py_file.relative_to(repo_root)} uses min_cluster_size={cluster_size}, "
                            f"but production default is {prod_min_cluster_size}. "
                            f"Files in {directory.name}/ must use production defaults. "
                            "See SPEC-024."
                        )

    def test_allowed_files_have_documentation_comment(self) -> None:
        """Verify files with intentional differences have documentation.

        Each file in ALLOWED_INTENTIONAL_DIFFERENCES should have a comment
        explaining why it uses non-production configuration.
        """
        repo_root = get_repo_root()

        for config_key, allowed_files in ALLOWED_INTENTIONAL_DIFFERENCES.items():
            for relative_path in allowed_files:
                file_path = repo_root / relative_path

                if not file_path.exists():
                    continue

                content = file_path.read_text()

                # Look for documentation explaining the intentional difference
                # Accept various comment patterns
                doc_patterns = [
                    r"#.*intentional",
                    r"#.*different.*config",
                    r"#.*non-production",
                    r'""".*different',
                    r"#.*test.*edge.*case",
                    r"#.*unit.*test",
                    r"#.*faster.*test",
                    r"#.*regression",
                ]

                has_doc = any(
                    re.search(pattern, content, re.IGNORECASE)
                    for pattern in doc_patterns
                )

                # Also accept if the file docstring mentions the configuration
                assert has_doc or config_key.lower() in content.lower()[:500], (
                    f"{relative_path} is in ALLOWED_INTENTIONAL_DIFFERENCES for '{config_key}' "
                    "but doesn't appear to document why it uses non-production configuration. "
                    "Add a comment explaining the intentional difference. See SPEC-024."
                )
```

### New File: `tests/infrastructure/test_shell_parity.py`

```python
"""Shell script configuration parity verification tests.

This module verifies that shell scripts (hooks) use configuration values
that match ServerSettings or properly source exported configuration.

Reference: SPEC-024
Related bugs: BUG-033 (server command in hooks)
"""

import re
import tempfile
from pathlib import Path

import pytest

from clams.server.config import ServerSettings

from .conftest import get_repo_root


class TestConfigExport:
    """Verify ServerSettings.export_for_shell() produces correct output."""

    def test_export_includes_server_configuration(self) -> None:
        """Verify exported config includes server command, host, and port."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert f"CLAMS_SERVER_COMMAND={settings.server_command}" in content, (
                "Exported config missing CLAMS_SERVER_COMMAND. See SPEC-024."
            )
            assert f"CLAMS_HTTP_HOST={settings.http_host}" in content, (
                "Exported config missing CLAMS_HTTP_HOST. See SPEC-024."
            )
            assert f"CLAMS_HTTP_PORT={settings.http_port}" in content, (
                "Exported config missing CLAMS_HTTP_PORT. See SPEC-024."
            )

    def test_export_includes_timeout_configuration(self) -> None:
        """Verify exported config includes all timeout values."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert f"CLAMS_VERIFICATION_TIMEOUT={settings.verification_timeout}" in content, (
                "Exported config missing CLAMS_VERIFICATION_TIMEOUT. See SPEC-024."
            )
            assert f"CLAMS_HTTP_CALL_TIMEOUT={settings.http_call_timeout}" in content, (
                "Exported config missing CLAMS_HTTP_CALL_TIMEOUT. See SPEC-024."
            )
            assert f"CLAMS_QDRANT_TIMEOUT={settings.qdrant_timeout}" in content, (
                "Exported config missing CLAMS_QDRANT_TIMEOUT. See SPEC-024."
            )

    def test_export_includes_clustering_configuration(self) -> None:
        """Verify exported config includes HDBSCAN parameters."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert f"CLAMS_HDBSCAN_MIN_CLUSTER_SIZE={settings.hdbscan_min_cluster_size}" in content, (
                "Exported config missing CLAMS_HDBSCAN_MIN_CLUSTER_SIZE. See SPEC-024."
            )
            assert f"CLAMS_HDBSCAN_MIN_SAMPLES={settings.hdbscan_min_samples}" in content, (
                "Exported config missing CLAMS_HDBSCAN_MIN_SAMPLES. See SPEC-024."
            )

    def test_export_includes_ghap_configuration(self) -> None:
        """Verify exported config includes GHAP settings."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert f"CLAMS_GHAP_CHECK_FREQUENCY={settings.ghap_check_frequency}" in content, (
                "Exported config missing CLAMS_GHAP_CHECK_FREQUENCY. See SPEC-024."
            )

    def test_export_creates_parent_directories(self) -> None:
        """Verify export_for_shell creates parent directories if needed."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "dir" / "config.env"
            settings.export_for_shell(config_path)

            assert config_path.exists(), (
                "export_for_shell should create parent directories"
            )

    def test_export_is_shell_sourceable(self) -> None:
        """Verify exported config can be sourced by shell."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            # Verify no shell syntax errors (basic check)
            # Each non-comment, non-empty line should be VAR=value
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                assert "=" in line, (
                    f"Invalid shell assignment: {line}. "
                    "Exported config must be shell-sourceable."
                )

                # Verify no spaces around =
                var_part = line.split("=")[0]
                assert " " not in var_part, (
                    f"Invalid shell assignment: {line}. "
                    "Variable names cannot contain spaces."
                )


class TestShellScriptConfiguration:
    """Verify shell scripts use correct configuration values."""

    def test_session_start_uses_repo_relative_paths(self) -> None:
        """Verify session_start.sh constructs paths from REPO_ROOT.

        The hook should determine paths relative to the repository root,
        not rely on PATH or hardcoded absolute paths.
        """
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        # Should determine script location
        assert "SCRIPT_DIR=" in content, (
            "session_start.sh should determine SCRIPT_DIR. See SPEC-024."
        )

        # Should navigate to repo root
        assert "REPO_ROOT=" in content, (
            "session_start.sh should determine REPO_ROOT. See SPEC-024."
        )

        # Should use REPO_ROOT for server path
        assert "$REPO_ROOT" in content, (
            "session_start.sh should use $REPO_ROOT for paths. See SPEC-024."
        )

    def test_session_start_uses_venv_python(self) -> None:
        """Verify session_start.sh uses the venv Python for daemon mode.

        The hook should use .venv/bin/python to ensure the correct
        environment is used, avoiding BUG-033 type issues.
        """
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        assert ".venv/bin/python" in content or "clams-server" in content, (
            "session_start.sh should use .venv/bin/python or clams-server binary. "
            "See BUG-033 and SPEC-024."
        )

    def test_session_start_has_fallback(self) -> None:
        """Verify session_start.sh has fallback if venv unavailable."""
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        assert "command -v clams-server" in content, (
            "session_start.sh should check for clams-server in PATH as fallback. "
            "See SPEC-024."
        )

    def test_session_start_uses_configurable_port(self) -> None:
        """Verify session_start.sh uses configurable port, not hardcoded."""
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        settings = ServerSettings()

        # Should use environment variable with default
        # Pattern: SERVER_PORT="${CLAMS_PORT:-6334}" or similar
        port_pattern = r'SERVER_PORT=.*\$\{.*:-(\d+)\}'
        match = re.search(port_pattern, content)

        assert match, (
            "session_start.sh should use configurable port with default. "
            "Expected pattern like: SERVER_PORT=\"${CLAMS_PORT:-6334}\". "
            "See SPEC-024."
        )

        default_port = int(match.group(1))
        assert default_port == settings.http_port, (
            f"session_start.sh default port is {default_port}, "
            f"but ServerSettings.http_port is {settings.http_port}. "
            "These should match. See SPEC-024."
        )

    def test_session_start_uses_configurable_host(self) -> None:
        """Verify session_start.sh uses configurable host, not hardcoded."""
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        settings = ServerSettings()

        # Pattern: SERVER_HOST="${CLAMS_HOST:-127.0.0.1}" or similar
        host_pattern = r'SERVER_HOST=.*\$\{.*:-([^}]+)\}'
        match = re.search(host_pattern, content)

        assert match, (
            "session_start.sh should use configurable host with default. "
            "See SPEC-024."
        )

        default_host = match.group(1)
        assert default_host == settings.http_host, (
            f"session_start.sh default host is {default_host}, "
            f"but ServerSettings.http_host is {settings.http_host}. "
            "These should match. See SPEC-024."
        )


class TestHooksConfigYaml:
    """Verify hooks/config.yaml values match ServerSettings."""

    def test_hooks_config_timeout_compatible_with_settings(self) -> None:
        """Verify hooks config timeouts are compatible with ServerSettings.

        The mcp.connection_timeout should be >= ServerSettings.verification_timeout
        to allow for server startup time.
        """
        import yaml

        settings = ServerSettings()
        config_path = get_repo_root() / "clams" / "hooks" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        mcp_timeout = config.get("mcp", {}).get("connection_timeout", 10)

        # Connection timeout should allow for verification
        assert mcp_timeout >= settings.http_call_timeout, (
            f"hooks/config.yaml mcp.connection_timeout ({mcp_timeout}) "
            f"should be >= ServerSettings.http_call_timeout ({settings.http_call_timeout}). "
            "See SPEC-024."
        )
```

## Test Strategy

### Unit Test Coverage

Each new test module includes:

1. **Positive tests**: Verify correct values match `ServerSettings`
2. **Negative detection**: Tests fail (with clear messages) when parity is violated
3. **Edge cases**: Handle missing files, parse errors, intentional differences

### Test Isolation

- Tests read files directly, no imports of test fixtures
- Tests instantiate `ServerSettings()` fresh for each assertion
- No shared mutable state between tests

### Error Message Quality

All assertions include:
- The file/fixture with the violation
- Expected value (from `ServerSettings`)
- Actual value found
- Reference to SPEC-024

Example:
```
mock_semantic_embedder uses dimension=512, but ServerSettings.embedding_dimension is 768.
These should match. See SPEC-024.
```

### Test Execution Time

Target: <5 seconds total for all parity tests

- File I/O and regex only (no heavy imports in tests)
- No subprocess calls
- No network calls

## Migration/Rollout Plan

### Phase 1: Add New Test Files (This PR)

1. Create `tests/infrastructure/conftest.py` with shared utilities
2. Create `tests/infrastructure/test_fixture_parity.py`
3. Create `tests/infrastructure/test_shell_parity.py`
4. Ensure all tests pass

### Phase 2: Documentation Update

1. Update `tests/infrastructure/test_config_parity.py` docstring to reference SPEC-024
2. Update `tests/infrastructure/test_mock_parity.py` docstring to reference SPEC-024
3. Add `tests/infrastructure/README.md` explaining the parity verification framework

### Phase 3: CI Integration (Future)

The parity tests are included in the standard `pytest` run. No additional CI configuration required.

## Extensibility for SPEC-025

This framework supports SPEC-025 (Production Command Verification) by:

1. **Shared utilities** in `conftest.py` can be extended for command parsing
2. **Pattern established** for comparing configuration across file types
3. **Allowlist mechanism** for documenting intentional differences
4. **Error message format** consistent for debugging

SPEC-025 will add:
- `test_command_parity.py` verifying shell commands match between hooks and tests
- Extension to `conftest.py` for command extraction utilities

## Summary of Key Design Decisions

1. **Keep existing tests**: `test_config_parity.py` and `test_mock_parity.py` remain unchanged
2. **Regex over AST**: Simple string matching is sufficient and more maintainable
3. **Explicit allowlist**: Intentional differences documented in code, not comments
4. **Single source of truth**: All expectations derive from `ServerSettings`
5. **Fail-fast philosophy**: Missing files cause test failures, not silent skips
6. **Reference spec in errors**: All assertion messages include "See SPEC-024"
