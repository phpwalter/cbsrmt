BEGIN;

CREATE SCHEMA IF NOT EXISTS governance;

CREATE TABLE IF NOT EXISTS governance.schema_migrations (
    migration_name text PRIMARY KEY,
    migration_checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by text NOT NULL DEFAULT current_user,
    CONSTRAINT schema_migrations_name_ck CHECK (btrim(migration_name) <> ''),
    CONSTRAINT schema_migrations_checksum_ck CHECK (migration_checksum ~ '^[0-9a-f]{64}$')
);

COMMENT ON TABLE governance.schema_migrations IS
    'Immutable ledger of applied migration filenames and SHA-256 checksums.';

COMMIT;
