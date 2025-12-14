"""Import time tests for CLAMS.

Tests measure cold-start import time to catch regressions in module loading.
Uses subprocess for isolated measurement (no module caching effects).

Performance targets:
- `import clams` (top-level): < 2 seconds
- `import clams.embedding` (loads base classes, not models): < 2 seconds

Expected baseline (as of BUG-037 investigation):
- Top-level import: ~0.1-0.3 seconds (lightweight, version info only)
- Embedding submodule: ~0.3-0.5 seconds (base classes, registry)
- Full model loading (clams.embedding.minilm): 4-6+ seconds (loads PyTorch)

The 2-second threshold protects against accidentally importing heavy dependencies
(torch, sentence_transformers) at module level, which caused BUG-037 and BUG-042.

Reference: BUG-037, BUG-042
"""

import subprocess
import sys
import time

import pytest

# Import time threshold in seconds
# This is strict to catch heavy imports early - see BUG-037
IMPORT_TIME_THRESHOLD_SECONDS = 2.0


class TestImportTime:
    """Test import times for regression tracking."""

    def test_clams_import_time_under_threshold(self) -> None:
        """Top-level `import clams` must complete in < 2 seconds.

        This test runs in a subprocess to measure cold-start import time,
        avoiding any module caching effects from the test process itself.

        The 2-second threshold ensures no heavy dependencies (torch,
        sentence_transformers) are imported at module level.

        Expected time: ~0.1-0.3 seconds for lightweight top-level import.
        Failure indicates: Heavy dependency imported at module level.

        Reference: BUG-037 (import timeouts), BUG-042 (fork after PyTorch init)
        """
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-c", "import clams"],
            capture_output=True,
            timeout=10,
        )
        elapsed = time.perf_counter() - start

        # Verify import succeeded
        assert result.returncode == 0, (
            f"Import failed with returncode {result.returncode}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        # Verify import time is under threshold
        assert elapsed < IMPORT_TIME_THRESHOLD_SECONDS, (
            f"Import took {elapsed:.2f}s, expected < {IMPORT_TIME_THRESHOLD_SECONDS}s.\n"
            f"This likely means a heavy dependency (torch, sentence_transformers) "
            f"is being imported at module level.\n"
            f"Check for top-level imports in clams/__init__.py or its submodules.\n"
            f"See BUG-037 and BUG-042 for context."
        )

    def test_clams_embedding_import_time_under_threshold(self) -> None:
        """Import of `clams.embedding` must complete in < 2 seconds.

        The embedding module is designed with lazy imports - it should only
        load base classes and the registry, not the actual embedding models
        (MiniLM, Nomic) which require PyTorch.

        Expected time: ~0.3-0.5 seconds for base classes and registry.
        Failure indicates: Model classes imported at embedding module level.

        Reference: clams/embedding/__init__.py design notes
        """
        start = time.perf_counter()
        result = subprocess.run(
            [sys.executable, "-c", "import clams.embedding"],
            capture_output=True,
            timeout=10,
        )
        elapsed = time.perf_counter() - start

        # Verify import succeeded
        assert result.returncode == 0, (
            f"Import failed with returncode {result.returncode}.\n"
            f"stdout: {result.stdout.decode()}\n"
            f"stderr: {result.stderr.decode()}"
        )

        # Verify import time is under threshold
        assert elapsed < IMPORT_TIME_THRESHOLD_SECONDS, (
            f"Import took {elapsed:.2f}s, expected < {IMPORT_TIME_THRESHOLD_SECONDS}s.\n"
            f"This likely means the embedding module is importing model classes "
            f"(MiniLMEmbedding, NomicEmbedding) at module level instead of lazily.\n"
            f"Check clams/embedding/__init__.py - model classes should only be "
            f"imported inside functions/methods, not at top level.\n"
            f"See BUG-037 and BUG-042 for context."
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
