# CBS Radio Mystery Theater Project

A preservation-oriented catalog and API project for **CBS Radio Mystery Theater (CBSRMT)**.

The repository contains historical source material, legacy catalog data, and a modernization effort that is rebuilding the project around a normalized PostgreSQL catalog, deterministic ingestion, provenance, and a formal API.

## Current development

Active modernization work is on the `foundation` branch.

The original `main` branch is being preserved as the historical baseline.

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
API
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
- the original `api/swagger.json` API experiment

The binary XLS workbook and ZIP archive are treated as primary archaeology sources and must be structurally inspected before their contents are mapped into production migrations.

## Database

The modernization target is PostgreSQL.

Initial schemas:

- `catalog` — canonical CBSRMT entities;
- `provenance` — sources, import batches, identifiers, and source assertions;
- `staging` — temporary normalized import structures.

Initial migration:

```text
db/migrations/0001_foundation.sql
```

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

## Documentation

Foundation documentation:

- `docs/data-archaeology.md` — current source inventory and verified domain conclusions;
- `docs/domain-model.md` — normalized domain architecture;
- `docs/import-1982-log.md` — deterministic import contract for the 1982 broadcast log.

## API status

The existing `api/swagger.json` is an early OpenAPI 3.0 experiment and is **not** the target contract for the rebuilt project.

It will be replaced after the canonical data model and import behavior are established. The rebuilt API will be catalog-centric rather than user-centric.

Expected resource families include:

```text
/episodes
/broadcasts
/people
/credits
/works
/recordings
/search
/sources
```

## Project rules

1. Preserve original historical source files.
2. Never fabricate missing historical precision.
3. Do not use historical external numbering systems as physical database primary keys.
4. Keep episode identity separate from broadcast identity.
5. Preserve provenance for imported historical facts.
6. Make imports reproducible and idempotent.
7. Surface source conflicts instead of silently resolving them.
8. Keep API-facing identifiers stable and independent of source systems.

## License

The repository currently contains a CC0 1.0 Universal license file. Individual historical source materials and media may have additional rights considerations; provenance and rights status should therefore be tracked explicitly as the archive is expanded.
