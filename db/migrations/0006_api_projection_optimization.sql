BEGIN;

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
    COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'namespace', i.namespace,
                'value', i.identifier_value
            )
            ORDER BY i.namespace, i.identifier_value
        ) FILTER (WHERE i.external_identifier_id IS NOT NULL),
        '[]'::jsonb
    ) AS identifiers,
    e.created_at,
    e.updated_at
FROM catalog.episodes e
LEFT JOIN provenance.external_identifiers i
    ON i.entity_type = 'episode'
   AND i.entity_id = e.episode_id
GROUP BY e.episode_id;

CREATE OR REPLACE VIEW api.broadcasts AS
SELECT
    b.broadcast_id,
    b.episode_id,
    b.broadcast_at,
    b.broadcast_date,
    b.broadcast_type,
    b.verification_status,
    COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'namespace', i.namespace,
                'value', i.identifier_value
            )
            ORDER BY i.namespace, i.identifier_value
        ) FILTER (WHERE i.external_identifier_id IS NOT NULL),
        '[]'::jsonb
    ) AS identifiers,
    b.created_at,
    b.updated_at
FROM catalog.broadcasts b
LEFT JOIN provenance.external_identifiers i
    ON i.entity_type = 'broadcast'
   AND i.entity_id = b.broadcast_id
GROUP BY b.broadcast_id;

COMMENT ON VIEW api.episodes IS
    'Stable episode API projection with pre-aggregated external identifiers.';
COMMENT ON VIEW api.broadcasts IS
    'Stable broadcast API projection with pre-aggregated external identifiers.';

COMMIT;
