# Workbook Archaeology and Ingestion Workflow

Legacy spreadsheet files are treated as historical source evidence, not as trusted database schemas.

The workbook workflow is deliberately split into discovery, staging, review, mapping, and canonicalization. No workbook column may write to `catalog.*` until a reviewed mapping manifest has been approved.

## 1. Inspect the workbook

Run:

```bash
python tools/inspect_workbook.py "cbs_rmt [02.15.02].xls" --output artifacts/workbook-inspection.json
```

The report records:

- file name, format, and SHA-256 checksum;
- sheet names and visibility;
- row and column counts;
- assumed header row;
- normalized headers;
- blank counts and blank percentages;
- distinct-value counts;
- candidate-key detection;
- observed value types;
- numeric and date ranges when detectable;
- formulas and merged cells where the workbook format exposes them;
- representative rows and column samples.

The inspection report always emits:

```text
mappingStatus: REVIEW_REQUIRED
```

Inspection does not infer canonical database mappings.

## 2. Stage the workbook

Run:

```bash
python tools/stage_workbook.py "cbs_rmt [02.15.02].xls"
```

Staging persists the workbook structure into:

```text
staging.workbooks
staging.workbook_sheets
staging.workbook_rows
staging.workbook_cells
```

The staging model preserves source coordinates down to the individual cell:

```text
workbook
  -> sheet
      -> row number
          -> column number
          -> column letter
          -> cell address
          -> header name
          -> raw value
          -> normalized value
          -> value type
          -> formula
```

This provides a stable provenance address such as:

```text
cbs_rmt [02.15.02].xls / Episodes / H1274
```

without requiring the workbook layout to become the production data model.

## 3. Review the inspection report

Before mapping, review each sheet for:

- actual semantic purpose;
- header location;
- duplicate or repeated header rows;
- identifier columns;
- date semantics;
- person/cast fields;
- adaptation/source-work fields;
- rerun or rebroadcast fields;
- recording/media fields;
- formulas versus literal historical values;
- hidden sheets and auxiliary lookup sheets;
- ambiguous abbreviations;
- sparse columns;
- conflicting numbering systems.

A statistically unique column is only a **candidate key**. It is not automatically a canonical identifier.

## 4. Create a reviewed mapping manifest

Start from:

```text
config/workbook-mapping.example.yaml
```

The manifest must bind itself to the inspected workbook checksum and identify every approved mapping explicitly.

A mapping should define at minimum:

```yaml
- sourceHeader: SHOW #
  target:
    entity: episode
    field: canonical_number
  transform: integer
  required: true
  provenance: preserve_raw_and_normalized
```

The workbook-level status must remain:

```text
REVIEW_REQUIRED
```

until the evidence has been reviewed.

Canonicalization is permitted only when the manifest status is:

```text
APPROVED
```

## 5. Quality classification

Workbook records use the same project-wide quality policy:

```text
INFO     -> retain finding, canonicalization allowed
WARNING  -> retain finding, canonicalization allowed
ERROR    -> quarantine row/cell, canonicalization blocked
FATAL    -> stop the workbook batch
```

Examples of probable workbook quality rules include:

- malformed identifier;
- duplicated identifier where uniqueness is expected;
- invalid or impossible date;
- ambiguous date precision;
- unexpected blank in a required mapped field;
- conflicting canonical episode title;
- conflicting episode/broadcast relationship;
- unresolved person name ambiguity;
- formula in a field expected to contain literal historical evidence.

Rules are added only after workbook structure is observed.

## 6. Canonicalization boundary

The current workbook tooling intentionally stops at staging.

The future canonical importer must:

1. require an approved mapping manifest;
2. verify the workbook SHA-256 against the manifest;
3. read only mapped sheets and columns;
4. preserve cell coordinates in provenance;
5. classify quality findings before canonical writes;
6. quarantine ERROR rows;
7. stop on FATAL conditions;
8. write canonical entities through explicit domain handlers;
9. remain idempotent for the same source checksum and importer version;
10. produce a reconciliation summary after import.

There must be no generic `spreadsheet row -> catalog row` shortcut.

## 7. Current legacy XLS limitation

The repository contains `cbs_rmt [02.15.02].xls`, but the connected repository interface does not expose binary workbook contents for direct inspection in this environment.

Therefore no sheet names, column names, row counts, or workbook-derived domain conclusions have been assumed in the foundation schema.

Once the workbook bytes are available locally, the inspector is the first authorized operation. The resulting report becomes the evidence used to design the next catalog migrations.
