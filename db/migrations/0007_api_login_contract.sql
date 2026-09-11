BEGIN;

-- cbsrmt_api remains the NOLOGIN privilege role. Runtime login roles are
-- provisioned separately and granted membership in cbsrmt_api. This avoids
-- storing environment-specific passwords in migrations.
--
-- This diagnostic is SECURITY DEFINER because a correctly restricted caller
-- cannot resolve protected catalog/provenance relations by name. The function
-- exposes only boolean privilege metadata and evaluates SESSION_USER, never the
-- definer's privileges. The fixed search_path prevents object-shadowing attacks.

CREATE OR REPLACE FUNCTION api.runtime_access_check()
RETURNS TABLE (
    login_role name,
    is_api_member boolean,
    can_read_api boolean,
    can_read_catalog_directly boolean,
    can_read_provenance_directly boolean
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, api
AS $$
    SELECT
        session_user::name,
        pg_has_role(session_user, 'cbsrmt_api', 'member'),
        has_table_privilege(session_user, 'api.episodes'::regclass, 'SELECT'),
        has_table_privilege(session_user, 'catalog.episodes'::regclass, 'SELECT'),
        has_table_privilege(session_user, 'provenance.external_identifiers'::regclass, 'SELECT');
$$;

REVOKE ALL ON FUNCTION api.runtime_access_check() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION api.runtime_access_check() TO cbsrmt_api;

COMMENT ON FUNCTION api.runtime_access_check() IS
    'Restricted runtime diagnostic. Evaluates SESSION_USER membership and effective SELECT privileges while exposing only boolean access metadata.';

COMMIT;
