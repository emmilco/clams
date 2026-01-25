## SPEC-028: Document Fork/Daemon Constraint

### Summary
Documents the critical constraint that torch/sentence_transformers must not be imported at module level due to MPS fork() incompatibility.

### Changes
- Added detailed docstring to src/clams/server/main.py explaining the fork/daemon constraint
- Documented why top-level imports of torch/sentence_transformers cause crashes
- Added references to BUG-037 and BUG-042 for historical context
- Made the constraint discoverable at the point of enforcement (daemonization)
