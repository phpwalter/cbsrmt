# CBS RMT Modernization Foundation

## Purpose

This document defines the modernization baseline for the CBS RMT repository. It does not attempt to rewrite the historical archive in place. Instead, it establishes the rules under which legacy source material is interpreted, normalized, validated, and exposed through future application interfaces.

## Architectural principles

### 1. Preserve source evidence

Historical assets are immutable inputs. Spreadsheet exports, SQL dumps, text logs, images, and existing JSON files are source evidence. They may be relocated with history intact, but normalized outputs must not overwrite them.

### 2. Normalize relationships, not just records

The historical data contains repeated human-readable names and denormalized episode attributes. The modern model must separate durable entities from relationships. A person is represented once; appearances in episodes are represented as credits.

### 3. Deterministic transformation

Given the same input files and transformation version, the normalization pipeline must produce the same canonical output. Imports must not rely on wall-clock values, unordered iteration, or network lookups unless those inputs are explicitly captured and versioned.

### 4. Provenance is part of the data model

A normalized value is incomplete without a traceable origin when multiple historical sources disagree. Corrections must preserve the prior evidence and explain why the canonical value changed.

### 5. Contract-first API design

The maintained OpenAPI document is the public contract. Runtime behavior, validation, tests, and documentation must conform to it. The current legacy Swagger/OpenAPI files are inputs for discovery only and are not authoritative.

### 6. Read-first product scope

The first modern API release should focus on trustworthy catalog access: episodes, people, writers, genres, credits, broadcasts, and search. Administrative mutation endpoints should be introduced only after data ownership, validation, and audit behavior are defined.

## Bounded contexts

### Catalog

Owns canonical episode identity and descriptive metadata.

Primary concepts:

- Episode
- Broadcast
- Genre
- Synopsis
- Production metadata

### People and credits

Owns normalized people and their participation in productions.

Primary concepts:

- Person
- CastCredit
- WriterCredit
- Role or character name

### Provenance

Owns evidence, import batches, source references, conflicts, and corrections.

Primary concepts:

- SourceArtifact
- SourceRecord
- ImportBatch
- DataConflict
- Correction

### API and search

Owns consumer-facing resource representations, query behavior, pagination, filtering, and full-text or faceted search.

## Canonical identity

Internal identifiers must be stable and independent from display names. Legacy numeric IDs may be retained when they are trustworthy, but they must not be assumed globally canonical without validation.

Episode identity should prefer the historically assigned episode number where it is unique and stable, while still maintaining an internal primary key. People require independent identifiers because names may vary by spelling, punctuation, initials, stage name, or source formatting.

## Data states

A value may be:

- `confirmed` — corroborated or trusted canonical value;
- `reported` — present in a source but not independently corroborated;
- `disputed` — conflicting source evidence exists;
- `unknown` — no reliable value is currently available;
- `derived` — computed from other source values.

These states should not be collapsed into null/non-null semantics where doing so would erase meaning.

## Import pipeline

The target pipeline is:

```text
historical source
    -> parser
    -> raw structured record
    -> normalization
    -> identity resolution
    -> validation
    -> conflict detection
    -> canonical dataset
    -> database load
    -> API contract tests
```

Every stage should be independently testable.

## Validation classes

### Structural validation

Ensures files parse and required fields have the expected type and shape.

### Referential validation

Ensures relationships reference known canonical entities.

### Historical validation

Detects impossible or suspicious dates, duplicate episode numbers, contradictory titles, malformed names, or conflicting assignments.

### Contract validation

Ensures API representations conform to the maintained OpenAPI schemas.

## Legacy API assessment

The repository currently contains early API definitions that expose generic `/user` resources and a `/ping` endpoint. Those definitions do not meaningfully represent the CBS Radio Mystery Theater catalog domain and should not become the basis of the modern public API except where generic infrastructure concepts remain useful.

The modern contract should instead model the archival catalog directly.

## Initial API surface

```text
GET /health
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

Nested relationship endpoints may be introduced where useful, for example:

```text
GET /episodes/{episodeId}/cast
GET /episodes/{episodeId}/writers
GET /people/{personId}/episodes
```

## Error model

The modern API should use a consistent machine-readable error representation based on RFC 9457 Problem Details for HTTP APIs. Validation failures should include field-level details without exposing implementation internals.

## Pagination and sorting

Collection endpoints must define deterministic ordering. Pagination must not depend on incidental database row order. Initial implementations may use page/limit semantics, but cursor pagination should be preferred if the dataset or consumer requirements justify it.

## Security posture

The catalog is expected to be publicly readable unless future product requirements dictate otherwise. Administrative imports, corrections, and mutation operations must be authenticated and authorized separately from public read access.

No secrets, credentials, or writable database configuration belong in the repository.

## Testing baseline

The foundation is complete only when automated validation can prove at least the following:

1. source datasets parse successfully;
2. canonical identifiers are unique;
3. all credit relationships resolve;
4. date fields conform to documented formats;
5. generated normalized output is deterministic;
6. the OpenAPI contract validates;
7. representative API responses validate against the contract.

## Migration strategy

The repository should be modernized incrementally. Historical artifacts remain available while modern equivalents are introduced alongside them. Once a modern artifact is verified and documented, legacy runtime artifacts may be moved into clearly labeled archival directories rather than silently deleted.

## Definition of foundation complete

The foundation phase is complete when the repository contains:

- an authoritative architecture statement;
- a documented canonical data model;
- a provenance model;
- deterministic import/validation rules;
- a maintained OpenAPI contract;
- automated validation tests;
- development instructions that reproduce the validation process locally and in CI.
