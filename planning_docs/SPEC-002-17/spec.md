# SPEC-002-17: Minimal Documentation

## Summary

Create minimal, self-updating documentation for the Learning Memory Server. The source of truth is the code itself. Documentation should provide navigation and conceptual guidance, not duplicate information that lives in code.

## Philosophy

**Anti-Documentation-Drift Principle:**
- Code is the source of truth
- Documentation should reference code, not duplicate it
- Include "how to find X" rather than "X is currently Y"
- Avoid brittle information that changes frequently

**Target Audience:**
- AI coding agents (Claude Code, CLAMS workers)
- Agents can read code directly, so docs should provide navigation, not exhaustive reference

## Requirements

### 1. GETTING_STARTED.md

A single onboarding document for AI agents. Include:

**What to include:**
- What is the Learning Memory Server? (2-3 sentences)
- How to start the server
- Where to find MCP tools: `src/learning_memory_server/server/tools/`
- Where to find configuration: `src/learning_memory_server/server/config.py`
- Where to find data models: `src/learning_memory_server/observation/models.py`
- GHAP concept: What is Goal-Hypothesis-Action-Prediction? (brief)
- Pointer to master spec for architecture: `planning_docs/SPEC-001-learning-memory-server.md`

**What NOT to include:**
- Tool parameter lists (read the code)
- Configuration value lists (read ServerSettings)
- Detailed architecture diagrams (read the code)
- Version-specific information

### 2. Docstring Audit

Ensure code is self-documenting:

**What to verify:**
- All MCP tools have docstrings with:
  - One-line purpose
  - Args section listing parameters
  - Returns section describing output
  - Raises section if applicable
- All public classes have docstrings
- All public functions have docstrings

**What NOT to do:**
- Create external documentation duplicating docstrings
- Add verbose comments where code is clear

### 3. Integration & Performance Tests (Deferred from SPEC-002-16)

Create the E2E tests and performance benchmarks that were deferred:

**`tests/integration/test_e2e.py`** - 5 scenarios:
1. Memory lifecycle (store → retrieve → delete)
2. Code indexing & search (index → search → find_similar)
3. Git analysis (index → search → churn → authors)
4. GHAP learning loop (20+ entries in ONE test for clustering)
5. Context assembly (populate → assemble light → assemble rich → premortem)

**`tests/performance/test_benchmarks.py`** - 4 benchmarks:
1. Code search: p95 < 200ms (100 iterations)
2. Memory retrieval: p95 < 200ms (100 iterations)
3. Context assembly: p95 < 500ms (10 iterations)
4. Clustering: < 5s for 100 entries (4 axes)

**Test Infrastructure**:
- Use test collection isolation (override AXIS_COLLECTIONS)
- Requires real Qdrant at localhost:6333
- Log benchmark results to JSON for tracking
- Performance targets are HARD requirements

### 4. ARCHITECTURE.md (Optional, if time permits)

A brief architectural map. Include ONLY:
- Module dependency diagram (text-based, not image)
- Data flow: GHAP entry → embedding → vector store → retrieval
- Storage layers: What's in Qdrant, SQLite, JSON files
- Pointer to each module's directory

**Format:**
```
## Module Map

embedding/     - EmbeddingService interface, NomicEmbedding impl
storage/       - VectorStore interface, Qdrant/SQLite impls
observation/   - GHAP state machine, ObservationPersister
...
```

## Acceptance Criteria

### Functional

1. **GETTING_STARTED.md exists** and:
   - Under 100 lines
   - Contains no version-specific or frequently-changing info
   - Points to code locations, not duplicated content
   - An AI agent can find any tool by following the pointers

2. **Docstrings are complete**:
   - All 23 MCP tools have docstrings
   - All public classes in core modules have docstrings
   - Docstrings follow Google style (Args, Returns, Raises)

3. **No documentation drift**:
   - No parameter lists that duplicate code
   - No configuration tables that duplicate ServerSettings
   - All "current value" references point to code, not state value

4. **Integration tests pass**:
   - All 5 E2E scenarios pass with real Qdrant
   - Tests clean up after themselves

5. **Performance benchmarks pass** (HARD requirements):
   - Code search: p95 < 200ms
   - Memory retrieval: p95 < 200ms
   - Context assembly: p95 < 500ms
   - Clustering: < 5s for 100 entries

### Quality

4. **Self-updating design**:
   - Documentation remains accurate even as code changes
   - References are to file paths, not specific line numbers
   - Concepts explained, specifics deferred to code

5. **AI-agent optimized**:
   - Agents can use Glob/Grep to find specifics
   - Docs tell agents WHERE to look, not WHAT they'll find
   - Minimal prose, maximum utility

## Non-Goals

Explicitly OUT OF SCOPE:
- Comprehensive tool reference documentation
- Configuration guide with all variables
- Troubleshooting guide
- Examples directory
- API reference
- Performance tuning guide
- Migration guide

These would create documentation drift. AI agents can read the code.

## File Structure

```
learning-memory-server/
├── README.md               # Minimal, done in SPEC-002-16
├── GETTING_STARTED.md      # NEW: AI agent onboarding
└── ARCHITECTURE.md         # NEW (optional): Module map
```

## Dependencies

**Blocked By:**
- SPEC-002-16 (Integration) - need working system before documenting

**Blocks:**
- Nothing - this is the final task

## Notes

The goal is NOT comprehensive documentation. The goal is:
1. AI agents can find what they need
2. Documentation doesn't drift from code
3. Minimal maintenance burden

If an agent needs to know tool parameters, it reads the tool's docstring. If it needs configuration options, it reads ServerSettings. Documentation provides the MAP, not the TERRITORY.
