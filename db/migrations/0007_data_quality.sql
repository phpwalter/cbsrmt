BEGIN;

CREATE SCHEMA IF NOT EXISTS quality;

CREATE TABLE IF NOT EXISTS quality.issues (
    issue_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id uuid REFERENCES provenance.import_batches(import_batch_id) ON DELETE CASCADE,
    source_id uuid REFERENCES provenance.sources(source_id) ON DELETE RESTRICT,
    entity_type text,
    entity_id uuid,
    source_line integer,
    severity text NOT NULL,
    issue_code text NOT NULL,
    field_name text,
    raw_value text,
    normalized_value text,
    message text NOT NULL,
    resolution_status text NOT NULL DEFAULT 'open',
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    CONSTRAINT quality_issue_severity_ck CHECK (severity IN ('INFO','WARNING','ERROR','FATAL')),
    CONSTRAINT quality_issue_resolution_ck CHECK (resolution_status IN ('open','accepted','corrected','rejected','ignored')),
    CONSTRAINT quality_issue_code_nonempty_ck CHECK (btrim(issue_code) <> ''),
    CONSTRAINT quality_issue_message_nonempty_ck CHECK (btrim(message) <> ''),
    CONSTRAINT quality_issue_source_line_ck CHECK (source_line IS NULL OR source_line > 0)
);

CREATE INDEX IF NOT EXISTS quality_issues_batch_idx ON quality.issues(import_batch_id);
CREATE INDEX IF NOT EXISTS quality_issues_entity_idx ON quality.issues(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS quality_issues_severity_idx ON quality.issues(severity, resolution_status);

CREATE TABLE IF NOT EXISTS quality.quarantine (
    quarantine_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id uuid NOT NULL REFERENCES provenance.import_batches(import_batch_id) ON DELETE CASCADE,
    source_id uuid REFERENCES provenance.sources(source_id) ON DELETE RESTRICT,
    source_line integer,
    record_type text NOT NULL,
    issue_code text NOT NULL,
    raw_record text NOT NULL,
    parsed_payload jsonb,
    severity text NOT NULL,
    resolution_status text NOT NULL DEFAULT 'open',
    resolution_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    CONSTRAINT quarantine_severity_ck CHECK (severity IN ('ERROR','FATAL')),
    CONSTRAINT quarantine_resolution_ck CHECK (resolution_status IN ('open','accepted','corrected','rejected','ignored')),
    CONSTRAINT quarantine_source_line_ck CHECK (source_line IS NULL OR source_line > 0),
    CONSTRAINT quarantine_record_type_nonempty_ck CHECK (btrim(record_type) <> ''),
    CONSTRAINT quarantine_issue_code_nonempty_ck CHECK (btrim(issue_code) <> '')
);

CREATE INDEX IF NOT EXISTS quarantine_batch_idx ON quality.quarantine(import_batch_id);
CREATE INDEX IF NOT EXISTS quarantine_status_idx ON quality.quarantine(resolution_status, severity);

COMMENT ON TABLE quality.issues IS
    'Data-quality findings generated during staging, normalization, reconciliation, or manual review.';
COMMENT ON TABLE quality.quarantine IS
    'Rejected or blocked source records preserved verbatim for later review; these records must not enter the canonical catalog until resolved.';

COMMIT;
