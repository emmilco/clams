## SPEC-034: Parameter Validation with Production Data

### Summary
Added data generators and validation tests that use production-like data profiles to catch parameter tuning issues.

### Changes
- Added `tests/fixtures/data_profiles.py` with profile dataclasses:
  - EmbeddingProfile, GHAPDataProfile, MemoryProfile, CodeProfile, CommitProfile
  - Preset profiles: PRODUCTION_LIKE_EMBEDDING, DIFFUSE_CLOUD_EMBEDDING, etc.
- Added `tests/fixtures/generators/` package:
  - embeddings.py - clusterable embedding generation
  - ghap.py - GHAP entry generation
  - temporal.py - temporal pattern generation
  - memories.py - memory corpus generation
  - code.py - code unit generation
  - commits.py - commit history generation
- Added `tests/validation/` test suite:
  - test_clustering.py - clustering with production-like data
  - test_search_pagination.py - pagination and score distribution
  - test_memory_operations.py - large corpus and category skew
  - test_temporal_patterns.py - burst patterns and time ranges
  - test_parameter_robustness.py - HDBSCAN parameter validation
- 73 validation tests marked with @pytest.mark.validation
- Addresses BUG-031 (clustering parameters too conservative)
