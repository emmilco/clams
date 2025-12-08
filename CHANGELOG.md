# Changelog

All notable changes to the CLAMS (Claude Learning and Memory System) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

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
