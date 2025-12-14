# Recommendation Tickets: R5-R8

## R5: External API Schema Conformance Tests

**Overall Priority**: P1 - High impact (prevents API contract bugs like BUG-050, BUG-051)
**Addresses Themes**: T1 (Schema/Type Inconsistency), T11 (Documentation vs Implementation Drift)

### R5-A: Claude Code Hook Schema Conformance Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: none

**Problem Statement**:
BUG-050 and BUG-051 were caused by hooks outputting JSON in a custom format (`{"type": ..., "content": ...}`) instead of Claude Code's required schema (`{"hookSpecificOutput": {"additionalContext": ...}}`). This was caught only after deployment. Conformance tests would catch schema mismatches before they reach production.

**Acceptance Criteria**:
- [ ] Test file exists at `tests/hooks/test_hook_schemas.py`
- [ ] Tests verify `session_start.sh` output matches Claude Code SessionStart schema
- [ ] Tests verify `session_end.sh` output matches Claude Code SessionEnd schema
- [ ] Tests verify `user_prompt_submit.sh` output matches Claude Code UserPromptSubmit schema
- [ ] Expected schemas are stored in `tests/fixtures/claude_code_schemas/` with links to authoritative documentation
- [ ] Tests run in CI and fail if hook output doesn't match expected schema

**Implementation Notes**:
- Hook scripts are located at `clams/hooks/*.sh`
- Current correct schema structure (from `clams/hooks/session_start.sh` lines 193-210):
  ```json
  {
    "hookSpecificOutput": {
      "hookEventName": "SessionStart",
      "additionalContext": "<string>"
    }
  }
  ```
- Tests should execute hooks with mocked dependencies and validate JSON structure
- Consider using `jsonschema` library for validation
- Document schema source: https://docs.anthropic.com/en/docs/claude-code/hooks

**Testing Requirements**:
- Run each hook script in isolation with mocked dependencies
- Parse output as JSON and validate against schema
- Test both success and error paths

---

### R5-B: MCP Tool Response Schema Tests

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: none (can run in parallel with R5-A)

**Problem Statement**:
MCP tool responses must match the schemas advertised in `_get_all_tool_definitions()` in `src/clams/server/tools/__init__.py`. BUG-026 showed that advertised enums can drift from actual validation. Tests should verify that tool responses match advertised schemas.

**Acceptance Criteria**:
- [ ] Test file exists at `tests/server/test_tool_response_schemas.py`
- [ ] For each MCP tool, tests verify response structure matches advertised output format
- [ ] Tests exercise at least one success and one error case per tool
- [ ] Tests validate that enum values in responses are valid per schema

**Implementation Notes**:
- Tool definitions are in `src/clams/server/tools/__init__.py` (lines 178-832)
- Focus on tools with enum fields: GHAP tools (domain, strategy, outcome), search tools (axis)
- Enum values are imported from `src/clams/server/tools/enums.py`
- Example validation pattern:
  ```python
  def test_start_ghap_response_schema():
      response = await tool_registry["start_ghap"](...)
      # Verify response contains expected fields
      assert "ghap_id" in response or "error" in response
      if "domain" in response:
          assert response["domain"] in DOMAINS
  ```

**Testing Requirements**:
- Use integration test fixtures with real services
- Validate enum fields against canonical sources in `enums.py`
- Document any schema constraints not captured in the MCP definition

---

### R5-C: HTTP API Schema Tests

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: none (can run in parallel with R5-A, R5-B)

**Problem Statement**:
The HTTP API at `/api/call` (used by hooks to communicate with the MCP server) has implicit schema requirements. BUG-033 showed configuration mismatches between hooks and server. Schema tests ensure the HTTP interface contract is documented and verified.

**Acceptance Criteria**:
- [ ] Test file exists at `tests/server/test_http_schemas.py`
- [ ] Tests verify request schema for `/api/call` endpoint
- [ ] Tests verify response schema for success and error cases
- [ ] Tests verify JSON-RPC style request format

**Implementation Notes**:
- HTTP server is in `src/clams/server/http.py`
- Hooks call HTTP API (see `clams/hooks/session_start.sh` lines 63-76):
  ```bash
  request=$(jq -n --arg name "$tool_name" --argjson args "$args" \
      '{method: "tools/call", params: {name: $name, arguments: $args}}')
  curl ... -d "$request"
  ```
- Expected request schema:
  ```json
  {
    "method": "tools/call",
    "params": {"name": "<tool_name>", "arguments": {...}}
  }
  ```

**Testing Requirements**:
- Start HTTP server in test fixture
- Send requests with various schemas and verify responses
- Test malformed requests return appropriate errors

---

## R6: Test-Production Parity Verification

**Overall Priority**: P1 - High impact (prevents "works in test, fails in production" bugs)
**Addresses Themes**: T7 (Test-Production Divergence)

### R6-A: Mock Interface Verification Tests

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: none

**Problem Statement**:
BUG-040 and BUG-041 showed that `MockSearcher` in tests didn't match the production `Searcher` interface. Tests passed but production failed. This ticket adds tests that verify mock classes implement the same interface as their production counterparts.

**Acceptance Criteria**:
- [ ] Test file exists at `tests/infrastructure/test_mock_parity.py`
- [ ] Tests verify `MockSearcher` (in `tests/context/test_assembler.py`) has all methods of production `Searcher`
- [ ] Tests verify mock method signatures match production signatures
- [ ] Tests verify any mock return types are compatible with production types
- [ ] CI fails if mock/production interfaces diverge

**Implementation Notes**:
- Production `Searcher` is at `src/clams/search/searcher.py`
- `MockSearcher` is at `tests/context/test_assembler.py` lines 19-82
- Use `inspect` module to compare signatures:
  ```python
  import inspect
  from clams.search.searcher import Searcher
  from tests.context.test_assembler import MockSearcher

  def test_mock_searcher_has_all_production_methods():
      prod_methods = {m for m in dir(Searcher) if not m.startswith('_')}
      mock_methods = {m for m in dir(MockSearcher) if not m.startswith('_')}
      missing = prod_methods - mock_methods
      assert not missing, f"MockSearcher missing methods: {missing}"

  def test_mock_searcher_signature_matches():
      for method_name in ['search_memories', 'search_code', 'search_experiences']:
          prod_sig = inspect.signature(getattr(Searcher, method_name))
          mock_sig = inspect.signature(getattr(MockSearcher, method_name))
          # Compare parameters (ignoring self)
  ```
- Also verify other test mocks: `mock_embedding_service`, `mock_vector_store`

**Testing Requirements**:
- Test passes when mock and production interfaces match
- Test fails with descriptive error showing which methods/signatures differ
- Run as part of standard test suite (not just CI)

---

### R6-B: Configuration Parity Verification

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: none (can run in parallel with R6-A)

**Problem Statement**:
BUG-031 showed tests used `min_cluster_size=3` but production used `min_cluster_size=5`. BUG-033 showed tests used `.venv/bin/clams-server` correctly but hooks used `python -m clams`. Configuration drift between tests and production causes silent failures.

**Acceptance Criteria**:
- [ ] Test file exists at `tests/infrastructure/test_config_parity.py`
- [ ] Tests verify test clustering parameters match production defaults in `ServerSettings`
- [ ] Tests verify server command in hooks matches integration test fixtures
- [ ] Tests document any intentional test vs. production differences with justification
- [ ] A constants file exists for shared configuration values

**Implementation Notes**:
- Production config is at `src/clams/server/config.py` (see `ServerSettings` class)
- Key values to verify:
  - `hdbscan_min_cluster_size` (default: 5)
  - `hdbscan_min_samples` (default: 3)
  - Server command (should be `.venv/bin/clams-server` or discovered path)
- Hooks use config at `clams/hooks/config.yaml` - verify alignment with `ServerSettings`
- Pattern for verification:
  ```python
  from clams.server.config import ServerSettings

  def test_clustering_uses_production_defaults():
      settings = ServerSettings()
      # Verify test fixtures use these values
      assert settings.hdbscan_min_cluster_size == 5
      # Check test setup matches
  ```

**Testing Requirements**:
- Explicitly list all configuration values that must match
- Any intentional differences must be documented in test docstrings
- CI fails if undocumented differences exist

---

### R6-C: Production Command Verification in Tests

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R6-B

**Problem Statement**:
Integration tests should use the exact same commands and entry points as production. This ensures tests catch issues like incorrect module paths or missing entry points.

**Acceptance Criteria**:
- [ ] Integration tests use `.venv/bin/clams-server` (or resolved equivalent) not `python -m clams`
- [ ] Tests for hooks verify the same server start command as hooks use
- [ ] A utility function exists to get the canonical server command
- [ ] Documentation added to test files explaining parity requirement

**Implementation Notes**:
- Create utility in `tests/conftest.py`:
  ```python
  def get_server_command() -> list[str]:
      """Get canonical server start command for tests.

      IMPORTANT: This must match the command used in clams/hooks/*.sh
      """
      repo_root = Path(__file__).parent.parent
      venv_server = repo_root / ".venv" / "bin" / "clams-server"
      if venv_server.exists():
          return [str(venv_server)]
      # Fallback with warning
      import warnings
      warnings.warn("Using fallback server command - may differ from production")
      return ["python", "-m", "clams.server.main"]
  ```
- Audit and update:
  - `tests/integration/` - use canonical command
  - `clams/hooks/session_start.sh` - already uses correct command (line 51)

**Testing Requirements**:
- Test that utility returns same command as hooks use
- Integration tests must use this utility, not hardcoded commands

---

## R7: Lazy Import for Heavy Dependencies

**Overall Priority**: P1 - High impact (prevents critical startup failures like BUG-042)
**Addresses Themes**: T8 (Import Order/Heavy Dependencies)

### R7-A: Pre-commit Hook for Heavy Import Detection

**Type**: feature
**Priority**: P1
**Estimated Complexity**: Medium
**Dependencies**: none

**Problem Statement**:
BUG-042 was caused by PyTorch initializing MPS at import time, then `os.fork()` failing because MPS doesn't support fork after initialization. BUG-037 showed heavy imports cause 4.6-6.2 second delays. A pre-commit hook would catch top-level imports of heavy packages before they're committed.

**Acceptance Criteria**:
- [ ] Pre-commit hook exists at `.pre-commit-config.yaml` (or equivalent)
- [ ] Hook detects top-level imports of: `torch`, `sentence_transformers`, `transformers`, `numpy` (in certain contexts)
- [ ] Hook allows imports inside functions/methods (lazy imports)
- [ ] Hook allows imports in test files (where eager loading is acceptable)
- [ ] Hook provides clear error message with fix instructions

**Implementation Notes**:
- Current lazy import pattern is correct (see `src/clams/embedding/__init__.py` lines 1-47)
- Heavy packages that need protection:
  - `torch` - initializes CUDA/MPS backends
  - `sentence_transformers` - imports torch
  - `transformers` - imports torch
  - `nomic` - imports sentence_transformers
- Use AST-based detection to distinguish:
  ```python
  # FORBIDDEN at top level
  import torch

  # ALLOWED (lazy import)
  def get_embeddings():
      import torch
      ...
  ```
- Existing pattern to follow in `src/clams/embedding/registry.py`:
  ```python
  def get_code_embedder(self) -> EmbeddingService:
      if self._code_embedder is None:
          # Lazy import to avoid loading PyTorch before fork
          from .minilm import MiniLMEmbedding
  ```

**Testing Requirements**:
- Test hook on files with forbidden imports (should fail)
- Test hook on files with lazy imports (should pass)
- Test hook ignores test files

---

### R7-B: Import Time Measurement Test

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: none (can run in parallel with R7-A)

**Problem Statement**:
BUG-037 showed import time exceeds timeouts. A test that measures and alerts on import time would catch regressions.

**Acceptance Criteria**:
- [ ] Test exists at `tests/performance/test_import_time.py`
- [ ] Test measures time to `import clams` (top-level only)
- [ ] Test fails if import takes longer than 2 seconds
- [ ] Test documents expected import time for regression tracking

**Implementation Notes**:
- Measure in subprocess to get cold-start time:
  ```python
  import subprocess
  import time

  def test_import_time_under_threshold():
      start = time.time()
      result = subprocess.run(
          ["python", "-c", "import clams"],
          capture_output=True,
          timeout=10
      )
      elapsed = time.time() - start
      assert elapsed < 2.0, f"Import took {elapsed:.2f}s, expected < 2s"
      assert result.returncode == 0
  ```
- Current threshold should be 2 seconds (based on BUG-037 where 5 seconds was too low)
- Consider separating: `import clams` vs `import clams.embedding` (latter loads models)

**Testing Requirements**:
- Run in isolated subprocess for accurate measurement
- Test must not cache imports between runs
- Document baseline time in test docstring

---

### R7-C: Document Fork/Daemon Constraint

**Type**: chore
**Priority**: P1
**Estimated Complexity**: Low
**Dependencies**: R7-A

**Problem Statement**:
BUG-042 root cause: daemonization uses `os.fork()`, but MPS (Metal Performance Shaders on macOS) doesn't support fork after initialization. This constraint must be documented to prevent recurrence.

**Acceptance Criteria**:
- [ ] `CLAUDE.md` updated with "Import Guidelines" section
- [ ] Section documents: "Do not import torch/sentence_transformers at module level"
- [ ] Section documents: "Do not fork() after importing torch"
- [ ] Section links to relevant bug reports (BUG-042, BUG-037)
- [ ] `src/clams/embedding/__init__.py` docstring references the constraint

**Implementation Notes**:
- Add to CLAUDE.md under "## Principles" or new "## Technical Constraints" section:
  ```markdown
  ### Heavy Import Constraints

  **Never import these packages at module top level:**
  - `torch` - initializes GPU backends that don't support fork()
  - `sentence_transformers` - imports torch
  - `transformers` - imports torch
  - `nomic` - imports sentence_transformers

  **Why**: The server uses `os.fork()` for daemonization. PyTorch's MPS backend
  (macOS GPU) doesn't support fork after initialization. Import heavy packages
  inside functions instead.

  See: BUG-042, BUG-037
  ```
- Existing comment in `src/clams/embedding/registry.py` line 52 is good example:
  ```python
  # Lazy import to avoid loading PyTorch before fork
  ```

**Testing Requirements**:
- Manual verification that documentation is clear
- Verify documentation is discoverable from key files

---

## R8: Centralized Configuration Management

**Overall Priority**: P2 - Medium impact (prevents configuration scatter like BUG-033, BUG-037)
**Addresses Themes**: T6 (Configuration/Path Issues)

### R8-A: Create Canonical Configuration Module

**Type**: feature
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: none

**Problem Statement**:
Configuration values are scattered across multiple files: `ServerSettings` in `src/clams/server/config.py`, hardcoded values in hooks, magic numbers in tests. BUG-033 showed hooks used wrong server command. BUG-037 showed timeout values weren't centralized.

**Acceptance Criteria**:
- [ ] All configurable values are documented in `src/clams/server/config.py`
- [ ] `ServerSettings` includes all production defaults with docstrings
- [ ] A generated config file for shell scripts exists at `~/.clams/config.env`
- [ ] Server writes config on startup for hooks to source
- [ ] No hardcoded configuration values in hook scripts (except as fallbacks)

**Implementation Notes**:
- Extend `src/clams/server/config.py` `ServerSettings` class:
  ```python
  class ServerSettings(BaseSettings):
      # ... existing fields ...

      # Server identification
      server_command: str = ".venv/bin/clams-server"  # Or discovered

      # Timeouts
      verification_timeout: int = 15  # seconds, accounts for heavy imports
      http_call_timeout: int = 5  # seconds for hook HTTP calls

      # Clustering (existing)
      hdbscan_min_cluster_size: int = 5
      hdbscan_min_samples: int = 3

      def export_for_shell(self, path: Path) -> None:
          """Export config as shell-sourceable file."""
          with open(path, "w") as f:
              f.write(f"CLAMS_SERVER_COMMAND={self.server_command}\n")
              f.write(f"CLAMS_VERIFICATION_TIMEOUT={self.verification_timeout}\n")
              # ... etc
  ```
- Hooks would source this:
  ```bash
  # clams/hooks/session_start.sh
  if [ -f "${CLAMS_DIR}/config.env" ]; then
      source "${CLAMS_DIR}/config.env"
  fi
  ```

**Testing Requirements**:
- Test that exported config can be sourced by bash
- Test that values round-trip correctly
- Test that server writes config on startup

---

### R8-B: Grep-based CI Check for Hardcoded Paths

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Low
**Dependencies**: R8-A

**Problem Statement**:
Hardcoded paths outside the config module are a source of bugs (BUG-033: wrong server path in hooks). A CI check would catch new hardcoded values before they're merged.

**Acceptance Criteria**:
- [ ] CI script exists at `.github/scripts/check_hardcoded_paths.sh` or similar
- [ ] Script greps for suspicious patterns: `/\.venv/`, `python -m clams`, hardcoded ports
- [ ] Script ignores: `src/clams/server/config.py`, test files, documentation
- [ ] Script fails CI if hardcoded values found outside allowed locations
- [ ] Script output shows file:line of violations

**Implementation Notes**:
- Patterns to detect:
  ```bash
  # Hardcoded server paths (should use config)
  grep -rn "\.venv/bin/clams" --include="*.sh" --exclude-dir=".git"

  # Hardcoded python module invocation
  grep -rn "python -m clams" --include="*.sh" --exclude-dir=".git"

  # Hardcoded ports (should use CLAMS_PORT env var)
  grep -rn ":6333\|:6334" --include="*.sh" --include="*.py" --exclude-dir=".git"
  ```
- Allowed locations (whitelist):
  - `src/clams/server/config.py` (canonical source)
  - `tests/` (test fixtures may need specific values)
  - `docs/` (documentation examples)
  - Comments (explanatory references)

**Testing Requirements**:
- Run script manually on codebase
- Verify it catches known hardcoded values
- Verify it doesn't false-positive on legitimate uses

---

### R8-C: Hook Configuration Consolidation

**Type**: chore
**Priority**: P2
**Estimated Complexity**: Medium
**Dependencies**: R8-A

**Problem Statement**:
Hook scripts have configuration scattered at the top of each file. This makes it hard to maintain consistency and requires editing multiple files to change a value.

**Acceptance Criteria**:
- [ ] All hook scripts source a common config file
- [ ] `clams/hooks/config.yaml` converted to shell-sourceable format (or hooks read from `~/.clams/config.env`)
- [ ] Hook scripts have minimal hardcoded defaults (for bootstrap only)
- [ ] Documentation updated to explain config hierarchy

**Implementation Notes**:
- Current hook configuration (from `clams/hooks/session_start.sh` lines 13-19):
  ```bash
  CLAMS_DIR="${HOME}/.clams"
  JOURNAL_DIR="${CLAMS_DIR}/journal"
  PID_FILE="${CLAMS_DIR}/server.pid"
  SERVER_PORT="${CLAMS_PORT:-6334}"
  SERVER_HOST="${CLAMS_HOST:-127.0.0.1}"
  SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"
  ```
- Consolidate to:
  ```bash
  # clams/hooks/common.sh
  : "${CLAMS_DIR:=${HOME}/.clams}"
  if [ -f "${CLAMS_DIR}/config.env" ]; then
      source "${CLAMS_DIR}/config.env"
  fi
  # Defaults for bootstrap (before server writes config)
  : "${CLAMS_PORT:=6334}"
  : "${CLAMS_HOST:=127.0.0.1}"
  # ... etc
  ```
- Each hook script:
  ```bash
  #!/bin/bash
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  source "${SCRIPT_DIR}/common.sh"
  # ... rest of hook
  ```

**Testing Requirements**:
- Test hooks work with and without config file present
- Test that config.env is sourced when present
- Test that defaults work for fresh install (no config yet)

---

## Summary Table

| Ticket | Type | Priority | Complexity | Dependencies | Parallelizable |
|--------|------|----------|------------|--------------|----------------|
| R5-A | feature | P1 | Low | none | Yes |
| R5-B | feature | P2 | Medium | none | Yes |
| R5-C | feature | P2 | Low | none | Yes |
| R6-A | feature | P1 | Medium | none | Yes |
| R6-B | feature | P1 | Medium | none | Yes |
| R6-C | chore | P1 | Low | R6-B | No |
| R7-A | feature | P1 | Medium | none | Yes |
| R7-B | feature | P2 | Low | none | Yes |
| R7-C | chore | P1 | Low | R7-A | No |
| R8-A | feature | P2 | Medium | none | Yes |
| R8-B | chore | P2 | Low | R8-A | No |
| R8-C | chore | P2 | Medium | R8-A | No |

## Recommended Implementation Order

**Phase 1** (can be done in parallel):
- R5-A: Claude Code Hook Schema Conformance Tests
- R6-A: Mock Interface Verification Tests
- R7-A: Pre-commit Hook for Heavy Import Detection
- R8-A: Create Canonical Configuration Module

**Phase 2** (after Phase 1 completes):
- R5-B, R5-C: Additional schema tests
- R6-B, R6-C: Configuration parity and command verification
- R7-B, R7-C: Import time tests and documentation
- R8-B, R8-C: CI check and hook consolidation
