# SPEC-058-04: Technical Proposal

## Overview

This proposal details the implementation of session journaling and the learning reflection loop for CALM. The implementation adds:

1. **Session Journal MCP Tools** - Four new tools for storing, listing, querying, and marking journal entries as reflected
2. **`/wrapup` Skill** - A skill file that guides Claude through session summarization and journal entry creation
3. **`/reflection` Skill** - A skill that orchestrates multi-agent analysis of unreflected sessions
4. **CLI Commands** - Commands for `calm session journal list` and `calm session journal show`

The implementation follows existing CALM patterns: MCP tools are defined in `src/calm/tools/`, CLI commands use Click in `src/calm/cli/`, and database operations use the connection helpers from `src/calm/db/`.

**Note on Skills**: The skill files (`~/.calm/skills/wrapup.md` and `~/.calm/skills/reflection.md`) are markdown documents that Claude Code loads natively when users invoke `/wrapup` or `/reflection`. Claude Code's skill loading mechanism reads skill files from `~/.calm/skills/` based on trigger patterns defined in YAML frontmatter. No custom code is needed to load skills - only the skill file content needs to be created.

## File Structure

### New Files

```
src/calm/
  tools/
    journal.py          # Session journal MCP tool implementations
  orchestration/
    journal.py          # Business logic for journal operations (shared by CLI and tools)
~/.calm/
  skills/
    wrapup.md           # /wrapup skill instructions
    reflection.md       # /reflection skill instructions
```

### Modified Files

```
src/calm/
  tools/__init__.py     # Export get_journal_tools
  server/app.py         # Register journal tools and add tool definitions
  cli/session.py        # Add 'journal' subgroup with list/show commands
  config.py             # sessions_dir property already exists (verified)
```

## Implementation Details

### MCP Tools

All journal tools will be implemented in `src/calm/tools/journal.py` following the established pattern from `memory.py` and `session.py`.

#### 1. `store_journal_entry`

```python
async def store_journal_entry(
    summary: str,
    working_directory: str,
    friction_points: list[str] | None = None,
    next_steps: list[str] | None = None,
    session_log_content: str | None = None,
) -> dict[str, Any]:
    """Store a new session journal entry with optional log capture."""
```

**Implementation:**
1. Generate UUID for entry ID
2. Extract `project_name` from last path component of `working_directory`
3. If `session_log_content` provided:
   - Create `~/.calm/sessions/` directory if needed
   - Generate filename: `{timestamp}_{uuid}.jsonl`
   - Write log content to file
   - Store path in `session_log_path`
4. Insert record into `session_journal` table using `calm.db.connection.get_connection`
5. Return `{"id": entry_id, "session_log_path": path_or_none}`

**Validation:**
- `summary` must be non-empty, max 10,000 characters
- `working_directory` must be non-empty
- `friction_points` and `next_steps` limited to 50 items each

#### 2. `list_journal_entries`

```python
async def list_journal_entries(
    unreflected_only: bool = False,
    project_name: str | None = None,
    working_directory: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List session journal entries with optional filters."""
```

**Implementation:**
1. Build SQL query with optional WHERE clauses:
   - `reflected_at IS NULL` if `unreflected_only`
   - `project_name = ?` if provided
   - `working_directory = ?` if provided
2. Order by `created_at DESC`, limit results
3. Return list of entry metadata (id, created_at, working_directory, project_name, summary, reflected_at)

**Validation:**
- `limit` must be 1-200

#### 3. `get_journal_entry`

```python
async def get_journal_entry(
    entry_id: str,
    include_log: bool = False,
) -> dict[str, Any]:
    """Get full details of a journal entry."""
```

**Implementation:**
1. Query `session_journal` by ID
2. If `include_log=True` and `session_log_path` exists:
   - Read file contents
   - Add `session_log` field to response
3. Parse JSON fields (`friction_points`, `next_steps`) before returning
4. Return full entry fields

**Validation:**
- `entry_id` must be valid UUID format

#### 4. `mark_entries_reflected`

```python
async def mark_entries_reflected(
    entry_ids: list[str],
    memories_created: int | None = None,
    delete_logs: bool = True,
) -> dict[str, Any]:
    """Mark entries as reflected and optionally delete their logs."""
```

**Implementation:**
1. Begin transaction
2. For each entry_id:
   - Update `reflected_at` to current timestamp
   - If `memories_created` provided, set `memories_created` field
   - If `delete_logs=True`, get `session_log_path` and delete file if exists
3. Commit transaction
4. Return `{"marked_count": N, "logs_deleted": M}`

**Validation:**
- `entry_ids` must be non-empty list of valid UUIDs
- `memories_created` must be >= 0 if provided

### Tool Registration in `server/app.py`

Add to `_get_all_tool_definitions()`:

```python
# === Session Journal Tools ===
Tool(
    name="store_journal_entry",
    description="Store a new session journal entry with optional log capture.",
    inputSchema={
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Session summary text (required)",
            },
            "working_directory": {
                "type": "string",
                "description": "The working directory of the session (required)",
            },
            "friction_points": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of friction points encountered",
            },
            "next_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Recommended next steps",
            },
            "session_log_content": {
                "type": "string",
                "description": "Raw session log content to store",
            },
        },
        "required": ["summary", "working_directory"],
    },
),
Tool(
    name="list_journal_entries",
    description="List session journal entries with optional filters.",
    inputSchema={
        "type": "object",
        "properties": {
            "unreflected_only": {
                "type": "boolean",
                "description": "Only return entries where reflected_at is NULL",
                "default": False,
            },
            "project_name": {
                "type": "string",
                "description": "Filter by project name",
            },
            "working_directory": {
                "type": "string",
                "description": "Filter by exact working directory",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum entries to return (default 50)",
                "default": 50,
            },
        },
        "required": [],
    },
),
Tool(
    name="get_journal_entry",
    description="Get full details of a journal entry.",
    inputSchema={
        "type": "object",
        "properties": {
            "entry_id": {
                "type": "string",
                "description": "The entry ID",
            },
            "include_log": {
                "type": "boolean",
                "description": "Include the full session log content",
                "default": False,
            },
        },
        "required": ["entry_id"],
    },
),
Tool(
    name="mark_entries_reflected",
    description="Mark entries as reflected and optionally delete their logs.",
    inputSchema={
        "type": "object",
        "properties": {
            "entry_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of entry IDs to mark",
            },
            "memories_created": {
                "type": "integer",
                "description": "Number of memories created from this batch",
            },
            "delete_logs": {
                "type": "boolean",
                "description": "Delete session log files after marking",
                "default": True,
            },
        },
        "required": ["entry_ids"],
    },
),
```

Update `create_server()` to register journal tools:

```python
from calm.tools.journal import get_journal_tools

# Journal tools
tool_registry.update(get_journal_tools())
```

### Skills

Skills are markdown files in `~/.calm/skills/` that Claude Code loads when triggered. They provide instructions for complex multi-step workflows.

#### `/wrapup` Skill (`~/.calm/skills/wrapup.md`)

```markdown
---
name: wrapup
triggers:
  - /wrapup
  - /wrapup continue
description: Wrap up the current session with summary and journal entry
---

# Session Wrapup

You are wrapping up a coding session. Follow these steps:

## 1. Analyze the Conversation

Review the conversation and identify:
- **Summary**: A concise 2-3 sentence summary of what was accomplished
- **Friction Points**: Problems, blockers, or unexpected issues encountered
- **Next Steps**: What should happen in the next session

## 2. Locate the Session Log

Claude stores session logs at `~/.claude/projects/<mapped-path>/` where the path
maps the working directory by replacing `/` with `-` and prefixing with `-`.

Example: `/Users/foo/project` -> `-Users-foo-project`

Find the most recent `.jsonl` file in that directory:

```bash
# Map the path
mapped_path="-${PWD//\//-}"
log_dir="$HOME/.claude/projects/$mapped_path"

# Find most recent log
ls -t "$log_dir"/*.jsonl 2>/dev/null | head -1
```

Read the log file content.

## 3. Store the Journal Entry

Call the `store_journal_entry` MCP tool with:
- `summary`: Your session summary
- `working_directory`: The current $PWD
- `friction_points`: List of friction points (or empty list)
- `next_steps`: List of next steps (or empty list)
- `session_log_content`: The log file contents

## 4. Report to the User

Format your response as:

```
## Session Wrapped Up

**Summary**: [Your summary text]

**Friction Points**:
- [Point 1]
- [Point 2]

**Next Steps**:
- [Step 1]
- [Step 2]

Journal entry saved: [entry_id]
```

## Variant: `/wrapup continue`

If the user ran `/wrapup continue`, include a note that continuation is expected
and ensure `next_steps` is populated with actionable items for the next session.
```

#### `/reflection` Skill (`~/.calm/skills/reflection.md`)

```markdown
---
name: reflection
triggers:
  - /reflection
description: Process unreflected sessions to extract memories
---

# Reflection Process

You are running the reflection process to extract memories from past sessions.

## 1. Load Unreflected Entries

Call `list_journal_entries` with `unreflected_only=true`:

```
list_journal_entries(unreflected_only=true, limit=10)
```

If no entries are found, report: "No unreflected sessions to process."

## 2. Load Session Details

For each entry (up to batch size of 10), call:

```
get_journal_entry(entry_id=<id>, include_log=true)
```

Collect the summary, friction_points, and session_log for analysis.

## 3. Dispatch Analysis Agents

Launch 4 analysis agents in parallel using the Task tool. Each agent analyzes
the session data with a specialized focus.

### Agent 1: Debugging Analyst

Focus: Root causes, misleading symptoms, what fixed things
Categories: "error", "decision"

Prompt:
```
You are analyzing coding session logs to extract debugging insights.

Focus on:
- What was the root cause of problems encountered?
- What symptoms were misleading or red herrings?
- What approaches worked vs. didn't work?
- What would help diagnose similar issues faster?

CRITICAL: Extract STABLE insights, not brittle specifics.
- BAD: "The bug was on line 234 of user.py"
- GOOD: "Async context managers must be awaited even in decorator usage"

For each insight, return JSON:
{"content": "...", "category": "error", "importance": 0.7, "reasoning": "..."}

Session data:
<session_summary>
{summary}
</session_summary>
<friction_points>
{friction_points}
</friction_points>
<session_log>
{session_log}
</session_log>
```

### Agent 2: Codebase Cartographer

Focus: Stable architectural knowledge, patterns, conventions
Categories: "fact"

Prompt:
```
You are analyzing coding session logs to extract codebase knowledge.

Focus on:
- How do major systems/components work?
- What are the architectural patterns in use?
- What conventions does the codebase follow?

CRITICAL: Extract STABLE abstractions only.
- BAD: "Config is in src/config.py with 5 settings"
- GOOD: "Configuration uses pydantic-settings; env vars override defaults"

For each insight, return JSON:
{"content": "...", "category": "fact", "importance": 0.7, "reasoning": "..."}

Session data:
<session_summary>
{summary}
</session_summary>
<friction_points>
{friction_points}
</friction_points>
<session_log>
{session_log}
</session_log>
```

### Agent 3: Process Observer

Focus: Workflow patterns, efficiency insights
Categories: "workflow", "preference"

Prompt:
```
You are analyzing coding session logs to extract workflow insights.

Focus on:
- What workflows or processes were efficient?
- What caused friction or wasted time?
- What tool usage patterns were effective?

For each insight, return JSON:
{"content": "...", "category": "workflow", "importance": 0.7, "reasoning": "..."}

Session data:
<session_summary>
{summary}
</session_summary>
<friction_points>
{friction_points}
</friction_points>
<session_log>
{session_log}
</session_log>
```

### Agent 4: Pattern Detector

Focus: Recurring themes, anti-patterns to avoid
Categories: "decision", "fact"

Prompt:
```
You are analyzing coding session logs to detect patterns and anti-patterns.

Focus on:
- What themes or issues recur?
- What mistakes should be avoided?
- What approaches consistently work well?

CRITICAL: Look for GENERALIZABLE patterns.
- BAD: "Don't forget to update the config file"
- GOOD: "After adding settings, verify they load by checking startup logs"

For each insight, return JSON:
{"content": "...", "category": "decision", "importance": 0.7, "reasoning": "..."}

Session data:
<session_summary>
{summary}
</session_summary>
<friction_points>
{friction_points}
</friction_points>
<session_log>
{session_log}
</session_log>
```

## 4. Collect and Deduplicate Proposals

After all agents complete, gather their proposed memories.

Use semantic similarity via `retrieve_memories` to detect duplicates:
- For each proposal, search existing memories with similar content
- If similarity > 0.85, consider it a duplicate and merge
- Keep the proposal with highest importance

## 5. Present Batch Approval UI

Present the deduplicated proposals to the user for approval:

```
## Proposed Memories from N Sessions

### Debugging Insights (X)
[x] 1. [error] When async tests hang, check for missing `await`...
    Source: Session 2026-02-01 (project-name)

### Codebase Knowledge (Y)
[x] 2. [fact] MCP tools are registered via a dispatcher pattern...
    Source: Session 2026-02-01 (project-name)

### Workflow Patterns (Z)
[ ] 3. [workflow] Run type checker before tests...
    Source: Session 2026-01-30 (project-name)

---
Enter numbers to toggle selection (e.g., "1 3 5"), 'all' to select all,
'none' to deselect all, or 'done' to proceed:
```

Wait for user input to toggle selections.

## 6. Store Approved Memories

For each approved proposal, call `store_memory`:

```
store_memory(
    content="<memory content>",
    category="<category>",
    importance=<importance>
)
```

Track the count of memories created.

## 7. Mark Entries Reflected

Call `mark_entries_reflected` with the processed entry IDs:

```
mark_entries_reflected(
    entry_ids=[...],
    memories_created=<count>,
    delete_logs=true
)
```

## 8. Report Results

```
## Reflection Complete

Sessions processed: N
Memories created: M
Session logs deleted: N

New memories:
- [category] memory content...
- [category] memory content...
```
```

### CLI Commands

Extend `src/calm/cli/session.py` with a `journal` subgroup to avoid conflict with existing `list` and `show` commands that handle orchestration handoffs.

**Existing Commands** (for orchestration handoffs):
- `calm session save` - Save handoff from stdin
- `calm session list` - List recent sessions (handoffs)
- `calm session show <id>` - Show a session's handoff content
- `calm session pending` - Show pending handoff
- `calm session resume <id>` - Mark a session as resumed
- `calm session next-commands` - Generate next commands for active tasks

**New Commands** (for journal entries, under `journal` subgroup):
- `calm session journal list` - List journal entries
- `calm session journal show <id>` - Show a journal entry

#### `calm session journal list`

```python
@session.group()
def journal() -> None:
    """Session journal management commands."""
    pass


@journal.command("list")
@click.option("--unreflected", is_flag=True, help="Only show unreflected entries")
@click.option("--project", "project_name", help="Filter by project name")
@click.option("--limit", default=20, help="Maximum entries (default: 20)")
def list_journal(unreflected: bool, project_name: str | None, limit: int) -> None:
    """List session journal entries."""
    from calm.orchestration.journal import list_journal_entries

    entries = list_journal_entries(
        unreflected_only=unreflected,
        project_name=project_name,
        limit=limit,
    )

    if not entries:
        click.echo("No journal entries found.")
        return

    # Table header
    click.echo(f"{'ID':<36}  {'Created':<19}  {'Project':<15}  {'Summary'}")
    click.echo("-" * 100)

    for entry in entries:
        created = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
        project = entry.project_name or "(none)"
        summary = (entry.summary[:40] + "...") if len(entry.summary) > 43 else entry.summary
        reflected = "" if entry.reflected_at else " [unreflected]"
        click.echo(f"{entry.id:<36}  {created:<19}  {project:<15}  {summary}{reflected}")
```

#### `calm session journal show`

```python
@journal.command("show")
@click.argument("entry_id")
@click.option("--log", is_flag=True, help="Include session log content")
def show_journal(entry_id: str, log: bool) -> None:
    """Show full details of a journal entry."""
    from calm.orchestration.journal import get_journal_entry

    entry = get_journal_entry(entry_id, include_log=log)

    if not entry:
        raise click.ClickException(f"Entry {entry_id} not found")

    click.echo(f"ID: {entry.id}")
    click.echo(f"Created: {entry.created_at}")
    click.echo(f"Project: {entry.project_name or '(none)'}")
    click.echo(f"Working Directory: {entry.working_directory}")
    click.echo(f"Reflected: {entry.reflected_at or 'No'}")
    click.echo(f"Memories Created: {entry.memories_created}")
    click.echo("")
    click.echo("--- Summary ---")
    click.echo(entry.summary)

    if entry.friction_points:
        click.echo("")
        click.echo("--- Friction Points ---")
        for point in entry.friction_points:
            click.echo(f"- {point}")

    if entry.next_steps:
        click.echo("")
        click.echo("--- Next Steps ---")
        for step in entry.next_steps:
            click.echo(f"- {step}")

    if log and entry.session_log:
        click.echo("")
        click.echo("--- Session Log ---")
        click.echo(entry.session_log)
```

### Business Logic Module

Create `src/calm/orchestration/journal.py` for shared business logic used by both MCP tools and CLI:

```python
"""Session journal operations for CALM.

This module handles storing, listing, and managing session journal entries.
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from calm.config import settings
from calm.db.connection import get_connection


@dataclass
class JournalEntry:
    """Represents a session journal entry."""
    id: str
    created_at: datetime
    working_directory: str
    project_name: str | None
    session_log_path: str | None
    summary: str
    friction_points: list[str]
    next_steps: list[str]
    reflected_at: datetime | None
    memories_created: int
    session_log: str | None = None  # Only populated when include_log=True


def store_journal_entry(
    summary: str,
    working_directory: str,
    friction_points: list[str] | None = None,
    next_steps: list[str] | None = None,
    session_log_content: str | None = None,
    db_path: Path | None = None,
) -> tuple[str, str | None]:
    """Store a new session journal entry.

    Returns:
        Tuple of (entry_id, session_log_path or None)
    """
    entry_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    project_name = Path(working_directory).name
    session_log_path = None

    # Save session log if provided
    if session_log_content:
        sessions_dir = settings.sessions_dir
        sessions_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        log_filename = f"{timestamp}_{entry_id}.jsonl"
        log_path = sessions_dir / log_filename
        log_path.write_text(session_log_content)
        session_log_path = str(log_path)

    # Store in database
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO session_journal
            (id, created_at, working_directory, project_name, session_log_path,
             summary, friction_points, next_steps)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                now,
                working_directory,
                project_name,
                session_log_path,
                summary,
                json.dumps(friction_points or []),
                json.dumps(next_steps or []),
            ),
        )
        conn.commit()

    return entry_id, session_log_path


def list_journal_entries(
    unreflected_only: bool = False,
    project_name: str | None = None,
    working_directory: str | None = None,
    limit: int = 50,
    db_path: Path | None = None,
) -> list[JournalEntry]:
    """List session journal entries with optional filters."""
    query = "SELECT * FROM session_journal WHERE 1=1"
    params: list[Any] = []

    if unreflected_only:
        query += " AND reflected_at IS NULL"
    if project_name:
        query += " AND project_name = ?"
        params.append(project_name)
    if working_directory:
        query += " AND working_directory = ?"
        params.append(working_directory)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [_row_to_entry(row) for row in cursor.fetchall()]


def get_journal_entry(
    entry_id: str,
    include_log: bool = False,
    db_path: Path | None = None,
) -> JournalEntry | None:
    """Get a journal entry by ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM session_journal WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        if not row:
            return None

        entry = _row_to_entry(row)

        if include_log and entry.session_log_path:
            log_path = Path(entry.session_log_path)
            if log_path.exists():
                entry.session_log = log_path.read_text()

        return entry


def mark_entries_reflected(
    entry_ids: list[str],
    memories_created: int | None = None,
    delete_logs: bool = True,
    db_path: Path | None = None,
) -> tuple[int, int]:
    """Mark entries as reflected.

    Returns:
        Tuple of (marked_count, logs_deleted)
    """
    now = datetime.now(UTC).isoformat()
    marked_count = 0
    logs_deleted = 0

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        for entry_id in entry_ids:
            # Get current entry for log path
            cursor.execute(
                "SELECT session_log_path FROM session_journal WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()
            if not row:
                continue

            # Update entry
            if memories_created is not None:
                cursor.execute(
                    """
                    UPDATE session_journal
                    SET reflected_at = ?, memories_created = ?
                    WHERE id = ?
                    """,
                    (now, memories_created, entry_id),
                )
            else:
                cursor.execute(
                    "UPDATE session_journal SET reflected_at = ? WHERE id = ?",
                    (now, entry_id),
                )

            if cursor.rowcount > 0:
                marked_count += 1

            # Delete log file if requested
            if delete_logs and row["session_log_path"]:
                log_path = Path(row["session_log_path"])
                if log_path.exists():
                    log_path.unlink()
                    logs_deleted += 1

        conn.commit()

    return marked_count, logs_deleted


def _row_to_entry(row: sqlite3.Row) -> JournalEntry:
    """Convert database row to JournalEntry."""
    return JournalEntry(
        id=row["id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        working_directory=row["working_directory"],
        project_name=row["project_name"],
        session_log_path=row["session_log_path"],
        summary=row["summary"],
        friction_points=json.loads(row["friction_points"] or "[]"),
        next_steps=json.loads(row["next_steps"] or "[]"),
        reflected_at=(
            datetime.fromisoformat(row["reflected_at"])
            if row["reflected_at"]
            else None
        ),
        memories_created=row["memories_created"] or 0,
    )
```

### MCP Tool Entry Point

Create `src/calm/tools/journal.py` with the `get_journal_tools()` function that returns the tool implementations for the MCP dispatcher. This follows the pattern established in `src/calm/tools/memory.py`:

```python
"""Session journal tools for MCP server."""

from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import structlog

from calm.orchestration.journal import (
    JournalEntry,
    get_journal_entry as _get_journal_entry,
    list_journal_entries as _list_journal_entries,
    mark_entries_reflected as _mark_entries_reflected,
    store_journal_entry as _store_journal_entry,
)

from .errors import MCPError
from .validation import ValidationError, validate_uuid

logger = structlog.get_logger()

# Type alias for tool functions
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


def get_journal_tools(
    db_path: Path | None = None,
) -> dict[str, ToolFunc]:
    """Get journal tool implementations for the dispatcher.

    Args:
        db_path: Optional database path (for testing)

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def store_journal_entry(
        summary: str,
        working_directory: str,
        friction_points: list[str] | None = None,
        next_steps: list[str] | None = None,
        session_log_content: str | None = None,
    ) -> dict[str, Any]:
        """Store a new session journal entry with optional log capture."""
        logger.info("journal.store", working_directory=working_directory)

        # Validate inputs
        if not summary or not summary.strip():
            raise ValidationError("Summary is required and cannot be empty")
        if len(summary) > 10000:
            raise ValidationError(f"Summary too long ({len(summary)} chars). Maximum is 10000.")
        if not working_directory or not working_directory.strip():
            raise ValidationError("Working directory is required")
        if friction_points and len(friction_points) > 50:
            raise ValidationError("Maximum 50 friction points allowed")
        if next_steps and len(next_steps) > 50:
            raise ValidationError("Maximum 50 next steps allowed")

        try:
            entry_id, session_log_path = _store_journal_entry(
                summary=summary,
                working_directory=working_directory,
                friction_points=friction_points,
                next_steps=next_steps,
                session_log_content=session_log_content,
                db_path=db_path,
            )

            logger.info("journal.stored", entry_id=entry_id)

            return {
                "id": entry_id,
                "session_log_path": session_log_path,
            }

        except Exception as e:
            logger.error("journal.store_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to store journal entry: {e}") from e

    async def list_journal_entries(
        unreflected_only: bool = False,
        project_name: str | None = None,
        working_directory: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List session journal entries with optional filters."""
        logger.info("journal.list", unreflected_only=unreflected_only, limit=limit)

        # Validate limit
        if not 1 <= limit <= 200:
            raise ValidationError(f"Limit {limit} out of range. Must be between 1 and 200.")

        try:
            entries = _list_journal_entries(
                unreflected_only=unreflected_only,
                project_name=project_name,
                working_directory=working_directory,
                limit=limit,
                db_path=db_path,
            )

            formatted = [
                {
                    "id": e.id,
                    "created_at": e.created_at.isoformat(),
                    "working_directory": e.working_directory,
                    "project_name": e.project_name,
                    "summary": e.summary,
                    "reflected_at": e.reflected_at.isoformat() if e.reflected_at else None,
                }
                for e in entries
            ]

            logger.info("journal.listed", count=len(formatted))

            return {"entries": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("journal.list_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to list journal entries: {e}") from e

    async def get_journal_entry(
        entry_id: str,
        include_log: bool = False,
    ) -> dict[str, Any]:
        """Get full details of a journal entry."""
        logger.info("journal.get", entry_id=entry_id, include_log=include_log)

        # Validate UUID format
        validate_uuid(entry_id, "entry_id")

        try:
            entry = _get_journal_entry(
                entry_id=entry_id,
                include_log=include_log,
                db_path=db_path,
            )

            if not entry:
                raise ValidationError(f"Entry {entry_id} not found")

            result: dict[str, Any] = {
                "id": entry.id,
                "created_at": entry.created_at.isoformat(),
                "working_directory": entry.working_directory,
                "project_name": entry.project_name,
                "session_log_path": entry.session_log_path,
                "summary": entry.summary,
                "friction_points": entry.friction_points,
                "next_steps": entry.next_steps,
                "reflected_at": entry.reflected_at.isoformat() if entry.reflected_at else None,
                "memories_created": entry.memories_created,
            }

            if include_log and entry.session_log:
                result["session_log"] = entry.session_log

            logger.info("journal.got", entry_id=entry_id)

            return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error("journal.get_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to get journal entry: {e}") from e

    async def mark_entries_reflected(
        entry_ids: list[str],
        memories_created: int | None = None,
        delete_logs: bool = True,
    ) -> dict[str, Any]:
        """Mark entries as reflected and optionally delete their logs."""
        logger.info("journal.mark_reflected", count=len(entry_ids), delete_logs=delete_logs)

        # Validate inputs
        if not entry_ids:
            raise ValidationError("At least one entry ID is required")
        for entry_id in entry_ids:
            validate_uuid(entry_id, "entry_id")
        if memories_created is not None and memories_created < 0:
            raise ValidationError("memories_created must be >= 0")

        try:
            marked_count, logs_deleted = _mark_entries_reflected(
                entry_ids=entry_ids,
                memories_created=memories_created,
                delete_logs=delete_logs,
                db_path=db_path,
            )

            logger.info("journal.marked_reflected", marked_count=marked_count, logs_deleted=logs_deleted)

            return {
                "marked_count": marked_count,
                "logs_deleted": logs_deleted,
            }

        except Exception as e:
            logger.error("journal.mark_reflected_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to mark entries reflected: {e}") from e

    return {
        "store_journal_entry": store_journal_entry,
        "list_journal_entries": list_journal_entries,
        "get_journal_entry": get_journal_entry,
        "mark_entries_reflected": mark_entries_reflected,
    }
```

## Database Operations

All journal operations use the existing `session_journal` table from `src/calm/db/schema.py`:

```sql
-- Insert new entry
INSERT INTO session_journal
(id, created_at, working_directory, project_name, session_log_path,
 summary, friction_points, next_steps)
VALUES (?, ?, ?, ?, ?, ?, ?, ?);

-- List entries with filters
SELECT * FROM session_journal
WHERE reflected_at IS NULL  -- if unreflected_only
  AND project_name = ?      -- if project_name filter
  AND working_directory = ? -- if working_directory filter
ORDER BY created_at DESC
LIMIT ?;

-- Get single entry
SELECT * FROM session_journal WHERE id = ?;

-- Mark entries reflected
UPDATE session_journal
SET reflected_at = ?, memories_created = ?
WHERE id = ?;
```

## Testing Strategy

### Unit Tests for MCP Tools

Create `tests/unit/tools/test_journal.py`:

```python
import pytest
from pathlib import Path
from calm.tools.journal import get_journal_tools

@pytest.fixture
def journal_tools(tmp_path):
    """Get journal tools with test database."""
    db_path = tmp_path / "test.db"
    return get_journal_tools(db_path=db_path)

class TestStoreJournalEntry:
    async def test_store_basic_entry(self, journal_tools):
        """Test storing a journal entry without log."""
        result = await journal_tools["store_journal_entry"](
            summary="Test session summary",
            working_directory="/test/project",
        )
        assert "id" in result
        assert result["session_log_path"] is None

    async def test_store_with_log(self, journal_tools, tmp_path):
        """Test storing a journal entry with session log."""
        result = await journal_tools["store_journal_entry"](
            summary="Test session",
            working_directory="/test/project",
            session_log_content='{"type":"test"}\n',
        )
        assert result["session_log_path"] is not None
        assert Path(result["session_log_path"]).exists()

    async def test_validation_empty_summary(self, journal_tools):
        """Test validation rejects empty summary."""
        with pytest.raises(ValidationError):
            await journal_tools["store_journal_entry"](
                summary="",
                working_directory="/test/project",
            )

class TestListJournalEntries:
    async def test_list_empty(self, journal_tools):
        """Test listing when no entries exist."""
        result = await journal_tools["list_journal_entries"]()
        assert result["entries"] == []
        assert result["count"] == 0

    async def test_unreflected_filter(self, journal_tools):
        """Test filtering for unreflected entries only."""
        # Store entry, mark one reflected
        await journal_tools["store_journal_entry"](
            summary="Entry 1",
            working_directory="/test",
        )
        # ... test unreflected filter

class TestGetJournalEntry:
    async def test_get_existing(self, journal_tools):
        """Test getting an existing entry."""
        store_result = await journal_tools["store_journal_entry"](
            summary="Test",
            working_directory="/test",
        )
        get_result = await journal_tools["get_journal_entry"](
            entry_id=store_result["id"],
        )
        assert get_result["summary"] == "Test"

    async def test_include_log(self, journal_tools, tmp_path):
        """Test including session log in response."""
        # Store with log, then get with include_log=True
        pass

class TestMarkEntriesReflected:
    async def test_mark_single(self, journal_tools):
        """Test marking a single entry as reflected."""
        pass

    async def test_delete_logs(self, journal_tools, tmp_path):
        """Test log deletion when marking reflected."""
        pass
```

### Unit Tests for Business Logic

Create `tests/unit/orchestration/test_journal.py`:

```python
import pytest
from calm.orchestration.journal import (
    store_journal_entry,
    list_journal_entries,
    get_journal_entry,
    mark_entries_reflected,
)

class TestJournalOperations:
    def test_store_and_retrieve(self, test_db):
        """Test round-trip of journal entry."""
        entry_id, _ = store_journal_entry(
            summary="Test summary",
            working_directory="/test/project",
            friction_points=["issue 1"],
            next_steps=["step 1"],
            db_path=test_db,
        )

        entry = get_journal_entry(entry_id, db_path=test_db)
        assert entry is not None
        assert entry.summary == "Test summary"
        assert entry.friction_points == ["issue 1"]
```

### CLI Tests

Create `tests/unit/cli/test_session_journal.py`:

```python
from click.testing import CliRunner
from calm.cli.main import cli

def test_session_journal_list_empty(test_db):
    """Test session journal list with no entries."""
    runner = CliRunner()
    result = runner.invoke(cli, ["session", "journal", "list"])
    assert result.exit_code == 0
    assert "No journal entries" in result.output

def test_session_journal_show_not_found(test_db):
    """Test session journal show with invalid ID."""
    runner = CliRunner()
    result = runner.invoke(cli, ["session", "journal", "show", "invalid-id"])
    assert result.exit_code != 0
    assert "not found" in result.output
```

## Migration/Compatibility

### Database Migration

No migration is needed - the `session_journal` table schema is already defined in `src/calm/db/schema.py` and created by `calm init`. The existing schema exactly matches what this spec requires.

### Skill File Installation

Skills are stored in `~/.calm/skills/`. The install script (SPEC-058-06) will copy skill files from the package to this location. For development, skills can be manually created.

### Backwards Compatibility

- The existing `session` CLI commands for orchestration handoffs remain unchanged
- Journal commands are added as new subcommands (`list`, `show`) that don't conflict
- MCP tools use new names that don't collide with existing tools

## Open Questions / Design Decisions

### 1. CLI Command Naming (RESOLVED)

**Issue**: The existing `session` CLI group already has `list` and `show` commands for orchestration handoffs. Adding journal commands with the same names would create conflicts.

**Decision**: Use a `journal` subgroup under `session`:
- `calm session journal list` - List journal entries
- `calm session journal show <id>` - Show journal entry details

This preserves the existing handoff commands:
- `calm session list` - List orchestration handoffs
- `calm session show <id>` - Show handoff content

**Rationale**: The subgroup approach is the cleanest solution because:
1. No breaking changes to existing CLI commands
2. Clear conceptual separation (handoffs vs journal entries)
3. Consistent with Click's nested group pattern

### 2. Agent Model for Reflection

**Spec states**: Use `haiku` for analysis agents to minimize cost.

**Implementation note**: The `/reflection` skill dispatches Task tool agents. The model selection should be configurable, defaulting to haiku but allowing override. This is handled by the skill instructions rather than code.

### 3. Semantic Deduplication in Reflection

**Spec states**: Use semantic similarity > 0.85 to detect duplicate proposed memories.

**Implementation**: The `/reflection` skill instructs Claude to use `retrieve_memories` to check for similar existing memories. This is a heuristic approach - the skill can compare the returned similarity scores. For cross-proposal deduplication within a batch, the skill will need to do pairwise comparisons or use embedding similarity directly.

**Alternative**: Add a `compare_similarity` MCP tool that takes two text strings and returns their cosine similarity. This would be more precise but adds another tool.

**Recommendation**: Start with the skill-based approach using `retrieve_memories`. If deduplication quality is poor, add a dedicated similarity comparison tool in a follow-up.

### 4. Session Log Path Mapping

The spec describes mapping `$PWD` to Claude's project path format by replacing `/` with `-` and prefixing with `-`. This logic is implemented in the `/wrapup` skill instructions rather than in code, since it's used during the skill execution to locate files.

**Verification needed**: Confirm the exact path mapping Claude Code uses for session logs. The skill instructions may need adjustment based on actual Claude behavior.

### 5. Skill Loading Mechanism (CLARIFIED)

**Issue**: How will the skill files (`~/.calm/skills/wrapup.md` and `reflection.md`) be loaded?

**Clarification**: Skills are loaded by Claude Code's native skill system. When a user types `/wrapup` or `/reflection`, Claude Code:
1. Searches for skill files in known locations (including `~/.calm/skills/`)
2. Matches the trigger patterns defined in YAML frontmatter
3. Loads the skill content into the conversation context

**No custom code is required for skill loading** - Claude Code provides this infrastructure. SPEC-058-04 only needs to:
1. Create the skill markdown files with proper frontmatter
2. Place them in `~/.calm/skills/` (either manually during development or via the install script in SPEC-058-06)

**Scope for SPEC-058-04**: This task creates the skill file content but does NOT implement any skill loading code. The skill files are documentation/instructions that Claude Code interprets directly.
