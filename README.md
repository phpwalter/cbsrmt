# CBS RMT

CBS RMT is a preservation, catalog, and API project for **CBS Radio Mystery Theater** episode metadata.

The repository contains historical source material, normalized JSON datasets, a legacy MySQL schema, and an early Swagger definition. The modernization effort keeps those archival assets intact while rebuilding the project around a documented, testable, versioned data and API foundation.

## Project goals

1. Preserve the historical CBS Radio Mystery Theater source data already contained in this repository.
2. Establish a canonical normalized data model for episodes, cast members, writers, genres, and their relationships.
3. Replace the incomplete legacy API definition with a maintained OpenAPI contract.
4. Provide deterministic import and validation tooling for the historical datasets.
5. Separate archival source material from generated or normalized application data.
6. Make the repository reproducible for local development, automated testing, and future API/UI consumers.

## Current repository assets

| Path | Purpose |
| --- | --- |
| `data/episodes.json` | Episode metadata |
| `data/cast.json` | Cast/person metadata |
| `data/writers.json` | Writer metadata |
| `data/genre.json` | Genre metadata |
| `sql/cbs.sql` | Legacy MySQL database export |
| `sql/cbs.mwb` | Legacy MySQL Workbench model |
| `api/swagger.json` | Early API contract |
| `cbsrmt/api/swagger.json` | Alternate/expanded early API contract |
| `CBSRMT_Log_1982.txt` | Historical source/log material |
| `cbs_rmt [02.15.02].xls` | Historical spreadsheet source |

The large historical images, spreadsheet, SQL export, and design files are treated as archival inputs rather than application runtime dependencies.

## Modernization structure

The target repository structure is:

```text
api/                    # maintained OpenAPI contract and API examples
data/
  source/               # immutable/raw historical inputs
  normalized/           # canonical machine-readable datasets
docs/
  architecture/         # architecture and design decisions
  data/                 # data dictionary, provenance, validation rules
  api/                  # API behavior and usage documentation
  development/          # setup, testing, contribution workflow
scripts/                 # deterministic import/validation utilities
sql/
  legacy/                # original schema/model assets
  migrations/            # versioned schema evolution
tests/                   # data-contract and application tests
```

Migration to this layout will be incremental. Existing historical files will not be silently discarded or rewritten.

## Canonical domain model

The initial domain consists of the following primary resources:

- **Episode** — numbered CBS Radio Mystery Theater broadcast episode.
- **Person** — normalized individual participating in a production.
- **Cast credit** — relationship between a person and an episode.
- **Writer credit** — relationship between a writer and an episode.
- **Genre** — classification assigned to one or more episodes.
- **Broadcast** — air-date or rebroadcast occurrence associated with an episode.
- **Source record** — provenance describing where a normalized fact originated.

Names and relationships must be represented independently rather than embedded repeatedly into episode records. Stable identifiers are required for API and import compatibility.

## API direction

The modern API will be contract-first and defined with OpenAPI. The contract should provide read-oriented access to the historical catalog first, followed by administrative/import endpoints only where required.

Initial resource families:

```text
GET /episodes
GET /episodes/{episodeId}
GET /people
GET /people/{personId}
GET /writers
GET /writers/{writerId}
GET /genres
GET /genres/{genreId}
GET /search
```

Collection endpoints should support pagination, filtering, deterministic sorting, and machine-readable error responses.

## Data integrity rules

At minimum, normalization and validation must enforce:

- stable episode identifiers;
- unique canonical episode numbers where historically applicable;
- ISO-formatted dates;
- normalized person and writer identities;
- referential integrity for cast, writer, and genre relationships;
- explicit handling of unknown or disputed metadata;
- source provenance for corrections and derived records;
- deterministic import output from identical input data.

No historical fact should be changed solely to make a record fit the modern model. Ambiguous or conflicting data should remain traceable to its source.

## Modernization phases

### Phase 1 — Foundation

- inventory repository assets;
- document the canonical domain model;
- define source-versus-normalized data boundaries;
- establish development and validation conventions;
- select the canonical legacy API/schema inputs.

### Phase 2 — Data normalization

- parse existing JSON, SQL, spreadsheet, and text sources;
- reconcile identifiers and names;
- generate canonical normalized datasets;
- record provenance and validation exceptions.

### Phase 3 — API contract

- replace Swagger 2-era definitions with the canonical OpenAPI contract;
- define pagination, filtering, search, errors, and schemas;
- add contract validation to CI.

### Phase 4 — Runtime implementation

- implement the API against the normalized datastore;
- add automated unit, integration, and contract tests;
- provide reproducible local startup and database initialization.

### Phase 5 — Consumer and preservation tooling

- add catalog/search UI or external clients;
- publish export formats;
- provide integrity reports and archival provenance views.

## Branch strategy

`main` remains the historical baseline until the modernization foundation is complete.

The active modernization work is developed on `foundation-work`. Changes should be promoted only after the data model, documentation, validation rules, and API contract agree with one another.

## Historical preservation policy

Historical source files are evidence. They should be moved only with traceable history, not replaced by generated derivatives. Generated normalized data must identify its source inputs and transformation version.

## License

See [`LICENSE`](LICENSE).
