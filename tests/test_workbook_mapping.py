from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from tools.validate_workbook_mapping import MappingError, validate
from tools.workbook_gate import evaluate


def make_workbook(tmp_path: Path) -> Path:
    path = tmp_path / "sample.xlsx"
    path.write_bytes(b"workbook-bytes")
    return path


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_for(path: Path) -> dict:
    return {
        "schemaVersion": "1.0",
        "fileName": path.name,
        "fileFormat": "xlsx",
        "sha256": checksum(path),
        "sheetCount": 1,
        "mappingStatus": "REVIEW_REQUIRED",
        "sheets": [
            {
                "sheetName": "Episodes",
                "headers": ["SHOW #", "Title"],
                "rowCount": 2,
                "columnCount": 2,
            }
        ],
    }


def approved_mapping(path: Path, inspection: Path) -> dict:
    return {
        "schemaVersion": 1.0,
        "workbook": {
            "fileName": path.name,
            "sha256": checksum(path),
            "inspectionReport": str(inspection),
            "status": "APPROVED",
            "approvedBy": "reviewer",
            "approvedAt": "2026-09-10T18:00:00-05:00",
        },
        "sheets": [
            {
                "sheetName": "Episodes",
                "headerRow": 1,
                "status": "APPROVED",
                "candidateEntity": "episode",
                "keyColumns": ["SHOW #"],
                "columns": [
                    {
                        "sourceHeader": "SHOW #",
                        "target": {"entity": "episode", "field": "canonical_number"},
                        "transform": "integer",
                        "required": True,
                        "provenance": "preserve_raw_and_normalized",
                    },
                    {
                        "sourceHeader": "Title",
                        "target": {"entity": "episode", "field": "title"},
                        "transform": "trim",
                        "required": True,
                        "provenance": "preserve_raw_and_normalized",
                    },
                ],
            }
        ],
    }


def test_approved_mapping_validates(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    report = report_for(workbook)
    mapping = approved_mapping(workbook, tmp_path / "inspection.json")
    validate(mapping, report, workbook)


def test_review_required_mapping_is_blocked(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    report = report_for(workbook)
    mapping = approved_mapping(workbook, tmp_path / "inspection.json")
    mapping["workbook"]["status"] = "REVIEW_REQUIRED"
    with pytest.raises(MappingError, match="not APPROVED"):
        validate(mapping, report, workbook)


def test_checksum_drift_is_blocked(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    report = report_for(workbook)
    mapping = approved_mapping(workbook, tmp_path / "inspection.json")
    workbook.write_bytes(b"changed")
    with pytest.raises(MappingError, match="source workbook checksum"):
        validate(mapping, report, workbook)


def test_unknown_header_is_blocked(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    report = report_for(workbook)
    mapping = approved_mapping(workbook, tmp_path / "inspection.json")
    mapping["sheets"][0]["columns"][0]["sourceHeader"] = "Unknown"
    with pytest.raises(MappingError, match="source header"):
        validate(mapping, report, workbook)


def test_duplicate_target_is_blocked(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    report = report_for(workbook)
    mapping = approved_mapping(workbook, tmp_path / "inspection.json")
    mapping["sheets"][0]["columns"][1]["target"] = {
        "entity": "episode",
        "field": "canonical_number",
    }
    with pytest.raises(MappingError, match="duplicate target"):
        validate(mapping, report, workbook)


def test_approved_workbook_requires_approved_sheet(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    report = report_for(workbook)
    mapping = approved_mapping(workbook, tmp_path / "inspection.json")
    mapping["sheets"][0]["status"] = "IGNORED"
    with pytest.raises(MappingError, match="at least one APPROVED sheet"):
        validate(mapping, report, workbook)


def test_gate_returns_checksum_bound_decision(tmp_path: Path) -> None:
    workbook = make_workbook(tmp_path)
    inspection = tmp_path / "inspection.json"
    inspection.write_text(json.dumps(report_for(workbook)), encoding="utf-8")
    mapping_path = tmp_path / "mapping.yaml"
    mapping_path.write_text(yaml.safe_dump(approved_mapping(workbook, inspection)), encoding="utf-8")

    result = evaluate(mapping_path, workbook)
    assert result["eligible"] is True
    assert result["workbook"] == "sample.xlsx"
    assert result["approvedSheets"] == ["Episodes"]
