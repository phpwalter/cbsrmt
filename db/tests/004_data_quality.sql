BEGIN;

DO $$
DECLARE
    batch_id uuid;
    source_id uuid;
BEGIN
    SELECT b.import_batch_id, b.source_id
      INTO batch_id, source_id
      FROM provenance.import_batches AS b
     ORDER BY b.started_at
     LIMIT 1;

    IF batch_id IS NULL THEN
        RAISE EXCEPTION 'Expected at least one import batch for data-quality test';
    END IF;

    BEGIN
        INSERT INTO quality.issues (
            import_batch_id, source_id, severity, issue_code, message
        ) VALUES (
            batch_id, source_id, 'INVALID', 'TEST_INVALID_SEVERITY', 'must fail'
        );
        RAISE EXCEPTION 'Invalid quality severity was accepted';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;

    BEGIN
        INSERT INTO quality.quarantine (
            import_batch_id, source_id, record_type, issue_code,
            raw_record, severity
        ) VALUES (
            batch_id, source_id, 'broadcast_log', 'TEST_WARNING',
            'test record', 'WARNING'
        );
        RAISE EXCEPTION 'WARNING severity was accepted into quarantine';
    EXCEPTION
        WHEN check_violation THEN
            NULL;
    END;
END
$$;

ROLLBACK;
