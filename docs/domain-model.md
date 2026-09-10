# CBSRMT Foundation Domain Model

## Design goals

The foundation model is intended to preserve historical fidelity while supporting a modern API, deterministic imports, conflict detection, and future enrichment.

The model deliberately separates canonical entities from source-specific assertions and identifiers.

## Core entities

### episodes

Represents one canonical CBS Radio Mystery Theater episode.

Suggested attributes:

- `episode_id` UUID primary key
- `canonical_number` integer nullable until verified
- `title` text
- `subtitle` text nullable
- `synopsis` text nullable
- `original_air_date` date nullable
- `duration_seconds` integer nullable
- `series_name` text default `CBS Radio Mystery Theater`
- `verification_status` enum/text
- `created_at`
- `updated_at`

Do not use historical numbering as the physical primary key.

### broadcasts

Represents one actual airing of an episode.

Suggested attributes:

- `broadcast_id` UUID primary key
- `episode_id` UUID foreign key
- `broadcast_at` timestamptz/date depending source precision
- `broadcast_type` (`original`, `rerun`, `unknown`)
- `station_id` nullable
- `network_id` nullable
- `verification_status`
- `created_at`
- `updated_at`

An episode may have many broadcasts.

### people

Represents a real person associated with an episode or production.

Suggested attributes:

- `person_id` UUID primary key
- `display_name`
- `given_name` nullable
- `middle_name` nullable
- `family_name` nullable
- `suffix` nullable
- `birth_date` nullable
- `death_date` nullable
- `notes` nullable

### credit_roles

Controlled vocabulary for production and performance roles.

Examples:

- actor
- writer
- adapter
- director
- producer
- host
- announcer
- composer
- sound

### episode_credits

Many-to-many relationship between episodes and people.

Suggested attributes:

- `episode_credit_id` UUID primary key
- `episode_id`
- `person_id`
- `credit_role_id`
- `character_name` nullable
- `billing_order` nullable
- `notes` nullable

### works

Represents an underlying literary, dramatic, historical, or other source work when an episode is adapted from one.

Suggested attributes:

- `work_id` UUID primary key
- `title`
- `work_type`
- `publication_date` nullable
- `description` nullable

### work_contributors

Links people to source works as authors, playwrights, editors, etc.

### episode_adaptations

Links episodes to works.

Suggested attributes:

- `episode_id`
- `work_id`
- `adaptation_type`
- `notes`

### genres

Controlled or curated genre vocabulary.

### episode_genres

Many-to-many episode-to-genre mapping.

### recordings

Represents a known recording or media representation.

Suggested attributes:

- `recording_id` UUID primary key
- `episode_id` nullable
- `broadcast_id` nullable
- `media_type`
- `format`
- `duration_seconds` nullable
- `uri` nullable
- `checksum` nullable
- `quality` nullable
- `rights_status` nullable

A recording may correspond to the canonical episode generally or to a particular broadcast if evidence supports that level of precision.

## Source and provenance model

### sources

Represents a data source.

Examples:

- 1982 broadcast log
- legacy XLS workbook
- legacy ZIP archive
- external catalog
- manually researched correction

Suggested attributes:

- `source_id` UUID primary key
- `source_type`
- `name`
- `description`
- `uri` nullable
- `license` nullable
- `retrieved_at` nullable

### import_batches

Represents one deterministic ingestion execution.

Suggested attributes:

- `import_batch_id` UUID primary key
- `source_id`
- `source_checksum`
- `importer_version`
- `started_at`
- `completed_at`
- `status`
- `rows_seen`
- `rows_accepted`
- `rows_rejected`

### external_identifiers

General mapping between canonical entities and identifiers from outside systems.

Suggested attributes:

- `external_identifier_id` UUID primary key
- `entity_type`
- `entity_id`
- `namespace`
- `identifier_value`
- `source_id`
- `valid_from` nullable
- `valid_to` nullable

Example namespaces:

- `cbsrmt.show_number`
- `otrwalter.broadcast_number`
- future third-party catalog namespaces

The 1982 log's SHOW # should normally identify an episode while OTRW # should identify a broadcast occurrence.

### source_assertions

Optional but recommended generalized provenance table for facts where multiple historical sources can disagree.

Suggested attributes:

- `source_assertion_id` UUID primary key
- `source_id`
- `import_batch_id` nullable
- `entity_type`
- `entity_id`
- `field_name`
- `raw_value`
- `normalized_value` nullable
- `confidence` nullable
- `verification_status`
- `observed_at` nullable
- `created_at`

This allows the canonical catalog to resolve a value without destroying contrary source evidence.

## Supporting entities

Later migrations may add:

- `networks`
- `stations`
- `series`
- `characters`
- `organizations`
- `locations`
- `awards`
- `collections`
- `collection_items`
- `user_accounts`
- `favorites`
- `playlists`

These should not block the catalog foundation.

## Data integrity rules

1. A broadcast must reference exactly one episode.
2. A rerun must not create a second canonical episode.
3. External identifiers must be unique within their namespace where the historical system guarantees uniqueness.
4. Source files must be checksum-addressable for reproducible imports.
5. Importing the same source with the same importer version must be idempotent.
6. Conflicting assertions must not be silently discarded.
7. Canonical corrections must remain traceable to the source or adjudication that caused them.
8. Raw source data must remain immutable.
9. Dates with incomplete source precision must not be fabricated into false precision.
10. API-facing IDs must be stable and independent of source numbering.

## Recommended schemas

PostgreSQL schemas can make the boundaries explicit:

- `catalog` — canonical domain entities
- `provenance` — sources, assertions, identifiers, import batches
- `staging` — import-specific normalized staging data
- `app` — application-level functions/API access layer if stored procedures are adopted

## First migration slice

The minimum useful production slice should create:

- `catalog.episodes`
- `catalog.broadcasts`
- `catalog.people`
- `catalog.credit_roles`
- `catalog.episode_credits`
- `provenance.sources`
- `provenance.import_batches`
- `provenance.external_identifiers`

That is enough to ingest the known 1982 log correctly without prematurely modeling every future feature.
