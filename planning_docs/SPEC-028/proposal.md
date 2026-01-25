# SPEC-028 Technical Proposal: Document Fork/Daemon Constraint

## Overview

This proposal details how to document the critical fork/daemon constraint throughout the CLAMS codebase. The constraint prevents importing heavy packages (torch, sentence_transformers, transformers, nomic) at module top level to avoid fork safety issues and slow startup.

**Background**: BUG-042 demonstrated that PyTorch's MPS (Metal Performance Shaders) backend on macOS crashes when `os.fork()` is called after initialization. BUG-037 showed these packages take 4.6-6.2 seconds to import, causing hook timeouts. SPEC-026 implemented automated detection via pre-commit hook; this spec documents the "why" at the point of enforcement.

## Implementation Details

### 1. Server Main Module Docstring Enhancement

**File**: `/Users/elliotmilco/Documents/GitHub/clams/.worktrees/SPEC-028/src/clams/server/main.py`

**Current docstring** (lines 1-6):
```python
"""Main entry point for the CLAMS server.

IMPORTANT: This module minimizes imports at module level to allow fast
argument parsing. Heavy imports (PyTorch, embedding models) are deferred
to _run_server() which is only called after daemon spawning completes.
"""
```

**New docstring**:
```python
"""Main entry point for the CLAMS server.

Fork/Daemon Constraint
======================

This server supports ``--daemon`` mode which uses ``os.fork()`` on macOS/Linux.
PyTorch's MPS backend (macOS GPU) does not support fork after initialization.

**NEVER import these packages at module top level anywhere in the codebase:**

- ``torch`` - initializes GPU backends that don't support fork()
- ``sentence_transformers`` - imports torch
- ``transformers`` - imports torch
- ``nomic`` - imports sentence_transformers

**Correct pattern** (lazy import inside function)::

    def process():
        import torch  # Safe: imported after fork completes
        return torch.tensor([1, 2, 3])

**Wrong pattern** (top-level import)::

    import torch  # FORBIDDEN: initializes MPS before fork

    def process():
        return torch.tensor([1, 2, 3])

**Performance note:** These packages also take 4-6 seconds to import,
causing hook timeouts if imported eagerly.

**References:**

- BUG-042: Daemon crash on macOS due to MPS fork safety
- BUG-037: Heavy imports cause hook timeout
- SPEC-026: Pre-commit hook enforces this constraint automatically

Implementation Note
-------------------

This module minimizes imports at module level to allow fast argument parsing.
Heavy imports (PyTorch, embedding models) are deferred to ``_run_server()``
which is only called after daemon spawning completes.
"""
```

**Rationale for format**:
- Uses reStructuredText format (consistent with Python docstrings)
- Puts the constraint first since it's the most important information
- Shows both correct and incorrect patterns for easy copy-paste
- Links to bug reports and the enforcement mechanism (SPEC-026)
- Preserves the original implementation note at the end

### 2. Embedding Package Docstring Enhancement

**File**: `/Users/elliotmilco/Documents/GitHub/clams/.worktrees/SPEC-028/src/clams/embedding/__init__.py`

**Current docstring** (lines 1-17):
```python
"""Embedding generation and management.

IMPORTANT: This module avoids importing concrete embedding implementations
(MiniLM, Nomic) at module level to prevent loading PyTorch before daemonization.

To get embedders, use the registry functions:
    from clams.embedding import (
        initialize_registry, get_code_embedder, get_semantic_embedder
    )

    initialize_registry(code_model, semantic_model)
    embedder = get_code_embedder()  # Loads model lazily

For direct class access (will load PyTorch):
    from clams.embedding.minilm import MiniLMEmbedding
    from clams.embedding.nomic import NomicEmbedding
"""
```

**New docstring**:
```python
"""Embedding generation and management.

Fork Safety Note
----------------

This module does NOT import heavy dependencies (torch, sentence_transformers)
at the top level. All embedding implementations use lazy imports to avoid:

1. Fork safety issues with MPS backend (BUG-042)
2. Slow import times causing hook timeouts (BUG-037)

See ``src/clams/server/main.py`` docstring for the full constraint documentation.

Usage
-----

To get embedders, use the registry functions::

    from clams.embedding import (
        initialize_registry, get_code_embedder, get_semantic_embedder
    )

    initialize_registry(code_model, semantic_model)
    embedder = get_code_embedder()  # Loads model lazily

For direct class access (will load PyTorch immediately)::

    from clams.embedding.minilm import MiniLMEmbedding
    from clams.embedding.nomic import NomicEmbedding
"""
```

**Rationale**:
- Adds explicit "Fork Safety Note" section
- References the authoritative documentation in main.py
- Links to both bug reports
- Preserves usage information

### 3. Registry Module Comment Enhancement

**File**: `/Users/elliotmilco/Documents/GitHub/clams/.worktrees/SPEC-028/src/clams/embedding/registry.py`

**Current comments** (lines 51-53 and 70-72):
```python
# Lazy import to avoid loading PyTorch before fork
from .minilm import MiniLMEmbedding
```

**Updated comments**:

In `get_code_embedder()` method (line 51-52):
```python
# Lazy import: PyTorch must not be loaded before fork()
# See src/clams/server/main.py docstring and BUG-042
from .minilm import MiniLMEmbedding
```

In `get_semantic_embedder()` method (line 70-71):
```python
# Lazy import: PyTorch must not be loaded before fork()
# See src/clams/server/main.py docstring and BUG-042
from .nomic import NomicEmbedding
```

**Rationale**:
- More explicit about "must not" (imperative)
- References authoritative documentation
- Links to bug report for context

### 4. Registry Module Docstring Enhancement

**File**: `/Users/elliotmilco/Documents/GitHub/clams/.worktrees/SPEC-028/src/clams/embedding/registry.py`

**Current docstring** (lines 1-5):
```python
"""Embedding service registry for dual embedding models.

IMPORTANT: This module defers importing embedding implementations (MiniLM, Nomic)
until actually needed to avoid loading PyTorch before daemonization.
"""
```

**New docstring**:
```python
"""Embedding service registry for dual embedding models.

Fork Safety: This module defers importing embedding implementations (MiniLM,
Nomic) until actually needed. PyTorch must not be loaded before fork() completes
in daemon mode. See ``src/clams/server/main.py`` docstring for full details.
"""
```

**Rationale**:
- Shorter and more direct
- References authoritative documentation
- Uses explicit "Fork Safety" prefix for scannability

### File Summary

| File | Change Type | Purpose |
|------|-------------|---------|
| `src/clams/server/main.py` | Docstring rewrite | Authoritative documentation of the constraint |
| `src/clams/embedding/__init__.py` | Docstring update | Reference constraint, explain lazy imports |
| `src/clams/embedding/registry.py` | Docstring + comments | Reference constraint at point of lazy import |

## Testing Strategy

### Manual Verification

1. **Documentation Clarity Test**
   - Read each updated docstring in isolation
   - Verify a developer unfamiliar with the constraint can understand:
     - What packages are forbidden
     - Why they are forbidden (fork safety + performance)
     - How to fix violations (lazy import pattern)
     - Where to find more context (bug reports)

2. **Cross-Reference Test**
   - Verify `embedding/__init__.py` points to `server/main.py`
   - Verify `embedding/registry.py` points to `server/main.py`
   - Verify all references to BUG-042 and BUG-037 are accurate

3. **Pattern Consistency Test**
   - Search for all existing "lazy import" comments
   - Verify updated comments use consistent terminology

### Automated Verification

```bash
# Verify docstrings contain required keywords
grep -l "fork" src/clams/server/main.py
grep -l "BUG-042" src/clams/server/main.py
grep -l "BUG-037" src/clams/server/main.py
grep -l "torch" src/clams/server/main.py

# Verify embedding module references main.py
grep -l "main.py" src/clams/embedding/__init__.py
grep -l "main.py" src/clams/embedding/registry.py

# Verify no test impact (these are doc changes only)
pytest tests/ -v --tb=short
```

### No Test Code Changes Required

This spec adds only documentation/comments. The existing test suite verifies:
- `tests/server/test_bug_042_regression.py` - Daemon works without MPS crash
- `tests/hooks/test_heavy_imports.py` - Pre-commit hook catches violations
- `tests/performance/test_import_time.py` - Import times are monitored

No new tests are needed since we're documenting existing behavior, not changing it.

## Risks and Mitigations

### Risk 1: Documentation Drift

**Risk**: Documentation becomes outdated if constraint or implementation changes.

**Mitigation**:
- Link to bug reports (immutable history)
- Link to SPEC-026 (pre-commit hook provides enforcement)
- Place documentation at the point of enforcement (main.py) so it's encountered naturally

### Risk 2: Incomplete Coverage

**Risk**: New modules added later may not reference the constraint.

**Mitigation**:
- The pre-commit hook (SPEC-026) provides automated enforcement
- The main.py docstring is the canonical reference
- New embedding modules will naturally follow the lazy import pattern in registry.py

### Risk 3: Docstring Too Long

**Risk**: The main.py docstring becomes unwieldy.

**Mitigation**:
- Keep the constraint documentation focused and structured
- Use clear section headers for skimmability
- The original implementation note is preserved but moved to end

## Design Decisions

### Decision 1: main.py as Canonical Location

**Choice**: Place the authoritative constraint documentation in `src/clams/server/main.py`.

**Alternatives considered**:
- `CLAUDE.md` - Rejected per spec (keep implementation details out)
- Separate documentation file - Rejected (not discoverable)
- `embedding/__init__.py` - Rejected (constraint applies more broadly)

**Rationale**: `main.py` is where daemonization happens, where developers will first encounter fork-related code, and where violations would cause crashes.

### Decision 2: Reference Pattern (Hub-and-Spoke)

**Choice**: Other files reference `main.py` rather than duplicating the full documentation.

**Rationale**:
- Single source of truth
- Easier to maintain
- Prevents documentation drift
- Keeps secondary files focused on their purpose

### Decision 3: reStructuredText Format

**Choice**: Use reStructuredText in docstrings.

**Rationale**:
- Standard Python documentation format
- Renders well in IDEs and documentation tools
- Supports code blocks with `::` syntax
- Consistent with existing codebase style

## Implementation Order

1. Update `src/clams/server/main.py` docstring (authoritative documentation)
2. Update `src/clams/embedding/__init__.py` docstring (reference)
3. Update `src/clams/embedding/registry.py` docstring and comments (reference)
4. Run tests to verify no regressions
5. Manual review of documentation clarity
