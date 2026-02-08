"""Regression tests for BUG-075: editable install worktree import isolation.

These tests verify that ``import calm`` resolves to the current project's
``src/`` directory rather than to a path injected by a PEP 660 ``.pth`` file.
The conftest.py sys.path fix (BUG-075) ensures this by prepending the
project's own ``src/`` before any other imports happen.
"""

import sys
from pathlib import Path


def test_calm_imports_from_project_src() -> None:
    """Verify calm is imported from this project's src/, not another location."""
    import calm

    project_root = Path(__file__).resolve().parent.parent
    expected_src = project_root / "src"
    calm_path = Path(calm.__file__).resolve()
    assert str(calm_path).startswith(str(expected_src)), (
        f"calm imported from {calm_path}, expected under {expected_src}"
    )


def test_project_src_on_sys_path() -> None:
    """Verify project src/ is on sys.path for proper import resolution."""
    project_root = Path(__file__).resolve().parent.parent
    expected_src = str(project_root / "src")
    assert expected_src in sys.path, f"{expected_src} not found in sys.path"
