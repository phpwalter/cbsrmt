#!/usr/bin/env python3
"""Import CBSRMT_Log_1982.txt into the foundation PostgreSQL catalog.

Pipeline:
    raw text -> parsed records -> staging -> validation -> canonical catalog

The importer is deliberately conservative. It never silently replaces a
conflicting canonical value. A second run with the same source checksum and
importer version reuses the existing batch and does not duplicate canonical
entities or identifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

IMPORTER_VERSION = "0.1.0"
SOURCE_NAME = "CBSRMT_Log_1982.txt"
SOURCE_TYPE = "historical_broadcast_log"
SHOW_NAMESPACE = "cbsrmt.show_number"
OTRW_NAMESPACE = "otrwalter.broadcast_number"
ROW_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d{6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class BroadcastRecord:
    source_line: int
    show_number: int
    otrw_number: int
    source_date: str
    broadcast_date: date
    raw_title: str
    normalized_title: str
    raw_record: str


def normalize_title(value: str) -> str:
    """Normalize whitespace only; historical wording is otherwise preserved."""
    return " ".join(value.strip().split())


def parse_source_date(value: str) -> date:
    """Parse the source YYMMDD date using the known 1982 log century."""
    if not re.fullmatch(r"\d{6}", value):
        raise ValueError(f"invalid YYMMDD date: {value!r}")
    year = 1900 + int(value[0:2])
    month = int(value[2:4])
    day = int(value[4:6])
    parsed = date(year, month, day)
    if parsed.year != 1982:
        raise ValueError(f"unexpected year in 1982 source: {value!r}")
    return parsed


def parse_log(lines: Iterable[str]) -> Iterator[BroadcastRecord]:
    """Yield structured rows from the historical log.

    Header/prose/separator lines are ignored. Any line beginning with a digit
    that resembles data but does not match the expected four-column shape is
    rejected rather than silently skipped.
    """
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")
        match = ROW_RE.match(line)
        if match:
            show_number = int(match.group(1))
            otrw_number = int(match.group(2))
            source_date = match.group(3)
            title = match.group(4)
            if show_number <= 0 or otrw_number <= 0:
                raise ValueError(f"line {line_number}: identifiers must be positive")
            yield BroadcastRecord(
                source_line=line_number,
                show_number=show_number,
                otrw_number=otrw_number,
                source_date=source_date,
                broadcast_date=parse_source_date(source_date),
                raw_title=title,
                normalized_title=normalize_title(title),
                raw_record=line,
            )
            continue

        if line.lstrip()[:1].isdigit():
            raise ValueError(f"line {line_number}: malformed data row: {line!r}")


def source_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_records(records: list[BroadcastRecord]) -> None:
    if not records:
        raise ValueError("source contains no broadcast rows")

    show_numbers: set[int] = set()
    otrw_numbers: set[int] = set()
    previous_show: int | None = None

    for record in records:
        if record.show_number in show_numbers:
            raise ValueError(f"duplicate SHOW #: {record.show_number}")
        if record.otrw_number in otrw_numbers:
            raise ValueError(f"duplicate OTRW #: {record.otrw_number}")
        if previous_show is not None and record.show_number <= previous_show:
            raise ValueError(
                f"SHOW # is not strictly increasing: {previous_show} -> {record.show_number}"
            )
        show_numbers.add(record.show_number)
        otrw_numbers.add(record.otrw_number)
        previous_show = record.show_number


def connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for database import; install requirements.txt"
        ) from exc
    return psycopg.connect(database_url)


def ensure_source(cur) -> str:
    cur.execute(
        """
        INSERT INTO provenance.sources (source_type, name, description, uri, license)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_type, name)
        DO UPDATE SET description = EXCLUDED.description
        RETURNING source_id::text
        """,
        (
            SOURCE_TYPE,
            SOURCE_NAME,
            "CBS Radio Mystery Theater Broadcast Log for 1982",
            SOURCE_NAME,
            "CC0 repository metadata; underlying historical facts are factual data",
        ),
    )
    return cur.fetchone()[0]


def ensure_batch(cur, source_id: str, checksum: str) -> tuple[str, str]:
    cur.execute(
        """
        INSERT INTO provenance.import_batches
            (source_id, source_checksum, importer_version, status)
        VALUES (%s::uuid, %s, %s, 'running')
        ON CONFLICT (source_id, source_checksum, importer_version)
        DO UPDATE SET source_checksum = EXCLUDED.source_checksum
        RETURNING import_batch_id::text, status
        """,
        (source_id, checksum, IMPORTER_VERSION),
    )
    row = cur.fetchone()
    return row[0], row[1]


def stage_records(cur, batch_id: str, records: list[BroadcastRecord]) -> None:
    for record in records:
        cur.execute(
            """
            INSERT INTO staging.broadcast_log_1982 (
                import_batch_id, source_line, show_number, otrw_number,
                source_date, parsed_broadcast_date, raw_title,
                normalized_title, validation_status, raw_record
            )
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, 'valid', %s)
            ON CONFLICT (import_batch_id, source_line)
            DO UPDATE SET
                show_number = EXCLUDED.show_number,
                otrw_number = EXCLUDED.otrw_number,
                source_date = EXCLUDED.source_date,
                parsed_broadcast_date = EXCLUDED.parsed_broadcast_date,
                raw_title = EXCLUDED.raw_title,
                normalized_title = EXCLUDED.normalized_title,
                validation_status = 'valid',
                validation_message = NULL,
                raw_record = EXCLUDED.raw_record
            """,
            (
                batch_id,
                record.source_line,
                record.show_number,
                record.otrw_number,
                record.source_date,
                record.broadcast_date,
                record.raw_title,
                record.normalized_title,
                record.raw_record,
            ),
        )


def find_entity_by_identifier(cur, namespace: str, value: str, entity_type: str):
    cur.execute(
        """
        SELECT entity_id::text
        FROM provenance.external_identifiers
        WHERE namespace = %s
          AND identifier_value = %s
          AND entity_type = %s
        """,
        (namespace, value, entity_type),
    )
    row = cur.fetchone()
    return row[0] if row else None


def ensure_episode(cur, source_id: str, batch_id: str, record: BroadcastRecord) -> str:
    episode_id = find_entity_by_identifier(
        cur, SHOW_NAMESPACE, str(record.show_number), "episode"
    )
    if episode_id is None:
        cur.execute(
            """
            INSERT INTO catalog.episodes
                (canonical_number, title, original_air_date, verification_status)
            VALUES (%s, %s, %s, 'source-backed')
            RETURNING episode_id::text
            """,
            (record.show_number, record.normalized_title, record.broadcast_date),
        )
        episode_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO provenance.external_identifiers
                (entity_type, entity_id, namespace, identifier_value, source_id)
            VALUES ('episode', %s::uuid, %s, %s, %s::uuid)
            """,
            (episode_id, SHOW_NAMESPACE, str(record.show_number), source_id),
        )
    else:
        cur.execute(
            "SELECT title, original_air_date FROM catalog.episodes WHERE episode_id = %s::uuid",
            (episode_id,),
        )
        title, original_air_date = cur.fetchone()
        if normalize_title(title) != record.normalized_title:
            raise ValueError(
                f"SHOW # {record.show_number}: canonical title conflict: "
                f"{title!r} != {record.normalized_title!r}"
            )
        if original_air_date and original_air_date != record.broadcast_date:
            raise ValueError(
                f"SHOW # {record.show_number}: original air date conflict: "
                f"{original_air_date} != {record.broadcast_date}"
            )

    assertions = (
        ("canonical_number", str(record.show_number), str(record.show_number)),
        ("title", record.raw_title, record.normalized_title),
        ("original_air_date", record.source_date, record.broadcast_date.isoformat()),
    )
    for field_name, raw_value, normalized_value in assertions:
        cur.execute(
            """
            SELECT 1 FROM provenance.source_assertions
            WHERE source_id = %s::uuid
              AND import_batch_id = %s::uuid
              AND entity_type = 'episode'
              AND entity_id = %s::uuid
              AND field_name = %s
              AND normalized_value IS NOT DISTINCT FROM %s
            """,
            (source_id, batch_id, episode_id, field_name, normalized_value),
        )
        if cur.fetchone() is None:
            cur.execute(
                """
                INSERT INTO provenance.source_assertions
                    (source_id, import_batch_id, entity_type, entity_id,
                     field_name, raw_value, normalized_value,
                     confidence, verification_status)
                VALUES (%s::uuid, %s::uuid, 'episode', %s::uuid,
                        %s, %s, %s, 1.0, 'source-backed')
                """,
                (
                    source_id,
                    batch_id,
                    episode_id,
                    field_name,
                    raw_value,
                    normalized_value,
                ),
            )
    return episode_id


def ensure_broadcast(
    cur, source_id: str, batch_id: str, episode_id: str, record: BroadcastRecord
) -> str:
    broadcast_id = find_entity_by_identifier(
        cur, OTRW_NAMESPACE, str(record.otrw_number), "broadcast"
    )
    if broadcast_id is None:
        cur.execute(
            """
            INSERT INTO catalog.broadcasts
                (episode_id, broadcast_date, broadcast_type, verification_status)
            VALUES (%s::uuid, %s, 'original', 'source-backed')
            RETURNING broadcast_id::text
            """,
            (episode_id, record.broadcast_date),
        )
        broadcast_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO provenance.external_identifiers
                (entity_type, entity_id, namespace, identifier_value, source_id)
            VALUES ('broadcast', %s::uuid, %s, %s, %s::uuid)
            """,
            (broadcast_id, OTRW_NAMESPACE, str(record.otrw_number), source_id),
        )
    else:
        cur.execute(
            """
            SELECT episode_id::text, broadcast_date
            FROM catalog.broadcasts
            WHERE broadcast_id = %s::uuid
            """,
            (broadcast_id,),
        )
        existing_episode_id, existing_date = cur.fetchone()
        if existing_episode_id != episode_id or existing_date != record.broadcast_date:
            raise ValueError(
                f"OTRW # {record.otrw_number}: canonical broadcast conflict"
            )

    cur.execute(
        """
        SELECT 1 FROM provenance.source_assertions
        WHERE source_id = %s::uuid
          AND import_batch_id = %s::uuid
          AND entity_type = 'broadcast'
          AND entity_id = %s::uuid
          AND field_name = 'broadcast_date'
          AND normalized_value = %s
        """,
        (source_id, batch_id, broadcast_id, record.broadcast_date.isoformat()),
    )
    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO provenance.source_assertions
                (source_id, import_batch_id, entity_type, entity_id,
                 field_name, raw_value, normalized_value,
                 confidence, verification_status)
            VALUES (%s::uuid, %s::uuid, 'broadcast', %s::uuid,
                    'broadcast_date', %s, %s, 1.0, 'source-backed')
            """,
            (
                source_id,
                batch_id,
                broadcast_id,
                record.source_date,
                record.broadcast_date.isoformat(),
            ),
        )
    return broadcast_id


def import_records(database_url: str, path: Path, records: list[BroadcastRecord]) -> None:
    checksum = source_checksum(path)
    with connect(database_url) as conn:
        try:
            with conn.cursor() as cur:
                source_id = ensure_source(cur)
                batch_id, _ = ensure_batch(cur, source_id, checksum)
                stage_records(cur, batch_id, records)

                for record in records:
                    episode_id = ensure_episode(cur, source_id, batch_id, record)
                    ensure_broadcast(cur, source_id, batch_id, episode_id, record)

                cur.execute(
                    """
                    UPDATE provenance.import_batches
                    SET status = 'completed',
                        completed_at = now(),
                        rows_seen = %s,
                        rows_accepted = %s,
                        rows_rejected = 0
                    WHERE import_batch_id = %s::uuid
                    """,
                    (len(records), len(records), batch_id),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        default=SOURCE_NAME,
        type=Path,
        help=f"path to source log (default: {SOURCE_NAME})",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL; defaults to DATABASE_URL",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="parse and validate without connecting to PostgreSQL",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.source.exists():
        print(f"error: source file not found: {args.source}", file=sys.stderr)
        return 2

    try:
        with args.source.open("r", encoding="utf-8-sig") as handle:
            records = list(parse_log(handle))
        validate_records(records)

        if args.validate_only:
            print(
                f"VALID: {len(records)} rows; "
                f"SHOW {records[0].show_number}-{records[-1].show_number}; "
                f"dates {records[0].broadcast_date}..{records[-1].broadcast_date}"
            )
            return 0

        if not args.database_url:
            print("error: --database-url or DATABASE_URL is required", file=sys.stderr)
            return 2

        import_records(args.database_url, args.source, records)
        print(f"IMPORTED: {len(records)} rows using importer {IMPORTER_VERSION}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
