# Technical Proposal: MCP Tools for GHAP and Learning

## Problem Statement

The Learning Memory Server provides the backend services for GHAP tracking (ObservationCollector, ObservationPersister), learning (Clusterer, ValueStore), and search (Searcher). However, these services are not yet exposed to Claude Code agents via MCP (Model Context Protocol) tools.

Without MCP tools, agents cannot:
1. **Track working state** - Start, update, and resolve GHAP entries during tasks
2. **Form values** - Cluster experiences and create validated values during retrospectives
3. **Search experiences** - Find relevant past experiences for context assembly

This spec implements the MCP tool layer that bridges Claude Code agents to the underlying services.

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Claude Code Agent                           │
│              (via MCP protocol over stdio)                       │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (main.py)                          │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              register_all_tools()                          │ │
│  │  • Initializes shared services once                       │ │
│  │  • Calls tool registration functions                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│  GHAP Tools    │  │ Learning Tools │  │  Search Tools  │
│  (ghap.py)     │  │ (learning.py)  │  │ (search.py)    │
└────────┬───────┘  └────────┬───────┘  └────────┬───────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│               Underlying Services                        │
│  • ObservationCollector / ObservationPersister          │
│  • ExperienceClusterer / Clusterer                      │
│  • ValueStore                                           │
│  • Searcher                                             │
│  • EmbeddingService / VectorStore                       │
└─────────────────────────────────────────────────────────┘
```

### Module Structure

```
server/
├── __init__.py
├── main.py              # Server entry point (already exists)
├── config.py            # Server settings (already exists)
├── logging.py           # Logging config (already exists)
└── tools/
    ├── __init__.py      # Tool registration coordinator
    ├── errors.py        # Custom error types (NEW)
    ├── enums.py         # Domain/strategy/root cause enums (NEW)
    ├── ghap.py          # GHAP tools (NEW)
    ├── learning.py      # Learning tools (NEW)
    └── search.py        # Search tools (NEW)
```

## Key Design Decisions

### 1. Tool Registration Pattern

**Pattern: Decorator-based registration with service dependency injection**

```python
# In tools/__init__.py
def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server."""

    # Initialize shared services (once per server instance)
    embedding_service = get_embedding_service(settings)
    vector_store = get_vector_store(settings)

    # Initialize GHAP/learning services
    observation_collector = ObservationCollector(settings.journal_path)
    observation_persister = ObservationPersister(embedding_service, vector_store)
    clusterer = Clusterer(
        min_cluster_size=settings.hdbscan_min_cluster_size,
        min_samples=settings.hdbscan_min_samples,
    )
    experience_clusterer = ExperienceClusterer(vector_store, clusterer)
    value_store = ValueStore(embedding_service, vector_store, experience_clusterer)
    searcher = Searcher(embedding_service, vector_store)

    # Register tool modules (each module receives services it needs)
    register_ghap_tools(server, observation_collector, observation_persister)
    register_learning_tools(server, experience_clusterer, value_store)
    register_search_tools(server, searcher)

    logger.info("tools.registered", tool_count=11)
```

**In ghap.py:**
```python
def register_ghap_tools(
    server: Server,
    collector: ObservationCollector,
    persister: ObservationPersister,
) -> None:
    """Register GHAP tools with MCP server."""

    @server.call_tool()  # type: ignore[misc, no-untyped-call]
    async def start_ghap(
        domain: str,
        strategy: str,
        goal: str,
        hypothesis: str,
        action: str,
        prediction: str,
    ) -> dict:
        """Begin tracking a new GHAP entry.

        Args:
            domain: Task domain (debugging, refactoring, feature, etc.)
            strategy: Problem-solving strategy
            goal: What meaningful change are you trying to make?
            hypothesis: What do you believe about the situation?
            action: What are you doing based on this belief?
            prediction: If your hypothesis is correct, what will you observe?

        Returns:
            GHAP entry record with id and timestamp
        """
        try:
            # Validate domain
            if domain not in DOMAINS:
                raise ValidationError(
                    f"Invalid domain '{domain}'. "
                    f"Valid options: {', '.join(DOMAINS)}"
                )

            # Validate strategy
            if strategy not in STRATEGIES:
                raise ValidationError(
                    f"Invalid strategy '{strategy}'. "
                    f"Valid options: {', '.join(STRATEGIES)}"
                )

            # Validate text lengths
            for field, value in [
                ("goal", goal), ("hypothesis", hypothesis),
                ("action", action), ("prediction", prediction)
            ]:
                if not value or not value.strip():
                    raise ValidationError(f"Field '{field}' cannot be empty")
                if len(value) > 1000:
                    raise ValidationError(
                        f"Field '{field}' exceeds 1000 character limit "
                        f"({len(value)} chars)"
                    )

            # Check for active GHAP (warn but allow)
            current = await collector.get_current()
            if current is not None:
                logger.warning(
                    "ghap.orphaned_entry",
                    current_id=current["id"],
                    message="Starting new GHAP with active entry - previous entry orphaned"
                )

            # Create GHAP entry
            entry = await collector.create_ghap(
                domain=domain,
                strategy=strategy,
                goal=goal,
                hypothesis=hypothesis,
                action=action,
                prediction=prediction,
            )

            logger.info("ghap.started", ghap_id=entry["id"], domain=domain, strategy=strategy)

            return {
                "id": entry["id"],
                "domain": entry["domain"],
                "strategy": entry["strategy"],
                "goal": entry["goal"],
                "hypothesis": entry["hypothesis"],
                "action": entry["action"],
                "prediction": entry["prediction"],
                "created_at": entry["created_at"],
            }

        except ValidationError as e:
            logger.warning("ghap.validation_error", error=str(e))
            return {"error": {"type": "validation_error", "message": str(e)}}
        except Exception as e:
            logger.error("ghap.unexpected_error", tool="start_ghap", error=str(e), exc_info=True)
            return {"error": {"type": "internal_error", "message": "Internal server error"}}

    # Register other GHAP tools: update_ghap, resolve_ghap, get_active_ghap, list_ghap_entries
    # ...
```

**Rationale:**
- **Single initialization** - Services created once per server instance, not per request
- **Explicit dependencies** - Each tool module receives only the services it needs
- **Decorator pattern** - MCP SDK's `@server.call_tool()` handles registration
- **Type safety** - Full type hints on parameters and return values
- **Clean separation** - Registration logic separate from tool implementation

### 2. Error Handling Strategy

**Pattern: Custom exception types with MCP error format responses**

```python
# In tools/errors.py
class MCPError(Exception):
    """Base error for MCP tool failures."""
    pass

class ValidationError(MCPError):
    """Input validation failed."""
    pass

class NotFoundError(MCPError):
    """Resource not found."""
    pass

class InsufficientDataError(MCPError):
    """Not enough data for operation."""
    pass
```

**Error response format (applied in all tools):**
```python
try:
    # Tool implementation
    result = await some_operation()
    return result
except ValidationError as e:
    logger.warning("tool.validation_error", tool="tool_name", error=str(e))
    return {"error": {"type": "validation_error", "message": str(e)}}
except NotFoundError as e:
    logger.warning("tool.not_found", tool="tool_name", error=str(e))
    return {"error": {"type": "not_found", "message": str(e)}}
except InsufficientDataError as e:
    logger.warning("tool.insufficient_data", tool="tool_name", error=str(e))
    return {"error": {"type": "insufficient_data", "message": str(e)}}
except Exception as e:
    logger.error("tool.unexpected_error", tool="tool_name", error=str(e), exc_info=True)
    return {"error": {"type": "internal_error", "message": "Internal server error"}}
```

**Rationale:**
- **Consistent format** - All errors follow same structure
- **Clear categorization** - Error type indicates failure mode
- **Helpful messages** - Include context (field names, valid values, etc.)
- **No stack traces to client** - Internal errors return generic message
- **Structured logging** - All errors logged with context for debugging

### 3. Enum Validation

**Pattern: Centralized enum definitions with validation helpers**

```python
# In tools/enums.py

# Domain values
DOMAINS = [
    "debugging",
    "refactoring",
    "feature",
    "testing",
    "configuration",
    "documentation",
    "performance",
    "security",
    "integration",
]

# Strategy values
STRATEGIES = [
    "systematic-elimination",
    "trial-and-error",
    "research-first",
    "divide-and-conquer",
    "root-cause-analysis",
    "copy-from-similar",
    "check-assumptions",
    "read-the-error",
    "ask-user",
]

# Root cause categories
ROOT_CAUSE_CATEGORIES = [
    "wrong-assumption",
    "missing-knowledge",
    "oversight",
    "environment-issue",
    "misleading-symptom",
    "incomplete-fix",
    "wrong-scope",
    "test-isolation",
    "timing-issue",
]

# Experience axes (note: domain is NOT an axis, it's metadata on experiences_full)
VALID_AXES = ["full", "strategy", "surprise", "root_cause"]

# Outcome status values
OUTCOME_STATUS_VALUES = ["confirmed", "falsified", "abandoned"]


def validate_domain(domain: str) -> None:
    """Validate domain enum value."""
    if domain not in DOMAINS:
        raise ValidationError(
            f"Invalid domain '{domain}'. "
            f"Valid options: {', '.join(DOMAINS)}"
        )


def validate_strategy(strategy: str) -> None:
    """Validate strategy enum value."""
    if strategy not in STRATEGIES:
        raise ValidationError(
            f"Invalid strategy '{strategy}'. "
            f"Valid options: {', '.join(STRATEGIES)}"
        )


def validate_axis(axis: str) -> None:
    """Validate clustering axis value."""
    if axis not in VALID_AXES:
        raise ValidationError(
            f"Invalid axis '{axis}'. "
            f"Valid options: {', '.join(VALID_AXES)}"
        )


def validate_outcome_status(status: str) -> None:
    """Validate outcome status value."""
    if status not in OUTCOME_STATUS_VALUES:
        raise ValidationError(
            f"Invalid outcome status '{status}'. "
            f"Valid options: {', '.join(OUTCOME_STATUS_VALUES)}"
        )


def validate_root_cause_category(category: str) -> None:
    """Validate root cause category value."""
    if category not in ROOT_CAUSE_CATEGORIES:
        raise ValidationError(
            f"Invalid root_cause category '{category}'. "
            f"Valid options: {', '.join(ROOT_CAUSE_CATEGORIES)}"
        )
```

**Rationale:**
- **Single source of truth** - Enums defined once, used everywhere
- **Validation helpers** - Consistent error messages across tools
- **Easy to update** - Adding new values requires changing one file
- **Clear documentation** - Comments clarify special cases (domain not an axis)

### 4. Persistence with Retry

**Pattern: Exponential backoff for ObservationPersister calls**

```python
# In resolve_ghap tool
async def resolve_ghap(
    status: str,
    result: str,
    surprise: str | None = None,
    root_cause: dict | None = None,
    lesson: dict | None = None,
) -> dict:
    """Mark the current GHAP entry as resolved."""
    try:
        # ... validation ...

        # Mark resolved locally (always succeeds)
        resolved = await collector.resolve_ghap(
            status=status,
            result=result,
            surprise=surprise,
            root_cause=root_cause,
            lesson=lesson,
        )

        # Persist to VectorStore with retry
        max_retries = 3
        backoff = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                await persister.persist(resolved)
                logger.info(
                    "ghap.persisted",
                    ghap_id=resolved["id"],
                    attempt=attempt + 1
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "ghap.persist_retry",
                        ghap_id=resolved["id"],
                        attempt=attempt + 1,
                        backoff_seconds=backoff,
                        error=str(e)
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2  # Exponential backoff: 1s, 2s, 4s
                else:
                    # Final attempt failed
                    logger.error(
                        "ghap.persist_failed",
                        ghap_id=resolved["id"],
                        attempts=max_retries,
                        error=str(e)
                    )
                    raise MCPError(
                        f"Failed to persist GHAP entry after {max_retries} attempts. "
                        "Local resolution saved, but embedding/storage failed. "
                        f"Error: {e}"
                    )

        return {
            "id": resolved["id"],
            "status": resolved["status"],
            "confidence_tier": resolved["confidence_tier"],
            "resolved_at": resolved["resolved_at"],
        }

    except ValidationError as e:
        # ... error handling ...
```

**Rationale:**
- **Resilience** - Transient failures (network, Qdrant restart) are retried
- **Local safety** - Resolution saved locally before persistence attempt
- **Exponential backoff** - Avoids hammering failed services (1s, 2s, 4s)
- **Clear failure** - After 3 attempts, error explains what succeeded (local) and what failed (remote)
- **Structured logging** - Track retry attempts for debugging

### 5. Tool Module Organization

Each tool module follows the same structure:

**ghap.py (5 tools):**
- `start_ghap` - Create new GHAP entry
- `update_ghap` - Update current entry
- `resolve_ghap` - Mark resolved and persist
- `get_active_ghap` - Get current entry
- `list_ghap_entries` - Query resolved entries

**learning.py (5 tools):**
- `get_clusters` - List clusters for an axis
- `get_cluster_members` - Get experiences in a cluster
- `validate_value` - Check value candidate against centroid
- `store_value` - Store validated value
- `list_values` - Query stored values

**search.py (1 tool):**
- `search_experiences` - Semantic search across axes

**Rationale:**
- **Logical grouping** - Tools grouped by functionality (GHAP, learning, search)
- **Independent modules** - Each can be developed and tested separately
- **Clear responsibilities** - One module per service layer

## Implementation Details

### Tool Signature Examples

#### GHAP Tools

```python
async def start_ghap(
    domain: str,
    strategy: str,
    goal: str,
    hypothesis: str,
    action: str,
    prediction: str,
) -> dict:
    """Begin tracking a new GHAP entry."""
    # Returns: {"id": str, "domain": str, ..., "created_at": str}
    # Or: {"error": {"type": str, "message": str}}


async def update_ghap(
    hypothesis: str | None = None,
    action: str | None = None,
    prediction: str | None = None,
    strategy: str | None = None,
    note: str | None = None,
) -> dict:
    """Update the current GHAP entry."""
    # Returns: {"success": bool, "iteration_count": int}
    # Or: {"error": {...}}


async def resolve_ghap(
    status: str,
    result: str,
    surprise: str | None = None,
    root_cause: dict | None = None,  # {"category": str, "description": str}
    lesson: dict | None = None,      # {"what_worked": str, "takeaway": str | None}
) -> dict:
    """Mark the current GHAP entry as resolved."""
    # Returns: {"id": str, "status": str, "confidence_tier": str, "resolved_at": str}
    # Or: {"error": {...}}


async def get_active_ghap() -> dict:
    """Get the current active GHAP entry."""
    # Returns: {"id": str | None, ..., "has_active": bool}


async def list_ghap_entries(
    limit: int = 20,
    domain: str | None = None,
    outcome: str | None = None,
    since: str | None = None,  # ISO date
) -> dict:
    """List recent GHAP entries with filters."""
    # Returns: {"results": [...], "count": int}
    # Or: {"error": {...}}
```

#### Learning Tools

```python
async def get_clusters(axis: str) -> dict:
    """Get cluster information for a given axis."""
    # Returns: {"axis": str, "clusters": [...], "count": int, "noise_count": int}
    # Or: {"error": {...}}


async def get_cluster_members(
    cluster_id: str,
    limit: int = 50,
) -> dict:
    """Get experiences in a specific cluster."""
    # Returns: {"cluster_id": str, "axis": str, "members": [...], "count": int}
    # Or: {"error": {...}}


async def validate_value(
    text: str,
    cluster_id: str,
) -> dict:
    """Validate a proposed value statement against a cluster centroid."""
    # Returns: {"valid": bool, "similarity": float | None, "centroid_distance": float, ...}
    # Or: {"error": {...}}


async def store_value(
    text: str,
    cluster_id: str,
    axis: str,
) -> dict:
    """Store a validated value statement."""
    # Returns: {"id": str, "text": str, "axis": str, ..., "created_at": str}
    # Or: {"error": {...}}


async def list_values(
    axis: str | None = None,
    limit: int = 20,
) -> dict:
    """List stored values with optional axis filter."""
    # Returns: {"results": [...], "count": int}
    # Or: {"error": {...}}
```

#### Search Tools

```python
async def search_experiences(
    query: str,
    axis: str = "full",
    domain: str | None = None,
    outcome: str | None = None,
    limit: int = 10,
) -> dict:
    """Search experiences semantically across axes."""
    # Returns: {"results": [...], "count": int}
    # Or: {"error": {...}}
```

### Service Initialization

```python
# In tools/__init__.py

def register_all_tools(server: Server, settings: ServerSettings) -> None:
    """Register all MCP tools with the server.

    Services are initialized once per server instance and passed to tool modules.
    """
    logger = structlog.get_logger(__name__)

    # Initialize shared infrastructure
    embedding_service = NomicEmbedding(
        model_name=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )

    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
    )

    # Initialize GHAP services
    observation_collector = ObservationCollector(
        journal_path=settings.journal_path,
    )
    observation_persister = ObservationPersister(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    # Initialize learning services
    clusterer = Clusterer(
        min_cluster_size=settings.hdbscan_min_cluster_size,
        min_samples=settings.hdbscan_min_samples,
        metric="cosine",
        cluster_selection_method="eom",
    )
    experience_clusterer = ExperienceClusterer(
        vector_store=vector_store,
        clusterer=clusterer,
    )
    value_store = ValueStore(
        embedding_service=embedding_service,
        vector_store=vector_store,
        clusterer=experience_clusterer,
    )

    # Initialize search services
    searcher = Searcher(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    # Register tool modules
    register_ghap_tools(server, observation_collector, observation_persister)
    register_learning_tools(server, experience_clusterer, value_store)
    register_search_tools(server, searcher)

    logger.info("tools.registered", tool_count=11)
```

### Datetime Handling

All timestamps use ISO 8601 format (UTC):

```python
from datetime import datetime, timezone

# Creating timestamps
timestamp = datetime.now(timezone.utc).isoformat()
# Example: "2024-01-15T10:30:45.123456+00:00"

# Parsing timestamps
parsed = datetime.fromisoformat(timestamp)
# Handles both 'Z' and '+00:00' formats
```

### Result Payload Mapping

Tools map underlying service results to MCP-friendly dicts:

```python
# Example: get_cluster_members
async def get_cluster_members(cluster_id: str, limit: int = 50) -> dict:
    try:
        # Validate cluster_id format
        if not cluster_id or "_" not in cluster_id:
            raise ValidationError(
                f"Invalid cluster_id format: {cluster_id}. "
                "Expected format: 'axis_label' (e.g., 'full_0', 'strategy_2')"
            )

        # Parse axis
        axis = cluster_id.rsplit("_", 1)[0]
        validate_axis(axis)

        # Get cluster info from ExperienceClusterer
        clusters = await experience_clusterer.cluster_axis(axis)
        cluster = next((c for c in clusters if c.cluster_id == cluster_id), None)

        if cluster is None:
            raise NotFoundError(f"Cluster not found: {cluster_id}")

        # Get member experiences from VectorStore
        collection = f"experiences_{axis}"
        members = []

        for member_id in cluster.member_ids[:limit]:
            result = await vector_store.get(
                collection=collection,
                id=member_id,
                with_vector=False,  # Don't need vectors for display
            )

            if result is not None:
                p = result.payload
                members.append({
                    "id": result.id,
                    "ghap_id": p["ghap_id"],
                    "goal": p["goal"],
                    "hypothesis": p["hypothesis"],
                    "action": p["action"],
                    "prediction": p["prediction"],
                    "outcome_status": p["outcome_status"],
                    "outcome_result": p["outcome_result"],
                    "surprise": p.get("surprise"),
                    "root_cause": p.get("root_cause"),
                    "lesson": p.get("lesson"),
                    "confidence_tier": p["confidence_tier"],
                    "created_at": p["created_at"],
                })

        return {
            "cluster_id": cluster_id,
            "axis": axis,
            "members": members,
            "count": len(members),
        }

    except ValidationError as e:
        return {"error": {"type": "validation_error", "message": str(e)}}
    except NotFoundError as e:
        return {"error": {"type": "not_found", "message": str(e)}}
    except Exception as e:
        logger.error("tool.error", tool="get_cluster_members", error=str(e), exc_info=True)
        return {"error": {"type": "internal_error", "message": "Internal server error"}}
```

## Testing Strategy

### Unit Tests

Each tool tested independently with mocked services:

```python
# tests/server/tools/test_ghap.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from learning_memory_server.server.tools.ghap import register_ghap_tools
from learning_memory_server.observation import ObservationCollector


@pytest.fixture
def mock_collector():
    collector = AsyncMock(spec=ObservationCollector)
    collector.create_ghap.return_value = {
        "id": "ghap_123",
        "domain": "debugging",
        "strategy": "systematic-elimination",
        "goal": "Fix auth timeout",
        "hypothesis": "Network latency exceeds timeout",
        "action": "Increasing timeout to 60s",
        "prediction": "Auth failures stop",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return collector


@pytest.fixture
def mock_persister():
    return AsyncMock()


@pytest.fixture
def mock_server():
    """Mock MCP Server with tool registry."""
    server = MagicMock()
    server.tools = {}

    def register_tool(func):
        server.tools[func.__name__] = func
        return func

    server.call_tool = lambda: register_tool
    return server


@pytest.mark.asyncio
async def test_start_ghap_success(mock_server, mock_collector, mock_persister):
    """Test successful GHAP creation."""
    register_ghap_tools(mock_server, mock_collector, mock_persister)

    tool = mock_server.tools["start_ghap"]
    result = await tool(
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix auth timeout",
        hypothesis="Network latency exceeds timeout",
        action="Increasing timeout to 60s",
        prediction="Auth failures stop",
    )

    assert "error" not in result
    assert result["id"] == "ghap_123"
    assert result["domain"] == "debugging"
    assert result["strategy"] == "systematic-elimination"

    mock_collector.create_ghap.assert_called_once()


@pytest.mark.asyncio
async def test_start_ghap_invalid_domain(mock_server, mock_collector, mock_persister):
    """Test validation error for invalid domain."""
    register_ghap_tools(mock_server, mock_collector, mock_persister)

    tool = mock_server.tools["start_ghap"]
    result = await tool(
        domain="invalid",
        strategy="systematic-elimination",
        goal="Test",
        hypothesis="Test",
        action="Test",
        prediction="Test",
    )

    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert "Invalid domain" in result["error"]["message"]
    assert "debugging" in result["error"]["message"]  # Shows valid options


@pytest.mark.asyncio
async def test_start_ghap_field_too_long(mock_server, mock_collector, mock_persister):
    """Test validation error for field exceeding length limit."""
    register_ghap_tools(mock_server, mock_collector, mock_persister)

    tool = mock_server.tools["start_ghap"]
    result = await tool(
        domain="debugging",
        strategy="systematic-elimination",
        goal="x" * 1001,  # Exceeds 1000 char limit
        hypothesis="Test",
        action="Test",
        prediction="Test",
    )

    assert "error" in result
    assert result["error"]["type"] == "validation_error"
    assert "1000 character limit" in result["error"]["message"]
```

### Integration Tests

Test tools with real services (in-memory or test container):

```python
# tests/server/tools/test_integration.py

import pytest
from datetime import datetime, timezone

from learning_memory_server.server.main import create_server
from learning_memory_server.server.config import ServerSettings
from learning_memory_server.storage.memory import InMemoryVectorStore
from learning_memory_server.embedding.mock import MockEmbedding


@pytest.fixture
async def test_server():
    """Create server with in-memory dependencies."""
    settings = ServerSettings(
        storage_path="/tmp/test-learning-memory",
        journal_path="/tmp/test-journal",
    )

    # Override dependencies with test implementations
    # (In real implementation, use dependency injection or config)
    server = create_server(settings)
    return server


@pytest.mark.asyncio
async def test_ghap_workflow_end_to_end(test_server):
    """Test full GHAP workflow: start, update, resolve."""
    # This would use the actual server's tool registry
    # and test the complete flow with real services

    # Start GHAP
    start_result = await test_server.call_tool(
        "start_ghap",
        domain="debugging",
        strategy="systematic-elimination",
        goal="Fix flaky test",
        hypothesis="Timing issue",
        action="Adding sleep",
        prediction="Test passes consistently",
    )

    assert "error" not in start_result
    ghap_id = start_result["id"]

    # Update GHAP
    update_result = await test_server.call_tool(
        "update_ghap",
        hypothesis="Test pollution - previous test leaves state",
        action="Adding teardown to previous test",
    )

    assert "error" not in update_result
    assert update_result["iteration_count"] == 2

    # Resolve GHAP
    resolve_result = await test_server.call_tool(
        "resolve_ghap",
        status="confirmed",
        result="Test passed 3/3 runs",
        lesson={
            "what_worked": "Added proper teardown",
            "takeaway": "Flaky tests often isolation issues",
        },
    )

    assert "error" not in resolve_result
    assert resolve_result["status"] == "confirmed"
    assert resolve_result["confidence_tier"] == "gold"
```

### Test Coverage Requirements

- **Unit tests**: ≥90% coverage for all tool modules
- **Integration tests**: All happy paths and major error cases
- **Error handling**: Test all error types for each tool
- **Input validation**: Test boundary conditions (length limits, enum values)
- **Enum validation**: Test all valid and invalid domain/strategy/outcome values

## Performance Considerations

### Latency Targets (P95)

| Tool | Target | Notes |
|------|--------|-------|
| start_ghap | <100ms | Local file write |
| update_ghap | <100ms | Local file write |
| resolve_ghap | <1s typical, <10s max | Includes embedding + storage with retries |
| get_active_ghap | <50ms | Local file read |
| list_ghap_entries | <200ms | VectorStore query with filters |
| get_clusters | <2s | Clustering computation |
| get_cluster_members | <300ms | VectorStore batch get |
| validate_value | <500ms | Includes embedding generation |
| store_value | <500ms | Includes validation + embedding + storage |
| list_values | <100ms | VectorStore query |
| search_experiences | <300ms | Includes embedding + vector search |

### Optimization Strategies

1. **Local GHAP storage** - ObservationCollector operates on local JSON (no network latency)
2. **Retry with backoff** - Persistence failures use exponential backoff (don't hammer)
3. **Connection pooling** - VectorStore connections reused across calls
4. **Result limiting** - Enforce max result counts to prevent large payloads
5. **Async throughout** - All I/O is async, no blocking operations

## Dependencies

### Existing (from prior specs)

- SPEC-002-02: EmbeddingService (Nomic)
- SPEC-002-03: VectorStore (Qdrant)
- SPEC-002-04: SQLite metadata store
- SPEC-002-05: MCP server skeleton
- SPEC-002-09: Searcher
- SPEC-002-10: ObservationCollector + ObservationPersister
- SPEC-002-12: Clusterer (HDBSCAN)
- SPEC-002-13: ValueStore

### New Dependencies

```toml
# pyproject.toml (already included in existing specs)
dependencies = [
    "mcp>=0.9.0",
    "structlog>=23.0.0",
    # ... (all others already specified)
]
```

## Alternatives Considered

### 1. Request Context for Service Access

**Alternative**: Store services in server request context instead of passing to registration functions.

```python
# Alternative pattern
@server.call_tool()
async def start_ghap(...) -> dict:
    collector = server.request_context.observation_collector
    # ...
```

**Pros:**
- No need to pass services to registration functions
- Services accessible from any tool

**Cons:**
- Less explicit dependencies (harder to see what each tool uses)
- Requires understanding request context pattern
- More magic, less clarity

**Decision:** Rejected. Explicit dependency injection is clearer and more testable.

### 2. Class-based Tools

**Alternative**: Define tools as methods on a class instead of standalone functions.

```python
class GHAPTools:
    def __init__(self, collector, persister):
        self.collector = collector
        self.persister = persister

    async def start_ghap(self, ...) -> dict:
        # Implementation
```

**Pros:**
- Encapsulation of shared state
- Familiar OOP pattern

**Cons:**
- MCP SDK uses decorator pattern on functions, not methods
- More boilerplate
- Less idiomatic for MCP

**Decision:** Rejected. Stick with MCP SDK's function-based pattern.

### 3. Single Error Type

**Alternative**: Use generic `MCPError` for all failures instead of specific subtypes.

**Pros:**
- Simpler error hierarchy
- Less code

**Cons:**
- No type-based error handling
- Clients can't distinguish validation errors from not-found errors
- Less precise error responses

**Decision:** Rejected. Specific error types provide better DX for clients.

### 4. No Retry Logic

**Alternative**: Don't retry persistence failures in resolve_ghap—just fail immediately.

**Pros:**
- Simpler implementation
- Fail fast

**Cons:**
- Transient network issues cause permanent failures
- Poor UX (agent loses work due to temporary Qdrant blip)
- Local resolution is already saved, retry is low risk

**Decision:** Rejected. Retry with backoff is more resilient and user-friendly.

## Implementation Plan

### Phase 1: Foundation (Est: 2 hours)

- [ ] Create `tools/errors.py` with custom exceptions
- [ ] Create `tools/enums.py` with domain/strategy/root cause lists and validation helpers
- [ ] Update `tools/__init__.py` to implement `register_all_tools()`
- [ ] Add basic tests for error types and enum validation

### Phase 2: GHAP Tools (Est: 4 hours)

- [ ] Implement `register_ghap_tools()` in `tools/ghap.py`
- [ ] Implement 5 GHAP tools with validation and error handling
- [ ] Add retry logic to `resolve_ghap`
- [ ] Unit tests for all GHAP tools
- [ ] Integration test for full GHAP workflow

### Phase 3: Learning Tools (Est: 4 hours)

- [ ] Implement `register_learning_tools()` in `tools/learning.py`
- [ ] Implement 5 learning tools
- [ ] Add validation for cluster_id format and value text length
- [ ] Unit tests for all learning tools
- [ ] Integration test for value formation workflow

### Phase 4: Search Tools (Est: 2 hours)

- [ ] Implement `register_search_tools()` in `tools/search.py`
- [ ] Implement `search_experiences` tool
- [ ] Add axis/domain/outcome validation
- [ ] Unit tests for search tool
- [ ] Integration test with real search

### Phase 5: Testing & Polish (Est: 3 hours)

- [ ] Comprehensive error case tests
- [ ] Boundary condition tests (empty fields, length limits)
- [ ] Performance validation tests (latency targets)
- [ ] Docstrings for all tools
- [ ] Type hint verification (mypy --strict)
- [ ] Linting (ruff)

**Total Estimate**: ~15 hours

## Open Questions

1. **GHAP check frequency**: Should we remind agents to check in on GHAP entries?
   - **Recommendation**: Out of scope for v1. Hook system (future work) will handle this.

2. **Cluster caching**: Should cluster results be cached until new experiences are added?
   - **Recommendation**: Not in v1. Clustering is fast enough (<2s) for on-demand computation.

3. **Value decay**: Should values have a lifespan or decay over time?
   - **Recommendation**: Out of scope for v1. Future enhancement.

4. **Cross-project values**: Should values be shareable across projects?
   - **Recommendation**: Out of scope for v1. Single-project for now.

## Success Criteria

Implementation is complete when:

1. ✅ All 11 tools implemented and registered
2. ✅ Input validation enforced for all parameters
3. ✅ Error handling returns MCP-compliant error format
4. ✅ Service initialization occurs once per server instance
5. ✅ GHAP workflow (start, update, resolve) works end-to-end
6. ✅ Value formation workflow (cluster, validate, store) works end-to-end
7. ✅ Search works with axis/domain/outcome filters
8. ✅ Test coverage ≥90% for tools module
9. ✅ All tests pass (unit and integration)
10. ✅ Code passes ruff linting
11. ✅ Code passes mypy --strict type checking
12. ✅ Docstrings present for all tools
13. ✅ Latency targets met in integration tests
14. ✅ Retry logic works for resolve_ghap persistence

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Service initialization fails | Server won't start | Low | Test initialization separately, fail fast with clear error |
| Persistence retry loops fail | Orphaned GHAP entries | Medium | Local state preserved, logs show retry failures clearly |
| Validation too strict | Poor UX | Low | Test with realistic inputs, adjust limits if needed |
| Tool parameter mismatch | Runtime errors | Low | Comprehensive unit tests, type checking |
| Performance misses targets | Slow tool calls | Low | Integration tests measure latency, optimize if needed |

## Conclusion

This proposal implements a clean MCP tool layer that:

- **Exposes all functionality** - GHAP tracking, learning, and search available to agents
- **Follows MCP patterns** - Decorator-based registration, async tools, error format
- **Maintains type safety** - Full type hints, mypy strict compliance
- **Handles errors gracefully** - Specific error types, helpful messages, structured logging
- **Provides resilience** - Retry logic for persistence, local GHAP safety
- **Enables testing** - Clear dependencies, mockable services, comprehensive tests

The design prioritizes **developer experience** (clear errors, validation) and **reliability** (retry logic, type safety) while keeping the implementation simple and maintainable. Tools are thin wrappers over underlying services, with validation and error handling as the primary added value.
