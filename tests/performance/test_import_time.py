"""Import time tests for CLAMS.

Tests measure cold-start import time to catch regressions in module loading.
Uses subprocess for isolated measurement (no module caching effects).

Performance targets:
- All core modules must import in < 3.0 seconds
- This includes: clams, clams.server, clams.server.main, clams.server.http,
  clams.server.config, clams.embedding, clams.storage, clams.search

Expected baseline (as of BUG-037 investigation):
- Top-level import: ~0.1-0.3 seconds (lightweight, version info only)
- Core submodules: ~0.1-0.5 seconds (base classes, registry)
- HTTP module: ~1.5-2.5 seconds (starlette, uvicorn, mcp dependencies)
- Full model loading (clams.embedding.minilm): 4-6+ seconds (loads PyTorch)

The 3.0-second threshold protects against accidentally importing heavy dependencies
(torch, sentence_transformers) at module level, which caused BUG-037 and BUG-042,
while allowing legitimate web framework imports that vary from 1.5-2.5s depending
on system load.

Reference: BUG-037, BUG-042, SPEC-027
"""

import subprocess
import sys
import time

import pytest

# Import time threshold in seconds
# 3.0s provides buffer above web framework imports (~1.5-2.5s for starlette/uvicorn)
# with additional margin for system load variability on CI runners
# This still catches PyTorch loads which take 4-6+ seconds
# Note: Some modules like clams.server.http legitimately import heavy web
# frameworks (starlette, uvicorn) which can take up to 2.5s depending on system load
IMPORT_TIME_THRESHOLD_SECONDS = 3.0

# Critical modules that must import quickly
# These are public entry points that should not load heavy dependencies
CRITICAL_MODULES = [
    "clams",
    "clams.server",
    "clams.server.main",
    "clams.server.http",
    "clams.server.config",
    "clams.embedding",
    "clams.storage",
    "clams.search",
]


def _measure_import_time(module: str) -> tuple[float, subprocess.CompletedProcess[bytes]]:
    """Measure import time for a module using subprocess isolation.

    Args:
        module: The module name to import (e.g., "clams.embedding")

    Returns:
        Tuple of (elapsed_time_seconds, subprocess_result)
    """
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        timeout=30,
    )
    elapsed = time.perf_counter() - start
    return elapsed, result


def _format_import_failure_message(
    module: str, elapsed: float, threshold: float
) -> str:
    """Format actionable failure message for import time violations.

    Args:
        module: The module that exceeded the threshold
        elapsed: Actual import time in seconds
        threshold: Maximum allowed import time in seconds

    Returns:
        Formatted error message with diagnostic guidance
    """
    return f"""
FAILED: Import of {module} took {elapsed:.2f}s, expected < {threshold:.1f}s

This likely means a heavy dependency (torch, sentence_transformers) is
being imported at module level instead of lazily.

To diagnose:
  python -c "import sys; import {module}; print([m for m in sys.modules if 'torch' in m])"

Common causes:
  1. Top-level import of torch or sentence_transformers
  2. Importing model class instead of using registry
  3. Transitive dependency that imports torch

See BUG-037 and BUG-042 for context.
"""


class TestCoreModuleImportTime:
    """Import time tests for all critical modules.

    Each module in the critical path must import in under 3.0 seconds.
    This catches regressions where heavy dependencies (torch, sentence_transformers)
    are accidentally imported at module level.

    Reference: BUG-037, BUG-042, SPEC-027
    """

    @pytest.mark.parametrize("module", CRITICAL_MODULES)
    def test_module_import_under_threshold(self, module: str) -> None:
        """Each core module must import in < 3.0s.

        Uses subprocess isolation to measure cold-start import time,
        avoiding any module caching effects from the test process itself.

        Args:
            module: The module to test from CRITICAL_MODULES list
        """
        elapsed, result = _measure_import_time(module)

        # Verify import succeeded
        assert result.returncode == 0, (
            f"Import of {module} failed with returncode {result.returncode}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        # Verify import time is under threshold
        assert elapsed < IMPORT_TIME_THRESHOLD_SECONDS, (
            _format_import_failure_message(module, elapsed, IMPORT_TIME_THRESHOLD_SECONDS)
        )


class TestImportTime:
    """Legacy import time tests with explicit test methods.

    These tests provide explicit test names for clarity and backward compatibility.
    They test the same modules as TestCoreModuleImportTime but with detailed
    docstrings explaining the purpose of each test.

    Reference: BUG-037, BUG-042
    """

    def test_clams_import_time_under_threshold(self) -> None:
        """Top-level `import clams` must complete in < 3.0 seconds.

        This test runs in a subprocess to measure cold-start import time,
        avoiding any module caching effects from the test process itself.

        The 3.0-second threshold ensures no heavy dependencies (torch,
        sentence_transformers) are imported at module level.

        Expected time: ~0.1-0.3 seconds for lightweight top-level import.
        Failure indicates: Heavy dependency imported at module level.

        Reference: BUG-037 (import timeouts), BUG-042 (fork after PyTorch init)
        """
        elapsed, result = _measure_import_time("clams")

        # Verify import succeeded
        assert result.returncode == 0, (
            f"Import failed with returncode {result.returncode}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        # Verify import time is under threshold
        assert elapsed < IMPORT_TIME_THRESHOLD_SECONDS, (
            _format_import_failure_message("clams", elapsed, IMPORT_TIME_THRESHOLD_SECONDS)
        )

    def test_clams_embedding_import_time_under_threshold(self) -> None:
        """Import of `clams.embedding` must complete in < 3.0 seconds.

        The embedding module is designed with lazy imports - it should only
        load base classes and the registry, not the actual embedding models
        (MiniLM, Nomic) which require PyTorch.

        Expected time: ~0.3-0.5 seconds for base classes and registry.
        Failure indicates: Model classes imported at embedding module level.

        Reference: clams/embedding/__init__.py design notes
        """
        elapsed, result = _measure_import_time("clams.embedding")

        # Verify import succeeded
        assert result.returncode == 0, (
            f"Import failed with returncode {result.returncode}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        # Verify import time is under threshold
        assert elapsed < IMPORT_TIME_THRESHOLD_SECONDS, (
            _format_import_failure_message(
                "clams.embedding", elapsed, IMPORT_TIME_THRESHOLD_SECONDS
            )
        )

    @pytest.mark.slow
    def test_clams_embedding_models_are_lazy(self) -> None:
        """Verify that importing clams.embedding does NOT load PyTorch.

        This is a more rigorous check that the lazy import pattern is working.
        We verify that torch is NOT in sys.modules after importing clams.embedding.

        If torch appears in sys.modules, it means something in the import chain
        is eagerly loading PyTorch, which will cause:
        1. Slow import times (4-6+ seconds)
        2. Fork failures on macOS (BUG-042)
        """
        # Check if torch gets loaded by importing clams.embedding
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import clams.embedding; import sys; "
                "print('torch' in sys.modules)",
            ],
            capture_output=True,
            timeout=30,  # Allow more time in case torch IS loaded
        )

        assert result.returncode == 0, (
            f"Check failed with returncode {result.returncode}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        torch_loaded = result.stdout.decode().strip()
        assert torch_loaded == "False", (
            "PyTorch was loaded by `import clams.embedding`.\n"
            "This breaks the lazy import pattern and will cause:\n"
            "  1. Slow startup (4-6+ seconds)\n"
            "  2. Fork failures on macOS MPS (BUG-042)\n"
            "Check that model classes (MiniLMEmbedding, NomicEmbedding) are only "
            "imported inside functions, not at module level."
        )

    @pytest.mark.slow
    def test_torch_import_baseline(self) -> None:
        """Document torch import time (not enforced, baseline only).

        This test is marked @slow and documents the expected baseline
        for heavy package imports. It does NOT enforce any threshold.

        Expected baseline: 2-4 seconds for torch

        Reference: BUG-037 investigation notes
        """
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-c", "import torch"],
            capture_output=True,
            timeout=60,
        )
        elapsed = time.perf_counter() - start

        # Log but don't assert - this is documentation only
        if result.returncode == 0:
            print(f"torch import baseline: {elapsed:.2f}s")
        else:
            pytest.skip("torch not installed")
