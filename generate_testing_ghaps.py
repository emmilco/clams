#!/usr/bin/env python
"""Generate 12 GHAP entries focused on debugging testing and CI/CD issues."""

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


async def generate_ghaps():
    """Generate 12 GHAP entries for testing/CI debugging scenarios."""

    # Initialize services
    embedding = NomicEmbedding()
    vector_store = QdrantVectorStore()
    collector = ObservationCollector()
    persister = ObservationPersister(vector_store=vector_store, embedding_service=embedding)

    # GHAP 1: Flaky test with race condition (confirmed)
    entry1 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.ROOT_CAUSE_ANALYSIS,
        goal="Fix intermittent failure in test_session_cleanup",
        hypothesis="Test fails because cleanup worker thread doesn't finish before assertions run",
        action="Add thread synchronization with join() and verify cleanup completion",
        prediction="Test will pass consistently when cleanup thread is properly synchronized"
    )
    resolved1 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Added threading.Event to signal cleanup completion, test now passes 100/100 runs",
        lesson=Lesson(
            what_worked="Using Event.wait(timeout=5) to ensure cleanup finishes before assertions",
            takeaway="Always synchronize with background threads in tests using events or joins"
        )
    )
    await persister.persist(resolved1)
    print(f"✓ Generated GHAP 1: {entry1.id}")

    # GHAP 2: Mock not being called (falsified)
    entry2 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.CHECK_ASSUMPTIONS,
        goal="Fix test_api_call failure where mock never gets called",
        hypothesis="Mock patch path is incorrect, should be where it's used not defined",
        action="Change @patch('module.api') to @patch('tested_module.api')",
        prediction="Mock will be called when patched at import location"
    )
    resolved2 = await collector.resolve_ghap(
        status=OutcomeStatus.FALSIFIED,
        result="Patch path was correct. Real issue was test calling old cached instance before mock was set up.",
        surprise="Mock path was fine, but instance caching bypassed the mock entirely",
        root_cause=RootCause(
            category="wrong-assumption",
            description="Focused on patch location when real issue was singleton cache loaded before test"
        ),
        lesson=Lesson(
            what_worked="Clear singleton cache in setUp() before each test",
            takeaway="Check for cached instances and singletons that bypass mocks"
        )
    )
    await persister.persist(resolved2)
    print(f"✓ Generated GHAP 2: {entry2.id}")

    # GHAP 3: CI timeout (confirmed)
    entry3 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.DIVIDE_AND_CONQUER,
        goal="Debug CI pipeline timeout in test stage after 30 minutes",
        hypothesis="Long-running integration tests consuming all time budget",
        action="Run tests locally with --durations=10 to find slowest tests",
        prediction="Will find 2-3 tests taking over 5 minutes each"
    )
    resolved3 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Found test_database_migration taking 18 minutes. Split into unit tests with mocked DB.",
        lesson=Lesson(
            what_worked="pytest --durations=10 revealed the bottleneck immediately",
            takeaway="Profile test duration regularly, set --timeout per test to catch slow tests early"
        )
    )
    await persister.persist(resolved3)
    print(f"✓ Generated GHAP 3: {entry3.id}")

    # GHAP 4: Environment variable missing in CI (confirmed)
    entry4 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.READ_THE_ERROR,
        goal="Fix KeyError: DATABASE_URL in CI but works locally",
        hypothesis="CI environment missing required environment variable",
        action="Add DATABASE_URL to CI secrets and check .env.example is complete",
        prediction="Setting environment variable in CI will fix the failure"
    )
    resolved4 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Added DATABASE_URL to GitHub Actions secrets, updated .env.example with all required vars",
        lesson=Lesson(
            what_worked="Checking .env.example against actual code usage to find missing vars",
            takeaway="Maintain .env.example with all required variables, validate in CI setup"
        )
    )
    await persister.persist(resolved4)
    print(f"✓ Generated GHAP 4: {entry4.id}")

    # GHAP 5: Test isolation issue (falsified)
    entry5 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test_user_creation passing alone but failing in full suite",
        hypothesis="Previous test modifying shared database state",
        action="Add database rollback in tearDown for all tests",
        prediction="Proper cleanup will make test pass in suite"
    )
    resolved5 = await collector.resolve_ghap(
        status=OutcomeStatus.FALSIFIED,
        result="Database cleanup was fine. Issue was module-level import executing code that created test user before tests ran.",
        surprise="Test isolation issue was at import time, not during test execution",
        root_cause=RootCause(
            category="wrong-scope",
            description="Looked at test cleanup when issue was module import side effects"
        ),
        lesson=Lesson(
            what_worked="Moving code from module level to test fixtures eliminated the import-time side effect",
            takeaway="Avoid code execution at module import - use fixtures or setUp instead"
        )
    )
    await persister.persist(resolved5)
    print(f"✓ Generated GHAP 5: {entry5.id}")

    # GHAP 6: Fixture dependency order (confirmed)
    entry6 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.ROOT_CAUSE_ANALYSIS,
        goal="Fix pytest fixture dependency causing test_api to fail",
        hypothesis="Fixtures executing in wrong order, database not ready when API starts",
        action="Add explicit fixture dependencies: api_client depends on db_session",
        prediction="Correct dependency order will ensure database is ready"
    )
    resolved6 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Changed @pytest.fixture to take db_session parameter, pytest now ensures correct order",
        lesson=Lesson(
            what_worked="Using fixture parameters to declare dependencies explicitly",
            takeaway="Declare fixture dependencies via parameters, don't rely on implicit ordering"
        )
    )
    await persister.persist(resolved6)
    print(f"✓ Generated GHAP 6: {entry6.id}")

    # GHAP 7: Docker layer caching in CI (confirmed)
    entry7 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.CHECK_ASSUMPTIONS,
        goal="Speed up CI build stage taking 15 minutes per run",
        hypothesis="Docker layers rebuilding unnecessarily, need better caching",
        action="Reorder Dockerfile to copy requirements before code, use buildx cache",
        prediction="Layer caching will reduce build time to 2-3 minutes"
    )
    resolved7 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Reordered Dockerfile, added GitHub Actions cache, build now 3 minutes instead of 15",
        lesson=Lesson(
            what_worked="Copy requirements.txt first, then COPY . later so code changes don't invalidate dependency layer",
            takeaway="Optimize Dockerfile layer order: least-changing files first, most-changing last"
        )
    )
    await persister.persist(resolved7)
    print(f"✓ Generated GHAP 7: {entry7.id}")

    # GHAP 8: Parametrized test failure (falsified)
    entry8 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.DIVIDE_AND_CONQUER,
        goal="Fix test_validation[case3] failing while other cases pass",
        hypothesis="Test case 3 has bad input data in parametrize",
        action="Review parametrize inputs for case 3, fix test data",
        prediction="Correcting test data will make case 3 pass"
    )
    resolved8 = await collector.resolve_ghap(
        status=OutcomeStatus.FALSIFIED,
        result="Test data was correct. Bug was in production code - edge case not handled for negative numbers.",
        surprise="Test was correctly catching a real bug, not a test issue",
        root_cause=RootCause(
            category="wrong-assumption",
            description="Assumed test was wrong when it was correctly identifying production bug"
        ),
        lesson=Lesson(
            what_worked="Stepping through test case revealed production code assumption about positive inputs",
            takeaway="When one parametrized case fails, it may be finding a real bug, not test issue"
        )
    )
    await persister.persist(resolved8)
    print(f"✓ Generated GHAP 8: {entry8.id}")

    # GHAP 9: Monkeypatch datetime (confirmed)
    entry9 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.SYSTEMATIC_ELIMINATION,
        goal="Fix test_expiration failing intermittently based on time of day",
        hypothesis="Test comparing against real time, need to freeze time",
        action="Use freezegun or monkeypatch datetime.now() to control time",
        prediction="Fixed time will make test deterministic"
    )
    resolved9 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Added @freeze_time('2024-01-15 10:00:00'), test now passes at any time of day",
        lesson=Lesson(
            what_worked="freezegun library for simple time freezing in tests",
            takeaway="Never rely on real time in tests - use time mocking for determinism"
        )
    )
    await persister.persist(resolved9)
    print(f"✓ Generated GHAP 9: {entry9.id}")

    # GHAP 10: CI matrix strategy (confirmed)
    entry10 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.READ_THE_ERROR,
        goal="Fix tests passing on Python 3.11 but failing on 3.9 in CI matrix",
        hypothesis="Code using Python 3.10+ features not available in 3.9",
        action="Review error trace for syntax/feature usage, add compatibility code",
        prediction="Removing 3.10+ features will make tests pass on 3.9"
    )
    resolved10 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Found match statement (3.10+) and union types (3.10+). Replaced with if/elif and Union[].",
        lesson=Lesson(
            what_worked="Error trace showed SyntaxError pointing directly to match statement",
            takeaway="Check minimum Python version in CI matrix matches project requirements"
        )
    )
    await persister.persist(resolved10)
    print(f"✓ Generated GHAP 10: {entry10.id}")

    # GHAP 11: Coverage threshold failure (falsified)
    entry11 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.CHECK_ASSUMPTIONS,
        goal="Fix CI failing on coverage threshold (85% required, got 83%)",
        hypothesis="New code not tested, need to add tests for recent changes",
        action="Run coverage report locally, identify untested code paths",
        prediction="Adding tests for untested code will raise coverage above 85%"
    )
    resolved11 = await collector.resolve_ghap(
        status=OutcomeStatus.FALSIFIED,
        result="Coverage was actually 86% locally. CI failure was because it included migration files. Fixed .coveragerc exclude.",
        surprise="Coverage was passing threshold, but CI included files it shouldn't",
        root_cause=RootCause(
            category="wrong-scope",
            description="Assumed missing tests when issue was coverage configuration including wrong files"
        ),
        lesson=Lesson(
            what_worked="Comparing local coverage output with CI to spot the difference in included files",
            takeaway="Ensure .coveragerc omit patterns match between local and CI environments"
        )
    )
    await persister.persist(resolved11)
    print(f"✓ Generated GHAP 11: {entry11.id}")

    # GHAP 12: Resource cleanup in tests (confirmed)
    entry12 = await collector.create_ghap(
        domain=Domain.DEBUGGING,
        strategy=Strategy.ROOT_CAUSE_ANALYSIS,
        goal="Fix ResourceWarning: unclosed file in test suite",
        hypothesis="Test opening files without closing them in all code paths",
        action="Add context managers (with statements) for all file operations",
        prediction="Using context managers will eliminate resource warnings"
    )
    resolved12 = await collector.resolve_ghap(
        status=OutcomeStatus.CONFIRMED,
        result="Found 5 file operations without context managers. Changed to 'with open()' pattern.",
        lesson=Lesson(
            what_worked="pytest -Werror::ResourceWarning to make warnings fail tests, grep for 'open(' to find all cases",
            takeaway="Always use context managers for resources (files, connections, locks)"
        )
    )
    await persister.persist(resolved12)
    print(f"✓ Generated GHAP 12: {entry12.id}")

    print("\n✅ Successfully generated 12 GHAP entries!")
    print("   - 8 confirmed outcomes")
    print("   - 4 falsified outcomes")


if __name__ == "__main__":
    asyncio.run(generate_ghaps())
