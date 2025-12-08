# CLAMS - Claude Learning and Memory System

A Model Context Protocol (MCP) server for semantic memory, code indexing, and experience-based learning.

## Features

- **Memory Management**: Store and retrieve semantic memories with categories
- **Code Indexing**: Index and search Python/TypeScript code with TreeSitter
- **Git Analysis**: Analyze commit history, find churn hotspots, identify code authors
- **GHAP Learning**: Goal-Hypothesis-Action-Prediction cycle with experience clustering
- **Context Assembly**: Generate rich context from memories, code, and experiences

## System Requirements

- Python 3.11+
- Qdrant vector database (Docker: `docker run -p 6333:6333 qdrant/qdrant`)
- 4GB RAM minimum (8GB recommended for embedding model)

## Installation

```bash
# Clone repository
git clone <repo-url>
cd clams

# Install with uv
uv pip install -e .

# Or with pip
pip install -e .
```

## Usage

### Start Server

```bash
# Start Qdrant first
docker run -p 6333:6333 qdrant/qdrant

# Start CLAMS server
clams-server
```

### Configuration

Environment variables:
- `CLAMS_QDRANT_URL` - Qdrant URL (default: http://localhost:6333)
- `CLAMS_EMBEDDING_MODEL` - Embedding model (default: nomic-ai/nomic-embed-text-v1.5)
- `CLAMS_LOG_LEVEL` - Logging level (default: INFO)

### Available Tools

See `src/clams/server/tools/` for all MCP tools:
- `memory.py` - store_memory, retrieve_memories, list_memories, delete_memory
- `code.py` - index_codebase, search_code, find_similar_code
- `git.py` - index_commits, search_commits, get_churn_hotspots, get_code_authors
- `ghap.py` - start_ghap, update_ghap, resolve_ghap, get_active_ghap, list_ghap_entries
- `learning.py` - get_clusters, get_cluster_members, validate_value, store_value, list_values
- `search.py` - search_experiences, search_all

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest -vvsx

# Run linter
ruff check src tests

# Run type checker
mypy src
```

## Architecture

Core components:
- **Embedding**: sentence-transformers with Nomic Embed
- **Vector Store**: Qdrant for semantic search
- **Metadata Store**: SQLite for structured data
- **Parsing**: TreeSitter for code analysis
- **Clustering**: HDBSCAN for experience grouping

See source code for detailed implementation.
