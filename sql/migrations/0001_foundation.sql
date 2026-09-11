-- CBS RMT canonical database foundation
-- Migration: 0001_foundation
-- Target: PostgreSQL 15+
--
-- Canonical identifiers are supplied by the importer/application. The database
-- does not generate them so deterministic imports can reproduce the same IDs.

BEGIN;

CREATE SCHEMA IF NOT EXISTS cbsrmt;

CREATE TYPE cbsrmt.metadata_status AS ENUM (
    'confirmed',
    'reported',
    'disputed',
    'unknown',
    'derived'
);

CREATE TYPE cbsrmt.import_result AS ENUM (
    'running',
    'succeeded',
    'failed',
    'partial'
);

CREATE TYPE cbsrmt.resolution_status AS ENUM (
    'open',
    'resolved',
    'deferred',
    'rejected'
);

CREATE TABLE cbsrmt.source_artifact (
    id                  uuid PRIMARY KEY,
    path                text NOT NULL,
    artifact_type       text NOT NULL,
    sha256              char(64) NOT NULL,
    description         text,
    captured_at         timestamptz,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    CONSTRAINT uq_source_artifact_path_hash UNIQUE (path, sha256),
    CONSTRAINT ck_source_artifact_sha256 CHECK (sha256 ~ '^[0-9a-fA-F]{64}$'),
    CONSTRAINT ck_source_artifact_path CHECK (btrim(path) <> ''),
    CONSTRAINT ck_source_artifact_type CHECK (btrim(artifact_type) <> '')
);

CREATE TABLE cbsrmt.import_batch (
    id                  uuid PRIMARY KEY,
    transform_version   text NOT NULL,
    source_manifest_hash char(64) NOT NULL,
    started_at          timestamptz NOT NULL,
    completed_at        timestamptz,
    result              cbsrmt.import_result NOT NULL DEFAULT 'running',
    CONSTRAINT ck_import_batch_transform_version CHECK (btrim(transform_version) <> ''),
    CONSTRAINT ck_import_batch_manifest_hash CHECK (source_manifest_hash ~ '^[0-9a-fA-F]{64}$'),
    CONSTRAINT ck_import_batch_time_order CHECK (completed_at IS NULL OR completed_at >= started_at)
);

CREATE TABLE cbsrmt.source_record (
    id                  uuid PRIMARY KEY,
    source_artifact_id  uuid NOT NULL REFERENCES cbsrmt.source_artifact(id) ON DELETE RESTRICT,
    import_batch_id     uuid REFERENCES cbsrmt.import_batch(id) ON DELETE RESTRICT,
    locator             text NOT NULL,
    raw_value           jsonb,
    record_hash         char(64) NOT NULL,
    CONSTRAINT uq_source_record_location UNIQUE (source_artifact_id, locator, record_hash),
    CONSTRAINT ck_source_record_locator CHECK (btrim(locator) <> ''),
    CONSTRAINT ck_source_record_hash CHECK (record_hash ~ '^[0-9a-fA-F]{64}$')
);

CREATE TABLE cbsrmt.episode (
    id                  uuid PRIMARY KEY,
    episode_number      integer,
    title               text NOT NULL,
    original_air_date   date,
    synopsis            text,
    duration_seconds    integer,
    production_code     text,
    notes               text,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    CONSTRAINT uq_episode_number UNIQUE (episode_number),
    CONSTRAINT ck_episode_number_positive CHECK (episode_number IS NULL OR episode_number > 0),
    CONSTRAINT ck_episode_title CHECK (btrim(title) <> ''),
    CONSTRAINT ck_episode_duration CHECK (duration_seconds IS NULL OR duration_seconds > 0)
);

CREATE TABLE cbsrmt.person (
    id                  uuid PRIMARY KEY,
    canonical_name      text NOT NULL,
    sort_name           text,
    notes               text,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    CONSTRAINT ck_person_name CHECK (btrim(canonical_name) <> '')
);

CREATE INDEX ix_person_canonical_name ON cbsrmt.person (canonical_name);
CREATE INDEX ix_person_sort_name ON cbsrmt.person (sort_name);

CREATE TABLE cbsrmt.person_alias (
    id                  uuid PRIMARY KEY,
    person_id           uuid NOT NULL REFERENCES cbsrmt.person(id) ON DELETE CASCADE,
    name                text NOT NULL,
    alias_type          text NOT NULL DEFAULT 'source_spelling',
    source_record_id    uuid REFERENCES cbsrmt.source_record(id) ON DELETE RESTRICT,
    CONSTRAINT uq_person_alias UNIQUE (person_id, name, alias_type),
    CONSTRAINT ck_person_alias_name CHECK (btrim(name) <> ''),
    CONSTRAINT ck_person_alias_type CHECK (btrim(alias_type) <> '')
);

CREATE INDEX ix_person_alias_name ON cbsrmt.person_alias (name);

CREATE TABLE cbsrmt.cast_credit (
    id                  uuid PRIMARY KEY,
    episode_id          uuid NOT NULL REFERENCES cbsrmt.episode(id) ON DELETE CASCADE,
    person_id           uuid NOT NULL REFERENCES cbsrmt.person(id) ON DELETE RESTRICT,
    character_name      text,
    credit_order        integer,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    source_record_id    uuid REFERENCES cbsrmt.source_record(id) ON DELETE RESTRICT,
    CONSTRAINT ck_cast_credit_order CHECK (credit_order IS NULL OR credit_order >= 0),
    CONSTRAINT uq_cast_credit UNIQUE NULLS NOT DISTINCT
        (episode_id, person_id, character_name, credit_order)
);

CREATE INDEX ix_cast_credit_episode ON cbsrmt.cast_credit (episode_id, credit_order);
CREATE INDEX ix_cast_credit_person ON cbsrmt.cast_credit (person_id, episode_id);

CREATE TABLE cbsrmt.writer_credit (
    id                  uuid PRIMARY KEY,
    episode_id          uuid NOT NULL REFERENCES cbsrmt.episode(id) ON DELETE CASCADE,
    person_id           uuid NOT NULL REFERENCES cbsrmt.person(id) ON DELETE RESTRICT,
    credit_type         text NOT NULL DEFAULT 'unknown',
    credit_order        integer,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    source_record_id    uuid REFERENCES cbsrmt.source_record(id) ON DELETE RESTRICT,
    CONSTRAINT ck_writer_credit_type CHECK (btrim(credit_type) <> ''),
    CONSTRAINT ck_writer_credit_order CHECK (credit_order IS NULL OR credit_order >= 0),
    CONSTRAINT uq_writer_credit UNIQUE NULLS NOT DISTINCT
        (episode_id, person_id, credit_type, credit_order)
);

CREATE INDEX ix_writer_credit_episode ON cbsrmt.writer_credit (episode_id, credit_order);
CREATE INDEX ix_writer_credit_person ON cbsrmt.writer_credit (person_id, episode_id);

CREATE TABLE cbsrmt.genre (
    id                  uuid PRIMARY KEY,
    name                text NOT NULL,
    description         text,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    CONSTRAINT uq_genre_name UNIQUE (name),
    CONSTRAINT ck_genre_name CHECK (btrim(name) <> '')
);

CREATE TABLE cbsrmt.episode_genre (
    episode_id          uuid NOT NULL REFERENCES cbsrmt.episode(id) ON DELETE CASCADE,
    genre_id            uuid NOT NULL REFERENCES cbsrmt.genre(id) ON DELETE RESTRICT,
    source_record_id    uuid REFERENCES cbsrmt.source_record(id) ON DELETE RESTRICT,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    PRIMARY KEY (episode_id, genre_id)
);

CREATE INDEX ix_episode_genre_genre ON cbsrmt.episode_genre (genre_id, episode_id);

CREATE TABLE cbsrmt.broadcast (
    id                  uuid PRIMARY KEY,
    episode_id          uuid NOT NULL REFERENCES cbsrmt.episode(id) ON DELETE CASCADE,
    broadcast_date      date,
    date_precision      text NOT NULL DEFAULT 'day',
    broadcast_type      text NOT NULL DEFAULT 'unknown',
    station_or_network  text,
    status              cbsrmt.metadata_status NOT NULL DEFAULT 'reported',
    source_record_id    uuid REFERENCES cbsrmt.source_record(id) ON DELETE RESTRICT,
    CONSTRAINT ck_broadcast_type CHECK (btrim(broadcast_type) <> ''),
    CONSTRAINT ck_broadcast_date_precision CHECK (date_precision IN ('day', 'month', 'year', 'unknown')),
    CONSTRAINT ck_broadcast_date_precision_value CHECK (
        (date_precision = 'unknown' AND broadcast_date IS NULL)
        OR (date_precision <> 'unknown' AND broadcast_date IS NOT NULL)
    ),
    CONSTRAINT uq_broadcast UNIQUE NULLS NOT DISTINCT
        (episode_id, broadcast_date, broadcast_type, station_or_network)
);

CREATE INDEX ix_broadcast_episode_date ON cbsrmt.broadcast (episode_id, broadcast_date);
CREATE INDEX ix_broadcast_date ON cbsrmt.broadcast (broadcast_date);

CREATE TABLE cbsrmt.entity_source (
    entity_type         text NOT NULL,
    entity_id           uuid NOT NULL,
    source_record_id    uuid NOT NULL REFERENCES cbsrmt.source_record(id) ON DELETE RESTRICT,
    field_name          text,
    PRIMARY KEY (entity_type, entity_id, source_record_id, field_name),
    CONSTRAINT ck_entity_source_type CHECK (entity_type IN (
        'episode', 'person', 'person_alias', 'cast_credit', 'writer_credit',
        'genre', 'episode_genre', 'broadcast'
    )),
    CONSTRAINT ck_entity_source_field CHECK (field_name IS NULL OR btrim(field_name) <> '')
);

CREATE INDEX ix_entity_source_record ON cbsrmt.entity_source (source_record_id);

CREATE TABLE cbsrmt.data_conflict (
    id                  uuid PRIMARY KEY,
    entity_type         text NOT NULL,
    entity_id           uuid NOT NULL,
    field_name          text NOT NULL,
    candidate_values    jsonb NOT NULL,
    resolution_status   cbsrmt.resolution_status NOT NULL DEFAULT 'open',
    resolution_note     text,
    resolved_value      jsonb,
    CONSTRAINT ck_data_conflict_entity_type CHECK (btrim(entity_type) <> ''),
    CONSTRAINT ck_data_conflict_field_name CHECK (btrim(field_name) <> ''),
    CONSTRAINT ck_data_conflict_candidates_array CHECK (jsonb_typeof(candidate_values) = 'array'),
    CONSTRAINT ck_data_conflict_resolution CHECK (
        resolution_status <> 'resolved' OR resolved_value IS NOT NULL
    )
);

CREATE INDEX ix_data_conflict_entity ON cbsrmt.data_conflict (entity_type, entity_id);
CREATE INDEX ix_data_conflict_status ON cbsrmt.data_conflict (resolution_status);

-- Compatibility/read-model indexes used by catalog and search endpoints.
CREATE INDEX ix_episode_title ON cbsrmt.episode (title);
CREATE INDEX ix_episode_air_date ON cbsrmt.episode (original_air_date);
CREATE INDEX ix_episode_status ON cbsrmt.episode (status);

COMMENT ON SCHEMA cbsrmt IS 'Canonical normalized CBS Radio Mystery Theater catalog and provenance data.';
COMMENT ON TABLE cbsrmt.entity_source IS 'Polymorphic provenance link. Referential entity validation is enforced by import/application validation because entity_id spans canonical tables.';

COMMIT;
