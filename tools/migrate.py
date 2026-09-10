#!/usr/bin/env python3
"""Apply ordered PostgreSQL migrations with checksum verification.

Rules:
- filenames are applied in lexical order and must use NNNN_name.sql;
- source checksums are calculated from the original migration bytes;
- legacy outer BEGIN/COMMIT wrappers are stripped only at execution time;
- migration SQL and its ledger insert commit atomically;
- embedded transaction-control statements are rejected;
- a PostgreSQL advisory lock serializes concurrent migration runners;
- checksum drift is a hard failure.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
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
MIGRATION_NAME_RE = re.compile(r"^\d{4}_[a-z0-9_]+\.sql$")
OUTER_BEGIN_RE = re.compile(r"\A\s*BEGIN\s*;", re.IGNORECASE)
OUTER_COMMIT_RE = re.compile(r"COMMIT\s*;\s*\Z", re.IGNORECASE)
FORBIDDEN_TRANSACTION_PATTERNS = (
    re.compile(r"\bBEGIN\b", re.IGNORECASE),
    re.compile(r"\bCOMMIT\b", re.IGNORECASE),
    re.compile(r"\bROLLBACK\b", re.IGNORECASE),
    re.compile(r"\bSAVEPOINT\b", re.IGNORECASE),
    re.compile(r"\bRELEASE\s+SAVEPOINT\b", re.IGNORECASE),
    re.compile(r"\bSTART\s+TRANSACTION\b", re.IGNORECASE),
    re.compile(r"\bSET\s+TRANSACTION\b", re.IGNORECASE),
)
ADVISORY_LOCK_KEY = "cbsrmt:schema-migrations"


def sha256_text(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required; install requirements.txt") from exc
    return psycopg.connect(database_url)


def applied_migrations(cur) -> dict[str, str]:
    cur.execute(
        "SELECT migration_name, migration_checksum FROM governance.schema_migrations"
    )
    return {name: checksum for name, checksum in cur.fetchall()}


def strip_sql_literals_and_comments(sql: str) -> str:
    """Mask strings/comments/dollar bodies so transaction keywords can be scanned safely."""
    out: list[str] = []
    i = 0
    n = len(sql)
    state = "normal"
    dollar_tag = ""

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if state == "normal":
            if ch == "'":
                state = "single"
                out.append(" ")
                i += 1
                continue
            if ch == '"':
                state = "double"
                out.append(" ")
                i += 1
                continue
            if ch == "-" and nxt == "-":
                state = "line_comment"
                out.extend("  ")
                i += 2
                continue
            if ch == "/" and nxt == "*":
                state = "block_comment"
                out.extend("  ")
                i += 2
                continue
            if ch == "$":
                match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[i:])
                if match:
                    dollar_tag = match.group(0)
                    state = "dollar"
                    out.extend(" " * len(dollar_tag))
                    i += len(dollar_tag)
                    continue
            out.append(ch)
            i += 1
            continue

        if state == "single":
            if ch == "'" and nxt == "'":
                out.extend("  ")
                i += 2
            elif ch == "'":
                out.append(" ")
                i += 1
                state = "normal"
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if state == "double":
            if ch == '"' and nxt == '"':
                out.extend("  ")
                i += 2
            elif ch == '"':
                out.append(" ")
                i += 1
                state = "normal"
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if state == "line_comment":
            if ch == "\n":
                out.append("\n")
                state = "normal"
            else:
                out.append(" ")
            i += 1
            continue

        if state == "block_comment":
            if ch == "*" and nxt == "/":
                out.extend("  ")
                i += 2
                state = "normal"
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if state == "dollar":
            if sql.startswith(dollar_tag, i):
                out.extend(" " * len(dollar_tag))
                i += len(dollar_tag)
                state = "normal"
            else:
                out.append("\n" if ch == "\n" else " ")
                i += 1
            continue

    if state in {"single", "double", "block_comment", "dollar"}:
        raise RuntimeError(f"unterminated SQL lexical construct: {state}")
    return "".join(out)


def execution_sql(path: Path) -> str:
    sql = path.read_text(encoding="utf-8")
    begin = OUTER_BEGIN_RE.search(sql)
    commit = OUTER_COMMIT_RE.search(sql)
    if bool(begin) != bool(commit):
        raise RuntimeError(f"migration must contain both outer BEGIN and COMMIT or neither: {path.name}")
    if begin and commit:
        sql = sql[begin.end():commit.start()]

    masked = strip_sql_literals_and_comments(sql)
    for pattern in FORBIDDEN_TRANSACTION_PATTERNS:
        if pattern.search(masked):
            raise RuntimeError(
                f"embedded transaction control is not allowed in migration {path.name}: "
                f"{pattern.pattern}"
            )
    return sql.strip()


def validate_migration_files(migrations: list[Path]) -> None:
    invalid = [path.name for path in migrations if not MIGRATION_NAME_RE.fullmatch(path.name)]
    if invalid:
        raise RuntimeError(f"invalid migration filenames: {', '.join(invalid)}")
    names = [path.name[:4] for path in migrations]
    if len(names) != len(set(names)):
        raise RuntimeError("duplicate migration sequence numbers detected")


def apply(database_url: str, directory: Path) -> tuple[int, int]:
    migrations = sorted(directory.glob("*.sql"))
    if not migrations:
        raise RuntimeError(f"no migrations found in {directory}")
    validate_migration_files(migrations)

    applied_count = 0
    verified_count = 0

    with connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(LEDGER_SCHEMA_SQL)
        conn.commit()

        try:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(hashtext(%s))", (ADVISORY_LOCK_KEY,))
            conn.commit()

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

                sql = execution_sql(path)
                with conn.transaction():
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
                existing[path.name] = checksum
                print(f"APPLY   {path.name}")
                applied_count += 1
        finally:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (ADVISORY_LOCK_KEY,))
                conn.commit()
            except Exception:
                conn.rollback()

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
