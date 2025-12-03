# Learning Memory Server

MCP server providing semantic code search and git history analysis with automatic learning from user queries.

## Features

- Semantic code search across indexed codebases
- Git history analysis and commit search
- Automatic learning from user query patterns
- Context-aware code recommendations

## Installation

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

## Development

Run tests:
```bash
uv run pytest
```

Linting:
```bash
uv run ruff check .
uv run mypy src/
```

## Usage

```bash
learning-memory-server
```
