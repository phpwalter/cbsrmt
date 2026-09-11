# Cast Credit Recovery

## Purpose

The normalized JSON person catalogs do not contain episode appearance relationships. Those relationships are preserved in the legacy MySQL export in the `appear` table.

The canonical recovery path is therefore:

```text
sql/cbs.sql -> appear rows -> legacy episode/cast identifiers -> canonical IDs -> cast_credits.json
```

## Legacy source structure

The legacy `appear` table contains:

- `appear_id`
- `episode_id`
- `episode_date`
- `episode_name`
- `cast_id`
- `cast_id_name`

Only `episode_id` and `cast_id` are used as identity-bearing relationship keys. The copied episode date, episode title, and cast handle are retained as corroborating source metadata and must not override canonical entity data automatically.

## Canonical mapping

`episode_id` maps through `data/normalized/episodes.json` using `legacy.episode_id`.

`cast_id` maps through `data/normalized/people.json` using `legacy_cast_ids`.

A cast credit is emitted only when both mappings resolve to exactly one canonical entity.

## Identifier policy

Cast-credit IDs are deterministic UUIDv5 values derived from legacy `appear_id`.

This preserves stable relationship identity across repeated imports as long as the legacy source row identity remains unchanged.

## Failure policy

The extractor hard-fails when it encounters:

- malformed `appear` INSERT rows;
- unexpected column counts;
- unknown legacy episode IDs;
- unknown legacy cast IDs;
- ambiguous legacy cast IDs mapped to multiple canonical people.

Duplicate episode/person pairs are reported as warnings because the source may contain repeated appearances that require historical review before deduplication.

## Source evidence

Every emitted cast credit records:

- source artifact path;
- SQL line locator;
- SHA-256 of the source INSERT line;
- original `appear_id`;
- legacy episode ID/date/title;
- legacy cast ID/handle.

This allows any canonical relationship to be traced back to its exact source statement.

## Non-authoritative legacy fields

The following copied values are evidence, not canonical truth:

- `episode_date`
- `episode_name`
- `cast_id_name`

Differences between these fields and the normalized episode/person records should generate reconciliation observations rather than silent canonical changes.

## Character roles

The `appear` table does not include character names. Therefore recovered credits currently set `character_name` to null.

Character-role enrichment requires an independent source and must not be inferred from ordering, episode title, or actor identity.

## Ordering

Legacy `appear_id` is preserved but must not be interpreted as billing or cast order without evidence. `credit_order` therefore remains null.

## Determinism

For identical SQL, episode, and person inputs, extraction must produce byte-for-byte stable JSON output.

Output sorting is based on legacy episode ID and then legacy appearance ID. Runtime timestamps are not written into canonical output.
