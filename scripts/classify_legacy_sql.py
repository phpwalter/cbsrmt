#!/usr/bin/env python3
"""Apply governed classifications to the generated legacy SQL inventory."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "normalized" / "legacy_sql_inventory.json"
RULES = ROOT / "data" / "legacy-table-classification.json"
OUTPUT = ROOT / "data" / "normalized" / "legacy_sql_classified.json"


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    mapping = rules.get("classifications", {})
    default = rules.get("default_classification", "review_required")

    classified = []
    review_required = 0
    recoverable = 0

    for table in inventory.get("tables", []):
        name = table["name"]
        rule = mapping.get(name, {})
        classification = rule.get("classification", default)
        record = dict(table)
        record["classification"] = classification
        record["canonical_target"] = rule.get("canonical_target")
        record["authority"] = rule.get("authority", "undetermined")
        record["classification_notes"] = rule.get("notes")
        classified.append(record)

        if classification == "review_required":
            review_required += 1
        if classification in {"relationship_source", "catalog_source", "lookup_source"} and table.get("insert_rows", 0) > 0:
            recoverable += 1

    classified.sort(key=lambda item: item["name"].casefold())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "source": "data/normalized/legacy_sql_inventory.json",
        "classification_rules": "data/legacy-table-classification.json",
        "table_count": len(classified),
        "recoverable_table_count": recoverable,
        "review_required_count": review_required,
        "tables": classified,
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"classified {len(classified)} legacy SQL tables")
    print(f"recoverable tables with rows: {recoverable}")
    print(f"tables requiring review: {review_required}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
