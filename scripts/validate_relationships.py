#!/usr/bin/env python3
"""Validate referential integrity and duplicate semantics across normalized outputs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NORMALIZED = ROOT / "data" / "normalized"


def load(name: str):
    return json.loads((NORMALIZED / name).read_text(encoding="utf-8"))


def main() -> int:
    episodes = load("episodes.json")
    people = load("people.json")
    genres = load("genres.json")
    cast_credits = load("cast_credits.json")
    relationships = load("episode_relationships.json")

    episode_ids = {row["id"] for row in episodes}
    person_ids = {row["id"] for row in people}
    genre_ids = {row["id"] for row in genres}

    issues = []

    cast_ids = set()
    cast_pairs = set()
    for row in cast_credits:
        if row["id"] in cast_ids:
            issues.append({"severity": "error", "code": "DUPLICATE_CAST_CREDIT_ID", "id": row["id"]})
        cast_ids.add(row["id"])

        if row["episode_id"] not in episode_ids:
            issues.append({"severity": "error", "code": "CAST_UNKNOWN_EPISODE", "id": row["id"], "episode_id": row["episode_id"]})
        if row["person_id"] not in person_ids:
            issues.append({"severity": "error", "code": "CAST_UNKNOWN_PERSON", "id": row["id"], "person_id": row["person_id"]})

        pair = (row["episode_id"], row["person_id"])
        if pair in cast_pairs:
            issues.append({"severity": "warning", "code": "DUPLICATE_CAST_PAIR", "episode_id": pair[0], "person_id": pair[1]})
        cast_pairs.add(pair)

    for row in relationships:
        episode_id = row.get("episode_id")
        if episode_id not in episode_ids:
            issues.append({"severity": "error", "code": "RELATIONSHIP_UNKNOWN_EPISODE", "episode_id": episode_id})

        genre_id = row.get("genre_id")
        if genre_id is not None and genre_id not in genre_ids:
            issues.append({"severity": "error", "code": "RELATIONSHIP_UNKNOWN_GENRE", "episode_id": episode_id, "genre_id": genre_id})

        for credit in row.get("writers", []):
            person_id = credit.get("person_id")
            if person_id is not None and person_id not in person_ids:
                issues.append({"severity": "error", "code": "WRITER_UNKNOWN_PERSON", "episode_id": episode_id, "person_id": person_id})

    issues.sort(key=lambda issue: (issue["severity"], issue["code"], issue.get("id", ""), issue.get("episode_id", ""), issue.get("person_id", "")))
    report = {
        "episode_count": len(episodes),
        "people_count": len(people),
        "genre_count": len(genres),
        "cast_credit_count": len(cast_credits),
        "relationship_count": len(relationships),
        "error_count": sum(1 for issue in issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues,
    }

    (NORMALIZED / "relationships.validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"relationship validation errors: {report['error_count']}; warnings: {report['warning_count']}")
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
