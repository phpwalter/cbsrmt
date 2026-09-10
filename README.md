# CBS Radio Mystery Theater Project

A preservation-oriented catalog and API project for **CBS Radio Mystery Theater (CBSRMT)**.

The repository contains historical source material, legacy catalog data, and a modernization effort that is rebuilding the project around a normalized PostgreSQL catalog, deterministic ingestion, provenance, and a formal API.

## Current development

Active modernization work is on the `foundation` branch.

The original `main` branch is preserved as the historical baseline.

## Foundation architecture

```text
historical source files
        |
        v
raw / immutable inputs
        |
        v
staging + validation
        |
        v
normalization + provenance
        |
        v
PostgreSQL canonical catalog
        |
        v
stable api.* read projections
        |
        v
FastAPI service
        |
        v
web, mobile, research, and archival clients
```

## Core domain

The central domain is the CBS Radio Mystery Theater catalog.

The foundation distinguishes between:

- **episodes** — canonical unique programs;
- **broadcasts** — individual original airings or reruns;
- **people** — actors, writers, directors, producers, hosts, and other contributors;
- **credits** — a person's role in an episode;
- **works/adaptations** — literary or dramatic works used as source material;
- **recordings** — known audio/media representations;
- **external identifiers** — historical numbering systems and third-party identifiers;
- **sources/import batches** — provenance and reproducibility records.

A rerun is a new broadcast occurrence, not a duplicate episode.

## Historical source material

Important legacy assets currently include:

- `CBSRMT_Log_1982.txt`
- `cbs_rmt [02.15.02].xls`
- `cbs_rmt [02.15.02].zip`
- historical artwork and design assets

The binary XLS workbook and ZIP archive are treated as primary archaeology sources and must be structurally inspected before their contents are mapped into production migrations.

## Database

The modernization target is PostgreSQL.

Schemas currently include:

- `catalog` — canonical CBSRMT entities;
- `provenance` — sources, import batches, identifiers, and source assertions;
- `staging` — temporary normalized import structures;
- `governance` — migration history;
- `api` — stable read projections consumed by the HTTP service.

Migrations live under:

```text
db/migrations/
```

Apply them with:

```bash
python tools/migrate.py
```

The migration runner records SHA-256 checksums and rejects drift in already-applied migration files.

## Data ingestion principles

Imports are designed to be:

- deterministic;
- idempotent;
- source-traceable;
- conflict-aware;
- non-destructive to historical evidence.

The ingestion pipeline is:

```text
raw source
  -> staging
  -> validation
  -> normalization
  -> provenance mapping
  -> canonical catalog
```

Conflicting historical claims are retained and surfaced rather than silently overwritten.

The 1982 source can be validated and imported with:

```bash
python tools/import_1982.py --validate-only
python tools/import_1982.py
```

## Reconciliation

Catalog health can be inspected with:

```bash
python tools/reconcile.py
```

The reconciliation command reports canonical counts, identifier counts, import-batch state, disputed assertions, and orphan records.

## API

The authoritative contract is:

```text
api/openapi.yaml
```

The old user-centric Swagger experiment has been removed from the `foundation` branch.

Current read-only endpoints:

```text
GET /health
GET /episodes
GET /episodes/{episodeId}
GET /episodes/{episodeId}/broadcasts
GET /broadcasts
GET /broadcasts/{broadcastId}
```

The implementation lives in `app/main.py` and reads through `api.*` PostgreSQL projections instead of querying normalized catalog tables directly.

Run locally with:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

`DATABASE_URL` must point to a migrated PostgreSQL database.

## Tests and CI

The foundation test pipeline:

1. installs Python dependencies;
2. runs the migration runner;
3. reruns the migration runner to verify idempotency and checksum stability;
4. validates the 1982 source;
5. imports the source twice to verify import idempotency;
6. runs Python parser and API integration tests;
7. runs PostgreSQL reconciliation tests;
8. emits a catalog reconciliation report.

Run Python tests with:

```bash
pytest -q
```

## Documentation

Foundation documentation:

- `docs/data-archaeology.md` — current source inventory and verified domain conclusions;
- `docs/domain-model.md` — normalized domain architecture;
- `docs/import-1982-log.md` — deterministic import contract for the 1982 broadcast log.

## Project rules

1. Preserve original historical source files.
2. Never fabricate missing historical precision.
3. Do not use historical external numbering systems as physical database primary keys.
4. Keep episode identity separate from broadcast identity.
5. Preserve provenance for imported historical facts.
6. Make imports reproducible and idempotent.
7. Surface source conflicts instead of silently resolving them.
8. Keep API-facing identifiers stable and independent of source systems.
9. Keep normalized catalog tables behind stable database/API boundaries.
10. Treat `api/openapi.yaml` as the authoritative HTTP contract.

## License

The repository currently contains a CC0 1.0 Universal license file. Individual historical source materials and media may have additional rights considerations; provenance and rights status should therefore be tracked explicitly as the archive is expanded.
