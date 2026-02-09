# Changelog

All notable changes to the CALM (Claude Agent Learning & Memory) project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## Consolidated (through 2026-02-08)

This consolidation covers all changes from project inception through the CALM cutover and post-cutover bug fixes. Organized by category, entries are listed in numeric order by task ID.

---

### Features

#### SPEC-002-01: Project Scaffolding
Created the foundational project structure for the CLAMS server with Python packaging, linting, type checking, and testing infrastructure.
- Added src layout with clams package and all module directories
- Added pyproject.toml with all production and development dependencies
- Configured ruff (line-length 88, Python 3.12), mypy (strict mode), pytest with pytest-asyncio

#### SPEC-002-02: EmbeddingService + NomicEmbedding
Implemented the embedding abstraction layer with mock and Nomic embedding support.
- Added `EmbeddingService` ABC with `embed()` and `embed_batch()` methods
- Added `MockEmbedding` for testing and `NomicEmbedding` using nomic-embed-text-v1.5

#### SPEC-002-03: VectorStore + QdrantVectorStore
Implemented vector storage abstraction with in-memory and Qdrant implementations.
- Added `VectorStore` ABC with CRUD and search operations
- Added `InMemoryVectorStore` for testing and `QdrantVectorStore` for production

#### SPEC-002-04: SQLite MetadataStore
Implemented SQLite-based metadata storage for indexed files, call graphs, and projects.
- Added `MetadataStore` class with async SQLite operations
- Automatic schema initialization and migrations

#### SPEC-002-05: MCP Server Skeleton
Implemented the MCP server framework with configuration and basic tool registration.
- Added `Settings` class with pydantic-settings for environment configuration
- Created MCP server entry point with `ping` tool for health checks

#### SPEC-002-06: CodeParser + CodeIndexer
Implemented code parsing and indexing for semantic code search. Supports 9 languages (Python, TypeScript, JavaScript, Rust, Swift, Java, C, C++, SQL) using tree-sitter grammars.
- Added `TreeSitterParser` and `CodeIndexer` with change detection via mtime + content hash
- Batch embedding (100 units at a time) to prevent memory issues

#### SPEC-002-07: GitReader + GitAnalyzer
Implemented git history reading and semantic commit search with embedding-based indexing.
- Added `GitPythonReader` and `GitAnalyzer` for commit indexing, search, churn analysis, and blame
- Extended `MetadataStore` with git_index_state table and `QdrantVectorStore` with range queries

#### SPEC-002-09: Searcher Unified Query Interface
Implemented unified, type-safe query interface for semantic search across all vector collections.
- Added `Searcher` class with typed result dataclasses (MemoryResult, CodeResult, ExperienceResult, ValueResult, CommitResult)
- Added `CollectionName` constants and filter translation layer

#### SPEC-002-11: MCP Tools for Memory, Code, Git
Implemented 13 MCP tools across 3 modules exposing the server's functionality.
- Added `ServiceContainer` for dependency injection with graceful degradation
- 4 memory tools, 3 code tools, 4 git tools with strict input validation

#### SPEC-002-12: Clusterer HDBSCAN
Implemented HDBSCAN-based clustering for experiences and memories.
- Added `Clusterer` and `ExperienceClusterer` with confidence tier weights (gold=1.0, silver=0.8, bronze=0.5, abandoned=0.2)
- Weighted centroid computation

#### SPEC-002-13: ValueStore Validation and Storage
Implemented ValueStore for validating and storing agent-generated values from experience clusters.
- Validation using centroid distance threshold (mean + 0.5 * std)
- Cluster access, value storage with embedding, axis filtering

#### SPEC-002-14: ObservationPersister Multi-Axis Embedding
Implemented ObservationPersister to embed and store resolved GHAP entries.
- Multi-axis embedding: full, strategy, surprise (falsified only), root_cause (falsified only)
- Template-based text rendering with optional field handling

#### SPEC-002-15: MCP Tools for GHAP and Learning
Implemented 11 MCP tools for GHAP tracking, learning/value formation, and semantic search.
- 5 GHAP tools, 5 learning tools, 1 search tool
- Exponential backoff retry logic for resolve_ghap persistence

#### SPEC-002-16: Full Integration and Performance Tuning
Completed integration work to create a working Learning Memory Server.
- Fixed integration bugs, enabled all services, implemented stub MCP tools
- Added `initialize_collections()` and `validate_configuration()` with fail-fast validation

#### SPEC-002-17: Documentation and E2E Testing
Completed the Learning Memory Server with documentation and comprehensive testing.
- Added GETTING_STARTED.md and verified all 23 MCP tools have docstrings
- E2E integration tests and performance benchmarks (code search p95 < 200ms, context assembly p95 < 500ms)
- 508 tests passing, 84%+ coverage

#### SPEC-002-19: Hook Scripts and Context Injection
Implemented Claude Code hook scripts for agent session integration.
- session_start.sh, user_prompt_submit.sh, ghap_checkin.sh, outcome_capture.sh, session_end.sh
- Python MCP client utility for shell scripts to call MCP tools
- All hooks use graceful degradation

#### SPEC-003: Optimize MCP Protocol Test Performance
Reduced MCP protocol test execution time from ~130s to ~8s (17x improvement).
- Changed `mcp_session` fixture from function-scoped to module-scoped
- Eliminated redundant server startups and embedding model loads

#### SPEC-004: Gate Pass Verification for Phase Transitions
Implemented commit-anchored gate pass verification for phase transitions.
- Added `gate_passes` table to track successful gate checks with commit SHAs
- Gate checks cannot be skipped; code cannot be modified after gate passes without re-running

#### SPEC-005: Portable Installation
Added one-command installation scripts for setting up CLAMS with Qdrant and Claude Code integration.
- docker-compose.yml, scripts/install.sh, scripts/uninstall.sh
- scripts/json_merge.py for safe JSON configuration merging, scripts/verify_install.py

#### SPEC-006: Dual Embedding Model Support
Implemented dual embedding model architecture: MiniLM (384-dim, fast) for code, Nomic (768-dim, quality) for memories/GHAP.
- Added `EmbeddingRegistry` for lazy-loaded dual models
- Automatic dimension migration for existing collections

#### SPEC-008: HTTP Transport for Singleton MCP Server
Implemented HTTP transport enabling hooks to connect to a shared daemon instead of spawning new processes.
- HTTP+SSE transport with Starlette, /api/call endpoint, /health endpoint
- Daemon mode with PID file management
- Session tools and assemble_context tool
- Performance: session start < 100ms, user prompt < 200ms

#### SPEC-009: CLAMS Animated Explainer
Built a 90-second animated explainer using HTML5/CSS/JS with GSAP and Three.js.
- Act 1 (Value Proposition): Problem statement and CLAMS pillars
- Act 2 (Pipeline Visualization): 3D GHAP-to-Embedding-to-Clustering-to-Value Formation pipeline
- Act 3 (Context Injection): Session start, semantic retrieval, context window visualization
- WebGL memory leak prevention with proper cleanup

#### SPEC-010: Move CLAMS Files Out of .claude Directory
Relocated CLAMS installation files from `.claude/hooks/` to dedicated `clams/` directory.

#### SPEC-011: Strengthen Bug Investigation Protocol
Enhanced bug investigation gate checks to require rigorous differential diagnosis.
- Gate script validating at least 3 hypotheses, evidence, and fix plan
- Enhanced bug report template and bug-investigator role

#### SPEC-012: Add End-to-End Trace to Reviewer Checklist
Added mandatory end-to-end trace requirements to code reviewer checklist.
- Data flow trace, caller analysis, error path trace, integration point verification checklists

#### SPEC-013: Consolidate VALID_AXES import
Removed duplicate VALID_AXES definition from values/store.py, importing from enums module.

#### SPEC-014: Refactor search/results.py imports
Removed duplicate RootCause and Lesson class definitions, importing from canonical source.

#### SPEC-015: Add Searcher ABC inheritance regression test
Added parametrized test verifying method signatures between Searcher ABC and concrete implementation.

#### SPEC-016: Create schema generation utility for JSON schema enums
Added utility module for generating and validating JSON schema definitions from Python Enum classes (38 tests).

#### SPEC-017: Add schema conformance tests for enum validation
Added tests verifying Python Enum classes stay in sync with validation constants and JSON schemas.

#### SPEC-018: Cold-Start Integration Tests for Vector Store Collections
Added 16 integration tests covering all 5 collection types with lazy creation verification.

#### SPEC-019: Add input validation test suite for MCP tools
Added 236 tests covering all MCP tool categories for required fields, enum values, and range boundaries.

#### SPEC-020: Claude Code Hook Schema Conformance Tests
Fixed ghap_checkin.sh and outcome_capture.sh hooks to use correct hookSpecificOutput schema. Added schema definition tests.

#### SPEC-022: HTTP API Schema Tests
Added Pydantic schema definitions and tests for health endpoint, error responses, and CORS.

#### SPEC-023: Mock Interface Verification Tests
Added 39 tests verifying mock classes implement the same interface as production counterparts (prevents mock drift).

#### SPEC-024: Configuration Parity Verification
Added test framework detecting configuration drift between test fixtures and production code.

#### SPEC-025: Production Command Verification in Tests
Added utility ensuring integration tests use the same commands as production hooks.

#### SPEC-026: Pre-commit Hook for Heavy Import Detection
Added AST-based pre-commit hook detecting top-level imports of heavy packages (torch, sentence_transformers).

#### SPEC-027: Import Time Measurement Test
Added parametrized import time tests for 8 critical modules with 3.0s threshold.

#### SPEC-028: Document Fork/Daemon Constraint
Documented the constraint that torch/sentence_transformers must not be imported at module level due to MPS fork() incompatibility.

#### SPEC-029: Canonical Configuration Module
Centralized all configuration in ServerSettings with shell export capability for hooks and scripts.

#### SPEC-030: Cold-Start Testing Protocol
Added 53 cold-start tests covering all major MCP tool operations in empty-state scenarios.

#### SPEC-031: Cross-Component Integration Tests
Added 40 tests verifying contracts at component boundaries (storage, retrieval, context assembly, embedding).

#### SPEC-032: Type-Safe Datetime and Numeric Handling
Added type-safe utilities for datetime serialization and numeric validation (139 tests).

#### SPEC-033: Platform-Specific Pre-Checks
Added centralized platform detection with PlatformInfo dataclass and pytest markers for platform-specific tests.

#### SPEC-034: Parameter Validation with Production Data
Added data generators and 73 validation tests using production-like data profiles for parameter tuning.

#### SPEC-040: Gate Type-Specific Routing
Added registry-based dispatcher routing gate checks to type-specific scripts based on project type detection. Supports composite projects.

#### SPEC-041: Shell/Hooks Gate Check Script Enhancements
Added bash -n syntax checking, severity filtering, and changed-only mode for shell linting.

#### SPEC-042: Frontend Gate Check Script
Added dedicated gate check script for frontend changes with graceful non-npm handling.

#### SPEC-043: Update Valid Implementation Directories
Improved error messages in gate checks with references to .claude/project.json configuration.

#### SPEC-044: Response Size Assertions for GHAP Tests
Added 8 regression tests verifying GHAP tool responses stay within token-efficient size limits.

#### SPEC-045: Response Size Assertions for Memory Tools
Fixed store_memory and list_memories to return minimal responses; added regression tests.

#### SPEC-046: Token Counting Utility Tests
Added 20 tests for token estimation accuracy, edge cases, truncation, and budget distribution.

#### SPEC-047: Hash/eq contract tests for ContextItem
Added 19 tests with property-based testing (hypothesis) verifying Python's hash/eq contract.

#### SPEC-048: Hash/Eq Contract Tests for Other Hashable Classes
Extended hash/eq contract testing to PlatformInfo with reusable verify_hash_eq_contract() helper.

#### SPEC-049: Pre-commit Hook for Hash/Eq Contract
Added advisory pre-commit hook warning when classes define __hash__ or __eq__ without contract tests.

#### SPEC-050: Reviewer Checklist Bug Pattern Prevention (R17-A through R17-D)
Added bug pattern prevention checklist items to code reviewer role covering initialization, validation, parity, and type consistency.

#### SPEC-054: Update spec and proposal reviewer checklists (R17-E)
Added bug pattern prevention sections to spec-reviewer.md and proposal-reviewer.md.

#### SPEC-057: Add Validation to Remaining MCP Tool Parameters
Added reusable validation helpers and validation to 9 MCP tools with helpful error messages.

#### SPEC-058-01: CALM Foundation - Package structure and core infrastructure
Created the CALM Python package with Click CLI, database schema (8 tables), MCP server skeleton, daemon management, and pydantic-settings configuration.

#### SPEC-058-02: CALM Memory/GHAP
Ported memory, GHAP tracking, code indexing, git, and learning tools from clams to calm. Implemented embedding and storage layers.

#### SPEC-058-03: CALM Orchestration CLI
Implemented Python CLI commands replacing bash-based CLAWS scripts: task, gate, worktree, worker, review, counter, status, backup, and session commands (185+ tests).

#### SPEC-058-04: CALM Session and Reflection
Implemented session journaling MCP tools and CLI commands for the CALM learning loop (56 tests).

#### SPEC-058-06: CALM Install Script
Added `calm install` command with template bundling, atomic JSON writes, and idempotent installation (78 tests).

#### SPEC-058-07: CALM Cutover - Switch from Old to New System
One-off migration script with 8 sequential phases migrating data, configuration, and documentation from CLAMS/CLAWS to CALM (60 integration tests).

#### SPEC-058-08: CALM Cleanup - Remove Deprecated Code
Removed src/clams/ (74 files), .claude/roles/, .claude/hooks/, and ~200 stale test files. Repository now has single Python package (src/calm/).

#### TASK-001: Improve GHAP uptake via session start hook messaging
Revised GHAP instructions addressing psychological barriers to adoption with concrete examples and reframed quick-start messaging.

---

### Bug Fixes

#### BUG-001: GHAP strategy enum schema mismatch
Fixed schema mismatch where JSON schema defined incorrect strategy enum values (6 underscored values vs 9 hyphenated values).

#### BUG-002: Git tools auto-detection fix
Added automatic repository detection from current working directory when `repo_path` is not configured.

#### BUG-005: Fix internal server errors in search_experiences, validate_value, and store_value
Fixed missing `Clusterer` initialization causing AttributeError in clustering operations.

#### BUG-006: search_experiences KeyError fix
Fixed incomplete GHAP payload schema in Qdrant and timestamp format (ISO string instead of float).

#### BUG-008: Fix list_ghap_entries internal server error
Moved vector_store variable access from registration time to call time, fixing closure timing issue.

#### BUG-009: Fix validate_value internal server error
Added experience count validation before clustering; returns helpful error for insufficient data.

#### BUG-010: Fix store_value internal server error
Added error handling around clustering failures to return meaningful error messages.

#### BUG-011: Add missing index_commits MCP tool
Added the `index_commits` tool so users can populate the vector store before searching commits.

#### BUG-012: Fix index_codebase hanging on large directories
Added default exclusion patterns (.venv/, node_modules/, .git/, etc.) to prevent traversing dependency directories.

#### BUG-013: Fix search_commits AttributeError for missing score
Introduced `CommitSearchResult` wrapper to preserve similarity scores from search results.

#### BUG-014: Fix extreme memory usage in index_codebase (15GB+)
Fixed PyTorch MPS backend memory leak by forcing CPU execution when MPS is available.

#### BUG-015: Fix list_ghap_entries internal server error
Added ensure_collections() for lazy collection creation on first access.

#### BUG-016: Fix resolve_ghap internal server error
Added ensure_collections() before persisting resolved GHAP entries.

#### BUG-017: Fix get_clusters internal server error
Modified count_experiences() to return 0 when collections are missing; returns insufficient_data error.

#### BUG-019: validate_value returns internal server error
Fixed to conditionally include similarity field only when not None.

#### BUG-020: store_value returns internal server error
Added explicit ValueError handler returning validation_error instead of internal_error.

#### BUG-021: search_experiences returns internal server error
Added dataclass-to-dict conversion handling nested objects and datetime.

#### BUG-022: Pagination bug in _delete_file_units
Fixed to use while loop for complete deletion of files with more than 1000 semantic units.

#### BUG-023: Hardcoded dimension in NomicEmbedding
Changed dimension property to query model dynamically via get_sentence_embedding_dimension().

#### BUG-024: Error message mismatch between InMemoryVectorStore and Searcher
Standardized error messages to "not found" across 7 InMemoryVectorStore methods.

#### BUG-025: InMemoryVectorStore missing range filter support
Added operator-based filter support ($gte, $lte, $gt, $lt, $in) matching QdrantVectorStore behavior.

#### BUG-026: Enum mismatch between JSON schema and validation code
Replaced 17 hardcoded enum arrays with constant references from enums.py.

#### BUG-027: TypeError in list_ghap_entries datetime parsing
Changed datetime.fromtimestamp() to datetime.fromisoformat() for correct ISO format parsing.

#### BUG-028: Hash/Eq contract violation in ContextItem
Modified __hash__() to include len(self.content), fixing contract violation for set/dict operations.

#### BUG-029: GHAP start should error when active entry exists
Returns active_ghap_exists error with GHAP ID instead of silently orphaning entries.

#### BUG-030: GHAP tools should return minimal responses
Optimized start_ghap and resolve_ghap to return `{"ok": true, "id": "..."}`, saving ~500+ tokens per operation.

#### BUG-031: Clustering not forming with 63 GHAP entries
Changed HDBSCAN min_cluster_size from 5 to 3 and min_samples from 3 to 2.

#### BUG-033: MCP client spawns new server instead of using existing one
Fixed server binary path computation and config.yaml server command reference.

#### BUG-034: Float timeout truncation in QdrantVectorStore
Removed int() cast preserving float timeouts (preventing int(0.5) = 0 infinite wait).

#### BUG-036: KeyError in distribute_budget on invalid source type
Added input validation with descriptive ValueError for invalid context types.

#### BUG-037: Install script verification timeout due to model loading
Increased subprocess timeout from 5 to 30 seconds.

#### BUG-040: Duplicate result type definitions with incompatible fields
Consolidated result types to search/results.py as canonical source; fixed field name mismatches.

#### BUG-041: Searcher class conflict - abstract vs concrete incompatible interfaces
Made concrete Searcher inherit from SearcherABC; updated method signatures and imports.

#### BUG-042: Fix daemon crash on macOS due to MPS fork safety
Changed daemonize() to subprocess.Popen; deferred heavy imports; made embedding imports lazy.

#### BUG-043: Qdrant collections not auto-created on first use
Added lazy collection creation pattern to memory tools, GitAnalyzer, and ValueStore.

#### BUG-050: Fix SessionStart hook output not injected into context
Updated session_start.sh to use hookSpecificOutput JSON schema.

#### BUG-051: Fix UserPromptSubmit hook output not injected into context
Updated user_prompt_submit.sh to use hookSpecificOutput schema across all output locations.

#### BUG-052: Add global pytest timeout
Added pytest-timeout plugin with 60-second default timeout.

#### BUG-053: Gate script timeout with force-kill
Added post-completion timeout that force-kills pytest processes hanging after tests complete.

#### BUG-054: Test isolation fixture for resource leaks
Added resource_tracker fixture tracking and cleaning up leaked async tasks and threads.

#### BUG-055: Mark and exclude slow tests
Configured @pytest.mark.slow marker with default exclusion via addopts.

#### BUG-056: Pre-commit hook for subprocess.run stdin
Added pre-commit hook checking for subprocess calls without explicit stdin handling.

#### BUG-057: Document worker agent permission model
Documented explicit permission boundaries for worker agents in worktrees.

#### BUG-058: Auto-sync pip after worktree merge
Modified worktree merge to run `uv sync` after successful merge.

#### BUG-059: Add worktree health check command
Added `worktree health` command auditing stale worktrees, uncommitted changes, and behind-main branches.

#### BUG-060: Detect file overlaps when creating worktree
Added --check-overlaps and --force flags for conflict prevention between parallel tasks.

#### BUG-061: Centralize implementation directory list
Added .claude/project.json with configurable directory patterns for gate checks.

#### BUG-062: Auto-detect project type in gate checks
Added detect_project_type() supporting Python, JavaScript, Rust, Go with explicit override.

#### BUG-063: Add pre-merge conflict check
Added dry-run merge check before attempting worktree merges.

#### BUG-064: Auto-commit staged changes on wrapup
Modified session save to auto-commit staged changes in worktrees during wrapup.

#### BUG-065: Add next-commands to handoff format
Added next-commands subcommand with phase-aware action suggestions in status display.

#### BUG-066: Fix claws-worktree merge to auto-update task phase
Added auto-transition after merge (bug tasks to DONE, feature tasks to VERIFY).

#### BUG-067: MCP server registration uses wrong transport
Changed installer to use SSE transport instead of command-based (stdio) transport.

#### BUG-069: Fix calm init missing skills/ and journal/ directories
Added skills_dir and journal_dir to the directories list in init_cmd.py.

#### BUG-070: Add missing skills/ and journal/ directory checks to verification
Added skills_dir and journal_dir checks to verify_storage_directory() and step_verify().

#### BUG-071: Fix task list from worktrees, document --include-done, add next-id
Fixed task list to use detect_main_repo() for correct path resolution; added `calm task next-id` command.

#### BUG-072: /orchestrate skill not registered in Claude Code skills directory
Created skill wrapper templates for orchestrate, wrapup, and reflection; added step_register_skills() install step.

#### BUG-073: get_churn_hotspots uses wrong attribute names on ChurnRecord
Changed h.path to h.file_path and h.commit_count to h.change_count in git tools.
