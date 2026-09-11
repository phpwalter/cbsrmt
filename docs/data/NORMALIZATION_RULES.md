# CBS RMT Normalization Rules

## Purpose

This document defines the operational rules used to transform historical CBS Radio Mystery Theater source artifacts into canonical data. The objective is not to make the source look cleaner. The objective is to produce a reproducible catalog while preserving evidence, ambiguity, and provenance.

## Core rule

A normalization step may change representation without changing historical meaning.

Examples of safe normalization:

- trim leading and trailing whitespace;
- collapse repeated internal whitespace where it is clearly formatting noise;
- normalize Unicode into NFC;
- parse an unambiguous ISO date into a date value;
- map a trusted legacy numeric episode identifier to a canonical UUID;
- represent a known source spelling as an alias while preserving it verbatim in provenance.

Examples of unsafe normalization without corroborating evidence:

- changing a person's birth or death date because it appears implausible;
- merging two people solely because their names are similar;
- assigning a writer from a fuzzy name match;
- changing a historical title merely for preferred capitalization;
- inventing a month or day for a partial date;
- replacing an unknown value with an assumed value.

## Deterministic identifiers

Canonical identifiers use UUIDv5 where an entity has a durable natural source identity.

The project namespace UUID is fixed and must not be changed after identifiers are published.

Episode IDs are generated from:

```text
episode:number:<episode_number>
```

when a trusted episode number exists.

Fallback identifiers may use another stable key only when the policy for that entity is explicitly documented. Mutable display text must not become the sole durable identity when a better source key exists.

## Episode normalization

The first-pass episode transformation maps legacy fields as follows:

| Legacy field | Canonical meaning |
| --- | --- |
| `episode_id` | `episode_number` plus canonical ID input |
| `episode_date` | `original_air_date` |
| `episode_name` | `title` |
| `episode_plot` | `synopsis` |
| `episode_writer` | unresolved writer source text |
| `origwriter` | unresolved original/source-author text |
| `genre_id` | unresolved legacy genre identifier |

Writer and genre relationships are intentionally deferred until their respective catalogs have been normalized and reconciliation can be performed against canonical identities.

## Person normalization

The legacy cast and writer datasets overlap and must be treated as source views of the same conceptual Person entity.

Candidate identity evidence, in descending order of confidence:

1. identical trusted legacy person/cast identifier;
2. explicit cross-source mapping;
3. identical stable source slug where corroborated;
4. exact normalized full name with compatible biographical evidence;
5. manual resolution.

A fuzzy name similarity score may identify review candidates but must never automatically merge people.

### Canonical name

Canonical names are assembled conservatively from source name components after Unicode and whitespace normalization.

The original component values remain available through source records or aliases.

### Biographical dates

Birth and death dates are facts, not formatting fields. A syntactically valid date may still be historically incorrect.

The pipeline therefore distinguishes:

- parse validity;
- logical plausibility;
- historical verification.

For example, a record whose death date precedes a known career period should be flagged for review rather than overwritten automatically.

## Writer reconciliation

`data/episodes.json` contains writer names as free text while `data/writers.json` contains person-shaped writer records.

Resolution must follow this order:

1. normalize source whitespace and Unicode;
2. attempt exact canonical-name match;
3. attempt exact known-alias match;
4. attempt explicit legacy mapping;
5. emit an unresolved relationship for review.

Do not use fuzzy matching as an automatic fifth step.

The `origwriter` field must not automatically be classified as the same credit type as `episode_writer`. Its semantics must be verified against the corpus before a controlled `writer_credit.credit_type` mapping is finalized.

## Genre reconciliation

Legacy genre identifiers are mapped through `data/genre.json`.

The source currently includes the spelling `Unkown`. The canonical representation may use `Unknown`, but the original spelling must remain traceable through provenance.

Genre IDs in source data are legacy identifiers, not public canonical IDs.

## Missing, unknown, disputed, and invalid

These conditions are distinct:

### Missing

The source does not contain a value.

### Unknown

The project has evidence that the value is not currently known.

### Disputed

Multiple incompatible source claims exist.

### Invalid

A source value cannot be parsed or violates a structural invariant.

Invalid source data must remain visible in validation output. It must not disappear simply because a canonical record cannot be produced from it.

## Validation severity

Validation output uses at least two levels.

### Error

An error prevents trustworthy canonicalization of the affected required fact or violates a hard invariant.

Examples:

- duplicate trusted episode number;
- malformed required identifier;
- empty required title;
- unresolved foreign key in a finalized relationship;
- duplicate canonical ID.

### Warning

A warning allows canonical output but requires investigation or acknowledges uncertainty.

Examples:

- suspicious biographical date;
- source spelling mismatch;
- unresolved optional writer text during an intermediate normalization stage;
- duplicated descriptive text that does not violate identity constraints.

## Provenance locators

Every normalized source-derived record must identify the source artifact and a stable locator.

For JSON arrays, the initial locator format is a JSON-pointer-like index:

```text
/0
/1
/2
```

For other source types, examples include:

```text
worksheet:Episode Data,row:42
sql:episode,pk:42
lines:120-127
```

Locators identify evidence; they are not canonical entity identifiers.

## Deterministic serialization

Generated JSON must be deterministic.

Requirements:

- UTF-8 encoding;
- normalized Unicode;
- sorted object keys;
- stable array ordering defined by domain semantics;
- final newline;
- no execution timestamps in canonical exports;
- no random UUID generation;
- no dependency on filesystem enumeration order.

Repeated execution with byte-identical inputs and the same transformation version must produce byte-identical normalized output.

## Source manifest

`data/source-manifest.json` declares the source artifacts that participate in normalization or reconciliation.

`scripts/build_source_manifest.py` generates `data/normalized/source-manifest.lock.json` containing deterministic file sizes and SHA-256 hashes.

That lock file identifies the exact source corpus used for a normalization run.

## Transformation versions

Any change that can alter canonical output requires a transformation-version change.

Examples:

- identifier algorithm changes;
- field mapping changes;
- name normalization changes;
- reconciliation policy changes;
- controlled vocabulary changes.

A refactor that provably leaves canonical output unchanged does not necessarily require a transformation-version increment.

## Manual corrections

Manual corrections must never be applied by directly editing generated normalized files.

The eventual correction mechanism must record:

- target entity and field;
- old/candidate values;
- resolved value;
- source evidence;
- rationale;
- resolution status.

The normalization pipeline then reproduces the corrected canonical output from source plus explicit resolution data.

## Current implementation state

The foundation implementation currently includes:

- source inventory declaration;
- deterministic source hashing;
- deterministic first-pass episode normalization;
- structural episode validation;
- stable UUIDv5 episode identifiers.

The next normalization stages are:

1. genre normalization;
2. person normalization from cast and writer source catalogs;
3. cast/writer identity reconciliation;
4. episode-to-writer relationship creation;
5. episode-to-genre relationship creation;
6. cross-source anomaly and conflict reporting.
