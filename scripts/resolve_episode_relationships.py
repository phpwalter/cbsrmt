#!/usr/bin/env python3
"""Resolve normalized episode writer and genre source values into relationships.

The resolver is intentionally conservative. Exact normalized-name matches are
accepted automatically. Ambiguous or missing matches are emitted to a review
report and are not guessed.
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


def clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(unicodedata.normalize("NFC", str(value)).strip().split())


def key(value: Any) -> str:
    return clean(value).casefold()


def load(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"Expected array in {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=Path, default=Path("data/normalized/episodes.json"))
    parser.add_argument("--people", type=Path, default=Path("data/normalized/people.json"))
    parser.add_argument("--genres", type=Path, default=Path("data/normalized/genres.json"))
    parser.add_argument("--output", type=Path, default=Path("data/normalized/episode_relationships.json"))
    parser.add_argument("--report", type=Path, default=Path("data/normalized/episode_relationships.validation.json"))
    args = parser.parse_args()

    episodes = load(args.episodes)
    people = load(args.people)
    genres = load(args.genres)

    people_index: dict[str, list[str]] = defaultdict(list)
    for person in people:
        names = {person.get("canonical_name") or ""}
        names.update(person.get("aliases") or [])
        for name in names:
            if clean(name):
                people_index[key(name)].append(person["id"])

    genre_index: dict[str, list[str]] = defaultdict(list)
    legacy_genre_index: dict[str, list[str]] = defaultdict(list)
    for genre in genres:
        if clean(genre.get("name")):
            genre_index[key(genre["name"])].append(genre["id"])
        for legacy_id in genre.get("legacy_genre_ids") or []:
            legacy_genre_index[clean(legacy_id)].append(genre["id"])

    relationships: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for episode in episodes:
        episode_id = episode["id"]
        resolved: dict[str, Any] = {
            "episode_id": episode_id,
            "writer_credits": [],
            "genre_ids": [],
        }

        writer_text = clean(episode.get("source_writer"))
        if writer_text:
            matches = sorted(set(people_index.get(key(writer_text), [])))
            if len(matches) == 1:
                resolved["writer_credits"].append({
                    "person_id": matches[0],
                    "credit_type": "writer",
                    "source_value": writer_text,
                    "status": "reported",
                })
            elif len(matches) == 0:
                warnings.append({
                    "code": "WRITER_NOT_FOUND",
                    "episode_id": episode_id,
                    "source_value": writer_text,
                })
            else:
                warnings.append({
                    "code": "WRITER_AMBIGUOUS",
                    "episode_id": episode_id,
                    "source_value": writer_text,
                    "candidate_person_ids": matches,
                })

        original_writer = clean(episode.get("source_original_writer"))
        if original_writer:
            matches = sorted(set(people_index.get(key(original_writer), [])))
            if len(matches) == 1:
                resolved["writer_credits"].append({
                    "person_id": matches[0],
                    "credit_type": "source_author",
                    "source_value": original_writer,
                    "status": "reported",
                })
            elif len(matches) == 0:
                warnings.append({
                    "code": "SOURCE_AUTHOR_NOT_FOUND",
                    "episode_id": episode_id,
                    "source_value": original_writer,
                })
            else:
                warnings.append({
                    "code": "SOURCE_AUTHOR_AMBIGUOUS",
                    "episode_id": episode_id,
                    "source_value": original_writer,
                    "candidate_person_ids": matches,
                })

        source_genre_id = clean(episode.get("source_genre_id"))
        if source_genre_id:
            matches = sorted(set(legacy_genre_index.get(source_genre_id, [])))
            if len(matches) == 1:
                resolved["genre_ids"].append(matches[0])
            elif len(matches) == 0:
                warnings.append({
                    "code": "GENRE_NOT_FOUND",
                    "episode_id": episode_id,
                    "source_genre_id": source_genre_id,
                })
            else:
                warnings.append({
                    "code": "GENRE_AMBIGUOUS",
                    "episode_id": episode_id,
                    "source_genre_id": source_genre_id,
                    "candidate_genre_ids": matches,
                })

        resolved["writer_credits"].sort(key=lambda x: (x["credit_type"], x["person_id"]))
        resolved["genre_ids"] = sorted(set(resolved["genre_ids"]))
        relationships.append(resolved)

    relationships.sort(key=lambda row: row["episode_id"])
    warnings.sort(key=lambda w: (w["code"], w["episode_id"], w.get("source_value", ""), w.get("source_genre_id", "")))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(relationships, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps({"warnings": warnings}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
