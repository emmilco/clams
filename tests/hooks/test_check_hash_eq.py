"""Tests for the check_hash_eq pre-commit hook.

This module tests the AST-based detection of __hash__/__eq__ methods
and the advisory warning system for classes without contract tests.

Reference: BUG-028 - ContextItem hash/eq contract violation
"""

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

# Add the hooks directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".claude" / "hooks"))

from check_hash_eq import (
    HashEqInfo,
    Warning,
    check_files,
    class_has_test,
    find_hash_eq_classes,
    format_methods,
    format_warning,
    is_test_file,
    main,
)


@pytest.fixture
def temp_python_file(tmp_path: Path) -> Callable[..., Path]:
    """Factory to create temporary Python files for testing."""

    def create(content: str, name: str = "test_module.py") -> Path:
        f = tmp_path / name
        f.write_text(content)
        return f

    return create


@pytest.fixture
def temp_test_file(tmp_path: Path) -> Callable[..., Path]:
    """Factory to create temporary test files."""

    def create(content: str) -> Path:
        f = tmp_path / "test_data_contracts.py"
        f.write_text(content)
        return f

    return create


class TestHashEqVisitor:
    """Tests for the AST visitor that detects __hash__ and __eq__."""

    def test_detects_hash_method(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Detects def __hash__(self) in a class."""
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 1
        assert results[0].class_name == "MyClass"
        assert results[0].has_hash is True
        assert results[0].has_eq is False

    def test_detects_eq_method(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Detects def __eq__(self, other) in a class."""
        source = """
class MyClass:
    def __eq__(self, other: object) -> bool:
        return True
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 1
        assert results[0].class_name == "MyClass"
        assert results[0].has_hash is False
        assert results[0].has_eq is True

    def test_detects_both_methods(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Detects class with both __hash__ and __eq__."""
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42

    def __eq__(self, other: object) -> bool:
        return True
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 1
        assert results[0].class_name == "MyClass"
        assert results[0].has_hash is True
        assert results[0].has_eq is True

    def test_detects_hash_none(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Recognizes __hash__ = None as intentionally unhashable."""
        source = """
class UnhashableClass:
    __hash__ = None

    def __eq__(self, other: object) -> bool:
        return True
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 1
        assert results[0].class_name == "UnhashableClass"
        assert results[0].has_hash is False
        assert results[0].has_eq is True
        assert results[0].has_hash_none is True

    def test_detects_nested_classes(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Finds __hash__/__eq__ in nested class definitions."""
        source = """
class Outer:
    class Inner:
        def __hash__(self) -> int:
            return 42
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 1
        assert results[0].class_name == "Inner"
        assert results[0].has_hash is True

    def test_reports_correct_line_number(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Line number matches class definition."""
        source = """# Comment
# Another comment

class MyClass:
    def __hash__(self) -> int:
        return 42
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 1
        assert results[0].line_number == 4  # Class starts on line 4

    def test_detects_multiple_classes(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Detects multiple classes with __hash__/__eq__."""
        source = """
class First:
    def __hash__(self) -> int:
        return 1

class Second:
    def __eq__(self, other: object) -> bool:
        return True

class Third:
    pass  # No __hash__ or __eq__
"""
        filepath = temp_python_file(source)
        results = find_hash_eq_classes(filepath)

        assert len(results) == 2
        class_names = {r.class_name for r in results}
        assert "First" in class_names
        assert "Second" in class_names
        assert "Third" not in class_names


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
        assert not is_test_file(Path("/project/src/clams/models.py"))


class TestClassHasTest:
    """Tests for the class_has_test function."""

    def test_class_with_test_found(
        self, temp_test_file: Callable[..., Path]
    ) -> None:
        """Returns True if class name in test file."""
        test_content = """
class TestContextItemContract:
    def test_equal_items_have_equal_hashes(self) -> None:
        item1 = ContextItem(...)
"""
        test_file = temp_test_file(test_content)
        assert class_has_test("ContextItem", test_file)

    def test_class_without_test(
        self, temp_test_file: Callable[..., Path]
    ) -> None:
        """Returns False if class name not in test file."""
        test_content = """
class TestOtherClass:
    pass
"""
        test_file = temp_test_file(test_content)
        assert not class_has_test("MyClass", test_file)

    def test_missing_test_file(self, tmp_path: Path) -> None:
        """Returns False if test file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.py"
        assert not class_has_test("AnyClass", nonexistent)

    def test_word_boundary_matching(
        self, temp_test_file: Callable[..., Path]
    ) -> None:
        """'Item' doesn't match 'ContextItem'."""
        test_content = """
class TestContextItemContract:
    item = ContextItem(...)
"""
        test_file = temp_test_file(test_content)
        # "ContextItem" should be found
        assert class_has_test("ContextItem", test_file)
        # "Item" should NOT match "ContextItem"
        assert not class_has_test("Item", test_file)
        # "Context" should NOT match "ContextItem"
        assert not class_has_test("Context", test_file)


class TestCheckFiles:
    """Tests for the check_files function."""

    def test_ignores_test_files(
        self,
        tmp_path: Path,
        temp_test_file: Callable[..., Path],
    ) -> None:
        """No warnings for test files."""
        # Create a test file with __hash__
        test_file_content = """
class TestHelper:
    def __hash__(self) -> int:
        return 42
"""
        test_source = tmp_path / "tests" / "test_helper.py"
        test_source.parent.mkdir(parents=True)
        test_source.write_text(test_file_content)

        contract_test = temp_test_file("")
        warnings = check_files([test_source], contract_test)

        assert len(warnings) == 0

    def test_class_with_test_no_warning(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """No warning if class name in test file."""
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("item = MyClass(...)")

        warnings = check_files([src_file], test_file)
        assert len(warnings) == 0

    def test_class_without_test_warns(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Warning if class name not in test file."""
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("# Empty test file")

        warnings = check_files([src_file], test_file)
        assert len(warnings) == 1
        assert warnings[0].class_name == "MyClass"

    def test_hash_none_no_warning(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """No warning for __hash__ = None (intentionally unhashable)."""
        source = """
class UnhashableClass:
    __hash__ = None

    def __eq__(self, other: object) -> bool:
        return True
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("")

        warnings = check_files([src_file], test_file)
        # Should NOT warn - __hash__ = None means intentionally unhashable
        assert len(warnings) == 0

    def test_hash_none_with_hash_method_warns(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Warning if class has both __hash__ = None AND def __hash__."""
        # This would be unusual, but if someone defines both, warn
        source = """
class WeirdClass:
    __hash__ = None

    def __hash__(self) -> int:
        return 42
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("")

        warnings = check_files([src_file], test_file)
        # Should warn because def __hash__ is present
        assert len(warnings) == 1


class TestErrorHandling:
    """Tests for error handling."""

    def test_handles_syntax_error(
        self, temp_python_file: Callable[..., Path]
    ) -> None:
        """Skips file with syntax errors, continues processing."""
        source = "def broken(\n"  # Invalid syntax
        filepath = temp_python_file(source)

        # Should not raise, should return empty list
        results = find_hash_eq_classes(filepath)
        assert results == []

    def test_handles_deleted_file(self, tmp_path: Path) -> None:
        """Skips deleted files without error."""
        nonexistent = tmp_path / "deleted.py"

        # Should not raise, should return empty list
        results = find_hash_eq_classes(nonexistent)
        assert results == []


class TestFormatting:
    """Tests for warning formatting."""

    def test_format_methods_both(self) -> None:
        """Formats correctly when both __hash__ and __eq__."""
        info = HashEqInfo(
            class_name="Test",
            has_hash=True,
            has_eq=True,
            has_hash_none=False,
            line_number=1,
            filepath="test.py",
        )
        assert format_methods(info) == "__hash__ and __eq__"

    def test_format_methods_hash_only(self) -> None:
        """Formats correctly when only __hash__."""
        info = HashEqInfo(
            class_name="Test",
            has_hash=True,
            has_eq=False,
            has_hash_none=False,
            line_number=1,
            filepath="test.py",
        )
        assert format_methods(info) == "__hash__"

    def test_format_methods_eq_only(self) -> None:
        """Formats correctly when only __eq__."""
        info = HashEqInfo(
            class_name="Test",
            has_hash=False,
            has_eq=True,
            has_hash_none=False,
            line_number=1,
            filepath="test.py",
        )
        assert format_methods(info) == "__eq__"

    def test_format_warning_includes_class_name(self) -> None:
        """Warning message includes class name."""
        warning = Warning(
            filepath="src/models.py",
            class_name="MyClass",
            line_number=42,
            methods="__hash__",
        )
        formatted = format_warning(warning)
        assert "MyClass" in formatted

    def test_format_warning_includes_filepath(self) -> None:
        """Warning message includes file path."""
        warning = Warning(
            filepath="src/models.py",
            class_name="MyClass",
            line_number=42,
            methods="__hash__",
        )
        formatted = format_warning(warning)
        assert "src/models.py" in formatted

    def test_format_warning_includes_line_number(self) -> None:
        """Warning message includes line number."""
        warning = Warning(
            filepath="src/models.py",
            class_name="MyClass",
            line_number=42,
            methods="__hash__",
        )
        formatted = format_warning(warning)
        assert "line 42" in formatted

    def test_format_warning_references_bug028(self) -> None:
        """Warning message references BUG-028."""
        warning = Warning(
            filepath="src/models.py",
            class_name="MyClass",
            line_number=42,
            methods="__hash__",
        )
        formatted = format_warning(warning)
        assert "BUG-028" in formatted

    def test_format_warning_suggests_test_file(self) -> None:
        """Warning message suggests test_data_contracts.py."""
        warning = Warning(
            filepath="src/models.py",
            class_name="MyClass",
            line_number=42,
            methods="__hash__",
        )
        formatted = format_warning(warning)
        assert "test_data_contracts.py" in formatted


class TestExitCodes:
    """Tests for exit codes (always advisory)."""

    def test_exits_zero_with_warnings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Advisory - always exits 0 even with warnings."""
        # Create source file with __hash__ but no test
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42
"""
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        # Create empty test file
        test_dir = tmp_path / "tests" / "context"
        test_dir.mkdir(parents=True)
        (test_dir / "test_data_contracts.py").write_text("")

        # Monkeypatch sys.argv and run main
        monkeypatch.setattr(sys, "argv", ["check_hash_eq.py", str(src_file)])
        monkeypatch.chdir(tmp_path)

        exit_code = main()
        assert exit_code == 0  # Advisory mode

    def test_exits_zero_without_warnings(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Clean run exits 0."""
        # Create source file without __hash__/__eq__
        source = """
class MyClass:
    pass
"""
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        monkeypatch.setattr(sys, "argv", ["check_hash_eq.py", str(src_file)])

        exit_code = main()
        assert exit_code == 0


class TestActualContextItem:
    """Integration tests with actual ContextItem."""

    def test_actual_contextitem_has_test(self) -> None:
        """Verify ContextItem is detected and has test."""
        # Find the actual models file
        models_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "clams"
            / "context"
            / "models.py"
        )
        test_file = (
            Path(__file__).parent.parent.parent
            / "tests"
            / "context"
            / "test_data_contracts.py"
        )

        if not models_path.exists():
            pytest.skip("models.py not found")

        if not test_file.exists():
            pytest.skip("test_data_contracts.py not found")

        # Find classes with __hash__/__eq__
        results = find_hash_eq_classes(models_path)

        # ContextItem should be detected
        class_names = {r.class_name for r in results}
        assert "ContextItem" in class_names, (
            f"ContextItem not detected in {models_path}. Found: {class_names}"
        )

        # ContextItem should have a test
        assert class_has_test("ContextItem", test_file), (
            "ContextItem should have a contract test in test_data_contracts.py"
        )

    def test_contextitem_generates_no_warning(self) -> None:
        """ContextItem should not generate warnings (has test)."""
        models_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "clams"
            / "context"
            / "models.py"
        )
        test_file = (
            Path(__file__).parent.parent.parent
            / "tests"
            / "context"
            / "test_data_contracts.py"
        )

        if not models_path.exists() or not test_file.exists():
            pytest.skip("Required files not found")

        warnings = check_files([models_path], test_file)

        # No warnings for ContextItem since it has tests
        context_item_warnings = [
            w for w in warnings if w.class_name == "ContextItem"
        ]
        assert len(context_item_warnings) == 0, (
            f"ContextItem should not generate warnings: {context_item_warnings}"
        )


class TestManualMode:
    """Tests for manual mode with explicit file arguments."""

    def test_manual_file_argument(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test with explicit file paths."""
        # Create source file with __hash__
        source = """
class TestClass:
    def __hash__(self) -> int:
        return 42
"""
        src_file = tmp_path / "module.py"
        src_file.write_text(source)

        # Create test file with the class name
        test_dir = tmp_path / "tests" / "context"
        test_dir.mkdir(parents=True)
        (test_dir / "test_data_contracts.py").write_text("obj = TestClass(...)")

        monkeypatch.setattr(sys, "argv", ["check_hash_eq.py", str(src_file)])
        monkeypatch.chdir(tmp_path)

        exit_code = main()
        assert exit_code == 0


class TestEdgeCases:
    """Tests for edge cases mentioned in the proposal."""

    def test_only_hash_defined_warns(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Only __hash__ defined - warns (may inherit broken __eq__)."""
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("")

        warnings = check_files([src_file], test_file)
        assert len(warnings) == 1
        assert warnings[0].methods == "__hash__"

    def test_only_eq_defined_warns(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Only __eq__ defined - warns (should set __hash__ = None or define it)."""
        source = """
class MyClass:
    def __eq__(self, other: object) -> bool:
        return True
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("")

        warnings = check_files([src_file], test_file)
        assert len(warnings) == 1
        assert warnings[0].methods == "__eq__"

    def test_both_methods_single_warning(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Both methods defined - single warning mentioning both."""
        source = """
class MyClass:
    def __hash__(self) -> int:
        return 42

    def __eq__(self, other: object) -> bool:
        return True
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("")

        warnings = check_files([src_file], test_file)
        assert len(warnings) == 1
        assert warnings[0].methods == "__hash__ and __eq__"

    def test_nested_classes_detected_separately(
        self,
        temp_python_file: Callable[..., Path],
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Nested classes are detected and warned for separately."""
        source = """
class Outer:
    class Inner:
        def __hash__(self) -> int:
            return 42
"""
        src_file = temp_python_file(source, "module.py")
        test_file = temp_test_file("")

        warnings = check_files([src_file], test_file)
        assert len(warnings) == 1
        assert warnings[0].class_name == "Inner"

    def test_non_python_files_skipped(
        self,
        tmp_path: Path,
        temp_test_file: Callable[..., Path],
    ) -> None:
        """Non-.py files are skipped."""
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("class Fake:\n    def __hash__(self): pass")
        test_file = temp_test_file("")

        warnings = check_files([txt_file], test_file)
        assert len(warnings) == 0
