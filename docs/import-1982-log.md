# Import Contract: 1982 Broadcast Log

## Source

`CBSRMT_Log_1982.txt`

## Purpose

This importer converts the historical 1982 log into deterministic staging data and then canonical episode/broadcast records while preserving source provenance.

## Source fields

Each data row contains:

- `SHOW #`
- `OTRW #`
- `Date`
- `Episode Title`

## Interpretation

### SHOW #

Represents the unique episode/program number and maps to:

- `catalog.episodes.canonical_number`
- `provenance.external_identifiers.namespace = 'cbsrmt.show_number'`

### OTRW #

Represents the OTRWalter broadcast occurrence number and maps to:

- the corresponding `catalog.broadcasts.broadcast_id`
- `provenance.external_identifiers.namespace = 'otrwalter.broadcast_number'`

### Date

The source date is six digits in `YYMMDD` format. For this importer, the file-level context fixes the century as 1982.

Rules:

1. Preserve the original six-character value in staging.
2. Parse only if the value is exactly six digits and forms a valid calendar date.
3. Store the parsed result in `parsed_broadcast_date`.
4. Never coerce an invalid date.

### Episode Title

Preserve the complete source title in `raw_title`.

Normalization may:

- trim leading/trailing whitespace;
- normalize repeated internal whitespace;
- separate obvious annotations from titles only when an explicit rule exists.

It must not silently discard parenthetical annotations such as `(Tammy Grimes)`.

## Deterministic pipeline

### Phase 1: source registration

Register the file in `provenance.sources`.

Suggested values:

- `source_type = 'broadcast_log'`
- `name = 'CBSRMT 1982 Broadcast Log'`
- `license = 'Repository source; rights subject to source provenance'`

### Phase 2: checksum

Compute a SHA-256 checksum over the exact source bytes.

Create an `import_batches` record using:

- source ID;
- source checksum;
- importer version.

The unique constraint makes the same source/importer combination idempotent.

### Phase 3: staging

Read the source line-by-line.

For every data row write:

- line number;
- parsed numeric fields;
- raw date;
- parsed date;
- raw title;
- normalized title;
- raw record;
- validation outcome.

No canonical writes happen in this phase.

### Phase 4: validation

Reject a row from canonicalization if any of the following are true:

- SHOW # is missing or non-numeric;
- OTRW # is missing or non-numeric;
- date is invalid;
- title is empty;
- duplicate SHOW # points to a conflicting title without an adjudication rule;
- duplicate OTRW # refers to a different broadcast.

Rejected rows remain in staging with an explanation.

### Phase 5: canonical episode upsert

For each accepted SHOW #:

1. Find an existing `cbsrmt.show_number` external identifier.
2. If found, resolve its canonical episode.
3. If not found, create a new episode and identifier.
4. Compare source title/date against canonical values.
5. Record source assertions for imported claims.
6. Do not overwrite conflicting verified values automatically.

### Phase 6: broadcast creation

For each accepted OTRW #:

1. Find an existing `otrwalter.broadcast_number` identifier.
2. If found, verify it points to the expected episode/date.
3. If not found, create a broadcast row linked to the episode.
4. Because this source currently documents original broadcasts, assign `broadcast_type = 'original'` unless later source evidence overrides that classification.

### Phase 7: reconciliation

The importer must emit a reconciliation report containing:

- rows seen;
- rows accepted;
- rows rejected;
- episodes created;
- episodes matched;
- broadcasts created;
- broadcasts matched;
- title conflicts;
- date conflicts;
- identifier conflicts.

## Idempotency requirements

Running the same importer version against byte-identical input must not create duplicate canonical entities.

A second execution should either:

- detect the completed import batch and exit successfully without mutation; or
- run a verification-only reconciliation.

## Testing requirements

Minimum automated cases:

1. valid source row;
2. malformed SHOW #;
3. malformed OTRW #;
4. invalid date;
5. blank title;
6. duplicate identical source row;
7. duplicate SHOW # with conflicting title;
8. duplicate OTRW # with conflicting episode;
9. re-import of identical file;
10. changed source checksum;
11. pre-existing canonical episode match;
12. pre-existing contradictory verified title.

## Historical fidelity principle

The importer is not an editor. Its job is to preserve what the source says, identify what can be normalized safely, and surface contradictions for explicit resolution.
