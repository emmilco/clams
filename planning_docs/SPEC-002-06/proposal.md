# SPEC-002-06: CodeParser + CodeIndexer - Technical Proposal

## Problem Statement

The Learning Memory Server needs to enable semantic code search across codebases. This requires:

1. **Parsing source files** into meaningful semantic units (functions, classes, methods) using tree-sitter
2. **Indexing parsed units** by embedding them and storing them in the vector store
3. **Change detection** to avoid reindexing unchanged files
4. **Error resilience** to handle malformed files without failing the entire indexing operation

The spec defines clear interfaces for CodeParser and CodeIndexer, along with storage schemas. This proposal details the implementation strategy.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CodeIndexer                          │
│  - Orchestrates parsing + embedding + storage               │
│  - Manages batch embedding (100 units max)                  │
│  - Handles change detection via MetadataStore               │
│  - Accumulates errors instead of failing fast               │
└───────┬─────────────┬─────────────┬────────────────┬────────┘
        │             │             │                │
        v             v             v                v
  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐
  │  Code   │  │Embedding │  │  Vector  │  │   Metadata   │
  │ Parser  │  │ Service  │  │  Store   │  │    Store     │
  └─────────┘  └──────────┘  └──────────┘  └──────────────┘
       │
       v
┌──────────────────────────────────────────────────────────────┐
│              TreeSitterParser                                 │
│  - Wraps tree-sitter-languages                               │
│  - Extracts: functions, classes, methods, YAML/JSON keys     │
│  - Computes complexity (cyclomatic)                          │
│  - Extracts docstrings (language-specific)                   │
│  - Uses run_in_executor for CPU-bound parsing                │
└──────────────────────────────────────────────────────────────┘
```

---

## Module Structure

### 1. File Organization

```
src/learning_memory_server/
├── indexers/
│   ├── __init__.py          # Exports: CodeParser, CodeIndexer, TreeSitterParser
│   ├── base.py              # Abstract CodeParser interface + types
│   ├── tree_sitter.py       # TreeSitterParser implementation
│   ├── indexer.py           # CodeIndexer implementation
│   └── utils.py             # Shared utilities (ID generation, hashing)
└── storage/
    └── schema.py            # (extend) Add code_units collection constants

tests/
├── indexers/
│   ├── __init__.py
│   ├── test_tree_sitter.py  # Parser unit tests
│   ├── test_indexer.py      # Indexer unit tests
│   └── test_integration.py  # End-to-end indexing tests
└── fixtures/
    └── code_samples/        # Sample files for each language
        ├── sample.py
        ├── sample.ts
        ├── sample.js
        ├── sample.lua
        ├── sample.yaml
        ├── sample.json
        ├── malformed.py
        ├── large_file.py
        ├── empty.py
        └── binary.dat
```

---

## Detailed Design

### 2.1 Base Types (`indexers/base.py`)

```python
"""Base types and interfaces for code parsing and indexing."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class UnitType(Enum):
    """Type of semantic unit extracted from code."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    MODULE = "module"
    KEY = "key"  # YAML/JSON root keys


@dataclass
class SemanticUnit:
    """A semantic unit extracted from source code."""
    name: str
    qualified_name: str  # e.g., "module.ClassName.method_name"
    unit_type: UnitType
    signature: str       # e.g., "def foo(x: int) -> bool"
    content: str         # Full source code
    file_path: str
    start_line: int
    end_line: int
    language: str
    docstring: Optional[str] = None
    complexity: Optional[int] = None  # Cyclomatic complexity


@dataclass
class IndexingError:
    """Error encountered during indexing."""
    file_path: str
    error_type: str  # parse_error, encoding_error, io_error, embedding_error
    message: str


@dataclass
class IndexingStats:
    """Statistics from an indexing operation."""
    files_indexed: int
    units_indexed: int
    files_skipped: int
    errors: list[IndexingError] = field(default_factory=list)
    duration_ms: int = 0


class ParseError(Exception):
    """Exception raised during code parsing."""
    def __init__(self, error_type: str, message: str, file_path: str = ""):
        self.error_type = error_type  # parse_error, encoding_error, io_error
        self.message = message
        self.file_path = file_path
        super().__init__(f"{error_type}: {message}")


class CodeParser(ABC):
    """Abstract interface for parsing code into semantic units."""

    @abstractmethod
    async def parse_file(self, path: str) -> list[SemanticUnit]:
        """Parse a file and extract semantic units.

        Must use run_in_executor for CPU-bound tree-sitter parsing.

        Raises:
            ParseError: If file cannot be parsed (encoding, IO, or syntax error)
        """
        pass

    @abstractmethod
    def supported_languages(self) -> list[str]:
        """Return list of supported language identifiers."""
        pass

    @abstractmethod
    def detect_language(self, path: str) -> str | None:
        """Detect language from file extension."""
        pass
```

---

### 2.2 TreeSitterParser (`indexers/tree_sitter.py`)

**Key Implementation Details**:

1. **Language Detection**: Use file extension mapping
   ```python
   EXTENSION_MAP = {
       ".py": "python",
       ".ts": "typescript", ".tsx": "typescript",
       ".js": "javascript", ".jsx": "javascript",
       ".lua": "lua",
       ".yaml": "yaml", ".yml": "yaml",
       ".json": "json",
   }
   ```

2. **Parser Initialization**: Load tree-sitter grammars on init
   ```python
   from tree_sitter import Node  # For type hints
   from tree_sitter_languages import get_parser, get_language

   def __init__(self):
       self._parsers = {
           "python": get_parser("python"),
           "typescript": get_parser("typescript"),
           "javascript": get_parser("javascript"),
           "lua": get_parser("lua"),
       }
       self._languages = {k: get_language(k) for k in self._parsers}
   ```

3. **Async Parsing**: Use executor for CPU-bound work
   ```python
   async def parse_file(self, path: str) -> list[SemanticUnit]:
       loop = asyncio.get_event_loop()
       return await loop.run_in_executor(
           None, self._parse_file_sync, path
       )
   ```

4. **Unit Extraction by Language**:
   - **Python**: Query for `function_definition`, `class_definition`
     - Methods: functions inside classes
     - Qualified names: Use parent class name if present
     - Docstrings: First string literal in body
     - Complexity: Count if/elif/for/while/try/except/with/and/or/match/case nodes

   - **TypeScript/JavaScript**: Query for `function_declaration`, `method_definition`, `class_declaration`, `arrow_function` (named), `interface_declaration` (TS)
     - JSDoc: Extract `/** */` comments immediately before unit
     - Complexity: Count if/for/while/try/catch/switch/case/&&/||/?: nodes

   - **Lua**: Query for `function_declaration`, `local_function`, method syntax (`:`)
     - LuaDoc: Extract `---` comments before unit
     - Complexity: Count if/elseif/for/while/repeat/and/or nodes

   - **YAML/JSON**: Use stdlib parsers (yaml/json modules, not tree-sitter), extract root keys only
     - Content: Serialize subtree back to string
     - No complexity, no docstrings

5. **Error Handling**:
   ```python
   def _parse_file_sync(self, path: str) -> list[SemanticUnit]:
       try:
           # Detect binary files (null bytes in first 8KB)
           with open(path, 'rb') as f:
               sample = f.read(8192)
               if b'\x00' in sample:
                   return []  # Skip silently

           # Read as UTF-8
           with open(path, 'r', encoding='utf-8') as f:
               source = f.read()
       except UnicodeDecodeError:
           raise ParseError("encoding_error", "Not valid UTF-8")
       except IOError as e:
           raise ParseError("io_error", str(e))

       # Parse with tree-sitter...
   ```

6. **Qualified Name Construction**:
   ```python
   def _build_qualified_name(
       self, file_path: str, node: Node, class_name: Optional[str]
   ) -> str:
       module = Path(file_path).stem
       name = self._extract_name(node)

       if class_name:
           return f"{module}.{class_name}.{name}"
       return f"{module}.{name}"
   ```

---

### 2.3 CodeIndexer (`indexers/indexer.py`)

**Core Workflow**:

```python
async def index_file(self, path: str, project: str) -> int:
    """Index a single file."""

    # 1. Check if reindex needed
    if not await self.needs_reindex(path, project):
        logger.info("file_skipped", path=path, reason="no_changes")
        return 0

    # 2. Parse file
    try:
        units = await self.parser.parse_file(path)
    except ParseError as e:
        logger.warning("parse_failed", path=path, error=e.message)
        return 0

    if not units:
        return 0

    # 3. Delete old entries (prevent orphans)
    await self._delete_file_units(path, project)

    # 4. Generate IDs and embeddings
    unit_ids = [generate_unit_id(project, path, u.qualified_name) for u in units]
    embeddings = await self._embed_units(units)

    # 5. Store in vector store
    for unit, unit_id, embedding in zip(units, unit_ids, embeddings):
        payload = self._build_payload(unit, project)
        await self.vector_store.upsert(
            collection="code_units",
            id=unit_id,
            vector=embedding,
            payload=payload,
        )

    # 6. Update metadata store
    file_hash = self._compute_file_hash(path)
    mtime = Path(path).stat().st_mtime
    await self.metadata_store.add_indexed_file(
        file_path=path,
        project=project,
        language=self.parser.detect_language(path),
        file_hash=file_hash,
        unit_count=len(units),
        last_modified=datetime.fromtimestamp(mtime),
    )

    return len(units)
```

**Batch Embedding**:

```python
async def _embed_units(self, units: list[SemanticUnit]) -> list[Vector]:
    """Embed units in batches of EMBEDDING_BATCH_SIZE."""
    embeddings = []

    for i in range(0, len(units), self.EMBEDDING_BATCH_SIZE):
        batch = units[i:i + self.EMBEDDING_BATCH_SIZE]
        texts = [self._prepare_embedding_text(u) for u in batch]

        try:
            batch_embeddings = await self.embedding_service.embed_batch(texts)
            embeddings.extend(batch_embeddings)
        except EmbeddingModelError as e:
            logger.error("embedding_failed", batch_size=len(batch), error=str(e))
            raise

    return embeddings

def _prepare_embedding_text(self, unit: SemanticUnit) -> str:
    """Format unit for embedding."""
    parts = [unit.signature]

    if unit.docstring:
        parts.append(unit.docstring)

    content = unit.content
    if len(content) > 2000:
        content = content[:2000]
    parts.append(content)

    return "\n\n".join(parts)
```

**Change Detection**:

```python
async def needs_reindex(self, path: str, project: str) -> bool:
    """Check if file needs reindexing."""
    # Check if file exists in metadata
    indexed_file = await self.metadata_store.get_indexed_file(path, project)
    if not indexed_file:
        return True  # New file

    # Fast path: check mtime
    current_mtime = Path(path).stat().st_mtime
    if current_mtime <= indexed_file.last_modified.timestamp():
        return False  # Unchanged

    # Slow path: compute hash and compare
    current_hash = self._compute_file_hash(path)
    return current_hash != indexed_file.file_hash
```

**Directory Indexing**:

```python
async def index_directory(
    self,
    path: str,
    project: str,
    recursive: bool = True,
    exclude_patterns: list[str] | None = None,
) -> IndexingStats:
    """Index all supported files in directory."""
    start_time = time.time()
    stats = IndexingStats(files_indexed=0, units_indexed=0, files_skipped=0)

    # Find all files
    files = self._find_files(path, recursive, exclude_patterns)

    # Index each file
    for file_path in files:
        try:
            units_count = await self.index_file(file_path, project)
            if units_count > 0:
                stats.files_indexed += 1
                stats.units_indexed += units_count
            else:
                stats.files_skipped += 1
        except Exception as e:
            error = IndexingError(
                file_path=file_path,
                error_type=self._classify_error(e),
                message=str(e),
            )
            stats.errors.append(error)
            logger.warning("file_index_failed", path=file_path, error=str(e))

    stats.duration_ms = int((time.time() - start_time) * 1000)
    return stats

def _classify_error(self, error: Exception) -> str:
    """Classify exception into error type for reporting."""
    if isinstance(error, ParseError):
        return error.error_type
    elif isinstance(error, IOError):
        return "io_error"
    elif isinstance(error, UnicodeDecodeError):
        return "encoding_error"
    else:
        return "unknown_error"

def _find_files(
    self, root: str, recursive: bool, exclude_patterns: list[str] | None
) -> list[str]:
    """Find all supported files in directory."""
    supported_exts = {ext for ext in EXTENSION_MAP.keys()}
    files = []

    root_path = Path(root)
    pattern = "**/*" if recursive else "*"

    for path in root_path.glob(pattern):
        if not path.is_file():
            continue
        if path.suffix not in supported_exts:
            continue
        if self._should_exclude(str(path), exclude_patterns):
            continue
        files.append(str(path))

    return files

def _should_exclude(self, path: str, patterns: list[str] | None) -> bool:
    """Check if path matches any exclusion pattern.

    Patterns use glob syntax:
    - '**/node_modules/**' - exclude node_modules anywhere
    - '**/__pycache__/**' - exclude Python cache dirs
    - '**/vendor/**' - exclude vendor directories
    - '*.min.js' - exclude minified JS files
    - 'tests/**' - exclude tests directory at root

    Example usage:
        exclude_patterns=[
            '**/node_modules/**',
            '**/__pycache__/**',
            '**/.*',  # hidden files/dirs
            '**/*.min.js',
        ]
    """
    if not patterns:
        return False

    from fnmatch import fnmatch
    for pattern in patterns:
        if fnmatch(path, pattern):
            return True
    return False

async def remove_file(self, path: str, project: str) -> int:
    """Remove all indexed units for a file.

    Deletes both vector store entries and metadata.
    Returns count of units removed.
    """
    # Count units before deletion
    count = await self._count_file_units(path, project)

    await self._delete_file_units(path, project)
    await self.metadata_store.delete_indexed_file(path, project)
    logger.info("file_removed", path=path, project=project, units_removed=count)

    return count

async def remove_project(self, project: str) -> int:
    """Remove all indexed units for a project.

    Deletes both vector store entries and metadata.
    Returns count of files removed.
    """
    # Get all files for this project
    files = await self.metadata_store.list_indexed_files(project=project)

    # Delete each file's units
    for file_info in files:
        await self._delete_file_units(file_info.file_path, project)

    # Delete metadata
    await self.metadata_store.delete_project(project)
    logger.info("project_removed", project=project, files_count=len(files))

    return len(files)

async def get_indexing_stats(self, project: str | None = None) -> dict:
    """Get indexing statistics.

    Returns summary of indexed files, units, languages, etc.
    """
    files = await self.metadata_store.list_indexed_files(project=project)

    total_files = len(files)
    total_units = sum(f.unit_count for f in files)
    languages = {}

    for file_info in files:
        lang = file_info.language or "unknown"
        languages[lang] = languages.get(lang, 0) + 1

    return {
        "total_files": total_files,
        "total_units": total_units,
        "languages": languages,
        "projects": len(set(f.project for f in files)) if project is None else 1,
    }

async def is_file_indexed(self, path: str, project: str) -> bool:
    """Check if a file is indexed."""
    file_info = await self.metadata_store.get_indexed_file(path, project)
    return file_info is not None

async def _count_file_units(self, path: str, project: str) -> int:
    """Count units for a file in the vector store."""
    results = await self.vector_store.query(
        collection=self.COLLECTION_NAME,
        filter={"file_path": path, "project": project},
        limit=1000,  # Arbitrary large number
    )
    return len(results)

async def _delete_file_units(self, path: str, project: str) -> None:
    """Delete all vector store entries for a file.

    This is a helper method used during reindexing and file removal.
    """
    # Query vector store for all units from this file
    results = await self.vector_store.query(
        collection=self.COLLECTION_NAME,
        filter={"file_path": path, "project": project},
        limit=1000,  # Arbitrary large number
    )

    # Delete each unit
    for result in results:
        await self.vector_store.delete(
            collection=self.COLLECTION_NAME,
            id=result.id,
        )

    logger.debug("file_units_deleted", path=path, project=project, count=len(results))
```

---

### 2.4 Utilities (`indexers/utils.py`)

```python
"""Utility functions for code indexing."""

import hashlib
from pathlib import Path


def generate_unit_id(project: str, file_path: str, qualified_name: str) -> str:
    """Generate unique ID for a semantic unit.

    Uses SHA-256 hash of project:file_path:qualified_name.
    Truncated to 32 chars (128 bits) for readability.
    """
    content = f"{project}:{file_path}:{qualified_name}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


def compute_file_hash(path: str) -> str:
    """Compute SHA-256 hash of file contents."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def detect_binary(path: str, sample_size: int = 8192) -> bool:
    """Detect if file is binary by checking for null bytes."""
    try:
        with open(path, 'rb') as f:
            sample = f.read(sample_size)
            return b'\x00' in sample
    except IOError:
        return False
```

---

## Storage Schema

### Vector Store Collection: `code_units`

**Payload structure**:
```python
{
    "id": str,              # SHA-256 hash (32 chars)
    "project": str,
    "file_path": str,
    "name": str,            # Short name
    "qualified_name": str,  # Full path
    "unit_type": str,       # function, class, method, etc.
    "signature": str,
    "language": str,
    "start_line": int,
    "end_line": int,
    "line_count": int,      # Computed
    "complexity": int | None,
    "has_docstring": bool,
    "indexed_at": str,      # ISO timestamp
}
```

**Notes**:
- Use existing `VectorStore.upsert()` method
- No changes needed to VectorStore interface

**Collection Initialization**:
```python
class CodeIndexer:
    COLLECTION_NAME = "code_units"

    async def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        try:
            await self.vector_store.create_collection(
                name=self.COLLECTION_NAME,
                dimension=self.embedding_service.dimension,
            )
        except (ValueError, Exception) as e:
            # Collection may already exist - log and continue
            logger.debug("collection_init", name=self.COLLECTION_NAME,
                        status="already_exists_or_skipped", error=str(e))

    async def index_file(self, path: str, project: str) -> int:
        await self._ensure_collection()  # Lazy init on first use
        # ... rest of indexing logic
```

### SQLite Metadata: `indexed_files` table

Already exists in `storage/schema.py`. No changes needed.

**Usage**:
- `add_indexed_file()` - Upsert after successful index
- `get_indexed_file()` - Check for changes
- `delete_indexed_file()` - Cleanup on file removal

---

## Complexity Calculation

Cyclomatic complexity = 1 + number of branch points

**Branch points by language**:

- **Python**: `if`, `elif`, `for`, `while`, `try`, `except`, `with`, `and`, `or`, `match`, `case`
- **TypeScript/JavaScript**: `if`, `for`, `while`, `try`, `catch`, `switch`, `case`, `&&`, `||`, `?:`
- **Lua**: `if`, `elseif`, `for`, `while`, `repeat`, `and`, `or`
- **YAML/JSON**: N/A (always None)

**Implementation**:
```python
def _compute_complexity(self, node: Node, language: str) -> int:
    """Compute cyclomatic complexity for a function/method."""
    branch_nodes = BRANCH_TYPES[language]
    count = 1  # Base complexity

    for child in node.walk():
        if child.type in branch_nodes:
            count += 1

    return count

BRANCH_TYPES = {
    "python": {
        "if_statement", "elif_clause", "for_statement", "while_statement",
        "try_statement", "except_clause", "with_statement",
        "boolean_operator",  # and, or
        "match_statement", "case_clause"
    },
    "typescript": {
        "if_statement", "for_statement", "while_statement", "do_statement",
        "try_statement", "catch_clause", "switch_statement", "switch_case",
        "binary_expression",  # &&, ||
        "ternary_expression"  # ?:
    },
    # ... similar for javascript, lua
}
```

---

## Error Handling Strategy

**Principle**: Accumulate errors, don't fail fast. This allows partial indexing.

**Error Types**:
1. **parse_error**: Tree-sitter parsing failed (syntax errors, corrupted file)
2. **encoding_error**: File is not valid UTF-8
3. **io_error**: File read failed (permissions, not found)
4. **embedding_error**: Embedding service failed

**Behavior**:
- **Binary files**: Skip silently (no error logged)
- **Parse errors**: Log warning, add to `IndexingStats.errors`, continue
- **Encoding errors**: Log warning, add to errors, continue
- **IO errors**: Log error, add to errors, continue
- **Embedding errors**: Log error, propagate (fail batch, not entire operation)

**Logging**:
Use `structlog` with structured fields:
```python
logger = structlog.get_logger(__name__)
logger.info("file_indexed", path=path, units=len(units), duration_ms=elapsed)
logger.warning("parse_failed", path=path, error_type="syntax", message=str(e))
logger.error("embedding_failed", batch_size=len(batch), error=str(e))
```

---

## Testing Strategy

### Unit Tests (`tests/indexers/test_tree_sitter.py`)

1. **Language detection**:
   - Test each extension maps to correct language
   - Test unsupported extension returns None

2. **Parsing correctness** (per language):
   - Python: Extract functions, classes, methods
   - TypeScript: Extract functions, classes, interfaces
   - JavaScript: Extract functions, arrow functions
   - Lua: Extract functions, local functions
   - YAML/JSON: Extract root keys only

3. **Docstring extraction**:
   - Python: Triple-quoted strings
   - TypeScript/JavaScript: JSDoc comments
   - Lua: LuaDoc comments

4. **Complexity calculation**:
   - Simple function (complexity=1)
   - Function with if/for (complexity=3)
   - Nested conditions

5. **Edge cases**:
   - Empty file -> empty list
   - Binary file -> empty list
   - Syntax error -> ParseError
   - Non-UTF8 -> ParseError

### Integration Tests (`tests/indexers/test_indexer.py`)

1. **Basic indexing**:
   - Index single file -> correct count
   - Verify vector store contains units
   - Verify metadata store updated

2. **Batch embedding**:
   - Index file with 150+ units (tests batching)
   - Verify all units embedded correctly

3. **Change detection**:
   - Index file twice -> second is skipped
   - Modify file -> reindex triggers
   - Touch file (mtime only) -> reindex triggers, hash check skips

4. **Orphan prevention**:
   - Index file with 5 units
   - Modify file to have 3 units
   - Reindex -> only 3 units remain (2 deleted)

5. **Error accumulation**:
   - Index directory with mix of valid/invalid files
   - Verify valid files indexed
   - Verify errors collected in stats

6. **Cleanup**:
   - `remove_file()` deletes vector + metadata entries
   - `remove_project()` deletes all project data

### E2E Tests (`tests/indexers/test_integration.py`)

1. **Index real codebase**:
   - Index `learning-memory-server/src/` directory
   - Verify > 50 units indexed
   - Verify search returns relevant results

2. **Incremental indexing**:
   - Index directory
   - Add new file
   - Reindex -> only new file processed

### Test Fixtures (`tests/fixtures/code_samples/`)

Create realistic sample files for each language:

- **sample.py**: 5 functions, 2 classes with methods, docstrings, various complexity
- **sample.ts**: Class, interface, functions, JSDoc comments
- **sample.js**: Functions, arrow functions, JSDoc
- **sample.lua**: Functions, local functions, methods (`:` syntax)
- **sample.yaml**: Multi-level config (test only root keys extracted)
- **sample.json**: Package.json style (test only root keys extracted)
- **malformed.py**: Syntax error (unclosed bracket)
- **large_file.py**: 5000+ lines (generate via script)
- **empty.py**: Empty file
- **binary.dat**: Binary file (e.g., PNG header bytes)
- **non_utf8.py**: Latin-1 encoded file (for encoding detection testing)

---

## Performance Considerations

**Target Performance** (M1 MacBook Pro):
- Parsing: >500 files/second
- Full indexing: >50 files/second
- Single file: <200ms end-to-end
- Memory: <500MB for 10k files

**Optimization Strategies**:

1. **Async everywhere**: Use `run_in_executor` for CPU-bound parsing
2. **Batch embedding**: 100 units per batch avoids memory spikes
3. **Change detection**: mtime check before expensive hash computation
4. **Incremental indexing**: Only process changed files
5. **Delete before insert**: Prevents orphan accumulation

**Memory Management**:
- Parse one file at a time (don't load all files into memory)
- Embed in batches (not entire file at once)
- Stream directory traversal (use generator pattern)

---

## Alternatives Considered

### 1. AST-based parsing (Python `ast` module)

**Pros**: Native Python, no dependencies
**Cons**: Language-specific, no unified interface, can't handle syntax errors

**Decision**: Tree-sitter provides unified interface across languages and robust error handling.

### 2. Store full content in vector store payload

**Pros**: No need to read file for display
**Cons**: Large payload size, vector store bloat

**Decision**: Store only metadata in payload. Content can be read from filesystem on demand.

### 3. Embed signature only (not content)

**Pros**: Faster embedding, smaller vectors
**Cons**: Poor search quality (misses implementation details)

**Decision**: Embed signature + docstring + truncated content (2000 chars) for rich semantic search.

### 4. Hash-based IDs instead of SHA-256

**Pros**: Shorter IDs
**Cons**: Higher collision risk, not deterministic across runs

**Decision**: SHA-256 truncated to 32 chars provides good balance of uniqueness and readability.

### 5. Store change detection in vector store payload

**Pros**: Fewer dependencies
**Cons**: SQLite is more efficient for metadata queries, payload bloat

**Decision**: Use SQLite `indexed_files` table for change detection.

---

## Open Questions

None at this time. The spec is comprehensive and all design decisions have clear rationales.

---

## Implementation Checklist

1. [ ] Create `indexers/base.py` with types and interfaces
2. [ ] Create `indexers/utils.py` with ID generation and hashing
3. [ ] Implement `TreeSitterParser` for Python
4. [ ] Extend `TreeSitterParser` for TypeScript/JavaScript
5. [ ] Extend `TreeSitterParser` for Lua
6. [ ] Extend `TreeSitterParser` for YAML/JSON
7. [ ] Implement `CodeIndexer` core logic
8. [ ] Implement batch embedding
9. [ ] Implement change detection
10. [ ] Implement directory indexing
11. [ ] Write unit tests for parser (each language)
12. [ ] Write unit tests for indexer
13. [ ] Write integration tests
14. [ ] Create test fixtures
15. [ ] Performance benchmarks
16. [ ] Documentation (docstrings + examples)

---

## Summary

This proposal provides a complete implementation plan for CodeParser and CodeIndexer:

- **Modular design**: Parser and indexer are separate, testable components
- **Language support**: Python, TypeScript, JavaScript, Lua, YAML, JSON via tree-sitter
- **Robust error handling**: Accumulates errors instead of failing fast
- **Efficient change detection**: mtime + hash-based to minimize reindexing
- **Batch processing**: 100-unit batches prevent memory issues
- **Orphan prevention**: Delete old entries before reindexing
- **Comprehensive testing**: Unit tests, integration tests, fixtures for all languages

The implementation follows existing codebase patterns (async/await, structlog, dataclasses, type hints) and integrates cleanly with the existing EmbeddingService, VectorStore, and MetadataStore abstractions.
