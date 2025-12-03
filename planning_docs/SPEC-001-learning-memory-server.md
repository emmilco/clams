# SPEC-001: Learning Memory Server

## Overview

A local MCP server that provides Claude Code agents with persistent memory, semantic code navigation, and reinforcement learning from experience.

### Problem Statement

Claude Code agents face three interconnected problems:

1. **The Memory Problem**: Agents start each session with no memory. Current solutions rely on static documentation that drifts from reality without failing visibly.

2. **The Navigation Problem**: Finding code by path references is brittle. Paths change, files move, and cached references go stale. Navigation cost makes agents avoid exploring.

3. **The Learning Problem**: Agents repeat mistakes across sessions. There's no mechanism to capture what went wrong, cluster similar failures, or surface patterns that could prevent future errors.

### Solution

A modular MCP server providing:

1. **Persistent Memory** - Facts with lifecycle management
2. **Semantic Code Search** - Find code by meaning, not paths (can't go stale)
3. **Git History Intelligence** - Blame, churn, file history, commit search
4. **Experience Learning** - GHAP tracking → embedding → clustering → emergent values
5. **Grounded Context** - Pre-mortems from past failures, JIT injection after errors

---

## Core Concepts

### GHAP Framework

Agents track working state through Goal-Hypothesis-Action-Prediction entries:

| Component | Prompt | Good Example | Bad Example |
|-----------|--------|--------------|-------------|
| **Goal** | What meaningful change are you trying to make? (Not the immediate action) | Fix the auth timeout bug | Run the tests |
| **Hypothesis** | What do you believe about the situation that informs your approach? | Slow network responses exceed the 30s timeout | The tests will tell me what's wrong |
| **Action** | What are you doing based on this belief? | Increasing timeout to 60s | Running pytest |
| **Prediction** | If your hypothesis is correct, what specific outcome will you observe? | Auth failures stop | Tests fail |

The key insight: **Prediction must follow logically from Hypothesis.** This forces articulation of a falsifiable belief, not just an observation.

**Outcome states:**
- **Confirmed**: Prediction matched reality
- **Falsified**: Prediction did not match reality
- **Abandoned**: Goal was dropped before resolution

On falsification, capture:
- **Surprise**: What was unexpected?
- **Root Cause**: Category + why the hypothesis was wrong
- **What Worked**: The actual fix

### Enrichment Dimensions

Each experience captures:

| Dimension | Values |
|-----------|--------|
| Domain | debugging, refactoring, feature, testing, configuration, documentation, performance, security, integration |
| Strategy | systematic-elimination, trial-and-error, research-first, divide-and-conquer, root-cause-analysis, copy-from-similar, check-assumptions, read-the-error, ask-user |
| Root Cause Category | wrong-assumption, missing-knowledge, oversight, environment-issue, misleading-symptom, incomplete-fix, wrong-scope, test-isolation, timing-issue |

### Confidence Tiers

| Tier | Criteria | Clustering Weight |
|------|----------|-------------------|
| Gold | Clear goal + hypothesis, auto-captured outcome, immediate annotation | 1.0 |
| Silver | Clear goal + hypothesis, outcome confirmed, wrapup annotation | 0.8 |
| Bronze | Vague hypothesis or ambiguous resolution | 0.5 |
| Abandoned | Goal abandoned, partial information | 0.2 |

### Multi-Axis Clustering

Experiences are embedded on multiple axes:
- **Full**: Complete narrative (goal, hypothesis, action, prediction, outcome)
- **Domain**: What happened in this type of work
- **Strategy**: How this approach performed
- **Surprise**: What was unexpected (falsified only)
- **Root Cause**: Why the hypothesis was wrong (falsified only)

Each axis clusters independently. Values emerge per axis as cluster centroid summaries.

### Value Formation

Values are emergent, not hand-written. Formation is **agent-driven**:

1. User triggers `/retro` slash command
2. Server clusters experiences on each axis (HDBSCAN)
3. Agent reads cluster members via MCP tools
4. Agent generates candidate value statements
5. Server validates: candidate must be closer to centroid than median member
6. If valid, server stores value with embedding and metadata

The value embedding ensures correct retrieval even if text is imperfect. The median-distance validation ensures values are semantically grounded in the cluster.

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE CODE SESSION                                │
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  UserPromptSubmit│  │   PreToolCall    │  │   PostToolCall   │          │
│  │      Hook        │  │      Hook        │  │      Hook        │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           └─────────────────────┼─────────────────────┘                     │
│                                 ▼                                           │
│                    LOCAL STATE (.claude/journal/)                           │
└─────────────────────────────────┼───────────────────────────────────────────┘
                                  │ MCP Protocol
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LEARNING MEMORY SERVER                               │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         MCP TOOL INTERFACE                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐                   │
│  │  Context  │ │   Value   │ │ Clusterer │ │  Searcher │                   │
│  │ Assembler │ │   Store   │ │           │ │           │                   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                   │
│        └─────────────┴─────────────┴─────────────┘                         │
│                                  │                                          │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐                   │
│  │   Code    │ │    Git    │ │Observation│ │  Memory   │                   │
│  │  Indexer  │ │ Analyzer  │ │ Persister │ │   CRUD    │                   │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘                   │
│        └─────────────┴─────────────┴─────────────┘                         │
│                                  │                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          VECTOR STORE                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                  │                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        EMBEDDING SERVICE                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Module Overview

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| Embedding Service | Text → vector | None (infrastructure) |
| Vector Store | Storage abstraction | None (infrastructure) |
| Code Indexer | Parse source → embed → store | Embedding, VectorStore |
| Git Analyzer | Commits, blame, churn | Embedding, VectorStore |
| Observation Collector | GHAP state machine (local) | None (file system only) |
| Observation Persister | Resolved entries → storage | Embedding, VectorStore |
| Searcher | Query interface | Embedding, VectorStore |
| Clusterer | HDBSCAN clustering | VectorStore |
| Value Store | Validate and store agent-generated values | Clusterer, Embedding |
| Context Assembler | Format context for injection | Searcher |

---

## Technology Decisions

### Summary

| Category | Decision |
|----------|----------|
| Language | Python 3.13 |
| Vector Database | Qdrant (Docker for tests, local mode for dev) |
| Embedding Model | nomic-embed-text (local) |
| MCP Framework | mcp Python SDK (official) |
| Code Parsing | tree-sitter-languages (bundled grammars) |
| Git Integration | GitPython |
| Clustering | scikit-learn HDBSCAN |
| Metadata Storage | SQLite |
| Package Management | uv + pyproject.toml |
| Linting/Formatting | Ruff |
| Type Checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |
| Logging | structlog |
| Configuration | pydantic-settings |

### Key Architectural Decisions

**No server-side LLM for value formation.** Value formation is triggered by the user via a slash command (e.g., `/retro`). The Claude Code agent reads cluster data via MCP tools, generates value candidates itself, and stores them back. This eliminates API key management, reduces costs, and keeps the server simpler.

**Value validation via centroid distance.** When the agent proposes a value, it must be closer to the cluster centroid than the median member distance. This ensures values are semantically grounded in the cluster.

```python
def validate_value(candidate_embedding, centroid, member_embeddings):
    candidate_dist = cosine_distance(candidate_embedding, centroid)
    member_dists = [cosine_distance(m, centroid) for m in member_embeddings]
    median_dist = median(member_dists)
    return candidate_dist <= median_dist
```

**Three storage layers, each fit for purpose:**
- **Qdrant**: Vector storage and semantic search
- **SQLite**: Relational metadata (file index, call graph, project config)
- **JSON files**: Local ephemeral GHAP state (`.claude/journal/`)

**Full async throughout.** The entire codebase is async-native. No sync/async bridging, no `asyncio.to_thread()`. This is a deliberate choice—see the Async Guidelines section below.

### Async Guidelines

**THIS CODEBASE IS FULLY ASYNC.** Every function that does I/O (database, network, file system, embedding) is `async def` and must be `await`ed.

**Common mistakes to avoid:**

```python
# WRONG - forgot await
result = searcher.search_code(query)  # Returns coroutine, not result!

# RIGHT
result = await searcher.search_code(query)
```

```python
# WRONG - sync function calling async
def process_files(paths: list[str]) -> list[Result]:
    results = []
    for path in paths:
        results.append(await index_file(path))  # SyntaxError!
    return results

# RIGHT - async all the way down
async def process_files(paths: list[str]) -> list[Result]:
    results = []
    for path in paths:
        results.append(await index_file(path))
    return results
```

```python
# WRONG - blocking call in async context
async def get_embedding(text: str) -> Vector:
    return model.encode(text)  # Blocks the event loop!

# RIGHT - use async-native libraries or run_in_executor for CPU-bound work
async def get_embedding(text: str) -> Vector:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, model.encode, text)
```

**Rules:**

1. **Every I/O function is async.** No exceptions.
2. **Always await async calls.** If you see a function that returns a coroutine, await it.
3. **Use `async for` and `async with`** for async iterators and context managers.
4. **CPU-bound work** (like embedding) uses `run_in_executor` to avoid blocking.
5. **Tests use `pytest-asyncio`** and are marked with `@pytest.mark.asyncio`.

**Why this choice:** Bridging sync and async creates its own bugs. A consistent async codebase is easier to reason about than a mixed one, despite the overhead of more `await` keywords.

**Docker for Qdrant in tests.** For test isolation with parallel agents, Qdrant runs in Docker. For simple local development, the local mode (in-process) is available as fallback.

### Project Structure

```
learning-memory-server/
├── src/
│   └── learning_memory_server/
│       ├── __init__.py
│       ├── server/                # MCP server
│       │   ├── __init__.py
│       │   ├── main.py            # Entry point
│       │   ├── tools/             # Tool definitions
│       │   │   ├── __init__.py
│       │   │   ├── memory.py
│       │   │   ├── code.py
│       │   │   ├── git.py
│       │   │   ├── ghap.py
│       │   │   └── learning.py
│       │   └── middleware.py
│       ├── embedding/             # EmbeddingService
│       ├── storage/               # VectorStore, SQLite
│       ├── indexers/              # CodeIndexer, GitAnalyzer
│       ├── observation/           # Collector, Persister
│       ├── search/                # Searcher
│       ├── clustering/            # Clusterer
│       ├── values/                # ValueStore
│       └── context/               # ContextAssembler
├── tests/
├── pyproject.toml
└── README.md
```

### Initial Language Support

Code indexing will initially support:
- Python
- TypeScript / JavaScript
- Lua
- YAML
- JSON

Note: YAML and JSON are data formats. "Semantic units" for these will be top-level keys or schema structures, not functions/classes.

---

## Module Specifications

### Embedding Service

**Purpose**: Convert text to vectors.

**Interface**:
```python
class EmbeddingService(ABC):
    def embed(self, text: str) -> Vector
    def embed_batch(self, texts: List[str]) -> List[Vector]
    @property
    def dimension(self) -> int
```

**Implementations**:
- `NomicEmbedding`: Local model (nomic-embed-text, 768 dimensions)
- `MockEmbedding`: Deterministic vectors for testing

**Configuration**:
- `EMBEDDING_MODEL`: Model name (default: nomic-embed-text)
- `EMBEDDING_DIMENSION`: Vector dimension (default: 768)

---

### Vector Store

**Purpose**: Abstract vector storage operations.

**Interface**:
```python
class VectorStore(ABC):
    def create_collection(self, name: str, dimension: int) -> None
    def upsert(self, collection: str, id: str, vector: Vector, payload: Dict) -> None
    def search(self, collection: str, query: Vector, limit: int,
               filters: Optional[Dict] = None) -> List[SearchResult]
    def delete(self, collection: str, id: str) -> None
    def scroll(self, collection: str, limit: int, filters: Optional[Dict] = None,
               with_vectors: bool = False) -> List[SearchResult]
    def count(self, collection: str, filters: Optional[Dict] = None) -> int
```

**Implementations**:
- `QdrantVectorStore`: Production storage
- `InMemoryVectorStore`: Testing and development

**Collections**:
- `memories`: General memory storage
- `code_units`: Indexed code (functions, classes, methods)
- `commits`: Git commit history
- `experiences_full`: Complete GHAP embeddings
- `experiences_domain`: Domain-axis embeddings
- `experiences_strategy`: Strategy-axis embeddings
- `experiences_surprise`: Surprise-axis embeddings
- `experiences_root_cause`: Root-cause-axis embeddings
- `values`: Emergent values from clustering

---

### Code Indexer

**Purpose**: Parse source code into semantic units and index for search.

**Components**:

```python
class CodeParser(ABC):
    def parse_file(self, path: str) -> List[SemanticUnit]
    def supported_languages(self) -> List[str]

class CodeIndexer:
    def __init__(self, parser: CodeParser, embedding_service: EmbeddingService,
                 vector_store: VectorStore)
    def index_file(self, path: str, project: str) -> int
    def index_directory(self, path: str, project: str, recursive: bool = True) -> int
    def remove_file(self, path: str, project: str) -> None
    def get_indexing_stats(self, project: str) -> IndexingStats
```

**SemanticUnit Structure**:
```python
@dataclass
class SemanticUnit:
    name: str
    qualified_name: str
    unit_type: UnitType  # function, class, method
    signature: str
    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    docstring: Optional[str]
    complexity: Optional[int]  # cyclomatic complexity
```

**Supported Languages** (via tree-sitter-languages):
- Python
- TypeScript / JavaScript
- Lua
- YAML (top-level keys as semantic units)
- JSON (top-level keys as semantic units)

---

### Git Analyzer

**Purpose**: Analyze git history for blame, churn, and semantic commit search.

**Components**:

```python
class GitReader(ABC):
    def get_commits(self, since: Optional[datetime], until: Optional[datetime],
                    path: Optional[str]) -> List[Commit]
    def get_blame(self, file_path: str) -> List[BlameEntry]
    def get_file_history(self, file_path: str, limit: int) -> List[Commit]

class GitAnalyzer:
    def __init__(self, git_reader: GitReader, embedding_service: EmbeddingService,
                 vector_store: VectorStore)
    def index_commits(self, since: Optional[datetime] = None) -> int
    def search_commits(self, query: str, limit: int = 10) -> List[Commit]
    def get_churn_hotspots(self, days: int = 90, limit: int = 10) -> List[ChurnRecord]
    def get_file_authors(self, file_path: str) -> List[AuthorStats]
```

**Commit Structure**:
```python
@dataclass
class Commit:
    sha: str
    message: str
    author: str
    author_email: str
    timestamp: datetime
    files_changed: List[str]
    insertions: int
    deletions: int
```

---

### Observation Collector

**Purpose**: Track GHAP state locally during agent session.

**Interface**:
```python
class ObservationCollector:
    def __init__(self, journal_dir: Path)

    # GHAP lifecycle
    def create_ghap(self, domain: Domain, strategy: Strategy, goal: str,
                    hypothesis: str, action: str, prediction: str) -> GHAPEntry
    def update_ghap(self, hypothesis: str = None, action: str = None,
                    prediction: str = None, strategy: Strategy = None,
                    note: str = None) -> None
    def resolve_ghap(self, status: OutcomeStatus, result: str,
                     surprise: str = None, root_cause: Dict = None,
                     lesson: Dict = None) -> GHAPEntry

    # State access
    def get_current(self) -> Optional[GHAPEntry]
    def get_session_entries(self) -> List[GHAPEntry]
    def has_orphaned_entry(self) -> bool

    # Persistence
    def load_state(self) -> None
    def save_state(self) -> None
```

**Local File Structure**:
```
.claude/journal/
├── current_ghap.json      # Active GHAP state
├── session_entries.jsonl  # Resolved entries this session
├── .tool_count            # Check-in frequency counter
└── archive/               # Past session entries
    └── 2025-12-01_session1.jsonl
```

**Key Design Decision**: Collection has NO dependency on the server. It operates entirely on local files. This allows testing the GHAP state machine independently.

---

### Observation Persister

**Purpose**: Embed and store resolved GHAP entries.

**Interface**:
```python
class ObservationPersister:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore)

    def persist_entry(self, entry: GHAPEntry) -> None
    def persist_batch(self, entries: List[GHAPEntry]) -> None
```

**Multi-Axis Embedding**:

For each resolved entry, create embeddings for:

1. **Full axis**: Complete narrative
   ```
   Domain: {domain} | Strategy: {strategy}
   Goal: {goal}
   Hypothesis: {hypothesis}
   Action: {action} | Prediction: {prediction}
   Outcome: {outcome_status} - {outcome_result}
   [Surprise: {surprise}] [Root cause: {root_cause}] [Lesson: {lesson}]
   ```

2. **Domain axis**: Domain-specific context
   ```
   {domain}: {goal}
   Hypothesis: {hypothesis}
   Result: {outcome_status}
   [Learned: {lesson}]
   ```

3. **Strategy axis**: Strategy performance
   ```
   Strategy: {strategy}
   Applied to: {goal}
   Hypothesis: {hypothesis}
   Iterations: {iteration_count}
   Outcome: {outcome_status}
   ```

4. **Surprise axis** (falsified only): What was unexpected
   ```
   {surprise}
   ```

5. **Root cause axis** (falsified only): Why the hypothesis was wrong
   ```
   {root_cause_category}: {root_cause_description}
   Context: {goal}
   Hypothesis was: {hypothesis}
   ```

---

### Searcher

**Purpose**: Unified query interface across all collections.

**Interface**:
```python
class Searcher:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore)

    def search_memories(self, query: str, category: str = None,
                        limit: int = 10) -> List[MemoryResult]

    def search_code(self, query: str, project: str = None,
                    language: str = None, unit_type: str = None,
                    limit: int = 10) -> List[CodeResult]

    def search_experiences(self, query: str, axis: str = "full",
                           domain: str = None, outcome: str = None,
                           limit: int = 10) -> List[ExperienceResult]

    def search_values(self, query: str, axis: str = None,
                      limit: int = 5) -> List[ValueResult]

    def search_commits(self, query: str, author: str = None,
                       since: datetime = None, limit: int = 10) -> List[CommitResult]
```

---

### Clusterer

**Purpose**: Cluster embeddings and compute centroids.

**Interface**:
```python
class Clusterer:
    def __init__(self, min_cluster_size: int = 5, min_samples: int = 3)

    def cluster(self, embeddings: np.ndarray,
                weights: np.ndarray = None) -> ClusterResult

    def compute_centroids(self, embeddings: np.ndarray, labels: np.ndarray,
                          ids: List[str], weights: np.ndarray = None) -> List[ClusterInfo]

class ExperienceClusterer:
    def __init__(self, vector_store: VectorStore, clusterer: Clusterer)

    def cluster_axis(self, axis: str) -> List[ClusterInfo]
    def cluster_all_axes(self) -> Dict[str, List[ClusterInfo]]
```

**ClusterInfo Structure**:
```python
@dataclass
class ClusterInfo:
    label: int
    centroid: np.ndarray
    member_ids: List[str]
    size: int
    avg_weight: float
```

**Clustering Parameters**:
- `min_cluster_size`: 5 (minimum experiences to form cluster)
- `min_samples`: 3 (HDBSCAN density parameter)
- `metric`: cosine
- `cluster_selection_method`: eom

---

### Value Store

**Purpose**: Validate and store agent-generated values.

Value formation is **agent-driven**, not server-driven. The server provides clustering and validation; the agent (Claude Code) generates value text via a slash command like `/retro`.

**Interface**:
```python
class ValueStore:
    def __init__(self, embedding_service: EmbeddingService,
                 vector_store: VectorStore, clusterer: Clusterer)

    def get_clusters(self, axis: str) -> List[ClusterInfo]
    def get_cluster_members(self, cluster_id: str) -> List[Experience]
    def validate_value_candidate(self, text: str, cluster_id: str) -> ValidationResult
    def store_value(self, text: str, cluster_id: str, axis: str) -> Value
    def list_values(self, axis: str = None) -> List[Value]
```

**Validation Logic**:

A value candidate must be closer to the cluster centroid than the median member distance:

```python
def validate_value_candidate(self, text: str, cluster_id: str) -> ValidationResult:
    candidate_embedding = self.embedding_service.embed(text)
    cluster = self.get_cluster(cluster_id)

    candidate_dist = cosine_distance(candidate_embedding, cluster.centroid)
    member_dists = [cosine_distance(m.embedding, cluster.centroid)
                   for m in cluster.members]
    median_dist = median(member_dists)

    if candidate_dist <= median_dist:
        return ValidationResult(valid=True, similarity=1 - candidate_dist)
    else:
        return ValidationResult(
            valid=False,
            reason=f"Value too far from centroid (dist={candidate_dist:.3f}, median={median_dist:.3f})"
        )
```

**Agent-Driven Value Formation Flow**:

1. User triggers `/retro` slash command
2. Agent calls `get_clusters(axis)` to see available clusters
3. For each cluster, agent calls `get_cluster_members(cluster_id)`
4. Agent reads experiences, generates candidate value text
5. Agent calls `validate_value_candidate(text, cluster_id)`
6. If valid, agent calls `store_value(text, cluster_id, axis)`
7. If invalid, agent revises and retries

**Axis-Specific Prompts** (used by agent, not server):

- **Domain**: "What principle emerges about working effectively in this domain?"
- **Strategy**: "What principle emerges about when this strategy works well?"
- **Surprise**: "What blindspot or misconception do these surprises reveal?"
- **Root Cause**: "What pattern of error does this reveal? What should be checked?"

---

### Context Assembler

**Purpose**: Assemble and format context for injection into agent conversation.

**Interface**:
```python
class ContextAssembler:
    def __init__(self, searcher: Searcher)

    def get_light_context(self, project: str = None) -> LightContext
    def get_rich_context(self, situation: str,
                         include_code: bool = True) -> RichContext
    def get_premortem(self, domain: str, strategy: str) -> Premortem
    def format_for_injection(self, context: RichContext,
                             max_tokens: int = 2000) -> str
```

**Context Types**:

1. **Light Context** (session start):
   - Top values (high cluster size)
   - Recent events
   - Key memories

2. **Rich Context** (after failure or on request):
   - Similar experiences with lessons
   - Domain-specific values
   - Strategy-specific values
   - Surprise patterns
   - Root cause patterns
   - Relevant code

3. **Premortem** (before risky action):
   - Past failures in this domain/strategy combination
   - Common surprises
   - Frequent root causes

---

## MCP Tool Interface

### Memory Tools

```typescript
// Store a memory
store_memory(content: string, category: string,
             importance?: number, tags?: string[]): { id: string }

// Retrieve memories by semantic search
retrieve_memories(query: string, limit?: number,
                  category?: string): Memory[]

// List memories with filters
list_memories(category?: string, tags?: string[],
              limit?: number, offset?: number): Memory[]

// Delete a memory
delete_memory(id: string): void
```

### Code Tools

```typescript
// Index a codebase
index_codebase(directory: string, project: string,
               recursive?: boolean): { indexed: number }

// Search code semantically
search_code(query: string, project?: string, language?: string,
            limit?: number): CodeResult[]

// Find similar code
find_similar_code(snippet: string, project?: string,
                  limit?: number): CodeResult[]

// Find callers of a function
find_callers(function_name: string, project?: string): CallResult[]

// Find functions called by a function
find_callees(function_name: string, project?: string): CallResult[]
```

### Git Tools

```typescript
// Search commits semantically
search_commits(query: string, author?: string, since?: string,
               limit?: number): Commit[]

// Get file history
get_file_history(path: string, limit?: number): Commit[]

// Get churn hotspots
get_churn_hotspots(days?: number, limit?: number): ChurnRecord[]

// Get file authors
get_code_authors(path: string): AuthorStats[]
```

### GHAP Tools

```typescript
// Create a new GHAP entry
create_ghap(domain: string, strategy: string, goal: string,
            hypothesis: string, action: string,
            prediction: string): { id: string }

// Update current GHAP
update_ghap(hypothesis?: string, action?: string, prediction?: string,
            strategy?: string, note?: string): void

// Resolve current GHAP
resolve_ghap(outcome: "confirmed" | "falsified" | "abandoned",
             result: string, surprise?: string,
             root_cause?: { category: string, description: string },
             lesson?: { what_worked: string }): void

// Get current GHAP state
get_current_ghap(): GHAPEntry | null
```

### Learning Tools

```typescript
// Get relevant context for a situation
get_context(situation: string, depth?: "light" | "rich"): Context

// Get premortem warnings
get_premortem(domain: string, strategy: string): Premortem

// Run clustering on an axis
run_clustering(axis: string): { clusters: ClusterInfo[], count: number }

// Get clusters for an axis
get_clusters(axis: string): ClusterInfo[]

// Get experiences in a cluster
get_cluster_members(cluster_id: string): Experience[]

// Validate a value candidate (checks centroid distance)
validate_value_candidate(text: string, cluster_id: string): ValidationResult

// Store a validated value
store_value(text: string, cluster_id: string, axis: string): Value

// List emergent values
list_values(axis?: string): Value[]
```

---

## Hook Configuration

### Claude Code Hooks

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "command": ".claude/hooks/session_start.sh",
        "timeout": 5000,
        "once": true
      }
    ],
    "PreToolCall": [
      {
        "matcher": "*",
        "command": ".claude/hooks/ghap_checkin.sh",
        "timeout": 15000
      }
    ],
    "PostToolCall": [
      {
        "matcher": "Bash(pytest|npm test|cargo test|make test|make build)",
        "command": ".claude/hooks/outcome_capture.sh",
        "timeout": 5000
      }
    ]
  }
}
```

### Hook Behaviors

**session_start.sh**:
- Check for orphaned GHAP from previous session
- Inject light context
- Inject premortem if continuing known work

**ghap_checkin.sh**:
- Frequency-based (every N tool uses, default N=10)
- Show current GHAP state
- Prompt for update or continuation

**outcome_capture.sh**:
- Capture test/build results
- Match prediction against observed outcome
- Prompt for resolution (confirmed/falsified/partial)

---

## Data Flow

### Experience Collection Flow

```
User Request
    │
    ▼
Session Start Hook
    │ Check orphans, inject light context
    ▼
Agent Creates GHAP
    │ Domain, strategy, goal, hypothesis, action, prediction
    ▼
Work Loop ◄──────────────────────┐
    │                            │
    ├─► Check-in (every N tools) │
    │   └─► Update or continue ──┘
    │
    ▼
Outcome Event (test/build)
    │
    ├─► Confirmed ──► Gold tier ──► Embed & Store
    │
    └─► Falsified ──► Annotate (surprise, root cause, lesson)
                          │
                          ▼
                      Gold/Silver tier ──► Embed & Store
```

### Value Formation Flow (Agent-Driven)

```
User triggers /retro command
    │
    ▼
Agent calls run_clustering(axis)
    │
    ▼
Agent calls get_clusters(axis)
    │
    ▼
For each cluster:
    │
    ├─► Agent calls get_cluster_members(cluster_id)
    │
    ├─► Agent reads experiences, understands the pattern
    │
    ├─► Agent generates candidate value text
    │
    ├─► Agent calls validate_value_candidate(text, cluster_id)
    │       │
    │       ├─► If valid: Agent calls store_value(...)
    │       │
    │       └─► If invalid: Agent revises and retries
    │
    └─► Continue to next cluster
```

**Key difference**: The server does clustering and validation. The agent does value generation. No LLM API calls from the server.

### Context Retrieval Flow

```
Context Request (situation + depth)
    │
    ▼
Embed situation
    │
    ├─► Query experiences_full
    ├─► Query experiences_domain
    ├─► Query experiences_strategy
    ├─► Query values collection
    └─► Query code_units (if include_code)
    │
    ▼
Merge & deduplicate
    │
    ▼
Format for injection
    │
    ▼
Return context string
```

---

## Development Phases

### Phase 1: Foundation

**Deliverables**:
- EmbeddingService interface + NomicEmbedding implementation
- VectorStore interface + QdrantVectorStore implementation
- MockEmbedding and InMemoryVectorStore for testing
- Basic MCP server skeleton with mcp Python SDK
- SQLite metadata store
- Project scaffolding (pyproject.toml, ruff, mypy config)
- Unit tests for all

**Exit Criteria**:
- Can embed text and store/retrieve vectors
- In-memory implementation passes all tests
- Qdrant (Docker) integration tests pass
- `uv pip install -e .` works

### Phase 2: Indexers

**Deliverables** (can parallelize):
- CodeParser (tree-sitter-languages) + CodeIndexer
- GitReader (GitPython) + GitAnalyzer
- ObservationCollector (local JSON files)

**Exit Criteria**:
- Can index Python, TypeScript, Lua, YAML, JSON files
- Can search git commits and get churn hotspots
- GHAP state machine works with local files only

### Phase 3: Query Layer

**Deliverables**:
- Searcher (unified query interface)
- MCP tools for memory, code, git, GHAP

**Exit Criteria**:
- Can search across all collections via MCP
- Integration tests with Claude Code

### Phase 4: Intelligence

**Deliverables**:
- Clusterer (scikit-learn HDBSCAN)
- ValueStore (validation + storage, no LLM)
- ObservationPersister (multi-axis embedding)

**Exit Criteria**:
- Can cluster experiences on each axis
- Value validation correctly enforces centroid distance
- Multi-axis storage working
- `/retro` slash command documented

### Phase 5: Integration

**Deliverables**:
- Full MCP tool suite wired up
- Integration with Claude Code
- Performance tuning
- Documentation

**Exit Criteria**:
- System works in real development sessions
- All core tools functional (memory, code search, git, GHAP, clustering, values)
- Latency acceptable (<200ms for search, <500ms for clustering)
- Documentation complete

**Note**: Launch without ContextAssembler. Users interact with tools directly.

### Phase 6: Context Assembly

**Deliverables**:
- ContextAssembler
- Hook scripts
- Light/rich context injection
- Premortem warnings

**Exit Criteria**:
- Light and rich context injection working
- Premortem warnings generated
- End-to-end flow from collection to automatic retrieval
- Hooks integrate cleanly with Claude Code

**Note**: This phase adds the "magic"—automatic context injection based on situation. Only after core system is stable.

---

## Configuration

### Environment Variables

```bash
# Storage
QDRANT_URL=http://localhost:6333
STORAGE_PATH=~/.learning-memory
SQLITE_PATH=~/.learning-memory/metadata.db

# Embedding
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768

# Clustering
HDBSCAN_MIN_CLUSTER_SIZE=5
HDBSCAN_MIN_SAMPLES=3

# Collection
GHAP_CHECK_FREQUENCY=10
JOURNAL_PATH=.claude/journal
```

Note: No LLM configuration needed—value formation is handled by the Claude Code agent.

### Collection Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| Min experiences for clustering | 20 | Don't cluster until sufficient data |
| Min cluster size | 5 | Minimum experiences per cluster |
| Value validation threshold | median | Value must be closer to centroid than median member |
| Cold storage threshold | Bronze | Move Bronze/Abandoned to cold storage |

---

## Success Criteria

### Functional

1. **Memory**: Can store, retrieve, and lifecycle-manage memories
2. **Code Search**: Semantic search returns relevant code
3. **Git Analysis**: Can search commits, find churn, get blame
4. **GHAP Tracking**: State machine correctly handles all transitions
5. **Clustering**: Produces meaningful clusters from experiences
6. **Value Formation**: Generated values are topically relevant
7. **Context Retrieval**: Returns relevant context for situations

### Performance

1. Context retrieval: <500ms p95
2. Code search: <200ms p95
3. Embedding: <100ms per text
4. Clustering (1000 experiences): <5s

### Quality

1. Values are in the "right ballpark" semantically (manual review)
2. Retrieval surfaces relevant experiences (manual review)
3. No regression in development velocity from friction
4. Experiences accumulate without excessive noise

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent writes low-quality GHAP entries | Poor learning signal | Confidence tiers, reduced clustering weight |
| Agent writes tautological hypotheses | No falsifiable belief captured | GHAP prompts explicitly require hypothesis that informs action |
| Clustering produces meaningless groups | Useless values | Conservative min_cluster_size, human review |
| Value text is misleading | Bad guidance | Experiences provide ground truth, values are hints |
| Cold start (no data) | No benefit initially | Focus on code search value first |
| Hook latency | Development friction | Keep hooks fast (<100ms), async where possible |
| Embedding model mismatch | Poor clustering | Use consistent model, test with real data |

---

## Open Questions

1. **Cross-project learning**: Should values transfer between projects? How?
2. **Value decay**: Should old values lose weight? What's the half-life?
3. **Conflict resolution**: What if two values seem to contradict?
4. **User feedback**: How to incorporate explicit user feedback?
5. **Multi-agent**: How does this work with multiple concurrent agents?

---

## Appendix A: Example GHAP Entry

```json
{
  "id": "ghap_20251202_143022_a1b2c3",
  "session_id": "session_20251202_140000",
  "created_at": "2025-12-02T14:30:22Z",
  "domain": "debugging",
  "strategy": "systematic-elimination",
  "goal": "Fix flaky test in test_cache.py",
  "history": [
    {
      "timestamp": "2025-12-02T14:30:22Z",
      "hypothesis": "The flakiness is caused by timing—the cache expiry check runs before the cache actually expires",
      "action": "Adding explicit sleep to allow cache expiry",
      "prediction": "Test will pass consistently with the added delay"
    }
  ],
  "current": {
    "hypothesis": "The flakiness is caused by test pollution—previous test is leaving cache state that interferes",
    "action": "Adding teardown to previous test to clean state",
    "prediction": "Test will pass consistently once isolation is fixed"
  },
  "iteration_count": 2,
  "outcome": {
    "status": "confirmed",
    "result": "test passed 3/3 runs",
    "captured_at": "2025-12-02T14:45:00Z",
    "auto_captured": true
  },
  "surprise": "The flakiness wasn't timing—it was test isolation. Previous test was leaving cache state.",
  "root_cause": {
    "category": "wrong-assumption",
    "description": "Assumed intermittent = timing issue. Actually test pollution."
  },
  "lesson": {
    "what_worked": "Added proper teardown to previous test",
    "takeaway": "Flaky tests are often isolation issues, not timing."
  },
  "resolution": {
    "status": "resolved",
    "resolved_at": "2025-12-02T14:46:00Z",
    "confidence_tier": "gold",
    "annotation_proximity": "immediate"
  }
}
```

## Appendix B: Example Value

```json
{
  "id": "value_surprise_a3f2e1",
  "axis": "surprise",
  "cluster_id": "cluster_surprise_7",
  "text": "Flaky tests are often test isolation issues, not timing issues. Check test order dependencies before adding sleeps.",
  "cluster_size": 8,
  "member_ids": ["ghap_1", "ghap_2", "ghap_5", "ghap_7", "ghap_12", "ghap_15", "ghap_18", "ghap_21"],
  "avg_confidence": 0.9,
  "similarity_to_centroid": 0.91,
  "created_at": "2025-12-02T15:00:00Z",
  "version": 1
}
```

---

## Changelog

### Version 1.5 (2025-12-03)
- Removed Verifier module (claims with predicates) from scope
- Verifier was tangential to core product concept (code/git indexing, GHAP tracking, clustering)
- Can be reconsidered in future if fact verification becomes important

### Version 1.4 (2025-12-02)
- Swapped Phase 5 and Phase 6: Integration now comes before Context Assembly
- Launch core system first, add context injection after stabilization

### Version 1.3 (2025-12-02)
- Changed from "minimize async" to "full async throughout"
- Added comprehensive Async Guidelines section with examples and rules

### Version 1.2 (2025-12-02)
- Added Technology Decisions section with all implementation choices
- Changed value formation from server-driven to agent-driven (no server LLM)
- Added value validation via centroid distance (must be closer than median member)
- Renamed "Value Former" module to "Value Store"
- Updated embedding model from generic to nomic-embed-text (768 dimensions)
- Updated supported languages: Python, TypeScript/JavaScript, Lua, YAML, JSON
- Added project structure with src layout
- Specified tooling: uv, ruff, mypy (strict), pytest, structlog, pydantic-settings
- Specified Python 3.13
- Updated MCP tools for agent-driven value formation
- Updated data flow diagrams

### Version 1.1 (2025-12-02)
- Renamed PAEO to GHAP (Goal-Hypothesis-Action-Prediction) for better signal elicitation

### Version 1.0 (2025-12-02)
- Initial spec

---

*Spec Version: 1.5*
*Date: 2025-12-03*
