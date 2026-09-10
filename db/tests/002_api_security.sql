DO $$
DECLARE
    can_api_episode boolean;
    can_catalog_episode boolean;
    can_provenance_identifier boolean;
    can_staging_log boolean;
    can_governance_migration boolean;
BEGIN
    SELECT has_table_privilege('cbsrmt_api', 'api.episodes', 'SELECT') INTO can_api_episode;
    SELECT has_table_privilege('cbsrmt_api', 'catalog.episodes', 'SELECT') INTO can_catalog_episode;
    SELECT has_table_privilege('cbsrmt_api', 'provenance.external_identifiers', 'SELECT') INTO can_provenance_identifier;
    SELECT has_table_privilege('cbsrmt_api', 'staging.broadcast_log_1982', 'SELECT') INTO can_staging_log;
    SELECT has_table_privilege('cbsrmt_api', 'governance.schema_migrations', 'SELECT') INTO can_governance_migration;

    IF NOT can_api_episode THEN
        RAISE EXCEPTION 'cbsrmt_api must be able to SELECT api.episodes';
    END IF;
    IF can_catalog_episode THEN
        RAISE EXCEPTION 'cbsrmt_api must not SELECT catalog.episodes';
    END IF;
    IF can_provenance_identifier THEN
        RAISE EXCEPTION 'cbsrmt_api must not SELECT provenance.external_identifiers';
    END IF;
    IF can_staging_log THEN
        RAISE EXCEPTION 'cbsrmt_api must not SELECT staging.broadcast_log_1982';
    END IF;
    IF can_governance_migration THEN
        RAISE EXCEPTION 'cbsrmt_api must not SELECT governance.schema_migrations';
    END IF;
END $$;
