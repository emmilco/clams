"""Code unit generators for validation testing.

This module generates code unit data for testing codebase
indexing and search operations.

Reference: SPEC-034 Code Units table
"""

import uuid
from dataclasses import dataclass
from typing import Literal

import numpy as np

from tests.fixtures.data_profiles import CodeUnitProfile


@dataclass
class GeneratedCodeUnit:
    """A generated code unit entry."""

    id: str
    file_path: str
    language: str
    unit_type: Literal["function", "class", "method", "module"]
    name: str
    content: str
    line_count: int
    docstring: str | None
    nested_depth: int


# Code templates by language
CODE_TEMPLATES: dict[str, dict[str, str]] = {
    "python": {
        "function": '''def {name}({params}) -> {return_type}:
    """{docstring}"""
    {body}
    return {return_value}
''',
        "class": '''class {name}:
    """{docstring}"""

    def __init__(self{init_params}) -> None:
        {init_body}

    def {method_name}(self{method_params}) -> {return_type}:
        {method_body}
''',
        "method": '''def {name}(self{params}) -> {return_type}:
    """{docstring}"""
    {body}
    return {return_value}
''',
        "module": '''"""{docstring}"""

{imports}

{constants}

{body}
''',
    },
    "typescript": {
        "function": '''export function {name}({params}): {return_type} {{
    // {docstring}
    {body}
    return {return_value};
}}
''',
        "class": '''export class {name} {{
    // {docstring}
    {fields}

    constructor({init_params}) {{
        {init_body}
    }}

    {method_name}({method_params}): {return_type} {{
        {method_body}
    }}
}}
''',
        "method": '''{name}({params}): {return_type} {{
    // {docstring}
    {body}
    return {return_value};
}}
''',
        "module": '''// {docstring}

{imports}

{constants}

{body}
''',
    },
    "go": {
        "function": '''// {docstring}
func {name}({params}) {return_type} {{
    {body}
    return {return_value}
}}
''',
        "class": '''// {docstring}
type {name} struct {{
    {fields}
}}

func New{name}({init_params}) *{name} {{
    {init_body}
}}

func (s *{name}) {method_name}({method_params}) {return_type} {{
    {method_body}
}}
''',
        "method": '''func (s *{struct_name}) {name}({params}) {return_type} {{
    // {docstring}
    {body}
    return {return_value}
}}
''',
        "module": '''// {docstring}
package {package_name}

{imports}

{constants}

{body}
''',
    },
}


def generate_code_units(
    profile: CodeUnitProfile,
    seed: int = 42,
) -> list[GeneratedCodeUnit]:
    """Generate code unit entries matching the profile.

    Args:
        profile: Code unit profile defining characteristics
        seed: Random seed for reproducibility

    Returns:
        List of generated code units
    """
    rng = np.random.default_rng(seed)

    # Generate language assignments
    languages = list(profile.language_distribution.keys())
    lang_weights = list(profile.language_distribution.values())
    language_assignments = rng.choice(languages, size=profile.count, p=lang_weights)

    # Generate unit type assignments
    unit_types = list(profile.unit_type_distribution.keys())
    type_weights = list(profile.unit_type_distribution.values())
    type_assignments = rng.choice(unit_types, size=profile.count, p=type_weights)

    # Generate documentation flags
    has_docs = rng.random(profile.count) < profile.documentation_ratio

    code_units: list[GeneratedCodeUnit] = []
    for i in range(profile.count):
        language = str(language_assignments[i])
        unit_type = str(type_assignments[i])

        # Generate line count with log-normal distribution (more small files)
        min_lines, max_lines = profile.line_count_range
        line_count = int(
            np.clip(
                rng.lognormal(mean=4.0, sigma=1.0),  # Peak around 55 lines
                min_lines,
                max_lines,
            )
        )

        # Generate nested depth
        min_depth, max_depth = profile.nested_depth_range
        nested_depth = int(rng.integers(min_depth, max_depth + 1))

        # Generate name
        name = _generate_code_name(unit_type, rng)

        # Generate content from template
        content = _generate_code_content(
            language=language,
            unit_type=unit_type,
            name=name,
            line_count=line_count,
            has_docs=bool(has_docs[i]),
            rng=rng,
        )

        # Generate file path
        file_path = _generate_file_path(language, unit_type, name, nested_depth, rng)

        docstring = _generate_docstring(unit_type, rng) if has_docs[i] else None

        code_units.append(
            GeneratedCodeUnit(
                id=f"code_{uuid.uuid4().hex[:12]}",
                file_path=file_path,
                language=language,
                unit_type=unit_type,  # type: ignore[arg-type]
                name=name,
                content=content,
                line_count=line_count,
                docstring=docstring,
                nested_depth=nested_depth,
            )
        )

    return code_units


def _generate_code_name(unit_type: str, rng: np.random.Generator) -> str:
    """Generate a realistic code unit name."""
    prefixes: dict[str, list[str]] = {
        "function": [
            "get",
            "set",
            "create",
            "update",
            "delete",
            "validate",
            "process",
            "handle",
            "parse",
            "format",
        ],
        "class": ["", "Abstract", "Base", "Default", "Custom"],
        "method": ["get", "set", "is", "has", "can", "should", "update", "validate"],
        "module": [""],
    }
    nouns = [
        "user",
        "item",
        "data",
        "config",
        "result",
        "handler",
        "service",
        "manager",
        "factory",
        "builder",
    ]
    suffixes: dict[str, list[str]] = {
        "function": ["", "_async", "_sync", "_cached"],
        "class": [
            "Service",
            "Manager",
            "Handler",
            "Factory",
            "Builder",
            "Client",
            "Repository",
        ],
        "method": ["", "_value", "_all", "_by_id"],
        "module": ["utils", "helpers", "constants", "types", "models", "services"],
    }

    prefix = str(rng.choice(prefixes.get(unit_type, [""])))
    noun = str(rng.choice(nouns))
    suffix = str(rng.choice(suffixes.get(unit_type, [""])))

    if unit_type == "class":
        return f"{prefix}{noun.title()}{suffix}"
    elif unit_type == "module":
        return f"{noun}_{suffix}" if suffix else noun
    else:
        return f"{prefix}_{noun}{suffix}" if prefix else f"{noun}{suffix}"


def _generate_code_content(
    language: str,
    unit_type: str,
    name: str,
    line_count: int,
    has_docs: bool,
    rng: np.random.Generator,
) -> str:
    """Generate code content from templates."""
    template = CODE_TEMPLATES.get(language, CODE_TEMPLATES["python"]).get(
        unit_type, ""
    )

    # Generate template fills
    fills = _generate_code_fills(language, unit_type, name, has_docs, rng)

    content = template.format(**fills)

    # Adjust to target line count by adding/removing body lines
    current_lines = content.count("\n") + 1
    if current_lines < line_count:
        # Add padding comments/code
        padding = _generate_padding_lines(language, line_count - current_lines, rng)
        content = content.replace("{body}", f"{{body}}\n{padding}")
        # Replace any remaining {body} placeholder
        content = content.replace("{body}", fills.get("body", "pass"))

    return content


def _generate_code_fills(
    language: str,
    unit_type: str,
    name: str,
    has_docs: bool,
    rng: np.random.Generator,
) -> dict[str, str]:
    """Generate fills for code templates."""
    types_by_lang: dict[str, dict[str, str]] = {
        "python": {
            "str": "str",
            "int": "int",
            "bool": "bool",
            "list": "list",
            "dict": "dict",
            "None": "None",
        },
        "typescript": {
            "str": "string",
            "int": "number",
            "bool": "boolean",
            "list": "Array<any>",
            "dict": "Record<string, any>",
            "None": "void",
        },
        "go": {
            "str": "string",
            "int": "int",
            "bool": "bool",
            "list": "[]interface{}",
            "dict": "map[string]interface{}",
            "None": "",
        },
    }
    types = types_by_lang.get(language, types_by_lang["python"])

    return_type = str(rng.choice(list(types.values())))
    param_type = str(rng.choice(["str", "int", "bool"]))

    return {
        "name": name,
        "params": f"value: {types[param_type]}"
        if language == "python"
        else f"value: {types[param_type]}",
        "return_type": return_type,
        "return_value": "result" if return_type != types["None"] else "",
        "docstring": _generate_docstring(unit_type, rng)
        if has_docs
        else "Undocumented",
        "body": f"result = value  # Process {name}",
        "init_params": ", value: int = 0"
        if language == "python"
        else "value: number = 0",
        "init_body": "self.value = value"
        if language == "python"
        else "this.value = value;",
        "method_name": f"process_{name.lower()}" if unit_type == "class" else name,
        "method_params": "",
        "method_body": "pass" if language == "python" else "return;",
        "fields": "value: number;"
        if language == "typescript"
        else "Value int"
        if language == "go"
        else "",
        "imports": "",
        "constants": "",
        "struct_name": name.title(),
        "package_name": "main",
    }


def _generate_docstring(unit_type: str, rng: np.random.Generator) -> str:
    """Generate a realistic docstring."""
    templates = [
        f"Process and validate the input {unit_type}.",
        f"Handle the {unit_type} operation with error checking.",
        "Create a new instance with the given parameters.",
        "Transform the input data according to configuration.",
        f"Execute the main logic for this {unit_type}.",
    ]
    return str(rng.choice(templates))


def _generate_padding_lines(
    language: str, count: int, rng: np.random.Generator
) -> str:
    """Generate padding lines to reach target line count."""
    comment_char = "#" if language == "python" else "//"
    lines: list[str] = []
    for _ in range(count):
        lines.append(f"    {comment_char} Additional processing logic")
    return "\n".join(lines)


def _generate_file_path(
    language: str,
    unit_type: str,
    name: str,
    nested_depth: int,
    rng: np.random.Generator,
) -> str:
    """Generate a realistic file path."""
    extensions = {"python": ".py", "typescript": ".ts", "go": ".go"}
    ext = extensions.get(language, ".py")

    dirs = ["src", "lib", "pkg", "internal", "core", "utils", "services", "handlers"]
    subdirs = ["auth", "users", "items", "api", "storage", "cache", "config"]

    path_parts = [str(rng.choice(dirs))]
    for _ in range(nested_depth - 1):
        path_parts.append(str(rng.choice(subdirs)))

    filename = f"{name.lower()}{ext}"
    return "/".join(path_parts) + "/" + filename
