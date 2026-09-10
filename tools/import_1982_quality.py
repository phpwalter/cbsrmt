#!/usr/bin/env python3
"""Quality-aware CBSRMT 1982 importer with row-level partial acceptance."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.import_1982 import (
    IMPORTER_VERSION,
    ensure_batch,
    ensure_broadcast,
    ensure_episode,
    ensure_source,
    parse_log,
    source_checksum,
    stage_records,
)
from tools.quality import QualityIssue, quarantine_record, record_issue


def scan_lines(lines: list[str]):
    accepted = []
    rejected = []
    seen_show: set[int] = set()
    seen_otrw: set[int] = set()

    for source_line, raw in enumerate(lines, start=1):
        try:
            rows = list(parse_log([raw]))
        except Exception as exc:
            if raw.lstrip()[:1].isdigit():
                rejected.append((source_line, raw.rstrip("\r\n"), "MALFORMED_ROW", str(exc)))
            continue

        if not rows:
            continue

        row = rows[0]
        row = type(row)(
            source_line=source_line,
            show_number=row.show_number,
            otrw_number=row.otrw_number,
            source_date=row.source_date,
            broadcast_date=row.broadcast_date,
            raw_title=row.raw_title,
            normalized_title=row.normalized_title,
            raw_record=row.raw_record,
        )

        if row.show_number in seen_show:
            rejected.append((source_line, row.raw_record, "DUPLICATE_SHOW_NUMBER", f"duplicate SHOW #: {row.show_number}"))
            continue
        if row.otrw_number in seen_otrw:
            rejected.append((source_line, row.raw_record, "DUPLICATE_OTRW_NUMBER", f"duplicate OTRW #: {row.otrw_number}"))
            continue

        seen_show.add(row.show_number)
        seen_otrw.add(row.otrw_number)
        accepted.append(row)

    return accepted, rejected


def persist_rejection(cur, *, batch_id: str, source_id: str, source_line: int, raw_record: str, code: str, message: str) -> None:
    issue = QualityIssue(
        severity="ERROR",
        issue_code=code,
        message=message,
        source_line=source_line,
        raw_value=raw_record,
    )
    record_issue(cur, source_id=source_id, import_batch_id=batch_id, issue=issue)
    quarantine_record(
        cur,
        import_batch_id=batch_id,
        record_type="broadcast_log_1982",
        issue_code=code,
        raw_record=raw_record,
        severity="ERROR",
        source_id=source_id,
        source_line=source_line,
    )


def import_quality(database_url: str, source: Path) -> tuple[int, int]:
    import psycopg

    raw_lines = source.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    accepted, rejected = scan_lines(raw_lines)
    checksum = source_checksum(source)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            source_id = ensure_source(cur)
            batch_id, _ = ensure_batch(cur, source_id, checksum)
            stage_records(cur, batch_id, accepted)

            accepted_count = 0
            canonical_rejections = 0
            for row in accepted:
                try:
                    with conn.transaction():
                        episode_id = ensure_episode(cur, source_id, batch_id, row)
                        ensure_broadcast(cur, source_id, batch_id, episode_id, row)
                    accepted_count += 1
                except Exception as exc:
                    canonical_rejections += 1
                    persist_rejection(
                        cur,
                        batch_id=batch_id,
                        source_id=source_id,
                        source_line=row.source_line,
                        raw_record=row.raw_record,
                        code="CANONICAL_CONFLICT",
                        message=str(exc),
                    )

            for source_line, raw_record, code, message in rejected:
                persist_rejection(
                    cur,
                    batch_id=batch_id,
                    source_id=source_id,
                    source_line=source_line,
                    raw_record=raw_record,
                    code=code,
                    message=message,
                )

            rejected_count = len(rejected) + canonical_rejections
            rows_seen = accepted_count + rejected_count
            cur.execute(
                """
                UPDATE provenance.import_batches
                SET status = 'completed', completed_at = now(),
                    rows_seen = %s, rows_accepted = %s, rows_rejected = %s
                WHERE import_batch_id = %s::uuid
                """,
                (rows_seen, accepted_count, rejected_count, batch_id),
            )
        conn.commit()

    return accepted_count, rejected_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=Path("CBSRMT_Log_1982.txt"))
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = parser.parse_args(argv)

    if not args.source.exists():
        print(f"error: source file not found: {args.source}", file=sys.stderr)
        return 2
    if not args.database_url:
        print("error: --database-url or DATABASE_URL is required", file=sys.stderr)
        return 2

    accepted, rejected = import_quality(args.database_url, args.source)
    print("CBSRMT 1982 Import Summary")
    print(f"Accepted.... {accepted}")
    print(f"Rejected.... {rejected}")
    print(f"Importer.... {IMPORTER_VERSION}")
    return 0 if rejected == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
