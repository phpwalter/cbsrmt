# CBS RMT API Contract

## Purpose

`api/openapi.yaml` is the canonical public contract for the modern CBS Radio Mystery Theater catalog API.

The two legacy Swagger files remain historical artifacts. They are not normative and must not be extended for new implementation work.

## Contract principles

The API is designed around catalog resources rather than application-user resources.

Primary resource families:

- episodes;
- people;
- writers;
- genres;
- search;
- system health.

The first public implementation is intentionally read-oriented. Administrative mutation/import operations should be introduced only after the normalization pipeline and provenance model are stable.

## Resource identity

Canonical API resource IDs are UUIDs and are independent from mutable presentation data.

Historical episode numbers remain first-class catalog attributes but are not the internal primary key. This permits the system to represent records whose historical numbering is missing, disputed, or corrected without changing their API identity.

## Representation conventions

Public JSON representations use `snake_case` to remain aligned with canonical normalized data and the relational model.

Dates use ISO 8601 full-date strings when day precision is known.

A `null` value means the canonical resource has no represented value for that field. It does not automatically imply the historical value is explicitly unknown or disputed; confidence is represented separately with `status` and provenance/conflict records in the data model.

## Metadata status

The shared status vocabulary is:

- `confirmed` — supported by sufficiently reliable evidence;
- `reported` — present in source material but not independently confirmed;
- `disputed` — incompatible claims remain unresolved;
- `unknown` — explicitly known to be unknown in the current corpus;
- `derived` — calculated or normalized from other evidence.

Clients must not interpret `reported` as equivalent to `confirmed`.

## Pagination

Collection endpoints use page-based pagination during the foundation phase:

```text
?page=1&page_size=25
```

Rules:

- `page` starts at 1;
- default `page_size` is 25;
- maximum `page_size` is 100;
- responses return `page`, `page_size`, `total_items`, and `total_pages`;
- pagination must be evaluated after filtering and before serialization.

If catalog volume or runtime characteristics later justify cursor pagination, that change should be introduced deliberately in a new contract version rather than silently changing semantics.

## Deterministic sorting

All collection endpoints must have deterministic ordering.

When a requested sort column is not itself unique, the runtime must apply a stable secondary sort using canonical `id`.

Example:

```text
ORDER BY title ASC, id ASC
```

This prevents duplicates or omissions while navigating pages containing equal sort values.

## Filtering

Filters are conjunctive unless explicitly documented otherwise.

For example:

```text
GET /episodes?original_air_date_from=1975-01-01&original_air_date_to=1975-12-31&genre=Mystery
```

means an episode must satisfy the date range and genre filter.

Text filters such as `title` and `name` are intended as case-insensitive contains matches in the foundation implementation. They are filters, not relevance-ranked full-text search.

## Search

`GET /search` is the cross-resource discovery endpoint.

The initial searchable resource classes are:

- `episode`;
- `person`.

Search must remain semantically distinct from exact collection filtering. A later implementation may use PostgreSQL full-text search or another ranking mechanism, but identical data and query inputs must produce deterministic result ordering when relevance scores tie.

## Writers

A writer is not a separate human entity type in the canonical model.

`/writers` is a read model over `person` records having one or more `writer_credit` relationships. `/writers/{writerId}` therefore uses the same canonical UUID as `/people/{personId}`.

This avoids creating duplicate identities when the same participant appears as both performer and writer.

## Episode detail

`GET /episodes/{episodeId}` returns the episode plus its principal catalog relationships:

- cast credits;
- writing credits;
- genres;
- broadcasts.

Relationship arrays must use deterministic ordering. Recommended defaults are:

- cast: `credit_order`, then person sort name, then credit ID;
- writers: `credit_order`, then person sort name, then credit ID;
- genres: canonical genre name, then genre ID;
- broadcasts: broadcast date, broadcast type, then broadcast ID.

Null order values must be handled consistently and documented in implementation tests.

## Error representation

Errors use `application/problem+json` following RFC 7807-style semantics.

Minimum fields:

```json
{
  "type": "https://example.invalid/problems/not-found",
  "title": "Resource not found",
  "status": 404,
  "detail": "No episode exists with the supplied identifier."
}
```

Production problem `type` URIs must be replaced with stable project-owned identifiers before public release.

## HTTP behavior

Read endpoints must observe standard HTTP semantics:

- `200` for successful reads;
- `400` for invalid query/path input where applicable;
- `404` when a canonical resource identifier does not exist;
- `500` only for unexpected server faults, not validation errors.

A later implementation should add request correlation IDs and explicit rate-limit behavior if operational requirements justify them.

## Versioning

The foundation contract version is identified in `info.version` as `2.0.0-foundation`.

This is a project artifact version, not a URI version. No `/v1` or `/v2` URI prefix is introduced during the foundation phase.

Backward-incompatible public contract changes must not be made silently after an implementation is released to consumers.

## Contract ownership

The OpenAPI document is authoritative for externally observable API behavior.

Implementation code, tests, database queries, generated client models, and documentation must conform to the contract. When they disagree, either:

1. implementation behavior must be corrected to match the contract; or
2. the contract must be intentionally revised and reviewed as an API change.

The runtime must not acquire undocumented fields or endpoints through incidental framework behavior.
