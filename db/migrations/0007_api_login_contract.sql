BEGIN;

-- cbsrmt_api remains the NOLOGIN privilege role. Runtime login roles are
-- provisioned separately and granted membership in cbsrmt_api. This avoids
-- storing environment-specific passwords in migrations.

CREATE OR REPLACE FUNCTION api.runtime_access_check()
RETURNS TABLE (
    login_role name,
    is_api_member boolean,
    can_read_api boolean,
    can_read_catalog_directly boolean,
    can_read_provenance_directly boolean
)
LANGUAGE sql
SECURITY INVOKER
AS $$
    SELECT
        current_user::name,
        pg_has_role(current_user, 'cbsrmt_api', 'member'),
        has_table_privilege(current_user, 'api.episodes', 'SELECT'),
        has_table_privilege(current_user, 'catalog.episodes', 'SELECT'),
        has_table_privilege(current_user, 'provenance.external_identifiers', 'SELECT');
$$;

GRANT EXECUTE ON FUNCTION api.runtime_access_check() TO cbsrmt_api;

COMMENT ON FUNCTION api.runtime_access_check() IS
    'Runtime diagnostic for API login roles. A valid login is a member of cbsrmt_api, can read api projections, and cannot directly read catalog/provenance tables.';

COMMIT;
