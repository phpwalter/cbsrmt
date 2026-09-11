#!/usr/bin/env python3
"""Validate canonical person records for structural and historical plausibility issues.

This validator never rewrites data. It reports conditions that require review.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--people", type=Path, default=Path("data/normalized/people.json"))
    parser.add_argument("--report", type=Path, default=Path("data/normalized/people.plausibility.json"))
    args = parser.parse_args()

    people = json.loads(args.people.read_text(encoding="utf-8"))
    findings: list[dict[str, Any]] = []

    for person in people:
        person_id = person.get("id")
        name = person.get("canonical_name") or ""
        born_raw = person.get("born_on")
        died_raw = person.get("died_on")
        born = parse_date(born_raw)
        died = parse_date(died_raw)

        if born_raw and born is None:
            findings.append({"severity": "error", "code": "INVALID_BIRTH_DATE", "person_id": person_id, "name": name, "value": born_raw})
        if died_raw and died is None:
            findings.append({"severity": "error", "code": "INVALID_DEATH_DATE", "person_id": person_id, "name": name, "value": died_raw})

        if born and died:
            if died < born:
                findings.append({"severity": "error", "code": "DEATH_BEFORE_BIRTH", "person_id": person_id, "name": name, "born_on": born_raw, "died_on": died_raw})
            else:
                age = (died - born).days / 365.2425
                if age < 10:
                    findings.append({"severity": "warning", "code": "IMPLAUSIBLY_SHORT_LIFESPAN", "person_id": person_id, "name": name, "born_on": born_raw, "died_on": died_raw, "approx_age": round(age, 1)})
                elif age > 115:
                    findings.append({"severity": "warning", "code": "IMPLAUSIBLY_LONG_LIFESPAN", "person_id": person_id, "name": name, "born_on": born_raw, "died_on": died_raw, "approx_age": round(age, 1)})

        if born and born.year < 1800:
            findings.append({"severity": "warning", "code": "BIRTH_YEAR_OUTLIER", "person_id": person_id, "name": name, "born_on": born_raw})
        if died and died.year > date.today().year:
            findings.append({"severity": "warning", "code": "FUTURE_DEATH_DATE", "person_id": person_id, "name": name, "died_on": died_raw})

        if not name.strip():
            findings.append({"severity": "error", "code": "EMPTY_CANONICAL_NAME", "person_id": person_id})

    findings.sort(key=lambda f: (f["severity"], f["code"], f.get("name", ""), str(f.get("person_id", ""))))
    summary = {
        "people_checked": len(people),
        "errors": sum(1 for f in findings if f["severity"] == "error"),
        "warnings": sum(1 for f in findings if f["severity"] == "warning"),
        "findings": findings,
    }

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
