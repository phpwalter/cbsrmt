from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

API_DATABASE_URL = os.getenv("API_DATABASE_URL") or os.getenv("DATABASE_URL", "")
DB_POOL_MIN_SIZE = int(os.getenv("CBSRMT_DB_POOL_MIN_SIZE", "1"))
DB_POOL_MAX_SIZE = int(os.getenv("CBSRMT_DB_POOL_MAX_SIZE", "10"))
DB_POOL_TIMEOUT_SECONDS = float(os.getenv("CBSRMT_DB_POOL_TIMEOUT_SECONDS", "5"))
DB_STATEMENT_TIMEOUT_MS = int(os.getenv("CBSRMT_DB_STATEMENT_TIMEOUT_MS", "5000"))
DB_LOCK_TIMEOUT_MS = int(os.getenv("CBSRMT_DB_LOCK_TIMEOUT_MS", "2000"))

_pool: ConnectionPool | None = None


def _validate_timeout(name: str, value: int) -> None:
    if value < 0:
        raise RuntimeError(f"{name} must be greater than or equal to zero")


def _configure_connection(conn) -> None:
    """Apply deterministic session settings when a pooled connection is created."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT set_config('statement_timeout', %s, false)",
            (f"{DB_STATEMENT_TIMEOUT_MS}ms",),
        )
        cur.execute(
            "SELECT set_config('lock_timeout', %s, false)",
            (f"{DB_LOCK_TIMEOUT_MS}ms",),
        )


def open_pool() -> None:
    global _pool
    if not API_DATABASE_URL:
        raise RuntimeError("API_DATABASE_URL or DATABASE_URL is required")
    if DB_POOL_MIN_SIZE < 0 or DB_POOL_MAX_SIZE < 1 or DB_POOL_MIN_SIZE > DB_POOL_MAX_SIZE:
        raise RuntimeError("invalid PostgreSQL pool size configuration")
    _validate_timeout("CBSRMT_DB_STATEMENT_TIMEOUT_MS", DB_STATEMENT_TIMEOUT_MS)
    _validate_timeout("CBSRMT_DB_LOCK_TIMEOUT_MS", DB_LOCK_TIMEOUT_MS)
    if _pool is not None:
        return

    _pool = ConnectionPool(
        conninfo=API_DATABASE_URL,
        min_size=DB_POOL_MIN_SIZE,
        max_size=DB_POOL_MAX_SIZE,
        timeout=DB_POOL_TIMEOUT_SECONDS,
        kwargs={"row_factory": dict_row, "autocommit": True},
        configure=_configure_connection,
        open=True,
    )
    _pool.wait(timeout=DB_POOL_TIMEOUT_SECONDS)


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("database pool is not initialized")
    return _pool


@contextmanager
def db_connection() -> Iterator:
    with pool().connection() as conn:
        yield conn
