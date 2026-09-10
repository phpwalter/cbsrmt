DO $$
DECLARE
    episode_count integer;
    broadcast_count integer;
    batch_count integer;
    orphan_broadcast_count integer;
    duplicate_show_ids integer;
    duplicate_otrw_ids integer;
BEGIN
    SELECT count(*) INTO episode_count FROM catalog.episodes;
    SELECT count(*) INTO broadcast_count FROM catalog.broadcasts;
    SELECT count(*) INTO batch_count FROM provenance.import_batches;

    IF episode_count <> 127 THEN
        RAISE EXCEPTION 'Expected 127 episodes, found %', episode_count;
    END IF;

    IF broadcast_count <> 127 THEN
        RAISE EXCEPTION 'Expected 127 broadcasts, found %', broadcast_count;
    END IF;

    IF batch_count <> 1 THEN
        RAISE EXCEPTION 'Expected 1 import batch, found %', batch_count;
    END IF;

    SELECT count(*) INTO orphan_broadcast_count
    FROM catalog.broadcasts b
    LEFT JOIN catalog.episodes e ON e.episode_id = b.episode_id
    WHERE e.episode_id IS NULL;

    IF orphan_broadcast_count <> 0 THEN
        RAISE EXCEPTION 'Found % orphan broadcasts', orphan_broadcast_count;
    END IF;

    SELECT count(*) INTO duplicate_show_ids
    FROM (
        SELECT identifier_value
        FROM provenance.external_identifiers
        WHERE entity_type = 'episode'
          AND namespace = 'cbsrmt.show_number'
        GROUP BY identifier_value
        HAVING count(*) > 1
    ) d;

    IF duplicate_show_ids <> 0 THEN
        RAISE EXCEPTION 'Found duplicate SHOW identifiers';
    END IF;

    SELECT count(*) INTO duplicate_otrw_ids
    FROM (
        SELECT identifier_value
        FROM provenance.external_identifiers
        WHERE entity_type = 'broadcast'
          AND namespace = 'otrwalter.broadcast_number'
        GROUP BY identifier_value
        HAVING count(*) > 1
    ) d;

    IF duplicate_otrw_ids <> 0 THEN
        RAISE EXCEPTION 'Found duplicate OTRW identifiers';
    END IF;
END
$$;
