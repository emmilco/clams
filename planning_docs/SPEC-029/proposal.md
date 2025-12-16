# SPEC-029: Canonical Configuration Module - Technical Proposal

**Author**: Architect Worker W-1765889444-88850
**Date**: 2025-12-16
**Status**: Draft

## Problem Statement

Configuration values are scattered across multiple locations in the CLAMS codebase, creating maintenance burden and bugs when values drift apart. Evidence:

- **BUG-033**: Hook scripts used `python -m clams.server.main` while production used `.venv/bin/clams-server`
- **BUG-037**: Timeout values inconsistent between installation verification and HTTP calls
- **BUG-023**: Embedding dimension hardcoded as `768` without central definition
- **BUG-026**: Tool schemas had hardcoded enums that drifted from canonical enums
- **BUG-061**: Implementation directories hardcoded in multiple scripts

Current configuration exists in at least 4 distinct locations with different access patterns:
1. `src/clams/server/config.py` - Python `ServerSettings` (pydantic-settings)
2. `src/clams/storage/base.py` - Python `StorageSettings` (duplicate, different defaults)
3. `clams/hooks/*.sh` - Shell scripts with hardcoded values
4. `.claude/project.json` - JSON configuration for directory patterns

## Proposed Solution

### High-Level Architecture

```
                    ┌─────────────────────────────────┐
                    │   Environment Variables         │
                    │   CLAMS_* prefix                │
                    └───────────────┬─────────────────┘
                                    │ (highest precedence)
                                    ▼
┌───────────────────────────────────────────────────────────────────┐
│                     ServerSettings                                 │
│                 (src/clams/server/config.py)                      │
│                                                                    │
│  - All configuration with typed defaults                          │
│  - Environment override via pydantic-settings                     │
│  - Docstrings for all fields                                      │
│  - export_for_shell() method                                      │
└───────────────────────────────────────────────────────────────────┘
          │                                      │
          │ Python import                        │ server startup
          ▼                                      ▼
┌──────────────────────┐              ┌──────────────────────────────┐
│   Python modules     │              │   ~/.clams/config.env        │
│   (direct access)    │              │   (shell-sourceable)         │
│                      │              │                              │
│ from clams.server    │              │ # Auto-generated on startup  │
│   import             │              │ CLAMS_HTTP_PORT=6334         │
│   ServerSettings     │              │ CLAMS_PID_FILE=~/.clams/...  │
└──────────────────────┘              │ CLAMS_QDRANT_URL=...         │
                                      └──────────────────────────────┘
                                                 │
                                                 │ source
                                                 ▼
                                      ┌──────────────────────────────┐
                                      │   Shell hooks                │
                                      │   session_start.sh           │
                                      │   user_prompt_submit.sh      │
                                      │   etc.                       │
                                      └──────────────────────────────┘
```

### Key Design Decisions

#### 1. ServerSettings as Single Source of Truth

Extend the existing `ServerSettings` class rather than creating new infrastructure. This class already:
- Uses pydantic-settings for typed configuration
- Supports `CLAMS_*` environment variable overrides
- Has `export_for_shell()` method for shell script access
- Is well-tested

**Addition required**: PID file and log file paths, collection names export.

#### 2. Remove StorageSettings Duplication

The `StorageSettings` class in `src/clams/storage/base.py` duplicates `ServerSettings` with:
- Different env prefix (`STORAGE_` vs `CLAMS_`)
- Different timeout default (30.0 vs 5.0 seconds)
- Subset of the same fields

**Solution**: Delete `StorageSettings`, update `QdrantVectorStore` to accept `ServerSettings` or individual parameters.

#### 3. CollectionName as Canonical Source for Collection Names

The existing `CollectionName` class in `src/clams/search/collections.py` provides:
- String constants (not Enum) for simple usage
- Axis mapping for experience collections
- Clear namespace grouping

**Decision**: Keep `CollectionName` as the canonical source. `ServerSettings` will import from it for shell export. Collection names don't need environment override.

#### 4. Shell Export Enhancement

Enhance `export_for_shell()` to include:
- PID file and log file paths (new fields)
- Collection names (imported from `CollectionName`)
- Path expansion for `~` prefixed paths

#### 5. Hooks Source Config File

Update all hook scripts to source `~/.clams/config.env` at startup:
```bash
# Source config if available (server writes on startup)
CONFIG_FILE="${HOME}/.clams/config.env"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Fallback to defaults if config not available
CLAMS_HTTP_PORT="${CLAMS_HTTP_PORT:-6334}"
```

This provides:
- Centralized configuration for hooks
- Graceful degradation if config file doesn't exist
- Consistent values across all hooks

## Alternative Approaches Considered

### Alternative 1: YAML Configuration File

**Approach**: Single `~/.clams/config.yaml` file as source of truth.

**Rejection Rationale**:
- Adds YAML dependency to Python code
- Shell scripts would need `yq` or complex parsing
- Loses pydantic validation benefits
- More complex than current pydantic-settings approach

### Alternative 2: Environment-Only Configuration

**Approach**: No config file, rely entirely on environment variables.

**Rejection Rationale**:
- Shell scripts would need extensive environment setup
- No validation at startup
- Harder to audit current configuration
- No documentation of available options

### Alternative 3: Central Config File Loaded by Both Python and Shell

**Approach**: JSON config file parsed by Python and shell.

**Rejection Rationale**:
- JSON parsing in shell is fragile (requires jq)
- Loses typed defaults from pydantic
- Complicates the codebase without benefit
- Current approach (pydantic + shell export) is simpler

### Alternative 4: Keep StorageSettings, Add Translation Layer

**Approach**: Keep both settings classes, add adapter to keep them in sync.

**Rejection Rationale**:
- More code to maintain
- Synchronization is error-prone
- Violates single source of truth principle
- Already caused BUG-037 (different timeout defaults)

## File/Module Structure

### Files Modified

```
src/clams/server/config.py       # Add pid_file, log_file; enhance export
src/clams/storage/base.py        # Remove StorageSettings class
src/clams/storage/qdrant.py      # Update to use ServerSettings or params
src/clams/storage/__init__.py    # Remove StorageSettings export
clams/hooks/session_start.sh     # Source config file
clams/hooks/user_prompt_submit.sh # Source config file
clams/hooks/ghap_checkin.sh      # Source config file (if needed)
clams/hooks/session_end.sh       # Source config file (if needed)
clams/hooks/outcome_capture.sh   # Source config file (if needed)
```

### Files Not Modified

```
src/clams/search/collections.py  # Already canonical for collection names
.claude/project.json             # Per-project, separate from system config
```

### New Tests

```
tests/server/test_config.py      # Extend existing tests
tests/infrastructure/test_config_parity.py  # Already exists, update if needed
```

## Detailed Implementation

### Phase 1: Add Missing Fields to ServerSettings

Add to `src/clams/server/config.py`:

```python
# Server process management
pid_file: str = Field(
    default="~/.clams/server.pid",
    description="Path to server PID file for daemon management",
)

log_file: str = Field(
    default="~/.clams/server.log",
    description="Path to server log file for daemon mode",
)
```

### Phase 2: Enhance Shell Export

Update `export_for_shell()` to include:

```python
def export_for_shell(self, path: Path | str) -> None:
    """Export configuration as a shell-sourceable file."""
    from clams.search.collections import CollectionName

    if isinstance(path, str):
        path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# CLAMS Configuration (auto-generated)",
        "# Source this file: source ~/.clams/config.env",
        "",
        "# Server configuration",
        f"CLAMS_SERVER_COMMAND={self.server_command}",
        f"CLAMS_HTTP_HOST={self.http_host}",
        f"CLAMS_HTTP_PORT={self.http_port}",
        f"CLAMS_PID_FILE={Path(self.pid_file).expanduser()}",
        f"CLAMS_LOG_FILE={Path(self.log_file).expanduser()}",
        "",
        "# Storage paths (expanded)",
        f"CLAMS_STORAGE_PATH={Path(self.storage_path).expanduser()}",
        f"CLAMS_SQLITE_PATH={Path(self.sqlite_path).expanduser()}",
        f"CLAMS_JOURNAL_PATH={self.journal_path}",
        "",
        "# Timeouts (seconds)",
        f"CLAMS_VERIFICATION_TIMEOUT={self.verification_timeout}",
        f"CLAMS_HTTP_CALL_TIMEOUT={self.http_call_timeout}",
        f"CLAMS_QDRANT_TIMEOUT={self.qdrant_timeout}",
        "",
        "# Qdrant configuration",
        f"CLAMS_QDRANT_URL={self.qdrant_url}",
        "",
        "# Collection names",
        f"CLAMS_COLLECTION_MEMORIES={CollectionName.MEMORIES}",
        f"CLAMS_COLLECTION_CODE={CollectionName.CODE}",
        f"CLAMS_COLLECTION_COMMITS={CollectionName.COMMITS}",
        f"CLAMS_COLLECTION_VALUES={CollectionName.VALUES}",
        "",
        "# GHAP configuration",
        f"CLAMS_GHAP_CHECK_FREQUENCY={self.ghap_check_frequency}",
        "",
        "# Clustering configuration",
        f"CLAMS_HDBSCAN_MIN_CLUSTER_SIZE={self.hdbscan_min_cluster_size}",
        f"CLAMS_HDBSCAN_MIN_SAMPLES={self.hdbscan_min_samples}",
        "",
        "# Logging configuration",
        f"CLAMS_LOG_LEVEL={self.log_level}",
        f"CLAMS_LOG_FORMAT={self.log_format}",
        "",
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines))
```

### Phase 3: Remove StorageSettings

1. Delete `StorageSettings` class from `src/clams/storage/base.py`
2. Update `src/clams/storage/__init__.py` to remove the export
3. Update `QdrantVectorStore.__init__()`:

```python
def __init__(
    self,
    url: str | None = None,
    api_key: str | None = None,
    timeout: float | None = None,
) -> None:
    """Initialize Qdrant client.

    Args:
        url: Qdrant server URL. Defaults to ServerSettings value or
             ":memory:" for in-memory mode.
        api_key: Optional API key for authentication
        timeout: Request timeout in seconds. Defaults to ServerSettings value.
    """
    from clams.server.config import ServerSettings

    settings = ServerSettings()
    self._url = url or settings.qdrant_url
    self._api_key = api_key  # No default in ServerSettings (secret)
    self._timeout = timeout or settings.qdrant_timeout
    # ... rest unchanged
```

### Phase 4: Update Hook Scripts

Add to beginning of each hook script that needs configuration:

```bash
# Source CLAMS configuration (written by server on startup)
CLAMS_CONFIG="${HOME}/.clams/config.env"
if [ -f "$CLAMS_CONFIG" ]; then
    # shellcheck source=/dev/null
    source "$CLAMS_CONFIG"
fi

# Fallback defaults if config not available
# These must match ServerSettings defaults
CLAMS_HTTP_HOST="${CLAMS_HTTP_HOST:-127.0.0.1}"
CLAMS_HTTP_PORT="${CLAMS_HTTP_PORT:-6334}"
CLAMS_PID_FILE="${CLAMS_PID_FILE:-${HOME}/.clams/server.pid}"
CLAMS_VERIFICATION_TIMEOUT="${CLAMS_VERIFICATION_TIMEOUT:-15}"
```

Then use the variables throughout:
```bash
# Replace hardcoded values
SERVER_URL="http://${CLAMS_HTTP_HOST}:${CLAMS_HTTP_PORT}"
PID_FILE="${CLAMS_PID_FILE}"
```

## Test Strategy

### Unit Tests (tests/server/test_config.py)

1. **Default values**: Verify all fields have expected defaults
2. **Environment override**: Verify CLAMS_* prefix works for all fields
3. **Shell export**: Verify export creates valid bash syntax
4. **Path expansion**: Verify ~ paths are expanded in shell export
5. **Collection names**: Verify collection names are included in export
6. **New fields**: Test pid_file and log_file configuration

### Integration Tests

1. **Server startup**: Verify server writes config.env on startup
2. **Hook sourcing**: Verify hooks can source config.env successfully
3. **Round-trip**: Verify values round-trip through export/source correctly

### Parity Tests (tests/infrastructure/test_config_parity.py)

1. **No hardcoded values in hooks**: Grep hooks for hardcoded port/host/timeout
2. **StorageSettings removed**: Verify import fails
3. **Single source of truth**: Verify ServerSettings is only config class

### Example Test Cases

```python
def test_shell_export_includes_pid_file():
    """Verify pid_file is exported for shell scripts."""
    settings = ServerSettings()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.env"
        settings.export_for_shell(path)
        content = path.read_text()
        assert "CLAMS_PID_FILE=" in content
        # Should be expanded, not contain ~
        assert "~" not in content.split("CLAMS_PID_FILE=")[1].split("\n")[0]

def test_shell_export_includes_collection_names():
    """Verify collection names are exported."""
    from clams.search.collections import CollectionName

    settings = ServerSettings()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.env"
        settings.export_for_shell(path)
        content = path.read_text()
        assert f"CLAMS_COLLECTION_MEMORIES={CollectionName.MEMORIES}" in content
        assert f"CLAMS_COLLECTION_CODE={CollectionName.CODE}" in content

def test_storage_settings_import_fails():
    """Verify StorageSettings is no longer available."""
    with pytest.raises(ImportError):
        from clams.storage import StorageSettings

def test_hook_sources_config_successfully():
    """Verify hook can source config file and access variables."""
    settings = ServerSettings()
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "config.env"
        settings.export_for_shell(config_path)

        # Simulate what hooks do
        result = subprocess.run(
            ["bash", "-c", f"""
                source {config_path}
                echo "$CLAMS_HTTP_PORT|$CLAMS_PID_FILE"
            """],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        parts = result.stdout.strip().split("|")
        assert parts[0] == str(settings.http_port)
        assert "~" not in parts[1]  # Should be expanded
```

## Migration/Rollout Plan

### Phase 1: Non-Breaking Additions (Safe to Merge)

1. Add `pid_file` and `log_file` fields to `ServerSettings`
2. Add collection names to shell export
3. Add path expansion to shell export
4. Add new tests for these features

No existing code is modified in a breaking way.

### Phase 2: Update Hooks (Safe to Merge)

1. Update hooks to source config file
2. Keep fallback defaults matching ServerSettings
3. Replace hardcoded values with variables

Hooks still work without config file (fallback defaults).

### Phase 3: Remove StorageSettings (Breaking)

1. Delete `StorageSettings` class
2. Update `QdrantVectorStore` to import from `ServerSettings`
3. Update any code that imported `StorageSettings`

This is a breaking change for any code importing `StorageSettings`.

### Rollout Verification

After each phase:
1. Run full test suite: `pytest -vvsx`
2. Start server: `.venv/bin/clams-server --http --daemon`
3. Verify config.env exists: `cat ~/.clams/config.env`
4. Test hook execution: Create a Claude Code session
5. Verify no hardcoded values remain: `grep -r "6334\|6333\|localhost" clams/hooks/`

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Hooks fail if config.env missing | Low | Medium | Fallback defaults in hooks |
| QdrantVectorStore breaks | Low | High | Phase 3 is explicit breaking change |
| Path expansion issues | Low | Medium | Unit tests with mock home dir |
| Import cycles | Low | High | Lazy import in QdrantVectorStore |

## Success Criteria

1. **Single source of truth**: All configuration originates from `ServerSettings`
2. **No duplicates**: `StorageSettings` is deleted
3. **Shell parity**: Hooks use exported values, not hardcoded
4. **Test coverage**: All new/modified code has tests
5. **Documentation**: All fields have descriptions

## References

- BUG-033: Server command mismatch between hooks and tests
- BUG-037: Timeout value inconsistencies
- BUG-023: Hardcoded embedding dimension
- BUG-026: Hardcoded enum arrays in schemas
- BUG-061: Hardcoded directory patterns
- Spec: `planning_docs/SPEC-029/spec.md`
