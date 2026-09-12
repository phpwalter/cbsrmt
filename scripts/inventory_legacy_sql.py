#!/usr/bin/env python3
"""Inventory table structures and INSERT row counts from sql/cbs.sql.

This script does not execute the SQL. It performs a deterministic static scan so
we can classify which legacy tables contain unique historical information worth
recovering into the canonical model.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "sql" / "cbs.sql"
OUTPUT = ROOT / "data" / "normalized" / "legacy_sql_inventory.json"

CREATE_RE = re.compile(r"^CREATE TABLE IF NOT EXISTS `([^`]+)` \($")
INSERT_RE = re.compile(r"^INSERT INTO `([^`]+)` VALUES\(")
COLUMN_RE = re.compile(r"^\s+`([^`]+)`\s+(.+?)(?:,)?$")


def main() -> int:
    tables: dict[str, dict] = {}
    row_counts: dict[str, int] = defaultdict(int)
    current_table: str | None = None

    with SOURCE.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.rstrip("\r\n")

            match = CREATE_RE.match(line)
            if match:
                current_table = match.group(1)
                tables.setdefault(current_table, {
                    "name": current_table,
                    "create_line": line_number,
                    "columns": [],
                    "insert_rows": 0,
                })
                continue

            if current_table:
                if line.startswith(") ENGINE=") or line == ");":
                    current_table = None
                    continue
                column = COLUMN_RE.match(line)
                if column:
                    name, definition = column.groups()
                    tables[current_table]["columns"].append({
                        "name": name,
                        "definition": definition.rstrip(","),
                    })

            insert = INSERT_RE.match(line)
            if insert:
                row_counts[insert.group(1)] += 1

    for name, table in tables.items():
        table["insert_rows"] = row_counts.get(name, 0)

    for name, count in row_counts.items():
        if name not in tables:
            tables[name] = {
                "name": name,
                "create_line": None,
                "columns": [],
                "insert_rows": count,
            }

    records = sorted(tables.values(), key=lambda item: item["name"].casefold())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "source": "sql/cbs.sql",
        "table_count": len(records),
        "tables": records,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"inventoried {len(records)} legacy SQL tables")
    for table in records:
        print(f"{table['name']}: {len(table['columns'])} columns, {table['insert_rows']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
