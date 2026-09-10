DO $$
DECLARE
    result record;
BEGIN
    SET LOCAL ROLE cbsrmt_api;

    SELECT * INTO result FROM api.runtime_access_check();

    IF NOT result.is_api_member THEN
        RAISE EXCEPTION 'cbsrmt_api must report membership in itself';
    END IF;

    IF NOT result.can_read_api THEN
        RAISE EXCEPTION 'cbsrmt_api must be able to read api projections';
    END IF;

    IF result.can_read_catalog_directly THEN
        RAISE EXCEPTION 'cbsrmt_api must not read catalog tables directly';
    END IF;

    IF result.can_read_provenance_directly THEN
        RAISE EXCEPTION 'cbsrmt_api must not read provenance tables directly';
    END IF;
END
$$;
