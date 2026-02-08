"""Markdown formatting logic for context items."""

from typing import Any

from .models import ContextItem


def format_memory(metadata: dict[str, Any]) -> str:
    content = metadata["content"]
    category = metadata["category"]
    importance = metadata.get("importance", 0.0)

    return (
        f"**Memory**: {content}\n"
        f"*Category: {category}, Importance: {importance:.2f}*"
    )


def format_code(metadata: dict[str, Any]) -> str:
    unit_type = metadata["unit_type"].capitalize()
    name = metadata["qualified_name"]
    file_path = metadata["file_path"]
    line_start = metadata.get("line_start") or metadata.get("start_line", 0)
    language = metadata.get("language", "python")
    code = metadata.get("code", "")
    docstring = metadata.get("docstring")

    result = f"**{unit_type}** `{name}` in `{file_path}:{line_start}`\n"
    result += f"```{language}\n{code}\n"
    if docstring:
        result += f'"""{docstring}"""\n'
    result += "```"

    return result


def format_experience(metadata: dict[str, Any]) -> str:
    domain = metadata["domain"]
    strategy = metadata["strategy"]
    goal = metadata["goal"]
    hypothesis = metadata["hypothesis"]
    action = metadata["action"]
    prediction = metadata["prediction"]
    outcome_status = metadata["outcome_status"]
    outcome_result = metadata["outcome_result"]
    surprise = metadata.get("surprise")
    lesson = metadata.get("lesson")

    result = f"**Experience**: {domain} | {strategy}\n"
    result += f"- **Goal**: {goal}\n"
    result += f"- **Hypothesis**: {hypothesis}\n"
    result += f"- **Action**: {action}\n"
    result += f"- **Prediction**: {prediction}\n"
    result += f"- **Outcome**: {outcome_status} - {outcome_result}\n"

    if surprise:
        result += f"- **Surprise**: {surprise}\n"

    if lesson:
        if hasattr(lesson, "what_worked"):
            what_worked = lesson.what_worked
        elif isinstance(lesson, dict):
            what_worked = lesson.get("what_worked", "")
        else:
            what_worked = str(lesson)
        result += f"- **Lesson**: {what_worked}\n"

    return result


def format_value(metadata: dict[str, Any]) -> str:
    axis = metadata["axis"]
    member_count = metadata.get("member_count") or metadata.get("cluster_size", 0)
    text = metadata["text"]

    return f"**Value** ({axis}, cluster size: {member_count}):\n{text}"


def format_commit(metadata: dict[str, Any]) -> str:
    sha = metadata["sha"][:7]
    author = metadata["author"]
    timestamp = metadata.get("committed_at", "unknown")
    message = metadata["message"]
    files = metadata.get("files_changed", [])

    result = f"**Commit** `{sha}` by {author} on {timestamp}\n"
    result += f"{message}\n"

    if files:
        file_list = ", ".join(files[:3])
        if len(files) > 3:
            file_list += f", ... ({len(files) - 3} more)"
        result += f"*Files: {file_list}*"

    return result


def assemble_markdown(
    items_by_source: dict[str, list[ContextItem]],
    premortem: bool = False,
    domain: str | None = None,
    strategy: str | None = None,
) -> str:
    if premortem:
        return _assemble_premortem_markdown(items_by_source, domain, strategy)
    else:
        return _assemble_standard_markdown(items_by_source)


def _assemble_standard_markdown(
    items_by_source: dict[str, list[ContextItem]],
) -> str:
    sections = ["# Context\n"]

    source_titles = {
        "memories": "Memories",
        "code": "Code",
        "experiences": "Experiences",
        "values": "Values",
        "commits": "Commits",
    }

    total_items = 0
    sources_count = 0

    for source, items in items_by_source.items():
        if not items:
            continue

        title = source_titles.get(source, source.capitalize())
        sections.append(f"\n## {title}\n")

        for item in items:
            sections.append(f"\n{item.content}\n")
            total_items += 1

        sources_count += 1

    sections.append(f"\n---\n*{total_items} items from {sources_count} sources*")

    return "\n".join(sections)


def _assemble_premortem_markdown(
    items_by_source: dict[str, list[ContextItem]],
    domain: str | None,
    strategy: str | None,
) -> str:
    header = f"# Premortem: {domain or 'Unknown Domain'}"
    if strategy:
        header += f" with {strategy}"

    sections = [header + "\n"]

    section_mapping = {
        "full": "Common Failures",
        "strategy": "Strategy Performance",
        "surprise": "Unexpected Outcomes",
        "root_cause": "Root Causes to Watch",
    }

    exp_items = items_by_source.get("experiences", [])
    experience_count = 0

    for axis, title in section_mapping.items():
        axis_items = [
            item for item in exp_items if item.metadata.get("axis") == axis
        ]

        if axis_items:
            sections.append(f"\n## {title}\n")
            for item in axis_items:
                sections.append(f"\n{item.content}\n")
                experience_count += 1

    value_items = items_by_source.get("values", [])
    if value_items:
        sections.append("\n## Relevant Principles\n")
        for item in value_items:
            sections.append(f"\n{item.content}\n")

    sections.append(f"\n---\n*Based on {experience_count} past experiences*")

    return "\n".join(sections)
