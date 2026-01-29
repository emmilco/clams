"""Configuration parity verification tests.

This module verifies that test and production configurations remain aligned,
preventing "works in test, fails in production" bugs like BUG-031 and BUG-033.

BUG-031: Tests used min_cluster_size=3 but production used min_cluster_size=5.
BUG-033: Tests used .venv/bin/clams-server correctly but hooks used python -m clams.

These tests fail if:
1. Test fixtures use different configuration than production defaults
2. Hook configuration diverges from integration test setup
3. Hardcoded values don't match ServerSettings

Intentional Differences (Documented):
--------------------------------------
Some test files intentionally use different parameters to test edge cases:

- tests/clustering/test_bug_031_regression.py:
  Uses min_cluster_size=3, min_samples=2 to test the BUG-031 fix behavior
  with smaller clusters. This is intentional for regression testing.

- tests/clustering/test_experience.py:
  Uses min_cluster_size=3 for faster test execution with smaller datasets.
  This is acceptable because these are unit tests, not integration tests.

- tests/clustering/test_clusterer.py:
  Uses min_cluster_size=3 for basic clustering unit tests.
  This is acceptable because these are unit tests, not integration tests.

All integration tests (tests/integration/) and production-like tests
(tests/server/tools/) MUST use production defaults.
"""

import re
from pathlib import Path

import yaml

from clams.server.config import ServerSettings


class TestClusteringConfiguration:
    """Verify clustering configuration parity between tests and production."""

    def test_production_clustering_defaults(self) -> None:
        """Verify ServerSettings has expected clustering defaults.

        This is the canonical source of truth for clustering configuration.
        If these values change, update all affected documentation and tests.
        """
        settings = ServerSettings()

        # Document production defaults
        assert settings.hdbscan_min_cluster_size == 5, (
            "Production min_cluster_size should be 5 "
            "(conservative default for real-world data density)"
        )
        assert settings.hdbscan_min_samples == 3, (
            "Production min_samples should be 3 "
            "(provides noise resilience without being too strict)"
        )

    def test_integration_tests_use_production_defaults(self) -> None:
        """Verify integration tests use production clustering defaults.

        Integration tests should mirror production behavior exactly.
        Unit tests may use different values for testing edge cases.
        """
        settings = ServerSettings()
        prod_min_cluster_size = settings.hdbscan_min_cluster_size
        prod_min_samples = settings.hdbscan_min_samples

        # Read integration test file
        repo_root = Path(__file__).parent.parent.parent
        e2e_test = repo_root / "tests" / "integration" / "test_e2e.py"
        e2e_content = e2e_test.read_text()

        # Find Clusterer instantiation in test_e2e.py
        # Pattern: Clusterer(min_cluster_size=X, min_samples=Y)
        clusterer_pattern = r"Clusterer\s*\(\s*min_cluster_size\s*=\s*(\d+)"
        matches = re.findall(clusterer_pattern, e2e_content)

        assert len(matches) > 0, (
            "test_e2e.py should contain Clusterer instantiation "
            "with explicit min_cluster_size"
        )

        for match in matches:
            test_min_cluster_size = int(match)
            assert test_min_cluster_size == prod_min_cluster_size, (
                f"test_e2e.py uses min_cluster_size={test_min_cluster_size} "
                f"but production default is {prod_min_cluster_size}. "
                "Integration tests must use production defaults."
            )

        # Also verify min_samples where specified
        samples_pattern = r"Clusterer\s*\([^)]*min_samples\s*=\s*(\d+)"
        samples_matches = re.findall(samples_pattern, e2e_content)
        for match in samples_matches:
            test_min_samples = int(match)
            assert test_min_samples == prod_min_samples, (
                f"test_e2e.py uses min_samples={test_min_samples} "
                f"but production default is {prod_min_samples}. "
                "Integration tests must use production defaults."
            )

    def test_server_tools_tests_use_production_defaults(self) -> None:
        """Verify server tool tests use production clustering defaults.

        Tests in tests/server/tools/ should use production configuration
        since they test server behavior as users experience it.
        """
        settings = ServerSettings()
        prod_min_cluster_size = settings.hdbscan_min_cluster_size
        prod_min_samples = settings.hdbscan_min_samples

        repo_root = Path(__file__).parent.parent.parent
        bug_005_test = (
            repo_root
            / "tests"
            / "server"
            / "tools"
            / "test_bug_005_clusterer_initialization.py"
        )
        test_content = bug_005_test.read_text()

        # This file should use production defaults (5, 3)
        pattern = r"min_cluster_size\s*=\s*(\d+)"
        matches = re.findall(pattern, test_content)

        for match in matches:
            cluster_size = int(match)
            assert cluster_size == prod_min_cluster_size, (
                f"test_bug_005_clusterer_initialization.py uses "
                f"min_cluster_size={cluster_size} "
                f"but production default is {prod_min_cluster_size}"
            )

        pattern = r"min_samples\s*=\s*(\d+)"
        matches = re.findall(pattern, test_content)

        for match in matches:
            samples = int(match)
            assert samples == prod_min_samples, (
                f"test_bug_005_clusterer_initialization.py uses "
                f"min_samples={samples} "
                f"but production default is {prod_min_samples}"
            )

    def test_performance_benchmarks_use_production_defaults(self) -> None:
        """Verify performance benchmarks use production clustering defaults.

        Benchmarks should measure production-like behavior.
        """
        settings = ServerSettings()
        prod_min_cluster_size = settings.hdbscan_min_cluster_size
        prod_min_samples = settings.hdbscan_min_samples

        repo_root = Path(__file__).parent.parent.parent
        benchmark_test = repo_root / "tests" / "performance" / "test_benchmarks.py"

        if not benchmark_test.exists():
            # Skip if benchmark file doesn't exist
            return

        test_content = benchmark_test.read_text()

        # Find Clusterer with explicit parameters
        pattern = r"Clusterer\s*\(\s*min_cluster_size\s*=\s*(\d+)\s*,\s*min_samples\s*=\s*(\d+)"
        matches = re.findall(pattern, test_content)

        for min_cluster, min_samples in matches:
            assert int(min_cluster) == prod_min_cluster_size, (
                f"test_benchmarks.py uses min_cluster_size={min_cluster} "
                f"but production default is {prod_min_cluster_size}"
            )
            assert int(min_samples) == prod_min_samples, (
                f"test_benchmarks.py uses min_samples={min_samples} "
                f"but production default is {prod_min_samples}"
            )


class TestServerCommandConfiguration:
    """Verify server command parity between hooks, tests, and config."""

    def test_hooks_config_uses_correct_server_command(self) -> None:
        """Verify hooks config.yaml uses correct server command.

        The server command should be .venv/bin/clams-server (as array).
        This aligns with the pyproject.toml entry point and how
        integration tests invoke the server.
        """
        repo_root = Path(__file__).parent.parent.parent
        config_path = repo_root / "clams_scripts" / "hooks" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        mcp_config = config.get("mcp", {})
        server_command = mcp_config.get("server_command", [])

        # Should be [".venv/bin/clams-server"]
        assert server_command == [".venv/bin/clams-server"], (
            f"hooks/config.yaml server_command is {server_command}, "
            'expected [".venv/bin/clams-server"]'
        )

    def test_integration_tests_use_correct_server_command(self) -> None:
        """Verify integration tests use correct server command.

        Tests should use .venv/bin/clams-server, not python -m clams.
        """
        repo_root = Path(__file__).parent.parent.parent
        mcp_test = repo_root / "tests" / "integration" / "test_mcp_protocol.py"
        test_content = mcp_test.read_text()

        # Should use clams-server binary
        assert ".venv/bin/clams-server" in test_content, (
            "test_mcp_protocol.py should use .venv/bin/clams-server"
        )

        # Should NOT use python -m clams (the old buggy pattern)
        assert "python -m clams" not in test_content, (
            "test_mcp_protocol.py should NOT use python -m clams "
            "(this was the BUG-033 bug pattern)"
        )

    def test_mcp_client_uses_correct_server_path(self) -> None:
        """Verify mcp_client.py computes correct server path.

        The get_clams_server_path() function should return path ending with
        .venv/bin/clams-server. We verify this by reading the source code
        since mcp_client.py is not part of the installed package.
        """
        repo_root = Path(__file__).parent.parent.parent
        mcp_client_path = repo_root / "clams_scripts" / "mcp_client.py"
        source = mcp_client_path.read_text()

        # Verify the function constructs the correct path
        assert ".venv" in source, (
            "mcp_client.py should reference .venv directory"
        )
        assert "bin" in source, (
            "mcp_client.py should reference bin directory"
        )
        assert "clams-server" in source, (
            "mcp_client.py should reference clams-server binary"
        )

        # Verify the path construction pattern
        assert 'os.path.join(repo_root, ".venv", "bin", "clams-server")' in source, (
            "mcp_client.py should construct path using os.path.join "
            'with repo_root, ".venv", "bin", "clams-server"'
        )

    def test_hooks_and_tests_use_same_command_pattern(self) -> None:
        """Verify hooks and integration tests use consistent server invocation.

        Both should use the .venv/bin/clams-server binary, not module invocation.
        """
        repo_root = Path(__file__).parent.parent.parent

        # Read hooks config
        config_path = repo_root / "clams_scripts" / "hooks" / "config.yaml"
        with open(config_path) as f:
            hook_config = yaml.safe_load(f)

        hook_command = hook_config.get("mcp", {}).get("server_command", [])

        # Read test fixture
        mcp_test = repo_root / "tests" / "integration" / "test_mcp_protocol.py"
        test_content = mcp_test.read_text()

        # Extract command from test
        # Pattern: command=".venv/bin/clams-server"
        import re

        match = re.search(r'command="([^"]+)"', test_content)
        assert match, "Could not find command= in test_mcp_protocol.py"
        test_command = match.group(1)

        # Verify consistency
        # hook_command is a list, test_command is a string
        assert hook_command[0] == test_command, (
            f"Hook config uses {hook_command[0]} but test uses {test_command}. "
            "These should be identical to prevent BUG-033 type issues."
        )


class TestSessionStartHookConfiguration:
    """Verify session_start.sh uses correct configuration."""

    def test_session_start_constructs_server_path_correctly(self) -> None:
        """Verify session_start.sh uses repo-relative path to server.

        The hook should construct the server path from REPO_ROOT,
        not rely on PATH or assume specific installation locations.
        """
        repo_root = Path(__file__).parent.parent.parent
        hook_path = repo_root / "clams_scripts" / "hooks" / "session_start.sh"
        hook_content = hook_path.read_text()

        # Should navigate to repo root from script location
        assert "SCRIPT_DIR=" in hook_content, (
            "session_start.sh should determine SCRIPT_DIR"
        )
        assert "REPO_ROOT=" in hook_content, (
            "session_start.sh should determine REPO_ROOT from SCRIPT_DIR"
        )

        # Should use python from .venv (for daemon mode)
        # The current implementation uses: $REPO_ROOT/.venv/bin/python -m clams.server.main
        # This is acceptable for daemon startup as it uses the venv's Python
        assert ".venv/bin/python" in hook_content or "clams-server" in hook_content, (
            "session_start.sh should use .venv/bin/python or clams-server binary"
        )

    def test_session_start_has_clams_server_fallback(self) -> None:
        """Verify session_start.sh has fallback to clams-server if in PATH."""
        repo_root = Path(__file__).parent.parent.parent
        hook_path = repo_root / "clams_scripts" / "hooks" / "session_start.sh"
        hook_content = hook_path.read_text()

        # Should have fallback: command -v clams-server
        assert "command -v clams-server" in hook_content, (
            "session_start.sh should check for clams-server in PATH as fallback"
        )


class TestGHAPFrequencyConfiguration:
    """Verify GHAP check frequency is consistent."""

    def test_ghap_frequency_matches_production(self) -> None:
        """Verify GHAP check frequency in hooks matches production config."""
        settings = ServerSettings()
        prod_frequency = settings.ghap_check_frequency

        repo_root = Path(__file__).parent.parent.parent
        config_path = repo_root / "clams_scripts" / "hooks" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        hook_frequency = config.get("hooks", {}).get("ghap_checkin", {}).get("frequency")

        assert hook_frequency == prod_frequency, (
            f"hooks/config.yaml ghap_checkin.frequency is {hook_frequency}, "
            f"but ServerSettings.ghap_check_frequency is {prod_frequency}. "
            "These should match."
        )


class TestDocumentedDifferences:
    """Tests that document intentional differences between test and production.

    These tests don't fail - they document expected variations and verify
    the variations are in expected files (not leaking into production code).
    """

    def test_intentional_differences_are_in_unit_tests_only(self) -> None:
        """Verify non-production cluster sizes only appear in unit tests.

        Files that may use min_cluster_size != 5:
        - tests/clustering/test_*.py (unit tests)
        - tests/clustering/test_bug_031_regression.py (regression test)

        Files that MUST use min_cluster_size == 5:
        - tests/integration/* (integration tests)
        - tests/server/tools/* (server tests)
        - src/* (production code)
        """
        settings = ServerSettings()
        prod_min_cluster_size = settings.hdbscan_min_cluster_size

        repo_root = Path(__file__).parent.parent.parent

        # Files that MUST use production defaults
        must_use_prod_defaults = [
            repo_root / "tests" / "integration" / "test_e2e.py",
            repo_root
            / "tests"
            / "server"
            / "tools"
            / "test_bug_005_clusterer_initialization.py",
        ]

        for filepath in must_use_prod_defaults:
            if not filepath.exists():
                continue

            content = filepath.read_text()
            # Find all min_cluster_size values
            pattern = r"min_cluster_size\s*=\s*(\d+)"
            matches = re.findall(pattern, content)

            for match in matches:
                cluster_size = int(match)
                # Allow 5 (production) or documented exceptions
                # test_e2e.py should only use 5
                assert cluster_size == prod_min_cluster_size, (
                    f"{filepath.name} uses min_cluster_size={cluster_size} "
                    f"but production default is {prod_min_cluster_size}. "
                    "This file must use production defaults."
                )
