"""Generate 12 GHAP entries for debugging API and network issues."""

import asyncio

from clams.embedding import NomicEmbedding
from clams.observation import (
    Domain,
    Lesson,
    ObservationCollector,
    ObservationPersister,
    OutcomeStatus,
    RootCause,
    Strategy,
)
from clams.storage.qdrant import QdrantVectorStore

# GHAP entries data - all focused on API and network debugging
GHAP_ENTRIES = [
    {
        "goal": "Fix API timeout errors occurring after exactly 30 seconds on /v1/embeddings endpoint",
        "hypothesis": "Default HTTP client timeout is too short for large embedding batches",
        "action": "Increase httpx client timeout from 30s to 120s for embedding requests",
        "prediction": "Large batches will complete successfully with longer timeout",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "confirmed",
        "result": "Extended timeout to 120s, all large batch requests now complete successfully without timeout errors",
        "lesson": {
            "what_worked": "Identified exact 30s timeout pattern, traced to httpx default timeout, increased limit resolved issue",
            "takeaway": "Set explicit timeouts based on expected operation duration, not client defaults"
        }
    },
    {
        "goal": "Debug intermittent 503 Service Unavailable errors from downstream API",
        "hypothesis": "No retry logic implemented for transient failures",
        "action": "Add exponential backoff retry with max 3 attempts for 5xx responses",
        "prediction": "Transient 503 errors will be automatically retried and succeed",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "confirmed",
        "result": "Implemented tenacity retry decorator with exponential backoff, 503 errors recovered automatically",
        "lesson": {
            "what_worked": "Retry logic with backoff handles transient service failures gracefully",
            "takeaway": "Always implement retry logic for external API calls with exponential backoff"
        }
    },
    {
        "goal": "Resolve API rate limiting causing 429 Too Many Requests errors",
        "hypothesis": "Concurrent requests exceeding API rate limit of 100 req/min",
        "action": "Implement token bucket rate limiter with 100 tokens per minute",
        "prediction": "Rate limiter will prevent 429 errors by throttling requests",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "falsified",
        "result": "Rate limiter reduced 429s but didn't eliminate them entirely",
        "surprise": "Still hitting rate limits despite throttling to documented limit",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "API has separate per-endpoint limits not documented - /search has 20 req/min while /embed has 100 req/min"
        },
        "lesson": {
            "what_worked": "Added per-endpoint rate limiting based on response headers, eliminated all 429s",
            "takeaway": "Don't trust documented rate limits - read actual limit headers from responses"
        }
    },
    {
        "goal": "Fix connection pool exhaustion causing 'Too many open files' errors",
        "hypothesis": "Connection pool size is too small for concurrent request volume",
        "action": "Increase httpx connection pool from default 10 to 100 connections",
        "prediction": "Pool exhaustion errors will stop with larger pool",
        "strategy": Strategy.DIVIDE_AND_CONQUER,
        "outcome": "falsified",
        "result": "Larger pool delayed the problem but errors still occurred under load",
        "surprise": "File descriptor exhaustion persisted even with larger pool",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Connections were leaking due to missing connection cleanup in error paths - not a pool size issue"
        },
        "lesson": {
            "what_worked": "Added explicit connection close in finally blocks, leak stopped completely",
            "takeaway": "Connection leaks look like pool exhaustion - check cleanup in error paths first"
        }
    },
    {
        "goal": "Debug SSL certificate verification failures on production API",
        "hypothesis": "Certificate expired or hostname mismatch in production environment",
        "action": "Check certificate validity and common name against actual hostname",
        "prediction": "Will find expired cert or CN mismatch causing verification failure",
        "strategy": Strategy.READ_THE_ERROR,
        "outcome": "confirmed",
        "result": "Production cert CN was '*.api.example.com' but we were calling 'api-v2.example.com'",
        "lesson": {
            "what_worked": "Examined SSLError details, found CN mismatch, updated hostname to match wildcard pattern",
            "takeaway": "SSL errors often indicate hostname/cert mismatch - verify CN matches request hostname"
        }
    },
    {
        "goal": "Resolve DNS resolution timeouts causing intermittent connection failures",
        "hypothesis": "DNS server is slow or unreliable causing timeout on name resolution",
        "action": "Add DNS caching with aiodns to avoid repeated lookups",
        "prediction": "DNS cache will eliminate timeout by reusing resolved addresses",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "confirmed",
        "result": "Implemented aiodns with 5-minute TTL cache, DNS timeouts eliminated completely",
        "lesson": {
            "what_worked": "DNS caching reduced resolution calls by 95%, all timeouts disappeared",
            "takeaway": "DNS resolution is often overlooked bottleneck - implement caching for frequently accessed hosts"
        }
    },
    {
        "goal": "Fix API returning 401 Unauthorized despite valid authentication token",
        "hypothesis": "Token is expired and needs refresh before request",
        "action": "Add token expiration check and automatic refresh logic",
        "prediction": "401 errors will stop after implementing token refresh",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "falsified",
        "result": "Token refresh implemented but 401s persisted",
        "surprise": "Fresh tokens also getting rejected with 401",
        "root_cause": {
            "category": "misunderstanding",
            "description": "API expects 'Authorization: Bearer <token>' but we were sending 'Authorization: <token>' without Bearer prefix"
        },
        "lesson": {
            "what_worked": "Checked request headers against API docs, added 'Bearer' prefix, auth works now",
            "takeaway": "Authorization header format matters - verify exact format required by API"
        }
    },
    {
        "goal": "Debug slow API response times averaging 5+ seconds per request",
        "hypothesis": "Server-side processing is slow, nothing we can optimize client-side",
        "action": "Add request timing instrumentation to identify bottlenecks",
        "prediction": "Will confirm server processing is the bottleneck",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "falsified",
        "result": "Timing showed 4.8s in connection establishment, only 0.2s in processing",
        "surprise": "Server was fast, connection setup was the bottleneck",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Connection pooling was disabled so every request did full TLS handshake - extremely slow"
        },
        "lesson": {
            "what_worked": "Enabled connection pooling with keep-alive, response time dropped to 200ms",
            "takeaway": "Profile request lifecycle - connection overhead often exceeds processing time"
        }
    },
    {
        "goal": "Resolve API returning stale data despite cache headers saying no-cache",
        "hypothesis": "Intermediate proxy is caching despite no-cache directive",
        "action": "Add unique query parameter to bust any intermediate caches",
        "prediction": "Cache-busting param will force fresh data on every request",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "confirmed",
        "result": "Added timestamp query param, all responses now fresh",
        "lesson": {
            "what_worked": "Query param bypassed aggressive proxy caching we couldn't control",
            "takeaway": "When cache headers fail, query param cache-busting forces fresh responses"
        }
    },
    {
        "goal": "Fix chunked transfer encoding causing incomplete response parsing",
        "hypothesis": "HTTP client not properly handling chunked responses",
        "action": "Ensure client fully reads response body before processing",
        "prediction": "Reading full body will prevent truncated response errors",
        "strategy": Strategy.READ_THE_ERROR,
        "outcome": "confirmed",
        "result": "Added explicit await response.aread() before json parsing, truncation stopped",
        "lesson": {
            "what_worked": "Forcing complete body read before parsing handled chunked encoding correctly",
            "takeaway": "Async HTTP clients need explicit body read for chunked responses"
        }
    },
    {
        "goal": "Debug API POST requests failing with 411 Length Required error",
        "hypothesis": "Content-Length header is missing from POST request",
        "action": "Explicitly set Content-Length header based on request body size",
        "prediction": "Adding Content-Length will satisfy server requirements",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "confirmed",
        "result": "httpx wasn't auto-setting Content-Length for streaming bodies, explicit header fixed it",
        "lesson": {
            "what_worked": "Manual Content-Length calculation for streaming request bodies resolved 411 errors",
            "takeaway": "Streaming request bodies may need explicit Content-Length header"
        }
    },
    {
        "goal": "Resolve API WebSocket connection dropping after exactly 60 seconds",
        "hypothesis": "Server-side idle timeout disconnecting inactive connections",
        "action": "Implement ping/pong heartbeat every 30 seconds to keep connection alive",
        "prediction": "Heartbeat will prevent idle timeout disconnections",
        "strategy": Strategy.DIVIDE_AND_CONQUER,
        "outcome": "confirmed",
        "result": "Added 30s ping interval, connections now stable for hours",
        "lesson": {
            "what_worked": "Regular heartbeat prevents idle timeout on long-lived WebSocket connections",
            "takeaway": "WebSocket connections need periodic activity to avoid idle timeouts"
        }
    },
]


async def generate_entries() -> None:
    """Generate all GHAP entries."""
    # Initialize services
    embedding = NomicEmbedding()
    vector_store = QdrantVectorStore()

    collector = ObservationCollector()
    persister = ObservationPersister(vector_store=vector_store, embedding_service=embedding)

    print(f"Generating {len(GHAP_ENTRIES)} GHAP entries for API and network debugging...")

    for i, entry_data in enumerate(GHAP_ENTRIES, 1):
        try:
            # Start GHAP
            entry = await collector.create_ghap(
                domain=Domain.DEBUGGING,
                strategy=entry_data["strategy"],
                goal=entry_data["goal"],
                hypothesis=entry_data["hypothesis"],
                action=entry_data["action"],
                prediction=entry_data["prediction"],
            )

            print(f"[{i}/12] Created GHAP {entry.id}: {entry_data['goal'][:70]}...")

            # Prepare outcome data
            outcome_status = OutcomeStatus(entry_data["outcome"])
            result = entry_data["result"]
            surprise = entry_data.get("surprise")

            # Root cause for falsified
            root_cause_model = None
            if entry_data.get("root_cause"):
                root_cause_model = RootCause(
                    category=entry_data["root_cause"]["category"],
                    description=entry_data["root_cause"]["description"],
                )

            # Lesson
            lesson_model = None
            if entry_data.get("lesson"):
                lesson_model = Lesson(
                    what_worked=entry_data["lesson"]["what_worked"],
                    takeaway=entry_data["lesson"].get("takeaway"),
                )

            # Resolve GHAP
            resolved = await collector.resolve_ghap(
                status=outcome_status,
                result=result,
                surprise=surprise,
                root_cause=root_cause_model,
                lesson=lesson_model,
            )

            # Persist to vector store
            await persister.persist(resolved)

            print(f"       Resolved as {outcome_status.value} and persisted")

            # Small delay to avoid overwhelming the system
            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"ERROR on entry {i}: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\nSuccessfully generated {len(GHAP_ENTRIES)} GHAP entries!")
    print("All entries focused on: API debugging, network issues, timeouts, rate limiting, SSL/TLS, connection pooling")


if __name__ == "__main__":
    asyncio.run(generate_entries())
