"""Generate 12 GHAP entries for database and data layer debugging theme."""

import asyncio
import random
from datetime import datetime

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
from clams.embedding import NomicEmbedding


# GHAP entries data - all focused on database and data layer debugging
GHAP_ENTRIES = [
    {
        "goal": "Fix N+1 query problem causing severe API slowdown",
        "hypothesis": "ORM lazy loading triggers individual queries for each related object",
        "action": "Add eager loading with select_related() for foreign keys",
        "prediction": "Query count will drop from 1000+ to under 10 per request",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "confirmed",
        "result": "Added select_related('user', 'category') - queries dropped from 1203 to 3, response time from 8s to 120ms",
        "lesson": {
            "what_worked": "Django debug toolbar revealed N+1, select_related eliminated extra queries",
            "takeaway": "Always use select_related() or prefetch_related() when accessing foreign key relationships in loops"
        }
    },
    {
        "goal": "Debug database connection pool exhaustion under moderate load",
        "hypothesis": "Connections not being released back to pool after transactions",
        "action": "Audit all database access points for missing connection cleanup",
        "prediction": "Will find code paths that don't close connections properly",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "confirmed",
        "result": "Found 3 exception handlers that failed to release connections, added proper cleanup",
        "lesson": {
            "what_worked": "Connection pool monitoring showed gradual exhaustion, traced to exception paths",
            "takeaway": "Always use context managers or try/finally blocks to guarantee connection cleanup, especially in error paths"
        }
    },
    {
        "goal": "Resolve transaction deadlocks occurring during concurrent updates",
        "hypothesis": "Two transactions acquiring row locks in different orders",
        "action": "Standardize lock acquisition order by primary key across all update operations",
        "prediction": "Deadlocks will cease after enforcing consistent ordering",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "falsified",
        "result": "Deadlocks persisted even with lock ordering",
        "surprise": "Lock ordering didn't resolve the issue as expected",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Actual cause was SELECT FOR UPDATE acquiring gap locks in different orders based on WHERE clause order - needed to order by PK in the SELECT itself"
        },
        "lesson": {
            "what_worked": "Added ORDER BY id to all SELECT FOR UPDATE queries, deadlocks eliminated",
            "takeaway": "Gap locks from range queries can deadlock - always use ORDER BY in SELECT FOR UPDATE to ensure consistent lock ordering"
        }
    },
    {
        "goal": "Fix intermittent query timeout errors on report generation",
        "hypothesis": "Missing database indexes causing full table scans",
        "action": "Add indexes on columns used in WHERE clauses",
        "prediction": "Query execution time will drop below timeout threshold",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "confirmed",
        "result": "Added composite index on (created_at, status, user_id), query time dropped from 45s to 0.3s",
        "lesson": {
            "what_worked": "EXPLAIN ANALYZE showed sequential scan, composite index enabled index-only scan",
            "takeaway": "Always check query plans with EXPLAIN before adding indexes - composite indexes for multi-column filters"
        }
    },
    {
        "goal": "Debug data corruption in cache layer causing inconsistent reads",
        "hypothesis": "Race condition between cache invalidation and update",
        "action": "Add distributed lock around cache write operations",
        "prediction": "Corruption will stop after serializing cache updates",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "falsified",
        "result": "Lock didn't prevent corruption, issue persisted",
        "surprise": "Distributed lock had no effect on data consistency",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Problem was actually stale data from database read replicas with replication lag - cache was correct but source data was stale"
        },
        "lesson": {
            "what_worked": "Added read-your-writes consistency by routing updates to primary, replication lag monitoring",
            "takeaway": "Consider replication lag when debugging cache issues - stale replica reads can appear as cache problems"
        }
    },
    {
        "goal": "Resolve connection leak causing database to refuse new connections",
        "hypothesis": "Abandoned connections not being cleaned up by pool timeout",
        "action": "Reduce connection max_idle_time to force faster recycling",
        "prediction": "Connection count will stabilize below pool limit",
        "strategy": Strategy.DIVIDE_AND_CONQUER,
        "outcome": "confirmed",
        "result": "Set max_idle_time from 3600s to 300s, connection leaks disappeared",
        "lesson": {
            "what_worked": "Aggressive timeout recycled leaked connections before pool exhaustion",
            "takeaway": "Set conservative connection timeouts to compensate for application bugs that leak connections"
        }
    },
    {
        "goal": "Fix slow bulk insert operation taking hours for large datasets",
        "hypothesis": "Individual INSERT statements instead of bulk operation",
        "action": "Replace loop of inserts with single bulk_create() call",
        "prediction": "Insert time will drop dramatically with batched operation",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "confirmed",
        "result": "Changed to bulk_create(batch_size=1000), time dropped from 3h to 4min for 100k rows",
        "lesson": {
            "what_worked": "Bulk insert with batching amortized transaction overhead across many rows",
            "takeaway": "Use bulk operations for large datasets - batch_size prevents memory bloat and transaction size issues"
        }
    },
    {
        "goal": "Debug query returning incorrect results after schema migration",
        "hypothesis": "Column type mismatch causing silent conversion errors",
        "action": "Audit query for implicit type conversions and add explicit casts",
        "prediction": "Explicit casts will prevent conversion issues",
        "strategy": Strategy.READ_THE_ERROR,
        "outcome": "falsified",
        "result": "Type conversions were correct, results still wrong",
        "surprise": "No type conversion errors, but results still incorrect",
        "root_cause": {
            "category": "misunderstanding",
            "description": "Migration changed column from nullable to NOT NULL with default value, existing NULL rows got default value breaking business logic"
        },
        "lesson": {
            "what_worked": "Compared pre/post migration data, found NULL -> default conversions, backfilled with correct values",
            "takeaway": "Validate data integrity after schema migrations, especially NULL handling changes"
        }
    },
    {
        "goal": "Resolve foreign key constraint violation in production",
        "hypothesis": "Race condition allowing parent deletion before child cleanup",
        "action": "Use database transaction to ensure atomic parent-child deletion",
        "prediction": "Constraint violations will stop with transactional delete",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "confirmed",
        "result": "Wrapped delete operations in transaction, violations eliminated",
        "lesson": {
            "what_worked": "Transaction isolation prevented race between parent delete and child query",
            "takeaway": "Always use transactions for multi-table operations with referential integrity requirements"
        }
    },
    {
        "goal": "Fix ORM query generating inefficient SQL with subqueries",
        "hypothesis": "Complex queryset chaining creating nested subqueries",
        "action": "Simplify queryset by combining filters into single query",
        "prediction": "Generated SQL will be simpler and faster",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "confirmed",
        "result": "Replaced 3-level nested subquery with JOIN, execution time from 12s to 0.8s",
        "lesson": {
            "what_worked": "Raw SQL analysis showed unnecessary nesting, refactored to use annotate() with joins",
            "takeaway": "Review generated SQL for complex querysets - sometimes manual query construction is clearer and faster"
        }
    },
    {
        "goal": "Debug database connection 'too many clients' error during load test",
        "hypothesis": "Connection pool size exceeds database max_connections limit",
        "action": "Reduce application pool size to stay under database limit",
        "prediction": "Error will disappear with smaller pool",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "falsified",
        "result": "Pool size was already under limit, error persisted",
        "surprise": "Pool configuration was correct but errors continued",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Multiple application instances each with their own pools - total connections across all instances exceeded limit"
        },
        "lesson": {
            "what_worked": "Calculated total as (pool_size × instance_count), set per-instance pool = max_connections / instance_count",
            "takeaway": "Connection pool limits must account for all application instances, not just one"
        }
    },
    {
        "goal": "Resolve transaction isolation issue causing lost updates",
        "hypothesis": "READ COMMITTED allowing race condition in read-modify-write",
        "action": "Change isolation level to REPEATABLE READ for update operations",
        "prediction": "Lost updates will stop with stricter isolation",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "confirmed",
        "result": "Set REPEATABLE READ for critical transactions, lost updates eliminated",
        "lesson": {
            "what_worked": "Higher isolation level prevented phantom reads during read-modify-write cycles",
            "takeaway": "Use REPEATABLE READ or SERIALIZABLE for read-modify-write patterns to prevent lost updates"
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

    print(f"Generating {len(GHAP_ENTRIES)} GHAP entries for database/data layer debugging...")

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

            print(f"[{i}/{len(GHAP_ENTRIES)}] Created GHAP {entry.id}: {entry_data['goal'][:60]}...")

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
    print("All entries focused on: database debugging, N+1 queries, connection management, deadlocks, query optimization")


if __name__ == "__main__":
    asyncio.run(generate_entries())
