#!/usr/bin/env python3
"""Normalize legacy CBS RMT genres into deterministic canonical records."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data" / "genre.json"
OUTPUT_PATH = ROOT / "data" / "normalized" / "genres.json"
REPORT_PATH = ROOT / "data" / "normalized" / "genres.validation.json"

CBS_RMT_NAMESPACE = uuid.UUID("646a1d8f-b1f5-5df3-9e06-44f9508c8d0a")
WHITESPACE_RE = re.compile(r"\s+")

# Corrections here alter canonical presentation only. Source spellings remain in provenance.
CANONICAL_NAME_OVERRIDES = {
    "Unkown": "Unknown",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value))
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def canonical_uuid(legacy_id: str) -> str:
    return str(uuid.uuid5(CBS_RMT_NAMESPACE, f"genre:legacy:{legacy_id}"))


def main() -> int:
    raw_records = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_records, list):
        raise TypeError("data/genre.json must contain a JSON array")

    normalized: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen_ids: dict[str, int] = {}
    seen_names: dict[str, int] = {}

    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            issues.append({"record_index": index, "severity": "error", "field": "$", "message": "record is not an object"})
            continue

        legacy_id = clean_text(raw.get("genre_id"))
        source_name = clean_text(raw.get("genre_name"))

        if legacy_id is None:
            issues.append({"record_index": index, "severity": "error", "field": "genre_id", "message": "genre id is empty"})
            continue
        if source_name is None:
            issues.append({"record_index": index, "severity": "error", "field": "genre_name", "message": "genre name is empty"})
            continue

        if legacy_id in seen_ids:
            issues.append({"record_index": index, "severity": "error", "field": "genre_id", "message": f"duplicate legacy genre id {legacy_id}; first seen at record {seen_ids[legacy_id]}"})
        else:
            seen_ids[legacy_id] = index

        canonical_name = CANONICAL_NAME_OVERRIDES.get(source_name, source_name)
        folded_name = canonical_name.casefold()
        if folded_name in seen_names:
            issues.append({"record_index": index, "severity": "error", "field": "genre_name", "message": f"duplicate canonical genre name {canonical_name!r}; first seen at record {seen_names[folded_name]}"})
        else:
            seen_names[folded_name] = index

        if canonical_name != source_name:
            issues.append({"record_index": index, "severity": "warning", "field": "genre_name", "message": f"canonical spelling normalized from {source_name!r} to {canonical_name!r}"})

        normalized.append({
            "id": canonical_uuid(legacy_id),
            "legacy_id": legacy_id,
            "name": canonical_name,
            "source_name": source_name,
            "status": "reported",
            "source": {"artifact": "data/genre.json", "locator": f"/{index}"},
        })

    normalized.sort(key=lambda item: (int(item["legacy_id"]) if item["legacy_id"].isdigit() else 10**9, item["legacy_id"]))
    issues.sort(key=lambda item: (item["record_index"], item["severity"], item["field"], item["message"]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(normalized, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    report = {
        "source": "data/genre.json",
        "input_records": len(raw_records),
        "output_records": len(normalized),
        "error_count": error_count,
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"normalized {len(normalized)} of {len(raw_records)} genre records")
    print(f"validation errors: {error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
