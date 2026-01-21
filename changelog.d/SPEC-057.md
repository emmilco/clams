## SPEC-057: Add Validation to Remaining MCP Tool Parameters

### Summary
Added comprehensive input validation to MCP tool parameters identified in the R4-A audit.

### Changes
- Added `src/clams/server/tools/validation.py` with reusable validation helpers
- Added validation to: assemble_context, retrieve_memories, store_memory, list_memories, delete_memory, search_code, index_codebase, update_ghap, distribute_budget
- All error messages include valid options or acceptable ranges
- Unified ValidationError usage across all tools
