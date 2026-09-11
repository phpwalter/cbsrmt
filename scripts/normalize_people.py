#!/usr/bin/env python3
"""Build a deterministic canonical Person registry from cast.json and writers.json.

The legacy cast and writer catalogs overlap. This script reconciles records by
trusted legacy cast_id first, then by normalized full name as a conservative
fallback. It preserves every source spelling and source identifier and emits a
review report for conflicts instead of silently merging incompatible facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

NAMESPACE = uuid.UUID("b2433f75-d190-51a4-81bf-5b70edf18c30")


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    return " ".join(text.strip().split())


def full_name(row: dict[str, Any]) -> str:
    return clean(" ".join(filter(None, [clean(row.get("first_name")), clean(row.get("middle_name")), clean(row.get("last_name"))])))


def sort_name(row: dict[str, Any]) -> str:
    last = clean(row.get("last_name"))
    first = clean(row.get("first_name"))
    middle = clean(row.get("middle_name"))
    given = " ".join(filter(None, [first, middle]))
    if last and given:
        return f"{last}, {given}"
    return last or given


def normalized_key(value: str) -> str:
    return clean(value).casefold()


def stable_person_id(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"person:{key}"))


def source_record_id(source: str, index: int, row: dict[str, Any]) -> str:
    canonical = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{source}#/{index}:{digest[:16]}"


def load(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Expected JSON array in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cast", type=Path, default=Path("data/cast.json"))
    parser.add_argument("--writers", type=Path, default=Path("data/writers.json"))
    parser.add_argument("--output", type=Path, default=Path("data/normalized/people.json"))
    parser.add_argument("--report", type=Path, default=Path("data/normalized/people.validation.json"))
    args = parser.parse_args()

    records: list[tuple[str, int, dict[str, Any]]] = []
    for source, path in (("cast", args.cast), ("writers", args.writers)):
        for index, row in enumerate(load(path)):
            records.append((source, index, row))

    by_legacy_id: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
    no_id: list[tuple[str, int, dict[str, Any]]] = []
    for item in records:
        legacy_id = clean(item[2].get("cast_id"))
        if legacy_id:
            by_legacy_id[legacy_id].append(item)
        else:
            no_id.append(item)

    groups: list[tuple[str, list[tuple[str, int, dict[str, Any]]]]] = []
    for legacy_id, items in sorted(by_legacy_id.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else kv[0]):
        groups.append((f"legacy:{legacy_id}", items))

    by_name: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
    for item in no_id:
        name = normalized_key(full_name(item[2]))
        by_name[name].append(item)
    for name, items in sorted(by_name.items()):
        groups.append((f"name:{name}", items))

    people: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    scalar_fields = ["first_name", "middle_name", "last_name", "born_on", "died_on", "bio", "image_url", "soundclip_url", "offsite_url", "other_series"]

    for key, items in groups:
        names = [full_name(row) for _, _, row in items if full_name(row)]
        canonical_name = names[0] if names else ""
        if not canonical_name:
            warnings.append({"code": "EMPTY_NAME", "group": key})

        conflicts: dict[str, list[str]] = {}
        merged: dict[str, str] = {}
        for field in scalar_fields:
            values = []
            for _, _, row in items:
                value = clean(row.get(field))
                if value and value not in values:
                    values.append(value)
            if values:
                merged[field] = values[0]
            if len(values) > 1:
                conflicts[field] = values

        aliases = sorted({name for name in names if name and name != canonical_name}, key=str.casefold)
        source_ids = []
        legacy_ids = sorted({clean(row.get("cast_id")) for _, _, row in items if clean(row.get("cast_id"))})
        source_handles = sorted({clean(row.get("cast_id_name")) for _, _, row in items if clean(row.get("cast_id_name"))})
        source_roles = sorted({source for source, _, _ in items})

        for source, index, row in items:
            source_ids.append(source_record_id(source, index, row))

        person = {
            "id": stable_person_id(key),
            "canonical_name": canonical_name,
            "sort_name": sort_name(items[0][2]) if items else canonical_name,
            "first_name": merged.get("first_name") or None,
            "middle_name": merged.get("middle_name") or None,
            "last_name": merged.get("last_name") or None,
            "born_on": merged.get("born_on") or None,
            "died_on": merged.get("died_on") or None,
            "bio": merged.get("bio") or None,
            "image_url": merged.get("image_url") or None,
            "soundclip_url": merged.get("soundclip_url") or None,
            "offsite_url": merged.get("offsite_url") or None,
            "other_series": merged.get("other_series") or None,
            "aliases": aliases,
            "legacy_cast_ids": legacy_ids,
            "legacy_handles": source_handles,
            "source_roles": source_roles,
            "source_records": sorted(source_ids),
            "status": "reported" if conflicts else "confirmed",
        }
        people.append(person)

        if conflicts:
            warnings.append({
                "code": "PERSON_FIELD_CONFLICT",
                "person_id": person["id"],
                "canonical_name": canonical_name,
                "fields": conflicts,
            })

    people.sort(key=lambda p: (p["sort_name"].casefold(), p["id"]))
    report = {
        "input_records": len(records),
        "canonical_people": len(people),
        "warnings": sorted(warnings, key=lambda w: (w["code"], w.get("canonical_name", ""), w.get("group", ""))),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(people, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
