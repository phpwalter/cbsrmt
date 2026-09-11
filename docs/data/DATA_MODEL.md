# CBS RMT Canonical Data Model

## Scope

This document defines the first canonical logical model for normalized CBS Radio Mystery Theater catalog data. It is intentionally technology-neutral so that JSON exports, relational storage, and API representations can share the same semantics.

## Entities

### Episode

Represents one numbered CBS Radio Mystery Theater production.

Required fields:

- `id` — stable internal identifier;
- `episode_number` — historical CBS RMT episode number when available;
- `title` — canonical episode title;
- `status` — metadata confidence state.

Common optional fields:

- `original_air_date`;
- `synopsis`;
- `duration_seconds`;
- `production_code`;
- `notes`.

Constraints:

- `id` must be unique and immutable;
- `episode_number` must be unique where historical evidence supports uniqueness;
- titles must not be used as identifiers;
- dates use ISO 8601 calendar format (`YYYY-MM-DD`) when the full date is known.

### Person

Represents a human participant independent of any episode credit.

Fields:

- `id`;
- `canonical_name`;
- `sort_name`;
- `status`;
- `notes`.

A person may have multiple known aliases or source spellings.

### PersonAlias

Represents a spelling, stage name, abbreviated name, or alternate source representation for a person.

Fields:

- `id`;
- `person_id`;
- `name`;
- `alias_type`;
- `source_record_id`.

### CastCredit

Represents a person's performance credit on an episode.

Fields:

- `id`;
- `episode_id`;
- `person_id`;
- `character_name`;
- `credit_order`;
- `status`;
- `source_record_id`.

The same person may have multiple credits on the same episode when the historical material distinguishes multiple roles.

### WriterCredit

Represents authorship or adaptation credit associated with an episode.

Fields:

- `id`;
- `episode_id`;
- `person_id`;
- `credit_type`;
- `credit_order`;
- `status`;
- `source_record_id`.

Candidate `credit_type` values include:

- `writer`;
- `adapter`;
- `source_author`;
- `teleplay_or_script`;
- `unknown`.

The final vocabulary must be derived from the source corpus rather than imposed prematurely.

### Genre

Represents a controlled catalog classification.

Fields:

- `id`;
- `name`;
- `description`;
- `status`.

### EpisodeGenre

Many-to-many relationship between episodes and genres.

Fields:

- `episode_id`;
- `genre_id`;
- `source_record_id`;
- `status`.

### Broadcast

Represents one known broadcast or rebroadcast occurrence.

Fields:

- `id`;
- `episode_id`;
- `broadcast_date`;
- `broadcast_type`;
- `station_or_network`;
- `status`;
- `source_record_id`.

The original broadcast date may be reflected on `Episode` for convenient access but should remain derivable from broadcast evidence where possible.

## Provenance entities

### SourceArtifact

Represents a repository input artifact.

Fields:

- `id`;
- `path`;
- `artifact_type`;
- `sha256`;
- `description`;
- `captured_at`;
- `status`.

Examples include the historical XLS workbook, SQL export, text logs, and JSON files.

### ImportBatch

Represents one deterministic execution of an import pipeline.

Fields:

- `id`;
- `transform_version`;
- `source_manifest_hash`;
- `started_at`;
- `completed_at`;
- `result`.

Timestamps describe execution history; they must not affect canonical output content.

### SourceRecord

Represents a traceable record or location within a source artifact.

Fields:

- `id`;
- `source_artifact_id`;
- `locator`;
- `raw_value`;
- `record_hash`.

A locator may be a worksheet and row number, JSON pointer, SQL table/key, or text line range.

### DataConflict

Represents incompatible source claims about the same canonical fact.

Fields:

- `id`;
- `entity_type`;
- `entity_id`;
- `field_name`;
- `candidate_values`;
- `resolution_status`;
- `resolution_note`;
- `resolved_value`.

Conflicts must remain inspectable after resolution.

## Confidence/status vocabulary

Initial normalized values should use the following states:

- `confirmed`;
- `reported`;
- `disputed`;
- `unknown`;
- `derived`.

This vocabulary may later be represented as an enum or reference table.

## Identifier policy

Identifiers are durable API/data-contract keys and must not be generated from mutable display text alone.

Recommended approach:

- preserve trusted historical numeric identifiers as explicit legacy identifiers;
- assign separate canonical IDs for normalized entities;
- maintain mapping records when source systems use different IDs;
- never recycle canonical IDs.

For human-readable exports, canonical IDs should remain stable across repeated normalization runs against unchanged source inputs.

## Name normalization

Name normalization must be conservative.

Allowed normalization examples:

- trimming surrounding whitespace;
- normalizing repeated internal whitespace;
- normalizing equivalent Unicode representations;
- recording alternate punctuation or initials as aliases.

Not allowed without evidence:

- merging two people solely because names are similar;
- expanding initials by assumption;
- correcting apparent misspellings without retaining the original source representation;
- treating stage names and legal names as automatically equivalent.

## Date handling

Dates must preserve source precision.

If only a year or month is known, do not invent a full date. The physical database design should support partial or uncertain dates explicitly if the source corpus requires them.

## Null and unknown semantics

A missing value means no value was supplied in the canonical record. `unknown` means the project explicitly determined that the historical value is not currently known. `disputed` means multiple incompatible candidates exist.

These states must not be conflated.

## Relationship cardinality

```text
Episode 1 --- * CastCredit * --- 1 Person
Episode 1 --- * WriterCredit * --- 1 Person
Episode * --- * Genre (through EpisodeGenre)
Episode 1 --- * Broadcast
SourceArtifact 1 --- * SourceRecord
SourceRecord 1 --- * normalized facts/relationships
```

## Canonical JSON conventions

Normalized JSON should use:

- UTF-8;
- snake_case property names unless the API contract deliberately chooses another convention;
- explicit arrays for to-many relationships;
- ISO date strings;
- stable deterministic ordering for generated exports;
- no embedded runtime timestamps in canonical content unless they represent historical facts.

## Validation requirements

The normalization pipeline must detect at least:

- duplicate canonical IDs;
- duplicate trusted episode numbers;
- unresolved person references;
- unresolved episode references;
- malformed dates;
- empty canonical names;
- duplicate relationship rows introduced by import logic;
- conflicting values from independent source artifacts;
- non-deterministic ordering or output changes from identical input.

## Physical model follow-up

The next schema step is to map these logical entities into a relational design with explicit primary keys, uniqueness constraints, foreign keys, indexes, provenance references, and migration ownership. That physical schema must be derived from this model rather than inferred from the legacy MySQL export alone.
