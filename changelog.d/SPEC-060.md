## SPEC-060: Add keyword/lexical search fallback to Searcher

### Summary
Added keyword and hybrid search modes alongside the existing semantic search, enabling reliable exact-match queries for function names, error messages, and identifiers.

### Changes
- Added `search_mode` parameter ("semantic", "keyword", "hybrid") to all search methods in the Searcher class
- Implemented keyword search via case-insensitive text substring matching on payload fields
- Implemented hybrid search that merges semantic and keyword results with score boosting
- Added `search_mode` parameter to MCP tool functions: `search_code`, `retrieve_memories`, `search_commits`, `search_experiences`
- Updated MCP tool schemas in `app.py` to expose the `search_mode` enum
- Added 36 tests covering keyword scoring, keyword search per collection, hybrid search, backward compatibility, validation, and error handling
