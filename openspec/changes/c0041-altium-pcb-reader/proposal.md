## Why

v0.3 reads the second backend. Fenolite writes PCB libraries and PCB documents, and Altium Designer
26.5 opens them, but the only reader is test code that accepts Fenolite's own short records. Import
(c0043), verification (c0044) and equivalence (c0045) need a product reader for files that Altium
saved: longer records, older records, more storages and more keys.

## What Changes

- **Product reader.** `fenolite.backends.altium.read.pcb.read_pcbdoc` and
  `read.pcblib.read_pcblib` read the compound file through c0039's reader and return typed records.
- **Records read.** The board record with outline and layer stack; nets; classes; components;
  pads; tracks; arcs; vias; fills; regions; polygons; texts with their wide strings. A library
  gives its board record and each footprint.
- **Rules stay opaque.** A rule keeps its kind number, kind text, name, priority, enabled flag and
  both scope expressions; every other key stays in its field list.
- **Nothing is lost.**
  - Every record keeps its bytes. Each stream is rebuilt from its records byte for byte.
  - Unknown keys keep their order and duplicates. Bytes after the known fields are the record's tail.
  - Storages the reader does not type are kept whole.
- **Record lengths.** The reader accepts every length seen in eleven public Altium-saved files
  (saved 2016 to 2025): tracks of 45 and 49 bytes, arcs of 56 and 60, vias of 299, 321 and 351,
  fills of 46 and 50, texts of 232 and 252, pad geometry of 170 to 194 with the 651-byte layer
  block. It also accepts the short forms Fenolite writes. A longer record is read; a shorter one is
  kept raw with an issue.
- **Lenient by default.** A problem is an `Issue` with a location; `strict=True` raises.
- **Corpus.** Eleven manifest rows (seven documents, four libraries; MIT, Apache-2.0, BSD-2-Clause,
  GPL-2.0, LGPL-3.0), fetched by `tools/corpus_fetch.py`, never committed.
- **Oracles.** `kicad-cli pcb import --format altium` (10.0) and `kicad-cli fp upgrade` read the
  same files; nets, components, pads, vias, copper tracks, the copper stack and zone outlines are
  compared.
- **Field evidence.** Each typed field has a level in `FIELD_LEVELS`, equal to its row of the fact
  page.

## Capabilities

### New Capabilities

- `altium-pcb-reader`: 21 ADDED requirements (package, lossless records, property records, length
  tolerance, each record kind, library and document, issues, field evidence, corpus rows, census,
  two oracles, own files, documentation).

### Modified Capabilities

None. `corpus-policy` is unchanged: the new rows carry no `rt0` use.

## Non-goals

- No neutral model, no `AltiumBackend`, no connectivity (c0043).
- No CLI command and no `inspect`, `check` or `diff` (c0039, c0044).
- No writing and no round trip through the writers (c0044).
- No ASCII PCB document, no schematic, no project or rule file (c0040, c0042).
- No typed component bodies, 3D models, dimensions, embedded fonts, differential pairs, unions or
  violation storages: they are kept as bytes.
- No meaning for rule keys beyond kind, name, priority and scope.
- No change to the writers or the test reader.

## Evidence level required

- Framing, lengths and stream identity: `CORPUS-VERIFIED` over the eleven rows
  (`H-A-RD-PCB-FRAME`, `-IDENTITY`, `-LENGTHS`).
- Fields that KiCad's importer also reads (positions, sizes, nets, layers, the copper chain, pad
  shapes and holes, zone outlines): `ORACLE-VERIFIED(kicad-cli)` on 10.0.x. This also settles
  `H-A-UNIT`.
- Fields no oracle reads (mask expansions, classes, rule keys, polygon names, text fonts):
  `CORPUS-VERIFIED` when the corpus gives an internal check, else `INFERRED`; bytes with no agreed
  meaning stay untyped.
- No Altium author report is required: this change writes nothing.
- Sources: the fact pages, `docs/evidence/sources.md` (S-0002, S-0148, S-0150 version 1 only,
  S-0160 to S-0163, S-0170 to S-0176, S-0188, S-0199, S-0200) and S-0285 to S-0287.
