BEGIN;

CREATE SCHEMA IF NOT EXISTS api;

CREATE OR REPLACE VIEW api.episodes AS
SELECT
    e.episode_id,
    e.canonical_number,
    e.title,
    e.subtitle,
    e.synopsis,
    e.original_air_date,
    e.duration_seconds,
    e.series_name,
    e.verification_status,
    e.created_at,
    e.updated_at
FROM catalog.episodes e;

CREATE OR REPLACE VIEW api.broadcasts AS
SELECT
    b.broadcast_id,
    b.episode_id,
    b.broadcast_at,
    b.broadcast_date,
    b.broadcast_type,
    b.verification_status,
    b.created_at,
    b.updated_at
FROM catalog.broadcasts b;

CREATE OR REPLACE VIEW api.episode_identifiers AS
SELECT
    x.entity_id AS episode_id,
    x.namespace,
    x.identifier_value,
    x.source_id,
    x.created_at
FROM provenance.external_identifiers x
WHERE x.entity_type = 'episode';

CREATE OR REPLACE VIEW api.broadcast_identifiers AS
SELECT
    x.entity_id AS broadcast_id,
    x.namespace,
    x.identifier_value,
    x.source_id,
    x.created_at
FROM provenance.external_identifiers x
WHERE x.entity_type = 'broadcast';

COMMENT ON VIEW api.episodes IS 'Stable read projection for canonical episode API responses.';
COMMENT ON VIEW api.broadcasts IS 'Stable read projection for broadcast API responses.';
COMMENT ON VIEW api.episode_identifiers IS 'Stable read projection for episode external identifiers.';
COMMENT ON VIEW api.broadcast_identifiers IS 'Stable read projection for broadcast external identifiers.';

COMMIT;
