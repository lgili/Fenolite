# Altium PCB library (`.PcbLib`)

This page states, in Fenolite's own words, what `fenolite.backends.altium.pcblib` (change c0035) relies on to
write an Altium PCB library, and what the test decoder `tests/_altium_pcb_read.py` checks. The records of
a footprint are in `pcb-records.md`; the container is in `compound-file.md`.

- Sources: KiCad's developer page (S-0002), KiCad's importer read for facts only (S-0160, S-0162),
  AltiumSharp **version 1 only** (S-0150 at commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`), the
  compound-file specification (S-0145) and the oracle observations of `kicad-cli` (S-0020, S-0166).
- No Altium-saved library was opened. Altium's own requirements are unknown: every Altium row stays
  `INFERRED` until the maintainer's report (`docs/evidence/altium-pcb.md`, Part D), which counts only when made with a
  licence the maintainer may use for Fenolite (`LEGAL.md` P4). The Altium 365 Viewer does not open
  libraries (S-0149).
- Rows that only say what KiCad's importer reads carry `ORACLE-VERIFIED(kicad-cli)` since the round trips of 2026-10-03 passed on 10.0.6; that label says nothing about Altium.
- `tests/unit/test_format_facts.py` checks the tables.

## Container

| fact | source | label | hypothesis |
|---|---|---|---|
| A PCB library is a compound file; KiCad accepts a `.PcbLib` for its Altium footprint plugin when the file has the compound-file signature | S-0002, S-0162 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| The root holds the stream `FileHeader`: a 32-bit length, then one length byte and the text `PCB 6.0 Binary Library File` (the 32-bit word and the length byte both carry the text length). KiCad does not read it | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0162 | INFERRED | H-A-PCB-LIB-OPEN |
| The root holds the storage `Library` with `Header` (32-bit 1), `Data` and the storage `Models` (`Header` 32-bit 0 and `Data`, empty without 3D models). KiCad reads `Library/Models/Data` only when present; the developer page puts `Models` at the root, the code reads it under `Library` | S-0002, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0162 | INFERRED | H-A-PCB-LIB-OPEN |
| `Library/Data` is one property block (`HEADER=PCB 6.0 Binary Library File`, `WEIGHT=<footprint count>`), then a 32-bit footprint count, then each footprint name as a string block. KiCad needs the stream, refuses an empty property block and reads the whole stream | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0162 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| Each footprint is a root storage holding `Header` (32-bit primitive count), `Parameters`, `WideStrings`, `Data` and the storage `UniqueIdPrimitiveInformation` with `Header` and `Data` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-LIB-OPEN |
| KiCad finds a footprint only through a root storage that holds `Parameters` with `PATTERN`: a footprint without `Parameters` is not converted, and `kicad-cli fp upgrade` still exits 0 (local probe of the format research). Each name of `Library/Data` must be found that way | S-0162, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `Parameters` is one property block with `PATTERN` (the footprint name), `HEIGHT` (a length in mil text) and `DESCRIPTION`; KiCad reads `PATTERN` and `DESCRIPTION` | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0162 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| A footprint's `Data` is its name as a string block, then its primitive records of mixed types one after another, until fewer than 4 bytes remain; `Header`'s count is not compared with it by KiCad | S-0160, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `WideStrings` of a footprint is one property block of `ENCODEDTEXT<i>` entries, one per text; KiCad's library path does not read it | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca), S-0160 | INFERRED | H-A-PCB-LIB-OPEN |
| `UniqueIdPrimitiveInformation/Data` holds one property block per primitive with `PRIMITIVEINDEX`, `PRIMITIVEOBJECTID` (such as `Pad`, `Track`, `Arc`) and an eight-letter `UNIQUEID`; `Header` holds the count. KiCad does not read it | S-0002, S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-LIB-OPEN |
| A storage name holds at most 31 characters and none of `/ \ : !` | S-0145 | INFERRED | H-A-PCB-LIB-NAME |
| Version 1 stores a footprint whose name is not a valid storage name under its name cut to 31 characters with `/` replaced by `_`, and writes the root stream `SectionKeys` only then: a 32-bit count, then per keyed footprint its full name (a 32-bit length and the NUL-terminated text, the length counting the NUL) and its storage name (a string block) | S-0150 (version 1 at afe796434b6d2110c745c90abe44a6ddf64f5bca) | INFERRED | H-A-PCB-LIB-NAME |
| `kicad-cli fp upgrade <lib>.PcbLib -o <dir>.pretty` converts a non-KiCad library through the plugin its path selects, on 10.0 and 9.0; the message on failure is only "Unable to convert library" | S-0166, S-0020 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `kicad-cli` 10.0.6 converts the PCB library Fenolite writes for the blink sample: three `.kicad_mod` files whose pads, holes, corner ratios, lines, rectangles, arcs and circle equal the source within 10 nm; without `Parameters` a footprint gives no file and exit 0 (`tests/kicad/altium/test_pcblib_oracle.py`, 2026-10-03) | S-0020, S-0166 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-LIB |
| `kicad-cli` 9.0.9 (pinned image, local run) converts the same library with the same pads and geometry; it puts Mechanical 13 on `B.Fab` and Mechanical 15 on `Eco2.User`, and exits 2 when a footprint has no `Parameters` | S-0020, S-0166 | INFERRED | H-A-PCB-KICAD-LIB |

## Version 2 not used

AltiumSharp version 2 (2026) cites a decompilation folder that is not public, so no fact found only in
version 2 is used (`LEGAL.md` P1). These streams and forms appear there and are **not** written; none of
them is needed by KiCad, and whether Altium needs them is `H-A-PCB-LIB-OPEN`:

- the root stream `FileVersionInfo`;
- `Library/LayerKindMapping`, `Library/PadViaLibrary`, `Library/ComponentParamsTOC` and an empty
  `Library/Textures`;
- the storage `ModelsNoEmbed`;
- the longer library `FileHeader` with a version double and a unique id.

The PcbDoc `FileHeader` form also appears in version 2, but Fenolite takes it from the MIT writer S-0143,
an independent source (`pcb-document.md`).

## Fenolite's choices

- One `<design>.PcbLib` holds every KiCad footprint of the design (`project.pcblib_name`), beside c0034's
  `<design>.SchLib`; Altium footprint links (`<X>.PcbLib:<name>`) get no footprint.
- The root holds `FileHeader`, `SectionKeys` only when a storage name differs from its footprint name,
  `Library`, then one storage per footprint in the MS-CFB order of storage names. Nothing else.
- Storage names come from c0034's `project.storage_name`; two footprints with one storage name are
  refused.
- `Parameters` holds `PATTERN`, `HEIGHT=0mil` and `DESCRIPTION` (left out when it is not printable 7-bit
  ASCII); `WideStrings` is an empty property block (only the NUL); `Data` holds the pads in definition
  order, then the tracks and arcs in graphic order; `UNIQUEID` is `project.unique_id("pcblib:<name>:<i>")`
  with `i` the zero-based primitive index.
