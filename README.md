# CLAMS - Claude Learning and Memory System

A Model Context Protocol (MCP) server for semantic memory, code indexing, and experience-based learning.

## Features

- **Memory Management**: Store and retrieve semantic memories with categories
- **Code Indexing**: Index and search Python/TypeScript code with TreeSitter
- **Git Analysis**: Analyze commit history, find churn hotspots, identify code authors
- **GHAP Learning**: Goal-Hypothesis-Action-Prediction cycle with experience clustering
- **Context Assembly**: Generate rich context from memories, code, and experiences

## Installation

### Prerequisites

- **Python 3.12+** - [Download](https://www.python.org/downloads/)
- **uv** - Fast Python package installer
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Docker** - For running Qdrant vector database
  - [Docker Desktop](https://docs.docker.com/get-docker/) (macOS/Windows)
  - Or Docker Engine (Linux)
- **jq** - Command-line JSON processor
  ```bash
  brew install jq  # macOS
  sudo apt-get install jq  # Ubuntu/Debian
  ```

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/clams.git
   cd clams
   ```

2. **Run the installer**:
   ```bash
   ./scripts/install.sh
   ```

   This will:
   - Install Python dependencies
   - Start Qdrant in Docker
   - Register CLAMS as a global MCP server
   - Configure hooks for automatic context injection
   - Initialize storage at `~/.clams/`

3. **Verify installation**:
   Open a new Claude Code session and run:
   ```
   Use the mcp__clams__ping tool
   ```

### Installation Options

```bash
# Preview what will be configured
./scripts/install.sh --dry-run

# Skip Qdrant setup (use existing instance)
./scripts/install.sh --skip-qdrant

# Show help
./scripts/install.sh --help
```

### What Gets Configured

CLAMS installs globally, working across all Claude Code sessions:

- **MCP Server**: Added to `~/.claude.json`
  - Binary: `<repo>/.venv/bin/clams`
- **Hooks**: Registered in `~/.claude/settings.json`
  - SessionStart: Inject context at session start
  - UserPromptSubmit: Retrieve relevant memories before each prompt
  - PreToolUse: Check GHAP status during tool execution
  - PostToolUse: Auto-capture test results as experiences
- **Storage**: `~/.clams/` stores all data
  - `metadata.db` - SQLite metadata store
  - `journal/` - Session journal and GHAP tracking
- **Qdrant**: Docker container on `localhost:6333`

### Troubleshooting

**Port 6333 already in use**:
```bash
# Option 1: Stop existing Qdrant
docker stop $(docker ps -q --filter ancestor=qdrant/qdrant)

# Option 2: Use existing Qdrant
./scripts/install.sh --skip-qdrant
```

**Python version too old**:
```bash
python3 --version  # Must be 3.12+
# Upgrade from https://www.python.org/downloads/
```

**Docker not running**:
```bash
# macOS: Open Docker Desktop
# Linux: sudo systemctl start docker
```

### Uninstallation

```bash
# Remove CLAMS but keep data
./scripts/uninstall.sh

# Full removal including ~/.clams/
./scripts/uninstall.sh --remove-data

# Skip confirmation prompts
./scripts/uninstall.sh --remove-data --force
```

This removes CLAMS from Claude Code configuration but does NOT delete the repository. To fully remove:
```bash
./scripts/uninstall.sh --remove-data --force
rm -rf ~/path/to/clams  # Delete repository
```

## Available Tools

See `src/clams/server/tools/` for all MCP tools:
- `memory.py` - store_memory, retrieve_memories, list_memories, delete_memory
- `code.py` - index_codebase, search_code, find_similar_code
- `git.py` - index_commits, search_commits, get_file_history, get_churn_hotspots, get_code_authors
- `ghap.py` - start_ghap, update_ghap, resolve_ghap, get_active_ghap, list_ghap_entries
- `learning.py` - get_clusters, get_cluster_members, validate_value, store_value, list_values
- `search.py` - search_experiences
- `session.py` - start_session, get_orphaned_ghap, should_check_in, increment_tool_count, reset_tool_count
- `context.py` - assemble_context

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
- **Embedding**: sentence-transformers with Nomic Embed (semantic) and MiniLM (code)
- **Vector Store**: Qdrant for semantic search
- **Metadata Store**: SQLite for structured data
- **Parsing**: TreeSitter for code analysis
- **Clustering**: HDBSCAN for experience grouping
- **HTTP Daemon**: Starlette-based server for hook integration

See source code for detailed implementation.

## Animated Explainer

An interactive visualization of how CLAMS works is available in `clams-visualizer/`. Open `index.html` in a browser to view a 90-second animated explainer covering:
- The GHAP (Goal-Hypothesis-Action-Prediction) learning loop
- Embedding and clustering pipeline
- Context injection into Claude Code sessions
