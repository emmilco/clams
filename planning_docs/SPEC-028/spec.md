# SPEC-028: Document Fork/Daemon Constraint (R7-C)

## Background

SPEC-026 (Pre-commit Hook for Heavy Import Detection) implemented automated detection of forbidden top-level imports. This spec complements that work by documenting the underlying constraint in the server code where it's enforced.

BUG-042 root cause: The server's `daemonize()` function used `os.fork()`, but PyTorch had already initialized MPS (Metal Performance Shaders) via imports. MPS doesn't support fork after initialization, causing crashes with: `MPSGraphObject initialize may have been in progress in another thread when fork() was called`.

BUG-037 showed that heavy imports (torch, sentence_transformers) cause 4.6-6.2 second delays, exceeding hook timeouts.

## Problem Statement

The constraint "don't import torch/sentence_transformers at module level" is critical for system stability but:
- Not documented where developers will encounter it
- Easy to forget when adding new code
- The "why" is not obvious to new contributors

Without documentation:
- Developers may accidentally add top-level imports
- Pre-commit hook failures are confusing without context
- Bug recurrence is likely when constraints aren't understood

## Goals

1. Document the constraint in `src/clams/server/main.py` (where daemonization happens)
2. Add explanatory comments in relevant source files
3. Link to bug reports for context
4. Make the constraint discoverable at the point of enforcement

## Non-Goals

- Implementing detection (done in SPEC-026)
- Changing how imports work
- Adding runtime enforcement
- Documenting in CLAUDE.md (keep project-specific implementation details out)

## Solution Overview

### 1. Server Main Module Docstring

Update `src/clams/server/main.py` module docstring to document the constraint. Use reStructuredText format (standard Python docstring style) and preserve the existing first line:

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

### 2. Source File Comments

Add/update comments in key files:

**`src/clams/embedding/__init__.py`** - Update docstring to reference constraint and preserve existing usage information:
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

**`src/clams/embedding/registry.py`** - Update module docstring and lazy import comments:
```python
# Module docstring:
"""Embedding service registry for dual embedding models.

Fork Safety: This module defers importing embedding implementations (MiniLM,
Nomic) until actually needed. PyTorch must not be loaded before fork() completes
in daemon mode. See ``src/clams/server/main.py`` docstring for full details.
"""

# In get_code_embedder() method:
# Lazy import: PyTorch must not be loaded before fork()
# See src/clams/server/main.py docstring and BUG-042
from .minilm import MiniLMEmbedding

# In get_semantic_embedder() method:
# Lazy import: PyTorch must not be loaded before fork()
# See src/clams/server/main.py docstring and BUG-042
from .nomic import NomicEmbedding
```

## Acceptance Criteria

- [ ] `src/clams/server/main.py` module docstring contains "Fork/Daemon Constraint" section
- [ ] Docstring lists forbidden packages: torch, sentence_transformers, transformers, nomic
- [ ] Docstring explains WHY (fork safety, MPS backend, import time)
- [ ] Docstring shows correct pattern (lazy import inside function) with code example
- [ ] Docstring shows wrong pattern (top-level import) with code example
- [ ] Docstring links to BUG-042 and BUG-037 in References section
- [ ] Docstring mentions SPEC-026 (pre-commit hook enforcement)
- [ ] `src/clams/embedding/__init__.py` docstring contains "Fork Safety Note" section
- [ ] `src/clams/embedding/__init__.py` references `src/clams/server/main.py`
- [ ] `src/clams/embedding/registry.py` module docstring references main.py
- [ ] `src/clams/embedding/registry.py` lazy import comments reference main.py and BUG-042

## Testing Requirements

- Manual verification that documentation is clear and discoverable
- Grep for existing lazy import patterns to ensure comments are consistent

## Dependencies

- SPEC-026 (Pre-commit Hook for Heavy Import Detection) - DONE

## References

- BUG-042: Daemon crashes on macOS due to MPS fork safety
- BUG-037: Heavy imports cause hook timeout
- R7-C in `planning_docs/tickets/recommendations-r5-r8.md`
