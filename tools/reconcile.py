#!/usr/bin/env python3
"""Report catalog reconciliation and fail on structural or unresolved quality inconsistencies."""

from __future__ import annotations

import argparse
import os
import sys


def connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("psycopg is required; install requirements.txt") from exc
    return psycopg.connect(database_url)


def scalar(cur, sql: str) -> int:
    cur.execute(sql)
    return int(cur.fetchone()[0])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--allow-open-errors",
        action="store_true",
        help="report open ERROR/FATAL quality findings without failing reconciliation",
    )
    args = parser.parse_args(argv)
    if not args.database_url:
        print("error: --database-url or DATABASE_URL is required", file=sys.stderr)
        return 2

    with connect(args.database_url) as conn, conn.cursor() as cur:
        metrics = {
            "Episodes": scalar(cur, "SELECT count(*) FROM catalog.episodes"),
            "Broadcasts": scalar(cur, "SELECT count(*) FROM catalog.broadcasts"),
            "Original broadcasts": scalar(cur, "SELECT count(*) FROM catalog.broadcasts WHERE broadcast_type = 'original'"),
            "Reruns": scalar(cur, "SELECT count(*) FROM catalog.broadcasts WHERE broadcast_type = 'rerun'"),
            "SHOW identifiers": scalar(cur, "SELECT count(*) FROM provenance.external_identifiers WHERE entity_type = 'episode' AND namespace = 'cbsrmt.show_number'"),
            "OTRW identifiers": scalar(cur, "SELECT count(*) FROM provenance.external_identifiers WHERE entity_type = 'broadcast' AND namespace = 'otrwalter.broadcast_number'"),
            "Import batches": scalar(cur, "SELECT count(*) FROM provenance.import_batches"),
            "Conflicting assertions": scalar(cur, "SELECT count(*) FROM provenance.source_assertions WHERE verification_status = 'disputed'"),
            "Open quality INFO": scalar(cur, "SELECT count(*) FROM quality.issues WHERE severity = 'INFO' AND resolution_status = 'open'"),
            "Open quality WARNING": scalar(cur, "SELECT count(*) FROM quality.issues WHERE severity = 'WARNING' AND resolution_status = 'open'"),
            "Open quality ERROR": scalar(cur, "SELECT count(*) FROM quality.issues WHERE severity = 'ERROR' AND resolution_status = 'open'"),
            "Open quality FATAL": scalar(cur, "SELECT count(*) FROM quality.issues WHERE severity = 'FATAL' AND resolution_status = 'open'"),
            "Quarantined records": scalar(cur, "SELECT count(*) FROM quality.quarantine WHERE resolution_status = 'open'"),
            "Orphan broadcasts": scalar(cur, "SELECT count(*) FROM catalog.broadcasts b LEFT JOIN catalog.episodes e ON e.episode_id = b.episode_id WHERE e.episode_id IS NULL"),
        }

    failures = []
    if metrics["Orphan broadcasts"] != 0:
        failures.append("orphan broadcasts exist")
    if metrics["SHOW identifiers"] > metrics["Episodes"]:
        failures.append("more SHOW identifiers than episodes")
    if metrics["OTRW identifiers"] > metrics["Broadcasts"]:
        failures.append("more OTRW identifiers than broadcasts")
    if not args.allow_open_errors:
        if metrics["Open quality ERROR"] != 0:
            failures.append("open ERROR data-quality findings exist")
        if metrics["Open quality FATAL"] != 0:
            failures.append("open FATAL data-quality findings exist")
        if metrics["Quarantined records"] != 0:
            failures.append("unresolved quarantined records exist")

    print("CBSRMT Catalog Reconciliation\n")
    width = max(len(label) for label in metrics)
    for label, value in metrics.items():
        print(f"{label:.<{width + 4}} {value}")
    print()
    if failures:
        print("RESULT: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
