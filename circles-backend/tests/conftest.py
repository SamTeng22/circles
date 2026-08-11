"""Shared test fakes.

The background tasks talk to Postgres via asyncpg and to Gemini via the
embedding/extract services. These fakes stand in for the DB so the background
functions can be unit-tested without a live database or network calls.
"""
import pytest


class _Transaction:
    """No-op async context manager returned by FakeConn.transaction()."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeConn:
    """Records every SQL statement executed against it.

    fetchrow/fetch return values queued ahead of time, so a test can script the
    rows a handler will see.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []
        self._fetchrow_queue: list = []
        self._fetch_queue: list = []
        self._fetchval_queue: list = []

    def queue_fetchrow(self, *rows):
        self._fetchrow_queue.extend(rows)

    def queue_fetch(self, *result_sets):
        self._fetch_queue.extend(result_sets)

    def queue_fetchval(self, *values):
        self._fetchval_queue.extend(values)

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        return "OK"

    async def executemany(self, sql, args_seq):
        # Record one call per row so tests can assert per-row bound params.
        for args in args_seq:
            self.calls.append((sql, tuple(args)))
        return "OK"

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        return self._fetchrow_queue.pop(0) if self._fetchrow_queue else None

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self._fetch_queue.pop(0) if self._fetch_queue else []

    async def fetchval(self, sql, *args):
        self.calls.append((sql, args))
        # Defaults to 0 (an empty circle) so tests that don't care about the
        # small/large-circle branch get the simpler, sequential-scan path.
        return self._fetchval_queue.pop(0) if self._fetchval_queue else 0

    def transaction(self):
        return _Transaction()

    # --- assertion helpers -------------------------------------------------
    def statements_matching(self, needle: str) -> list[tuple[str, tuple]]:
        return [(sql, args) for sql, args in self.calls if needle in sql]

    def ran(self, needle: str) -> bool:
        return bool(self.statements_matching(needle))


class _Acquire:
    """Async context manager returned by FakePool.acquire()."""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


@pytest.fixture
def fake_conn() -> FakeConn:
    return FakeConn()


@pytest.fixture
def fake_pool(fake_conn) -> FakePool:
    return FakePool(fake_conn)
