# CBSRMT Data Archaeology

## Purpose

This document records the historical source material currently present in the repository and the domain conclusions that can be made without inventing missing data.

## Source inventory

### `CBSRMT_Log_1982.txt`

The 1982 broadcast log explicitly distinguishes two numbering systems:

- **SHOW #** — identifies each unique episode/broadcast program once and does not count reruns.
- **OTRW #** — identifies each individual broadcast occurrence and is intended to include both original broadcasts and reruns.

The file currently lists original broadcasts and notes that reruns were intended to be added later.

This distinction is architecturally significant: an episode and a broadcast occurrence are different domain objects.

### `cbs_rmt [02.15.02].xls`

Legacy spreadsheet catalog. GitHub exposes the file but not its workbook contents through the repository connector because it is a binary XLS file. It should be treated as a primary archaeology source and imported only after workbook sheets, columns, datatypes, formulas, and anomalies are inspected directly.

### `cbs_rmt [02.15.02].zip`

Legacy archive associated with the spreadsheet. Contents must be inventoried before use.

### Artwork and media assets

The repository contains historical artwork and design files. These are not part of the normalized catalog model but may later become source-backed media assets.

## Confirmed domain rule

### Episode identity is not broadcast identity

A unique CBS Radio Mystery Theater episode can have one or more broadcast occurrences.

Therefore:

- `episodes` represents the canonical program/episode.
- `broadcasts` represents an individual airing.
- reruns create additional `broadcasts` rows, not duplicate `episodes` rows.
- external numbering systems belong in identifiers or source mappings, not as the database primary key.

## Provenance requirement

Historical catalog data may conflict across sources. Every imported assertion that can vary by source should retain provenance.

The foundation data model therefore requires:

- source records;
- source identifiers;
- import batch identity;
- original source value where normalization changes representation;
- confidence or verification state where appropriate;
- timestamps for ingestion and later verification.

## Initial bounded context

The first normalized catalog should support these concepts:

1. episodes
2. broadcasts
3. people
4. episode credits
5. works and adaptations
6. genres/tags
7. recordings/media
8. external identifiers
9. sources
10. import batches

## Questions the model must eventually answer

- What is the canonical episode identified by a given historical show number?
- On what dates was an episode broadcast or rebroadcast?
- Which actors appeared in an episode?
- Which episodes involved a particular actor, writer, director, producer, or host?
- Which episodes were adaptations, and what source work were they based on?
- Which external catalog identifiers refer to the same episode or broadcast?
- Which source supplied a particular catalog fact?
- Which recordings or media assets are associated with an episode or broadcast?

## Import policy

Historical source files are immutable inputs. Importers may normalize data into staging tables, but must not silently overwrite conflicting values. Conflicts are to be surfaced for deterministic resolution.

Recommended pipeline:

`raw source -> staging -> validation -> normalization -> provenance mapping -> canonical catalog`

## Next archaeology step

Inspect the XLS workbook and ZIP contents outside the GitHub text-content API, document their complete structures, and build a field-by-field mapping into staging tables before production migrations depend on them.
