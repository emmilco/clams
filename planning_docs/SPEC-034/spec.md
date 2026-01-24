# SPEC-034: Parameter Validation with Production Data

## Problem Statement

Several bugs have surfaced only when code encounters realistic production data rather than minimal test cases. Tests pass with synthetic data that does not represent actual usage patterns, leading to failures in production.

### Evidence

1. **BUG-031: Clustering Parameters**
   - Test suite used `min_cluster_size=3` but production used `min_cluster_size=5`
   - 63 real GHAP entries (thematically similar, single diffuse cloud) produced 0 clusters
   - Parameters tuned for well-separated test clusters failed on organic data distribution
   - Root cause: Parameters validated against synthetic data, not realistic data profiles

2. **Test-Production Parameter Divergence**
   - Test fixtures often use minimal data counts (3-5 items) that do not stress boundary conditions
   - Pagination tests use 10-20 items when production may have hundreds
   - Clustering tests use artificially separated clusters when production has overlapping themes

3. **Data Distribution Assumptions**
   - Algorithms assume certain data characteristics (spread, density, count) that match test data
   - Real data often has skewed distributions, noise, and edge cases not covered by tests

### Root Causes

- **No documented data profiles**: Production data characteristics are not formally specified
- **Synthetic test data**: Test fixtures generate arbitrary data rather than representative samples
- **Parameter tuning on tests**: Algorithm parameters optimized for test data, not production patterns
- **Missing boundary testing**: Tests do not exercise upper bounds, density variations, or distribution edge cases

## Proposed Solution

Create a systematic approach to testing with production-like data:

1. **Document Production Data Profiles** for each data type
2. **Create Data Generators** that produce representative test data
3. **Add Validation Tests** that verify algorithm behavior across expected data ranges
4. **Establish Benchmark Tests** that measure performance on realistic data volumes

## Categories of Production-Like Data to Test

### 1. GHAP Entries

| Characteristic | Minimal Test Data | Production-Like Data |
|---------------|-------------------|---------------------|
| Count | 3-10 entries | 20-200 entries |
| Theme distribution | Distinct domains | Single dominant theme with variations |
| Embedding spread | Well-separated clusters | Diffuse cloud, overlapping themes |
| Temporal spread | Same session | Weeks/months of accumulated data |
| Outcome distribution | Even mix | 70% confirmed, 20% falsified, 10% pivoted |

### 2. Memories

| Characteristic | Minimal Test Data | Production-Like Data |
|---------------|-------------------|---------------------|
| Count | 5-20 memories | 50-500 memories |
| Category distribution | Even mix | Skewed (60% facts, 20% preferences, 20% workflow) |
| Importance distribution | Uniform 0.5-0.8 | Bimodal (many at 0.3-0.4, few at 0.9-1.0) |
| Content length | Short strings (10-50 chars) | Variable (10-2000 chars) |
| Tag patterns | 1-2 tags | 0-10 tags, some duplicated across memories |

### 3. Code Units

| Characteristic | Minimal Test Data | Production-Like Data |
|---------------|-------------------|---------------------|
| Count per project | 10-50 units | 500-5000 units |
| File size distribution | Small files (100 lines) | Variable (10-5000 lines) |
| Language mix | Single language | Multiple languages |
| Nested depth | Shallow (1-2 levels) | Deep (5+ levels for complex modules) |
| Documentation | None or minimal | Mixed (some heavily documented, some bare) |

### 4. Git Commits

| Characteristic | Minimal Test Data | Production-Like Data |
|---------------|-------------------|---------------------|
| Count | 10-50 commits | 100-10000 commits |
| Author distribution | Single author | Skewed (80% from top 20% of authors) |
| Temporal patterns | Even spread | Bursts around releases, quiet periods |
| Message length | Short (20 chars) | Variable (10-500 chars with conventions) |
| Files per commit | 1-3 files | Variable (1-50+ files, larger for merges) |

### 5. Clustering Input

| Characteristic | Minimal Test Data | Production-Like Data |
|---------------|-------------------|---------------------|
| Point count | 10-30 points | 20-200 points |
| Cluster structure | Well-separated | Overlapping, varying density |
| Noise ratio | 0-10% | 10-40% noise/outliers |
| Dimensionality | Full 768 dims | Full 768 dims with realistic variance |
| Similarity within theme | High (>0.8) | Moderate (0.5-0.8) |

### 6. Search Results

| Characteristic | Minimal Test Data | Production-Like Data |
|---------------|-------------------|---------------------|
| Result count | 3-10 results | 10-100 potential matches |
| Score distribution | Even high scores | Long tail (few high, many moderate) |
| Pagination | Single page | Multiple pages needed |
| Filter combinations | Single filter | Multiple overlapping filters |

## Data Generation Approaches

### 1. Profile-Based Generators

Create data generators that accept a profile configuration:

```python
@dataclass
class GHAPDataProfile:
    """Defines characteristics of GHAP data to generate."""
    count: int = 50
    theme_count: int = 3  # Number of distinct themes
    theme_skew: float = 0.7  # Probability of dominant theme
    noise_ratio: float = 0.2  # Fraction of outliers
    confirmed_ratio: float = 0.7
    falsified_ratio: float = 0.2
    # Remaining is pivoted

def generate_ghap_entries(profile: GHAPDataProfile) -> list[GHAPEntry]:
    """Generate GHAP entries matching the given profile."""
    ...
```

### 2. Embedding Generators

Generate embeddings with controlled characteristics using profile dataclasses:

```python
@dataclass(frozen=True)
class EmbeddingProfile:
    """Defines characteristics of embedding clusters to generate."""
    n_points: int = 50
    n_clusters: int = 3
    cluster_spread: float = 0.3  # Intra-cluster variance (cosine distance)
    noise_ratio: float = 0.2
    embedding_dim: int = 768
    inter_cluster_distance: float = 0.5  # Minimum distance between centroids


class GeneratedEmbeddings(NamedTuple):
    """Result from embedding generation."""
    embeddings: npt.NDArray[np.float32]
    labels: npt.NDArray[np.int64]  # True cluster labels (-1 for noise)
    centroids: npt.NDArray[np.float32]  # Cluster centroids


def generate_clusterable_embeddings(
    profile: EmbeddingProfile,
    seed: int = 42,
) -> GeneratedEmbeddings:
    """Generate embeddings with realistic cluster structure."""
    ...
```

### 3. Temporal Pattern Generators

Generate data with realistic temporal patterns:

```python
def generate_temporal_distribution(
    count: int,
    pattern: Literal["uniform", "bursts", "decay", "growth"],
    start: datetime,
    end: datetime,
) -> list[datetime]:
    """Generate timestamps matching the specified pattern."""
    ...
```

### 4. Fixtures from Production Snapshots

When appropriate, use anonymized snapshots of production data:

- Export data profiles (not actual content) from production
- Generate synthetic data matching those profiles
- Never commit actual production data

## Validation Scenarios

### Clustering Validation

1. **Min Cluster Size Boundary**
   - Generate data with exactly `min_cluster_size` points in a cluster
   - Verify cluster forms (not all noise)
   - Test with `min_cluster_size - 1` points, verify no cluster

2. **Diffuse Theme Cloud**
   - Generate 50-100 points with moderate spread (simulating single-theme data)
   - Verify at least some clustering (not 100% noise)
   - Parameters should handle diffuse clouds, not just well-separated clusters

3. **Mixed Density Regions**
   - Generate data with varying local density
   - Verify clusters found in dense regions
   - Verify sparse outliers correctly identified as noise

### Search and Pagination

4. **Large Result Set Pagination**
   - Generate 200+ searchable items
   - Request pages of 20 items
   - Verify all items accessible via pagination
   - Verify no duplicates across pages

5. **Score Distribution Handling**
   - Generate results with long-tail score distribution
   - Verify ranking is stable and meaningful
   - Verify low-score results can be excluded by threshold

### Memory Operations

6. **Category Skew Handling**
   - Generate memories with 80% in one category
   - Verify category filters work correctly
   - Verify search does not over-weight the dominant category

7. **Large Memory Corpus**
   - Generate 500 memories with varied content lengths
   - Verify search returns in acceptable time (<1s)
   - Verify relevance scoring handles content length variation

### Temporal Data

8. **Burst Pattern Handling**
   - Generate commits with burst patterns (many commits in short period)
   - Verify search handles temporal clustering
   - Verify date range filters work at burst boundaries

9. **Long Time Range Queries**
   - Generate data spanning months
   - Verify "since" filters work correctly
   - Verify no off-by-one errors at boundaries

### Algorithm Parameter Validation

10. **HDBSCAN Parameter Robustness**
    - Test with production-like data profiles at various parameter settings
    - Document minimum viable settings for expected data characteristics
    - Add assertions that parameters are appropriate for data profile

## Acceptance Criteria

1. **Data Profile Documentation**
   - [ ] `tests/fixtures/data_profiles.py` defines production-like data profiles
   - [ ] Each profile documents expected ranges and distributions
   - [ ] Profiles cover all major data types (GHAP, memories, code, commits)

2. **Data Generators**
   - [ ] Generators exist for each data type with profile configuration
   - [ ] Generators produce reproducible output (seeded randomness)
   - [ ] Generators can create edge-case scenarios (boundary conditions)

3. **Validation Test Suite**
   - [ ] NEW validation tests added in `tests/validation/` directory (do not modify existing unit tests)
   - [ ] Validation tests use production-like profiles, not minimal data
   - [ ] Tests verify algorithm behavior at expected data scales
   - [ ] Tests document why specific profiles were chosen

4. **Clustering Tests**
   - [ ] Test with 63+ similar embeddings (BUG-031 scenario) passes
   - [ ] Test with diffuse single-theme cloud produces >0 clusters
   - [ ] Parameters documented as appropriate for 20-200 point datasets

5. **Pagination Tests**
   - [ ] Test pagination with 200+ items
   - [ ] Verify no duplicates or missing items across pages
   - [ ] Test boundary conditions (first page, last page, exact fit)

6. **Performance Baselines**
   - [ ] Benchmark tests establish acceptable performance with production-like data
   - [ ] Tests fail if operations exceed these time bounds:
     - Data generation: <5s for any profile
     - Clustering operations: <10s for datasets up to 200 points
     - Search operations: <1s for result sets up to 100 items
     - Memory operations: <2s for corpus up to 500 memories
   - [ ] Results logged to `tests/performance/benchmark_results.json`

7. **Documentation**
   - [ ] README or docstring explains data profile design rationale
   - [ ] Tests include comments linking to bug reports they prevent
   - [ ] Profile parameters reference real-world observations where available

## Out of Scope

- Automated extraction of production data profiles (manual analysis for now)
- Load testing or stress testing (focus is on correctness, not scale)
- Synthetic data that requires external ML models to generate
- Changes to production algorithm parameters (only testing validation)

## Implementation Notes

### Initialization Requirements

- Profile dataclasses and generators can be imported directly from `tests.fixtures.data_profiles` and `tests.fixtures.generators`
- Validation test fixtures are defined in `tests/validation/conftest.py`
- `tests/performance/benchmark_results.json` will be created automatically on first benchmark run if it doesn't exist
- No special initialization required for generators; they are stateless functions with deterministic output given a seed

### Test Organization

- Tests should be deterministic (use fixed random seeds)
- Tests should be reasonably fast (<10s each, <60s total for suite)
- Mark validation tests with `@pytest.mark.validation` for selective execution
- Use pytest parametrization to test multiple profiles efficiently

### File Structure

Generators are organized in a subpackage for modularity:

```
tests/fixtures/
  data_profiles.py          # Profile dataclasses and preset profiles
  generators/
    __init__.py             # Package exports
    embeddings.py           # Clusterable embedding generators
    ghap.py                 # GHAP entry generators
    temporal.py             # Temporal pattern generators
    memories.py             # Memory corpus generators
    commits.py              # Git commit generators (for temporal tests)
```

### Incremental Implementation

This spec covers significant breadth. If implementing incrementally:
1. **Priority 1**: Data profiles and GHAP/clustering generators (addresses BUG-031 directly)
2. **Priority 2**: Clustering validation scenarios (1-3)
3. **Priority 3**: Search/pagination scenarios (4-5)
4. **Priority 4**: Memory and temporal scenarios (6-9)
5. **Priority 5**: Documentation and benchmarks

## References

- BUG-031: Clustering parameters too conservative for real data
- RESEARCH-bug-pattern-analysis.md: Theme T9 (Algorithm Parameter Tuning)
- Recommendation R13: Parameter Validation with Production Data
- Recommendation R6: Test-Production Parity Verification
