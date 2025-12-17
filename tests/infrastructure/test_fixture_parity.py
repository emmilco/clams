"""Fixture value parity verification tests.

This module verifies that test fixtures use values compatible with production
configuration. It complements test_config_parity.py (which checks configuration
files) and test_mock_parity.py (which checks mock interfaces).

Reference: SPEC-024 (Configuration Parity Verification)
Related bugs: BUG-031 (clustering), BUG-033 (server command)
"""

import re
from pathlib import Path

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
        pattern = r"\.embed\.return_value\s*=\s*\[[\d.]+\]\s*\*\s*(\d+)"
        matches = re.findall(pattern, content)

        expectations = get_fixture_expectations()

        # We expect two matches: one for 384 (code) and one for 768 (semantic)
        expected_lengths = {
            expectations["mock_code_embedder"]["embed_return_length"],
            expectations["mock_semantic_embedder"]["embed_return_length"],
        }

        actual_lengths = {int(m) for m in matches}

        assert actual_lengths == expected_lengths, (
            f"embed.return_value lengths are {actual_lengths}, "
            f"expected {expected_lengths}. "
            "Embedding return lengths should match dimensions. See SPEC-024."
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
                            f"{py_file.relative_to(repo_root)} uses "
                            f"min_cluster_size={cluster_size}, "
                            f"but production default is {prod_min_cluster_size}. "
                            f"Files in {directory.name}/ must use production defaults. "
                            "See SPEC-024."
                        )

    def test_allowed_files_documented_in_config_parity(self) -> None:
        """Verify allowed files are documented in test_config_parity.py.

        The central documentation for intentional differences is in
        test_config_parity.py's module docstring. This test verifies that
        each allowed file is mentioned there.
        """
        repo_root = get_repo_root()
        config_parity_path = repo_root / "tests" / "infrastructure" / "test_config_parity.py"
        config_parity_content = config_parity_path.read_text()

        for config_key, allowed_files in ALLOWED_INTENTIONAL_DIFFERENCES.items():
            for relative_path in allowed_files:
                # Each allowed file should be mentioned in test_config_parity.py
                # Either by full path or just filename
                file_name = Path(relative_path).name
                assert file_name in config_parity_content or relative_path in config_parity_content, (
                    f"{relative_path} is in ALLOWED_INTENTIONAL_DIFFERENCES "
                    f"for '{config_key}' "
                    "but is not documented in test_config_parity.py. "
                    "Add documentation for this intentional difference. See SPEC-024."
                )

    def test_allowed_files_are_not_integration_tests(self) -> None:
        """Verify allowlisted files are unit tests, not integration tests.

        Integration tests must always use production defaults to catch
        configuration drift issues.
        """
        integration_prefixes = [
            "tests/integration/",
            "tests/server/",
            "tests/performance/",
        ]

        for config_key, allowed_files in ALLOWED_INTENTIONAL_DIFFERENCES.items():
            for relative_path in allowed_files:
                for prefix in integration_prefixes:
                    assert not relative_path.startswith(prefix), (
                        f"{relative_path} is in ALLOWED_INTENTIONAL_DIFFERENCES "
                        f"for '{config_key}', "
                        f"but files in {prefix} must use production defaults. "
                        "Remove this file from the allowlist and fix its configuration."
                    )
