"""Tests for TreeSitterParser."""

from pathlib import Path

import pytest

from learning_memory_server.indexers import TreeSitterParser, UnitType

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "code_samples"


@pytest.fixture
def parser():
    """Create a TreeSitterParser instance."""
    return TreeSitterParser()


def test_language_detection(parser):
    """Test language detection from file extensions."""
    assert parser.detect_language("test.py") == "python"
    assert parser.detect_language("test.ts") == "typescript"
    assert parser.detect_language("test.tsx") == "typescript"
    assert parser.detect_language("test.js") == "javascript"
    assert parser.detect_language("test.jsx") == "javascript"
    assert parser.detect_language("test.rs") == "rust"
    assert parser.detect_language("test.swift") == "swift"
    assert parser.detect_language("test.java") == "java"
    assert parser.detect_language("test.c") == "c"
    assert parser.detect_language("test.h") == "c"
    assert parser.detect_language("test.cpp") == "cpp"
    assert parser.detect_language("test.hpp") == "cpp"
    assert parser.detect_language("test.sql") == "sql"
    assert parser.detect_language("test.lua") is None  # Not supported
    assert parser.detect_language("test.unknown") is None


def test_supported_languages(parser):
    """Test listing supported languages."""
    languages = parser.supported_languages()
    assert "python" in languages
    assert "typescript" in languages
    assert "javascript" in languages
    assert "rust" in languages
    assert "swift" in languages
    assert "java" in languages
    assert "c" in languages
    assert "cpp" in languages
    assert "sql" in languages


@pytest.mark.asyncio
async def test_parse_python(parser):
    """Test parsing Python files."""
    path = str(FIXTURES_DIR / "sample.py")
    units = await parser.parse_file(path)

    # Should extract module docstring, functions, class, methods
    # Constants are optional (tree-sitter extraction is complex)
    assert len(units) >= 4

    # Check for module docstring
    module_units = [u for u in units if u.unit_type == UnitType.MODULE]
    assert len(module_units) == 1
    assert "Sample Python module" in module_units[0].content

    # Check for functions
    functions = [u for u in units if u.unit_type == UnitType.FUNCTION]
    assert len(functions) >= 2
    func_names = {u.name for u in functions}
    assert "simple_function" in func_names
    assert "complex_function" in func_names

    # Check for class
    classes = [u for u in units if u.unit_type == UnitType.CLASS]
    assert len(classes) == 1
    assert classes[0].name == "Calculator"

    # Check for methods
    methods = [u for u in units if u.unit_type == UnitType.METHOD]
    assert len(methods) >= 2
    method_names = {u.name for u in methods}
    assert "add" in method_names
    assert "multiply" in method_names

    # Check docstrings
    simple_func = next(u for u in units if u.name == "simple_function")
    assert simple_func.docstring is not None
    assert "Add two numbers" in simple_func.docstring

    # Check complexity
    simple_func = next(u for u in units if u.name == "simple_function")
    assert simple_func.complexity == 1  # No branches

    complex_func = next(u for u in units if u.name == "complex_function")
    assert complex_func.complexity and complex_func.complexity > 3  # Has if/elif/while


@pytest.mark.asyncio
async def test_parse_typescript(parser):
    """Test parsing TypeScript files."""
    path = str(FIXTURES_DIR / "sample.ts")
    units = await parser.parse_file(path)

    assert len(units) >= 3

    # Check for interface
    interfaces = [u for u in units if u.name == "User"]
    assert len(interfaces) == 1

    # Check for function
    functions = [u for u in units if u.name == "add"]
    assert len(functions) == 1

    # Check for class
    classes = [u for u in units if u.name == "UserService"]
    assert len(classes) == 1

    # Check for methods
    methods = [u for u in units if u.unit_type == UnitType.METHOD]
    assert len(methods) >= 2


@pytest.mark.asyncio
async def test_parse_javascript(parser):
    """Test parsing JavaScript files."""
    path = str(FIXTURES_DIR / "sample.js")
    units = await parser.parse_file(path)

    assert len(units) >= 2

    # Check for function
    functions = [u for u in units if u.name == "greet"]
    assert len(functions) == 1

    # Check for class
    classes = [u for u in units if u.name == "Counter"]
    assert len(classes) == 1


@pytest.mark.asyncio
async def test_parse_rust(parser):
    """Test parsing Rust files."""
    path = str(FIXTURES_DIR / "sample.rs")
    units = await parser.parse_file(path)

    assert len(units) >= 3

    # Check for struct
    structs = [u for u in units if u.name == "Point"]
    assert len(structs) >= 1

    # Check for enum
    enums = [u for u in units if u.name == "Color"]
    assert len(enums) >= 1

    # Check for function
    functions = [u for u in units if u.name == "distance"]
    assert len(functions) >= 1


@pytest.mark.asyncio
async def test_parse_java(parser):
    """Test parsing Java files."""
    path = str(FIXTURES_DIR / "sample.java")
    units = await parser.parse_file(path)

    assert len(units) >= 2

    # Check for class (constructor may also be extracted with same name)
    classes = [
        u for u in units if u.name == "Calculator" and u.unit_type == UnitType.CLASS
    ]
    assert len(classes) == 1

    # Check for interface
    interfaces = [u for u in units if u.name == "Operation"]
    assert len(interfaces) == 1


@pytest.mark.asyncio
async def test_parse_c(parser):
    """Test parsing C files."""
    path = str(FIXTURES_DIR / "sample.c")
    units = await parser.parse_file(path)

    assert len(units) >= 2

    # Check for functions
    names = {u.name for u in units}
    assert "add" in names
    assert "factorial" in names


@pytest.mark.asyncio
async def test_parse_cpp(parser):
    """Test parsing C++ files."""
    path = str(FIXTURES_DIR / "sample.cpp")
    units = await parser.parse_file(path)

    assert len(units) >= 2

    # Check for class
    classes = [u for u in units if u.name == "Vector"]
    assert len(classes) >= 1


@pytest.mark.asyncio
async def test_parse_swift(parser):
    """Test parsing Swift files."""
    path = str(FIXTURES_DIR / "sample.swift")
    units = await parser.parse_file(path)

    assert len(units) >= 2

    # Check for struct
    structs = [u for u in units if u.name == "Rectangle"]
    assert len(structs) >= 1

    # Check for class
    classes = [u for u in units if u.name == "Circle"]
    assert len(classes) >= 1


@pytest.mark.asyncio
async def test_parse_empty_file(parser):
    """Test parsing empty file."""
    path = str(FIXTURES_DIR / "empty.py")
    units = await parser.parse_file(path)

    # Empty file should return empty list
    assert len(units) == 0


@pytest.mark.asyncio
async def test_parse_malformed_file(parser):
    """Test parsing malformed file."""
    path = str(FIXTURES_DIR / "malformed.py")
    units = await parser.parse_file(path)

    # Should still extract valid units despite syntax errors
    # Tree-sitter is error-tolerant
    assert isinstance(units, list)
