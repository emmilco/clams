# SPEC-002-17: Documentation

## Summary

Create comprehensive documentation for the Learning Memory Server to enable users (Claude Code agents and developers) to effectively use the MCP tools, understand the system architecture, configure the server, and troubleshoot issues.

## Background

### Current State

The Learning Memory Server has:
- **Minimal README**: Basic installation and development commands only (610 bytes)
- **Master Spec**: Comprehensive technical spec (SPEC-001) but aimed at implementers, not users
- **Implementation Summary**: Internal development tracking document (SPEC-002-11)
- **Code Docstrings**: Tool functions have docstrings, but scattered across multiple files
- **No User-Facing Guides**: No documentation on how to actually use the 23 MCP tools
- **No Configuration Guide**: Settings scattered between config.py and the spec
- **No Examples**: No practical examples of tool usage patterns
- **No Troubleshooting**: No guidance for common issues

### What Needs Documentation

The system now has:
- **23 MCP Tools** across 6 modules (memory, code, git, GHAP, learning, search)
- **GHAP Framework** for tracking goal-hypothesis-action-prediction cycles
- **Multi-axis clustering** for experience learning
- **Agent-driven value formation** workflow
- **Configuration options** via environment variables and pydantic-settings
- **Multiple storage layers** (Qdrant, SQLite, local JSON)
- **Async-first architecture** with specific patterns and guidelines

### Target Audiences

1. **Claude Code Agents**: Need to know which tools to use when, parameter formats, expected results
2. **Developers**: Need to understand architecture, add features, debug issues
3. **System Integrators**: Need to deploy, configure, and operate the server
4. **CLAMS Orchestrator**: Needs to dispatch workers with correct context and tools

## Requirements

### Must Have

1. **User Guide for Claude Code Agents**
   - Tool catalog with purpose and use cases
   - Parameter reference for all 23 tools
   - Practical examples of common workflows
   - GHAP usage patterns
   - Error handling guidance

2. **README.md Enhancement**
   - Clear value proposition (what this solves)
   - Quick start (installation to first tool call)
   - Link to detailed guides
   - System requirements

3. **Configuration Guide**
   - All environment variables documented
   - Default values explained
   - When to change settings
   - Multiple deployment scenarios

4. **MCP Tool Reference**
   - All 23 tools documented
   - Required vs optional parameters
   - Return value structures
   - Error conditions
   - Code examples

5. **GHAP Usage Guide**
   - What GHAP is and why it matters
   - How to write good hypotheses
   - When to create entries
   - Resolution patterns
   - Confidence tier implications

6. **Troubleshooting Guide**
   - Common errors and solutions
   - Debug logging configuration
   - Health check procedures
   - Service availability issues

### Should Have

7. **Architecture Overview**
   - System diagram
   - Module responsibilities
   - Data flow diagrams
   - Storage layer explanation
   - Async patterns in the codebase

8. **Value Formation Workflow**
   - Agent-driven clustering process
   - How to trigger clustering
   - Validating value candidates
   - Interpreting cluster results

9. **Developer Guide**
   - Project structure
   - Adding new tools
   - Testing conventions
   - Async guidelines from SPEC-001
   - Contributing guidelines

### Nice to Have

10. **API Examples Collection**
    - Python snippets for direct API usage
    - Claude Code skill integration examples
    - Common multi-tool workflows

11. **Performance Tuning Guide**
    - Embedding batch size optimization
    - Qdrant configuration for scale
    - When to use local vs Docker Qdrant

12. **Migration Guide**
    - Data export/import
    - Version upgrade procedures
    - Backup/restore workflows

## Document Structure

### Proposed File Organization

```
learning-memory-server/
├── README.md                          # Enhanced overview + quick start
├── docs/
│   ├── guides/
│   │   ├── user-guide.md              # Claude Code agent guide
│   │   ├── ghap-guide.md              # GHAP framework usage
│   │   ├── value-formation.md         # Clustering & value workflow
│   │   ├── configuration.md           # All config options
│   │   ├── troubleshooting.md         # Common issues & solutions
│   │   └── architecture.md            # System design overview
│   ├── reference/
│   │   ├── mcp-tools.md               # Complete tool reference
│   │   ├── data-models.md             # Key data structures
│   │   └── environment-variables.md   # Config reference
│   ├── examples/
│   │   ├── basic-workflow.md          # Simple tool usage
│   │   ├── code-search.md             # Code indexing examples
│   │   ├── git-analysis.md            # Git tool examples
│   │   └── learning-cycle.md          # Full GHAP to value cycle
│   └── development/
│       ├── developer-guide.md         # Internal dev docs
│       ├── async-patterns.md          # Async guidelines
│       ├── testing.md                 # Test conventions
│       └── adding-tools.md            # Extending the system
└── CHANGELOG.md                       # Version history (optional)
```

## Content Requirements

### README.md

**Structure:**
```markdown
# Learning Memory Server

## What It Does
- Clear 2-3 sentence value proposition
- Key features (persistent memory, semantic code search, git intelligence, learning from experience)

## Quick Start
1. Installation (uv pip install)
2. Start server
3. First tool call example
4. Link to full user guide

## Documentation
- Links to all guides
- Tool reference link

## Requirements
- Python version
- System dependencies (Qdrant)

## Development
- Brief dev setup
- Link to developer guide
```

**Quality Standards:**
- Must be under 200 lines
- Code examples must be tested/testable
- No marketing fluff, just facts
- Links must be relative and valid

### User Guide (docs/guides/user-guide.md)

**Structure:**
1. **Introduction**
   - What is the Learning Memory Server?
   - Who should use it?
   - Core concepts (MCP, semantic search, GHAP)

2. **Tool Catalog**
   - Memory Tools (4 tools): When to use each
   - Code Tools (3 tools): Indexing and search workflows
   - Git Tools (4 tools): History analysis use cases
   - GHAP Tools (5 tools): Tracking work cycles
   - Learning Tools (5 tools): Clustering and values
   - Search Tools (1 tool): Experience search
   - Utility Tools (1 tool): Health check

3. **Common Workflows**
   - Storing and retrieving memories
   - Indexing a codebase for search
   - Finding code by meaning, not path
   - Tracking debugging with GHAP
   - Running retrospectives (clustering)

4. **Error Handling**
   - Common error types (ValidationError, MCPError, NotFoundError)
   - How to interpret error messages
   - Recovery patterns

**Quality Standards:**
- Real tool examples with actual parameter values
- Show both success and error cases
- Explain *why* to use each tool, not just *how*
- Cross-reference related tools

### GHAP Guide (docs/guides/ghap-guide.md)

**Structure:**
1. **What is GHAP?**
   - Goal-Hypothesis-Action-Prediction framework
   - Why it matters for learning
   - Difference from traditional logging

2. **Writing Good Entries**
   - Goal: Meaningful change, not immediate action
   - Hypothesis: Falsifiable belief that informs action
   - Action: What you're doing based on the hypothesis
   - Prediction: Specific observable outcome
   - Table of good vs bad examples (from SPEC-001)

3. **GHAP Lifecycle**
   - start_ghap: When to create an entry
   - update_ghap: Revising hypothesis mid-work
   - resolve_ghap: Confirmed, falsified, abandoned
   - Annotations: Surprise, root cause, lesson

4. **Confidence Tiers**
   - Gold, Silver, Bronze, Abandoned
   - What affects tier assignment
   - Why tiers matter for clustering

5. **Practical Examples**
   - Debugging example (full cycle)
   - Refactoring example
   - Feature implementation example

**Quality Standards:**
- Include actual GHAP JSON structures
- Show iteration examples (hypothesis revision)
- Contrast good vs bad hypotheses explicitly
- Link to master spec for deeper details

### MCP Tool Reference (docs/reference/mcp-tools.md)

**Structure:**
For each of the 23 tools:

```markdown
### tool_name

**Purpose:** One-line description

**Parameters:**
- `param1` (type, required/optional): Description, constraints
- `param2` (type, required/optional): Description, constraints

**Returns:**
```json
{
  "field": "description",
  "structure": "example"
}
```

**Errors:**
- ValidationError: When X happens
- MCPError: When Y happens

**Example:**
```json
// Request
{
  "tool": "tool_name",
  "arguments": {
    "param1": "value"
  }
}

// Response
{
  "result": "value"
}
```

**See Also:** Related tools
```

**Quality Standards:**
- Every parameter documented (including defaults)
- Return structure fully specified
- At least one complete example per tool
- Error conditions exhaustive
- Examples use realistic data

### Configuration Guide (docs/guides/configuration.md)

**Structure:**
1. **Overview**
   - How configuration works (pydantic-settings, env vars)
   - Precedence order

2. **Environment Variables**
   - For each variable in ServerSettings:
     - Name (with LMS_ prefix)
     - Purpose
     - Default value
     - Valid values/constraints
     - When to change it

3. **Deployment Scenarios**
   - Local development (in-memory Qdrant)
   - Docker-based testing
   - Production deployment
   - Multi-project setup

4. **Storage Configuration**
   - Qdrant URL and connection
   - SQLite path
   - Journal path for GHAP state

5. **Performance Tuning**
   - Embedding model selection
   - Clustering parameters
   - GHAP check frequency

**Quality Standards:**
- Complete table of all variables
- Explain trade-offs for tunable settings
- Provide config examples for each scenario
- Security considerations (if any)

### Architecture Overview (docs/guides/architecture.md)

**Structure:**
1. **System Diagram**
   - High-level component view (from SPEC-001)
   - Data flow arrows

2. **Module Responsibilities**
   - Table: Module → Purpose → Dependencies
   - All 11 modules from project structure

3. **Storage Layers**
   - Qdrant: What and why
   - SQLite: What and why
   - Local JSON: What and why

4. **MCP Integration**
   - How tools are registered
   - Service container pattern
   - Request/response flow

5. **Async Architecture**
   - Why fully async
   - Common patterns
   - Pitfalls to avoid (from SPEC-001 guidelines)

6. **Multi-Axis Embedding**
   - Full, domain, strategy, surprise, root_cause
   - Why multiple axes
   - How clustering uses them

**Quality Standards:**
- Diagrams in ASCII or reference SPEC-001
- Explain *why* for each design choice
- Link to relevant code modules
- Keep under 2000 lines

### Troubleshooting Guide (docs/guides/troubleshooting.md)

**Structure:**
1. **Quick Diagnostics**
   - Health check procedure (ping tool)
   - Log file locations
   - How to enable debug logging

2. **Common Issues**

   **"Code indexing not available"**
   - Cause: CodeIndexer not initialized
   - Check: Service availability in logs
   - Fix: Verify dependencies, check initialization

   **"Git analyzer not available"**
   - Cause: No repo_path or invalid path
   - Fix: Set LMS_REPO_PATH correctly

   **"Not enough experiences for clustering"**
   - Cause: < 20 experiences on axis
   - Fix: Create more GHAP entries or wait

   **"Value validation failed"**
   - Cause: Candidate too far from centroid
   - Fix: Revise value text to better match cluster

   **Connection refused (Qdrant)**
   - Cause: Qdrant not running
   - Fix: Start Qdrant Docker container

   **Empty search results**
   - Possible causes: Not indexed, wrong filters, typo
   - Debug steps: Check collection count, verify filters

3. **Error Reference**
   - ValidationError: Meaning and typical causes
   - MCPError: Meaning and typical causes
   - NotFoundError: Meaning and typical causes
   - InsufficientDataError: Meaning and typical causes

4. **Debugging Techniques**
   - Enabling structlog console output
   - Inspecting vector store collections
   - Checking SQLite metadata
   - Reading journal files

**Quality Standards:**
- Error messages quoted exactly as they appear
- Step-by-step debug procedures
- Copy-paste-able commands
- Links to relevant config/guide sections

## Acceptance Criteria

### Functional

1. **Documentation Completeness**
   - [ ] All 23 MCP tools documented in reference
   - [ ] All 12 environment variables documented
   - [ ] README includes quick start
   - [ ] User guide covers all tool categories
   - [ ] GHAP guide includes good vs bad examples
   - [ ] Configuration guide covers all deployment scenarios
   - [ ] Troubleshooting covers top 10 issues

2. **Quality Standards**
   - [ ] All code examples are syntactically valid JSON/Python
   - [ ] All internal links are valid (no 404s)
   - [ ] No broken cross-references
   - [ ] Consistent terminology throughout
   - [ ] No contradictions with SPEC-001

3. **Usability**
   - [ ] A new user can start the server from README alone
   - [ ] A Claude agent can find the right tool for a task
   - [ ] Error messages reference troubleshooting guide
   - [ ] Examples are copy-paste-able
   - [ ] Guide structure supports skimming (headers, tables)

### Coverage

4. **User Guide**
   - [ ] All 6 tool categories explained with use cases
   - [ ] At least 3 complete workflow examples
   - [ ] Common error patterns documented

5. **GHAP Guide**
   - [ ] GHAP lifecycle fully explained
   - [ ] Good vs bad hypothesis table with 5+ examples
   - [ ] Confidence tier implications clear
   - [ ] At least 2 complete GHAP cycles shown

6. **MCP Tool Reference**
   - [ ] All parameters documented (required, optional, defaults)
   - [ ] All return structures shown as JSON schemas
   - [ ] All error conditions listed
   - [ ] At least 1 example per tool

7. **Configuration Guide**
   - [ ] All ServerSettings fields documented
   - [ ] Environment variable table complete
   - [ ] At least 3 deployment scenarios with example configs

8. **Architecture Guide**
   - [ ] System diagram included
   - [ ] All 11 modules explained
   - [ ] Storage layer rationale clear
   - [ ] Async patterns documented

9. **Troubleshooting Guide**
   - [ ] At least 10 common issues with solutions
   - [ ] Debug logging instructions clear
   - [ ] Health check procedure documented

### Maintainability

10. **Structure**
    - [ ] Clear file organization (guides/, reference/, examples/, development/)
    - [ ] No single file > 1000 lines
    - [ ] Consistent markdown formatting
    - [ ] Table of contents in long documents

11. **Accuracy**
    - [ ] Tool parameter names match actual code
    - [ ] Config variable names match ServerSettings
    - [ ] Error types match actual exception classes
    - [ ] Examples match actual API behavior

12. **Cross-References**
    - [ ] README links to all guides
    - [ ] User guide links to tool reference
    - [ ] Troubleshooting links to config guide
    - [ ] GHAP guide links to master spec for details

## Dependencies

- **SPEC-002-11**: MCP tools implementation (defines tool signatures)
- **SPEC-002-15**: GHAP and learning tools (defines GHAP workflow)
- **SPEC-001**: Master specification (architectural decisions, async guidelines)
- **config.py**: Authoritative source for environment variables
- **Existing docstrings**: Starting point for tool descriptions

## Implementation Notes

### Documentation Tooling

- Plain Markdown (no special tooling required)
- Validate links with `markdown-link-check` or similar
- JSON examples validated with `jq` or Python json.loads()

### Examples Philosophy

- **Prefer real data**: Use actual file paths, repo commits where possible
- **Show failures**: Don't just document happy path
- **Keep focused**: One concept per example
- **Make testable**: Examples should be verifiable against actual system

### Avoiding Duplication

- **Single source of truth**: Config from config.py, tool params from docstrings
- **Link, don't copy**: Reference master spec for deep details
- **Summarize judiciously**: User guide summarizes, reference exhaustive

### Async Guidelines

The architecture guide should extract key async guidelines from SPEC-001:
1. Every I/O function is async
2. Always await async calls
3. Use async for/with for iterators and context managers
4. CPU-bound work uses run_in_executor
5. No sync/async bridging

Include the "wrong vs right" examples from SPEC-001 lines 211-235.

### GHAP Examples

Reuse the excellent example from SPEC-001 Appendix A (lines 1143-1188) as the canonical "good GHAP" example. Show both successful (confirmed) and failed (falsified) cycles.

### Tool Organization

Group tools logically in user guide:
- **Memory**: General-purpose persistence
- **Code**: Codebase indexing and search
- **Git**: Repository history and analysis
- **GHAP**: Work tracking and learning
- **Learning**: Clustering and value formation
- **Search**: Experience retrieval
- **Utility**: System health

## Success Metrics

### Quantitative
- Documentation coverage: 23/23 tools documented
- Example count: At least 30 complete examples
- Cross-reference validity: 100% of links work
- Troubleshooting coverage: Top 10 issues documented

### Qualitative
- **Discoverability**: User can find answer to "How do I X?" in < 2 minutes
- **Completeness**: No critical workflows undocumented
- **Accuracy**: Examples work when copy-pasted
- **Clarity**: Non-technical user can understand GHAP framework

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Documentation drifts from implementation | High | Extract examples from tests, validate against code |
| Examples don't work | High | Make examples executable/testable |
| Too detailed, overwhelming | Medium | Provide quick start + deep dive structure |
| Missing edge cases | Medium | Cross-reference with actual error handling code |
| Inconsistent terminology | Low | Create glossary, use consistent terms |

## Out of Scope

### Explicitly Not Included

1. **API client libraries**: Documentation is for direct MCP usage, not language-specific SDKs
2. **Video tutorials**: Text-only documentation
3. **Interactive playground**: No web-based tool explorer
4. **Comparison with alternatives**: No "vs X" comparisons
5. **Performance benchmarks**: No specific latency/throughput numbers (varies by deployment)
6. **Deployment automation**: No Docker Compose, Kubernetes configs, etc.
7. **Historical context**: No "how we got here" narrative

## Appendix: Tool Inventory

### Memory Tools (4)
1. `store_memory` - Store a memory with semantic embedding
2. `retrieve_memories` - Search memories semantically
3. `list_memories` - List memories with filters (non-semantic)
4. `delete_memory` - Delete a memory by ID

### Code Tools (3)
5. `index_codebase` - Index a directory of source code
6. `search_code` - Search code semantically
7. `find_similar_code` - Find similar code snippets

### Git Tools (4)
8. `search_commits` - Search commits semantically
9. `get_file_history` - Get commit history for a file
10. `get_churn_hotspots` - Find high-churn files
11. `get_code_authors` - Get author statistics for a file

### GHAP Tools (5)
12. `start_ghap` - Begin tracking a new GHAP entry
13. `update_ghap` - Update the current GHAP entry
14. `resolve_ghap` - Resolve the current GHAP entry
15. `get_active_ghap` - Get the current active GHAP entry
16. `list_ghap_entries` - List GHAP entries for the session

### Learning Tools (5)
17. `get_clusters` - Get cluster information for an axis
18. `get_cluster_members` - Get experiences in a cluster
19. `validate_value` - Validate a value candidate
20. `store_value` - Store a validated value
21. `list_values` - List emergent values

### Search Tools (1)
22. `search_experiences` - Search experiences semantically

### Utility Tools (1)
23. `ping` - Health check endpoint

## Appendix: Configuration Variables

From `src/learning_memory_server/server/config.py`:

| Variable | Default | Type | Purpose |
|----------|---------|------|---------|
| `LMS_STORAGE_PATH` | `~/.learning-memory` | str | Base storage directory |
| `LMS_SQLITE_PATH` | `~/.learning-memory/metadata.db` | str | SQLite database path |
| `LMS_JOURNAL_PATH` | `.claude/journal` | str | GHAP journal directory |
| `LMS_QDRANT_URL` | `http://localhost:6333` | str | Qdrant connection URL |
| `LMS_EMBEDDING_MODEL` | `nomic-ai/nomic-embed-text-v1.5` | str | Embedding model name |
| `LMS_EMBEDDING_DIMENSION` | `768` | int | Vector dimension |
| `LMS_HDBSCAN_MIN_CLUSTER_SIZE` | `5` | int | Minimum cluster size |
| `LMS_HDBSCAN_MIN_SAMPLES` | `3` | int | HDBSCAN density parameter |
| `LMS_GHAP_CHECK_FREQUENCY` | `10` | int | Tool calls between GHAP checks |
| `LMS_REPO_PATH` | `None` | str? | Git repository path (optional) |
| `LMS_LOG_LEVEL` | `INFO` | str | Logging level |
| `LMS_LOG_FORMAT` | `json` | str | Log format (json/console) |

---

**Version:** 1.0
**Date:** 2025-12-04
**Author:** CLAMS Orchestrator
**Dependencies:** SPEC-002-11, SPEC-002-15, SPEC-001
