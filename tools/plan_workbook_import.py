#!/usr/bin/env python3
"""Build a deterministic dry-run plan for an approved staged workbook import."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from tools.validate_workbook_mapping import load_report, load_yaml, validate
from tools.workbook_handlers import HANDLERS
from tools.workbook_transforms import apply_transform


def load_staged_rows(cur, workbook_sha: str, sheet_name: str) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT r.row_id::text, r.row_number,
               jsonb_object_agg(c.header_value, c.raw_value ORDER BY c.column_number)
                   FILTER (WHERE c.header_value IS NOT NULL) AS values,
               jsonb_object_agg(c.header_value, c.cell_address ORDER BY c.column_number)
                   FILTER (WHERE c.header_value IS NOT NULL) AS cells
        FROM staging.workbooks w
        JOIN staging.workbook_sheets s ON s.workbook_id = w.workbook_id
        JOIN staging.workbook_rows r ON r.sheet_id = s.sheet_id
        LEFT JOIN staging.workbook_cells c ON c.row_id = r.row_id
        WHERE w.sha256 = %s
          AND s.sheet_name = %s
          AND r.row_number > s.header_row
        GROUP BY r.row_id, r.row_number
        ORDER BY r.row_number
        """,
        (workbook_sha, sheet_name),
    )
    return [dict(row) for row in cur.fetchall()]


def transform_row(sheet_mapping: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    source_values = row.get("values") or {}
    source_cells = row.get("cells") or {}
    entities: dict[str, dict[str, Any]] = defaultdict(dict)
    provenance: dict[str, dict[str, Any]] = defaultdict(dict)

    for column in sheet_mapping["columns"]:
        header = column["sourceHeader"]
        target = column["target"]
        raw = source_values.get(header)
        if column.get("required", False) and raw in (None, ""):
            raise ValueError(f"required source value is blank: {header}")
        transformed = apply_transform(column.get("transform", "identity"), raw)
        entities[target["entity"]][target["field"]] = transformed
        provenance[target["entity"]][target["field"]] = {
            "sourceHeader": header,
            "cell": source_cells.get(header),
            "rawValue": raw,
            "normalizedValue": transformed,
            "policy": column["provenance"],
        }

    return {"entities": dict(entities), "provenance": dict(provenance)}


def build_plan(database_url: str, mapping_path: Path, inspection_path: Path | None = None) -> dict[str, Any]:
    mapping = load_yaml(mapping_path)
    report_path = inspection_path or Path(mapping["workbook"]["inspectionReport"])
    report = load_report(report_path)
    validate(mapping, report)

    workbook_sha = mapping["workbook"]["sha256"]
    planned_rows = []
    summary: dict[str, int] = defaultdict(int)

    with psycopg.connect(database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
        for sheet in mapping["sheets"]:
            if sheet.get("status") != "APPROVED":
                continue
            rows = load_staged_rows(cur, workbook_sha, sheet["sheetName"])
            for row in rows:
                try:
                    transformed = transform_row(sheet, row)
                    entities = sorted(transformed["entities"].keys())
                    for entity in entities:
                        if entity not in HANDLERS:
                            raise ValueError(f"unsupported canonical entity: {entity}")
                        summary[entity] += 1
                    planned_rows.append(
                        {
                            "sheet": sheet["sheetName"],
                            "rowNumber": row["row_number"],
                            "status": "PLANNED",
                            **transformed,
                        }
                    )
                except Exception as exc:
                    planned_rows.append(
                        {
                            "sheet": sheet["sheetName"],
                            "rowNumber": row["row_number"],
                            "status": "BLOCKED",
                            "error": str(exc),
                        }
                    )

    blocked = sum(1 for row in planned_rows if row["status"] == "BLOCKED")
    return {
        "mode": "DRY_RUN",
        "workbook": mapping["workbook"]["fileName"],
        "sha256": workbook_sha,
        "approvedBy": mapping["workbook"]["approvedBy"],
        "rowCount": len(planned_rows),
        "blockedCount": blocked,
        "entityCounts": dict(sorted(summary.items())),
        "rows": planned_rows,
        "canonicalWritesPerformed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--inspection", type=Path)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: --database-url or DATABASE_URL is required", file=sys.stderr)
        return 2

    try:
        plan = build_plan(args.database_url, args.mapping, args.inspection)
    except Exception as exc:
        print(f"WORKBOOK IMPORT PLAN: FAIL - {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(plan, indent=2, default=str, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"WROTE: {args.output}")
    else:
        print(rendered)
    return 1 if plan["blockedCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
