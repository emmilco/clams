# CLAMS: Getting Started

## What Is This?

The CLAMS is an MCP server providing semantic memory, code indexing, git analysis, and a GHAP (Goal-Hypothesis-Action-Prediction) learning loop for AI agents. It embeds observations and clusters them to extract patterns, enabling agents to learn from their experiences over time.

## Quick Start

After installation (see README.md), CLAMS runs automatically as an MCP server in all Claude Code sessions.

## Configuration

CLAMS is configured via environment variables with the `CLAMS_` prefix.

### Storage Paths

```bash
# Change storage location (default: ~/.clams)
export CLAMS_STORAGE_PATH=/custom/path

# SQLite database (default: ~/.clams/metadata.db)
export CLAMS_SQLITE_PATH=/custom/metadata.db

# Journal location (default: .claude/journal - relative to CWD)
export CLAMS_JOURNAL_PATH=/custom/journal
```

### Qdrant Connection

```bash
# Qdrant URL (default: http://localhost:6333)
export CLAMS_QDRANT_URL=http://localhost:6333
```

### Embedding Models

```bash
# Code embedding model (default: sentence-transformers/all-MiniLM-L6-v2)
export CLAMS_CODE_MODEL=sentence-transformers/all-mpnet-base-v2

# Semantic embedding model (default: nomic-ai/nomic-embed-text-v1.5)
export CLAMS_SEMANTIC_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Logging

```bash
# Log level (default: INFO)
export CLAMS_LOG_LEVEL=DEBUG

# Log format (default: json)
export CLAMS_LOG_FORMAT=console  # Human-readable
```

### Setting Environment Variables

To make configuration persistent, add exports to `~/.claude.json` using the `env` field:

```json
{
  "mcpServers": {
    "clams": {
      "type": "stdio",
      "command": "/path/to/clams/.venv/bin/clams",
      "args": [],
      "env": {
        "CLAMS_LOG_LEVEL": "DEBUG",
        "CLAMS_QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

## Exploring the Codebase

### MCP Tools
Location: `src/clams/server/tools/`

| File | Purpose |
|------|---------|
| `memory.py` | Memory storage and retrieval (4 tools) |
| `code.py` | Code indexing and search (3 tools) |
| `git.py` | Git commit analysis (5 tools) |
| `ghap.py` | GHAP learning loop (5 tools) |
| `learning.py` | Clustering and values (5 tools) |
| `search.py` | Cross-collection search (1 tool) |
| `session.py` | Session management (5 tools) |
| `context.py` | Context assembly (1 tool) |
| `__init__.py` | ping health check (1 tool) |

### Configuration
`src/clams/server/config.py` - ServerSettings class with all environment variable options.

### Data Models
`src/clams/observation/models.py` - GHAPEntry, Domain, Strategy, OutcomeStatus, ConfidenceTier.

### Storage
`src/clams/storage/` - VectorStore interface with Qdrant implementation, MetadataStore for SQLite.

### Embedding
`src/clams/embedding/` - EmbeddingService interface with dual implementations:
- `NomicEmbedding` - 768-dim for semantic memory, GHAP, and git analysis
- `MiniLMEmbedding` - 384-dim for fast code indexing

## Key Concepts

### GHAP (Goal-Hypothesis-Action-Prediction)
A structured observation format for AI learning:
1. **Goal**: What meaningful change are you trying to make?
2. **Hypothesis**: What do you believe about the situation?
3. **Action**: What are you doing based on this belief?
4. **Prediction**: If hypothesis is correct, what will you observe?
5. **Resolution**: What actually happened? (confirmed/falsified/abandoned)

### Experience Axes
GHAP entries are projected onto 4 semantic axes and stored in separate Qdrant collections for multi-perspective clustering:
- `full` - Complete narrative embedding
- `strategy` - Problem-solving approach
- `surprise` - Unexpected outcomes
- `root_cause` - Why hypothesis was wrong

### Confidence Tiers
Observations are weighted based on outcome confidence:
- **gold** (1.0): Auto-captured outcome
- **silver** (0.7): Manual resolution
- **bronze** (0.4): Poor quality hypothesis

## Architecture

**Master Spec**: `planning_docs/SPEC-001-learning-memory-server.md`

**Module Layout**:
```
src/clams/
  embedding/     - Embedding service interface and implementations
  storage/       - Vector store and metadata store interfaces
  indexers/      - Code parsing (TreeSitter) and git analysis
  observation/   - GHAP state machine and persistence
  clustering/    - HDBSCAN clustering for experience axes
  values/        - Value extraction from clusters
  context/       - Context assembly for rich agent prompts
  search/        - Hybrid semantic search across collections
  server/        - MCP server and tool implementations
```

## Testing

```bash
pytest -vvsx                       # Unit tests
pytest tests/integration/ -vvsx    # Integration tests (requires Qdrant)
pytest tests/performance/ -vvsx    # Performance benchmarks
pytest tests/cold_start/ -vvsx     # Cold-start tests (empty state handling)
pytest -m cold_start -vvsx         # All cold-start marked tests
```

**Test Categories**:
- **Unit tests**: Core functionality, mocked dependencies
- **Integration tests**: Real Qdrant instance, collection lifecycle
- **Cold-start tests**: First-use scenarios, empty collections
- **Performance tests**: Response latency, token efficiency

**Requirements**: Python 3.12+, Qdrant 1.8.0+ at localhost:6333

**Test Count**: 1700+ tests covering all MCP tools and edge cases
