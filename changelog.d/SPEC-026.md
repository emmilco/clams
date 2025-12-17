## SPEC-026: Pre-commit Hook for Heavy Import Detection

### Summary
Adds a pre-commit hook that uses AST analysis to detect top-level imports of heavy packages (torch, sentence_transformers, transformers, nomic) that cause startup delays and fork failures.

### Changes
- Added `.claude/hooks/check_heavy_imports.py` with AST-based import detection
- Hook detects forbidden imports at module level but allows lazy imports inside functions
- Hook respects TYPE_CHECKING guards and designated leaf modules (minilm.py, nomic.py)
- Test files are automatically excluded from checking
- Clear error messages explain the issue and show correct lazy import pattern
- Registered in `.pre-commit-config.yaml` to run on all Python files

### References
- Related bugs: BUG-037 (startup latency), BUG-042 (MPS fork safety)
