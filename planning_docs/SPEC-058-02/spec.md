# SPEC-058-02: CALM Memory/GHAP - Port memory and learning features

## Overview

Port the memory and GHAP (Goal-Hypothesis-Action-Prediction) functionality from the existing clams MCP server to the new calm package. This includes memory CRUD operations, GHAP tracking, code/git indexing, semantic search, and context assembly.

## Background

The current clams package provides memory and learning features through MCP tools. This spec covers porting these features to the calm package, reusing the existing code where appropriate but integrating with calm's new architecture (single `~/.calm/` directory, unified database).

## Scope

### In Scope

1. **Memory Tools**
   - `store_memory` - Store a memory with category, importance, tags
   - `retrieve_memories` - Semantic search for memories
   - `list_memories` - List memories with filters (non-semantic)
   - `delete_memory` - Delete a memory by ID

2. **GHAP Tools**
   - `start_ghap` - Begin tracking a hypothesis
   - `update_ghap` - Update active GHAP (hypothesis, prediction, etc.)
   - `resolve_ghap` - Mark as confirmed/falsified/abandoned with learnings
   - `get_active_ghap` - Get current active GHAP if any
   - `list_ghap_entries` - List past GHAP entries with filters

3. **Code Indexing Tools**
   - `index_codebase` - Index directory for semantic search
   - `search_code` - Semantic code search
   - `find_similar_code` - Find code similar to snippet

4. **Git Tools**
   - `index_commits` - Index git commits for search
   - `search_commits` - Semantic commit search
   - `get_file_history` - Get commit history for file
   - `get_churn_hotspots` - Find high-change-frequency files
   - `get_code_authors` - Get author stats for file

5. **Learning Tools**
   - `search_experiences` - Search past GHAP experiences
   - `get_clusters` - Get experience clusters by axis
   - `get_cluster_members` - Get experiences in a cluster
   - `validate_value` - Check if value statement fits cluster
   - `store_value` - Store validated value statement
   - `list_values` - List stored values

6. **Context Tools**
   - `assemble_context` - Build context from memories + experiences

7. **Session Tools** (basic)
   - `ping` - Health check endpoint
   - `start_session` - Initialize session
   - `get_orphaned_ghap` - Check for orphaned GHAP from previous session
   - `should_check_in` - Check if GHAP reminder is due
   - `increment_tool_count` - Increment the tool counter
   - `reset_tool_count` - Reset tool counter after reminder

### Out of Scope

- Session journaling (`store_journal_entry`, etc.) - covered in SPEC-058-04
- `/reflection` skill - covered in SPEC-058-04
- Orchestration tools (tasks, gates, worktrees, workers, reviews) - covered in SPEC-058-03
- CLI commands - this phase focuses on MCP tools only

## Technical Approach

### Code Reuse Strategy

Most of the memory/GHAP logic already exists in `src/clams/`. The approach:

1. **Copy relevant modules** from `src/clams/` to `src/calm/`
2. **Update imports** to use `calm.*` instead of `clams.*`
3. **Adapt to new config** - use `calm.config.settings` instead of clams config
4. **Register tools** with the calm MCP server (in `src/calm/server/app.py`)

### Modules to Port

| Source (clams) | Destination (calm) | Notes |
|----------------|-------------------|-------|
| `storage/qdrant.py` | `storage/qdrant.py` | Vector storage client |
| `storage/embeddings.py` | `storage/embeddings.py` | Embedding generation |
| `memory/store.py` | `memory/store.py` | Memory CRUD |
| `ghap/tracker.py` | `ghap/tracker.py` | GHAP state management |
| `code/indexer.py` | `code/indexer.py` | Code indexing |
| `git/commits.py` | `git/commits.py` | Git integration |
| `clustering/` | `clustering/` | Experience clustering |
| `values/` | `values/` | Value store |
| `context/assembler.py` | `context/assembler.py` | Context building |
| `tools/*.py` | `tools/*.py` | MCP tool handlers |

### Database Tables

The tables were already created in SPEC-058-01:
- `memories` - Memory storage with category, importance, tags
- `ghap_entries` - GHAP tracking with full lifecycle
- `code_files`, `code_chunks` - Code indexing metadata
- `commits` - Git commit indexing
- `values` - Validated value statements (already in schema)
- `settings` - Runtime settings storage

### Values and Clustering Storage

- **Values**: Stored in the `values` table with `text`, `cluster_id`, `axis`, and `created_at`
- **Clustering**: Computed at query time from GHAP entry embeddings in Qdrant. No persistent clustering tables - clusters are dynamically calculated using HDBSCAN on the embedded GHAP data when `get_clusters` is called

### Qdrant Collections

The existing clams collections will be reused (same Qdrant instance):

| Collection | Content | Dimension | Metric |
|------------|---------|-----------|--------|
| `memories` | Memory content embeddings | 768 | Cosine |
| `code_chunks` | Code snippet embeddings | 384 | Cosine |
| `commits` | Commit message embeddings | 768 | Cosine |
| `ghap_full` | Full GHAP entry text | 768 | Cosine |
| `ghap_strategy` | Strategy-focused GHAP text | 768 | Cosine |
| `ghap_surprise` | Surprise descriptions | 768 | Cosine |
| `ghap_root_cause` | Root cause descriptions | 768 | Cosine |

Note: Code chunks use a smaller model (all-MiniLM-L6-v2, 384 dim) optimized for code. Semantic content uses nomic-embed-text-v1.5 (768 dim).

### Configuration

Settings in `calm.config`:
- `qdrant_url` - Qdrant server URL (default: http://localhost:6333)
- `code_embedding_model` - Model for code embeddings
- `semantic_embedding_model` - Model for semantic embeddings

## Acceptance Criteria

1. [ ] All memory MCP tools functional (`store_memory`, `retrieve_memories`, `list_memories`, `delete_memory`)
2. [ ] All GHAP MCP tools functional (`start_ghap`, `update_ghap`, `resolve_ghap`, `get_active_ghap`, `list_ghap_entries`)
3. [ ] All code indexing tools functional (`index_codebase`, `search_code`, `find_similar_code`)
4. [ ] All git tools functional (`index_commits`, `search_commits`, `get_file_history`, `get_churn_hotspots`, `get_code_authors`)
5. [ ] All learning tools functional (`search_experiences`, `get_clusters`, `get_cluster_members`, `validate_value`, `store_value`, `list_values`)
6. [ ] `assemble_context` tool functional
7. [ ] Session helper tools functional (`ping`, `start_session`, `get_orphaned_ghap`, `should_check_in`, etc.)
8. [ ] All tools registered in calm MCP server
9. [ ] Tools use calm's `~/.calm/metadata.db` and `~/.calm/` paths
10. [ ] Existing clams functionality unchanged (runs in parallel)
11. [ ] Tests for all ported functionality
12. [ ] All code passes mypy --strict

## Dependencies

- **SPEC-058-01**: Foundation must be complete (DONE)
- **Qdrant**: Vector database must be running

## Risks

1. **Embedding model compatibility** - Need to ensure same models are used to avoid index corruption
2. **Database migration** - Need to handle case where user has existing clams data

## Notes

- This is a port, not a rewrite - minimize changes to working code
- Keep clams running during development - we use it to orchestrate this work
- Focus on making tools work first, optimization later
