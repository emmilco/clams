"""TreeSitter-based code parser implementation."""

import asyncio
from pathlib import Path

import structlog
from tree_sitter import Language, Node, Parser

from .base import CodeParser, ParseError, SemanticUnit, UnitType
from .utils import EXTENSION_MAP

logger = structlog.get_logger(__name__)

# Branch node types for cyclomatic complexity by language
BRANCH_TYPES: dict[str, set[str]] = {
    "python": {
        "if_statement",
        "elif_clause",
        "for_statement",
        "while_statement",
        "try_statement",
        "except_clause",
        "with_statement",
        "boolean_operator",  # and, or
        "match_statement",
        "case_clause",
    },
    "typescript": {
        "if_statement",
        "for_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "catch_clause",
        "switch_statement",
        "switch_case",
        "binary_expression",  # &&, ||
        "ternary_expression",  # ?:
    },
    "javascript": {
        "if_statement",
        "for_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "catch_clause",
        "switch_statement",
        "switch_case",
        "binary_expression",  # &&, ||
        "ternary_expression",  # ?:
    },
    "lua": {
        "if_statement",
        "elseif_clause",
        "for_statement",
        "while_statement",
        "repeat_statement",
        "binary_operator",  # and, or
    },
    "rust": {
        "if_expression",
        "else_clause",
        "match_expression",
        "match_arm",
        "for_expression",
        "while_expression",
        "loop_expression",
        "binary_expression",  # &&, ||, ?
    },
    "swift": {
        "if_statement",
        "else_clause",
        "switch_statement",
        "switch_case",
        "for_statement",
        "while_statement",
        "guard_statement",
        "binary_expression",  # &&, ||, ??
        "ternary_expression",
    },
    "java": {
        "if_statement",
        "else_clause",
        "switch_statement",
        "switch_case",
        "for_statement",
        "while_statement",
        "do_statement",
        "try_statement",
        "catch_clause",
        "binary_expression",  # &&, ||
        "ternary_expression",  # ?:
    },
    "c": {
        "if_statement",
        "else_clause",
        "switch_statement",
        "case_statement",
        "for_statement",
        "while_statement",
        "do_statement",
        "binary_expression",  # &&, ||
        "conditional_expression",  # ?:
    },
    "cpp": {
        "if_statement",
        "else_clause",
        "switch_statement",
        "case_statement",
        "for_statement",
        "while_statement",
        "do_statement",
        "binary_expression",  # &&, ||
        "conditional_expression",  # ?:
    },
}


class TreeSitterParser(CodeParser):
    """Code parser using tree-sitter for multi-language support."""

    def __init__(self) -> None:
        """Initialize parser with all supported language grammars.

        Loading is done eagerly to avoid lazy-loading overhead during parsing.
        Each language grammar is imported from its respective package.
        """
        # Import languages dynamically
        import tree_sitter_cpp
        import tree_sitter_java
        import tree_sitter_javascript
        import tree_sitter_python
        import tree_sitter_rust
        import tree_sitter_sql
        import tree_sitter_swift
        import tree_sitter_typescript

        # Create parsers for each language
        self._parsers: dict[str, Parser] = {}
        self._languages: dict[str, Language] = {}

        # Python
        self._languages["python"] = Language(tree_sitter_python.language())
        self._parsers["python"] = Parser(self._languages["python"])

        # TypeScript
        ts_lang = Language(tree_sitter_typescript.language_typescript())
        self._languages["typescript"] = ts_lang
        self._parsers["typescript"] = Parser(ts_lang)

        # JavaScript
        js_lang = Language(tree_sitter_javascript.language())
        self._languages["javascript"] = js_lang
        self._parsers["javascript"] = Parser(js_lang)

        # Rust
        rust_lang = Language(tree_sitter_rust.language())
        self._languages["rust"] = rust_lang
        self._parsers["rust"] = Parser(rust_lang)

        # Swift
        swift_lang = Language(tree_sitter_swift.language())
        self._languages["swift"] = swift_lang
        self._parsers["swift"] = Parser(swift_lang)

        # Java
        java_lang = Language(tree_sitter_java.language())
        self._languages["java"] = java_lang
        self._parsers["java"] = Parser(java_lang)

        # C++
        cpp_lang = Language(tree_sitter_cpp.language())
        self._languages["cpp"] = cpp_lang
        self._parsers["cpp"] = Parser(cpp_lang)
        # C uses same parser as C++
        self._languages["c"] = cpp_lang
        self._parsers["c"] = Parser(cpp_lang)

        # SQL
        sql_lang = Language(tree_sitter_sql.language())
        self._languages["sql"] = sql_lang
        self._parsers["sql"] = Parser(sql_lang)

    def supported_languages(self) -> list[str]:
        """Return list of supported language identifiers."""
        return list(self._parsers.keys())

    def detect_language(self, path: str) -> str | None:
        """Detect language from file extension."""
        ext = Path(path).suffix.lower()
        return EXTENSION_MAP.get(ext)

    async def parse_file(self, path: str) -> list[SemanticUnit]:
        """Parse a file and extract semantic units.

        Uses run_in_executor for CPU-bound tree-sitter parsing.

        Raises:
            ParseError: If file cannot be parsed
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_file_sync, path)

    def _parse_file_sync(self, path: str) -> list[SemanticUnit]:
        """Synchronous file parsing (runs in executor)."""
        # Detect language
        language = self.detect_language(path)
        if not language:
            logger.debug("unsupported_language", path=path)
            return []

        # Read file with binary detection
        try:
            # Detect binary files (null bytes in first 8KB)
            with open(path, "rb") as f:
                sample = f.read(8192)
                if b"\x00" in sample:
                    return []  # Skip silently

            # Read as UTF-8
            with open(path, encoding="utf-8") as f:
                source = f.read()
        except UnicodeDecodeError:
            raise ParseError("encoding_error", "Not valid UTF-8", path)
        except OSError as e:
            raise ParseError("io_error", str(e), path)

        # Parse with tree-sitter
        parser = self._parsers[language]
        tree = parser.parse(bytes(source, "utf8"))

        # Extract units based on language
        units: list[SemanticUnit] = []
        if language == "python":
            units = self._extract_python_units(tree.root_node, source, path)
        elif language in ("typescript", "javascript"):
            units = self._extract_ts_js_units(tree.root_node, source, path, language)
        elif language == "lua":
            units = self._extract_lua_units(tree.root_node, source, path)
        elif language == "rust":
            units = self._extract_rust_units(tree.root_node, source, path)
        elif language == "swift":
            units = self._extract_swift_units(tree.root_node, source, path)
        elif language == "java":
            units = self._extract_java_units(tree.root_node, source, path)
        elif language in ("c", "cpp"):
            units = self._extract_c_cpp_units(tree.root_node, source, path, language)
        elif language == "sql":
            units = self._extract_sql_units(tree.root_node, source, path)

        return units

    def _extract_python_units(
        self, root: Node, source: str, file_path: str
    ) -> list[SemanticUnit]:
        """Extract Python functions, classes, methods, module docstrings, constants."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        # Extract module docstring
        if root.child_count > 0:
            first_child = root.children[0]
            if first_child.type == "expression_statement":
                expr = first_child.children[0] if first_child.child_count > 0 else None
                if expr and expr.type == "string":
                    text = self._extract_text(expr, source)
                    docstring = text.strip('"""').strip("'''").strip()
                    units.append(
                        SemanticUnit(
                            name=module_name,
                            qualified_name=module_name,
                            unit_type=UnitType.MODULE,
                            signature=f"# Module: {module_name}",
                            content=docstring,
                            file_path=file_path,
                            start_line=expr.start_point[0] + 1,
                            end_line=expr.end_point[0] + 1,
                            language="python",
                            docstring=docstring,
                            complexity=None,
                        )
                    )

        # Extract classes and functions
        for node in root.children:
            if node.type == "class_definition":
                units.extend(
                    self._extract_python_class(node, source, file_path, module_name)
                )
            elif node.type == "function_definition":
                unit = self._extract_python_function(
                    node, source, file_path, module_name, None
                )
                if unit:
                    units.append(unit)
            elif node.type == "assignment":
                # Extract module-level constants (UPPER_CASE)
                target = node.child_by_field_name("left")
                if target and target.type == "identifier":
                    name = self._extract_text(target, source)
                    if name.isupper() and "_" in name:
                        text = self._extract_text(node, source)
                        units.append(
                            SemanticUnit(
                                name=name,
                                qualified_name=f"{module_name}.{name}",
                                unit_type=UnitType.CONSTANT,
                                signature=text.split("\n")[0],
                                content=text,
                                file_path=file_path,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                language="python",
                                docstring=None,
                                complexity=None,
                            )
                        )

        return units

    def _extract_python_class(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> list[SemanticUnit]:
        """Extract a Python class and its methods."""
        units: list[SemanticUnit] = []

        # Get class name
        name_node = node.child_by_field_name("name")
        if not name_node:
            return units

        class_name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{class_name}"

        # Extract class docstring
        docstring = self._extract_python_docstring(node, source)

        # Get class signature (first line)
        signature = self._extract_text(node, source).split("\n")[0]

        # Get class body
        body = node.child_by_field_name("body")

        units.append(
            SemanticUnit(
                name=class_name,
                qualified_name=qualified_name,
                unit_type=UnitType.CLASS,
                signature=signature,
                content=self._extract_text(node, source),
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="python",
                docstring=docstring if docstring else None,
                complexity=None,
            )
        )

        # Extract methods
        if body:
            for child in body.children:
                if child.type == "function_definition":
                    method = self._extract_python_function(
                        child, source, file_path, module_name, class_name
                    )
                    if method:
                        units.append(method)

        return units

    def _extract_python_function(
        self,
        node: Node,
        source: str,
        file_path: str,
        module_name: str,
        class_name: str | None,
    ) -> SemanticUnit | None:
        """Extract a Python function or method."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)

        # Build qualified name
        if class_name:
            qualified_name = f"{module_name}.{class_name}.{name}"
            unit_type = UnitType.METHOD
        else:
            qualified_name = f"{module_name}.{name}"
            unit_type = UnitType.FUNCTION

        # Get signature (first line)
        signature = self._extract_text(node, source).split("\n")[0]

        # Extract docstring
        docstring = self._extract_python_docstring(node, source)

        # Compute complexity
        complexity = self._compute_complexity(node, "python")

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=unit_type,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="python",
            docstring=docstring if docstring else None,
            complexity=complexity,
        )

    def _extract_python_docstring(self, node: Node, source: str) -> str | None:
        """Extract Python docstring from function/class body."""
        body = node.child_by_field_name("body")
        if not body or body.child_count == 0:
            return None

        # Check first statement in body
        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement" and first_stmt.child_count > 0:
            expr = first_stmt.children[0]
            if expr.type == "string":
                text = self._extract_text(expr, source)
                # Remove quotes
                for quote in ['"""', "'''"]:
                    if text.startswith(quote) and text.endswith(quote):
                        return text[3:-3].strip()
                # Single quotes
                for quote in ['"', "'"]:
                    if text.startswith(quote) and text.endswith(quote):
                        return text[1:-1].strip()
                return text.strip()
        return None

    def _extract_ts_js_units(
        self, root: Node, source: str, file_path: str, language: str
    ) -> list[SemanticUnit]:
        """Extract TypeScript/JavaScript units."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            # Handle export statements that wrap declarations
            actual_node = node
            if node.type == "export_statement":
                # Get the declaration inside the export
                declaration = node.child_by_field_name("declaration")
                if declaration:
                    actual_node = declaration
                else:
                    continue

            if actual_node.type in ("function_declaration", "arrow_function"):
                unit = self._extract_ts_js_function(
                    actual_node, source, file_path, module_name, None, language
                )
                if unit:
                    units.append(unit)
            elif actual_node.type == "class_declaration":
                units.extend(
                    self._extract_ts_js_class(
                        actual_node, source, file_path, module_name, language
                    )
                )
            elif (
                actual_node.type == "interface_declaration"
                and language == "typescript"
            ):
                unit = self._extract_ts_interface(
                    actual_node, source, file_path, module_name
                )
                if unit:
                    units.append(unit)

        return units

    def _extract_ts_js_class(
        self, node: Node, source: str, file_path: str, module_name: str, language: str
    ) -> list[SemanticUnit]:
        """Extract a TypeScript/JavaScript class and its methods."""
        units: list[SemanticUnit] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            return units

        class_name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{class_name}"

        # Extract JSDoc
        docstring = self._extract_jsdoc(node, source)

        signature = self._extract_text(node, source).split("\n")[0]

        units.append(
            SemanticUnit(
                name=class_name,
                qualified_name=qualified_name,
                unit_type=UnitType.CLASS,
                signature=signature,
                content=self._extract_text(node, source),
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                docstring=docstring if docstring else None,
                complexity=None,
            )
        )

        # Extract methods
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "method_definition":
                    method = self._extract_ts_js_function(
                        child, source, file_path, module_name, class_name, language
                    )
                    if method:
                        units.append(method)

        return units

    def _extract_ts_js_function(
        self,
        node: Node,
        source: str,
        file_path: str,
        module_name: str,
        class_name: str | None,
        language: str,
    ) -> SemanticUnit | None:
        """Extract a TypeScript/JavaScript function or method."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)

        if class_name:
            qualified_name = f"{module_name}.{class_name}.{name}"
            unit_type = UnitType.METHOD
        else:
            qualified_name = f"{module_name}.{name}"
            unit_type = UnitType.FUNCTION

        signature = self._extract_text(node, source).split("\n")[0]
        docstring = self._extract_jsdoc(node, source)
        complexity = self._compute_complexity(node, language)

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=unit_type,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language=language,
            docstring=docstring if docstring else None,
            complexity=complexity,
        )

    def _extract_ts_interface(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> SemanticUnit | None:
        """Extract a TypeScript interface."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{name}"

        signature = self._extract_text(node, source).split("\n")[0]
        docstring = self._extract_jsdoc(node, source)

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=UnitType.CLASS,  # Treat interfaces like classes
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="typescript",
            docstring=docstring if docstring else None,
            complexity=None,
        )

    def _extract_jsdoc(self, node: Node, source: str) -> str | None:
        """Extract JSDoc comment preceding a node."""
        # Look for comment node before this node
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment = self._extract_text(node.prev_sibling, source)
            if comment.startswith("/**") and comment.endswith("*/"):
                # Remove /** and */
                return comment[3:-2].strip()
        return None

    def _extract_lua_units(
        self, root: Node, source: str, file_path: str
    ) -> list[SemanticUnit]:
        """Extract Lua functions."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            if node.type in ("function_declaration", "local_function"):
                unit = self._extract_lua_function(node, source, file_path, module_name)
                if unit:
                    units.append(unit)

        return units

    def _extract_lua_function(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> SemanticUnit | None:
        """Extract a Lua function."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{name}"

        signature = self._extract_text(node, source).split("\n")[0]
        complexity = self._compute_complexity(node, "lua")

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=UnitType.FUNCTION,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="lua",
            docstring=None,
            complexity=complexity,
        )

    def _extract_rust_units(
        self, root: Node, source: str, file_path: str
    ) -> list[SemanticUnit]:
        """Extract Rust functions, structs, enums, impl blocks, traits."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            if node.type == "function_item":
                unit = self._extract_rust_function(node, source, file_path, module_name)
                if unit:
                    units.append(unit)
            elif node.type in ("struct_item", "enum_item", "trait_item"):
                unit = self._extract_rust_type(node, source, file_path, module_name)
                if unit:
                    units.append(unit)

        return units

    def _extract_rust_function(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> SemanticUnit | None:
        """Extract a Rust function."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}::{name}"

        signature = self._extract_text(node, source).split("\n")[0]
        complexity = self._compute_complexity(node, "rust")

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=UnitType.FUNCTION,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="rust",
            docstring=None,
            complexity=complexity,
        )

    def _extract_rust_type(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> SemanticUnit | None:
        """Extract a Rust struct, enum, or trait."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}::{name}"

        signature = self._extract_text(node, source).split("\n")[0]

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=UnitType.CLASS,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="rust",
            docstring=None,
            complexity=None,
        )

    def _extract_swift_units(
        self, root: Node, source: str, file_path: str
    ) -> list[SemanticUnit]:
        """Extract Swift functions, classes, structs, enums, protocols."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            if node.type == "function_declaration":
                unit = self._extract_swift_function(
                    node, source, file_path, module_name, None
                )
                if unit:
                    units.append(unit)
            elif node.type in (
                "class_declaration",
                "struct_declaration",
                "enum_declaration",
                "protocol_declaration",
            ):
                units.extend(
                    self._extract_swift_type(node, source, file_path, module_name)
                )

        return units

    def _extract_swift_type(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> list[SemanticUnit]:
        """Extract a Swift class/struct/enum/protocol and its methods."""
        units: list[SemanticUnit] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            return units

        type_name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{type_name}"

        signature = self._extract_text(node, source).split("\n")[0]

        units.append(
            SemanticUnit(
                name=type_name,
                qualified_name=qualified_name,
                unit_type=UnitType.CLASS,
                signature=signature,
                content=self._extract_text(node, source),
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="swift",
                docstring=None,
                complexity=None,
            )
        )

        # Extract methods
        for child in node.children:
            if child.type == "function_declaration":
                method = self._extract_swift_function(
                    child, source, file_path, module_name, type_name
                )
                if method:
                    units.append(method)

        return units

    def _extract_swift_function(
        self,
        node: Node,
        source: str,
        file_path: str,
        module_name: str,
        class_name: str | None,
    ) -> SemanticUnit | None:
        """Extract a Swift function or method."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)

        if class_name:
            qualified_name = f"{module_name}.{class_name}.{name}"
            unit_type = UnitType.METHOD
        else:
            qualified_name = f"{module_name}.{name}"
            unit_type = UnitType.FUNCTION

        signature = self._extract_text(node, source).split("\n")[0]
        complexity = self._compute_complexity(node, "swift")

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=unit_type,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="swift",
            docstring=None,
            complexity=complexity,
        )

    def _extract_java_units(
        self, root: Node, source: str, file_path: str
    ) -> list[SemanticUnit]:
        """Extract Java classes, interfaces, enums, methods."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            if node.type in (
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
            ):
                units.extend(
                    self._extract_java_type(node, source, file_path, module_name)
                )

        return units

    def _extract_java_type(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> list[SemanticUnit]:
        """Extract a Java class/interface/enum and its methods."""
        units: list[SemanticUnit] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            return units

        type_name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{type_name}"

        signature = self._extract_text(node, source).split("\n")[0]
        docstring = self._extract_javadoc(node, source)

        units.append(
            SemanticUnit(
                name=type_name,
                qualified_name=qualified_name,
                unit_type=UnitType.CLASS,
                signature=signature,
                content=self._extract_text(node, source),
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="java",
                docstring=docstring if docstring else None,
                complexity=None,
            )
        )

        # Extract methods and constructors
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type in ("method_declaration", "constructor_declaration"):
                    method = self._extract_java_method(
                        child, source, file_path, module_name, type_name
                    )
                    if method:
                        units.append(method)

        return units

    def _extract_java_method(
        self, node: Node, source: str, file_path: str, module_name: str, class_name: str
    ) -> SemanticUnit | None:
        """Extract a Java method or constructor."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{class_name}.{name}"

        signature = self._extract_text(node, source).split("\n")[0]
        docstring = self._extract_javadoc(node, source)
        complexity = self._compute_complexity(node, "java")

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=UnitType.METHOD,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="java",
            docstring=docstring if docstring else None,
            complexity=complexity,
        )

    def _extract_javadoc(self, node: Node, source: str) -> str | None:
        """Extract Javadoc comment preceding a node."""
        if node.prev_sibling and node.prev_sibling.type == "comment":
            comment = self._extract_text(node.prev_sibling, source)
            if comment.startswith("/**") and comment.endswith("*/"):
                return comment[3:-2].strip()
        return None

    def _extract_c_cpp_units(
        self, root: Node, source: str, file_path: str, language: str
    ) -> list[SemanticUnit]:
        """Extract C/C++ functions, classes, structs."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            if node.type == "function_definition":
                unit = self._extract_c_cpp_function(
                    node, source, file_path, module_name, language
                )
                if unit:
                    units.append(unit)
            elif (
                node.type in ("class_specifier", "struct_specifier")
                and language == "cpp"
            ):
                units.extend(
                    self._extract_cpp_class(node, source, file_path, module_name)
                )

        return units

    def _extract_c_cpp_function(
        self, node: Node, source: str, file_path: str, module_name: str, language: str
    ) -> SemanticUnit | None:
        """Extract a C/C++ function."""
        declarator = node.child_by_field_name("declarator")
        if not declarator:
            return None

        # Get function name from declarator
        name = self._extract_function_name_from_declarator(declarator, source)
        if not name:
            return None

        qualified_name = f"{module_name}.{name}"

        signature = self._extract_text(node, source).split("\n")[0]
        complexity = self._compute_complexity(node, language)

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=UnitType.FUNCTION,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language=language,
            docstring=None,
            complexity=complexity,
        )

    def _extract_function_name_from_declarator(
        self, declarator: Node, source: str
    ) -> str | None:
        """Extract function name from C/C++ declarator."""
        # Handle different declarator types
        if declarator.type == "function_declarator":
            child_declarator = declarator.child_by_field_name("declarator")
            if child_declarator:
                return self._extract_function_name_from_declarator(
                    child_declarator, source
                )
        elif declarator.type == "identifier":
            return self._extract_text(declarator, source)
        return None

    def _extract_cpp_class(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> list[SemanticUnit]:
        """Extract a C++ class and its methods."""
        units: list[SemanticUnit] = []

        name_node = node.child_by_field_name("name")
        if not name_node:
            return units

        class_name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}::{class_name}"

        signature = self._extract_text(node, source).split("\n")[0]

        units.append(
            SemanticUnit(
                name=class_name,
                qualified_name=qualified_name,
                unit_type=UnitType.CLASS,
                signature=signature,
                content=self._extract_text(node, source),
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="cpp",
                docstring=None,
                complexity=None,
            )
        )

        # Extract methods
        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                if child.type == "function_definition":
                    method = self._extract_c_cpp_function(
                        child, source, file_path, module_name, "cpp"
                    )
                    if method:
                        # Update qualified name to include class
                        qname = f"{module_name}::{class_name}::{method.name}"
                        method.qualified_name = qname
                        method.unit_type = UnitType.METHOD
                        units.append(method)

        return units

    def _extract_sql_units(
        self, root: Node, source: str, file_path: str
    ) -> list[SemanticUnit]:
        """Extract SQL CREATE statements."""
        units: list[SemanticUnit] = []
        module_name = Path(file_path).stem

        for node in root.children:
            if node.type in (
                "create_table_statement",
                "create_view_statement",
                "create_function_statement",
                "create_procedure_statement",
            ):
                unit = self._extract_sql_object(node, source, file_path, module_name)
                if unit:
                    units.append(unit)

        return units

    def _extract_sql_object(
        self, node: Node, source: str, file_path: str, module_name: str
    ) -> SemanticUnit | None:
        """Extract a SQL object (table, view, function, procedure)."""
        # Try to find name node
        name_node = node.child_by_field_name("name")
        if not name_node:
            # Fallback: look for identifier in children
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break

        if not name_node:
            return None

        name = self._extract_text(name_node, source)
        qualified_name = f"{module_name}.{name}"

        signature = self._extract_text(node, source).split("\n")[0]

        # Determine unit type
        if "table" in node.type:
            unit_type = UnitType.CLASS
        elif "view" in node.type:
            unit_type = UnitType.CLASS
        else:
            unit_type = UnitType.FUNCTION

        return SemanticUnit(
            name=name,
            qualified_name=qualified_name,
            unit_type=unit_type,
            signature=signature,
            content=self._extract_text(node, source),
            file_path=file_path,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            language="sql",
            docstring=None,
            complexity=None,  # SQL complexity N/A
        )

    def _compute_complexity(self, node: Node, language: str) -> int:
        """Compute cyclomatic complexity for a function/method."""
        branch_nodes = BRANCH_TYPES.get(language, set())
        count = 1  # Base complexity

        # Walk the tree and count branch points
        cursor = node.walk()
        visited_children = False
        while True:
            if not visited_children:
                current_node = cursor.node
                if current_node and current_node.type in branch_nodes:
                    count += 1
                if not cursor.goto_first_child():
                    visited_children = True
            elif cursor.goto_next_sibling():
                visited_children = False
            elif not cursor.goto_parent():
                break
            else:
                visited_children = True

        return count

    def _extract_text(self, node: Node, source: str) -> str:
        """Extract source text for a node."""
        start_byte = node.start_byte
        end_byte = node.end_byte
        return source[start_byte:end_byte]
