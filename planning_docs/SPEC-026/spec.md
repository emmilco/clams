# SPEC-026: Pre-commit Hook for Heavy Import Detection

## Problem Statement

### Background

CLAMS uses PyTorch-based embedding models (sentence-transformers, nomic) for semantic code search and memory functionality. These packages initialize GPU backends (MPS on macOS, CUDA on Linux) at import time, causing two critical issues:

1. **Startup Latency (BUG-037)**: Importing PyTorch and related packages takes 4-6 seconds, making CLI tools feel sluggish. This affected the installation verification script, which had to increase its timeout from 5 to 30 seconds.

2. **Fork Safety (BUG-042)**: On macOS with Apple Silicon, the MPS (Metal Performance Shaders) backend cannot be forked after initialization. When the daemon calls `os.fork()` to daemonize, any prior PyTorch import causes a crash:
   ```
   objc[42701]: +[MPSGraphObject initialize] may have been in progress in another thread when fork() was called.
   We cannot safely call it or ignore it in the fork() child process. Crashing instead.
   ```

### Root Cause

The import chain `main.py -> clams.embedding -> nomic.py -> torch` causes PyTorch to initialize MPS before the daemon has a chance to fork. This is a fundamental architectural constraint: **fork must happen before heavy imports**.

### Current Mitigations

The codebase uses lazy imports to defer PyTorch loading:
- `src/clams/embedding/registry.py` imports MiniLM and Nomic implementations only when `get_code_embedder()` or `get_semantic_embedder()` is called
- The leaf modules (`minilm.py`, `nomic.py`) are allowed to have top-level PyTorch imports because they are never imported directly at startup

However, without automated enforcement, developers may accidentally introduce top-level heavy imports elsewhere, reintroducing these bugs.

## Solution Overview

Implement a pre-commit hook that uses AST analysis to detect top-level imports of "heavy" packages (those that initialize GPU backends or load large models). The hook will:

1. Parse Python files using the `ast` module
2. Identify imports at module level (not inside functions or methods)
3. Flag forbidden packages: `torch`, `sentence_transformers`, `transformers`, `nomic`
4. Allow exceptions for designated "leaf" modules and test files
5. Provide helpful error messages explaining the issue and how to fix it

## Heavy Packages

The following packages are considered "heavy" and must not be imported at module level:

| Package | Reason |
|---------|--------|
| `torch` | Initializes MPS/CUDA backends, 3-5 second load time |
| `sentence_transformers` | Imports torch, loads tokenizers |
| `transformers` | Imports torch, loads model infrastructure |
| `nomic` | Imports torch, downloads model weights |

### Future Considerations

Other packages that may need to be added:
- `tensorflow` (if ever used)
- `onnxruntime` (GPU variants)
- `jax` (if ever used)

## Allowed Patterns

### 1. Lazy Imports Inside Functions

Heavy imports inside functions are allowed because they only execute when the function is called:

```python
# ALLOWED: Lazy import inside function
def get_embeddings(texts: list[str]) -> list[Vector]:
    import torch
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("model-name")
    return model.encode(texts)
```

### 2. TYPE_CHECKING Guard

Imports inside `if TYPE_CHECKING:` blocks are allowed because they only execute during static analysis:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch  # ALLOWED: Only for type hints

def process(tensor: "torch.Tensor") -> None:
    import torch  # Lazy import for runtime
    ...
```

### 3. Designated Leaf Modules

Certain modules are allowed to have top-level heavy imports because they are themselves lazily imported. These "leaf" modules are loaded only when needed:

**Allowed modules:**
- `src/clams/embedding/minilm.py` - Lazily imported by registry.py
- `src/clams/embedding/nomic.py` - Lazily imported by registry.py

### 4. Test Files

Test files may have top-level heavy imports because:
- They don't run in production
- They don't involve daemon forking
- Startup latency is acceptable for tests

**Test file patterns:**
- Files in `tests/` directory
- Files matching `test_*.py` or `*_test.py`
- `conftest.py` files

## Forbidden Patterns

### 1. Top-Level Import Statements

```python
# FORBIDDEN: Top-level import
import torch
from sentence_transformers import SentenceTransformer

def process():
    ...
```

### 2. Top-Level From Imports

```python
# FORBIDDEN: Top-level from import
from torch import nn
from transformers import AutoModel

class MyModel:
    ...
```

### 3. Imports in Class Bodies (Outside Methods)

```python
# FORBIDDEN: Class-level import
class Embedder:
    import torch  # This executes at class definition time

    def embed(self):
        ...
```

## Implementation Approach

### Hook Location

`.claude/hooks/check_heavy_imports.py`

### AST Analysis Strategy

1. **Parse the file**: Use `ast.parse()` to build the syntax tree
2. **Track scope**: Use an AST visitor that tracks whether we're inside a function/method
3. **Check imports**: For each `Import` or `ImportFrom` node at module level:
   - Extract the top-level package name
   - Check if it's in the forbidden set
   - Record violations with file, line, and column
4. **Handle exceptions**:
   - Skip test files (check path patterns)
   - Skip allowed leaf modules (check against allowlist)
   - Allow imports inside `if TYPE_CHECKING:` blocks

### Pre-commit Configuration

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: check-heavy-imports
        name: Check for top-level heavy imports
        description: >
          Detects top-level imports of heavy packages (torch, sentence_transformers,
          transformers, nomic) that cause startup delays and fork failures.
          See BUG-037, BUG-042.
        entry: python .claude/hooks/check_heavy_imports.py
        language: python
        types: [python]
        pass_filenames: true
```

### Error Output Format

The hook should produce clear, actionable error messages:

```
ERROR: Top-level imports of heavy packages detected!

These packages initialize GPU backends at import time, which causes:
  - 4-6 second startup delays
  - Fork failures when daemonizing (os.fork() after PyTorch init fails)

Violations found:
  src/clams/server/tools/search.py:5:0: import torch
  src/clams/context/assembler.py:12:0: from sentence_transformers import SentenceTransformer

To fix, move imports inside functions (lazy import pattern):

  # WRONG - top-level import
  import torch

  def get_embeddings():
      return torch.tensor(...)

  # CORRECT - lazy import inside function
  def get_embeddings():
      import torch  # Only loaded when function is called
      return torch.tensor(...)

See BUG-042, BUG-037 for context.
See src/clams/embedding/registry.py for the correct pattern.
```

## Testing Strategy

### Unit Tests

Create `tests/hooks/test_check_heavy_imports.py`:

1. **Test detection of forbidden imports**:
   - Top-level `import torch`
   - Top-level `from torch import nn`
   - Top-level `import sentence_transformers`
   - Top-level `from transformers import AutoModel`
   - Top-level `import nomic`

2. **Test allowed patterns**:
   - Imports inside functions
   - Imports inside async functions
   - Imports inside methods
   - Imports inside `if TYPE_CHECKING:` blocks

3. **Test file exclusions**:
   - Files in `tests/` directory
   - Files matching `test_*.py`
   - Files matching `*_test.py`
   - `conftest.py` files

4. **Test module exclusions**:
   - `src/clams/embedding/minilm.py`
   - `src/clams/embedding/nomic.py`

### Integration Test

Test the hook runs correctly via pre-commit:

```bash
# Stage a file with forbidden imports
echo "import torch" > /tmp/bad_import.py
cp /tmp/bad_import.py src/clams/test_bad.py
pre-commit run check-heavy-imports --files src/clams/test_bad.py
# Should fail with error message

# Cleanup
rm src/clams/test_bad.py
```

## Acceptance Criteria

### Functional Requirements

1. [ ] Hook detects top-level `import torch` and reports the violation
2. [ ] Hook detects top-level `from torch import X` and reports the violation
3. [ ] Hook detects all heavy packages: `torch`, `sentence_transformers`, `transformers`, `nomic`
4. [ ] Hook allows imports inside functions (lazy imports)
5. [ ] Hook allows imports inside async functions
6. [ ] Hook allows imports inside methods
7. [ ] Hook allows imports inside `if TYPE_CHECKING:` blocks
8. [ ] Hook skips test files (`tests/`, `test_*.py`, `*_test.py`, `conftest.py`)
9. [ ] Hook skips allowed leaf modules (`minilm.py`, `nomic.py`)
10. [ ] Hook produces clear error messages with fix instructions

### Integration Requirements

11. [ ] Hook is registered in `.pre-commit-config.yaml`
12. [ ] Hook runs on all Python files during pre-commit
13. [ ] Hook exits 0 when no violations found
14. [ ] Hook exits 1 when violations found
15. [ ] Hook handles syntax errors gracefully (skip file, don't crash)

### Documentation Requirements

16. [ ] Error message references BUG-037 and BUG-042
17. [ ] Error message shows correct lazy import pattern
18. [ ] Error message points to `registry.py` as reference implementation

### Non-Functional Requirements

19. [ ] Hook completes in <1 second for typical commits
20. [ ] Hook uses only standard library (ast, sys, pathlib) plus typing
21. [ ] Hook is compatible with Python 3.10+

## Dependencies

- **Blocks**: SPEC-028 (Document Fork/Daemon Constraint) - This spec provides the enforcement mechanism referenced by the documentation spec

## References

- **BUG-037**: Install script verification timeout due to model loading
- **BUG-042**: Daemon crashes on macOS due to MPS fork safety
- **Existing Pattern**: `src/clams/embedding/registry.py` - Demonstrates correct lazy import pattern
- **Similar Hook**: `.claude/hooks/check_subprocess.py` - Example of AST-based pre-commit hook in this codebase
