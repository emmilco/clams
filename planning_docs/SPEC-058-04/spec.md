# SPEC-058-04: CALM Session and Reflection

## Overview

Implement session journaling and the learning reflection loop for CALM. This phase adds:
- MCP tools for storing and querying session journal entries
- `/wrapup` skill for capturing session summaries and logs
- `/reflection` skill for multi-agent analysis and memory extraction

## Background

From the parent spec (SPEC-058), Phase 4 enables the learning loop:
- Sessions are journaled via `/wrapup` with summary, friction points, and next steps
- Session logs are captured for later analysis
- `/reflection` analyzes unreflected sessions with specialized agents
- Human reviews and approves proposed memories in batch
- Approved memories are stored, session logs deleted

## Scope

### In Scope
- Session journal MCP tools (store, list, get, mark_reflected)
- `/wrapup` skill implementation
- `/reflection` skill implementation with multi-agent analysis
- Batch approval UI for proposed memories
- Session log capture and cleanup
- CLI commands for session management

### Out of Scope
- Hook implementations (covered in SPEC-058-05)
- `/orchestrate` skill (covered in SPEC-058-05)
- Install script (covered in SPEC-058-06)

## Technical Requirements

### Database Schema

The schema already exists in `metadata.db` (from SPEC-058-01):

```sql
CREATE TABLE session_journal (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    working_directory TEXT NOT NULL,
    project_name TEXT,  -- Last component of path
    session_log_path TEXT,  -- Path to copied log in ~/.calm/sessions/
    summary TEXT NOT NULL,
    friction_points TEXT,  -- JSON array
    next_steps TEXT,  -- JSON array
    reflected_at TEXT,  -- NULL if unreflected
    memories_created INTEGER DEFAULT 0
);

CREATE INDEX idx_journal_reflected ON session_journal(reflected_at);
CREATE INDEX idx_journal_project ON session_journal(project_name);
CREATE INDEX idx_journal_directory ON session_journal(working_directory);
```

### MCP Tools

#### `store_journal_entry`
Store a new session journal entry with optional log capture.

**Parameters:**
- `summary` (string, required): Session summary text
- `working_directory` (string, required): The working directory of the session
- `friction_points` (array[string], optional): List of friction points encountered
- `next_steps` (array[string], optional): Recommended next steps
- `session_log_content` (string, optional): Raw session log content to store

**Returns:**
- `id`: The created entry ID
- `session_log_path`: Path where log was saved (if provided)

**Behavior:**
1. Generate UUID for entry ID
2. Extract `project_name` from last component of `working_directory`
3. If `session_log_content` provided:
   - Create `~/.calm/sessions/` if needed
   - Save to `~/.calm/sessions/<timestamp>_<uuid>.jsonl`
   - Store path in `session_log_path`
4. Insert record into `session_journal`

#### `list_journal_entries`
List session journal entries with optional filters.

**Parameters:**
- `unreflected_only` (boolean, optional, default=false): Only return entries where `reflected_at` is NULL
- `project_name` (string, optional): Filter by project name
- `working_directory` (string, optional): Filter by exact working directory
- `limit` (integer, optional, default=50): Maximum entries to return

**Returns:**
Array of entries with: `id`, `created_at`, `working_directory`, `project_name`, `summary`, `reflected_at`

#### `get_journal_entry`
Get full details of a journal entry.

**Parameters:**
- `entry_id` (string, required): The entry ID
- `include_log` (boolean, optional, default=false): Include the full session log content

**Returns:**
- Full entry fields
- If `include_log=true` and `session_log_path` exists, include `session_log` field with file contents

#### `mark_entries_reflected`
Mark entries as reflected and optionally delete their logs.

**Parameters:**
- `entry_ids` (array[string], required): List of entry IDs to mark
- `memories_created` (integer, optional): Number of memories created from this batch
- `delete_logs` (boolean, optional, default=true): Delete session log files after marking

**Returns:**
- `marked_count`: Number of entries marked
- `logs_deleted`: Number of log files deleted

**Behavior:**
1. Update `reflected_at` to current timestamp for all entries
2. Update `memories_created` if provided (divide evenly or use provided count)
3. If `delete_logs=true`, delete each entry's `session_log_path` file

### `/wrapup` Skill

The `/wrapup` skill wraps up a session by:
1. Analyzing the conversation for summary, friction points, next steps
2. Locating and copying the current session log
3. Storing a journal entry
4. Reporting to the user

**Trigger:** User runs `/wrapup` or `/wrapup continue`

**Skill File:** `~/.calm/skills/wrapup.md` (or inline in skill-rules.json)

**Behavior:**

1. **Analyze Conversation:**
   - Generate a concise summary (2-3 sentences)
   - Identify friction points (problems, blockers, unexpected issues)
   - Determine next steps (what should happen next)

2. **Locate Session Log:**
   - Map `$PWD` to Claude project path format:
     - Replace `/` with `-`
     - Prefix with `-`
     - Example: `/Users/foo/project` → `-Users-foo-project`
   - Find most recent `.jsonl` in `~/.claude/projects/<mapped>/`
   - Read the log content

3. **Store Journal Entry:**
   - Call `store_journal_entry` MCP tool with:
     - `summary`
     - `working_directory` (current $PWD)
     - `friction_points`
     - `next_steps`
     - `session_log_content` (the log file contents)

4. **Report to User:**
   ```
   ## Session Wrapped Up

   **Summary**: [summary text]

   **Friction Points**:
   - [friction point 1]
   - [friction point 2]

   **Next Steps**:
   - [next step 1]
   - [next step 2]

   Journal entry saved: [entry_id]
   ```

**Variant: `/wrapup continue`**
Same as above, but adds a note that continuation is expected. The journal entry could include a `needs_continuation` flag (or we rely on next_steps being non-empty).

### `/reflection` Skill

The `/reflection` skill processes unreflected sessions to extract memories.

**Trigger:** User runs `/reflection`

**Behavior:**

1. **Load Unreflected Entries:**
   - Call `list_journal_entries(unreflected_only=true)`
   - If none found, report "No unreflected sessions to process"

2. **For Each Entry (up to batch size):**
   - Call `get_journal_entry(entry_id, include_log=true)`
   - Prepare context: summary, friction_points, session_log

3. **Dispatch Analysis Agents (in parallel):**
   Launch 4 agents using Task tool, each with a specialized prompt:

   **Agent 1: Debugging Analyst**
   - Focus: Root causes, misleading symptoms, what fixed things
   - Categories: "error", "decision"

   **Agent 2: Codebase Cartographer**
   - Focus: Stable architectural knowledge, patterns, conventions
   - Categories: "fact"

   **Agent 3: Process Observer**
   - Focus: Workflow patterns, efficiency insights
   - Categories: "workflow", "preference"

   **Agent 4: Pattern Detector**
   - Focus: Recurring themes, anti-patterns to avoid
   - Categories: "decision", "fact"

4. **Collect and Deduplicate Proposals:**
   - Gather all proposed memories from agents
   - Use semantic similarity to detect duplicates (threshold: 0.85)
   - Merge similar proposals, keeping highest importance

5. **Present Batch Approval UI:**
   Use AskUserQuestion tool with multi-select to present proposals:
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
   ```

6. **Store Approved Memories:**
   - For each approved proposal, call `store_memory` MCP tool
   - Track count of memories created

7. **Mark Entries Reflected:**
   - Call `mark_entries_reflected` with entry IDs and memory count
   - This deletes the session log files

8. **Report Results:**
   ```
   ## Reflection Complete

   Sessions processed: N
   Memories created: M
   Session logs deleted: N

   New memories:
   - [category] memory content...
   - [category] memory content...
   ```

### CLI Commands

#### `calm session list`
List journal entries.

**Options:**
- `--unreflected`: Only show unreflected entries
- `--project <name>`: Filter by project name
- `--limit <n>`: Maximum entries (default: 20)

**Output:**
```
ID                                    Created              Project      Summary
------------------------------------  -------------------  -----------  --------
abc123...                             2026-02-01 15:30:00  clams        Implemented CALM foundation...
def456...                             2026-02-01 10:15:00  clams        Fixed async test issue...
```

#### `calm session show <id>`
Show full details of a journal entry.

**Options:**
- `--log`: Include session log content (can be large)

#### `calm session reflect`
Trigger the reflection process (CLI equivalent of `/reflection` skill).

Note: This may be complex to implement as CLI since it involves multi-agent analysis. Could be a simplified version or just invoke the skill.

### Agent Analysis Prompts

See parent spec (SPEC-058) section "Reflection Analysis Agents" for detailed prompts for each of the 4 agents.

Key principles for agents:
- Extract STABLE insights, not brittle specifics
- BAD: "The bug was on line 234 of user.py"
- GOOD: "Async context managers must be awaited even in decorator usage"
- Return structured data: content, category, importance, reasoning

## Acceptance Criteria

### MCP Tools
- [ ] `store_journal_entry` creates entries and optionally saves log files
- [ ] `list_journal_entries` returns filtered entries
- [ ] `get_journal_entry` returns full entry with optional log content
- [ ] `mark_entries_reflected` updates entries and deletes logs
- [ ] All tools registered in calm MCP server
- [ ] Tools use `~/.calm/sessions/` for log storage

### `/wrapup` Skill
- [ ] Skill file created (or inline rules defined)
- [ ] Analyzes conversation for summary, friction points, next steps
- [ ] Locates current session log in `~/.claude/projects/`
- [ ] Copies log to `~/.calm/sessions/`
- [ ] Stores journal entry via MCP tool
- [ ] Reports completion to user with entry ID

### `/reflection` Skill
- [ ] Loads unreflected journal entries
- [ ] Dispatches 4 analysis agents in parallel
- [ ] Collects proposals and deduplicates by semantic similarity
- [ ] Presents batch approval UI via AskUserQuestion
- [ ] Stores approved memories
- [ ] Marks entries as reflected and deletes logs
- [ ] Reports results to user

### CLI
- [ ] `calm session list` with filters
- [ ] `calm session show` with optional log display

### Testing
- [ ] Unit tests for all MCP tools
- [ ] Tests for journal entry CRUD operations
- [ ] Tests for log file management
- [ ] Tests for CLI commands
- [ ] All tests pass with mypy --strict

## Implementation Notes

1. **Session Log Location**: Claude stores session logs at `~/.claude/projects/<mapped-path>/`. The path mapping replaces `/` with `-` and prefixes with `-`.

2. **Log File Format**: Session logs are JSONL files with one JSON object per line representing conversation turns.

3. **Batch Size**: Default reflection batch size is 10 sessions to avoid overwhelming context.

4. **Semantic Deduplication**: Use the embedding service to compare proposed memories. Similarity > 0.85 indicates duplicates.

5. **Agent Model**: Use `haiku` for analysis agents to minimize cost while maintaining quality.

6. **Skill Implementation**: Skills can be implemented as:
   - Skill files in `~/.calm/skills/`
   - Inline rules in skill-rules.json
   - Both approaches load instructions into context when triggered

## Dependencies

- SPEC-058-01: CALM Foundation (database, server) - DONE
- SPEC-058-02: CALM Memory/GHAP (memory tools, embeddings) - DONE
- SPEC-058-03: CALM Orchestration CLI (task management) - DONE
