#!/usr/bin/env python3
"""Apply ordered PostgreSQL migrations with checksum verification.

Rules:
- filenames are applied in lexical order;
- an unapplied migration is executed once and recorded;
- an already-applied migration must have the same SHA-256 checksum;
- checksum drift is a hard failure.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

LEDGER_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS governance;
CREATE TABLE IF NOT EXISTS governance.schema_migrations (
    migration_name text PRIMARY KEY,
    migration_checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by text NOT NULL DEFAULT current_user,
    CONSTRAINT schema_migrations_name_ck CHECK (btrim(migration_name) <> ''),
    CONSTRAINT schema_migrations_checksum_ck CHECK (migration_checksum ~ '^[0-9a-f]{64}$')
);
"""


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required; install requirements.txt") from exc
    return psycopg.connect(database_url)


def applied_migrations(cur) -> dict[str, str]:
    cur.execute(LEDGER_SCHEMA_SQL)
    cur.execute(
        "SELECT migration_name, migration_checksum FROM governance.schema_migrations"
    )
    return {name: checksum for name, checksum in cur.fetchall()}


def apply(database_url: str, directory: Path) -> tuple[int, int]:
    migrations = sorted(directory.glob("*.sql"))
    if not migrations:
        raise RuntimeError(f"no migrations found in {directory}")

    applied_count = 0
    verified_count = 0

    with connect(database_url) as conn:
        with conn.cursor() as cur:
            existing = applied_migrations(cur)
            conn.commit()

        for path in migrations:
            checksum = sha256_text(path)
            previous = existing.get(path.name)

            if previous is not None:
                if previous != checksum:
                    raise RuntimeError(
                        f"migration checksum drift: {path.name}: "
                        f"database={previous} file={checksum}"
                    )
                print(f"VERIFY  {path.name}")
                verified_count += 1
                continue

            sql = path.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        """
                        INSERT INTO governance.schema_migrations
                            (migration_name, migration_checksum)
                        VALUES (%s, %s)
                        """,
                        (path.name, checksum),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

            print(f"APPLY   {path.name}")
            applied_count += 1

    return applied_count, verified_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--directory", type=Path, default=Path("db/migrations"), help="migration directory"
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: --database-url or DATABASE_URL is required", file=sys.stderr)
        return 2
    if not args.directory.is_dir():
        print(f"error: migration directory not found: {args.directory}", file=sys.stderr)
        return 2

    try:
        applied, verified = apply(args.database_url, args.directory)
        print(f"MIGRATIONS: applied={applied} verified={verified}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
