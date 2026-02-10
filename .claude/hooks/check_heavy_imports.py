#!/usr/bin/env python3
"""Pre-commit hook to detect top-level imports of heavy packages.

This hook uses AST analysis to find top-level imports of packages that
initialize heavy backends (PyTorch, CUDA, MPS) at import time. These
imports can cause:
- 4-6 second startup delays (BUG-037)
- Fork failures when daemonizing (BUG-042)

Heavy packages are allowed:
- Inside functions/methods (lazy imports)
- In test files
- In dedicated embedding modules that are themselves lazily imported

Usage:
    python check_heavy_imports.py file1.py file2.py ...

Exit codes:
    0 - No issues found
    1 - Issues found (prints to stderr)
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple


class HeavyImportIssue(NamedTuple):
    """Represents a forbidden top-level heavy import."""

    filename: str
    lineno: int
    col_offset: int
    module_name: str


# Heavy packages that should not be imported at module top level
# These packages initialize GPU backends or load large models at import time
HEAVY_PACKAGES = frozenset({
    "torch",
    "sentence_transformers",
    "transformers",
    "nomic",
})

# Modules that are allowed to have top-level heavy imports because
# they are themselves lazily imported (only loaded when needed).
# These are the "leaf" modules that actually use the heavy dependencies.
ALLOWED_MODULES = frozenset({
    # Embedding implementations - lazily imported by registry.py
    "src/calm/embedding/minilm.py",
    "src/calm/embedding/nomic.py",
    "calm/embedding/minilm.py",
    "calm/embedding/nomic.py",
})


class HeavyImportChecker(ast.NodeVisitor):
    """AST visitor that checks for top-level heavy imports.

    Only flags imports at module level (not inside functions, methods, or classes).
    Allows imports inside TYPE_CHECKING blocks (for type hints only).
    """

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.issues: list[HeavyImportIssue] = []
        self._in_function = False
        self._in_type_checking = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track when we're inside a function."""
        old_in_function = self._in_function
        self._in_function = True
        self.generic_visit(node)
        self._in_function = old_in_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track when we're inside an async function."""
        old_in_function = self._in_function
        self._in_function = True
        self.generic_visit(node)
        self._in_function = old_in_function

    def visit_If(self, node: ast.If) -> None:
        """Track when we're inside an 'if TYPE_CHECKING:' block.

        TYPE_CHECKING imports only execute during static analysis (mypy/pyright),
        never at runtime, so they're safe for type hints without fork issues.
        """
        is_type_checking = (
            isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
        )

        if is_type_checking:
            old_in_type_checking = self._in_type_checking
            self._in_type_checking = True
            # Only visit the body (true branch), not the orelse (else branch)
            for child in node.body:
                self.visit(child)
            self._in_type_checking = old_in_type_checking
            # Visit the else branch normally (not inside TYPE_CHECKING)
            for child in node.orelse:
                self.visit(child)
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check 'import X' statements."""
        if self._in_function or self._in_type_checking:
            return  # Lazy imports inside functions or TYPE_CHECKING are OK

        for alias in node.names:
            # Get the top-level package name (e.g., 'torch' from 'torch.nn')
            top_package = alias.name.split(".")[0]
            if top_package in HEAVY_PACKAGES:
                self.issues.append(
                    HeavyImportIssue(
                        filename=self.filename,
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        module_name=alias.name,
                    )
                )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check 'from X import Y' statements."""
        if self._in_function or self._in_type_checking:
            return  # Lazy imports inside functions or TYPE_CHECKING are OK

        if node.module is None:
            return  # Relative imports without module name

        # Get the top-level package name
        top_package = node.module.split(".")[0]
        if top_package in HEAVY_PACKAGES:
            self.issues.append(
                HeavyImportIssue(
                    filename=self.filename,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    module_name=node.module,
                )
            )


def is_test_file(filepath: Path) -> bool:
    """Check if a file is a test file.

    Test files are allowed to have eager imports since they don't
    run in production and don't need to worry about fork() issues.

    Args:
        filepath: Path to check

    Returns:
        True if this is a test file
    """
    path_str = str(filepath)

    # Check for test directory
    if "/tests/" in path_str or "\\tests\\" in path_str:
        return True

    # Check for test file naming conventions
    filename = filepath.name
    if filename.startswith("test_") or filename.endswith("_test.py"):
        return True

    # Check for conftest.py
    if filename == "conftest.py":
        return True

    return False


def is_allowed_module(filepath: Path) -> bool:
    """Check if a module is allowed to have top-level heavy imports.

    These are modules that are themselves lazily imported, so their
    top-level imports don't execute until the module is needed.

    Args:
        filepath: Path to check

    Returns:
        True if this module is allowed heavy imports
    """
    path_str = str(filepath)

    # Normalize path separators
    path_str = path_str.replace("\\", "/")

    # Check if path ends with any allowed module pattern
    for allowed in ALLOWED_MODULES:
        if path_str.endswith(allowed):
            return True

    return False


def check_file(filepath: Path) -> list[HeavyImportIssue]:
    """Check a single Python file for forbidden heavy imports.

    Args:
        filepath: Path to the Python file to check

    Returns:
        List of heavy import issues found (empty if file is allowed)
    """
    # Skip test files
    if is_test_file(filepath):
        return []

    # Skip allowed modules (leaf modules that are lazily imported)
    if is_allowed_module(filepath):
        return []

    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        # Skip files with syntax errors (they'll fail elsewhere)
        return []
    except Exception:
        # Skip files we can't read
        return []

    checker = HeavyImportChecker(str(filepath))
    checker.visit(tree)
    return checker.issues


def format_error_message(issues: list[HeavyImportIssue]) -> str:
    """Format a helpful error message for the user.

    Args:
        issues: List of heavy import issues found

    Returns:
        Formatted error message with fix instructions
    """
    lines = [
        "ERROR: Top-level imports of heavy packages detected!",
        "",
        "These packages initialize GPU backends at import time, which causes:",
        "  - 4-6 second startup delays",
        "  - Fork failures when daemonizing (os.fork() after PyTorch init fails)",
        "",
        "Violations found:",
    ]

    for issue in issues:
        lines.append(
            f"  {issue.filename}:{issue.lineno}:{issue.col_offset}: "
            f"import {issue.module_name}"
        )

    lines.extend([
        "",
        "To fix, move imports inside functions (lazy import pattern):",
        "",
        "  # WRONG - top-level import",
        "  import torch",
        "",
        "  def get_embeddings():",
        "      return torch.tensor(...)",
        "",
        "  # CORRECT - lazy import inside function",
        "  def get_embeddings():",
        "      import torch  # Only loaded when function is called",
        "      return torch.tensor(...)",
        "",
        "See BUG-042, BUG-037 for context.",
        "See src/calm/embedding/registry.py for the correct pattern.",
    ])

    return "\n".join(lines)


def main() -> int:
    """Main entry point.

    Returns:
        0 if no issues found, 1 if issues found
    """
    if len(sys.argv) < 2:
        print(
            "Usage: check_heavy_imports.py file1.py [file2.py ...]",
            file=sys.stderr,
        )
        return 1

    all_issues: list[HeavyImportIssue] = []

    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)
        if not filepath.exists():
            continue
        if filepath.suffix != ".py":
            continue

        issues = check_file(filepath)
        all_issues.extend(issues)

    if all_issues:
        print(format_error_message(all_issues), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
