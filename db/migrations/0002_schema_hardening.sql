BEGIN;

-- Verification state is deliberately constrained at the database boundary.
-- Historical data may be disputed, so "verified" is not the only accepted state.
ALTER TABLE catalog.episodes
    DROP CONSTRAINT IF EXISTS episodes_verification_status_ck;
ALTER TABLE catalog.episodes
    ADD CONSTRAINT episodes_verification_status_ck
    CHECK (verification_status IN ('unverified','source-backed','verified','disputed','rejected'));

ALTER TABLE catalog.broadcasts
    DROP CONSTRAINT IF EXISTS broadcasts_verification_status_ck;
ALTER TABLE catalog.broadcasts
    ADD CONSTRAINT broadcasts_verification_status_ck
    CHECK (verification_status IN ('unverified','source-backed','verified','disputed','rejected'));

ALTER TABLE provenance.source_assertions
    DROP CONSTRAINT IF EXISTS source_assertions_verification_status_ck;
ALTER TABLE provenance.source_assertions
    ADD CONSTRAINT source_assertions_verification_status_ck
    CHECK (verification_status IN ('unverified','source-backed','verified','disputed','rejected'));

-- Identifier values are unique within an entity type and namespace. This avoids
-- imposing the stronger and unnecessary assumption that unrelated entity types
-- can never use the same lexical identifier in the same namespace.
ALTER TABLE provenance.external_identifiers
    DROP CONSTRAINT IF EXISTS external_identifiers_namespace_identifier_value_key;

ALTER TABLE provenance.external_identifiers
    ADD CONSTRAINT external_identifiers_entity_namespace_value_uq
    UNIQUE (entity_type, namespace, identifier_value);

-- Import-batch assertions are facts observed from one source/import execution.
-- Prevent accidental duplicate assertions when a deterministic importer is rerun.
CREATE UNIQUE INDEX IF NOT EXISTS source_assertions_batch_fact_uq
    ON provenance.source_assertions (
        source_id,
        import_batch_id,
        entity_type,
        entity_id,
        field_name,
        COALESCE(normalized_value, '')
    );

-- Basic semantic constraints for source assertions.
ALTER TABLE provenance.source_assertions
    DROP CONSTRAINT IF EXISTS source_assertions_field_name_nonempty_ck;
ALTER TABLE provenance.source_assertions
    ADD CONSTRAINT source_assertions_field_name_nonempty_ck
    CHECK (btrim(field_name) <> '');

ALTER TABLE provenance.external_identifiers
    DROP CONSTRAINT IF EXISTS external_identifiers_namespace_nonempty_ck;
ALTER TABLE provenance.external_identifiers
    ADD CONSTRAINT external_identifiers_namespace_nonempty_ck
    CHECK (btrim(namespace) <> '');

ALTER TABLE provenance.external_identifiers
    DROP CONSTRAINT IF EXISTS external_identifiers_value_nonempty_ck;
ALTER TABLE provenance.external_identifiers
    ADD CONSTRAINT external_identifiers_value_nonempty_ck
    CHECK (btrim(identifier_value) <> '');

COMMIT;
