"""Tests for the hardcoded paths CI check.

This module tests the AST-based scanner that detects hardcoded paths
in Python source files.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Add the checks directory to the path so we can import the module
CHECKS_DIR = Path(__file__).parent.parent.parent / ".claude" / "checks"
sys.path.insert(0, str(CHECKS_DIR))

from check_hardcoded_paths import (  # noqa: E402
    PathVisitor,
    Violation,
    check_string,
    format_output,
    has_tempfile_usage,
    load_allowlist,
    main,
    scan_directory,
    scan_file,
    should_skip_dir,
)

if TYPE_CHECKING:
    pass


class TestCheckString:
    """Tests for check_string function."""

    def test_detects_macos_path(self) -> None:
        """Detect macOS home directory paths."""
        result = check_string("/Users/john/project/file.txt", has_tempfile=False)
        assert result == "macOS home directory"

    def test_detects_macos_path_with_username(self) -> None:
        """Detect macOS paths with various usernames."""
        result = check_string("/Users/alice123/Documents", has_tempfile=False)
        assert result == "macOS home directory"

    def test_detects_linux_path(self) -> None:
        """Detect Linux home directory paths."""
        result = check_string("/home/username/project", has_tempfile=False)
        assert result == "Linux home directory"

    def test_detects_linux_path_with_underscore(self) -> None:
        """Detect Linux paths with underscore in username."""
        result = check_string("/home/_admin/config", has_tempfile=False)
        assert result == "Linux home directory"

    def test_detects_linux_path_with_dash(self) -> None:
        """Detect Linux paths with dash in username."""
        result = check_string("/home/user-name/config", has_tempfile=False)
        assert result == "Linux home directory"

    def test_detects_windows_path_backslash(self) -> None:
        """Detect Windows paths with backslashes."""
        result = check_string("C:\\Users\\name\\file.txt", has_tempfile=False)
        assert result == "Windows user directory"

    def test_detects_windows_path_forward_slash(self) -> None:
        """Detect Windows paths with forward slashes."""
        result = check_string("C:/Users/name/file.txt", has_tempfile=False)
        assert result == "Windows user directory"

    def test_detects_windows_path_lowercase(self) -> None:
        """Detect Windows paths with lowercase drive letter."""
        result = check_string("c:\\users\\name\\file.txt", has_tempfile=False)
        assert result == "Windows user directory"

    def test_flags_tmp_without_tempfile(self) -> None:
        """Flag /tmp/ paths when tempfile is not imported."""
        result = check_string("/tmp/cache/data.json", has_tempfile=False)
        assert result is not None
        assert "hardcoded /tmp/" in result

    def test_allows_tmp_with_tempfile(self) -> None:
        """Allow /tmp/ paths when tempfile is imported."""
        result = check_string("/tmp/cache/data.json", has_tempfile=True)
        assert result is None

    def test_ignores_usr_bin_path(self) -> None:
        """Safe system paths should not be flagged."""
        assert check_string("/usr/bin/python", has_tempfile=False) is None

    def test_ignores_etc_path(self) -> None:
        """Configuration paths should not be flagged."""
        assert check_string("/etc/config", has_tempfile=False) is None

    def test_ignores_var_path(self) -> None:
        """Variable data paths should not be flagged."""
        assert check_string("/var/log/app.log", has_tempfile=False) is None

    def test_ignores_empty_string(self) -> None:
        """Empty strings should not be flagged."""
        assert check_string("", has_tempfile=False) is None

    def test_ignores_relative_path(self) -> None:
        """Relative paths should not be flagged."""
        assert check_string("./config/settings.json", has_tempfile=False) is None

    def test_ignores_partial_pattern(self) -> None:
        """Patterns that don't match completely should not be flagged."""
        # Missing trailing slash after username
        assert check_string("/Users", has_tempfile=False) is None
        assert check_string("/Users/", has_tempfile=False) is None


class TestHasTempfileUsage:
    """Tests for tempfile detection."""

    def test_detects_import_tempfile(self) -> None:
        """Detect 'import tempfile' statement."""
        code = "import tempfile\nf = tempfile.mktemp()"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_from_tempfile_import(self) -> None:
        """Detect 'from tempfile import ...' statement."""
        code = "from tempfile import NamedTemporaryFile"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_from_tempfile_import_multiple(self) -> None:
        """Detect 'from tempfile import multiple, items'."""
        code = "from tempfile import mkstemp, mkdtemp"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_tmp_path_fixture(self) -> None:
        """Detect pytest tmp_path fixture usage."""
        code = "def test_foo(tmp_path):\n    pass"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_tmp_path_in_async_function(self) -> None:
        """Detect tmp_path in async test functions."""
        code = "async def test_async(tmp_path):\n    pass"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_tmp_path_with_other_args(self) -> None:
        """Detect tmp_path when there are other arguments."""
        code = "def test_foo(fixture1, tmp_path, fixture2):\n    pass"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_no_tempfile_usage(self) -> None:
        """Return False when no tempfile utilities are used."""
        code = "x = '/tmp/foo'\nimport os"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is False

    def test_different_module_not_detected(self) -> None:
        """Other modules should not trigger tempfile detection."""
        code = "from os import path"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is False


class TestPathVisitor:
    """Tests for AST visitor."""

    def test_ignores_comments(self) -> None:
        """Comments are not in AST, so should find nothing."""
        code = "# /Users/example/path\nx = 1"
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_ignores_module_docstring(self) -> None:
        """Module docstrings should be ignored."""
        code = '''"""/Users/example is documented here."""
x = 1
'''
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_ignores_function_docstring(self) -> None:
        """Function docstrings should be ignored."""
        code = '''
def foo():
    """/Users/example is documented here."""
    pass
'''
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_ignores_class_docstring(self) -> None:
        """Class docstrings should be ignored."""
        code = '''
class Foo:
    """/Users/example is documented here."""
    pass
'''
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_ignores_multiline_docstring(self) -> None:
        """Multi-line docstrings should be ignored."""
        code = '''
def foo():
    """This is a docstring.

    Example path: /Users/example/file.txt
    More text here.
    """
    pass
'''
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_detects_string_literal(self) -> None:
        """String literals with paths should be detected."""
        code = 'path = "/Users/john/project"'
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 1
        assert visitor.violations[0].lineno == 1

    def test_detects_f_string(self) -> None:
        """F-strings with hardcoded path prefixes should be detected."""
        code = 'path = f"/Users/{name}/project"'
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 1

    def test_detects_multiple_violations(self) -> None:
        """Multiple violations in the same file should all be detected."""
        code = '''
path1 = "/Users/john/file1"
path2 = "/home/user/file2"
'''
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 2

    def test_allowlist_skips_file(self) -> None:
        """File-level allowlist should skip all violations."""
        code = 'path = "/Users/john/project"'
        tree = ast.parse(code)
        allowlist: set[tuple[str, int | None]] = {("test.py", None)}
        visitor = PathVisitor("test.py", False, allowlist)
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_allowlist_skips_specific_line(self) -> None:
        """Line-level allowlist should skip only that line."""
        code = '''path1 = "/Users/john/file1"
path2 = "/Users/john/file2"
'''
        tree = ast.parse(code)
        allowlist: set[tuple[str, int | None]] = {("test.py", 1)}
        visitor = PathVisitor("test.py", False, allowlist)
        visitor.visit(tree)
        # Line 1 is allowlisted, line 2 should still be flagged
        assert len(visitor.violations) == 1
        assert visitor.violations[0].lineno == 2

    def test_allowlist_suffix_match(self) -> None:
        """Allowlist should match path suffixes for flexibility."""
        code = 'path = "/Users/john/project"'
        tree = ast.parse(code)
        # Allowlist entry is a suffix of the actual path
        allowlist: set[tuple[str, int | None]] = {("src/test.py", None)}
        visitor = PathVisitor("/full/path/to/src/test.py", False, allowlist)
        visitor.visit(tree)
        assert len(visitor.violations) == 0


class TestAllowlist:
    """Tests for allowlist handling."""

    def test_load_missing_file(self, tmp_path: Path) -> None:
        """Missing allowlist file should return empty set."""
        result = load_allowlist(tmp_path / "missing.txt")
        assert result == set()

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Empty allowlist file should return empty set."""
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("")
        result = load_allowlist(allowlist)
        assert result == set()

    def test_load_with_comments(self, tmp_path: Path) -> None:
        """Comments should be ignored."""
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("# Comment\nfile.py\n# Another comment\n")
        result = load_allowlist(allowlist)
        assert result == {("file.py", None)}

    def test_load_with_blank_lines(self, tmp_path: Path) -> None:
        """Blank lines should be ignored."""
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("file1.py\n\n\nfile2.py\n")
        result = load_allowlist(allowlist)
        assert result == {("file1.py", None), ("file2.py", None)}

    def test_load_with_line_numbers(self, tmp_path: Path) -> None:
        """Line numbers should be parsed correctly."""
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("file.py:42\nother.py:10\n")
        result = load_allowlist(allowlist)
        assert result == {("file.py", 42), ("other.py", 10)}

    def test_load_mixed_entries(self, tmp_path: Path) -> None:
        """Mix of file-level and line-level entries."""
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("# Comment\nfile.py\nother.py:10\nthird.py\n")
        result = load_allowlist(allowlist)
        assert result == {("file.py", None), ("other.py", 10), ("third.py", None)}

    def test_load_invalid_line_number(self, tmp_path: Path) -> None:
        """Invalid line numbers should be treated as file paths."""
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("file.py:not_a_number\n")
        result = load_allowlist(allowlist)
        # Treated as whole-file entry
        assert result == {("file.py:not_a_number", None)}


class TestShouldSkipDir:
    """Tests for directory exclusion."""

    def test_skips_git(self) -> None:
        """Skip .git directories."""
        assert should_skip_dir(".git") is True

    def test_skips_node_modules(self) -> None:
        """Skip node_modules directories."""
        assert should_skip_dir("node_modules") is True

    def test_skips_pycache(self) -> None:
        """Skip __pycache__ directories."""
        assert should_skip_dir("__pycache__") is True

    def test_skips_venv(self) -> None:
        """Skip venv directories."""
        assert should_skip_dir("venv") is True
        assert should_skip_dir(".venv") is True

    def test_skips_mypy_cache(self) -> None:
        """Skip .mypy_cache directories."""
        assert should_skip_dir(".mypy_cache") is True

    def test_skips_pytest_cache(self) -> None:
        """Skip .pytest_cache directories."""
        assert should_skip_dir(".pytest_cache") is True

    def test_skips_egg_info(self) -> None:
        """Skip .egg-info directories."""
        assert should_skip_dir("mypackage.egg-info") is True
        assert should_skip_dir("foo.egg-info") is True

    def test_allows_src(self) -> None:
        """Normal directories should not be skipped."""
        assert should_skip_dir("src") is False
        assert should_skip_dir("tests") is False
        assert should_skip_dir("lib") is False


class TestScanFile:
    """Tests for single file scanning."""

    def test_scan_clean_file(self, tmp_path: Path) -> None:
        """Clean files should return no violations."""
        pyfile = tmp_path / "clean.py"
        pyfile.write_text("x = 1\ny = 2\n")
        result = scan_file(pyfile, set())
        assert result == []

    def test_scan_file_with_violation(self, tmp_path: Path) -> None:
        """Files with violations should be detected."""
        pyfile = tmp_path / "bad.py"
        pyfile.write_text('path = "/Users/john/file"\n')
        result = scan_file(pyfile, set())
        assert len(result) == 1
        assert result[0].lineno == 1

    def test_scan_file_with_syntax_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Files with syntax errors should be skipped with warning."""
        pyfile = tmp_path / "broken.py"
        pyfile.write_text("def broken(\n")
        result = scan_file(pyfile, set())
        assert result == []
        captured = capsys.readouterr()
        assert "syntax error" in captured.err.lower()

    def test_scan_file_with_encoding_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Files with encoding errors should be skipped with warning."""
        pyfile = tmp_path / "binary.py"
        pyfile.write_bytes(b"\x80\x81\x82\x83")  # Invalid UTF-8
        result = scan_file(pyfile, set())
        assert result == []
        captured = capsys.readouterr()
        assert "encoding error" in captured.err.lower()


class TestScanDirectory:
    """Tests for directory scanning."""

    def test_scan_clean_directory(self, tmp_path: Path) -> None:
        """Clean directories should return no violations."""
        (tmp_path / "clean.py").write_text("x = 1\n")
        result = scan_directory(tmp_path, set())
        assert len(result) == 0

    def test_scan_with_violation(self, tmp_path: Path) -> None:
        """Directories with violations should be detected."""
        (tmp_path / "bad.py").write_text('path = "/Users/john/file"\n')
        result = scan_directory(tmp_path, set())
        assert len(result) == 1
        assert result[0].lineno == 1

    def test_scan_recursive(self, tmp_path: Path) -> None:
        """Should scan subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "bad.py").write_text('path = "/Users/john/file"\n')
        result = scan_directory(tmp_path, set())
        assert len(result) == 1

    def test_skips_pycache(self, tmp_path: Path) -> None:
        """Should skip __pycache__ directories."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "bad.py").write_text('x = "/Users/john"')
        result = scan_directory(tmp_path, set())
        assert len(result) == 0

    def test_skips_venv(self, tmp_path: Path) -> None:
        """Should skip venv directories."""
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "bad.py").write_text('x = "/Users/john"')
        result = scan_directory(tmp_path, set())
        assert len(result) == 0

    def test_skips_non_python(self, tmp_path: Path) -> None:
        """Should skip non-Python files."""
        (tmp_path / "data.json").write_text('{"path": "/Users/john"}')
        (tmp_path / "script.sh").write_text('PATH="/Users/john"')
        result = scan_directory(tmp_path, set())
        assert len(result) == 0

    def test_does_not_follow_symlinks(self, tmp_path: Path) -> None:
        """Should not follow symlinks to avoid loops and external code."""
        # Create external directory with violation
        external = tmp_path / "external"
        external.mkdir()
        (external / "bad.py").write_text('x = "/Users/john"')

        # Create project with symlink to external
        project = tmp_path / "project"
        project.mkdir()
        (project / "link").symlink_to(external)

        result = scan_directory(project, set())
        assert len(result) == 0  # Should not follow symlink


class TestFormatOutput:
    """Tests for output formatting."""

    def test_format_no_violations(self) -> None:
        """Format output when no violations found."""
        output = format_output([])
        assert "No hardcoded paths found" in output

    def test_format_single_violation(self) -> None:
        """Format output with a single violation."""
        violations = [
            Violation(
                filepath="test.py",
                lineno=10,
                description="macOS home directory",
                string_value="/Users/john/file",
            )
        ]
        output = format_output(violations)
        assert "test.py:10" in output
        assert "macOS home directory" in output
        assert "/Users/john/file" in output
        assert "Found 1 hardcoded path(s)" in output

    def test_format_truncates_long_strings(self) -> None:
        """Long strings should be truncated in output."""
        long_path = "/Users/john/" + "a" * 100
        violations = [
            Violation(
                filepath="test.py",
                lineno=10,
                description="macOS home directory",
                string_value=long_path,
            )
        ]
        output = format_output(violations)
        assert "..." in output
        # Full path should not appear
        assert long_path not in output


class TestMain:
    """Tests for main entry point."""

    def test_clean_directory_returns_0(self, tmp_path: Path) -> None:
        """Clean directory should return exit code 0."""
        (tmp_path / "clean.py").write_text("x = 1\n")
        result = main([str(tmp_path)])
        assert result == 0

    def test_violations_returns_1(self, tmp_path: Path) -> None:
        """Directory with violations should return exit code 1."""
        (tmp_path / "bad.py").write_text('path = "/Users/john/file"\n')
        result = main([str(tmp_path)])
        assert result == 1

    def test_nonexistent_directory_returns_2(self, tmp_path: Path) -> None:
        """Non-existent directory should return exit code 2."""
        result = main([str(tmp_path / "nonexistent")])
        assert result == 2

    def test_file_instead_of_directory_returns_2(self, tmp_path: Path) -> None:
        """Passing a file instead of directory should return exit code 2."""
        pyfile = tmp_path / "test.py"
        pyfile.write_text("x = 1")
        result = main([str(pyfile)])
        assert result == 2

    def test_too_many_arguments_returns_2(self, tmp_path: Path) -> None:
        """Too many arguments should return exit code 2."""
        result = main([str(tmp_path), "extra_arg"])
        assert result == 2


class TestViolationStr:
    """Tests for Violation string representation."""

    def test_str_format(self) -> None:
        """Test string formatting of Violation."""
        v = Violation(
            filepath="path/to/file.py",
            lineno=42,
            description="macOS home directory",
            string_value="/Users/test/file",
        )
        s = str(v)
        assert "path/to/file.py:42" in s
        assert "macOS home directory" in s
        assert '"/Users/test/file"' in s

    def test_str_truncates_long_string(self) -> None:
        """Test that long strings are truncated."""
        long_value = "x" * 100
        v = Violation(
            filepath="file.py",
            lineno=1,
            description="test",
            string_value=long_value,
        )
        s = str(v)
        assert "..." in s
        assert len(s) < 200  # Should be truncated


class TestTempfileDetection:
    """Integration tests for /tmp/ path detection with tempfile usage."""

    def test_tmp_flagged_without_tempfile(self, tmp_path: Path) -> None:
        """Hardcoded /tmp/ without tempfile import should be flagged."""
        pyfile = tmp_path / "test.py"
        pyfile.write_text('path = "/tmp/cache/data.json"\n')
        result = scan_file(pyfile, set())
        assert len(result) == 1
        assert "/tmp/" in result[0].description

    def test_tmp_allowed_with_import_tempfile(self, tmp_path: Path) -> None:
        """Hardcoded /tmp/ with 'import tempfile' should be allowed."""
        pyfile = tmp_path / "test.py"
        pyfile.write_text('import tempfile\npath = "/tmp/cache/data.json"\n')
        result = scan_file(pyfile, set())
        assert len(result) == 0

    def test_tmp_allowed_with_from_tempfile(self, tmp_path: Path) -> None:
        """Hardcoded /tmp/ with 'from tempfile import' should be allowed."""
        pyfile = tmp_path / "test.py"
        pyfile.write_text(
            'from tempfile import NamedTemporaryFile\npath = "/tmp/cache"\n'
        )
        result = scan_file(pyfile, set())
        assert len(result) == 0

    def test_tmp_allowed_with_tmp_path_fixture(self, tmp_path: Path) -> None:
        """Hardcoded /tmp/ in test with tmp_path fixture should be allowed."""
        pyfile = tmp_path / "test.py"
        pyfile.write_text('def test_foo(tmp_path):\n    path = "/tmp/cache"\n')
        result = scan_file(pyfile, set())
        assert len(result) == 0
