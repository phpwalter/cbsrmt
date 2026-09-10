# Workbook Canonicalization

Workbook canonicalization is intentionally disabled until the source workbook has been inspected, staged, mapped, reviewed, and checksum-bound.

## Required sequence

1. Inspect the workbook with `tools/inspect_workbook.py`.
2. Stage the workbook with `tools/stage_workbook.py`.
3. Review the machine-readable inspection report.
4. Create a mapping from `config/workbook-mapping.example.yaml`.
5. Set the workbook and relevant sheets to `APPROVED` only after review.
6. Record `approvedBy`, `approvedAt`, and `approvalNote`.
7. Validate the mapping with `tools/validate_workbook_mapping.py`.
8. Run `tools/workbook_gate.py` against the exact workbook bytes.
9. Run `tools/plan_workbook_import.py` and review every blocked row and entity count.
10. Only then enable the required canonical entity handlers.

## Handler activation rule

Canonical entity handlers are registered explicitly in `tools/workbook_handlers.py`.

The initial registry contains:

- `episode`
- `broadcast`
- `person`
- `episode_credit`
- `work`
- `adaptation`
- `recording`

All handlers initially fail closed. A handler may be enabled only after an approved mapping proves what the source fields mean and how identity, nulls, conflicts, and provenance should be handled.

No handler may derive a canonical field from a workbook column that is not present in the approved mapping.

## Dry-run plan

`tools/plan_workbook_import.py` transforms staged values using only approved transforms and returns a JSON plan. It performs no canonical writes.

The plan contains:

- workbook filename and SHA-256;
- approving reviewer;
- planned row count;
- blocked row count;
- canonical entity counts;
- transformed values by entity;
- source-cell coordinates and raw values for provenance;
- `canonicalWritesPerformed: false`.

A blocked row must be resolved before production canonicalization unless the approved policy explicitly allows row-level quarantine.

## Execution semantics

`tools/import_workbook.py` re-validates the mapping and canonicalization gate before execution. Each staged workbook row is processed within its own nested transaction/savepoint.

If an enabled handler fails:

- row changes are rolled back;
- the finding is recorded as an `ERROR` quality issue;
- the staged row is copied into quarantine with sheet and row coordinates;
- processing may continue with subsequent rows.

The outer import batch records accepted and rejected row counts.

## Transform rules

Transforms are registered explicitly in `tools/workbook_transforms.py`. Supported transforms are deterministic and side-effect free:

- `identity`
- `trim`
- `integer`
- `decimal`
- `date`
- `datetime`
- `boolean`
- `normalize_name`
- `split_names`

Unknown transforms fail closed. Transform functions must not perform database lookups or infer domain semantics.

## Provenance

Every mapped field carries its source header, source cell address, raw value, normalized value, and provenance policy into the handler context. Enabled handlers are responsible for persisting the appropriate `provenance.source_assertions` and identifier relationships.

Canonical values must therefore remain traceable to the exact workbook, sheet, row, and cell that asserted them.

## Non-negotiable rules

- Never enable a generic dynamic table writer.
- Never interpolate target table names from mapping YAML.
- Never canonicalize from a workbook whose checksum differs from the approved checksum.
- Never silently discard blocked rows.
- Never let transform functions invent historical facts.
- Never treat a workbook row number as a durable canonical identifier.
- Never enable a handler until its identity and conflict rules are documented and tested.
