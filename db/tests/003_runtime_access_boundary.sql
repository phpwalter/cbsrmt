DO $$
BEGIN
    IF NOT pg_has_role('cbsrmt_api', 'cbsrmt_api', 'member') THEN
        RAISE EXCEPTION 'cbsrmt_api must report membership in itself';
    END IF;

    IF NOT has_table_privilege('cbsrmt_api', 'api.episodes', 'SELECT') THEN
        RAISE EXCEPTION 'cbsrmt_api must be able to read api projections';
    END IF;

    IF has_table_privilege('cbsrmt_api', 'catalog.episodes', 'SELECT') THEN
        RAISE EXCEPTION 'cbsrmt_api must not read catalog tables directly';
    END IF;

    IF has_table_privilege('cbsrmt_api', 'provenance.external_identifiers', 'SELECT') THEN
        RAISE EXCEPTION 'cbsrmt_api must not read provenance tables directly';
    END IF;

    IF has_schema_privilege('cbsrmt_api', 'catalog', 'USAGE') THEN
        RAISE EXCEPTION 'cbsrmt_api must not have catalog schema usage';
    END IF;

    IF has_schema_privilege('cbsrmt_api', 'provenance', 'USAGE') THEN
        RAISE EXCEPTION 'cbsrmt_api must not have provenance schema usage';
    END IF;
END
$$;
