# SPEC-060: Add keyword/lexical search fallback to Searcher

## Summary

Add keyword-based (text substring) search alongside the existing semantic (vector similarity) search so that exact-match queries -- function names, error messages, identifiers -- can be found reliably.

## Motivation

Semantic search works well for conceptual queries but can miss exact text matches (e.g., searching for `_keyword_match_score` by name). A keyword fallback and hybrid mode fill this gap.

## Design

### Search Modes

Three modes, selectable via the `search_mode` parameter (default `"semantic"`):

| Mode | Behaviour |
|------|-----------|
| `semantic` | Existing vector similarity search (default, backward-compatible) |
| `keyword` | Case-insensitive text substring matching on payload fields |
| `hybrid` | Semantic search with keyword-match score boosting |

### Implementation Details

- **Keyword search** scrolls the collection (up to 1000 items), scores each item by substring/term matching against configurable text fields, and returns the top results.
- **Hybrid search** runs both semantic and keyword search, then merges results: items appearing in both get a 0.15 score boost; keyword-only items are appended.
- Per-collection text fields are configured in `_TEXT_FIELDS` (e.g., `content` for memories, `code`/`qualified_name`/`docstring` for code units, `message` for commits).

### Changed Files

- `src/calm/search/searcher.py` -- Core keyword/hybrid/semantic dispatch logic
- `src/calm/tools/code.py` -- `search_code` accepts `search_mode`
- `src/calm/tools/memory.py` -- `retrieve_memories` accepts `search_mode`
- `src/calm/tools/git.py` -- `search_commits` accepts `search_mode`
- `src/calm/tools/learning.py` -- `search_experiences` accepts `search_mode`
- `src/calm/server/app.py` -- MCP tool schemas updated with `search_mode` enum
- `tests/search/test_keyword_search.py` -- New test file (36 tests)
- `tests/search/test_searcher.py` -- Updated invalid-mode test

## Acceptance Criteria

1. `search_mode="keyword"` finds exact text matches in payload fields.
2. `search_mode="semantic"` works identically to the previous behaviour (default).
3. `search_mode="hybrid"` merges semantic and keyword results with proper ranking.
4. `search_mode` parameter is optional and defaults to `"semantic"` everywhere.
5. Invalid `search_mode` values raise `InvalidSearchModeError`.
6. MCP tool schemas expose the `search_mode` enum for `search_code`, `retrieve_memories`, `search_commits`, and `search_experiences`.
