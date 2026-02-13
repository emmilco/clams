# CALM - Claude Agent Learning & Management

A unified system for memory, learning, and workflow orchestration for Claude Code agents.

## What is CALM?

CALM provides Claude Code with:

- **Memory**: Persistent semantic memories that improve over time
- **Learning**: Structured capture of experiences via the GHAP (Goal-Hypothesis-Action-Prediction) loop
- **Orchestration**: Task tracking, phase gates, and workflow management (opt-in)

CALM operates in two modes:

| Mode | Activation | Features |
|------|------------|----------|
| **Memory** | Always on | Memory storage/retrieval, GHAP tracking, `/wrapup`, `/reflection`, context assembly |
| **Orchestration** | `/orchestrate` per session | + Tasks, phases, gates, worktrees, workers, reviews |

## Features

- **Semantic Memory**: Store and retrieve memories with categories (facts, preferences, decisions, workflows)
- **Code Indexing**: Index and search Python/TypeScript/Rust/Java code with TreeSitter
- **Git Analysis**: Analyze commit history, find churn hotspots, identify code authors
- **GHAP Learning**: Track hypotheses, compare predictions to outcomes, cluster experiences
- **Context Assembly**: Automatically inject relevant memories and experiences into sessions
- **Workflow Orchestration**: Full software development lifecycle management with phase gates

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

### Quick Start

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>   # Replace with your actual repo URL
   cd calm
   ```

2. **Run the installer**:
   ```bash
   ./scripts/install.sh
   ```

   This will:
   - Install Python dependencies
   - Start Qdrant in Docker
   - Register CALM as a global MCP server
   - Configure hooks for automatic context injection
   - Initialize storage at `~/.calm/`

3. **Verify installation**:
   Open a new Claude Code session. You should see:
   ```
   CALM (Claude Agent Learning & Management) is available.

   Always active: /wrapup, /reflection, memory tools
   Run /orchestrate to enable task tracking and workflow tools.
   ```

### Installation Options

```bash
# Preview what will be configured
./scripts/install.sh --dry-run

# Skip Qdrant setup (use existing instance)
./scripts/install.sh --skip-qdrant

# Skip confirmation prompts
./scripts/install.sh -y

# Show help
./scripts/install.sh --help
```

### What Gets Configured

CALM installs globally, working across all Claude Code sessions:

- **MCP Server**: Added to `~/.claude.json`
- **Hooks**: Registered in `~/.claude/settings.json`
  - SessionStart: Announce CALM availability and project tasks
  - UserPromptSubmit: Inject relevant memories before each prompt
  - PreToolUse: GHAP check-in reminders
  - PostToolUse: Capture test outcomes as experiences
- **Storage**: `~/.calm/` stores all data
  - `metadata.db` - SQLite database for memories, sessions, tasks
  - `sessions/` - Session logs for reflection
  - `roles/` - Specialist role definitions
  - `workflows/` - Orchestration workflow instructions
  - `skills/` - Claude Code skill wrappers
  - `journal/` - Session journal storage
- **Qdrant**: Docker container on `localhost:6333`

### Uninstallation

```bash
# Remove CALM but keep data
./scripts/uninstall.sh

# Full removal including ~/.calm/
./scripts/uninstall.sh --remove-data
```

## Usage

### Memory Mode (Always Active)

Memory features work automatically in every Claude Code session:

**Session Wrapup** - End sessions cleanly with `/wrapup`:
```
/wrapup           # Archive session
/wrapup continue  # Handoff for continuation
```

**Reflection** - Extract learnings from past sessions with `/reflection`:
- Analyzes unreflected session logs
- Proposes memories using multi-agent analysis
- Batch approval UI for storing durable insights

**Context Injection** - Automatic memory retrieval:
- Relevant memories are injected at the start of each prompt
- GHAP experiences inform similar debugging scenarios

### Orchestration Mode (Opt-In)

Enable full workflow orchestration for a session:
```
/orchestrate
```

This activates:
- **Task Management**: Create, track, and transition tasks through phases
- **Phase Gates**: Automated checks before phase transitions
- **Worktrees**: Isolated git worktrees for each task
- **Workers**: Dispatch specialist agents for implementation
- **Reviews**: 2x review requirement before advancing

See `CLAUDE.md` for detailed workflow instructions.

## CLI Reference

The `calm` CLI provides all orchestration commands:

```bash
# System status
calm status              # Full status overview
calm init                # First-time setup

# Task management
calm task create SPEC-001 "Feature title"
calm task list
calm task show SPEC-001
calm task transition SPEC-001 DESIGN --gate-result pass

# Gate checks
calm gate check SPEC-001 IMPLEMENT-CODE_REVIEW
calm gate list

# Worktrees
calm worktree create SPEC-001
calm worktree list
calm worktree merge SPEC-001

# Server
calm server start
calm server stop
calm server status
```

Run `calm --help` or `calm <command> --help` for full documentation.

## Architecture

### Core Components

- **Embedding**: sentence-transformers with Nomic Embed (semantic) and MiniLM (code)
- **Vector Store**: Qdrant for semantic search
- **Metadata Store**: SQLite for structured data
- **Parsing**: TreeSitter for code analysis
- **Clustering**: HDBSCAN for experience grouping
- **MCP Server**: Exposes tools to Claude Code

### Directory Structure

```
~/.calm/
├── config.yaml              # User preferences
├── metadata.db              # SQLite database
├── workflows/
│   └── default.md           # Orchestration instructions
├── roles/
│   ├── architect.md
│   ├── backend.md
│   ├── reviewer.md
│   └── ...
├── skills/                  # Claude Code skill wrappers
├── journal/                 # Session journal storage
└── sessions/
    └── <timestamp>.jsonl    # Session logs for reflection
```

### Source Layout

```
src/calm/
├── cli/            # Click-based CLI commands
├── clustering/     # HDBSCAN experience clustering
├── context/        # Context assembly and token budgeting
├── db/             # SQLite metadata store
├── embedding/      # Embedding service implementations
├── ghap/           # GHAP state machine and persistence
├── git/            # Git history analysis
├── hooks/          # Claude Code hook scripts
├── indexers/       # Tree-sitter code parsing
├── install/        # Installation and setup
├── orchestration/  # Task, worktree, worker, gate management
├── search/         # Unified semantic search
├── server/         # MCP server
├── storage/        # Vector store (Qdrant and in-memory)
├── tools/          # MCP tool definitions
├── utils/          # Shared utilities
└── values/         # Value store and validation
```

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
pytest -vvsx

# Run linter
ruff check src tests

# Run type checker
mypy --strict src
```

### Test Categories

- **Unit tests**: Core functionality with mocked dependencies
- **Integration tests**: Real Qdrant instance (`tests/integration/`)
- **Cold-start tests**: Empty state scenarios (`-m cold_start`)
- **Performance tests**: Latency benchmarks (`tests/performance/`)

## Troubleshooting

**Port 6333 already in use**:
```bash
# Stop existing Qdrant
docker stop $(docker ps -q --filter ancestor=qdrant/qdrant)

# Or use existing instance
./scripts/install.sh --skip-qdrant
```

**Python version too old**:
```bash
python3 --version  # Must be 3.12+
```

**Docker not running**:
```bash
# macOS: Open Docker Desktop
# Linux: sudo systemctl start docker
```

**MCP server not responding**:
```bash
# Check server status
calm server status

# Restart the server
calm server restart
```

**CALM not recognized in Claude Code**:
```bash
# Verify MCP server is registered
cat ~/.claude.json | grep calm

# Restart Claude Code after installation
```

## Animated Explainer

An interactive visualization of how CALM works is available in `calm-visualizer/`. Open `index.html` in a browser to view a 90-second animated explainer covering the GHAP learning loop and context injection.

## License

MIT
