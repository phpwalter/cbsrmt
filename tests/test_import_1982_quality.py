from pathlib import Path

from tools.import_1982_quality import scan_lines


def test_scan_lines_accepts_clean_rows():
    accepted, rejected = scan_lines([
        "1273 2711 820104 The Acquisition\n",
        "1274 2715 820108 The Last Orbit\n",
    ])
    assert len(accepted) == 2
    assert rejected == []
    assert accepted[0].source_line == 1
    assert accepted[1].source_line == 2


def test_scan_lines_quarantines_malformed_data_row():
    accepted, rejected = scan_lines([
        "1273 2711 820104 The Acquisition\n",
        "1274 2715 bad-date The Last Orbit\n",
        "1275 2719 820112 The Third Record\n",
    ])
    assert [row.show_number for row in accepted] == [1273, 1275]
    assert len(rejected) == 1
    assert rejected[0][0] == 2
    assert rejected[0][2] == "MALFORMED_ROW"


def test_scan_lines_rejects_duplicate_show_number():
    accepted, rejected = scan_lines([
        "1273 2711 820104 The Acquisition\n",
        "1273 2715 820108 The Last Orbit\n",
    ])
    assert len(accepted) == 1
    assert rejected[0][2] == "DUPLICATE_SHOW_NUMBER"


def test_scan_lines_rejects_duplicate_otrw_number():
    accepted, rejected = scan_lines([
        "1273 2711 820104 The Acquisition\n",
        "1274 2711 820108 The Last Orbit\n",
    ])
    assert len(accepted) == 1
    assert rejected[0][2] == "DUPLICATE_OTRW_NUMBER"


def test_repository_source_is_clean_if_present():
    path = Path("CBSRMT_Log_1982.txt")
    if not path.exists():
        return
    accepted, rejected = scan_lines(path.read_text(encoding="utf-8-sig").splitlines(keepends=True))
    assert len(accepted) == 127
    assert rejected == []
