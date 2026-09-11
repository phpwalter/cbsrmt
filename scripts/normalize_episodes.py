#!/usr/bin/env python3
"""Normalize the legacy episode catalog into a deterministic canonical export."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data" / "episodes.json"
OUTPUT_PATH = ROOT / "data" / "normalized" / "episodes.json"
REPORT_PATH = ROOT / "data" / "normalized" / "episodes.validation.json"

# Namespace is project-specific and must remain unchanged after canonical IDs are published.
CBS_RMT_NAMESPACE = uuid.UUID("646a1d8f-b1f5-5df3-9e06-44f9508c8d0a")
WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value))
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text or None


def parse_episode_number(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        number = int(text)
    except ValueError as exc:
        raise ValueError(f"invalid episode number: {value!r}") from exc
    if number < 1:
        raise ValueError(f"episode number must be positive: {number}")
    return number


def parse_date(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValueError(f"invalid ISO episode date: {value!r}") from exc


def episode_uuid(episode_number: int | None, title: str) -> str:
    if episode_number is not None:
        key = f"episode:number:{episode_number}"
    else:
        key = f"episode:title:{title.casefold()}"
    return str(uuid.uuid5(CBS_RMT_NAMESPACE, key))


def normalize_record(raw: dict[str, Any], index: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []

    try:
        number = parse_episode_number(raw.get("episode_id"))
    except ValueError as exc:
        issues.append({"record_index": index, "severity": "error", "field": "episode_id", "message": str(exc)})
        number = None

    title = clean_text(raw.get("episode_name"))
    if title is None:
        issues.append({"record_index": index, "severity": "error", "field": "episode_name", "message": "episode title is empty"})

    try:
        air_date = parse_date(raw.get("episode_date"))
    except ValueError as exc:
        issues.append({"record_index": index, "severity": "error", "field": "episode_date", "message": str(exc)})
        air_date = None

    writer_source = clean_text(raw.get("episode_writer"))
    original_writer_source = clean_text(raw.get("origwriter"))
    genre_source_id = clean_text(raw.get("genre_id"))

    if title is None or any(issue["severity"] == "error" and issue["field"] in {"episode_id", "episode_name"} for issue in issues):
        return None, issues

    normalized = {
        "id": episode_uuid(number, title),
        "episode_number": number,
        "title": title,
        "original_air_date": air_date,
        "synopsis": clean_text(raw.get("episode_plot")),
        "status": "reported",
        "legacy": {
            "episode_id": clean_text(raw.get("episode_id")),
            "writer_text": writer_source,
            "original_writer_text": original_writer_source,
            "genre_id": genre_source_id,
        },
        "source": {
            "artifact": "data/episodes.json",
            "locator": f"/{index}",
        },
    }

    return normalized, issues


def main() -> int:
    raw_records = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw_records, list):
        raise TypeError("data/episodes.json must contain a JSON array")

    normalized_records: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    seen_numbers: dict[int, int] = {}
    seen_ids: dict[str, int] = {}

    for index, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            issues.append({"record_index": index, "severity": "error", "field": "$", "message": "record is not an object"})
            continue

        record, record_issues = normalize_record(raw, index)
        issues.extend(record_issues)
        if record is None:
            continue

        number = record["episode_number"]
        if number is not None:
            if number in seen_numbers:
                issues.append(
                    {
                        "record_index": index,
                        "severity": "error",
                        "field": "episode_id",
                        "message": f"duplicate episode number {number}; first seen at record {seen_numbers[number]}",
                    }
                )
            else:
                seen_numbers[number] = index

        canonical_id = record["id"]
        if canonical_id in seen_ids:
            issues.append(
                {
                    "record_index": index,
                    "severity": "error",
                    "field": "id",
                    "message": f"duplicate canonical id; first seen at record {seen_ids[canonical_id]}",
                }
            )
        else:
            seen_ids[canonical_id] = index

        normalized_records.append(record)

    normalized_records.sort(key=lambda item: (item["episode_number"] is None, item["episode_number"] or 0, item["title"].casefold()))
    issues.sort(key=lambda item: (item["record_index"], item["severity"], item["field"], item["message"]))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(normalized_records, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    report = {
        "source": "data/episodes.json",
        "input_records": len(raw_records),
        "output_records": len(normalized_records),
        "error_count": error_count,
        "warning_count": sum(1 for issue in issues if issue["severity"] == "warning"),
        "issues": issues,
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"normalized {len(normalized_records)} of {len(raw_records)} episode records")
    print(f"validation errors: {error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
