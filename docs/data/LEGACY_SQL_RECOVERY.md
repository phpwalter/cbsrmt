# Legacy SQL Completeness and Recovery

## Purpose

The legacy `sql/cbs.sql` export contains both historical catalog information and application-era implementation detail. The modernization effort must recover unique historical facts without treating the entire database dump as authoritative.

This document defines the recovery policy.

## Recovery principle

The SQL export is evidence, not the canonical schema.

A legacy table may contribute one of five things:

1. a primary relationship not available elsewhere;
2. corroborating copies of catalog data already represented in JSON;
3. lookup/reference data;
4. administrative/application data unrelated to the CBS RMT historical catalog;
5. unknown content requiring review.

Only the first three categories participate in canonical normalization.

## Inventory workflow

Run:

```bash
python scripts/inventory_legacy_sql.py
python scripts/classify_legacy_sql.py
```

The first command performs a static scan of `sql/cbs.sql` and produces:

```text
data/normalized/legacy_sql_inventory.json
```

The second command applies governed table classifications from:

```text
data/legacy-table-classification.json
```

and produces:

```text
data/normalized/legacy_sql_classified.json
```

Unknown tables remain `review_required` until explicitly classified.

## Classification meanings

### `relationship_source`

The table contains a relationship that is absent from the simpler JSON exports.

Example:

```text
appear -> cast_credits
```

For such tables, relationship keys are authoritative subject to successful reconciliation.

### `catalog_source`

The table overlaps a canonical catalog already represented by JSON.

Examples may include episode, cast, or writer tables.

These tables are compared against the normalized JSON-derived records. They may reveal missing fields or conflicting claims, but they do not automatically overwrite canonical values.

### `lookup_source`

The table contains controlled vocabulary or lookup values such as genres.

Lookup tables are reconciled against corresponding JSON exports and may contribute aliases or legacy identifiers.

### `administrative`

The table belongs to the historical application rather than the radio-program catalog.

Examples include application users, sessions, or other implementation-specific state.

Administrative data is excluded from the modernization unless a later requirement explicitly brings it into scope.

### `review_required`

The table has not yet been classified.

No automated canonical import may consume a `review_required` table.

## Field-level authority

Authority is field-specific, not merely table-specific.

For example, the legacy `appear` table contains:

```text
appear_id
episode_id
episode_date
episode_name
cast_id
cast_id_name
```

The canonical recovery interpretation is:

| Legacy field | Treatment |
| --- | --- |
| `appear_id` | stable legacy relationship identifier |
| `episode_id` | relationship key |
| `cast_id` | relationship key |
| `cast_id_name` | corroborating person handle |
| `episode_date` | corroborating episode evidence |
| `episode_name` | corroborating episode evidence |

Copied descriptive fields never overwrite canonical episode records merely because they occur in the relationship table.

## Completeness analysis

For each recoverable SQL table, the pipeline should answer four questions:

1. Does the table contain entities or relationships not present in normalized JSON?
2. Does it contain attributes absent from the current canonical model?
3. Does it disagree with the JSON source on any identity-bearing fields?
4. Does it expose useful provenance or alternate identifiers worth retaining?

The result of this analysis determines whether a dedicated extractor is required.

## Reconciliation rules

When SQL and JSON disagree:

- preserve both source claims;
- do not choose a value solely because one source is relational;
- compare source age, specificity, and field semantics;
- emit a conflict or review item where authority is unresolved;
- use a version-controlled reconciliation override only after review.

## Required guarantees

A recovery extractor must:

- never execute the legacy SQL dump;
- statically parse only the table(s) it owns;
- reject unexpected column counts;
- map legacy identifiers to canonical identifiers explicitly;
- report every unresolved foreign key;
- retain source location and/or source hash;
- sort output deterministically;
- produce the same output for the same input bytes;
- fail the pipeline on unresolved structural errors.

## Current recovered relationship

The `appear` table has been identified as the primary historical source for episode-to-cast relationships and is handled by:

```text
scripts/extract_cast_credits.py
```

Its canonical output is:

```text
data/normalized/cast_credits.json
```

## Next recovery targets

After inventory/classification runs against the full SQL export, remaining tables should be reviewed in this order:

1. episode metadata tables;
2. writer/author relationship tables;
3. broadcast or air-date history tables;
4. media/audio/link tables;
5. alternate identifier or alias tables;
6. remaining lookup tables;
7. administrative tables only if future product requirements justify them.

This ordering favors historical catalog completeness over reconstruction of the old application's implementation details.
