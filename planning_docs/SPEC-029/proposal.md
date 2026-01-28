# SPEC-029: Canonical Configuration Module - Technical Proposal

**Author**: Architect Worker W-1769633608-24681
**Date**: 2026-01-28
**Status**: Draft (Revision 2)

## Problem Statement

Configuration values are scattered across multiple locations in the CLAMS codebase, creating maintenance burden and making it difficult to:

1. **Discover configuration options**: Developers must search through multiple files to find all tunable parameters
2. **Override values consistently**: Some constants are hardcoded without environment variable support
3. **Maintain the codebase**: Scattered constants create implicit dependencies between modules

### Evidence from Past Bugs

- **BUG-033**: Hook scripts used `python -m clams.server.main` while production used `.venv/bin/clams-server`
- **BUG-037**: Timeout values inconsistent between installation verification and HTTP calls
- **BUG-023**: Embedding dimension hardcoded as `768` without central definition
- **BUG-026**: Tool schemas had hardcoded enums that drifted from canonical enums

### Scattered Constants per Spec

The spec identifies these scattered constants requiring consolidation:

| Module | Constants | Current Location |
|--------|-----------|------------------|
| Context | `MAX_ITEM_FRACTION`, `SOURCE_WEIGHTS` | `context/tokens.py` |
| Context | `SIMILARITY_THRESHOLD`, `MAX_FUZZY_CONTENT_LENGTH` | `context/deduplication.py` |
| Tools | `PROJECT_ID_MAX_LENGTH` | `server/tools/validation.py` |
| Indexers | `EMBEDDING_BATCH_SIZE` | `indexers/indexer.py` (class attribute) |
| Session | `CLAMS_DIR`, `JOURNAL_DIR` | `server/tools/session.py` |
| HTTP | `DEFAULT_PID_FILE`, `DEFAULT_LOG_FILE` | `server/http.py` |
| Code Tools | `max_length = 5_000` | `server/tools/code.py` (inline) |
| Memory Tools | `max_length = 10_000` | `server/tools/memory.py` (inline) |

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
│                     src/clams/config.py                           │
│                     (Unified Configuration Entry Point)           │
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ ServerSettings  │  │ ContextSettings │  │ IndexerSettings │   │
│  │ (re-exported)   │  │ (NEW)           │  │ (NEW)           │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                    │
│  ┌─────────────────┐  ┌─────────────────┐                         │
│  │ ToolSettings    │  │ PathSettings    │  Module singleton:      │
│  │ (NEW)           │  │ (NEW)           │  `settings = Settings()`│
│  └─────────────────┘  └─────────────────┘                         │
└───────────────────────────────────────────────────────────────────┘
          │                                      │
          │ Python import                        │ server startup
          ▼                                      ▼
┌──────────────────────┐              ┌──────────────────────────────┐
│   Python modules     │              │   ~/.clams/config.env        │
│   (direct access)    │              │   (shell-sourceable)         │
│                      │              │                              │
│ from clams.config    │              │ # Auto-generated on startup  │
│   import settings    │              │ CLAMS_HTTP_PORT=6334         │
│                      │              │ CLAMS_CONTEXT__...           │
│ settings.server.*    │              │ CLAMS_TOOLS__...             │
│ settings.context.*   │              └──────────────────────────────┘
│ settings.tools.*     │                         │
└──────────────────────┘                         │ source
                                                 ▼
                                      ┌──────────────────────────────┐
                                      │   Shell hooks                │
                                      │   session_start.sh           │
                                      │   user_prompt_submit.sh      │
                                      └──────────────────────────────┘
```

### Key Design Decisions

#### 1. New Top-Level Config Module with Domain-Specific Settings Classes

Per the spec requirements, create `src/clams/config.py` that:
- Re-exports `ServerSettings` from `src/clams/server/config.py`
- Adds `ContextSettings` for context assembly constants
- Adds `IndexerSettings` for indexing constants
- Adds `ToolSettings` for tool parameter limits
- Adds `PathSettings` for file/directory paths
- Provides a `Settings` root class composing all sections
- Exports a module-level `settings` singleton for convenience

#### 2. Environment Variable Convention

All settings use the `CLAMS_` prefix. Nested settings use double underscore:
- `CLAMS_HTTP_PORT` (ServerSettings)
- `CLAMS_CONTEXT__MAX_ITEM_FRACTION` (ContextSettings)
- `CLAMS_TOOLS__SNIPPET_MAX_LENGTH` (ToolSettings)
- `CLAMS_INDEXER__EMBEDDING_BATCH_SIZE` (IndexerSettings)

#### 3. Backwards Compatibility

- `ServerSettings` is re-exported from `clams.config` for existing imports
- Module-level aliases at original locations initially point to config values
- No behavior changes - all defaults match current hardcoded values

#### 4. ServerSettings Enhancement

The existing `ServerSettings` already includes `pid_file` and `log_file` fields and the `export_for_shell()` method. No changes needed.

#### 5. CollectionName Remains Separate

The `CollectionName` class in `src/clams/search/collections.py` provides collection name constants. These are already exported in `export_for_shell()` and don't need environment override.

#### 6. StorageSettings Removal (If Still Present)

If `StorageSettings` exists in `src/clams/storage/base.py`, it should be removed and `QdrantVectorStore` updated to use `ServerSettings` values.

## Alternative Approaches Considered

### Alternative 1: Single Flat ServerSettings Class

**Approach**: Add all settings to `ServerSettings` instead of creating new domain classes.

**Rejection Rationale**:
- `ServerSettings` would grow too large (30+ settings)
- Loses logical grouping of related settings
- Harder to document and maintain
- Doesn't scale as CLAMS grows

### Alternative 2: YAML/TOML Configuration Files

**Approach**: Single `~/.clams/config.yaml` or `.toml` file as source of truth.

**Rejection Rationale**:
- Spec explicitly marks external config files as out of scope
- Adds file parsing dependency
- Environment variables are standard for container/cloud deployments
- pydantic-settings already provides excellent env var support

### Alternative 3: Keep Constants Where They Are, Just Document

**Approach**: Don't centralize, just add documentation pointing to each location.

**Rejection Rationale**:
- Doesn't solve the discoverability problem
- No environment variable override support for scattered constants
- Harder to test different configurations
- Violates DRY principle for path constants appearing in multiple places

### Alternative 4: Environment-Only Configuration

**Approach**: No config classes, rely entirely on environment variables with os.getenv().

**Rejection Rationale**:
- No validation at startup
- No type safety
- Harder to audit current configuration
- No documentation of available options in code

## File/Module Structure

### New Files

```
src/clams/config.py              # NEW - Unified configuration entry point
```

### Files Modified

```
src/clams/context/tokens.py      # Import constants from clams.config
src/clams/context/deduplication.py # Import constants from clams.config
src/clams/indexers/indexer.py    # Import EMBEDDING_BATCH_SIZE from config
src/clams/server/tools/validation.py # Import limits from clams.config
src/clams/server/tools/session.py # Import paths from clams.config
src/clams/server/tools/code.py   # Import max_length from clams.config
src/clams/server/tools/memory.py # Import max_length from clams.config
src/clams/server/http.py         # Import paths from clams.config
src/clams/storage/qdrant.py      # Use ServerSettings for defaults (if StorageSettings exists)
```

### Files Not Modified

```
src/clams/server/config.py       # Keep as-is, re-exported from top-level
src/clams/search/collections.py  # Already canonical for collection names
```

### New Tests

```
tests/unit/test_config.py        # Test new config module and settings classes
tests/integration/test_config_imports.py  # Test import compatibility
```

## Detailed Implementation

### Phase 1: Create New Config Module

Create `src/clams/config.py`:

```python
"""CLAMS Configuration Module.

This module provides centralized configuration for all CLAMS components.
All settings support environment variable overrides with CLAMS_ prefix.

Usage:
    from clams.config import settings

    # Access server settings
    print(settings.server.http_port)

    # Access context settings
    print(settings.context.max_item_fraction)

    # Access tool settings
    print(settings.tools.snippet_max_length)
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Re-export for backwards compatibility
from clams.server.config import ServerSettings


class ContextSettings(BaseSettings):
    """Configuration for context assembly and deduplication."""

    model_config = SettingsConfigDict(env_prefix="CLAMS_CONTEXT__")

    # Token management (from context/tokens.py)
    max_item_fraction: float = Field(
        default=0.25,
        description="Maximum fraction of source budget any single item can consume",
    )

    # Source weights for budget distribution
    source_weight_memories: int = Field(default=1)
    source_weight_code: int = Field(default=2)
    source_weight_experiences: int = Field(default=3)
    source_weight_values: int = Field(default=1)
    source_weight_commits: int = Field(default=2)

    # Deduplication (from context/deduplication.py)
    similarity_threshold: float = Field(
        default=0.90,
        description="Similarity threshold for fuzzy matching (90%)",
    )
    max_fuzzy_content_length: int = Field(
        default=1000,
        description="Max content length for fuzzy matching (performance optimization)",
    )

    @property
    def source_weights(self) -> dict[str, int]:
        """Get source weights as a dictionary for backwards compatibility."""
        return {
            "memories": self.source_weight_memories,
            "code": self.source_weight_code,
            "experiences": self.source_weight_experiences,
            "values": self.source_weight_values,
            "commits": self.source_weight_commits,
        }


class IndexerSettings(BaseSettings):
    """Configuration for code and commit indexing."""

    model_config = SettingsConfigDict(env_prefix="CLAMS_INDEXER__")

    embedding_batch_size: int = Field(
        default=100,
        description="Number of items to embed in a single batch",
    )


class ToolSettings(BaseSettings):
    """Configuration for MCP tool parameters."""

    model_config = SettingsConfigDict(env_prefix="CLAMS_TOOLS__")

    # Validation limits (from server/tools/validation.py)
    project_id_max_length: int = Field(
        default=100,
        description="Maximum length for project identifiers",
    )

    # Content length limits (from server/tools/code.py, memory.py)
    snippet_max_length: int = Field(
        default=5_000,
        description="Maximum length for code snippets in find_similar_code",
    )
    memory_content_max_length: int = Field(
        default=10_000,
        description="Maximum length for memory content in store_memory",
    )


class PathSettings(BaseSettings):
    """Configuration for file and directory paths.

    Note: These overlap with some ServerSettings fields but provide
    Path objects instead of strings for convenience.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_PATHS__")

    clams_dir: Path = Field(
        default=Path.home() / ".clams",
        description="Base directory for CLAMS data storage",
    )
    journal_dir: Path = Field(
        default=Path.home() / ".clams" / "journal",
        description="Directory for session journal files",
    )


class Settings(BaseSettings):
    """Root settings class that composes all configuration sections."""

    model_config = SettingsConfigDict(env_prefix="CLAMS_")

    server: ServerSettings = Field(default_factory=ServerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    indexer: IndexerSettings = Field(default_factory=IndexerSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    paths: PathSettings = Field(default_factory=PathSettings)


# Module-level singleton instance
settings = Settings()

__all__ = [
    "Settings",
    "ServerSettings",
    "ContextSettings",
    "IndexerSettings",
    "ToolSettings",
    "PathSettings",
    "settings",
]
```

### Phase 2: Update Consumer Modules

For each module with scattered constants, add import and use settings:

**context/tokens.py**:
```python
from clams.config import settings

# Keep as module-level aliases for backwards compatibility
SOURCE_WEIGHTS = settings.context.source_weights
MAX_ITEM_FRACTION = settings.context.max_item_fraction
```

**context/deduplication.py**:
```python
from clams.config import settings

SIMILARITY_THRESHOLD = settings.context.similarity_threshold
MAX_FUZZY_CONTENT_LENGTH = settings.context.max_fuzzy_content_length
```

**indexers/indexer.py**:
```python
from clams.config import settings

class CodeIndexer:
    COLLECTION_NAME = "code_units"

    @property
    def embedding_batch_size(self) -> int:
        return settings.indexer.embedding_batch_size
```

**server/tools/validation.py**:
```python
from clams.config import settings

PROJECT_ID_MAX_LENGTH = settings.tools.project_id_max_length
```

**server/tools/code.py** and **memory.py**:
```python
from clams.config import settings

# In find_similar_code:
max_length = settings.tools.snippet_max_length

# In store_memory:
max_length = settings.tools.memory_content_max_length
```

**server/tools/session.py**:
```python
from clams.config import settings

CLAMS_DIR = settings.paths.clams_dir
JOURNAL_DIR = settings.paths.journal_dir
```

**server/http.py**:
```python
from clams.config import settings

# Replace module-level constants
def get_pid_file() -> Path:
    return Path(settings.server.pid_file).expanduser()

def get_log_file() -> Path:
    return Path(settings.server.log_file).expanduser()
```

### Phase 3: Update Remaining Imports

Update any code that imports directly from `clams.server.config`:

```python
# Before
from clams.server.config import ServerSettings

# After (preferred)
from clams.config import settings
# or for backwards compat
from clams.config import ServerSettings
```

## Test Strategy

### Unit Tests (tests/unit/test_config.py)

1. **Default values**: Verify all settings classes have correct defaults
2. **Environment override**: Verify env vars override defaults for all classes
3. **Nested env vars**: Verify `CLAMS_CONTEXT__MAX_ITEM_FRACTION` works
4. **Type validation**: Verify pydantic validates types correctly
5. **Backwards compatibility**: Ensure `ServerSettings` re-export works
6. **Source weights property**: Verify `source_weights` dict computed correctly

### Integration Tests (tests/integration/test_config_imports.py)

1. **No circular imports**: Verify `from clams.config import settings` works
2. **Module aliases**: Verify constants at original locations work
3. **Settings usage**: Verify all modules can access settings correctly

### Example Test Cases

```python
import os
import pytest
from clams.config import settings, Settings, ContextSettings, ToolSettings


def test_default_max_item_fraction():
    """Verify context settings default matches original constant."""
    assert settings.context.max_item_fraction == 0.25


def test_default_source_weights():
    """Verify source weights match original dict."""
    expected = {
        "memories": 1,
        "code": 2,
        "experiences": 3,
        "values": 1,
        "commits": 2,
    }
    assert settings.context.source_weights == expected


def test_default_similarity_threshold():
    """Verify deduplication threshold matches original constant."""
    assert settings.context.similarity_threshold == 0.90


def test_default_embedding_batch_size():
    """Verify indexer batch size matches original class attribute."""
    assert settings.indexer.embedding_batch_size == 100


def test_default_tool_limits():
    """Verify tool limits match original inline constants."""
    assert settings.tools.snippet_max_length == 5_000
    assert settings.tools.memory_content_max_length == 10_000
    assert settings.tools.project_id_max_length == 100


def test_context_env_override(monkeypatch):
    """Verify environment override for nested settings."""
    monkeypatch.setenv("CLAMS_CONTEXT__MAX_ITEM_FRACTION", "0.5")
    fresh_settings = Settings()
    assert fresh_settings.context.max_item_fraction == 0.5


def test_tools_env_override(monkeypatch):
    """Verify environment override for tool settings."""
    monkeypatch.setenv("CLAMS_TOOLS__SNIPPET_MAX_LENGTH", "10000")
    fresh_settings = Settings()
    assert fresh_settings.tools.snippet_max_length == 10000


def test_server_settings_reexport():
    """Verify ServerSettings is re-exported from clams.config."""
    from clams.config import ServerSettings
    from clams.server.config import ServerSettings as OriginalServerSettings
    assert ServerSettings is OriginalServerSettings


def test_no_circular_imports():
    """Verify config module can be imported cleanly."""
    import importlib
    import clams.config
    importlib.reload(clams.config)  # Should not raise


def test_module_level_aliases():
    """Verify original import locations still work."""
    # These should be importable (backwards compat)
    from clams.context.tokens import SOURCE_WEIGHTS, MAX_ITEM_FRACTION
    from clams.context.deduplication import SIMILARITY_THRESHOLD
    # Values should match settings
    assert MAX_ITEM_FRACTION == settings.context.max_item_fraction
```

## Migration/Rollout Plan

### Phase 1: Create Config Module (Non-Breaking)

1. Create `src/clams/config.py` with all new settings classes
2. Add re-exports from `clams.server.config`
3. Add tests for new settings classes
4. **No changes to existing imports yet**

No existing code is modified.

### Phase 2: Update Consumer Modules (Non-Breaking)

For each module with scattered constants:
1. Add import: `from clams.config import settings`
2. Add module-level aliases that reference settings
3. Existing code continues to work via the aliases

Example for `context/tokens.py`:
```python
# Old code (keep working)
MAX_ITEM_FRACTION = 0.25

# New code
from clams.config import settings
MAX_ITEM_FRACTION = settings.context.max_item_fraction
```

### Phase 3: Update Direct ServerSettings Imports (Optional)

Replace direct imports from `clams.server.config`:
```python
# Before
from clams.server.config import ServerSettings

# After
from clams.config import ServerSettings
```

This is optional since re-exports maintain compatibility.

### Rollout Verification

After each phase:
1. Run full test suite: `pytest -vvsx`
2. Run type checker: `mypy --strict src/clams/config.py`
3. Verify imports work: `python -c "from clams.config import settings; print(settings.context.max_item_fraction)"`
4. Verify environment overrides: `CLAMS_CONTEXT__MAX_ITEM_FRACTION=0.5 python -c "from clams.config import Settings; print(Settings().context.max_item_fraction)"`

## Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Circular imports | Low | High | `config.py` at top level with minimal deps (only pydantic, pathlib) |
| Breaking existing code | Low | Medium | Re-exports and module-level aliases maintain compatibility |
| Performance impact | Low | Low | Settings loaded once at import, cached in singleton |
| Environment variable conflicts | Low | Low | Nested settings use double underscore to avoid collisions |

## Success Criteria (Mapping to Acceptance Criteria)

| Acceptance Criterion | How This Proposal Addresses It |
|---------------------|-------------------------------|
| `src/clams/config.py` exists and re-exports `ServerSettings` | Created as main module with `__all__` export |
| New settings classes for `ContextSettings`, `IndexerSettings`, `ToolSettings` | All three classes defined with appropriate fields |
| All constants migrated to appropriate settings class | Migration strategy defined for each constant |
| Environment variable support with `CLAMS_` prefix | pydantic-settings with `env_prefix` on all classes |
| Type annotations on all configuration values | All fields use pydantic `Field` with types |
| Tests verify configuration values are accessible | Testing strategy with example tests defined |
| No circular import issues | Design places `config.py` at top level with minimal deps |
| Existing functionality unchanged | Default values match current hardcoded values |
| Imports updated throughout codebase | Migration strategy covers all affected modules |

## References

- Spec: `planning_docs/SPEC-029/spec.md`
- Past bugs caused by scattered config: BUG-033, BUG-037, BUG-023, BUG-026
