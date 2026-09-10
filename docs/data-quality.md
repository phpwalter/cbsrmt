# Data Quality and Quarantine Policy

## Purpose

CBSRMT combines historical source material that may be incomplete, contradictory, transcribed incorrectly, or differently numbered by different collectors. The system therefore treats data quality as an explicit workflow rather than assuming every parsed value is canonical truth.

## Severity taxonomy

### INFO

Informational observations that do not reduce confidence in the canonical record.

Examples:

- whitespace normalization;
- known source-format conversion;
- harmless legacy notation retained in provenance.

INFO findings never block canonicalization.

### WARNING

Potentially questionable data that remains usable and does not contradict an existing canonical invariant.

Examples:

- title punctuation differs from another source;
- a source omits optional metadata;
- a known alias or abbreviation is used.

WARNING findings may enter the canonical catalog, but remain visible for later review.

### ERROR

A record cannot safely enter the canonical catalog without review or correction.

Examples:

- malformed date;
- duplicate source identifier within the same source scope;
- conflicting episode title for an already-established SHOW number;
- broadcast identifier resolves to a different episode than the source row claims.

ERROR records are quarantined and excluded from canonicalization.

### FATAL

The import batch itself cannot be trusted to continue.

Examples:

- unreadable source structure;
- importer/source version mismatch;
- database invariant failure;
- source checksum or identity mismatch that indicates the wrong file was supplied.

FATAL findings terminate the import batch.

## Resolution statuses

Every finding or quarantined record uses one of these states:

- `open` — unresolved and requires review;
- `accepted` — reviewed and intentionally accepted as supplied;
- `corrected` — reviewed and corrected before canonicalization;
- `rejected` — reviewed and intentionally excluded;
- `ignored` — explicitly deemed non-actionable.

Resolution must be explicit. Importers must never silently delete quality findings.

## Canonicalization policy

| Severity | Canonicalization | Quarantine | Reconciliation failure |
| --- | --- | --- | --- |
| INFO | allowed | no | no |
| WARNING | allowed | no | no |
| ERROR | blocked | yes | yes while open |
| FATAL | blocked | yes when record-specific | yes |

An import batch containing warnings may complete. A batch containing unresolved errors may preserve valid rows, but the affected records remain quarantined and reconciliation fails until those findings are resolved. A fatal batch failure stops further canonicalization.

## Evidence preservation

Quarantined records retain:

- import batch;
- source identity;
- source line when available;
- record type;
- issue code;
- original raw record;
- parsed representation when available;
- severity;
- resolution state and note.

The raw record is never replaced by a normalized representation.

## Importer contract

All future importers should follow this sequence:

```text
read raw record
      |
      v
parse
      |
      +-- cannot parse ----------> quality issue + quarantine
      |
      v
validate
      |
      +-- WARNING ---------------> record issue; continue
      |
      +-- ERROR -----------------> record issue + quarantine; skip canonicalization
      |
      +-- FATAL -----------------> record issue; stop batch
      |
      v
stage
      |
      v
canonicalize
      |
      +-- conflict --------------> ERROR + quarantine
      |
      v
provenance assertions
```

## Reconciliation policy

`tools/reconcile.py` reports the number of open findings by severity and unresolved quarantined records.

By default reconciliation fails when any of the following exist:

- open ERROR findings;
- open FATAL findings;
- unresolved quarantined records.

INFO and WARNING findings remain visible but do not fail reconciliation.

The `--allow-open-errors` switch exists only for investigation and recovery workflows. It must not be used as the normal CI acceptance path.

## Historical-source principle

A questionable historical record is not equivalent to a bad record. The archive should preserve what a source claimed while separately deciding whether that claim is safe to promote into the canonical catalog.
