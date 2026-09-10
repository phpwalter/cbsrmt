from datetime import date
from pathlib import Path

import pytest

from tools.import_1982 import parse_log, parse_source_date, validate_records


def test_parse_source_date():
    assert parse_source_date("820104") == date(1982, 1, 4)


def test_parse_source_date_rejects_wrong_year():
    with pytest.raises(ValueError, match="unexpected year"):
        parse_source_date("810104")


def test_parse_log_extracts_record():
    rows = list(parse_log(["1273\t2711\t820104\tThe Acquisition\n"]))
    assert len(rows) == 1
    row = rows[0]
    assert row.show_number == 1273
    assert row.otrw_number == 2711
    assert row.broadcast_date == date(1982, 1, 4)
    assert row.normalized_title == "The Acquisition"


def test_parse_log_ignores_header_text():
    rows = list(parse_log(["CBS Radio Mystery Theater\n", "Show # OTRW # Date Episode Title\n"]))
    assert rows == []


def test_parse_log_rejects_malformed_data_row():
    with pytest.raises(ValueError, match="malformed data row"):
        list(parse_log(["1273 2711 bad-date The Acquisition\n"]))


def test_validate_records_rejects_duplicate_show_number():
    rows = list(
        parse_log(
            [
                "1273 2711 820104 The Acquisition\n",
                "1273 2715 820108 The Last Orbit\n",
            ]
        )
    )
    with pytest.raises(ValueError, match="duplicate SHOW"):
        validate_records(rows)


def test_validate_records_rejects_duplicate_otrw_number():
    rows = list(
        parse_log(
            [
                "1273 2711 820104 The Acquisition\n",
                "1274 2711 820108 The Last Orbit\n",
            ]
        )
    )
    with pytest.raises(ValueError, match="duplicate OTRW"):
        validate_records(rows)


def test_repository_1982_log_parses_if_present():
    path = Path("CBSRMT_Log_1982.txt")
    if not path.exists():
        pytest.skip("repository source file not available")

    with path.open("r", encoding="utf-8-sig") as handle:
        rows = list(parse_log(handle))
    validate_records(rows)

    assert rows[0].show_number == 1273
    assert rows[0].otrw_number == 2711
    assert rows[0].broadcast_date == date(1982, 1, 4)
    assert rows[-1].show_number == 1399
    assert rows[-1].broadcast_date == date(1982, 12, 7)
