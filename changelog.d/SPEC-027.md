## SPEC-027: Import Time Measurement Test

### Summary
Add comprehensive tests to measure and enforce import time limits for CLAMS modules, preventing accidental eager loading of heavy ML dependencies.

### Changes
- Added parametrized import time tests for 8 critical modules (clams, clams.server, clams.server.main, clams.server.http, clams.server.config, clams.embedding, clams.storage, clams.search)
- Added lazy import isolation tests verifying torch, sentence_transformers, and transformers are not loaded by light imports
- Added actionable error messages with diagnostic commands for import time violations
- Threshold set to 3.0s to accommodate legitimate web framework imports while catching PyTorch loads (4-6s+)
