from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from openpyxl import Workbook

from tools.inspect_workbook import _xls_cell_value, inspect, inspect_matrix
from tools.stage_workbook import assert_mapping_allows_canonicalization, _column_letter


def test_inspect_matrix_detects_candidate_key_and_blanks():
    report = inspect_matrix(
        "Episodes",
        [
            ["SHOW #", "Title", "Air Date"],
            [1273, "The Acquisition", "1982-01-04"],
            [1274, "The Last Orbit", "1982-01-08"],
        ],
    )

    assert report["rowCount"] == 3
    assert report["columnCount"] == 3
    assert report["columns"][0]["candidateKey"] is True
    assert report["columns"][1]["blankPercent"] == 0.0


def test_inspect_xlsx_reports_sheets_formulas_and_merged_ranges(tmp_path: Path):
    path = tmp_path / "sample.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Episodes"
    sheet.append(["SHOW #", "Title", "Total"])
    sheet.append([1273, "The Acquisition", "=A2+1"])
    sheet.merge_cells("A4:B4")
    workbook.save(path)

    report = inspect(path)

    assert report["fileFormat"] == "xlsx"
    assert report["sheetCount"] == 1
    assert report["mappingStatus"] == "REVIEW_REQUIRED"
    assert report["sheets"][0]["sheetName"] == "Episodes"
    assert report["sheets"][0]["formulaCount"] == 1
    assert "A4:B4" in report["sheets"][0]["mergedRanges"]


def test_xls_cell_conversion_preserves_typed_values():
    xlrd = SimpleNamespace(
        XL_CELL_EMPTY=0,
        XL_CELL_TEXT=1,
        XL_CELL_NUMBER=2,
        XL_CELL_DATE=3,
        XL_CELL_BOOLEAN=4,
        XL_CELL_ERROR=5,
        xldate_as_datetime=lambda value, datemode: datetime(1982, 1, 4),
    )

    assert _xls_cell_value(SimpleNamespace(ctype=0, value=""), 0, xlrd) is None
    assert _xls_cell_value(SimpleNamespace(ctype=3, value=29954.0), 0, xlrd).isoformat() == "1982-01-04"
    assert _xls_cell_value(SimpleNamespace(ctype=4, value=1), 0, xlrd) is True
    assert _xls_cell_value(SimpleNamespace(ctype=5, value=7), 0, xlrd) == "#XLERROR:7"
    assert _xls_cell_value(SimpleNamespace(ctype=2, value=1273.0), 0, xlrd) == 1273.0
    assert _xls_cell_value(SimpleNamespace(ctype=1, value="The Acquisition"), 0, xlrd) == "The Acquisition"


def test_mapping_guard_rejects_missing_or_unapproved_mapping():
    with pytest.raises(RuntimeError, match="requires a reviewed mapping"):
        assert_mapping_allows_canonicalization(None)

    with pytest.raises(RuntimeError, match="canonicalization blocked"):
        assert_mapping_allows_canonicalization(
            {"workbook": {"status": "REVIEW_REQUIRED"}}
        )


def test_mapping_guard_accepts_approved_mapping():
    assert_mapping_allows_canonicalization({"workbook": {"status": "APPROVED"}})


def test_column_letter_conversion():
    assert _column_letter(1) == "A"
    assert _column_letter(26) == "Z"
    assert _column_letter(27) == "AA"
    assert _column_letter(52) == "AZ"
    assert _column_letter(53) == "BA"
