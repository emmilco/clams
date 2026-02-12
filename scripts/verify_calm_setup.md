# CALM Installation Verification Prompt

Paste this prompt into a Claude Code session in a **brand new repo** (or any repo that is NOT the CALM source repo) to verify the full CALM installation.

---

## Prompt

You are running a verification check of the CALM (Claude Agent Learning & Memory) system. Run every check below and produce a final report. Do NOT fix anything — just report pass/fail for each check.

### 1. CALM CLI

Run each command and verify it produces output (not an error):

```bash
calm --version
calm status
calm status health
calm task list
calm counter list
calm gate list
calm worker list
calm session list
calm backup list
calm task next-id BUG
calm task next-id SPEC
```

### 2. CALM MCP Server

Verify the server is running:
```bash
calm server status
```

Then verify all 29 MCP tools are available by calling:
```
mcp__calm__ping
```

Then verify each tool category works by calling these tools (use the MCP tool calls, not bash):

**Memory tools:**
- `mcp__calm__store_memory` with content="CALM verification test", category="fact"
- `mcp__calm__retrieve_memories` with query="CALM verification test"
- `mcp__calm__list_memories` with limit=5
- `mcp__calm__delete_memory` with the memory_id from the store call above

**GHAP tools:**
- `mcp__calm__start_ghap` with domain="testing", strategy="check-assumptions", goal="Verify CALM setup", hypothesis="All tools work", action="Running checks", prediction="All calls succeed"
- `mcp__calm__get_active_ghap`
- `mcp__calm__update_ghap` with note="Verification in progress"
- `mcp__calm__resolve_ghap` with status="confirmed", result="All tools verified"
- `mcp__calm__list_ghap_entries` with limit=5
- `mcp__calm__search_experiences` with query="verification"

**Code indexing tools:**
- `mcp__calm__index_codebase` with directory=(current working directory), project="verify-test"
- `mcp__calm__search_code` with query="function", project="verify-test"
- `mcp__calm__find_similar_code` with snippet="def main():\n    pass"

**Git tools:**
- `mcp__calm__index_commits` with limit=10
- `mcp__calm__search_commits` with query="initial"
- `mcp__calm__get_churn_hotspots` with days=30

**Clustering tools:**
- `mcp__calm__get_clusters` with axis="full"

**Values tools:**
- `mcp__calm__list_values`

**Context tools:**
- `mcp__calm__assemble_context` with query="test verification"

**Journal tools:**
- `mcp__calm__store_journal_entry` with summary="Verification test session", working_directory=(current working directory)
- `mcp__calm__list_journal_entries` with limit=5
- `mcp__calm__get_journal_entry` with the entry_id from the store call above
- `mcp__calm__mark_entries_reflected` with entry_ids=[the entry_id from above]

### 3. Claude Code Skills

Verify these skills appear in your available skills list (check the system reminder at the top of this conversation):

- `orchestrate` — should mention "CALM orchestration mode"
- `wrapup` — should mention "session" and "handoff"
- `reflection` — should mention "sessions" and "learnings"

### 4. Skill Wrappers (file check)

Verify these files exist:
```bash
ls -la ~/.claude/skills/orchestrate/SKILL.md
ls -la ~/.claude/skills/wrapup/SKILL.md
ls -la ~/.claude/skills/reflection/SKILL.md
cat ~/.claude/skills/skill-rules.json
```

Verify `skill-rules.json` contains entries for:
- `calm-orchestrate`
- `calm-wrapup`
- `calm-reflection`

### 5. CALM Directory Structure

Verify all directories and files exist:
```bash
ls ~/.calm/
ls ~/.calm/roles/
ls ~/.calm/skills/
ls ~/.calm/workflows/
ls ~/.calm/sessions/
ls ~/.calm/journal/
ls -la ~/.calm/metadata.db
ls -la ~/.calm/config.yaml
```

Expected roles (15 total): `ai-dl.md`, `architect.md`, `backend.md`, `bug-investigator.md`, `doc-writer.md`, `e2e-runner.md`, `frontend.md`, `infra.md`, `planning.md`, `product.md`, `proposal-reviewer.md`, `qa.md`, `reviewer.md`, `spec-reviewer.md`, `ux.md`

Expected skills (3): `orchestrate.md`, `reflection.md`, `wrapup.md`

Expected workflows (1): `default.md`

### 6. Docker / Qdrant

```bash
docker ps --filter name=calm-qdrant --format '{{.Names}} {{.Status}}'
```

Should show `calm-qdrant` running. If not running, check:
```bash
docker ps -a --filter name=calm-qdrant --format '{{.Names}} {{.Status}}'
```

### 7. Database Integrity

```bash
calm backup create verify-test
calm backup list
```

### Final Report

Produce a summary table:

| Category | Check | Result |
|----------|-------|--------|
| CLI | `calm --version` | PASS/FAIL |
| CLI | `calm status` | PASS/FAIL |
| CLI | All subcommands accessible | PASS/FAIL |
| MCP Server | Server running | PASS/FAIL |
| MCP Server | ping tool | PASS/FAIL |
| MCP Tools | Memory tools (4) | PASS/FAIL |
| MCP Tools | GHAP tools (6) | PASS/FAIL |
| MCP Tools | Code indexing tools (3) | PASS/FAIL |
| MCP Tools | Git tools (3) | PASS/FAIL |
| MCP Tools | Clustering tools (1) | PASS/FAIL |
| MCP Tools | Values tools (1) | PASS/FAIL |
| MCP Tools | Context tools (1) | PASS/FAIL |
| MCP Tools | Journal tools (4) | PASS/FAIL |
| Skills | orchestrate discoverable | PASS/FAIL |
| Skills | wrapup discoverable | PASS/FAIL |
| Skills | reflection discoverable | PASS/FAIL |
| Skills | Wrapper files exist | PASS/FAIL |
| Skills | skill-rules.json entries | PASS/FAIL |
| Directory | ~/.calm/ structure complete | PASS/FAIL |
| Directory | All 15 roles present | PASS/FAIL |
| Directory | All 3 CALM skills present | PASS/FAIL |
| Directory | Workflow file present | PASS/FAIL |
| Docker | Qdrant container running | PASS/FAIL |
| Database | Backup create/list works | PASS/FAIL |

After producing the table, clean up any test data you created (delete the verification memory, the test journal entry should already be marked reflected).

**Total: X/24 checks passed.**
