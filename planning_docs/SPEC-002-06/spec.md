# SPEC-002-06: CodeParser + CodeIndexer

## Overview

Implement the code parsing and indexing layer for the Learning Memory Server. This enables semantic code search by extracting meaningful units (functions, classes, methods) from source files, embedding them, and storing them in the vector store.

## Dependencies

- SPEC-002-02: EmbeddingService (completed)
- SPEC-002-03: VectorStore (completed)
- SPEC-002-04: SQLite metadata store (completed)

## Components

### 1. CodeParser

**Purpose**: Parse source files into semantic units using tree-sitter.

**Interface**:
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class UnitType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    KEY = "key"  # For YAML/JSON root-level keys

@dataclass
class SemanticUnit:
    name: str
    qualified_name: str  # e.g., "module.ClassName.method_name"
    unit_type: UnitType
    signature: str  # e.g., "def foo(x: int, y: str) -> bool"
    content: str  # Full source code of the unit
    file_path: str
    start_line: int
    end_line: int
    language: str
    docstring: Optional[str] = None
    complexity: Optional[int] = None  # Cyclomatic complexity

class CodeParser(ABC):
    @abstractmethod
    async def parse_file(self, path: str) -> list[SemanticUnit]:
        """
        Parse a file and extract semantic units.

        Note: Tree-sitter parsing is CPU-bound. Implementations MUST use
        asyncio.get_event_loop().run_in_executor(None, ...) to avoid
        blocking the event loop.
        """
        pass

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return list of supported language identifiers."""
        pass

    @abstractmethod
    def detect_language(self, path: str) -> str | None:
        """
        Detect language from file extension.

        Returns language identifier or None if unsupported.
        Mapping: .py -> python, .ts -> typescript, .js -> javascript,
                 .lua -> lua, .yaml/.yml -> yaml, .json -> json
        """
        pass
```

**Implementation**: `TreeSitterParser`
- Uses `tree-sitter-languages` for bundled grammars
- Supports: Python, TypeScript, JavaScript, Lua, YAML, JSON
- Extracts docstrings where available
- Computes cyclomatic complexity for functions/methods
- Uses `run_in_executor` for CPU-bound parsing

### 2. CodeIndexer

**Purpose**: Index parsed code units for semantic search.

**Interface**:
```python
from dataclasses import dataclass, field

@dataclass
class IndexingError:
    file_path: str
    error_type: str  # "parse_error", "encoding_error", "io_error"
    message: str

@dataclass
class IndexingStats:
    files_indexed: int
    units_indexed: int
    files_skipped: int
    errors: list[IndexingError] = field(default_factory=list)
    duration_ms: int = 0

class CodeIndexer:
    # Maximum units to embed in a single batch call
    EMBEDDING_BATCH_SIZE: int = 100

    def __init__(
        self,
        parser: CodeParser,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        metadata_store: MetadataStore,  # SQLite
    ):
        ...

    async def index_file(self, path: str, project: str) -> int:
        """
        Index a single file. Returns number of units indexed.

        IMPORTANT: Before indexing, deletes all existing entries for this file
        to prevent orphaned entries when code is renamed/removed.
        """
        pass

    async def index_directory(
        self,
        path: str,
        project: str,
        recursive: bool = True,
        exclude_patterns: list[str] | None = None,
    ) -> IndexingStats:
        """
        Index all supported files in a directory.

        - Skips files that haven't changed (via needs_reindex check)
        - Accumulates errors instead of failing fast
        - Logs progress via structlog
        """
        pass

    async def remove_file(self, path: str, project: str) -> int:
        """Remove all indexed units from a file. Returns count removed."""
        pass

    async def remove_project(self, project: str) -> int:
        """Remove all indexed units for a project. Returns count removed."""
        pass

    async def get_indexing_stats(self, project: str) -> IndexingStats:
        """Get current indexing statistics for a project."""
        pass

    async def is_file_indexed(self, path: str, project: str) -> bool:
        """Check if a file is already indexed."""
        pass

    async def needs_reindex(self, path: str, project: str) -> bool:
        """
        Check if file has changed since last index.

        Compares current file mtime and content hash against stored values.
        Returns True if file is new, modified, or not yet indexed.
        """
        pass
```

## ID Generation

Unit IDs are generated using SHA-256 hash to ensure uniqueness and determinism:

```python
import hashlib

def generate_unit_id(project: str, file_path: str, qualified_name: str) -> str:
    """
    Generate a unique, deterministic ID for a semantic unit.

    Uses SHA-256 hash of project + file_path + qualified_name.
    Truncated to 32 chars for readability while maintaining uniqueness.
    """
    content = f"{project}:{file_path}:{qualified_name}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]
```

**Collision handling**: SHA-256 truncated to 32 hex chars (128 bits) has negligible collision probability for our use case (<10M units). If a collision occurs (same ID, different content), the newer entry overwrites the older one, which is acceptable since we reindex full files.

## Storage Schema

### Vector Store Collection: `code_units`

**Payload fields**:
```python
{
    "id": str,              # SHA-256 hash (32 chars) of project:file_path:qualified_name
    "project": str,         # Project identifier
    "file_path": str,       # Absolute path to file
    "name": str,            # Short name (e.g., "foo")
    "qualified_name": str,  # Full path (e.g., "module.Class.foo")
    "unit_type": str,       # "function", "class", "method", etc.
    "signature": str,       # Full signature
    "language": str,        # "python", "typescript", etc.
    "start_line": int,
    "end_line": int,
    "line_count": int,      # Computed: end_line - start_line + 1
    "complexity": int | None,
    "has_docstring": bool,
    "indexed_at": str,      # ISO timestamp (UTC)
}
```

### SQLite Metadata: `indexed_files` table

Change detection uses SQLite only (not VectorStore payloads):

```sql
CREATE TABLE IF NOT EXISTS indexed_files (
    id INTEGER PRIMARY KEY,
    project TEXT NOT NULL,
    file_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,     -- SHA-256 of file content for change detection
    mtime REAL NOT NULL,            -- File modification time (quick check before hashing)
    unit_count INTEGER NOT NULL,
    indexed_at TEXT NOT NULL,       -- ISO timestamp (UTC)
    UNIQUE(project, file_path)
);

CREATE INDEX IF NOT EXISTS idx_indexed_files_project ON indexed_files(project);
```

## Language Support Details

### Python
- **Units**: functions, classes, methods (module-level executable code is NOT indexed)
- **Qualified names**: `module.ClassName.method_name` (module = file stem)
- **Docstrings**: Extract via tree-sitter string node as first statement in body
- **Complexity**: Count branch points (if, elif, for, while, try, except, with, and, or, match/case)

### TypeScript / JavaScript
- **Units**: functions, classes, methods, arrow functions (named only), interfaces (TS)
- **Qualified names**: `module.ClassName.methodName`
- **Docstrings**: JSDoc comments (/** ... */) immediately preceding the unit
- **Complexity**: Count branch points (if, for, while, try, catch, switch case, &&, ||, ?:)

### Lua
- **Units**: functions (named and local), methods (via `:`)
- **Qualified names**: `module.function_name`
- **Docstrings**: LuaDoc comments (--- style) immediately preceding
- **Complexity**: Count branch points (if, elseif, for, while, repeat, and, or)

### YAML
- **Units**: Root-level keys only (e.g., `services`, not `services.api.port`)
- **Qualified names**: Key name (e.g., `services`)
- **Content**: Full YAML subtree serialized as string
- **Complexity**: N/A (always None)

### JSON
- **Units**: Root-level keys only (e.g., `dependencies`, not `dependencies.axios`)
- **Qualified names**: Key name (e.g., `dependencies`)
- **Content**: Full JSON subtree serialized as string
- **Complexity**: N/A (always None)

## Embedding Strategy

For each SemanticUnit, create an embedding from:
```
{signature}

{docstring if present, else empty}

{content truncated to 2000 chars if longer}
```

**Batching**: Embed units in batches of up to `EMBEDDING_BATCH_SIZE` (100) to avoid memory issues and respect any API limits.

## Error Handling

Errors are accumulated, not thrown, to allow partial indexing:

```python
class IndexingError:
    file_path: str
    error_type: str  # One of:
    #   - "parse_error": Tree-sitter failed to parse
    #   - "encoding_error": File is not valid UTF-8
    #   - "io_error": File read failed (permissions, not found, etc.)
    #   - "embedding_error": EmbeddingService failed
    message: str
```

**Behavior**:
- Parse errors: Log warning, skip file, continue with next
- Encoding errors: Log warning, skip file, continue
- Binary files: Skip silently (detected by null bytes in first 8KB)
- IO errors: Log error, skip file, continue
- Embedding errors: Log error, skip batch, continue with next batch

All errors are recorded in `IndexingStats.errors` for caller inspection.

## Acceptance Criteria

### Functional
1. Can parse Python files and extract functions, classes, methods
2. Can parse TypeScript/JavaScript files and extract functions, classes, methods, interfaces
3. Can parse Lua files and extract functions
4. Can parse YAML/JSON files and extract root-level keys only
5. Index stores units in VectorStore with correct payloads
6. Index tracks files in SQLite for change detection
7. Reindexing only processes files where mtime OR content hash changed
8. Reindexing deletes old entries before adding new ones (no orphans)
9. Remove cleans up both VectorStore and SQLite

### Quality
1. Handles malformed files: logs warning, skips, continues
2. Handles files with syntax errors: extracts what's parseable, logs partial
3. Handles binary files: detects via null bytes, skips silently
4. Handles very large files (>10k lines): processes without OOM
5. Handles non-UTF8 encoding: detects, logs warning, skips

### Performance
Measured on M1 MacBook Pro, files <1000 lines, no syntax errors:
1. Parsing: >500 files/second (tree-sitter is fast)
2. Full index (parse + embed + store): >50 files/second
3. Single file index: <200ms end-to-end
4. Memory: <500MB RSS for indexing 10k files

## Testing Strategy

### Unit Tests
- Parser extracts correct units from sample files (each language)
- Parser detects language from extension correctly
- Parser handles edge cases: empty files, syntax errors, binary detection
- Indexer generates correct IDs (deterministic, collision-resistant)
- Indexer deletes old entries before reindexing
- Change detection works (mtime fast-path, hash verification)
- Error accumulation works (doesn't fail fast)

### Integration Tests
- Index a real codebase directory (this repo's `learning-memory-server/`)
- Verify search returns relevant results
- Verify reindex detects changes correctly
- Verify no orphan entries after rename/delete

### Test Fixtures
Create sample files in `tests/fixtures/code_samples/`:
- `sample.py` - Python with functions, classes, methods, docstrings
- `sample.ts` - TypeScript with classes, interfaces, JSDoc
- `sample.js` - JavaScript with functions, arrow functions
- `sample.lua` - Lua with functions, local functions, LuaDoc
- `sample.yaml` - YAML configuration (test root-level extraction)
- `sample.json` - JSON configuration (test root-level extraction)
- `malformed.py` - Syntax errors (partial extraction test)
- `large_file.py` - 5000+ lines (memory test)
- `empty.py` - Empty file
- `non_utf8.py` - Latin-1 encoded file (encoding detection test)
- `binary.dat` - Binary file (skip detection test)

## Out of Scope

- Call graph extraction (SPEC-002-XX)
- Incremental parsing (full file reparse on change)
- Symbol resolution across files
- Import/dependency tracking
- AST caching

## Notes

- Use `tree-sitter-languages` package for bundled grammars
- All I/O methods are async; CPU-bound parsing uses `run_in_executor`
- Embedding happens via existing EmbeddingService
- Vector storage via existing VectorStore abstraction
- Logging via `structlog` following existing codebase patterns
