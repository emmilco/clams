#!/usr/bin/env python3
"""Pre-commit hook to check subprocess calls for stdin handling.

This hook uses AST analysis to find subprocess.run, subprocess.Popen, and
related calls that don't specify stdin handling. Missing stdin handling
can cause tests to hang waiting for input.

Usage:
    python check_subprocess.py file1.py file2.py ...

Exit codes:
    0 - No issues found
    1 - Issues found (prints to stderr)
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple


class SubprocessIssue(NamedTuple):
    """Represents a subprocess call without stdin handling."""

    filename: str
    lineno: int
    col_offset: int
    func_name: str


class SubprocessChecker(ast.NodeVisitor):
    """AST visitor that checks for subprocess calls without stdin handling."""

    # Functions that need stdin handling
    SUBPROCESS_FUNCS = frozenset({
        "run",
        "Popen",
        "call",
        "check_call",
        "check_output",
    })

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.issues: list[SubprocessIssue] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Check each function call for subprocess patterns."""
        func_name = self._get_subprocess_func_name(node)
        if func_name and not self._has_stdin_handling(node):
            self.issues.append(
                SubprocessIssue(
                    filename=self.filename,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    func_name=func_name,
                )
            )
        self.generic_visit(node)

    def _get_subprocess_func_name(self, node: ast.Call) -> str | None:
        """Return the subprocess function name if this is a subprocess call.

        Handles patterns like:
        - subprocess.run(...)
        - subprocess.Popen(...)
        """
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self.SUBPROCESS_FUNCS:
                # Check if it's subprocess.X or could be subprocess
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == "subprocess":
                        return f"subprocess.{node.func.attr}"
        return None

    def _has_stdin_handling(self, node: ast.Call) -> bool:
        """Check if the call has stdin handling via keyword argument.

        Valid stdin handling:
        - stdin=subprocess.DEVNULL
        - stdin=subprocess.PIPE
        - stdin=<any variable>
        - input=<any value>
        """
        for kw in node.keywords:
            if kw.arg in ("stdin", "input"):
                return True
        return False


def check_file(filepath: Path) -> list[SubprocessIssue]:
    """Check a single Python file for subprocess issues.

    Args:
        filepath: Path to the Python file to check

    Returns:
        List of subprocess issues found
    """
    try:
        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        # Skip files with syntax errors (they'll fail elsewhere)
        return []
    except Exception:
        # Skip files we can't read
        return []

    checker = SubprocessChecker(str(filepath))
    checker.visit(tree)
    return checker.issues


def main() -> int:
    """Main entry point.

    Returns:
        0 if no issues found, 1 if issues found
    """
    if len(sys.argv) < 2:
        print("Usage: check_subprocess.py file1.py [file2.py ...]", file=sys.stderr)
        return 1

    all_issues: list[SubprocessIssue] = []

    for filepath_str in sys.argv[1:]:
        filepath = Path(filepath_str)
        if not filepath.exists():
            continue
        if filepath.suffix != ".py":
            continue

        issues = check_file(filepath)
        all_issues.extend(issues)

    if all_issues:
        print(
            "ERROR: subprocess calls must specify stdin handling "
            "(stdin=subprocess.DEVNULL, stdin=subprocess.PIPE, or input=):\n",
            file=sys.stderr,
        )
        for issue in all_issues:
            print(
                f"  {issue.filename}:{issue.lineno}:{issue.col_offset}: "
                f"{issue.func_name}() missing stdin= or input= argument",
                file=sys.stderr,
            )
        print(
            "\nFix by adding stdin=subprocess.DEVNULL to prevent hangs.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
