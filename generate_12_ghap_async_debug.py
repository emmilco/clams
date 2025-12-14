"""Generate 12 GHAP entries for async/concurrent debugging theme."""

import asyncio
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


# GHAP entries data - focused on async/concurrent debugging
GHAP_ENTRIES = [
    {
        "goal": "Fix race condition in user session handler causing data corruption",
        "hypothesis": "Multiple requests updating session simultaneously without proper locking",
        "action": "Add mutex around session write operations",
        "prediction": "Session corruption will stop after adding lock",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "confirmed",
        "result": "Added asyncio.Lock around session writes, corruption stopped completely in stress testing",
        "lesson": {
            "what_worked": "Identified race condition through concurrent request simulation, lock eliminated all corruption",
            "takeaway": "Always protect shared mutable state in async handlers with explicit locking primitives"
        }
    },
    {
        "goal": "Resolve deadlock in database connection pool",
        "hypothesis": "Two threads acquiring locks in opposite order",
        "action": "Establish consistent lock ordering across all database operations",
        "prediction": "Deadlocks will cease after enforcing lock hierarchy",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "confirmed",
        "result": "Implemented lock ordering by connection ID, no deadlocks in 48hr stress test",
        "lesson": {
            "what_worked": "Thread dump analysis revealed lock inversion, consistent ordering resolved it",
            "takeaway": "Lock ordering protocol prevents deadlocks in multi-resource scenarios"
        }
    },
    {
        "goal": "Fix intermittent timeout errors in async API calls",
        "hypothesis": "Event loop blocking during I/O operations",
        "action": "Offload CPU-intensive work to thread pool executor",
        "prediction": "Timeouts will disappear after moving blocking work off event loop",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "falsified",
        "result": "Timeouts persisted after offloading CPU work",
        "surprise": "CPU work was not the bottleneck, timeouts continued at same rate",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Actual cause was connection pool exhaustion from not releasing connections in exception paths"
        },
        "lesson": {
            "what_worked": "Added connection tracking revealed leak in error handlers",
            "takeaway": "Profile before optimizing - assumed CPU bottleneck was actually resource leak"
        }
    },
    {
        "goal": "Debug connection pool exhaustion under load",
        "hypothesis": "Connections not being returned to pool after use",
        "action": "Add proper try/finally blocks to ensure connection release",
        "prediction": "Pool exhaustion will stop after guaranteed cleanup",
        "strategy": Strategy.READ_THE_ERROR,
        "outcome": "confirmed",
        "result": "Added context managers for all connection usage, pool exhaustion eliminated",
        "lesson": {
            "what_worked": "Pool monitoring showed connections never freed, context managers fixed it",
            "takeaway": "Always use context managers for resource cleanup in async code"
        }
    },
    {
        "goal": "Fix async queue blocking indefinitely in worker pool",
        "hypothesis": "Producer/consumer count mismatch causing queue to never drain",
        "action": "Add queue size monitoring and timeout on get operations",
        "prediction": "Will identify which side is stalling the queue",
        "strategy": Strategy.DIVIDE_AND_CONQUER,
        "outcome": "falsified",
        "result": "Monitoring showed queue size stayed at zero, not a count mismatch",
        "surprise": "Queue was empty but consumers still blocked waiting",
        "root_cause": {
            "category": "misunderstanding",
            "description": "Used queue.get() instead of queue.get_nowait() inside a cancelled task, blocking forever"
        },
        "lesson": {
            "what_worked": "Task cancellation testing revealed blocking get() in cancelled context",
            "takeaway": "Use get_nowait() or get(timeout=) in cancellable async contexts"
        }
    },
    {
        "goal": "Resolve sporadic task cancellation errors in async workers",
        "hypothesis": "Tasks being cancelled without proper cleanup",
        "action": "Add CancelledError handling and cleanup in all async tasks",
        "prediction": "Cancellation errors will stop propagating after proper handling",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "confirmed",
        "result": "Added try/except CancelledError with cleanup, no more unhandled exceptions",
        "lesson": {
            "what_worked": "Wrapped task bodies with cancellation cleanup, errors disappeared",
            "takeaway": "Always handle CancelledError explicitly in long-running async tasks"
        }
    },
    {
        "goal": "Fix periodic event loop freeze in async server",
        "hypothesis": "Blocking I/O call sneaking into async handler",
        "action": "Use loop.run_in_executor for all file I/O",
        "prediction": "Freezes will stop after moving file I/O to executor",
        "strategy": Strategy.SYSTEMATIC_ELIMINATION,
        "outcome": "falsified",
        "result": "Freezes continued even after moving file I/O",
        "surprise": "File I/O wasn't the culprit, freezes persisted",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Actual cause was DNS resolution blocking - used sync getaddrinfo instead of async"
        },
        "lesson": {
            "what_worked": "Event loop instrumentation showed DNS calls blocking, switched to aiodns",
            "takeaway": "DNS resolution is blocking by default in Python - use async DNS library"
        }
    },
    {
        "goal": "Debug task leak causing unbounded memory growth",
        "hypothesis": "Tasks being created but never awaited",
        "action": "Enable asyncio debug mode and check for unawaited coroutine warnings",
        "prediction": "Debug mode will show which tasks are not being awaited",
        "strategy": Strategy.READ_THE_ERROR,
        "outcome": "confirmed",
        "result": "Found 15 fire-and-forget tasks never awaited, collected them properly",
        "lesson": {
            "what_worked": "asyncio.run(debug=True) revealed all unawaited coroutines",
            "takeaway": "Always await or explicitly create_task for background work"
        }
    },
    {
        "goal": "Resolve thundering herd on shared async resource",
        "hypothesis": "All waiting tasks rushing to acquire resource simultaneously",
        "action": "Add jittered backoff to resource acquisition",
        "prediction": "Request distribution will smooth out with jitter",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "falsified",
        "result": "Jitter didn't help, herd behavior persisted",
        "surprise": "Backoff had no effect on spike patterns",
        "root_cause": {
            "category": "wrong_hypothesis",
            "description": "Problem was actually semaphore release waking all waiters at once, not retry timing"
        },
        "lesson": {
            "what_worked": "Switched to queue-based fair acquisition instead of semaphore",
            "takeaway": "Semaphores can cause thundering herd - use queues for fair resource distribution"
        }
    },
    {
        "goal": "Debug async lock held across await causing deadlock",
        "hypothesis": "Lock being held while awaiting another lock-protected operation",
        "action": "Release lock before awaiting nested operation",
        "prediction": "Deadlock will disappear after releasing lock early",
        "strategy": Strategy.DIVIDE_AND_CONQUER,
        "outcome": "confirmed",
        "result": "Released lock before nested call, deadlock eliminated",
        "lesson": {
            "what_worked": "Lock ordering analysis showed circular dependency, early release broke cycle",
            "takeaway": "Never hold lock while calling code that might acquire the same lock"
        }
    },
    {
        "goal": "Fix race condition in async flag check-and-set operation",
        "hypothesis": "Flag being checked and set in separate operations",
        "action": "Use atomic compare-and-swap for flag operations",
        "prediction": "Race will disappear with atomic flag updates",
        "strategy": Strategy.ROOT_CAUSE_ANALYSIS,
        "outcome": "confirmed",
        "result": "Implemented lock-protected check-and-set, race eliminated",
        "lesson": {
            "what_worked": "Lock around check+set makes it atomic, prevents race",
            "takeaway": "Check-then-act patterns need atomicity - use locks or atomic primitives"
        }
    },
    {
        "goal": "Resolve async timeout not working in nested await chain",
        "hypothesis": "wait_for timeout not propagating to inner awaits",
        "action": "Add timeout parameter to inner async calls",
        "prediction": "Timeout will work after passing to inner calls",
        "strategy": Strategy.CHECK_ASSUMPTIONS,
        "outcome": "falsified",
        "result": "Inner calls already timeout correctly with wait_for",
        "surprise": "wait_for cancels entire task tree, timeout propagates automatically",
        "root_cause": {
            "category": "misunderstanding",
            "description": "Thought timeout needed manual propagation, but wait_for cancels the whole coroutine tree"
        },
        "lesson": {
            "what_worked": "wait_for handles nested timeouts automatically via cancellation",
            "takeaway": "asyncio.wait_for propagates timeout through entire coroutine chain"
        }
    }
]


async def generate_entries() -> None:
    """Generate all GHAP entries."""
    # Initialize services
    embedding = NomicEmbedding()
    vector_store = QdrantVectorStore()

    collector = ObservationCollector()
    persister = ObservationPersister(vector_store=vector_store, embedding_service=embedding)

    print(f"Generating {len(GHAP_ENTRIES)} GHAP entries for async/concurrent debugging...")

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
    print("All entries focused on: async/concurrent debugging, race conditions, deadlocks, timing issues")


if __name__ == "__main__":
    asyncio.run(generate_entries())
