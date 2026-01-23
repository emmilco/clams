"""Lazy import isolation tests for CLAMS.

These tests verify that light imports (clams, clams.embedding, clams.server.main, etc.)
do NOT load heavy packages (torch, sentence_transformers) into sys.modules.

This catches transitive dependencies that accidentally import heavy packages,
which would cause:
1. Slow startup times (4-6+ seconds)
2. Fork failures on macOS MPS (BUG-042)

The tests use subprocess isolation to ensure a fresh Python interpreter state,
so we get accurate sys.modules inspection without test runner pollution.

Reference: BUG-037, BUG-042, SPEC-027
"""

import subprocess
import sys

import pytest

# Heavy packages that should NOT be loaded by light imports
# These are the packages that cause slow startup and fork issues
HEAVY_PACKAGES = ["torch", "sentence_transformers", "transformers"]

# Modules that should NOT load heavy packages
# These are the critical paths that must remain lightweight
LIGHT_MODULES = [
    "clams",
    "clams.server",
    "clams.server.main",
    "clams.server.http",
    "clams.server.config",
    "clams.embedding",
    "clams.storage",
    "clams.search",
]


def _check_heavy_package_loaded(module: str, heavy_package: str) -> bool:
    """Check if importing a module loads a heavy package.

    Args:
        module: The module to import
        heavy_package: The heavy package to check for

    Returns:
        True if the heavy package was loaded, False otherwise
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import sys; import {module}; print('{heavy_package}' in sys.modules)",
        ],
        capture_output=True,
        timeout=30,
    )

    if result.returncode != 0:
        # Import failed, treat as loaded (will fail the test with import error)
        return True

    return result.stdout.decode().strip() == "True"


class TestLazyImportIsolation:
    """Verify heavy packages are not loaded by light imports.

    Each test verifies that importing a light module does NOT cause
    heavy packages (torch, sentence_transformers, transformers) to
    be loaded into sys.modules.

    This protects against:
    1. Accidentally adding top-level imports of heavy packages
    2. Transitive dependencies that import heavy packages
    3. Module-level code that triggers heavy imports

    Reference: BUG-037, BUG-042, SPEC-027
    """

    @pytest.mark.parametrize("module", LIGHT_MODULES)
    @pytest.mark.parametrize("heavy_package", HEAVY_PACKAGES)
    def test_light_import_does_not_load_heavy(
        self, module: str, heavy_package: str
    ) -> None:
        """Importing a light module must not load heavy packages.

        This test runs in a subprocess to get a clean Python interpreter
        state, then imports the specified module and checks if any heavy
        packages ended up in sys.modules.

        Args:
            module: The light module to import
            heavy_package: The heavy package that should NOT be loaded
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys; import {module}; "
                f"print('{heavy_package}' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        # First check import succeeded
        assert result.returncode == 0, (
            f"Import check failed for {module}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        # Then check heavy package was not loaded
        heavy_loaded = result.stdout.decode().strip()
        assert heavy_loaded == "False", (
            f"{heavy_package} was loaded by `import {module}`.\n"
            "This breaks the lazy import pattern and will cause:\n"
            "  1. Slow startup (4-6+ seconds)\n"
            "  2. Fork failures on macOS MPS (BUG-042)\n"
            f"Check that {heavy_package} is only imported inside functions, "
            "not at module level.\n"
            f"Debug: python -c \"import sys; import {module}; "
            f"print([m for m in sys.modules if '{heavy_package}' in m.lower()])\""
        )


class TestSpecificLazyImports:
    """Specific lazy import tests with detailed documentation.

    These tests duplicate some coverage from TestLazyImportIsolation but
    provide explicit test names and detailed docstrings for clarity.
    They serve as documentation of the expected lazy import behavior.

    Reference: BUG-037, BUG-042
    """

    def test_clams_does_not_load_torch(self) -> None:
        """Verify `import clams` does not load torch.

        The top-level clams package should only load version info and
        re-export public APIs. It must NOT trigger PyTorch loading.

        Failure indicates a top-level import in clams/__init__.py or
        one of its submodules that transitively imports torch.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clams; print('torch' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import check failed.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        torch_loaded = result.stdout.decode().strip()
        assert torch_loaded == "False", (
            "torch was loaded by `import clams`.\n"
            "This breaks the lazy import pattern.\n"
            "Check clams/__init__.py and its imports."
        )

    def test_clams_embedding_does_not_load_torch(self) -> None:
        """Verify `import clams.embedding` does not load torch.

        The embedding module exposes base classes and registry but should
        NOT load actual model implementations (MiniLM, Nomic) which require
        PyTorch. Models should only be loaded when accessed via the registry.

        Failure indicates that model classes are imported at module level
        instead of lazily through the registry.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clams.embedding; print('torch' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import check failed.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        torch_loaded = result.stdout.decode().strip()
        assert torch_loaded == "False", (
            "torch was loaded by `import clams.embedding`.\n"
            "This breaks the lazy import pattern.\n"
            "Model classes (MiniLMEmbedding, NomicEmbedding) should only be\n"
            "imported inside functions, not at module level.\n"
            "Check clams/embedding/__init__.py"
        )

    def test_clams_server_main_does_not_load_torch(self) -> None:
        """Verify `import clams.server.main` does not load torch.

        The server entry point is critical for CLI responsiveness. It handles:
        - --help output
        - --stop command (daemon shutdown)
        - --daemon flag (background process)

        All of these must work without loading PyTorch, which takes 3-4 seconds.
        Additionally, loading PyTorch before fork() on macOS causes MPS failures.

        Failure indicates the main module or its argument parsing code is
        loading heavy dependencies at import time.

        Reference: BUG-042 (fork failures on macOS)
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clams.server.main; print('torch' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import check failed.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        torch_loaded = result.stdout.decode().strip()
        assert torch_loaded == "False", (
            "torch was loaded by `import clams.server.main`.\n"
            "This breaks CLI responsiveness and causes fork failures on macOS.\n"
            "The server entry point must NOT import heavy dependencies.\n"
            "See BUG-042 for context."
        )

    def test_clams_server_http_does_not_load_torch(self) -> None:
        """Verify `import clams.server.http` does not load torch.

        The HTTP transport module is used for daemon management (health checks,
        shutdown commands). It must import quickly without loading PyTorch.

        Failure indicates the HTTP module has a dependency that loads torch.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clams.server.http; print('torch' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import check failed.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        torch_loaded = result.stdout.decode().strip()
        assert torch_loaded == "False", (
            "torch was loaded by `import clams.server.http`.\n"
            "This breaks daemon management responsiveness.\n"
            "The HTTP module must NOT import heavy dependencies."
        )

    def test_clams_does_not_load_sentence_transformers(self) -> None:
        """Verify `import clams` does not load sentence_transformers.

        sentence_transformers is another heavy dependency that transitively
        imports PyTorch. It should only be loaded when actually needed for
        embedding generation.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clams; "
                "print('sentence_transformers' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import check failed.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        st_loaded = result.stdout.decode().strip()
        assert st_loaded == "False", (
            "sentence_transformers was loaded by `import clams`.\n"
            "This breaks the lazy import pattern and causes slow startup."
        )

    def test_clams_embedding_does_not_load_sentence_transformers(self) -> None:
        """Verify `import clams.embedding` does not load sentence_transformers.

        The embedding module registry should not import sentence_transformers
        until a model that requires it is actually instantiated.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import clams.embedding; "
                "print('sentence_transformers' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"Import check failed.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        st_loaded = result.stdout.decode().strip()
        assert st_loaded == "False", (
            "sentence_transformers was loaded by `import clams.embedding`.\n"
            "This breaks the lazy import pattern.\n"
            "Model classes should only import sentence_transformers when instantiated."
        )
