# Changelog

All notable changes to the CLAMS (Claude Learning and Memory System) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### SPEC-057: Add Validation to Remaining MCP Tool Parameters
**Type**: Enhancement

Added comprehensive input validation to MCP tool parameters identified in the R4-A audit.

**Changes**:
- Added `src/clams/server/tools/validation.py` with reusable validation helpers
- Added validation to: assemble_context, retrieve_memories, store_memory, list_memories, delete_memory, search_code, index_codebase, update_ghap, distribute_budget
- All error messages include valid options or acceptable ranges
- Unified ValidationError usage across all tools

### SPEC-049: Pre-commit Hook for Hash/Eq Contract
**Type**: Testing

Created an advisory pre-commit hook that warns when classes define __hash__ or __eq__ without corresponding contract tests.

**Changes**:
- Added `.claude/hooks/check_hash_eq.py` for AST-based detection
- Detects __hash__, __eq__, and __hash__ = None patterns
- Checks for tests in `tests/context/test_data_contracts.py`
- Advisory mode (exits 0) to avoid blocking commits
- References BUG-028 in warnings for context

### SPEC-048: Hash/Eq Contract Tests for Other Hashable Classes (R16-B)
**Type**: Testing

Extended hash/eq contract testing beyond ContextItem to cover all hashable classes in the codebase.

**Changes**:
- Added `verify_hash_eq_contract()` reusable helper function in `tests/context/test_data_contracts.py`
- Added comprehensive audit documentation header with audit date (2026-01-28)
- Created `tests/utils/test_platform_contracts.py` with 6 contract tests for PlatformInfo
- Classes audited: ContextItem (already tested), PlatformInfo (new tests), Enums (excluded - Python guarantees their contract)

### SPEC-043: Update Valid Implementation Directories
**Type**: Enhancement

Improves error messages in claws-gate when the "Implementation code exists" check fails.

**Changes**:
- Updated error messages in claws-gate to list valid implementation directories from project.json
- Added reference to .claude/project.json configuration file in error output
- Provides helpful guidance for common scenarios (docs-only vs code changes)
- Updated both feature (IMPLEMENT-CODE_REVIEW) and bug (INVESTIGATED-FIXED) transitions

### SPEC-042: Frontend Gate Check Script
**Type**: Feature

Adds a dedicated gate check script for frontend (clams-visualizer) changes that gracefully handles non-npm projects.

**Changes**:
- Added `.claude/gates/check_frontend.sh` for frontend validation
- Runs `npm run lint` and `npm run typecheck` if configured in package.json
- Handles missing npm gracefully (exit code 2)
- Handles non-npm frontend projects gracefully (skip with exit 0)
- Reads frontend_dirs from project.json for configurable paths

### SPEC-041: Shell/Hooks Gate Check Script Enhancements
**Type**: Enhancement

Enhanced the shell linter gate script with bash -n syntax checking, severity filtering, and changed-only mode.

**Changes**:
- Added `bash -n` syntax checking before shellcheck
- Added `-S warning` severity threshold to shellcheck
- Added `CHECK_CHANGED_ONLY=1` environment variable for checking only changed files
- Added `clams_scripts/hooks/` to default script directories
- Improved exit code handling and error messages

### SPEC-034: Parameter Validation with Production Data
**Type**: Testing

Added data generators and validation tests that use production-like data profiles to catch parameter tuning issues.

**Changes**:
- Added `tests/fixtures/data_profiles.py` with profile dataclasses (EmbeddingProfile, GHAPDataProfile, MemoryProfile, CodeProfile, CommitProfile)
- Added `tests/fixtures/generators/` package with generators for embeddings, GHAP entries, temporal patterns, memories, code units, and commits
- Added `tests/validation/` test suite covering clustering, search pagination, memory operations, temporal patterns, and HDBSCAN parameter validation
- 73 validation tests marked with @pytest.mark.validation
- Addresses BUG-031 (clustering parameters too conservative)

### SPEC-033: Platform-Specific Pre-Checks
**Type**: Feature

Added centralized platform detection and pytest integration to handle platform-specific test requirements consistently.

**Changes**:
- Added `src/clams/utils/platform.py` with `PlatformInfo` dataclass, `get_platform_info()`, `check_requirements()`, and `format_report()` functions
- Added pytest markers: `requires_mps`, `requires_cuda`, `requires_ripgrep`, `requires_docker`, `requires_qdrant`, `macos_only`, `linux_only`
- Added `pytest_collection_modifyitems` hook to auto-skip tests when platform requirements not met
- Added `.claude/gates/check_platform.sh` for pre-flight platform capability reporting
- Modified `check_tests.sh` and `check_tests_python.sh` to distinguish platform skips (allowed) from code skips (fail gate)
- Migrated existing tests to use new markers instead of inline `skipif` decorators
- Addresses BUG-042 (MPS fork safety) and BUG-014 (memory leaks)

### SPEC-032: Type-Safe Datetime and Numeric Handling
**Type**: Feature

Added type-safe utilities for datetime serialization and numeric validation with comprehensive error handling.

**Changes**:
- Extended `src/clams/utils/datetime.py` with `is_valid_datetime_format()`, `serialize_datetime_optional()`, `deserialize_datetime_optional()`
- Added `src/clams/utils/numeric.py` with `safe_int()`, `clamp()`, `is_positive()`
- Added `src/clams/utils/validation.py` with `@validate_datetime_params()` and `@validate_numeric_range()` decorators
- Added 139 new tests covering edge cases, error messages, and timezone handling

### SPEC-031: Cross-Component Integration Tests
**Type**: Testing

Added integration tests verifying contracts at component boundaries, catching field mismatches and type incompatibilities.

**Changes**:
- Added `tests/integration/test_boundary_contracts.py` with 40 tests covering storage, retrieval, context assembly, and embedding service contracts
- Defined contract specifications: GHAP_PAYLOAD_CONTRACT, MEMORY_PAYLOAD_CONTRACT, etc.
- Added regression tests for BUG-006, BUG-019, BUG-027, BUG-036, BUG-040, BUG-041
- Tests verify field names match across storage, retrieval, and assembly layers

### SPEC-028: Document Fork/Daemon Constraint
**Type**: Documentation

Documents the critical constraint that torch/sentence_transformers must not be imported at module level due to MPS fork() incompatibility.

**Changes**:
- Added detailed docstring to `src/clams/server/main.py` explaining the fork/daemon constraint
- Documented why top-level imports of torch/sentence_transformers cause crashes
- Added references to BUG-037 and BUG-042 for historical context
- Made the constraint discoverable at the point of enforcement (daemonization)

### SPEC-025: Production Command Verification in Tests
**Type**: Testing

Ensures integration tests use the same commands as production hooks to prevent "works in test, fails in production" scenarios.

**Changes**:
- Added `get_server_command()` utility in tests/conftest.py that returns canonical server commands
- Supports both module invocation and binary entry point styles
- Updated integration tests to use this utility for consistency with production hooks
- Added comments documenting command parity requirements

### SPEC-023: Mock Interface Verification Tests
**Type**: Testing

Added systematic tests to verify mock classes implement the same interface as production counterparts, preventing mock drift bugs.

**Changes**:
- Added `tests/infrastructure/test_mock_parity.py` with 39 tests covering MockSearcher, MockEmbedder, and MockExperienceResult verification
- Helper functions: `get_public_methods()`, `compare_signatures()`, `compare_return_types()`
- Central registries: `get_all_mock_production_pairs()`, `get_all_mock_dataclass_pairs()`
- Added docstrings to mock classes referencing test_mock_parity.py
- Prevents BUG-040, BUG-041 class issues (mock field name mismatches)

### SPEC-017: Add Schema Conformance Tests for Enum Validation
**Type**: Testing

Added tests verifying Python Enum classes stay in sync with validation constants and JSON schemas.

**Changes**:
- Enhanced `tests/server/test_enum_schema_conformance.py` with Python enum validation tests
- Tests Domain, Strategy, and OutcomeStatus enums against their constants

### SPEC-016: Create Schema Generation Utility for JSON Schema Enums
**Type**: Feature

Added utility module for generating and validating JSON schema definitions from Python Enum classes.

**Changes**:
- Added `src/clams/utils/schema.py` with functions for enum schema generation and validation
- Added 38 tests in `tests/utils/test_schema.py`
- Updated `src/clams/utils/__init__.py` to export new functions

### SPEC-015: Add Searcher ABC Inheritance Regression Test
**Type**: Testing

Added parametrized test to verify method signatures between Searcher ABC and concrete implementation stay synchronized.

**Changes**:
- Added `test_method_signatures_match_abc` to `tests/search/test_searcher_interface.py`
- Tests all 5 search methods for parameter name consistency

### SPEC-012: Add End-to-End Trace to Reviewer Checklist
**Type**: Process

Added mandatory end-to-end trace requirements to the code reviewer checklist to prevent integration bugs from incomplete data flow analysis.

**Changes**:
- Added Step 3.5 "End-to-End Trace" section to `.claude/roles/reviewer.md` with:
  - Data flow trace checklist (entry points, transformations, return value usage)
  - Caller analysis checklist (all callers identified and verified)
  - Error path trace checklist (exception propagation, cleanup)
  - Integration point verification checklist
  - Helper grep commands for finding callers, imports, and exception handlers
  - Documentation template for trace summary
- Updated APPROVED report template to include Trace Summary section
- Added trace-related items to spec-reviewer.md and proposal-reviewer.md Bug Pattern Prevention sections

### SPEC-011: Strengthen Bug Investigation Protocol
**Type**: Process

Enhanced bug investigation gate checks to require rigorous differential diagnosis with evidence-based hypothesis elimination.

**Changes**:
- Added `.claude/gates/check_bug_investigation.sh` gate script validating:
  - At least 3 hypotheses considered
  - Exactly 1 CONFIRMED hypothesis
  - Evidence documented for eliminated hypotheses
  - Evidentiary scaffold code present
  - Captured output from scaffold
  - Fix plan references in bug report
- Updated `.claude/templates/bug-report.md` with requirements callout, example differential diagnosis, and evidentiary scaffold examples
- Enhanced `.claude/roles/bug-investigator.md` with evidence thresholds, anti-patterns, and self-review checklist
- Added 13 test cases in `tests/gates/test_check_bug_investigation.py`

### SPEC-054: Spec and Proposal Reviewer Checklist Updates (R17-E)
**Type**: Enhancement

Added bug pattern prevention checklist items to spec-reviewer.md and proposal-reviewer.md, enabling earlier detection of issues during the design phase.

**Changes**:
- Added "Bug Pattern Prevention" section to `.claude/roles/spec-reviewer.md`:
  - T3: Initialization requirements stated
  - T5: Input validation expectations
  - T7: Test requirements explicit
- Added "Bug Pattern Prevention" section to `.claude/roles/proposal-reviewer.md`:
  - T3: Initialization strategy defined
  - T5: Input validation strategy
  - T1/T2: Type location decided
  - T7: Test strategy covers production parity
- Cross-references to code reviewer checklist for implementation-phase checks

### SPEC-050: Reviewer Checklist Bug Pattern Prevention (R17-A through R17-D)
**Type**: Enhancement

Added bug pattern prevention checklist items to the code reviewer role, consolidating lessons learned from recurring bugs.

**Changes**:
- Added "Additional Checklist Items (Bug Pattern Prevention)" section to `.claude/roles/reviewer.md`
- Added Initialization Patterns (T3) checklist - catches missing `ensure_exists` calls (BUG-016, BUG-043)
- Added Input Validation (T5) checklist - catches missing input validation (BUG-029, BUG-036)
- Added Test-Production Parity (T7) checklist - catches test/production divergence (BUG-031, BUG-033, BUG-040)
- Added Type Consistency (T1, T2) checklist - catches duplicate types and missing inheritance (BUG-040, BUG-041)

### SPEC-047: Hash/Eq Contract Tests for ContextItem (R16-A)
**Type**: Testing

Added comprehensive tests to verify ContextItem maintains Python's hash/eq contract, preventing silent bugs in set/dict operations.

**Changes**:
- Added `tests/context/test_data_contracts.py` with 19 tests covering:
  - Hash/eq contract invariant verification
  - Edge cases (prefix collisions, unicode, whitespace, empty content)
  - Set membership and deduplication consistency
  - Dict key lookup consistency
  - Property-based testing with hypothesis
- Tests reference BUG-028 which originally identified the contract violation

### SPEC-046: Token Counting Utility Tests (R15-C)
**Type**: Testing

Added comprehensive tests for the token estimation utility to verify accuracy and catch edge cases.

**Changes**:
- Added 20 new tests to `tests/context/test_tokens.py` (32 total)
- `TestEstimateTokensAccuracy`: Verifies 4-char/token heuristic for English, code, JSON, markdown
- `TestEstimateTokensEdgeCases`: Covers single chars, Unicode (CJK, emojis), whitespace, long text
- `TestTruncateToTokensIntegrity`: Verifies budget enforcement and newline boundary handling
- `TestDistributeBudgetValidation`: Tests error handling and budget distribution

### SPEC-045: Response Size Assertions for Memory Tools (R15-B)
**Type**: Optimization

Added regression tests for memory tool response sizes and optimized memory.py to reduce token waste.

**Changes**:
- Added `TestMemoryResponseEfficiency` class in `tests/server/test_response_efficiency.py`
- 6 tests covering: store_memory, retrieve_memories, list_memories, delete_memory
- Fixed `store_memory` to return confirmation only (not echo content)
- Fixed `list_memories` to return metadata only (no content field)
- Verified size limits: store < 500 bytes, retrieve < 1000 bytes/entry, list < 500 bytes/entry, delete < 300 bytes

### SPEC-044: Response Size Assertions for GHAP Tests (R15-A)
**Type**: Testing

Added regression tests to verify GHAP tool responses stay within token-efficient size limits.

**Changes**:
- Added `TestGHAPResponseEfficiency` class in `tests/server/test_response_efficiency.py`
- 8 tests covering all GHAP tools: start, update, resolve, get_active, list
- Verified size limits: 500 bytes for simple operations, 2000 bytes for active GHAP with history
- Added minimum 10-byte checks to catch broken endpoints

### SPEC-030: Cold-Start Testing Protocol
**Type**: Testing

Added comprehensive cold-start testing infrastructure to catch bugs that only manifest on first use when no collections or data exist.

**Changes**:
- Added `tests/cold_start/` package with tests for memory, git, GHAP, and values operations
- Added `cold_start` pytest marker for selective test execution
- Added `cold_start_qdrant` and `cold_start_db` fixtures in `tests/fixtures/cold_start.py`
- Tests verify graceful handling of empty collections (no 404 errors, proper empty results)
- 53 new cold-start tests covering all major MCP tool operations

### SPEC-027: Import Time Measurement Tests
**Type**: Testing

Added comprehensive tests to measure and enforce import time limits for CLAMS modules, preventing accidental eager loading of heavy ML dependencies.

**Changes**:
- Added parametrized import time tests for 8 critical modules (clams, clams.server, clams.server.main, clams.server.http, clams.server.config, clams.embedding, clams.storage, clams.search)
- Added lazy import isolation tests verifying torch, sentence_transformers, and transformers are not loaded by light imports
- Added actionable error messages with diagnostic commands for import time violations
- Threshold set to 3.0s to accommodate legitimate web framework imports while catching PyTorch loads (4-6s+)

### SPEC-018: Cold-Start Integration Tests for Vector Store Collections
**Type**: Testing

Added integration tests that verify all vector store collections can be properly created on first use against a real Qdrant instance.

**Changes**:
- Added `tests/integration/test_cold_start_collections.py` with 16 integration tests
- Tests cover all 5 collection types: memories, commits, values, code_units, and GHAP collections
- Each test verifies: collection deletion, non-existence check, lazy creation, dimension verification (768), and data round-trip
- Tests fail (not skip) if Qdrant is unavailable, ensuring CI catches infrastructure issues

### SPEC-009: CLAMS Animated Explainer
**Type**: Feature

Built a 90-second animated explainer video for CLAMS using HTML5/CSS/JavaScript with GSAP animations and Three.js 3D visualizations. The explainer covers the GHAP learning loop, embedding/clustering pipeline, and context injection workflow.

**Changes**:
- Added `clams-visualizer/` directory with complete web-based animation
- **Act 1 - Value Proposition** (SPEC-009-02):
  - Problem statement scene: "AI Agents Lose Context"
  - CLAMS pillars: Semantic Code Search, Layered Working Memory, Hook-Based Injection
  - Smooth GSAP timeline animations with SVG icons
- **Act 2 - Pipeline Visualization** (SPEC-009-03, SPEC-009-04):
  - Three.js 3D foundation with scene, camera, renderer setup
  - Point cloud component with sprite-based rendering and dual depth cues
  - Cluster sphere component with translucent boundaries and wireframe
  - Centroid markers for cluster centers
  - Full GHAP -> Embedding -> Clustering -> Value Formation pipeline animation
- **Act 3 - Context Injection** (SPEC-009-05):
  - Claude Code session UI with user prompt
  - Semantic retrieval animation showing prompt-to-vector transformation
  - Context window visualization with injected values
  - Tagline and closing animation
- **Polish** (SPEC-009-06):
  - WebGL memory leak prevention with proper cleanup
  - CSS transforms for smooth entrance animations

### SPEC-008: HTTP Transport for Singleton MCP Server
**Type**: Feature

Implemented HTTP transport for the MCP server, enabling hooks to connect to a shared daemon instead of spawning new processes. This eliminates the 10+ second startup time per hook invocation.

**Changes**:
- Added HTTP+SSE transport support using Starlette (`src/clams/server/http.py`)
- Added `/api/call` endpoint for direct tool invocation by hook scripts
- Added `/health` endpoint for daemon health checks
- Implemented daemon mode with PID file management (`~/.clams/server.pid`)
- Implemented session management tools: `start_session`, `get_orphaned_ghap`, `should_check_in`, `increment_tool_count`, `reset_tool_count`
- Implemented `assemble_context` tool for context injection
- Updated all 4 hook scripts to use HTTP transport via `/api/call`
- Updated install/uninstall scripts for daemon lifecycle management

**Performance**:
- Session start hook: < 100ms (non-blocking, daemon starts in background)
- User prompt submit: < 200ms (after server warm)
- Models load once at daemon startup, stay in memory

### SPEC-005: Portable Installation
**Type**: Feature

Added one-command installation scripts for setting up CLAMS with Qdrant vector database and Claude Code integration.

**Changes**:
- Added `docker-compose.yml` for Qdrant vector database service
- Added `scripts/install.sh` for automated setup (Docker, Python deps, Claude config)
- Added `scripts/uninstall.sh` for clean removal
- Added `scripts/json_merge.py` for safe JSON configuration merging
- Added `scripts/verify_install.py` for installation verification
- Updated README.md with installation instructions
- Updated GETTING_STARTED.md with configuration guide

### SPEC-010: Move CLAMS Files Out of .claude Directory
**Type**: Refactor

Relocated CLAMS installation files from `.claude/hooks/` to a dedicated `clams/` directory to separate CLAMS (learning system) from CLAWS (orchestration system) concerns.

**Changes**:
- Moved hook scripts from `.claude/hooks/` to `clams/hooks/`
- Moved `mcp_client.py` from `.claude/hooks/` to `clams/`
- Updated `scripts/install.sh` and `scripts/uninstall.sh` with new paths
- Updated internal path calculations in hook scripts and mcp_client.py
- Updated test imports in `tests/hooks/test_mcp_client.py`

**Migration**: Users must re-run `./scripts/install.sh` to update hook registrations in `~/.claude/settings.json`.

### SPEC-006: Dual Embedding Model Support for Faster Code Indexing
**Type**: Feature

Implemented dual embedding model architecture to accelerate code indexing while maintaining quality for memory/GHAP operations. Code indexing now uses MiniLM (384-dim, fast) while memories/GHAP use Nomic (768-dim, quality).

**Changes**:
- Added `MiniLMEmbedding` class for fast code embeddings
- Added `EmbeddingRegistry` for lazy-loaded dual embedding models
- Added `code_model` and `semantic_model` to `ServerSettings` (configurable via env vars)
- Added `CollectionInfo` dataclass and `get_collection_info()` to `VectorStore` protocol
- Updated `ServiceContainer` to hold both `code_embedder` and `semantic_embedder`
- Updated `CodeIndexer._ensure_collection()` to handle dimension migration
- Updated server initialization to use embedding registry (models load on first use)
- Updated code tools to use `code_embedder` (MiniLM)
- Updated memory/GHAP/git tools to use `semantic_embedder` (Nomic)

**Migration**: Existing `code_units` collection will auto-recreate on first `index_codebase` call if dimension mismatches. No user action required.

### SPEC-004: Gate Pass Verification for Phase Transitions
**Type**: Feature

Implemented commit-anchored gate pass verification to ensure phase transitions cannot happen without proof that automated gate checks actually passed.

**Changes**:
- Added `gate_passes` table to track successful gate checks with commit SHAs
- Modified `claws-gate check` to record passes for test-requiring transitions
- Modified `claws-task transition` to verify gate passes before allowing transitions
- Covers transitions: IMPLEMENT-CODE_REVIEW, TEST-INTEGRATE, INVESTIGATED-FIXED, REVIEWED-TESTED

**Benefits**: Gate checks cannot be skipped, code cannot be modified after gate passes without re-running the gate, clear audit trail of what code state was tested.

### SPEC-003: Optimize MCP Protocol Test Performance
**Type**: Optimization

Reduced MCP protocol test execution time from ~130 seconds to ~8 seconds (17x improvement) by eliminating redundant server startups and embedding model loads.

**Changes**:
- Changed `mcp_session` test fixture from function-scoped to module-scoped, reducing server startups from 10 to 1 per test run
- Added `create_embedding_service()` function in `main.py` to load the embedding model once at startup
- Refactored initialization chain to pass embedding service through `run_server()`, `create_server()`, `register_all_tools()`, and `initialize_services()`
- Removed duplicate model loading from `validate_configuration()` and `initialize_services()`
- Added unit test for `create_embedding_service()` function

### SPEC-002-19: Hook Scripts and Context Injection
**Type**: Feature

Implemented Claude Code hook scripts that integrate the Learning Memory Server with agent sessions. Hooks run at specific conversation lifecycle points (session start, user prompt, tool calls) to inject context, check GHAP state, and auto-capture outcomes.

**Changes**:
- Added `.claude/hooks/mcp_client.py`: Python MCP client utility for shell scripts to call MCP tools
- Added `.claude/hooks/session_start.sh`: Initialize session state and inject light context
- Added `.claude/hooks/user_prompt_submit.sh`: Analyze user intent and inject rich context (v1: no domain detection)
- Added `.claude/hooks/ghap_checkin.sh`: Remind agent to update GHAP state periodically
- Added `.claude/hooks/outcome_capture.sh`: Auto-capture test/build outcomes and prompt for GHAP resolution
- Added `.claude/hooks/session_end.sh`: Session cleanup (future use, not yet supported by Claude Code)
- Added `.claude/hooks/config.yaml`: Hook configuration file
- Added comprehensive tests in `tests/hooks/test_mcp_client.py`
- All hooks use `set -uo pipefail` with explicit error handling and graceful degradation
- All Python code uses strict type hints and passes `mypy --strict`

**Implementation Notes**: v1 simplification - No domain-specific premortem detection. All hooks exit with code 0 (graceful degradation) even on errors.

### SPEC-002-17: Documentation and E2E Testing
**Type**: Feature

Completed the Learning Memory Server with minimal documentation and comprehensive E2E/performance testing.

**Changes**:
- Added GETTING_STARTED.md (98 lines) - navigation guide for AI agents
- Verified all 23 MCP tools have Google-style docstrings
- All public classes and functions documented
- Added E2E integration tests covering memory lifecycle, code workflow, git workflow, GHAP learning loop, context assembly, observation collector
- Added performance benchmarks: code search (p95 < 200ms), memory retrieval (p95 < 200ms), context assembly (p95 < 500ms), clustering (< 5s for 100 entries)
- Collection isolation using TEST_COLLECTIONS and BENCHMARK_COLLECTIONS
- No-skip policy: tests fail if Qdrant unavailable
- Benchmark results logged to `tests/performance/benchmark_results.json`
- Fixed Searcher.search_experiences() missing `strategy` parameter

**Test Results**: 508 tests passing, 84%+ coverage maintained.

### SPEC-002-16: Full Integration and Performance Tuning
**Type**: Feature

Completed critical integration work to transform independent modules into a working, functional Learning Memory Server. Fixed integration bugs, enabled all services, and implemented stub MCP tools.

**Changes**:
- Copied real `ObservationPersister` from main repo to replace stub class
- Fixed `ghap.py` line 374 to pass `GHAPEntry` directly instead of `.to_dict()`
- Imported real implementation to fix shadowing issue in `observation/__init__.py`
- Added `initialize_collections()` to create all 8 required collections on startup
- Added `validate_configuration()` with fail-fast validation for Qdrant connectivity
- Enabled Code and Git services with graceful degradation
- Implemented `search_experiences()`, `list_ghap_entries()`, `get_cluster_members()`, `list_values()` MCP tools
- Updated README.md with comprehensive installation, configuration, and usage instructions

### SPEC-002-15: MCP Tools for GHAP and Learning
**Type**: Feature

Implemented 11 MCP tools for GHAP tracking, learning/value formation, and semantic search.

**Changes**:
- Added 5 GHAP tools: `start_ghap`, `update_ghap`, `resolve_ghap`, `get_active_ghap`, `list_ghap_entries`
- Added 5 learning tools: `get_clusters`, `get_cluster_members`, `validate_value`, `store_value`, `list_values`
- Added 1 search tool: `search_experiences`
- Added custom exception types and enum validation
- Decorator-based registration using `@server.call_tool()`
- Exponential backoff retry logic (1s, 2s, 4s) for resolve_ghap persistence
- 65 tests passing (100% pass rate), ≥90% coverage on tools module

### SPEC-002-14: ObservationPersister Multi-Axis Embedding
**Type**: Feature

Implemented ObservationPersister to embed and store resolved GHAP entries using multi-axis embedding for semantic search.

**Changes**:
- Added `observation/persister.py` with ObservationPersister class
- Multi-axis embedding: full, strategy, surprise (falsified only), root_cause (falsified only)
- Template-based text rendering with optional field handling
- Collection management with `ensure_collections()`
- Comprehensive test suite (28 tests)

### SPEC-002-13: ValueStore Validation and Storage
**Type**: Feature

Implemented the ValueStore module for validating and storing agent-generated values derived from experience clusters.

**Changes**:
- Added `values/types.py` with dataclasses (ValidationResult, Value, ClusterInfo, Experience)
- Added `values/store.py` with ValueStore implementation
- Implemented validation using centroid distance threshold (mean + 0.5 * std)
- Added cluster access methods (get_clusters, get_cluster_members)
- Added value storage with embedding and metadata
- Added value listing with axis filtering and recency sorting
- Created comprehensive unit tests (28 test cases, 100% coverage)

### SPEC-002-12: Clusterer HDBSCAN
**Type**: Feature

Implemented HDBSCAN-based clustering for experiences and memories with weighted centroid computation.

**Changes**:
- Added `Clusterer` class wrapping scikit-learn HDBSCAN with configurable parameters
- Added `ExperienceClusterer` for experience clustering with confidence tier weights (gold=1.0, silver=0.8, bronze=0.5, abandoned=0.2)
- Added weighted centroid computation formula: `centroid = Σ(wᵢ * eᵢ) / Σ(wᵢ)`
- Added 10k scroll limit warning for large datasets
- Added `ClusterInfo` and `ClusterResult` dataclasses for type-safe results
- Added comprehensive test suite (36 tests)

### SPEC-002-11: MCP Tools for Memory, Code, Git
**Type**: Feature

Implemented 13 MCP tools across 3 modules (memory, code, git) that expose the Learning Memory Server's functionality through the Model Context Protocol.

**Changes**:
- Added `ServiceContainer` class for dependency injection
- Added `initialize_services()` with graceful degradation for optional dependencies
- Added 4 memory tools: `store_memory`, `retrieve_memories`, `list_memories`, `delete_memory`
- Added 3 code tools: `index_codebase`, `search_code`, `find_similar_code`
- Added 4 git tools: `search_commits`, `get_file_history`, `get_churn_hotspots`, `get_code_authors`
- Strict input validation with helpful error messages (no silent clamping/truncation)
- 42 unit tests covering all tools and validation cases

### SPEC-002-09: Searcher Unified Query Interface
**Type**: Feature

Implemented the Searcher module providing a unified, type-safe query interface for semantic search across all vector collections.

**Changes**:
- Added `Searcher` class with search methods for all collection types
- Added typed result dataclasses: `MemoryResult`, `CodeResult`, `ExperienceResult`, `ValueResult`, `CommitResult`
- Added `CollectionName` constants for collection name management
- Added exception classes for search errors
- Implemented filter translation layer for VectorStore compatibility
- Added comprehensive unit tests (35 tests)

### SPEC-002-07: GitReader + GitAnalyzer
**Type**: Feature

Implemented git history reading and semantic commit search with embedding-based indexing.

**Changes**:
- Added GitReader abstract base class for git repository access
- Implemented GitPythonReader using GitPython library
- Added GitAnalyzer for commit indexing and semantic search
- Implemented incremental indexing with state tracking
- Added commit search with filters (author, date range, path)
- Added churn analysis (get_churn_hotspots)
- Added blame search for code authorship
- Extended MetadataStore with git_index_state table
- Extended QdrantVectorStore with range query support ($gte, $lte)
- Full test coverage (38 tests)

### SPEC-002-06: CodeParser + CodeIndexer
**Type**: Feature

Implemented code parsing and indexing layer for semantic code search. Supports 9 languages (Python, TypeScript, JavaScript, Rust, Swift, Java, C, C++, SQL) using tree-sitter grammars.

**Changes**:
- Added `CodeParser` abstract interface for parsing code into semantic units
- Implemented `TreeSitterParser` with support for 9 languages
- Added `CodeIndexer` for embedding and storing parsed code units
- Implements change detection via mtime + content hash
- Batch embedding (100 units at a time) to prevent memory issues
- Error accumulation instead of fail-fast for partial indexing
- Comprehensive test coverage with fixtures for all supported languages

**Test Results**: 131 tests passed, 2 tests skipped (Lua parser not available, SQL parsing complex).

### SPEC-002-05: MCP Server Skeleton
**Type**: Feature

Implemented the MCP server framework with configuration and basic tool registration.

**Changes**:
- Added `Settings` class with pydantic-settings for environment configuration
- Created MCP server entry point with tool registration
- Added `ping` tool for health checks
- Structured logging with structlog
- Server configuration via environment variables

### SPEC-002-04: SQLite MetadataStore
**Type**: Feature

Implemented SQLite-based metadata storage for indexed files, call graphs, and projects.

**Changes**:
- Added `MetadataStore` class with async SQLite operations
- Indexed files tracking with project, path, hash, and timestamps
- Call graph storage for function relationships
- Project settings with JSON serialization
- Automatic schema initialization and migrations

### SPEC-002-03: VectorStore + QdrantVectorStore
**Type**: Feature

Implemented the vector storage abstraction with in-memory and Qdrant implementations.

**Changes**:
- Added `VectorStore` abstract base class with CRUD and search operations
- Added `InMemoryVectorStore` for testing and development
- Added `QdrantVectorStore` for production use with Qdrant
- String ID to UUID conversion for Qdrant compatibility
- Full test suite with Qdrant integration tests

### SPEC-002-02: EmbeddingService + NomicEmbedding
**Type**: Feature

Implemented the embedding abstraction layer with a mock implementation and Nomic embedding support.

**Changes**:
- Added `EmbeddingService` abstract base class with `embed()` and `embed_batch()` methods
- Added `MockEmbedding` implementation for testing (deterministic, dimension-configurable)
- Added `NomicEmbedding` implementation using nomic-embed-text-v1.5
- Tests for both implementations

### SPEC-002-01: Project Scaffolding
**Type**: Feature

Created the foundational project structure for the CLAMS server with Python packaging, linting, type checking, and testing infrastructure.

**Changes**:
- Added src layout with clams package and all module directories
- Added pyproject.toml with all production and development dependencies
- Configured ruff (line-length 88, Python 3.12)
- Configured mypy (strict mode)
- Configured pytest with pytest-asyncio (auto mode)
- Added .gitignore for Python projects
- Added README.md with setup instructions
- Added placeholder tests verifying project setup

**Notes**: Python requirement set to >=3.12 (3.13 deferred until tree-sitter-languages adds support).

---

## Bug Fixes

### BUG-071: Session start hook not using configurable port and host
**Type**: Bug Fix

Fixed test patterns to recognize both direct and indirect configuration patterns in session_start.sh.

**Changes**:
- Updated test patterns to accept two-step configuration (CLAMS_HTTP_PORT -> SERVER_PORT)
- Added comprehensive docstrings explaining valid patterns
- Fixed E2E test failure in test_session_start_uses_configurable_port

### BUG-066: Fix claws-worktree merge to auto-update task phase
**Type**: Bug Fix

Fixed a bug where `claws-worktree merge` would clear the worktree_path but not update the task phase, causing tasks to remain in stale phases after merge.

**Changes**:
- Modified `cmd_merge()` to query task_type and current_phase before merge
- Added auto-transition logic after successful merge:
  - Bug tasks -> DONE (merge is final step)
  - Feature tasks -> VERIFY (need verification on main)
- Added logging of phase transitions for visibility

### BUG-065: Add next-commands to handoff format
**Type**: Enhancement

Session handoffs now include actionable next commands based on task phases.

**Changes**:
- Added `next-commands` subcommand to `claws-session`
- Added `get_next_action()` function that returns correct commands for each task phase
- Added `describe_next_action()` for human-readable descriptions
- `claws-status` now displays next commands prominently when resuming from a handoff

### BUG-064: Auto-commit staged changes on wrapup
**Type**: Bug Fix

Added automatic commit of staged changes in worktrees during session wrapup.

**Changes**:
- Modified claws-session save to check all active worktrees for staged changes
- Automatically commits staged changes with descriptive message before wrapup
- Prevents uncommitted work from blocking operations in next session

### BUG-063: Add pre-merge conflict check
**Type**: Enhancement

Added conflict detection before attempting worktree merges to catch issues early.

**Changes**:
- Modified claws-worktree merge to perform a dry-run merge check first
- Warns if conflicts would occur and lists conflicting files
- Prevents surprise merge failures by detecting conflicts early

### BUG-062: Auto-detect project type in gate checks
**Type**: Enhancement

Gate checks now auto-detect project type and run appropriate language-specific tools.

**Changes**:
- Added `detect_project_type()` function to `claws-common.sh`
- Detects Python (pyproject.toml), JavaScript (package.json), Rust (Cargo.toml), Go (go.mod)
- Supports explicit override via `project_type` in `.claude/project.json`
- Gate checks dispatch appropriate test/lint/typecheck commands based on detected type

### BUG-061: Centralize implementation directory list
**Type**: Enhancement

Created central project configuration for directory patterns used in gate checks.

**Changes**:
- Added `.claude/project.json` with `implementation_dirs`, `test_dirs`, `script_dirs`, `doc_dirs`, and `frontend_dirs` arrays
- Updated `claws-gate` with `get_impl_dirs()`, `get_test_dirs()`, and `get_frontend_dirs()` helper functions
- Gate checks now read from project.json with sensible fallback defaults

### BUG-060: Detect file overlaps when creating worktree
**Type**: Enhancement

Added overlap detection to `claws-worktree create` to prevent merge conflicts between parallel tasks.

**Changes**:
- Added `--check-overlaps` flag to detect potential file conflicts before creating a worktree
- Added `--force` flag to bypass overlap warnings
- Added `check_overlaps()` function that scans all worktrees for uncommitted changes and file mentions in planning docs
- Reports conflicting task IDs with recommendations for resolution

### BUG-059: Add worktree health check command
**Type**: Enhancement

Added a health check subcommand to claws-worktree for auditing worktree state.

**Changes**:
- Added `claws-worktree health` command that audits all worktrees
- Reports stale worktrees (task DONE but worktree not cleaned)
- Reports uncommitted changes that may block operations
- Reports worktrees behind main branch

### BUG-058: Auto-sync pip after worktree merge
**Type**: Enhancement

Added automatic dependency sync after worktree merges to prevent import failures when new dependencies are added.

**Changes**:
- Modified claws-worktree merge to run `uv sync` after successful merge
- Dependencies are now automatically installed when a worktree with new deps is merged
- Added regression test to verify sync runs after merge

### BUG-057: Document worker agent permission model
**Type**: Documentation

Investigated and documented the permission model for worker agents operating in worktrees.

**Changes**:
- Documented explicit permission boundaries in CLAUDE.md for worker agents
- Added guidelines for file/directory restrictions in worker prompts
- Created framework for future technical enforcement of scope boundaries

### BUG-056: Pre-commit hook for subprocess.run stdin
**Type**: Enhancement

Added a pre-commit hook that checks for subprocess.run/Popen calls without explicit stdin handling.

**Changes**:
- Added custom hook to .pre-commit-config.yaml that greps for subprocess calls without stdin=
- Hook prevents commits with subprocess calls that could hang waiting for input
- Added regression test to verify the check works

### BUG-055: Mark and exclude slow tests
**Type**: Enhancement

Configured pytest to support a `@pytest.mark.slow` marker and exclude slow tests from default runs.

**Changes**:
- Added `slow` marker definition to pyproject.toml
- Configured default addopts to exclude slow tests with `-m "not slow"`
- Tests taking >15 seconds can now be marked and excluded from gate checks

### BUG-054: Test isolation fixture for resource leaks
**Type**: Enhancement

Added a pytest fixture that tracks and cleans up resources (async tasks, threads) created during tests, making resource leaks explicit failures.

**Changes**:
- Added `resource_tracker` fixture to tests/conftest.py that captures baseline state before each test
- Fixture compares state after test and attempts cleanup of leaked resources
- Tests explicitly fail if cleanup was required, preventing silent hangs

### BUG-053: Gate script timeout with force-kill
**Type**: Bug Fix

Added a post-completion timeout mechanism to the gate script that force-kills pytest processes that hang after tests complete.

**Changes**:
- Added cleanup timer in claws-gate that starts after tests complete
- Implemented force-kill if pytest doesn't exit within 30 seconds
- Gate now fails (rather than passes) when cleanup timeout occurs, since cleanup failure indicates a resource leak

### BUG-052: Add global pytest timeout
**Type**: Bug Fix

Added pytest-timeout plugin with a 60-second default timeout to prevent tests from hanging indefinitely.

**Changes**:
- Added `pytest-timeout` to dev dependencies in pyproject.toml
- Configured `timeout = 60` in pytest.ini_options section
- Added regression test to verify timeout configuration is active

### BUG-051: Fix UserPromptSubmit hook output not injected into context
**Type**: Bug Fix

Fixed the `user_prompt_submit.sh` hook to use Claude Code's expected JSON schema so that relevant experiences are properly injected into Claude's context based on user prompts.

**Root Cause**: The hook was outputting `{"type": ..., "content": ..., "token_count": ...}` instead of the required `{"hookSpecificOutput": {"additionalContext": "..."}}` schema.

**Changes**:
- Updated `clams/hooks/user_prompt_submit.sh` to output correct JSON schema
- Updated all three output locations (success case and two degraded cases)
- Added regression test to prevent schema regression

### BUG-050: Fix SessionStart hook output not injected into context
**Type**: Bug Fix

Fixed the `session_start.sh` hook to use Claude Code's expected JSON schema so that GHAP instructions are properly injected into Claude's context at session start.

**Root Cause**: The hook was outputting `{"type": ..., "content": ...}` instead of the required `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}` schema.

**Changes**:
- Updated `clams/hooks/session_start.sh` to output correct JSON schema with `hookEventName` field
- Added regression test to prevent schema regression

### BUG-043: Qdrant collections not auto-created on first use
**Type**: Bug Fix

Fixed 404 errors when using memory, git commit, and value tools on fresh installations where Qdrant collections don't exist.

**Root Cause**: Tools assumed collections existed and failed with 404 errors instead of auto-creating them.

**Changes**:
- Added lazy collection creation (`_ensure_*_collection()` pattern) to memory tools, GitAnalyzer, and ValueStore
- Collections are now automatically created on first use
- Pattern follows existing `CodeIndexer._ensure_collection()` implementation

### BUG-042: Fix daemon crash on macOS due to MPS fork safety
**Type**: Bug Fix

Fixed a critical bug where the CLAMS daemon crashed immediately after starting on macOS with Apple Silicon.

**Root Cause**: The daemon used `os.fork()` for daemonization, but PyTorch MPS crashes when `fork()` is called after MPS initialization (which happens automatically when torch is imported on Apple Silicon Macs).

**Changes**:
- Changed `daemonize()` to use `subprocess.Popen(start_new_session=True)` instead of `os.fork()`
- Restructured `main.py` to defer all heavy imports until after daemonization
- Made embedding module imports lazy - concrete classes imported only when accessed
- Updated test imports to use specific module paths

### BUG-041: Searcher class conflict - abstract vs concrete incompatible interfaces
**Type**: Bug Fix

Fixed Searcher class inheritance so the concrete implementation properly inherits from the abstract Searcher ABC.

**Root Cause**: The concrete `Searcher` in `search/searcher.py` and abstract `SearcherABC` in `context/searcher_types.py` had incompatible method signatures, causing type errors.

**Changes**:
- Made concrete `Searcher` class inherit from `SearcherABC`
- Updated ABC method signatures to include all optional parameters
- Removed `Searcher` from `search/__init__.py` exports to avoid circular import
- Updated import statements across codebase

### BUG-040: Duplicate result type definitions with incompatible fields
**Type**: Bug Fix

Fixed type inconsistency between `context/searcher_types.py` and `search/results.py` that caused KeyError and AttributeError when using `ContextAssembler` with the concrete `Searcher` implementation.

**Root Cause**: Two independent type definitions had different field names (`start_line` vs `line_start`, `cluster_size` vs `member_count`, dict vs dataclass for `Lesson`).

**Changes**:
- Consolidated result types to use `search/results.py` as canonical source
- Updated `context/searcher_types.py` to re-export from `search/results`
- Fixed field name mismatches in formatters

### BUG-037: Install script verification timeout due to model loading
**Type**: Bug Fix

Fixed install script verification timeout caused by insufficient timeout value when loading heavy ML dependencies.

**Changes**:
- Increased subprocess timeout from 5 to 30 seconds in `scripts/verify_install.py`

### BUG-036: KeyError in distribute_budget on invalid source type
**Type**: Bug Fix

Fixed unhelpful KeyError when `distribute_budget()` is called with invalid context types.

**Root Cause**: The function accessed `SOURCE_WEIGHTS[t]` without first validating that `t` was a valid key.

**Changes**:
- Added input validation at the start of `distribute_budget()` in `src/clams/context/tokens.py`
- Invalid context types now raise a descriptive `ValueError` listing both invalid types and valid options

### BUG-034: Float timeout truncation in QdrantVectorStore may cause zero timeout
**Type**: Bug Fix

Fixed float timeout values being truncated to integers, which could cause 0.5s timeouts to become 0 (infinite wait).

**Root Cause**: The `int()` truncation converted `int(0.5) = 0`, which in httpx means "no timeout" (infinite wait).

**Changes**:
- Removed `int()` cast on timeout values in `QdrantVectorStore.__init__`
- Float timeouts are now passed directly to `AsyncQdrantClient`

### BUG-033: MCP client spawns new server instead of using existing one
**Type**: Bug Fix

Fixed the MCP hook client to use the correct server binary path, resolving slow hook startup times and connection failures.

**Root Cause**: The MCP client was using an incorrect server command that referenced a non-existent module entry point, causing connection failures and 10+ second delays.

**Changes**:
- Updated `mcp_client.py` to compute the correct absolute path to `.venv/bin/clams-server`
- Fixed `config.yaml` to reference the correct server command

### BUG-031: Clustering not forming with 63 GHAP entries
**Type**: Bug Fix

Fixed HDBSCAN parameters that were too conservative for typical GHAP data distributions, causing all points to be classified as noise.

**Root Cause**: Default `min_cluster_size=5` and `min_samples=3` were too conservative for datasets with 20-100 thematically similar entries.

**Changes**:
- Changed `min_cluster_size` from 5 to 3
- Changed `min_samples` from 3 to 2

### BUG-030: GHAP tools should return minimal responses to reduce token usage
**Type**: Bug Fix

Optimized `start_ghap` and `resolve_ghap` to return minimal responses instead of echoing back full records.

**Changes**:
- Modified `start_ghap` to return `{"ok": true, "id": ghap_id}` instead of 8 fields
- Modified `resolve_ghap` to return `{"ok": true, "id": ghap_id}` instead of 4 fields
- Reduces token waste by ~500+ tokens per GHAP operation

### BUG-029: GHAP start should error when active entry exists
**Type**: Bug Fix

Fixed `start_ghap` to return a helpful error when an active GHAP entry already exists instead of silently orphaning it.

**Changes**:
- Modified `start_ghap` handler to check for active entry and return `active_ghap_exists` error type
- Error message now includes the active GHAP ID and suggests using `resolve_ghap`

### BUG-028: Hash/Eq contract violation in ContextItem
**Type**: Bug Fix

Fixed hash/eq contract violation in `ContextItem` class that caused incorrect behavior when using items in sets or as dict keys.

**Root Cause**: The `__hash__()` method only used `source` and first 100 characters of content, but `__eq__()` also compared full content length. This violated Python's hash/eq contract: equal objects must have equal hashes.

**Changes**:
- Modified `__hash__()` to include `len(self.content)` in the hash tuple
- Items with same source and prefix but different lengths now hash differently
- Maintains performance by still only hashing first 100 characters

### BUG-027: TypeError in list_ghap_entries datetime parsing
**Type**: Bug Fix

Fixed TypeError when parsing datetime in `list_ghap_entries` due to format mismatch between storage and retrieval.

**Root Cause**: The persister stores datetimes as ISO format strings, but `list_ghap_entries` was using `datetime.fromtimestamp()` expecting Unix timestamps.

**Changes**:
- Changed `datetime.fromtimestamp()` to `datetime.fromisoformat()` in ghap.py line 563
- Now correctly parses ISO format strings stored by the persister

### BUG-026: Enum mismatch between JSON schema and validation code
**Type**: Bug Fix

Fixed enum mismatch between MCP tool JSON schemas and validation code that caused validation errors for schema-advertised values.

**Root Cause**: Tool schemas had hardcoded enum arrays that drifted from the canonical enums in `enums.py`, causing clients using schema-compliant values to fail validation.

**Changes**:
- Imported all enum constants from `enums.py` into tool schemas
- Replaced 17 hardcoded enum arrays with constant references (DOMAINS, STRATEGIES, ROOT_CAUSE_CATEGORIES, OUTCOME_STATUS_VALUES, VALID_AXES)
- Ensures schema and validation code cannot drift apart

### BUG-025: InMemoryVectorStore missing range filter support
**Type**: Bug Fix

Fixed missing range filter support in `InMemoryVectorStore._apply_filters()` that caused date-filtered searches to return empty results.

**Root Cause**: `InMemoryVectorStore` only supported simple equality filters, while `QdrantVectorStore` supported operator-based filters ($gte, $lte, etc.). Code using date range filters worked in production but failed in tests.

**Changes**:
- Enhanced `_apply_filters()` to detect and handle operator-based filters
- Added `_match_operators()` helper supporting `$gte`, `$lte`, `$gt`, `$lt`, `$in` operators
- Maintains backward compatibility with simple equality filters
- Now matches QdrantVectorStore filter behavior

### BUG-024: Error message mismatch between InMemoryVectorStore and Searcher
**Type**: Bug Fix

Fixed error message inconsistency that prevented proper error conversion in the Searcher class when using InMemoryVectorStore.

**Root Cause**: `InMemoryVectorStore` raised errors with "does not exist" message while `Searcher` expected "not found" pattern for `CollectionNotFoundError` conversion.

**Changes**:
- Changed all error messages in `InMemoryVectorStore` from "does not exist" to "not found"
- Now matches the pattern expected by Searcher's `CollectionNotFoundError` conversion logic
- Updated 7 methods: delete_collection, search, upsert, scroll, count, get, delete

### BUG-023: Hardcoded dimension in NomicEmbedding
**Type**: Bug Fix

Fixed hardcoded embedding dimension in `NomicEmbedding` that caused vector store mismatches when using models with different dimensions.

**Root Cause**: The `dimension` property returned a hardcoded `768` value instead of querying the actual model, causing failures when the model's actual dimension differed.

**Changes**:
- Removed hardcoded `_DIMENSION = 768` constant
- Changed `dimension` property to query the model via `get_sentence_embedding_dimension()`
- Added error handling for when model returns `None`

### BUG-022: Pagination bug in _delete_file_units
**Type**: Bug Fix

Fixed a pagination bug in `CodeIndexer._delete_file_units()` that left orphaned entries in the vector store when a file had more than 1000 semantic units.

**Root Cause**: The method called `scroll()` only once, fetching the first 1000 entries and deleting them, but never continuing to fetch subsequent pages.

**Changes**:
- Modified `_delete_file_units()` to use a `while True` loop instead of a single `scroll()` call
- Now continues deleting until all entries are removed, regardless of count
- Added `total_deleted` counter for accurate logging

### BUG-021: search_experiences returns internal server error
**Type**: Bug Fix

Fixed internal server error in search_experiences tool by converting ExperienceResult dataclasses to JSON-serializable dictionaries.

**Changes**:
- Added dataclass-to-dict conversion in search_experiences tool return path
- Handles nested objects (root_cause, lesson) and datetime conversion
- Added regression test to verify JSON serializability

### BUG-020: store_value returns internal server error (regression)
**Type**: Bug Fix

Fixed internal server error in store_value tool when ValueError is raised by ValueStore.

**Changes**:
- Added explicit ValueError handler in store_value tool to return validation_error instead of internal_error
- Added regression test to verify ValueError is properly handled

### BUG-019: validate_value returns internal server error (regression)
**Type**: Bug Fix

Fixed internal server error in validate_value tool when similarity is None.

**Changes**:
- Modified validate_value tool to conditionally include similarity field only when not None
- Added regression test to verify similarity is omitted when None

### BUG-017: Fix get_clusters internal server error
**Type**: Bug Fix

Fixed `get_clusters` MCP tool returning internal server error when GHAP collections don't exist.

**Changes**:
- Modified `count_experiences()` in `experience.py` to return 0 when GHAP collections are missing
- Modified `cluster_axis()` to catch collection-not-found errors and raise a clear ValueError
- Tool now correctly returns `insufficient_data` error instead of `internal_error`

### BUG-016: Fix resolve_ghap internal server error
**Type**: Bug Fix

Fixed `resolve_ghap` MCP tool returning internal server error when attempting to persist resolved GHAP entries due to missing vector collections.

**Changes**:
- Added `ensure_collections()` call in `resolve_ghap` tool before persisting to create GHAP collections if they don't exist
- Ensures GHAP entries can be properly persisted to vector store on resolution

### BUG-015: Fix list_ghap_entries internal server error
**Type**: Bug Fix

Fixed a regression where `list_ghap_entries` MCP tool returned internal server error due to missing GHAP collections.

**Changes**:
- Added `ensure_collections()` call in `list_ghap_entries` tool to create GHAP collections if they don't exist
- Collections are now lazily created on first access rather than requiring pre-initialization

---

## Bug Fixes (Historical)

### BUG-014: Fix extreme memory usage in index_codebase (15GB+)
**Type**: Bug Fix

Fixed PyTorch MPS backend memory leak that caused 15+ GB memory usage and severe performance degradation when running `index_codebase` on Apple Silicon Macs.

**Root Cause**: The embedding model automatically loaded on Apple's MPS (GPU) device. PyTorch's MPS backend has known memory management issues where GPU memory allocated for tensors is not properly released.

**Changes**:
- Modified `NomicEmbedding.__init__` to force CPU execution when MPS is available
- Added `torch` import for device detection
- Added 3 comprehensive regression tests to verify the fix

### BUG-013: Fix search_commits AttributeError for missing score
**Type**: Bug Fix

Fixed `search_commits` MCP tool failing with `'Commit' object has no attribute 'score'` by introducing a `CommitSearchResult` wrapper class.

**Root Cause**: `GitAnalyzer.search_commits()` was discarding the similarity score when converting from `SearchResult` to `Commit` objects.

**Changes**:
- Added `CommitSearchResult` dataclass in `git/base.py`
- Modified `GitAnalyzer.search_commits()` to return `list[CommitSearchResult]`
- Updated tool handler to access commit data through the wrapper
- Added regression test

### BUG-012: Fix index_codebase hanging on large directories
**Type**: Bug Fix

Fixed `index_codebase` MCP tool hanging when indexing directories containing `.venv/`, `node_modules/`, or other dependency directories.

**Root Cause**: The MCP tool was not passing `exclude_patterns` to `index_directory()`, causing the indexer to traverse tens of thousands of files in virtual environments and dependency directories.

**Changes**:
- Added default exclusion patterns to `index_codebase` in `server/tools/code.py`
- Exclusions include: `.venv/`, `venv/`, `node_modules/`, `.git/`, `__pycache__/`, `dist/`, `build/`, `target/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `htmlcov/`, `.coverage`, `*.egg-info/`
- Added regression tests

### BUG-011: Add missing index_commits MCP tool
**Type**: Bug Fix

Added the missing `index_commits` MCP tool so users can populate the vector store before using `search_commits`.

**Changes**:
- Added `index_commits` tool definition with schema for `since`, `limit`, `force` parameters
- Implemented tool with proper validation and error handling
- Registered tool in the tool registry
- Added comprehensive regression tests for the index-then-search workflow

### BUG-010: Fix store_value internal server error
**Type**: Bug Fix

Fixed `store_value` MCP tool returning internal server error when clustering fails due to insufficient data.

**Changes**:
- Added try-except around `clusterer.cluster_axis()` in `ValueStore.get_clusters()` to re-raise with context
- Added try-except in `validate_value_candidate()` to catch clustering errors and return validation failure
- Provides meaningful error messages instead of generic internal server error

### BUG-009: Fix validate_value internal server error
**Type**: Bug Fix

Fixed `validate_value` MCP tool returning internal server error when fewer than 20 experiences exist for clustering.

**Changes**:
- Added experience count validation in `ValueStore.get_clusters()` before calling clusterer
- Added try-except in `validate_value_candidate()` to return `ValidationResult(valid=False)` instead of raising
- Returns helpful error message about insufficient experiences

### BUG-008: Fix list_ghap_entries internal server error
**Type**: Bug Fix

Fixed `list_ghap_entries` MCP tool returning internal server error by moving vector_store variable access from registration time to call time.

**Changes**:
- Moved `vector_store = persister._vector_store` from `get_ghap_tools()` scope into `list_ghap_entries` function body
- Eliminates closure timing issue where vector_store was captured before initialization
- Added MCP protocol regression test to verify the fix

### BUG-006: search_experiences KeyError fix
**Type**: Bug Fix

Fixed KeyError when calling search_experiences, validate_value, and store_value MCP tools due to incomplete GHAP payload schema in Qdrant.

**Changes**:
- Added missing GHAP content fields to Qdrant payload in ObservationPersister._build_axis_metadata()
- Fixed timestamp format (ISO string instead of float) for proper deserialization
- Added comprehensive regression tests covering all affected MCP tools

### BUG-005: Fix internal server errors in search_experiences, validate_value, and store_value
**Type**: Bug Fix

Fixed missing `Clusterer` initialization causing these MCP tools to return internal server errors.

**Root Cause**: The tools were initialized with `clusterer=None`, causing `AttributeError` when attempting clustering operations.

**Changes**:
- Added `Clusterer` instance initialization in `server/tools/__init__.py`
- Properly wired `Clusterer` → `ExperienceClusterer` → `ValueStore` dependency chain
- Removed type ignore comments that were masking None values
- Added regression tests to verify clusterer initialization

### BUG-002: Git tools auto-detection fix
**Type**: Bug Fix

Fixed git tools returning "not available" errors by adding automatic repository detection from the current working directory when `repo_path` is not explicitly configured.

**Root Cause**: The `initialize_services()` function only created a `GitAnalyzer` when `settings.repo_path` was explicitly configured. Since most users don't set the `CLAMS_REPO_PATH` environment variable, git tools were never initialized.

**Changes**:
- Added auto-detection logic in `initialize_services()` using GitPython's `Repo(search_parent_directories=True)`
- Updated config docstring to document auto-detection behavior
- Added regression tests for auto-detection, explicit config override, and graceful failure scenarios

### BUG-001: GHAP strategy enum schema mismatch
**Type**: Bug Fix

Fixed a schema mismatch bug where the JSON schema for `start_ghap` and `update_ghap` MCP tools defined incorrect strategy enum values, causing validation errors when clients used the schema-compliant values.

**Root Cause**: The JSON schema was never updated when the strategy enum values were finalized during initial implementation. The schema had 6 underscored values while the server validated against 9 hyphenated values.

**Changes**:
- Updated strategy enum in `start_ghap` tool definition from outdated underscored values to correct hyphenated values
- Updated strategy enum in `update_ghap` tool definition with the same fix
- Added regression test to prevent future drift between JSON schema and server validation
