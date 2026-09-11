# Identity and Relationship Reconciliation

## Purpose

CBS RMT source data represents the same human beings in more than one catalog. `data/cast.json` is the broad person/cast catalog, while `data/writers.json` contains a writer-focused subset that repeats the same legacy identifiers and biographical structure. Episode records separately carry writer names as free text.

The normalization layer must therefore establish one canonical `Person` identity before writer and cast relationships can be trusted.

## Reconciliation order

Automatic reconciliation follows this precedence:

1. identical trusted legacy `cast_id`;
2. exact normalized full-name match when a legacy identifier is absent;
3. no automatic merge when those checks fail.

Fuzzy matching is intentionally excluded from the automatic pipeline. Similar names generate review work; they do not prove identity.

## Canonical person record

A canonical person may preserve:

- one stable UUIDv5 canonical identifier;
- one or more legacy cast identifiers;
- one or more legacy handles (`cast_id_name`);
- the canonical display name;
- sort name;
- source spellings/aliases;
- biographical fields;
- URLs and media references;
- source roles showing whether the record appeared in cast, writer, or both catalogs;
- provenance locators for every contributing source row;
- a metadata confidence status.

## Conflict behavior

When two source rows reconcile to the same person but disagree on a non-empty field, the pipeline does not silently choose a historical truth. It selects a deterministic value for reproducible output and records all competing values in the validation report.

Such records receive `reported` status until reviewed.

Examples of conflicts include:

- different birth or death dates;
- different spellings beyond harmless whitespace differences;
- conflicting biographies;
- different URLs;
- incompatible middle names.

## Suspicious biographical dates

A date being syntactically valid does not mean it is historically plausible. The source corpus already contains examples where a person's birth/death values appear questionable.

Historical plausibility validation is therefore separate from basic date parsing. Corrections require evidence and must retain the original source value in provenance.

## Episode writer resolution

Episode records contain `episode_writer` and `origwriter` as free text. After people normalization, relationship resolution uses exact normalized-name or recorded-alias lookup.

A unique match produces a writer-credit relationship.

No match produces a review warning.

Multiple matches produce an ambiguity warning containing candidate person IDs.

The resolver never chooses among ambiguous candidates automatically.

`episode_writer` maps initially to `credit_type = writer`.

`origwriter` maps initially to `credit_type = source_author` because the legacy field appears to represent original/source authorship. This remains a semantic assumption subject to source-corpus verification; the raw source value is retained.

## Genre resolution

Episode `genre_id` values are resolved through the normalized genre registry's preserved legacy identifiers. The relationship uses canonical genre UUIDs after resolution.

The source value remains traceable and spelling corrections in genre names do not alter relationship identity.

## Determinism

For unchanged source data and transformation version:

- person grouping is stable;
- canonical IDs are stable;
- output ordering is stable;
- validation warning ordering is stable;
- relationship resolution is stable.

Manual correction data, when introduced, must itself be version-controlled input so that it does not undermine reproducibility.

## Next reconciliation layer

The next stage should add explicit override/mapping files for reviewed identity decisions, validate biographical plausibility, derive database-ready relationship datasets, and reconcile cast-to-episode credits from the legacy SQL/export sources where those relationships are available.
