#!/usr/bin/env python3
"""Pre-commit hook to warn when __hash__/__eq__ methods lack contract tests.

This hook uses AST analysis to find class definitions that define __hash__
or __eq__ methods, then checks if those classes have tests in the canonical
test file: tests/context/test_data_contracts.py

The hook is ADVISORY ONLY - it always exits 0 to allow commits during
development before tests are written.

Reference: BUG-028 - ContextItem hash/eq contract violation

Usage:
    # Check staged files (pre-commit mode)
    python check_hash_eq.py

    # Check specific files (manual mode)
    python check_hash_eq.py file1.py file2.py ...

Exit codes:
    0 - Always (advisory mode)
"""

import ast
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


class HashEqInfo(NamedTuple):
    """Information about a class with __hash__ or __eq__."""

    class_name: str
    has_hash: bool
    has_eq: bool
    has_hash_none: bool
    line_number: int
    filepath: str


class Warning(NamedTuple):
    """A warning to display to the user."""

    filepath: str
    class_name: str
    line_number: int
    methods: str  # "__hash__", "__eq__", or "__hash__ and __eq__"


# Canonical location for hash/eq contract tests (from SPEC-047)
TEST_FILE_PATH = Path("tests/context/test_data_contracts.py")


class HashEqVisitor(ast.NodeVisitor):
    """Visit class definitions to find __hash__ and __eq__ methods."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self.results: list[HashEqInfo] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check class for __hash__ and __eq__ definitions."""
        has_hash = False
        has_eq = False
        has_hash_none = False

        for item in node.body:
            # Method definitions: def __hash__(self) or def __eq__(self, other)
            if isinstance(item, ast.FunctionDef):
                if item.name == "__hash__":
                    has_hash = True
                elif item.name == "__eq__":
                    has_eq = True

            # Assignment: __hash__ = None (explicit unhashable)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__hash__":
                        if (
                            isinstance(item.value, ast.Constant)
                            and item.value.value is None
                        ):
                            has_hash_none = True

        if has_hash or has_eq:
            self.results.append(
                HashEqInfo(
                    class_name=node.name,
                    has_hash=has_hash,
                    has_eq=has_eq,
                    has_hash_none=has_hash_none,
                    line_number=node.lineno,
                    filepath=self.filepath,
                )
            )

        # Recurse into nested classes
        self.generic_visit(node)


def is_test_file(filepath: Path) -> bool:
    """Check if a file is a test file.

    Test files are not checked since they don't need contract tests.

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


def find_hash_eq_classes(filepath: Path) -> list[HashEqInfo]:
    """Parse a file for __hash__/__eq__ definitions.

    Args:
        filepath: Path to the Python file to parse

    Returns:
        List of HashEqInfo for classes with __hash__ or __eq__
    """
    if not filepath.exists():
        return []  # File deleted after staging

    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        print(f"Notice: Could not parse {filepath}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Notice: Error reading {filepath}: {e}", file=sys.stderr)
        return []

    visitor = HashEqVisitor(str(filepath))
    visitor.visit(tree)
    return visitor.results


def class_has_test(class_name: str, test_file_path: Path) -> bool:
    """Check if class appears in the test file using word boundary matching.

    Args:
        class_name: Name of the class to search for
        test_file_path: Path to the test file

    Returns:
        True if class name appears in test file as a whole word
    """
    if not test_file_path.exists():
        return False

    try:
        content = test_file_path.read_text()
    except Exception:
        return False

    # Word boundary regex: class name as complete word
    # Matches: "ContextItem" in "ContextItem(" or "ContextItem,"
    # Does not match: "ContextItemExtra" or "MyContextItem"
    pattern = rf"\b{re.escape(class_name)}\b"
    return bool(re.search(pattern, content))


def get_staged_files() -> list[str]:
    """Get list of staged Python files.

    Returns:
        List of file paths that are staged for commit
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            check=True,
        )
        files = result.stdout.strip().split("\n")
        return [f for f in files if f.endswith(".py") and f]
    except subprocess.CalledProcessError as e:
        print(f"Notice: Git command failed: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Notice: Error getting staged files: {e}", file=sys.stderr)
        return []


def format_methods(info: HashEqInfo) -> str:
    """Format which methods are defined for a class.

    Args:
        info: HashEqInfo for the class

    Returns:
        String like "__hash__", "__eq__", or "__hash__ and __eq__"
    """
    if info.has_hash and info.has_eq:
        return "__hash__ and __eq__"
    elif info.has_hash:
        return "__hash__"
    else:
        return "__eq__"


def format_warning(warning: Warning) -> str:
    """Format a single warning message.

    Args:
        warning: Warning to format

    Returns:
        Formatted warning string
    """
    location = f"{warning.filepath} (line {warning.line_number})"
    return f"""
NOTICE: Class '{warning.class_name}' in {location} defines {warning.methods}.

No contract test found in tests/context/test_data_contracts.py.

Add a test to verify the hash/eq contract:

    class Test{warning.class_name}Contract:
        def test_equal_items_have_equal_hashes(self) -> None:
            obj1 = {warning.class_name}(...)
            obj2 = {warning.class_name}(...)
            if obj1 == obj2:
                assert hash(obj1) == hash(obj2), "Hash/eq contract violation"

See BUG-028 for context on why this matters.
"""


def check_files(filepaths: list[Path], test_file: Path) -> list[Warning]:
    """Check multiple files for untested __hash__/__eq__ classes.

    Args:
        filepaths: List of Python files to check
        test_file: Path to the contract test file

    Returns:
        List of warnings for classes without tests
    """
    warnings: list[Warning] = []

    for filepath in filepaths:
        # Skip test files
        if is_test_file(filepath):
            continue

        # Skip non-Python files
        if filepath.suffix != ".py":
            continue

        # Find classes with __hash__ or __eq__
        classes = find_hash_eq_classes(filepath)

        for info in classes:
            # Skip if __hash__ = None (intentionally unhashable)
            if info.has_hash_none and not info.has_hash:
                continue

            # Check if class has a test
            if not class_has_test(info.class_name, test_file):
                warnings.append(
                    Warning(
                        filepath=info.filepath,
                        class_name=info.class_name,
                        line_number=info.line_number,
                        methods=format_methods(info),
                    )
                )

    return warnings


def main() -> int:
    """Main entry point.

    Returns:
        0 always (advisory mode)
    """
    # Determine which files to check
    if len(sys.argv) > 1:
        # Manual mode: check specified files
        filepaths = [Path(arg) for arg in sys.argv[1:]]
    else:
        # Pre-commit mode: check staged files
        staged = get_staged_files()
        if not staged:
            return 0
        filepaths = [Path(f) for f in staged]

    # Find the test file (relative to current directory or repo root)
    test_file = TEST_FILE_PATH
    if not test_file.exists():
        # Try finding from repo root
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())
            test_file = repo_root / TEST_FILE_PATH
        except Exception:
            pass  # Use relative path

    # Check files and collect warnings
    warnings = check_files(filepaths, test_file)

    # Display warnings
    for warning in warnings:
        print(format_warning(warning), file=sys.stderr)

    # Always exit 0 (advisory mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
