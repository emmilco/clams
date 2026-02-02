"""Skill loader for CALM.

This module provides utilities for loading and rendering skill templates,
particularly the /orchestrate skill which requires dynamic task list injection.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from calm.config import settings

if TYPE_CHECKING:
    pass


@dataclass
class TaskInfo:
    """Minimal task info for skill display."""

    id: str
    phase: str
    title: str
    blocked_by: list[str]


def get_tasks_for_project(
    project_path: str,
    db_path: Path | None = None,
) -> list[TaskInfo]:
    """Get tasks for a project from the database.

    Args:
        project_path: Project directory path
        db_path: Optional database path (defaults to settings.db_path)

    Returns:
        List of TaskInfo objects
    """
    effective_db_path = db_path or settings.db_path

    if not effective_db_path.exists():
        return []

    try:
        conn = sqlite3.connect(effective_db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, phase, title, blocked_by
            FROM tasks
            WHERE project_path = ? AND phase != 'DONE'
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (project_path,),
        )
        rows = cursor.fetchall()
        conn.close()

        tasks = []
        for row in rows:
            blocked_by_str = row["blocked_by"]
            blocked_by: list[str] = []
            if blocked_by_str:
                import json

                try:
                    blocked_by = json.loads(blocked_by_str)
                except json.JSONDecodeError:
                    pass

            tasks.append(
                TaskInfo(
                    id=row["id"],
                    phase=row["phase"],
                    title=row["title"],
                    blocked_by=blocked_by,
                )
            )
        return tasks
    except (sqlite3.Error, OSError):
        return []


def format_task_table(tasks: list[TaskInfo]) -> str:
    """Format tasks as a markdown table.

    Args:
        tasks: List of TaskInfo objects

    Returns:
        Markdown table string
    """
    if not tasks:
        return "No active tasks for this project."

    lines = [
        "| ID | Phase | Title | Blocked By |",
        "|----|-------|-------|------------|",
    ]

    for task in tasks[:20]:  # Limit to 20 tasks
        blocked = ", ".join(task.blocked_by) if task.blocked_by else "-"
        title = task.title[:40]
        if len(task.title) > 40:
            title += "..."
        lines.append(f"| {task.id} | {task.phase} | {title} | {blocked} |")

    if len(tasks) > 20:
        lines.append(f"\n_...and {len(tasks) - 20} more tasks_")

    return "\n".join(lines)


def load_orchestrate_skill(
    project_path: str,
    db_path: Path | None = None,
) -> str:
    """Load and render the orchestrate skill.

    Args:
        project_path: Current project directory
        db_path: Optional database path (defaults to settings.db_path)

    Returns:
        Rendered skill content

    Raises:
        FileNotFoundError: If skill or workflow file missing
    """
    skill_path = settings.skills_dir / "orchestrate.md"
    workflow_path = settings.workflows_dir / "default.md"

    if not skill_path.exists():
        raise FileNotFoundError(
            f"Skill file not found at {skill_path}. Run `calm init` to set up."
        )

    if not workflow_path.exists():
        raise FileNotFoundError(f"Workflow file not found at {workflow_path}")

    # Load templates
    skill_template = skill_path.read_text()
    workflow_content = workflow_path.read_text()

    # Get tasks
    effective_db_path = db_path or settings.db_path
    tasks = get_tasks_for_project(project_path, effective_db_path)
    task_table = format_task_table(tasks)

    # Substitute placeholders
    content = skill_template.replace("{{WORKFLOW_CONTENT}}", workflow_content)
    content = content.replace("{{TASK_LIST}}", task_table)

    return content


def load_skill(
    skill_name: str,
    project_path: str,
    db_path: Path | None = None,
) -> str:
    """Load and render a skill by name.

    Args:
        skill_name: Name of the skill (e.g., "orchestrate")
        project_path: Current project directory
        db_path: Optional database path

    Returns:
        Rendered skill content

    Raises:
        FileNotFoundError: If skill file not found
        ValueError: If skill name is unknown
    """
    if skill_name == "orchestrate":
        return load_orchestrate_skill(project_path, db_path)

    # For other skills, just load the file directly
    skill_path = settings.skills_dir / f"{skill_name}.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill file not found at {skill_path}")

    return skill_path.read_text()
