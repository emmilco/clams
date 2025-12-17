"""Tests for the check_heavy_imports pre-commit hook.

This module tests the AST-based detection of top-level heavy package imports.
See BUG-037 (startup delays) and BUG-042 (fork failures) for context.
"""

import sys
import tempfile
from pathlib import Path

# Add the hooks directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))

from check_heavy_imports import (
    ALLOWED_MODULES,
    HEAVY_PACKAGES,
    check_file,
    is_allowed_module,
    is_test_file,
)


class TestHeavyPackagesList:
    """Tests that the heavy packages list is correct."""

    def test_torch_is_heavy(self) -> None:
        """torch initializes CUDA/MPS backends at import time."""
        assert "torch" in HEAVY_PACKAGES

    def test_sentence_transformers_is_heavy(self) -> None:
        """sentence_transformers imports torch."""
        assert "sentence_transformers" in HEAVY_PACKAGES

    def test_transformers_is_heavy(self) -> None:
        """transformers imports torch."""
        assert "transformers" in HEAVY_PACKAGES

    def test_nomic_is_heavy(self) -> None:
        """nomic imports sentence_transformers."""
        assert "nomic" in HEAVY_PACKAGES


class TestAllowedModules:
    """Tests that the allowed modules list is correct."""

    def test_minilm_is_allowed(self) -> None:
        """minilm.py is lazily imported by registry.py."""
        assert any("minilm.py" in m for m in ALLOWED_MODULES)

    def test_nomic_is_allowed(self) -> None:
        """nomic.py is lazily imported by registry.py."""
        assert any("nomic.py" in m for m in ALLOWED_MODULES)


class TestIsTestFile:
    """Tests for the is_test_file function."""

    def test_test_directory_detected(self) -> None:
        """Files in tests/ directory are detected as test files."""
        assert is_test_file(Path("/project/tests/test_foo.py"))
        assert is_test_file(Path("/project/tests/unit/test_bar.py"))

    def test_test_prefix_detected(self) -> None:
        """Files starting with test_ are detected as test files."""
        assert is_test_file(Path("/project/test_something.py"))

    def test_test_suffix_detected(self) -> None:
        """Files ending with _test.py are detected as test files."""
        assert is_test_file(Path("/project/something_test.py"))

    def test_conftest_detected(self) -> None:
        """conftest.py files are detected as test files."""
        assert is_test_file(Path("/project/conftest.py"))
        assert is_test_file(Path("/project/tests/conftest.py"))

    def test_regular_file_not_test(self) -> None:
        """Regular source files are not detected as test files."""
        assert not is_test_file(Path("/project/src/module.py"))
        assert not is_test_file(Path("/project/src/clams/server.py"))


class TestIsAllowedModule:
    """Tests for the is_allowed_module function."""

    def test_minilm_is_allowed(self) -> None:
        """src/clams/embedding/minilm.py is allowed."""
        assert is_allowed_module(Path("src/clams/embedding/minilm.py"))
        assert is_allowed_module(
            Path("/project/src/clams/embedding/minilm.py")
        )

    def test_nomic_is_allowed(self) -> None:
        """src/clams/embedding/nomic.py is allowed."""
        assert is_allowed_module(Path("src/clams/embedding/nomic.py"))
        assert is_allowed_module(
            Path("/project/src/clams/embedding/nomic.py")
        )

    def test_registry_not_allowed(self) -> None:
        """registry.py is NOT allowed (it must use lazy imports)."""
        assert not is_allowed_module(Path("src/clams/embedding/registry.py"))

    def test_arbitrary_file_not_allowed(self) -> None:
        """Arbitrary files are not allowed."""
        assert not is_allowed_module(Path("src/clams/server/main.py"))


class TestHeavyImportChecker:
    """Tests for the AST-based import checker."""

    def test_detects_import_torch(self) -> None:
        """Detects 'import torch' at top level."""
        source = "import torch\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "torch"

    def test_detects_from_torch_import(self) -> None:
        """Detects 'from torch import ...' at top level."""
        source = "from torch import nn\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "torch"

    def test_detects_from_torch_submodule(self) -> None:
        """Detects 'from torch.nn import ...' at top level."""
        source = "from torch.nn import Module\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "torch.nn"

    def test_detects_sentence_transformers(self) -> None:
        """Detects sentence_transformers imports."""
        source = "from sentence_transformers import SentenceTransformer\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "sentence_transformers"

    def test_detects_transformers(self) -> None:
        """Detects transformers imports."""
        source = "import transformers\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "transformers"

    def test_detects_nomic(self) -> None:
        """Detects nomic imports."""
        source = "import nomic\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "nomic"

    def test_allows_lazy_import_in_function(self) -> None:
        """Allows imports inside functions (lazy imports)."""
        source = """
def get_model():
    import torch
    return torch.zeros(10)
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_allows_lazy_import_in_async_function(self) -> None:
        """Allows imports inside async functions (lazy imports)."""
        source = """
async def get_model():
    import torch
    return torch.zeros(10)
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_allows_lazy_import_in_method(self) -> None:
        """Allows imports inside class methods (lazy imports)."""
        source = """
class MyClass:
    def get_model(self):
        import torch
        return torch.zeros(10)
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_allows_other_imports(self) -> None:
        """Allows non-heavy imports at top level."""
        source = """
import os
import sys
from pathlib import Path
import numpy as np
import structlog
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_allows_type_checking_import(self) -> None:
        """Allows imports inside 'if TYPE_CHECKING:' blocks."""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
    from sentence_transformers import SentenceTransformer

def process(tensor: "torch.Tensor") -> None:
    import torch
    return torch.zeros(10)
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_allows_type_checking_from_import(self) -> None:
        """Allows 'from X import Y' inside TYPE_CHECKING blocks."""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from torch import Tensor
    from torch.nn import Module

def get_tensor() -> "Tensor":
    from torch import Tensor
    return Tensor([1, 2, 3])
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_detects_import_outside_type_checking_else(self) -> None:
        """Detects heavy imports in else branch of TYPE_CHECKING."""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch
else:
    import transformers  # Should be flagged - runs at runtime!
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "transformers"

    def test_detects_import_after_type_checking_block(self) -> None:
        """Detects heavy imports after TYPE_CHECKING block ends."""
        source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch  # OK

import sentence_transformers  # Should be flagged - at module level
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 1
        assert issues[0].module_name == "sentence_transformers"

    def test_detects_multiple_violations(self) -> None:
        """Detects all top-level heavy imports."""
        source = """
import torch
from sentence_transformers import SentenceTransformer
import transformers

def lazy():
    import nomic  # This is OK
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 3
        module_names = {i.module_name for i in issues}
        assert "torch" in module_names
        assert "sentence_transformers" in module_names
        assert "transformers" in module_names


class TestCheckFileIntegration:
    """Integration tests for check_file function."""

    def test_skips_test_files(self) -> None:
        """Test files are skipped entirely."""
        source = "import torch\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix="test_", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0

    def test_skips_syntax_errors(self) -> None:
        """Files with syntax errors are skipped."""
        source = "import torch\ndef broken(\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(source)
            f.flush()
            issues = check_file(Path(f.name))

        assert len(issues) == 0


class TestActualSourceFiles:
    """Tests that actual source files pass the check."""

    def test_embedding_registry_passes(self) -> None:
        """registry.py uses lazy imports correctly."""
        registry_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "clams"
            / "embedding"
            / "registry.py"
        )
        if registry_path.exists():
            issues = check_file(registry_path)
            assert len(issues) == 0, f"registry.py has violations: {issues}"

    def test_embedding_init_passes(self) -> None:
        """embedding/__init__.py uses lazy imports correctly."""
        init_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "clams"
            / "embedding"
            / "__init__.py"
        )
        if init_path.exists():
            issues = check_file(init_path)
            assert len(issues) == 0, f"__init__.py has violations: {issues}"

    def test_minilm_is_allowed(self) -> None:
        """minilm.py is allowed to have top-level imports."""
        minilm_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "clams"
            / "embedding"
            / "minilm.py"
        )
        if minilm_path.exists():
            issues = check_file(minilm_path)
            assert len(issues) == 0, f"minilm.py incorrectly flagged: {issues}"

    def test_nomic_is_allowed(self) -> None:
        """nomic.py is allowed to have top-level imports."""
        nomic_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "clams"
            / "embedding"
            / "nomic.py"
        )
        if nomic_path.exists():
            issues = check_file(nomic_path)
            assert len(issues) == 0, f"nomic.py incorrectly flagged: {issues}"
