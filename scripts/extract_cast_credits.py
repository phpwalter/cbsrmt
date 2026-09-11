#!/usr/bin/env python3
"""Extract legacy episode/cast relationships from sql/cbs.sql.

The legacy MySQL export contains an `appear` table whose rows connect episode_id
and cast_id. This script parses only INSERT statements for that table, maps the
legacy identifiers to canonical normalized episode/person IDs, and emits a
traceable cast-credit dataset plus reconciliation report.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CREDIT_NAMESPACE = uuid.UUID("ad8bd981-c6fd-5e6a-aa5f-1094eb9d42c4")
INSERT_RE = re.compile(r"^INSERT INTO `appear` VALUES\((.*)\);$")


def parse_values(payload: str) -> list[str]:
    """Parse one MySQL VALUES tuple using CSV quoting semantics.

    MySQL escapes a single quote inside a quoted string by doubling it. Replacing
    doubled quotes with a temporary sentinel lets Python's csv parser consume the
    row without interpreting commas embedded inside quoted text as separators.
    """
    sentinel = "\u0000QUOTE\u0000"
    cooked = payload.replace("''", sentinel)
    reader = csv.reader(io.StringIO(cooked), delimiter=",", quotechar="'", skipinitialspace=True)
    values = next(reader)
    return [value.replace(sentinel, "'").strip() for value in values]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cast_credit_id(appear_id: str) -> str:
    return str(uuid.uuid5(CREDIT_NAMESPACE, f"legacy-appear:{appear_id}"))


def source_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", type=Path, default=ROOT / "sql" / "cbs.sql")
    parser.add_argument("--episodes", type=Path, default=ROOT / "data" / "normalized" / "episodes.json")
    parser.add_argument("--people", type=Path, default=ROOT / "data" / "normalized" / "people.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "normalized" / "cast_credits.json")
    parser.add_argument("--report", type=Path, default=ROOT / "data" / "normalized" / "cast_credits.validation.json")
    args = parser.parse_args()

    episodes = load_json(args.episodes)
    people = load_json(args.people)

    episode_by_legacy = {
        str(record.get("legacy", {}).get("episode_id")): record["id"]
        for record in episodes
        if record.get("legacy", {}).get("episode_id") is not None
    }

    person_by_legacy: dict[str, str] = {}
    duplicate_person_ids: dict[str, list[str]] = {}
    for person in people:
        for legacy_id in person.get("legacy_cast_ids", []):
            legacy_id = str(legacy_id)
            if legacy_id in person_by_legacy and person_by_legacy[legacy_id] != person["id"]:
                duplicate_person_ids.setdefault(legacy_id, [person_by_legacy[legacy_id]]).append(person["id"])
            else:
                person_by_legacy[legacy_id] = person["id"]

    credits: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    parsed_rows = 0

    with args.sql.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            match = INSERT_RE.match(line)
            if not match:
                continue

            parsed_rows += 1
            try:
                values = parse_values(match.group(1))
            except Exception as exc:  # parser failure must remain visible
                issues.append({
                    "severity": "error",
                    "code": "APPEAR_PARSE_ERROR",
                    "line": line_number,
                    "message": str(exc),
                })
                continue

            if len(values) != 6:
                issues.append({
                    "severity": "error",
                    "code": "APPEAR_COLUMN_COUNT",
                    "line": line_number,
                    "actual": len(values),
                    "expected": 6,
                })
                continue

            appear_id, episode_id, episode_date, episode_name, cast_id, cast_handle = values
            canonical_episode_id = episode_by_legacy.get(episode_id)
            canonical_person_id = person_by_legacy.get(cast_id)

            if canonical_episode_id is None:
                issues.append({
                    "severity": "error",
                    "code": "UNKNOWN_EPISODE_ID",
                    "line": line_number,
                    "appear_id": appear_id,
                    "legacy_episode_id": episode_id,
                })
            if canonical_person_id is None:
                issues.append({
                    "severity": "error",
                    "code": "UNKNOWN_CAST_ID",
                    "line": line_number,
                    "appear_id": appear_id,
                    "legacy_cast_id": cast_id,
                    "legacy_handle": cast_handle,
                })
            if canonical_episode_id is None or canonical_person_id is None:
                continue

            credits.append({
                "id": cast_credit_id(appear_id),
                "episode_id": canonical_episode_id,
                "person_id": canonical_person_id,
                "character_name": None,
                "credit_order": None,
                "status": "reported",
                "legacy": {
                    "appear_id": int(appear_id) if appear_id.isdigit() else appear_id,
                    "episode_id": int(episode_id) if episode_id.isdigit() else episode_id,
                    "episode_date": episode_date or None,
                    "episode_name": episode_name or None,
                    "cast_id": int(cast_id) if cast_id.isdigit() else cast_id,
                    "cast_id_name": cast_handle or None,
                },
                "source": {
                    "artifact": "sql/cbs.sql",
                    "locator": f"line:{line_number}",
                    "sha256": source_hash(line),
                },
            })

    seen_pairs: dict[tuple[str, str], str] = {}
    for credit in credits:
        pair = (credit["episode_id"], credit["person_id"])
        if pair in seen_pairs:
            issues.append({
                "severity": "warning",
                "code": "DUPLICATE_EPISODE_PERSON_PAIR",
                "cast_credit_id": credit["id"],
                "first_cast_credit_id": seen_pairs[pair],
                "episode_id": credit["episode_id"],
                "person_id": credit["person_id"],
            })
        else:
            seen_pairs[pair] = credit["id"]

    for legacy_id, canonical_ids in sorted(duplicate_person_ids.items()):
        issues.append({
            "severity": "error",
            "code": "AMBIGUOUS_LEGACY_CAST_ID",
            "legacy_cast_id": legacy_id,
            "person_ids": sorted(set(canonical_ids)),
        })

    credits.sort(key=lambda item: (
        int(item["legacy"]["episode_id"]) if isinstance(item["legacy"]["episode_id"], int) else str(item["legacy"]["episode_id"]),
        int(item["legacy"]["appear_id"]) if isinstance(item["legacy"]["appear_id"], int) else str(item["legacy"]["appear_id"]),
    ))
    issues.sort(key=lambda item: (item["severity"], item["code"], item.get("line", 0), item.get("cast_credit_id", "")))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(credits, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = {
        "source": "sql/cbs.sql#appear",
        "parsed_rows": parsed_rows,
        "output_credits": len(credits),
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"parsed {parsed_rows} legacy appear rows")
    print(f"resolved {len(credits)} canonical cast credits")
    print(f"validation errors: {report['error_count']}; warnings: {report['warning_count']}")
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
