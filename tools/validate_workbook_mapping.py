#!/usr/bin/env python3
"""Validate a reviewed workbook mapping against its inspection report and source checksum."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ALLOWED_MAPPING_STATUS = {"REVIEW_REQUIRED", "APPROVED", "REJECTED"}
ALLOWED_SHEET_STATUS = {"REVIEW_REQUIRED", "APPROVED", "IGNORED", "REJECTED"}
ALLOWED_TRANSFORMS = {
    "identity",
    "trim",
    "integer",
    "decimal",
    "date",
    "datetime",
    "boolean",
    "split_names",
    "normalize_name",
}
ALLOWED_PROVENANCE = {"preserve_raw", "preserve_raw_and_normalized"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class MappingError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MappingError(message)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "mapping root must be an object")
    return data


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "inspection report root must be an object")
    return data


def validate_approval_metadata(workbook: dict[str, Any]) -> None:
    approved_by = workbook.get("approvedBy")
    approved_at = workbook.get("approvedAt")
    require(isinstance(approved_by, str) and approved_by.strip(), "APPROVED mapping requires workbook.approvedBy")
    require(isinstance(approved_at, str) and approved_at.strip(), "APPROVED mapping requires workbook.approvedAt")
    try:
        parsed = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MappingError("workbook.approvedAt must be ISO-8601") from exc
    require(parsed.tzinfo is not None, "workbook.approvedAt must include a timezone offset")


def validate(mapping: dict[str, Any], report: dict[str, Any], workbook_path: Path | None = None) -> None:
    require(str(mapping.get("schemaVersion")) == "1.0", "unsupported mapping schemaVersion")
    workbook = mapping.get("workbook")
    require(isinstance(workbook, dict), "workbook section is required")

    status = workbook.get("status")
    require(status in ALLOWED_MAPPING_STATUS, f"invalid workbook status: {status!r}")
    require(status == "APPROVED", "workbook mapping is not APPROVED")
    validate_approval_metadata(workbook)

    expected_name = workbook.get("fileName")
    expected_sha = workbook.get("sha256")
    require(isinstance(expected_name, str) and expected_name.strip(), "workbook.fileName is required")
    require(isinstance(expected_sha, str) and SHA256_RE.fullmatch(expected_sha) is not None, "workbook.sha256 must be a lowercase 64-character SHA-256")
    require(report.get("fileName") == expected_name, "inspection report fileName does not match mapping")
    require(report.get("sha256") == expected_sha, "inspection report checksum does not match mapping")

    if workbook_path is not None:
        require(workbook_path.name == expected_name, "source workbook filename does not match approved mapping")
        require(sha256(workbook_path) == expected_sha, "source workbook checksum does not match approved mapping")

    report_sheets = {sheet["sheetName"]: sheet for sheet in report.get("sheets", [])}
    mappings = mapping.get("sheets")
    require(isinstance(mappings, list) and mappings, "at least one sheet mapping is required")

    approved_sheet_count = 0
    for sheet in mappings:
        require(isinstance(sheet, dict), "sheet mapping must be an object")
        sheet_name = sheet.get("sheetName")
        sheet_status = sheet.get("status")
        require(sheet_status in ALLOWED_SHEET_STATUS, f"invalid sheet status for {sheet_name!r}")
        require(sheet_name in report_sheets, f"mapped sheet not present in inspection report: {sheet_name!r}")

        if sheet_status != "APPROVED":
            continue
        approved_sheet_count += 1
        require(isinstance(sheet.get("headerRow"), int) and sheet["headerRow"] > 0, f"{sheet_name}: headerRow must be positive")

        candidate_entity = sheet.get("candidateEntity")
        require(
            isinstance(candidate_entity, str) and candidate_entity.strip(),
            f"{sheet_name}: candidateEntity is required for an APPROVED sheet",
        )

        report_headers = set(report_sheets[sheet_name].get("headers", []))
        key_columns = sheet.get("keyColumns", [])
        require(isinstance(key_columns, list), f"{sheet_name}: keyColumns must be a list")
        for key in key_columns:
            require(key in report_headers, f"{sheet_name}: key column {key!r} not found in inspected headers")

        columns = sheet.get("columns", [])
        require(isinstance(columns, list) and columns, f"{sheet_name}: approved sheet must map at least one column")
        seen_sources: set[str] = set()
        seen_targets: set[tuple[str, str]] = set()
        mapped_entities: set[str] = set()

        for column in columns:
            require(isinstance(column, dict), f"{sheet_name}: column mapping must be an object")
            source_header = column.get("sourceHeader")
            require(source_header in report_headers, f"{sheet_name}: source header {source_header!r} not found")
            require(source_header not in seen_sources, f"{sheet_name}: duplicate source header mapping {source_header!r}")
            seen_sources.add(source_header)

            target = column.get("target")
            require(isinstance(target, dict), f"{sheet_name}/{source_header}: target is required")
            entity = target.get("entity")
            field = target.get("field")
            require(isinstance(entity, str) and entity.strip(), f"{sheet_name}/{source_header}: target.entity is required")
            require(isinstance(field, str) and field.strip(), f"{sheet_name}/{source_header}: target.field is required")
            mapped_entities.add(entity)
            target_key = (entity, field)
            require(target_key not in seen_targets, f"{sheet_name}: duplicate target mapping {entity}.{field}")
            seen_targets.add(target_key)

            transform = column.get("transform", "identity")
            require(transform in ALLOWED_TRANSFORMS, f"{sheet_name}/{source_header}: unsupported transform {transform!r}")
            provenance = column.get("provenance")
            require(provenance in ALLOWED_PROVENANCE, f"{sheet_name}/{source_header}: invalid provenance policy")
            require(isinstance(column.get("required", False), bool), f"{sheet_name}/{source_header}: required must be boolean")

        require(
            candidate_entity in mapped_entities,
            f"{sheet_name}: candidateEntity {candidate_entity!r} is not among mapped target entities",
        )

    require(approved_sheet_count > 0, "APPROVED workbook must contain at least one APPROVED sheet")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--inspection", type=Path)
    parser.add_argument("--workbook", type=Path)
    args = parser.parse_args(argv)

    try:
        mapping = load_yaml(args.mapping)
        inspection_path = args.inspection or Path(mapping["workbook"]["inspectionReport"])
        report = load_report(inspection_path)
        validate(mapping, report, args.workbook)
    except Exception as exc:
        print(f"MAPPING VALIDATION: FAIL - {exc}", file=sys.stderr)
        return 1

    print("MAPPING VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
