BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cbsrmt_api') THEN
        CREATE ROLE cbsrmt_api NOLOGIN;
    END IF;
END
$$;

REVOKE ALL ON SCHEMA catalog FROM cbsrmt_api;
REVOKE ALL ON SCHEMA provenance FROM cbsrmt_api;
REVOKE ALL ON SCHEMA staging FROM cbsrmt_api;
REVOKE ALL ON SCHEMA governance FROM cbsrmt_api;
REVOKE ALL ON ALL TABLES IN SCHEMA catalog FROM cbsrmt_api;
REVOKE ALL ON ALL TABLES IN SCHEMA provenance FROM cbsrmt_api;
REVOKE ALL ON ALL TABLES IN SCHEMA staging FROM cbsrmt_api;
REVOKE ALL ON ALL TABLES IN SCHEMA governance FROM cbsrmt_api;

GRANT USAGE ON SCHEMA api TO cbsrmt_api;
GRANT SELECT ON ALL TABLES IN SCHEMA api TO cbsrmt_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA api GRANT SELECT ON TABLES TO cbsrmt_api;

COMMENT ON ROLE cbsrmt_api IS
    'Read-only application role. May select from api.* projections only; no direct catalog/provenance/staging/governance access.';

COMMIT;
