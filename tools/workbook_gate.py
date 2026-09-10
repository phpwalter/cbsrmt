#!/usr/bin/env python3
"""Gate canonical workbook imports on reviewed, checksum-bound mappings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.validate_workbook_mapping import load_report, load_yaml, validate


def evaluate_gate(mapping_path: Path, workbook_path: Path, inspection_path: Path | None = None) -> dict[str, object]:
    mapping = load_yaml(mapping_path)
    report_path = inspection_path or Path(mapping["workbook"]["inspectionReport"])
    report = load_report(report_path)
    validate(mapping, report, workbook_path)

    approved_sheets = [
        sheet["sheetName"]
        for sheet in mapping.get("sheets", [])
        if sheet.get("status") == "APPROVED"
    ]

    return {
        "eligible": True,
        "workbook": workbook_path.name,
        "sha256": mapping["workbook"]["sha256"],
        "approvedSheets": approved_sheets,
        "mappingSchemaVersion": str(mapping["schemaVersion"]),
    }


# Backward-compatible alias for earlier callers/tests.
evaluate = evaluate_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--inspection", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        result = evaluate_gate(args.mapping, args.workbook, args.inspection)
    except Exception as exc:
        if args.json:
            print(json.dumps({"eligible": False, "reason": str(exc)}, indent=2))
        else:
            print(f"CANONICALIZATION GATE: BLOCKED - {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("CANONICALIZATION GATE: PASS")
        print(f"Workbook........ {result['workbook']}")
        print(f"SHA-256......... {result['sha256']}")
        print(f"Approved sheets. {', '.join(result['approvedSheets'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
