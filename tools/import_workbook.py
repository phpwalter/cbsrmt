#!/usr/bin/env python3
"""Execute an approved workbook mapping through explicit canonical handlers.

This command is intentionally fail-closed. The workbook, inspection report, and
mapping must pass the canonicalization gate, and each mapped canonical entity
must have an explicitly enabled handler. Row failures are quarantined without
silently committing partial row state.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from tools.plan_workbook_import import load_staged_rows, transform_row
from tools.quality import QualityIssue, quarantine_record, record_issue
from tools.validate_workbook_mapping import load_report, load_yaml, validate
from tools.workbook_gate import evaluate_gate
from tools.workbook_handlers import HandlerContext, get_handler


def resolve_workbook_id(cur, checksum: str) -> str:
    cur.execute(
        "SELECT workbook_id::text FROM staging.workbooks WHERE sha256 = %s",
        (checksum,),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("approved workbook has not been staged")
    return row["workbook_id"]


def execute_import(
    database_url: str,
    mapping_path: Path,
    inspection_path: Path,
    workbook_path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    mapping = load_yaml(mapping_path)
    report = load_report(inspection_path)
    validate(mapping, report, workbook_path)
    gate = evaluate_gate(mapping_path, inspection_path, workbook_path)
    if not gate["eligible"]:
        raise RuntimeError("canonicalization gate did not pass")

    result = {
        "mode": "DRY_RUN" if dry_run else "EXECUTE",
        "workbook": mapping["workbook"]["fileName"],
        "sha256": mapping["workbook"]["sha256"],
        "acceptedRows": 0,
        "rejectedRows": 0,
        "canonicalWritesPerformed": False,
    }

    with psycopg.connect(database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
        workbook_id = resolve_workbook_id(cur, mapping["workbook"]["sha256"])

        cur.execute(
            """
            SELECT source_id::text
            FROM provenance.sources
            WHERE source_type = 'workbook'
              AND uri = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (mapping["workbook"]["fileName"],),
        )
        source_row = cur.fetchone()
        if source_row is None:
            raise RuntimeError("staged workbook source provenance record not found")
        source_id = source_row["source_id"]

        cur.execute(
            """
            INSERT INTO provenance.import_batches
                (source_id, source_checksum, importer_version, status)
            VALUES (%s::uuid, %s, 'workbook-1.0', 'running')
            ON CONFLICT (source_id, source_checksum, importer_version)
            DO UPDATE SET source_checksum = EXCLUDED.source_checksum
            RETURNING import_batch_id::text
            """,
            (source_id, mapping["workbook"]["sha256"]),
        )
        import_batch_id = cur.fetchone()["import_batch_id"]

        if dry_run:
            conn.rollback()
            result["canonicalWritesPerformed"] = False
            return result

        for sheet in mapping["sheets"]:
            if sheet.get("status") != "APPROVED":
                continue

            rows = load_staged_rows(cur, mapping["workbook"]["sha256"], sheet["sheetName"])
            for row in rows:
                try:
                    transformed = transform_row(sheet, row)
                    context = HandlerContext(
                        source_id=source_id,
                        import_batch_id=import_batch_id,
                        workbook_id=workbook_id,
                        sheet_name=sheet["sheetName"],
                        row_number=row["row_number"],
                    )
                    with conn.transaction():
                        for entity, values in transformed["entities"].items():
                            handler = get_handler(entity)
                            handler(cur, context, values, transformed["provenance"].get(entity, {}))
                    result["acceptedRows"] += 1
                    result["canonicalWritesPerformed"] = True
                except Exception as exc:
                    result["rejectedRows"] += 1
                    issue = QualityIssue(
                        severity="ERROR",
                        issue_code="WORKBOOK_CANONICALIZATION_BLOCKED",
                        message=str(exc),
                        source_line=row["row_number"],
                        raw_value=json.dumps(row.get("values") or {}, default=str, sort_keys=True),
                    )
                    record_issue(
                        cur,
                        source_id=source_id,
                        import_batch_id=import_batch_id,
                        issue=issue,
                    )
                    quarantine_record(
                        cur,
                        import_batch_id=import_batch_id,
                        source_id=source_id,
                        source_line=row["row_number"],
                        record_type=f"workbook:{sheet['sheetName']}",
                        issue_code="WORKBOOK_CANONICALIZATION_BLOCKED",
                        raw_record=json.dumps(row.get("values") or {}, default=str, sort_keys=True),
                        severity="ERROR",
                        parsed_payload={"sheet": sheet["sheetName"], "rowNumber": row["row_number"]},
                    )

        cur.execute(
            """
            UPDATE provenance.import_batches
            SET status = 'completed', completed_at = now(),
                rows_seen = %s, rows_accepted = %s, rows_rejected = %s
            WHERE import_batch_id = %s::uuid
            """,
            (
                result["acceptedRows"] + result["rejectedRows"],
                result["acceptedRows"],
                result["rejectedRows"],
                import_batch_id,
            ),
        )
        conn.commit()

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--inspection", required=True, type=Path)
    parser.add_argument("--workbook", required=True, type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: --database-url or DATABASE_URL is required", file=sys.stderr)
        return 2

    try:
        result = execute_import(
            args.database_url,
            args.mapping,
            args.inspection,
            args.workbook,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"WORKBOOK IMPORT: FAIL - {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 1 if result["rejectedRows"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
