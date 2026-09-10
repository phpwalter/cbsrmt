BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS provenance;
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS catalog.episodes (
    episode_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_number integer,
    title text NOT NULL,
    subtitle text,
    synopsis text,
    original_air_date date,
    duration_seconds integer CHECK (duration_seconds IS NULL OR duration_seconds > 0),
    series_name text NOT NULL DEFAULT 'CBS Radio Mystery Theater',
    verification_status text NOT NULL DEFAULT 'unverified',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT episodes_canonical_number_positive CHECK (canonical_number IS NULL OR canonical_number > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS episodes_canonical_number_uq
    ON catalog.episodes (canonical_number)
    WHERE canonical_number IS NOT NULL;

CREATE TABLE IF NOT EXISTS catalog.broadcasts (
    broadcast_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id uuid NOT NULL REFERENCES catalog.episodes (episode_id) ON DELETE RESTRICT,
    broadcast_at timestamptz,
    broadcast_date date,
    broadcast_type text NOT NULL DEFAULT 'unknown',
    verification_status text NOT NULL DEFAULT 'unverified',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT broadcasts_type_ck CHECK (broadcast_type IN ('original','rerun','unknown')),
    CONSTRAINT broadcasts_temporal_ck CHECK (broadcast_at IS NOT NULL OR broadcast_date IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS broadcasts_episode_idx ON catalog.broadcasts (episode_id);
CREATE INDEX IF NOT EXISTS broadcasts_date_idx ON catalog.broadcasts (broadcast_date);

CREATE TABLE IF NOT EXISTS catalog.people (
    person_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name text NOT NULL,
    given_name text,
    middle_name text,
    family_name text,
    suffix text,
    birth_date date,
    death_date date,
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT people_lifespan_ck CHECK (birth_date IS NULL OR death_date IS NULL OR death_date >= birth_date)
);

CREATE TABLE IF NOT EXISTS catalog.credit_roles (
    credit_role_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL UNIQUE,
    name text NOT NULL UNIQUE,
    description text
);

INSERT INTO catalog.credit_roles (code, name, description)
VALUES
    ('actor', 'Actor', 'Performance credit'),
    ('writer', 'Writer', 'Original or episode writing credit'),
    ('adapter', 'Adapter', 'Adaptation credit'),
    ('director', 'Director', 'Episode direction credit'),
    ('producer', 'Producer', 'Production credit'),
    ('host', 'Host', 'Program host credit'),
    ('announcer', 'Announcer', 'Announcer credit'),
    ('composer', 'Composer', 'Music composition credit'),
    ('sound', 'Sound', 'Sound production credit')
ON CONFLICT (code) DO NOTHING;

CREATE TABLE IF NOT EXISTS catalog.episode_credits (
    episode_credit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id uuid NOT NULL REFERENCES catalog.episodes (episode_id) ON DELETE CASCADE,
    person_id uuid NOT NULL REFERENCES catalog.people (person_id) ON DELETE RESTRICT,
    credit_role_id uuid NOT NULL REFERENCES catalog.credit_roles (credit_role_id) ON DELETE RESTRICT,
    character_name text,
    billing_order integer CHECK (billing_order IS NULL OR billing_order > 0),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS episode_credits_episode_idx ON catalog.episode_credits (episode_id);
CREATE INDEX IF NOT EXISTS episode_credits_person_idx ON catalog.episode_credits (person_id);

CREATE TABLE IF NOT EXISTS provenance.sources (
    source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type text NOT NULL,
    name text NOT NULL,
    description text,
    uri text,
    license text,
    retrieved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_type, name)
);

CREATE TABLE IF NOT EXISTS provenance.import_batches (
    import_batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES provenance.sources (source_id) ON DELETE RESTRICT,
    source_checksum text NOT NULL,
    importer_version text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    rows_seen integer NOT NULL DEFAULT 0 CHECK (rows_seen >= 0),
    rows_accepted integer NOT NULL DEFAULT 0 CHECK (rows_accepted >= 0),
    rows_rejected integer NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    CONSTRAINT import_batch_status_ck CHECK (status IN ('running','completed','failed','rejected')),
    UNIQUE (source_id, source_checksum, importer_version)
);

CREATE TABLE IF NOT EXISTS provenance.external_identifiers (
    external_identifier_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    namespace text NOT NULL,
    identifier_value text NOT NULL,
    source_id uuid REFERENCES provenance.sources (source_id) ON DELETE RESTRICT,
    valid_from date,
    valid_to date,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT external_identifier_entity_type_ck CHECK (entity_type IN ('episode','broadcast','person','work','recording')),
    CONSTRAINT external_identifier_validity_ck CHECK (valid_from IS NULL OR valid_to IS NULL OR valid_to >= valid_from),
    UNIQUE (namespace, identifier_value)
);

CREATE INDEX IF NOT EXISTS external_identifiers_entity_idx
    ON provenance.external_identifiers (entity_type, entity_id);

CREATE TABLE IF NOT EXISTS provenance.source_assertions (
    source_assertion_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id uuid NOT NULL REFERENCES provenance.sources (source_id) ON DELETE RESTRICT,
    import_batch_id uuid REFERENCES provenance.import_batches (import_batch_id) ON DELETE RESTRICT,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    field_name text NOT NULL,
    raw_value text,
    normalized_value text,
    confidence numeric(5,4) CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    verification_status text NOT NULL DEFAULT 'unverified',
    observed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS source_assertions_entity_idx
    ON provenance.source_assertions (entity_type, entity_id, field_name);

CREATE TABLE IF NOT EXISTS staging.broadcast_log_1982 (
    staging_id bigserial PRIMARY KEY,
    import_batch_id uuid NOT NULL REFERENCES provenance.import_batches (import_batch_id) ON DELETE CASCADE,
    source_line integer NOT NULL CHECK (source_line > 0),
    show_number integer,
    otrw_number integer,
    source_date text,
    parsed_broadcast_date date,
    raw_title text NOT NULL,
    normalized_title text,
    validation_status text NOT NULL DEFAULT 'pending',
    validation_message text,
    raw_record text NOT NULL,
    UNIQUE (import_batch_id, source_line)
);

COMMENT ON TABLE catalog.episodes IS 'Canonical CBS Radio Mystery Theater episodes. Reruns do not create additional episode rows.';
COMMENT ON TABLE catalog.broadcasts IS 'Individual broadcast occurrences, including original airings and reruns.';
COMMENT ON TABLE provenance.external_identifiers IS 'Source/external identifiers mapped to stable canonical UUID entities.';
COMMENT ON TABLE staging.broadcast_log_1982 IS 'Staging representation for CBSRMT_Log_1982.txt prior to canonicalization.';

COMMIT;
