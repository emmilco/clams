"""UserPromptSubmit hook for CALM.

Injects relevant context from memories and past experiences based on user prompt.

Input (stdin): {"prompt": "user's question"}
Output (stdout): Plain text context (max 1200 chars), or empty if no relevant context
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from calm.hooks.common import (
    get_db_path,
    read_json_input,
    truncate_output,
    write_output,
)

MAX_OUTPUT_CHARS = 1200
MAX_PROMPT_CHARS = 50000
MAX_MEMORIES = 5
MAX_EXPERIENCES = 3


def get_relevant_memories(db_path: Path, prompt: str) -> list[dict[str, Any]]:
    """Get memories potentially relevant to the prompt.

    Uses simple importance-based filtering (semantic search requires server).

    Args:
        db_path: Path to database
        prompt: User's prompt text

    Returns:
        List of memory dicts with content and category
    """
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get recent, high-importance memories
        # (Full semantic search would require embeddings/server)
        cursor.execute(
            """
            SELECT content, category
            FROM memories
            WHERE importance >= 0.5
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
            """,
            (MAX_MEMORIES,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {"content": row["content"], "category": row["category"]}
            for row in rows
        ]
    except (sqlite3.Error, OSError):
        return []


def get_relevant_experiences(
    db_path: Path,
    prompt: str,
) -> list[dict[str, Any]]:
    """Get GHAP experiences potentially relevant to the prompt.

    Uses recency-based filtering (semantic search requires server).

    Args:
        db_path: Path to database
        prompt: User's prompt text

    Returns:
        List of experience dicts with goal, outcome, domain
    """
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get recent confirmed/falsified experiences
        cursor.execute(
            """
            SELECT goal, hypothesis, status, domain
            FROM ghap_entries
            WHERE status IN ('confirmed', 'falsified')
            ORDER BY resolved_at DESC
            LIMIT ?
            """,
            (MAX_EXPERIENCES,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "goal": row["goal"],
                "hypothesis": row["hypothesis"],
                "outcome": row["status"],
                "domain": row["domain"],
            }
            for row in rows
        ]
    except (sqlite3.Error, OSError):
        return []


def format_context(
    memories: list[dict[str, Any]],
    experiences: list[dict[str, Any]],
) -> str:
    """Format memories and experiences as markdown context.

    Args:
        memories: List of memory dicts
        experiences: List of experience dicts

    Returns:
        Formatted markdown string (empty if no context)
    """
    if not memories and not experiences:
        return ""

    sections: list[str] = []
    sections.append("## Relevant Context from Past Sessions")
    sections.append("")

    if memories:
        sections.append("### Memories")
        for m in memories:
            category = m["category"]
            content = m["content"][:100]
            if len(m["content"]) > 100:
                content += "..."
            sections.append(f"- [{category}] {content}")
        sections.append("")

    if experiences:
        sections.append("### Past Experiences")
        for e in experiences:
            outcome = e["outcome"]
            goal = e["goal"][:60]
            if len(e["goal"]) > 60:
                goal += "..."
            sections.append(f"- Similar {e['domain']}: \"{goal}\" ({outcome})")

    return "\n".join(sections)


def main() -> None:
    """Main entry point for UserPromptSubmit hook."""
    # Read input
    input_data = read_json_input()
    prompt = input_data.get("prompt", "")

    # Validate/truncate prompt
    if not prompt or not prompt.strip():
        write_output("")
        return

    prompt = prompt[:MAX_PROMPT_CHARS]

    # Check database
    db_path = get_db_path()
    if not db_path.exists():
        write_output("")
        return

    # Get context (fail silently on errors)
    try:
        memories = get_relevant_memories(db_path, prompt)
        experiences = get_relevant_experiences(db_path, prompt)
    except Exception:
        write_output("")
        return

    # Format and write output
    output = format_context(memories, experiences)
    output = truncate_output(output, MAX_OUTPUT_CHARS)
    write_output(output)


if __name__ == "__main__":
    main()
