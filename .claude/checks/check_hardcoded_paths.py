#!/usr/bin/env python3
"""CI check for hardcoded paths in Python files.

This script uses Python AST to scan for hardcoded paths that would cause
environment-specific failures, such as:
- macOS home directories: /Users/someone/...
- Linux home directories: /home/username/...
- Windows user directories: C:\\Users\\...
- Hardcoded /tmp/ paths (when tempfile utilities aren't used)

Exit codes:
- 0: No violations found
- 1: Violations found
- 2: Script error
"""

from __future__ import annotations

import ast
import dataclasses
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Pre-compiled patterns for path detection
# NOTE: Order matters! Windows pattern must come first because paths like
# "C:/Users/name" would also match the macOS pattern "/Users/[^/]+/"
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[Cc]:[/\\][Uu]sers[/\\]"), "Windows user directory"),
    (re.compile(r"/Users/[^/]+/"), "macOS home directory"),
    (re.compile(r"/home/[a-z_][a-z0-9_-]*/"), "Linux home directory"),
]

# Patterns for f-string parts (more lenient since the username might be interpolated)
# These are checked when we know we're inside an f-string
FSTRING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[Cc]:[/\\][Uu]sers[/\\]?$"), "Windows user directory"),
    (re.compile(r"/Users/$"), "macOS home directory"),
    (re.compile(r"/home/$"), "Linux home directory"),
]

# Directories to exclude from scanning
EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        ".eggs",
        ".worktrees",  # Don't scan worktrees (may contain stale copies)
    }
)


@dataclasses.dataclass
class Violation:
    """A single hardcoded path violation."""

    filepath: str
    lineno: int
    description: str
    string_value: str

    def __str__(self) -> str:
        """Format violation for display."""
        # Truncate long strings
        display_value = self.string_value
        if len(display_value) > 80:
            display_value = display_value[:77] + "..."
        return (
            f"{self.filepath}:{self.lineno}: {self.description}\n"
            f'  String: "{display_value}"'
        )


def check_string(
    value: str, has_tempfile: bool, *, is_fstring_part: bool = False
) -> str | None:
    """Check a string for hardcoded path violations.

    Args:
        value: The string literal to check
        has_tempfile: Whether the file imports tempfile or uses tmp_path
        is_fstring_part: Whether this string is part of an f-string

    Returns:
        Violation description, or None if clean
    """
    # Check regular patterns first
    for pattern, description in PATTERNS:
        if pattern.search(value):
            return description

    # For f-string parts, also check partial patterns
    # (e.g., "/Users/" without username, since username might be interpolated)
    if is_fstring_part:
        for pattern, description in FSTRING_PATTERNS:
            if pattern.search(value):
                return description

    if "/tmp/" in value and not has_tempfile:
        return "hardcoded /tmp/ path (use tempfile or tmp_path fixture)"

    return None


def has_tempfile_usage(tree: ast.AST) -> bool:
    """Check if file imports tempfile or uses tmp_path fixture."""
    for node in ast.walk(tree):
        # import tempfile
        if isinstance(node, ast.Import):
            if any(alias.name == "tempfile" for alias in node.names):
                return True
        # from tempfile import ...
        elif isinstance(node, ast.ImportFrom):
            if node.module == "tempfile":
                return True
        # def test_foo(tmp_path): ...
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(arg.arg == "tmp_path" for arg in node.args.args):
                return True
    return False


class PathVisitor(ast.NodeVisitor):
    """AST visitor that collects hardcoded path violations."""

    def __init__(
        self,
        filepath: str,
        has_tempfile: bool,
        allowlist: set[tuple[str, int | None]],
    ) -> None:
        """Initialize the visitor.

        Args:
            filepath: Path to the file being scanned
            has_tempfile: Whether the file uses tempfile utilities
            allowlist: Set of (filepath, line_number_or_None) tuples to skip
        """
        self.filepath = filepath
        self.has_tempfile = has_tempfile
        self.allowlist = allowlist
        self.violations: list[Violation] = []
        self._docstring_lines: set[int] = set()

    def _mark_docstring(
        self, node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """Mark the line of a docstring so it can be skipped."""
        if node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                if isinstance(first.value.value, str):
                    # Mark all lines of multi-line docstrings
                    if hasattr(first.value, "end_lineno") and first.value.end_lineno:
                        start = first.value.lineno
                        end = first.value.end_lineno + 1
                        for lineno in range(start, end):
                            self._docstring_lines.add(lineno)
                    else:
                        self._docstring_lines.add(first.value.lineno)

    def _is_allowed(self, lineno: int) -> bool:
        """Check if a violation at this location is allowlisted."""
        # Normalize path for comparison
        normalized = self.filepath.replace("\\", "/")

        # Check exact line match
        if (normalized, lineno) in self.allowlist:
            return True

        # Check file-level allowlist
        if (normalized, None) in self.allowlist:
            return True

        # Check if path ends with allowlist entry (for relative paths)
        for entry_path, entry_line in self.allowlist:
            if entry_line is None and normalized.endswith(entry_path):
                return True
            if entry_line == lineno and normalized.endswith(entry_path):
                return True

        return False

    def _check_string(
        self, value: str, lineno: int, *, is_fstring_part: bool = False
    ) -> None:
        """Check a string value for violations."""
        # Skip docstrings
        if lineno in self._docstring_lines:
            return

        # Skip allowlisted
        if self._is_allowed(lineno):
            return

        violation_desc = check_string(
            value, self.has_tempfile, is_fstring_part=is_fstring_part
        )
        if violation_desc:
            self.violations.append(
                Violation(
                    filepath=self.filepath,
                    lineno=lineno,
                    description=violation_desc,
                    string_value=value,
                )
            )

    def visit_Module(self, node: ast.Module) -> None:
        """Visit module and mark its docstring."""
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class and mark its docstring."""
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function and mark its docstring."""
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function and mark its docstring."""
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """Visit constant nodes (includes string literals)."""
        if isinstance(node.value, str):
            self._check_string(node.value, node.lineno)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Visit f-strings and check their string parts.

        F-strings are split into parts where interpolated values are separate.
        We use relaxed patterns here because the username/path portion might
        be an interpolated variable (e.g., f"/Users/{name}/file").
        """
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                self._check_string(part.value, node.lineno, is_fstring_part=True)
        self.generic_visit(node)


def load_allowlist(path: Path) -> set[tuple[str, int | None]]:
    """Load allowlist entries from file.

    Args:
        path: Path to the allowlist file

    Returns:
        Set of (filepath, line_number_or_None) tuples
    """
    if not path.exists():
        return set()

    entries: set[tuple[str, int | None]] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            filepath, lineno_str = line.rsplit(":", 1)
            try:
                entries.add((filepath, int(lineno_str)))
            except ValueError:
                # Malformed line number, treat as whole-file
                entries.add((line, None))
        else:
            entries.add((line, None))

    return entries


def should_skip_dir(dirname: str) -> bool:
    """Check if directory should be skipped."""
    return dirname in EXCLUDED_DIRS or dirname.endswith(".egg-info")


def scan_file(
    filepath: Path,
    allowlist: set[tuple[str, int | None]],
) -> list[Violation]:
    """Scan a single Python file for hardcoded paths.

    Args:
        filepath: Path to the Python file
        allowlist: Set of allowlisted (filepath, lineno) tuples

    Returns:
        List of violations found
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"WARNING: Skipping {filepath} (encoding error: {e})", file=sys.stderr)
        return []

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError as e:
        print(f"WARNING: Skipping {filepath} (syntax error: {e})", file=sys.stderr)
        return []

    has_tempfile = has_tempfile_usage(tree)
    visitor = PathVisitor(str(filepath), has_tempfile, allowlist)
    visitor.visit(tree)

    return visitor.violations


def scan_directory(
    root: Path,
    allowlist: set[tuple[str, int | None]],
) -> list[Violation]:
    """Scan directory recursively for hardcoded paths.

    Args:
        root: Root directory to scan
        allowlist: Set of allowlisted (filepath, lineno) tuples

    Returns:
        List of all violations found
    """
    violations: list[Violation] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Remove excluded directories in-place to prevent descending
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            filepath = Path(dirpath) / filename
            file_violations = scan_file(filepath, allowlist)
            violations.extend(file_violations)

    return violations


def format_output(violations: list[Violation]) -> str:
    """Format violations for display.

    Args:
        violations: List of violations to format

    Returns:
        Formatted output string
    """
    if not violations:
        return "=== Checking for hardcoded paths ===\n\nNo hardcoded paths found."

    # Group by file
    by_file: dict[str, list[Violation]] = {}
    for v in violations:
        by_file.setdefault(v.filepath, []).append(v)

    lines = ["=== Checking for hardcoded paths ===\n"]

    for filepath, file_violations in sorted(by_file.items()):
        for v in sorted(file_violations, key=lambda x: x.lineno):
            lines.append(str(v))
            lines.append("")

    file_count = len(by_file)
    lines.append("=== Summary ===")
    lines.append(f"Found {len(violations)} hardcoded path(s) in {file_count} file(s)")

    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0=clean, 1=violations, 2=error)
    """
    if argv is None:
        argv = sys.argv[1:]

    # Parse arguments
    if len(argv) > 1:
        print("Usage: check_hardcoded_paths.py [directory]", file=sys.stderr)
        return 2

    if argv:
        root = Path(argv[0])
    else:
        root = Path.cwd()

    if not root.exists():
        print(f"ERROR: Directory does not exist: {root}", file=sys.stderr)
        return 2

    if not root.is_dir():
        print(f"ERROR: Not a directory: {root}", file=sys.stderr)
        return 2

    # Load allowlist from script's directory
    script_dir = Path(__file__).parent
    allowlist_path = script_dir / "path_allowlist.txt"
    allowlist = load_allowlist(allowlist_path)

    # Scan
    try:
        violations = scan_directory(root, allowlist)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        return 2

    # Output
    print(format_output(violations))

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
