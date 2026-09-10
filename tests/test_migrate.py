from pathlib import Path

import pytest

from tools.migrate import (
    execution_sql,
    sha256_text,
    strip_sql_literals_and_comments,
    validate_migration_files,
)


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_execution_sql_strips_outer_transaction_wrapper(tmp_path: Path):
    path = write(tmp_path, "0001_test.sql", "BEGIN;\nCREATE TABLE example(id int);\nCOMMIT;\n")
    assert execution_sql(path) == "CREATE TABLE example(id int);"


def test_execution_sql_allows_migration_without_wrapper(tmp_path: Path):
    path = write(tmp_path, "0001_test.sql", "CREATE TABLE example(id int);\n")
    assert execution_sql(path) == "CREATE TABLE example(id int);"


def test_execution_sql_rejects_unpaired_wrapper(tmp_path: Path):
    path = write(tmp_path, "0001_test.sql", "BEGIN;\nCREATE TABLE example(id int);\n")
    with pytest.raises(RuntimeError, match="both outer BEGIN and COMMIT"):
        execution_sql(path)


def test_execution_sql_rejects_embedded_transaction_control(tmp_path: Path):
    path = write(
        tmp_path,
        "0001_test.sql",
        "BEGIN;\nCREATE TABLE example(id int);\nSAVEPOINT unsafe;\nCOMMIT;\n",
    )
    with pytest.raises(RuntimeError, match="embedded transaction control"):
        execution_sql(path)


def test_transaction_words_inside_literals_comments_and_dollar_blocks_are_ignored(tmp_path: Path):
    sql = """BEGIN;
-- COMMIT ROLLBACK SAVEPOINT
CREATE TABLE example(note text);
INSERT INTO example(note) VALUES ('BEGIN COMMIT ROLLBACK');
DO $$
BEGIN
    RAISE NOTICE 'COMMIT';
END
$$;
COMMIT;
"""
    path = write(tmp_path, "0001_test.sql", sql)
    body = execution_sql(path)
    assert "CREATE TABLE example" in body
    assert "DO $$" in body


def test_strip_sql_literals_and_comments_preserves_real_keywords_only():
    masked = strip_sql_literals_and_comments(
        "SELECT 'COMMIT'; -- ROLLBACK\n/* SAVEPOINT */ SELECT 1;"
    )
    assert "COMMIT" not in masked
    assert "ROLLBACK" not in masked
    assert "SAVEPOINT" not in masked
    assert "SELECT" in masked


def test_validate_migration_files_requires_sequence_name(tmp_path: Path):
    valid = write(tmp_path, "0001_valid.sql", "SELECT 1;")
    validate_migration_files([valid])

    invalid = write(tmp_path, "migration.sql", "SELECT 1;")
    with pytest.raises(RuntimeError, match="invalid migration filenames"):
        validate_migration_files([invalid])


def test_validate_migration_files_rejects_duplicate_sequence(tmp_path: Path):
    first = write(tmp_path, "0001_first.sql", "SELECT 1;")
    second = write(tmp_path, "0001_second.sql", "SELECT 2;")
    with pytest.raises(RuntimeError, match="duplicate migration sequence"):
        validate_migration_files([first, second])


def test_checksum_uses_original_bytes_not_execution_body(tmp_path: Path):
    path = write(tmp_path, "0001_test.sql", "BEGIN;\nSELECT 1;\nCOMMIT;\n")
    checksum_before = sha256_text(path)
    assert execution_sql(path) == "SELECT 1;"
    assert sha256_text(path) == checksum_before
