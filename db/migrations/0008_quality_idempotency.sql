BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS quality_issues_import_identity_uq
    ON quality.issues (
        import_batch_id,
        COALESCE(source_line, 0),
        severity,
        issue_code,
        COALESCE(field_name, ''),
        COALESCE(raw_value, ''),
        message
    );

CREATE UNIQUE INDEX IF NOT EXISTS quality_quarantine_import_identity_uq
    ON quality.quarantine (
        import_batch_id,
        COALESCE(source_line, 0),
        record_type,
        issue_code,
        raw_record,
        severity
    );

COMMIT;
