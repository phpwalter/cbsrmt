# Foundation Development Workflow

## Scope

This document defines the working rules for the CBS RMT modernization effort on `foundation-work`.

The objective is to turn the historical repository into a reproducible catalog platform without destroying, silently rewriting, or conflating archival source material.

## Source-of-truth hierarchy

During the foundation phase, conflicts between artifacts are resolved according to the following ownership model:

1. `docs/data/DATA_MODEL.md` defines canonical domain semantics.
2. `sql/migrations/*.sql` defines physical relational storage.
3. `api/openapi.yaml` defines externally observable API behavior.
4. normalization/import tooling defines deterministic transformation from source artifacts into canonical data.
5. historical JSON, SQL, spreadsheet, text, and image artifacts are evidence inputs, not modern implementation contracts.

The hierarchy does not mean historical data can be overruled by documentation. It means implementation structure must be changed deliberately through the canonical model rather than inferred ad hoc from legacy file layout.

## Foundation acceptance criteria

The foundation is not complete until all of the following are true:

- a clean PostgreSQL database can apply every migration in order;
- schema objects match the documented canonical model;
- OpenAPI validation passes;
- every OpenAPI schema and endpoint used by the runtime has contract tests;
- source files can be inventoried and hashed deterministically;
- normalized output can be reproduced from identical source inputs;
- unresolved source conflicts are surfaced rather than silently overwritten;
- repeated imports do not create duplicate canonical relationships;
- README and development documentation describe the commands actually used by the project.

## Migration policy

Database changes must be additive, ordered migrations.

Rules:

- migrations are immutable after they have been accepted into a released baseline;
- migration filenames use a zero-padded sequence and descriptive suffix;
- migrations must run inside explicit transactions unless PostgreSQL prevents the operation;
- schema changes must have corresponding data-model documentation changes;
- destructive changes require an explicit migration and rationale;
- no runtime process may depend on the legacy `sql/cbs.sql` schema directly once canonical import is implemented.

The initial migration is:

```text
sql/migrations/0001_foundation.sql
```

## PostgreSQL baseline

The foundation schema targets PostgreSQL 15 or newer.

The design currently uses `UNIQUE NULLS NOT DISTINCT`, which requires PostgreSQL 15+. If support for an older PostgreSQL release becomes a requirement, equivalent uniqueness semantics must be implemented deliberately rather than removing the constraints.

## Identifier generation

Canonical IDs are UUIDs, but the database does not generate them automatically.

The importer/application must generate stable IDs according to a documented deterministic strategy. This is necessary so repeated normalization against unchanged source material produces the same identifiers instead of creating an entirely new catalog graph.

A future identifier specification should define namespaces and key material for each entity class before production imports are treated as canonical.

## Provenance policy

Every material normalization step should be traceable back to source evidence.

At minimum, import tooling must capture:

- source artifact path;
- SHA-256 of the source artifact;
- source record locator;
- source-record content hash;
- transformation version;
- import batch identifier;
- conflicts detected during reconciliation.

Do not use timestamps as part of canonical record identity or normalized content hashes.

## Import transactions

An import batch should be atomic for a defined unit of work.

Preferred behavior:

1. inventory and hash source inputs;
2. validate source syntax;
3. construct normalized candidate records;
4. detect conflicts and unresolved references;
5. begin database transaction;
6. upsert deterministic canonical records and provenance;
7. validate post-import invariants;
8. commit;
9. mark the import batch succeeded.

A failed validation should rollback the transactional catalog changes. Diagnostic output should remain available outside the transaction where practical.

## Legacy artifacts

The current repository contains duplicate/alternate API definitions and historical data assets.

Do not delete them during foundation work merely because a canonical replacement exists.

The eventual archival reorganization should place historical material under clear legacy/source locations while preserving Git history and documenting any path changes.

## Testing layers

The modernization should establish four separate test classes.

### 1. Source validation tests

Validate input structure without assuming it is already canonical.

Examples:

- JSON parses successfully;
- expected root structures exist;
- spreadsheet worksheets can be identified;
- required legacy keys are present where expected;
- malformed source dates are reported.

### 2. Normalization tests

Validate transformation rules.

Examples:

- name whitespace normalization;
- deterministic IDs;
- alias retention;
- relationship deduplication;
- conflict creation;
- partial-date preservation.

### 3. Database contract tests

Validate PostgreSQL constraints and migrations.

Examples:

- foreign keys reject orphan relationships;
- duplicate episode numbers are rejected;
- duplicate normalized credits are rejected;
- resolved conflicts require a resolved value;
- migration can build a clean database from zero.

### 4. API contract tests

Validate runtime behavior against `api/openapi.yaml`.

Examples:

- endpoint status codes;
- pagination metadata;
- response schemas;
- deterministic ordering;
- filtering semantics;
- RFC 7807-style error responses;
- undocumented response properties are rejected where the schema sets `additionalProperties: false`.

## Determinism rule

The same source bytes, transformation version, and configuration must result in the same canonical normalized records.

Differences in execution time, host machine, operating system, process ID, iteration order, or database-generated sequence values must not affect canonical output.

This rule is central to the project. A pipeline that cannot reproduce its own catalog is not considered trustworthy enough for archival normalization.

## Immediate implementation sequence

The next implementation block after this foundation should be:

1. source inventory/manifest tool;
2. JSON source validator;
3. deterministic identifier specification and helper;
4. episode normalizer;
5. person/cast/writer reconciliation;
6. genre reconciliation;
7. PostgreSQL loader;
8. post-load invariant verifier;
9. minimal read-only API runtime;
10. contract and integration CI.

The sequence intentionally proves data integrity before investing in a UI or administrative mutation API.
