# SPEC-029: Canonical Configuration Module

**Status**: SPEC
**Type**: Feature
**Priority**: P2
**Dependencies**: None
**Unblocks**: SPEC-055 (Grep-based CI Check for Hardcoded Paths), SPEC-056 (Hook Configuration Consolidation)

## Problem Statement

Configuration values are scattered across multiple locations in the CLAMS codebase, creating maintenance burden and causing bugs when values drift apart:

### Evidence of Current Problems

1. **BUG-033**: Hook scripts used `python -m clams.server.main` while tests and production used `.venv/bin/clams-server`, causing server startup failures.

2. **BUG-037**: Timeout values were not centralized. Installation verification used one timeout while HTTP calls used another, leading to race conditions.

3. **BUG-023**: Embedding dimension was hardcoded as `768` in `NomicEmbedding` rather than queried from the model, causing vector store mismatches.

4. **BUG-026**: Tool schemas had hardcoded enum arrays that drifted from canonical enums in `enums.py`, causing validation errors.

5. **BUG-061**: Implementation directories (`src/`, `tests/`, etc.) were hardcoded in multiple scripts without central definition.

### Current Configuration Locations

| Location | Type | Examples |
|----------|------|----------|
| `src/clams/server/config.py` | Python | `ServerSettings` class with pydantic-settings |
| `.claude/bin/claws-common.sh` | Shell | `MAIN_REPO`, `DB_PATH`, `WORKTREE_DIR` |
| `.claude/project.json` | JSON | `implementation_dirs`, `test_dirs` |
| `clams/hooks/*.sh` | Shell | Hardcoded paths, ports, timeouts |
| `src/clams/storage/base.py` | Python | Duplicate `qdrant_url`, `storage_path` defaults |
| `src/clams/search/collections.py` | Python | Collection name constants |
| Individual modules | Python | Magic numbers, collection names inline |

### Types of Configuration Currently Scattered

1. **Server Configuration**
   - Server command: `.venv/bin/clams-server`
   - HTTP host/port: `127.0.0.1:6334`
   - PID file location: `~/.clams/server.pid`
   - Log file location: `~/.clams/server.log`

2. **Storage Paths**
   - Base storage: `~/.clams`
   - SQLite metadata: `~/.clams/metadata.db`
   - Journal directory: `.claude/journal`

3. **Qdrant Configuration**
   - URL: `http://localhost:6333`
   - Timeout: `5.0` seconds (in config), `30.0` (in storage/base.py)

4. **Collection Names**
   - `memories`, `code_units`, `commits`, `values`
   - `ghap_full`, `ghap_strategy`, `ghap_surprise`, `ghap_root_cause`

5. **Timeouts**
   - Verification timeout: `15` seconds
   - HTTP call timeout: `5` seconds
   - Qdrant timeout: `5.0` seconds

6. **Embedding Configuration**
   - Code model: `sentence-transformers/all-MiniLM-L6-v2`
   - Semantic model: `nomic-ai/nomic-embed-text-v1.5`
   - Dimension: `768`

7. **Clustering Parameters**
   - HDBSCAN min_cluster_size: `5`
   - HDBSCAN min_samples: `3`

8. **Project Structure**
   - Implementation directories: `src/`, `clams-visualizer/`
   - Test directories: `tests/`
   - Script directories: `.claude/bin/`, `scripts/`

## Technical Approach

### 1. Extend ServerSettings as Canonical Source

The existing `ServerSettings` class in `src/clams/server/config.py` already uses pydantic-settings with environment variable overrides. This should become the single source of truth for ALL configuration.

```python
class ServerSettings(BaseSettings):
    """Canonical configuration for all CLAMS components.

    All settings can be overridden via environment variables with CLAMS_ prefix.
    """
    model_config = SettingsConfigDict(env_prefix="CLAMS_")

    # =========================================================================
    # Server configuration
    # =========================================================================
    server_command: str = ".venv/bin/clams-server"
    http_host: str = "127.0.0.1"
    http_port: int = 6334
    pid_file: str = "~/.clams/server.pid"
    log_file: str = "~/.clams/server.log"

    # =========================================================================
    # Storage paths
    # =========================================================================
    storage_path: str = "~/.clams"
    sqlite_path: str = "~/.clams/metadata.db"
    journal_path: str = ".claude/journal"

    # =========================================================================
    # Qdrant configuration
    # =========================================================================
    qdrant_url: str = "http://localhost:6333"
    qdrant_timeout: float = 5.0

    # =========================================================================
    # Collection names
    # =========================================================================
    collection_memories: str = "memories"
    collection_code: str = "code_units"
    collection_commits: str = "commits"
    collection_values: str = "values"
    collection_ghap_prefix: str = "ghap"

    # =========================================================================
    # Timeouts (seconds)
    # =========================================================================
    verification_timeout: int = 15
    http_call_timeout: int = 5

    # =========================================================================
    # Embedding configuration
    # =========================================================================
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dimension: int = 768
    code_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_model: str = "nomic-ai/nomic-embed-text-v1.5"

    # =========================================================================
    # Clustering configuration (HDBSCAN)
    # =========================================================================
    hdbscan_min_cluster_size: int = 5
    hdbscan_min_samples: int = 3

    # =========================================================================
    # GHAP configuration
    # =========================================================================
    ghap_check_frequency: int = 10
```

### 2. Shell Configuration Export

The existing `export_for_shell()` method should be enhanced to include ALL configuration values needed by shell scripts:

```python
def export_for_shell(self, path: Path | str) -> None:
    """Export configuration as a shell-sourceable file."""
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
        "# Storage paths",
        f"CLAMS_STORAGE_PATH={Path(self.storage_path).expanduser()}",
        f"CLAMS_SQLITE_PATH={Path(self.sqlite_path).expanduser()}",
        "",
        "# Qdrant configuration",
        f"CLAMS_QDRANT_URL={self.qdrant_url}",
        f"CLAMS_QDRANT_TIMEOUT={self.qdrant_timeout}",
        "",
        "# Timeouts (seconds)",
        f"CLAMS_VERIFICATION_TIMEOUT={self.verification_timeout}",
        f"CLAMS_HTTP_CALL_TIMEOUT={self.http_call_timeout}",
        "",
        "# Collection names",
        f"CLAMS_COLLECTION_MEMORIES={self.collection_memories}",
        f"CLAMS_COLLECTION_CODE={self.collection_code}",
        f"CLAMS_COLLECTION_COMMITS={self.collection_commits}",
        f"CLAMS_COLLECTION_VALUES={self.collection_values}",
        "",
    ]
    # ... write to file
```

### 3. Configuration Hierarchy

Configuration should follow this precedence (highest to lowest):

1. **Environment variables**: `CLAMS_*` prefix (already supported)
2. **Config file**: `~/.clams/config.env` (for shell scripts)
3. **Code defaults**: `ServerSettings` class defaults

### 4. Server Writes Config on Startup

When the CLAMS server starts, it should write the current configuration to `~/.clams/config.env`:

```python
# In server startup
settings = ServerSettings()
settings.export_for_shell(settings.get_config_env_path())
```

This ensures hooks always have access to the current configuration.

### 5. Remove Duplicate Definitions

After centralizing configuration:

1. **Remove** `StorageSettings` class from `src/clams/storage/base.py` - it duplicates `ServerSettings`
2. **Remove** inline collection name strings - use `settings.collection_*` or `CollectionName.*`
3. **Update** hook scripts to source `~/.clams/config.env` instead of hardcoding values
4. **Update** `.claude/project.json` to be read by Python config (or remove if redundant)

### 6. Collection Name Integration

The existing `CollectionName` class in `src/clams/search/collections.py` should either:

- **Option A**: Be generated from `ServerSettings` at runtime
- **Option B**: Be the canonical source that `ServerSettings` references

Recommended: **Option B** - Keep `CollectionName` as the canonical source for collection names since they're used pervasively in code and don't need environment override. `ServerSettings` can import from `CollectionName` for the shell export.

## Migration Plan

### Phase 1: Add Missing Configuration to ServerSettings

1. Add `pid_file`, `log_file` paths
2. Add `collection_*` fields (importing from `CollectionName`)
3. Ensure all timeout values are present
4. Add comprehensive docstrings

### Phase 2: Update Shell Export

1. Enhance `export_for_shell()` to include all needed values
2. Add path expansion for `~` prefixed paths
3. Write config file on server startup

### Phase 3: Update Hook Scripts

1. Update `clams/hooks/session_start.sh` to source config
2. Update `clams/hooks/user_prompt_submit.sh` to source config
3. Replace hardcoded values with environment variables

### Phase 4: Remove Duplicate Definitions

1. Remove `StorageSettings` from `storage/base.py`
2. Update imports throughout codebase
3. Replace inline collection names with references

### Phase 5: Documentation

1. Document all configuration options in `ServerSettings` docstrings
2. Add configuration section to README/docs
3. Document environment variable overrides

## Acceptance Criteria

1. **Single Source of Truth**
   - [ ] All configuration values are defined in `src/clams/server/config.py`
   - [ ] `ServerSettings` includes all production defaults with docstrings
   - [ ] No duplicate `StorageSettings` class exists

2. **Shell Script Support**
   - [ ] `~/.clams/config.env` is generated on server startup
   - [ ] All hook scripts source the config file
   - [ ] No hardcoded configuration values in hook scripts (except as fallbacks)

3. **Collection Names**
   - [ ] `CollectionName` class is the canonical source for collection names
   - [ ] All modules import collection names instead of hardcoding strings
   - [ ] Collection names are included in shell export

4. **Timeouts**
   - [ ] All timeout values are centralized in `ServerSettings`
   - [ ] No duplicate timeout definitions across modules

5. **Environment Override**
   - [ ] All settings can be overridden via `CLAMS_*` environment variables
   - [ ] Override precedence is documented

6. **Tests**
   - [ ] Unit tests verify config export round-trips correctly
   - [ ] Integration tests verify server writes config on startup
   - [ ] Tests verify bash can source the generated config

## Testing Requirements

### Unit Tests

```python
def test_export_for_shell_creates_valid_bash():
    """Generated config should be valid bash syntax."""
    settings = ServerSettings()
    with tempfile.NamedTemporaryFile(suffix=".env") as f:
        settings.export_for_shell(f.name)
        # Verify bash can source it
        result = subprocess.run(["bash", "-c", f"source {f.name} && echo $CLAMS_HTTP_PORT"])
        assert result.stdout.strip() == "6334"

def test_all_settings_exported():
    """All ServerSettings fields should be exported."""
    settings = ServerSettings()
    with tempfile.NamedTemporaryFile(suffix=".env") as f:
        settings.export_for_shell(f.name)
        content = Path(f.name).read_text()
        # Verify key settings are present
        assert "CLAMS_SERVER_COMMAND" in content
        assert "CLAMS_HTTP_PORT" in content
        assert "CLAMS_QDRANT_URL" in content

def test_env_override_works():
    """Environment variables should override defaults."""
    with mock.patch.dict(os.environ, {"CLAMS_HTTP_PORT": "9999"}):
        settings = ServerSettings()
        assert settings.http_port == 9999
```

### Integration Tests

```python
def test_server_writes_config_on_startup():
    """Server should write config.env when starting."""
    config_path = Path.home() / ".clams" / "config.env"
    # Start server
    # Verify config file exists and has expected content

def test_hooks_use_config():
    """Hook scripts should use values from config."""
    # Run hook script
    # Verify it uses configured values, not hardcoded defaults
```

## Non-Goals

1. **Dynamic configuration reloading**: Configuration is read at startup. Changes require restart.
2. **UI for configuration**: This is a developer-facing module, not end-user configuration.
3. **Encrypted secrets**: Secrets like API keys are handled separately via environment variables.
4. **Per-project configuration**: This is system-wide configuration. Per-project settings (like `.claude/project.json`) remain separate.

## References

- BUG-033: Server command mismatch between hooks and tests
- BUG-037: Timeout value inconsistencies
- BUG-023: Hardcoded embedding dimension
- BUG-026: Hardcoded enum arrays in schemas
- BUG-061: Hardcoded directory patterns
- R8-A (recommendations-r5-r8.md): Original ticket for this feature
