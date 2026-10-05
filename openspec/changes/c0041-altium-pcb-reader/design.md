## Context

- **Need.** v0.3 reads the second backend. c0043 (import), c0044 (inspect, check, diff, round trip)
  and c0045 (equivalence) need typed PCB records read from files that Altium saved.
- **Today.**
  - `src/fenolite/backends/altium/` writes `.PcbLib` and `.PcbDoc` (c0035), and c0038 adds copper.
    Altium Designer 26.5 opens these files (author reports of 2026-10-03).
  - `tests/_altium_pcb_read.py` is a strict test reader for Fenolite's own output. It refuses
    anything that breaks a rule of the writer, so it cannot read most Altium-saved files, and it is
    test code.
  - The fact pages `docs/formats/altium/pcb-library.md`, `pcb-records.md` and `pcb-document.md`
    (and c0038's `pcb-copper.md`) state the short forms and what Altium-saved files hold.
- **What Altium-saved files hold** (census of 2026-10-03 on eleven public files that earlier changes
  already consulted; scratch copies, counts and lengths only, nothing copied):

  | record | Fenolite writes | saved 2016–2019 | saved 2021–2025 |
  |---|---|---|---|
  | track | 36 | 45 | 49 |
  | arc | 47 | 56 | 60 |
  | via | 321 (c0038) | 299 | 321, 351 |
  | fill | — | 46 | 50 |
  | text, first subrecord | 137 | 232 | 252 |
  | pad, fifth subrecord | 114 | 170, 171 | 185, 186, 194 |
  | pad, sixth subrecord | 0, 596 | 0, 651 | 0, 651 |
  | region | — | variable | variable |

  - Every primitive stream of the ten files that the test container reader opens ends exactly at a
    record end.
  - A region is the prefix, five bytes with a 16-bit hole count at 14, a property text, a vertex
    count and vertices; `ShapeBasedRegions6` holds the same regions with 37-byte vertices.
  - `Rules6` is a 16-bit number and a property block per rule, 39 to 50 rules per document.
  - Documents hold storages no fact page lists: violation storages named after a rule, primitive
    ids, differential pairs, connections, unions, parameters.
  - The document of 2017 needs DIFAT sectors, which only c0039's reader handles.
  - `FILENAME` of a saved board record holds the saving machine's path. It must never reach the
    repository or test output.
- **Constraints.** Clean-room (`LEGAL.md`, ADR-0003); the core has no runtime dependency;
  `backends.<x>` imports `model`, `geometry` and `backends.base` only; corpus files are fetched, not
  committed.

## Goals / Non-Goals

**Goals**
- Read every PCB document and library of the corpus, and every file Fenolite writes, into typed
  records.
- Lose nothing: each stream can be rebuilt from its records.
- Accept any record length at or above the shortest typed form.
- Report problems as located issues; fail only in strict mode.
- Give two independent checks: the corpus census and `kicad-cli`.
- Give c0043 one clear API.

**Non-Goals**
- The neutral model, connectivity, an `AltiumBackend` (c0043).
- CLI commands (c0039, c0044). Writing or re-encoding records (c0044).
- The ASCII PCB form; schematic, project and rule files.
- Typed component bodies, 3D models, dimensions, fonts, differential pairs, unions, violations.
- The meaning of rule keys and of scope expressions (c0042 maps rule kinds; c0043 decides).

## Decisions

1. **Five modules under `backends/altium/read/`.** `pcbprops` (property text), `pcbprims` (binary
   primitives), `pcbstack` (board record and stack), `pcb` (document) and `pcblib` (library). The
   public entry points are `read.pcb` and `read.pcblib`, the names of the naming contract.
   - Rejected: one module (about 1 500 lines; the test reader is already 650).
   - Rejected: extending the writer modules. A reader that shares code with the writer cannot check
     it.
2. **The reader does not import the writers, and the test reader stays apart.** Three independent
   readings exist: the product reader, `tests/_altium_pcb_read.py` and KiCad's importer. The layer
   name table is written again from the fact page; a unit test compares it with the writer's.
   - Rejected: importing `pcbrecords` for constants. It would couple both sides of c0044's round
     trip.
3. **Lossless by keeping bytes, not by re-encoding.** Each record keeps `raw`. Typed fields are
   views. The identity "records joined plus trailing equals the stream" is checked on every corpus
   file. Streams of storages the reader does not type are returned unchanged.
   - Rejected: typed fields plus an `extra` mapping, re-encoded on demand. Doubles, key order, CR
     separators, duplicate keys and unknown tails would each need a rule, and a wrong rule loses
     data silently.
   - Cost: memory is about twice the file size. The largest corpus file is 10 MB.
4. **Lengths: a minimum, never a list.** A subrecord at or above its minimum is typed; fields past
   its end are `None`; bytes past the known fields are `tail`. The list of observed lengths lives in
   the census test, where a new length fails on purpose.
   - Rejected: a table of accepted lengths in the reader. Each Altium release would break reading.
   - Rejected: the test reader's minimums (track 36, arc 47). Altium-saved files meet them, but the
     field tables allow 33 and 45, and a shorter record still gives every core field.
5. **Lenient by default, strict on request.** A short record becomes a `RawPrimitive` with a
   warning. An unknown type byte or a cut subrecord ends that stream with an error and keeps the
   rest as `trailing`; other storages are still read. `strict=True` raises `PcbReadError` on the
   first error.
   - Rejected: always raising. c0044's `inspect` must show a damaged file.
   - Rejected: guessing the subrecord count of an unknown type. A wrong guess misreads everything
     after it.
6. **Text is ISO-8859-1, with `%UTF8%` keys preferred.** Every byte maps to a character, so the
   text is exact, and it is what KiCad's importer does (S-0148), which keeps the oracle comparable.
   - Rejected: Windows-1252. Five byte values have no character there.
   - Open: see question 3.
7. **Numbers stay in the file's units.** Lengths are integers of 1/10 000 mil; angles and region
   vertices are the stored doubles. `to_nm` and `to_nm_exact` convert. `to_nm` is
   `fenolite.core.units.u_to_nm`: half to even, the project rule of `docs/formats/units.md`
   (settled at integration, 2026-10-03; the first draft rounded half away from zero, which differs
   by 1 nm at `u ≡ 25 (mod 50)`). The "no floats" rule belongs to the neutral model, so c0043
   rounds, with the same function.
   - Rejected: a rounding rule of the reader's own. Two rules for one conversion would make the
     reader's oracle figures and the imported model disagree at ties.
   - Rejected: converting to nanometres while reading. One unit is 2.54 nm, so the conversion
     rounds, and the round trip of c0044 needs the stored value.
8. **Two stack views, not merged.** `layers` and `copper_chain` come from the numbered keys, which
   every file holds and KiCad reads. `stack` comes from the `V9_STACK_LAYER` list when present, with
   long ids and the real dielectric order. c0043 chooses.
   - Rejected: one merged stack. The two lists disagree on dielectric names and order in saved
     files (c0038's research), and the rule for merging is an import decision.
9. **Rules are opaque.** Only the kind number, `RULEKIND`, name, enabled, priority, comment, id and
   the two scope texts are typed. Kind-specific keys stay in `fields`, which holds every pair of
   the record, the typed keys included: c0043 passes `fields` to c0042's `map_rules` unchanged.
   - Rejected: typing Clearance, Width and Routing Via Style. c0042 owns the mapping of rule kinds.
10. **Component bodies are framed only.** Type 12 is always a `RawPrimitive`, and the body storages
    of a document stay in `storages` as bytes. Hand-over (settled at integration, 2026-10-03):
    c0043 owns `read/bodies.py`, which decodes those bytes; this change types no body field and
    c0043 parses no other record.
11. **Evidence per field.** `FIELD_LEVELS` maps each typed field to the label of its fact row, and a
    test keeps both equal. A field is typed only with two agreeing sources, or one source plus a
    corpus or oracle check.
    - Rejected: one level for the reader. The lowest row would make everything `INFERRED`.
    - **S-0173 is never the only source of a row.** Its format page (scratch copy at the pinned
      commit) attributes two facts to the vendor's software: an enumeration of mask states and a
      layer vocabulary. Those two are not used at all (`LEGAL.md` P1), and the page's other tables
      are used only where S-0160, S-0150 version 1 or the corpus agree.
12. **Authored long-form fixtures.** Unit tests need long records without the corpus.
    `tests/_altium_long.py` builds them: Fenolite's short record, extended to each observed length
    with a counting byte pattern, plus authored fills, regions, wide strings, rules and classes.
    Nothing is copied from a corpus file, so the residue test stays clean.
    - Rejected: committing excerpts of public files. Only CC0 or authored files may be committed.
13. **The oracle compares what KiCad imports, and counts the rest.** KiCad drops or transforms some
    records (keep-outs, tracks of hatched pours, tracks on unmapped layers). Each exclusion is a
    fact row with its count per file. An item KiCad has and the reader lacks always fails.
    - Rejected: comparing counts only. It would not check a single offset.
14. **Corpus rows are reused, not duplicated.** c0039 owns the row ids and already lists six of the
    eleven files. Task 1.3 adds the use `altium-pcbdoc` or `altium-pcblib` to those six and adds
    five rows with the next free numbers. Tests select rows by use.
15. **No CLI and no capability entry.** c0044 adds `inspect`, `check` and `diff`. This change is a
    library API with tests.

## Interface used from c0039

c0039 owns the container API (settled at integration, 2026-10-03; this section first stated a
needed interface with other names). The reader uses only this:

| name of c0039 | use here |
|---|---|
| `read.cfb.is_compound(data) -> bool` | a source that fails it raises `PcbReadError` ("only the binary form is read") |
| `read.cfb.open_compound(data, *, file="") -> CompoundFile` | bytes to a container; default limits, `strict=False` |
| `CompoundFile.streams()`, `.storages()` | the stream and storage paths, names as stored |
| `path in compound`, `CompoundFile.read(path) -> bytes` | lookup without case; one stream |
| `CompoundFile.notes` | copied to the front of the result's `issues` |
| `read.cfb.CompoundError` (a `FormatError`) | not caught by this reader |

`read/pcb.py` reaches the container through one private function, `_open(source)` (task 2.2), which
also accepts a `CompoundFile` that the caller already opened.

## Interface for c0043 (and c0044, c0045)

| name | gives |
|---|---|
| `read.pcb.read_pcbdoc(source, *, file="", strict=False) -> PcbDocument` | a document |
| `read.pcblib.read_pcblib(source, *, file="", strict=False) -> PcbLibrary` | a library |
| `read.pcb.detect_pcb(source) -> Literal["pcbdoc", "pcblib"] \| None` | the kind |
| `PcbDocument.board`, `.nets`, `.components`, `.classes`, `.rules`, `.polygons`, `.pads`, `.vias`, `.tracks`, `.arcs`, `.texts`, `.fills`, `.regions`, `.shape_regions` | tuples in stream order; an index is a position |
| `PcbDocument.net_name(i)`, `.primitives_of(component)`, `.regions_of(polygon)` | joins by index |
| `PcbDocument.wide_strings`, `.pad_unique_ids`, `.storages`, `.issues`, `.evidence`, `.rebuild(storage)` | the rest, and the identity |
| `PcbLibrary.board`, `.names`, `.footprints`, `.footprint(name)`, `.storages`, `.issues` | a library |
| `LibFootprint.name`, `.parameters`, `.description`, `.height`, `.primitives`, `.pads`, `.unique_ids`, `.rebuild()` | a footprint; coordinates relative to its origin, Y up |
| `BoardRecord.outline`, `.origin`, `.layers`, `.copper_chain`, `.stack`, `.plane_nets`, `.layer_pairs` | board and stack |
| `pcbprims.to_nm`, `to_nm_exact`, `field_level`, `LAYER_NAMES` (in `pcbstack`) | conversion and evidence |

Notes for c0043:
- Y points up and angles turn counter-clockwise; a document's coordinates are absolute, with the
  board origin in `BoardRecord.origin`.
- A component's primitives carry its index; the document holds no footprint definitions.
- Poured copper is `regions_of(polygon)`. Region vertices are doubles and need rounding.
- A pad's corner ratio, slot and per-layer shapes are in the sixth subrecord's fields; they are
  `None` when it is empty.
- Internal planes are layers 39 to 54 in `copper_chain`, with their net in `plane_nets`.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/read/pcbprops.py` (new) | `PropertyRecord(raw, fields, lead)` with `get`, `get_all`, `keys`; `parse_blocks(data, *, lead=0, where) -> tuple[tuple[PropertyRecord, ...], bytes, list[Issue]]`; `parse_text(text: bytes) -> tuple[tuple[str, str], ...]`; `parse_mil`, `parse_bool`, `parse_int`, `parse_angle` |
| `src/fenolite/backends/altium/read/pcbprims.py` (new) | `Prefix`; `TrackRecord`, `ArcRecord`, `ViaRecord`, `FillRecord`, `PadRecord`, `TextRecord`, `RegionRecord`, `RegionVertex`, `RawPrimitive`; `Primitive` (their union); `decode_primitives(data, *, where, shape_based=False, start=0) -> tuple[tuple[Primitive, ...], bytes, list[Issue]]`; `SUBRECORDS`, `MINIMUMS`; `FIELD_LEVELS`, `field_level(record, field) -> Level`; `to_nm`, `to_nm_exact`; `PcbReadError(FormatError)`; `PCB_READ_ISSUE_CODES` |
| `src/fenolite/backends/altium/read/pcbstack.py` (new) | `BoardRecord`; `NumberedLayer`, `StackLayer`, `OutlineVertex`; `LAYER_NAMES`; `long_layer_id(value) -> tuple[str, int]`; `read_board(record: PropertyRecord, *, where) -> tuple[BoardRecord, list[Issue]]` |
| `src/fenolite/backends/altium/read/pcb.py` (new) | `read_pcbdoc`, `detect_pcb`; `PcbDocument`; `NetRecord`, `ComponentRecord`, `ClassRecord`, `PolygonRecord`, `RuleRecord`; `TYPED_STORAGES`; `EVIDENCE` |
| `src/fenolite/backends/altium/read/pcblib.py` (new) | `read_pcblib`; `PcbLibrary`, `LibFootprint`; `EVIDENCE` |
| `tests/_altium_long.py` (new, test code) | `long_track(n)`, `long_arc(n)`, `long_via(n)`, `long_fill(n)`, `long_text(n)`, `long_pad(n5, n6)`, `region(outline, holes, *, shape_based)`, `document(**storages) -> bytes`, `library(...) -> bytes` |
| `tests/unit/backends/altium/read/test_pcbprops.py`, `test_pcbprims.py`, `test_pcbprims_pad.py`, `test_pcbprims_region.py`, `test_pcbstack.py`, `test_pcb_records.py`, `test_pcbdoc_read.py`, `test_pcblib_read.py`, `test_pcb_issues.py`, `test_pcb_imports.py`, `test_pcb_field_levels.py`, `test_pcb_own_files.py` (new) | unit tests |
| `tests/corpus/test_altium_pcb_rows.py`, `test_altium_pcb_census.py` (new) | corpus rows; census and identity |
| `tests/kicad/altium/test_pcbdoc_read_oracle.py`, `test_pcblib_read_oracle.py` (new) | the two oracles |
| `tests/unit/test_docs_altium_read.py` (new) | the documentation check |
| `tests/corpus/manifest.toml` (extended) | eleven rows |
| `docs/formats/altium/pcb-read.md`, `docs/evidence/altium-pcb-read.md` (new); `docs/altium.md`, `docs/hypotheses.md`, `docs/evidence/sources.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md`, `tests/unit/test_altium_rows.py` (extended) | facts, results, rows |

The package `read/` and its `__init__.py` come from c0039. The modules import the standard library,
`fenolite.core` (`errors`, `evidence`) and each other. `tests/unit/test_import_graph.py` needs no
`ALLOWED` change. `pyproject.toml` `dependencies` stays empty.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0285 | https://www.altium.com/documentation/altium-designer/pcb-obj-fillfill-ad (redirects to the page "Polygons & Copper Regions"; read 2026-10-03) | Altium documentation, all rights reserved (read for facts) | a fill is a rectangle on any layer that can be rotated and can be a keep-out; solid regions and polygon pours as objects |
| S-0286 | https://www.altium.com/documentation/altium-designer/pcb/defining-scoping-managing-design-rules (read 2026-10-03) | Altium documentation, all rights reserved (read for facts) | a rule has a kind, a name, a priority (1 the highest) and one or two scope queries such as `All`, `InNet('…')`, `InNetClass('…')` |
| S-0287 | https://www.altium.com/documentation/altium-designer/pcb/design-rule-types/high-speed (URL to verify by task 1.1, with the sibling pages of the rule-type reference) | Altium documentation, all rights reserved (read for facts) | the names of rule kinds, to label the kind numbers seen |

S-0288 to S-0292 stay free. The range of this change was moved from S-0221–S-0228 to S-0285–S-0292
at integration (2026-10-03): S-0220 to S-0226 are registered by the active change c0023. c0043
cites S-0286 for the rule page instead of registering the same URL again.

Existing ids (task 1.1 widens their "used for" cells with "c0041"):
- S-0002 (KiCad's developer page): storages, primitive types, units.
- S-0148 (KiCad's binary parser, GPL, facts only): the length word, ISO-8859-1 text, `%UTF8%` keys.
- S-0160, S-0161, S-0162, S-0163 (KiCad's importer, GPL, facts only, nothing transcribed): field
  order and length thresholds of pads, vias, tracks, arcs, fills, texts and regions; the two region
  forms; what the importer drops.
- S-0150 (AltiumSharp **version 1 only**, commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`): field
  order of library primitives. Version 2 is not a source.
- S-0152 (pyaltiumlib documentation, MIT, facts only): library primitives.
- S-0173 (GPL-3.0 format page, facts only, no source code): a second witness for field tables,
  under decision 11.
- S-0170, S-0171 (four libraries; MIT and GPL-2.0), S-0172, S-0174, S-0175, S-0176 (documents;
  Apache-2.0, BSD-2-Clause, MIT, Apache-2.0), S-0188 (c0037; LGPL-3.0; its PCB document), S-0199,
  S-0200 (c0038; MIT): the corpus.
- S-0020, S-0166 (`kicad-cli`, a subprocess): the oracles.

### Corpus rows (task 1.3)

| row id | source | saved | licence | size |
|---|---|---|---|---|
| `altium-third-party-pcbdoc-01` (c0039's row) | S-0188, the PCB document of its folder | 2017 | LGPL-3.0 | 10.1 MB |
| `altium-third-party-pcbdoc-02` (c0039's row) | S-0176 (LFS object) | 2023 | Apache-2.0 | 6.7 MB |
| `altium-third-party-pcbdoc-03` (c0039's row) | S-0172 | 2024 | Apache-2.0 | 2.8 MB |
| `altium-third-party-pcbdoc-04` (c0039's row) | S-0199 | 2021 | MIT | 2.5 MB |
| `altium-third-party-pcbdoc-05` | S-0174 (LFS object) | 2021 | BSD-2-Clause | 1.7 MB |
| `altium-third-party-pcbdoc-06` | S-0175 (LFS object) | 2025 | MIT | 1.4 MB |
| `altium-third-party-pcbdoc-07` | S-0200 | 2021 | MIT | 2.9 MB |
| `altium-third-party-pcblib-01` (c0039's row) | S-0170, first file | 2016 | MIT | 0.1 MB |
| `altium-third-party-pcblib-02` (c0039's row) | S-0170, second file | 2019 | MIT | 0.1 MB |
| `altium-third-party-pcblib-03` | S-0171, first file | 2022 | GPL-2.0 | 0.1 MB |
| `altium-third-party-pcblib-04` | S-0171, second file | 2022 | GPL-2.0 | 0.1 MB |

- c0039 owns the id scheme and lists the six rows marked above (uses `altium`, `cfb`,
  `origin:third-party`). Task 1.3 adds `altium-pcbdoc` or `altium-pcblib` to them and adds the five
  other rows with the next free numbers, without `cfb` (first draft: eleven new rows numbered from
  01, which collided with c0039's ids; renumbered at integration, 2026-10-03).
- Each row's `url` is the raw file at the pinned commit (the media URL for an LFS object); `ref` is
  the commit; `sha256` is the value in `docs/evidence/sources.md` (S-0188's document:
  `e8a87333123e36e6b0260258322bccedac466624ed7f68dfe574db11ca11e4c4`, recorded by c0037's research).
- Every row is `embeddable = false`. The GPL and LGPL rows are measurement material under the
  corpus policy ("Measurement versus embedding").
- No repository of the excluded GitHub user is used.

## Hypotheses registered by this change

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-RD-PCB-FRAME` | Every primitive stream of an Altium-saved PCB file is a sequence of the eight record types with fixed subrecord counts, and ends at a record end | `tests/corpus/test_altium_pcb_census.py` | 11 rows, no error issue, empty `trailing` |
| `H-A-RD-PCB-IDENTITY` | Joining the records' bytes gives each stream back | the same test | byte-equal for every typed storage of 11 rows |
| `H-A-RD-PCB-LENGTHS` | Subrecord lengths grow by appending: the fields of the shortest form keep their offsets in every length seen | the census and both oracles | only listed lengths; oracle agreement on every length class |
| `H-A-RD-PCB-KICAD-DOC` | The reader's nets, components, pads, vias, copper tracks and copper chain of a saved document equal what `kicad-cli pcb import` reads | `tests/kicad/altium/test_pcbdoc_read_oracle.py` | within 2 nm; exclusions documented and counted |
| `H-A-RD-PCB-KICAD-LIB` | The reader's footprints and pads of a saved library equal what `kicad-cli fp upgrade` converts | `tests/kicad/altium/test_pcblib_read_oracle.py` | within 2 nm on 4 rows |
| `H-A-RD-PCB-PAD` | The long pad subrecords (170 to 194, and 651) keep the short form's offsets; the corner percentage and alternate shape sit at the offsets of the 596-byte form | both oracles (shape, size, hole, corner ratio) | every pad of the corpus agrees |
| `H-A-RD-PCB-REGION` | A region is the prefix, a hole count at 14, a property text at 18, a vertex count, vertices of 16 bytes (37 in the shape-based storage, one more than the count) and holes of 16-byte vertices | the census | empty tail on every region; equal record counts in both storages |
| `H-A-RD-PCB-TEXT` | A text's shown string is the wide string at its index; designator texts carry their component's designator | the census | every designator text equals `SOURCEDESIGNATOR` |
| `H-A-RD-PCB-STACK` | Following `LAYER<i>NEXT` from layer 1 gives the copper layers in order, also in files of 2016 and 2017 | the document oracle | the chain length equals KiCad's copper layer count on every row |
| `H-A-RD-PCB-RULE` | A rule is a 16-bit kind number and one property block; a kind number maps to one `RULEKIND` text | the census | `Rules6` ends at a record end; one text per number over the corpus |
| `H-A-RD-PCB-POLYNAME` | A polygon's `NAME` is a list of decimal character codes | the census | every non-empty name decodes to printable text |
| `H-A-RD-PCB-CODEC` | Property text and 8-bit strings are ISO-8859-1 unless a `%UTF8%` key exists | the census | counts of non-ASCII bytes and of `%UTF8%` keys recorded per row; no decode failure |

- The existing row `H-A-UNIT` ("positions agree within 1.27 nm") is settled by the document oracle;
  task 8.1 records the largest difference found.
- All twelve start at `INFERRED`. The census rows become `CORPUS-VERIFIED`, the two `KICAD` rows,
  `-PAD` and `-STACK` `ORACLE-VERIFIED(kicad-cli)`, when their tests pass.
- No id collides with `docs/hypotheses.md` or an active change (checked 2026-10-03: no `H-A-RD-`
  row exists).

## Evidence level per behaviour (before merge)

| behaviour | level | basis |
|---|---|---|
| Framing, subrecord counts, stream identity | `CORPUS-VERIFIED` | census on 11 rows |
| Length tolerance | `CORPUS-VERIFIED` for the lengths seen; Fenolite's rule beyond them | census; unit tests |
| Positions, sizes, widths, holes, nets, component links | `ORACLE-VERIFIED(kicad-cli)` 10.0.x | document and library oracles |
| Copper chain | `ORACLE-VERIFIED(kicad-cli)` | document oracle |
| Pad shapes, corner percentages, slots | `ORACLE-VERIFIED(kicad-cli)` where KiCad imports them, else `INFERRED` | oracles |
| Region structure, wide strings, rule framing, polygon names | `CORPUS-VERIFIED` | census consistency checks |
| Mask expansions and modes, text fonts, class kinds, `V9` stack entries | `INFERRED` (two public sources) | fact rows |
| Rule keys, storages kept as bytes, tails | not interpreted | — |
| `PcbDocument.evidence`, `PcbLibrary.evidence` | `CORPUS-VERIFIED` after tasks 7.1 to 8.2, `INFERRED` before | lowest of the framing rows |

No Altium author report is needed: nothing is written.

## Size (design-days)

| group | tasks | dd |
|---|---|---|
| 1. sources, hypotheses, fact page, corpus rows | 1.1 0.25, 1.2 0.75, 1.3 0.25 | 1.25 |
| 2. property records and the container seam | 2.1 0.5, 2.2 0.25 | 0.75 |
| 3. primitives | 3.1 0.5, 3.2 0.5, 3.3 0.75, 3.4 0.5, 3.5 0.5, 3.6 0.25 | 3.0 |
| 4. board record and stack | 4.1 0.5, 4.2 0.5 | 1.0 |
| 5. property kinds | 5.1 0.5, 5.2 0.5 | 1.0 |
| 6. library, document, issues | 6.1 0.75, 6.2 0.75, 6.3 0.5, 6.4 0.25 | 2.25 |
| 7. corpus census | 7.1 0.75, 7.2 0.25 | 1.0 |
| 8. oracles | 8.1 1.0, 8.2 0.5 | 1.5 |
| 9. documentation | 9.1 0.5 | 0.5 |
| 10. closing | 10.1 0.25, 10.2 0.15, 10.3 0.1 | 0.5 |
| **total** | | **12.75** |

This is a size, not a calendar estimate. A refuted hypothesis costs about 0.25 (a fact row and an
offset). The document oracle is the largest unknown: its exclusion list is found while writing it.

## Dependencies and archive order

- **Needs c0039** (the container reader and the `read/` package), implemented first.
- **Needs c0035, c0037 and c0038 on the branch**: the fact pages, S-0188, S-0199, S-0200 and
  `pcb-copper.md` come from them; one unit test builds c0038's via record.
- **Independent of c0040 and c0042.** If c0040 lands a shared property-text parser with the same
  lossless guarantees, task 2.1 may reuse it; the spec's behaviour is unchanged.
- **Consumed by** c0043, c0044, c0045.
- **Archive order.** The capability `altium-pcb-reader` is new and every delta is ADDED, so the
  order with other changes is free. No requirement name collides: "PCB files read back" and "Copper
  records read back" belong to `altium-pcb-writer`.

## Risks / Trade-offs

- [KiCad's import drops or reshapes more than expected, so the oracle needs many exclusions] →
  exclusions are fact rows with counts; if tracks cannot be matched on a row, that row falls back to
  pads, vias, nets and the stack, and the evidence page says so.
- [`kicad-cli` fails on a corpus document] → the row is recorded with its exit code and keeps
  `CORPUS-VERIFIED` only.
- [A corpus URL or LFS object disappears] → the hash is pinned; the row is replaced by another
  public file of the same era in a follow-up, and the census count is updated.
- [Eleven files are few, and none is older than 2016] → the reader depends on minimums, not on the
  list; the census names its coverage; older files give issues, not wrong data.
- [A field typed from two public sources is still wrong] → `FIELD_LEVELS` marks it `INFERRED`, and
  `raw` keeps the bytes.
- [Private paths inside public files leak into logs] → issues carry no file values; the census
  prints counts; a test greps its own output.
- [Memory doubles] → accepted for files of this size; `raw` could become a slice later without an
  API change.
- [The test reader and the product reader drift] → "Own files read" compares them on every golden
  file.

## Migration Plan

- New modules only; no existing behaviour changes.
- Rollback: remove the five modules, their tests, the manifest rows and the two pages.

## Open Questions

1. Settled (integration, 2026-10-03): component bodies (type 12) are not typed here. c0043 owns
   "component bodies" in the model and the decoder `read/bodies.py`; this reader keeps the bytes.
2. Should `Dimensions6`, `DifferentialPairs6` and `Connections6` be typed? Default: no, kept as
   bytes; the corpus holds five differential pairs and four connections in all.
3. Is ISO-8859-1 right for files saved under another system code page? Default: yes, with the raw
   bytes kept; `H-A-RD-PCB-CODEC` records what the corpus shows.
4. Should the reader accept the ASCII PCB form? Default: no; it raises with a clear message.
5. Should the LGPL-3.0 and GPL-2.0 rows stay in the corpus? Default: yes, fetch-only, as the corpus
   policy allows; without them no file older than 2021 is covered.
6. Should a corpus row that `kicad-cli` cannot import fail the build? Default: no; it is recorded
   and excluded by id.
7. Settled (integration, 2026-10-03): no typed rule kinds here. c0043 passes `RuleRecord.fields` to
   c0042's `map_rules`, which owns the kind table.

## Implementation notes

Recorded while implementing (2026-10-05); each note says what changed against the text above and why.

1. **`H-A-RD-PCB-TEXT` refuted, `H-A-RD-PCB-TEXT-2` registered.** The census found that the document of
   2017 (`altium-third-party-pcbdoc-01`, a project with a repeated sheet) shows 84 of its 248 designator
   texts as the logical designator followed by a channel suffix (components whose `SOURCEDESIGNATOR` is
   shared by 12 or 13 components), and 2 more with another designator. The six other rows agree on every
   text. The register keeps the refuted row; the spec's census bullet now allows the counted exceptions
   and the census compares the counts per row with the evidence page.
2. **Empty wide strings.** The document of 2017 stores its four empty `WideStrings6` entries with the
   length 2 and no text bytes. The reader follows S-0148 (an entry of length 2 or less is empty and no
   bytes follow); a fact row records it. The test helper writes empty entries that way.
3. **Count check after a cut stream.** A storage whose parse stopped early (non-empty `trailing`) is not
   compared with its `Header` count, so that a cut stream gives one `truncated` error and no second
   issue (scenario "Lenient and strict").
4. **Shape-based regions.** `RegionRecord.outline` holds the counted vertices in both forms; the extra
   vertex the shape-based form stores is `RegionRecord.closing` (scenario "Region with a hole": four
   outline vertices, five stored).
5. **Tails.** `PadRecord.tail` is a pair (fifth subrecord after 114, sixth after 596); the other records
   have one `tail`. A text below 123 bytes has its tail after offset 40, a track below 35 bytes after 33
   and an arc below 47 bytes after 45.
6. **Record tuples.** The primitive tuples of `PcbDocument` keep a `RawPrimitive` of their own type in
   place, so that an index stays a position; a record of another type goes to `others` with the
   `wrong-type` warning. `PcbDocument.trailing(storage)` gives the bytes after the last whole record.
7. **Issue codes** are defined in `read.pcbprops` (which `read.pcbprims` imports) and re-exported by
   `read.pcbprims` as the design names them.
8. **The container seam.** `read.pcb._open` stays private; `read.pcb.open_container` names the same
   function for `read.pcblib`, because the strict type check refuses a private name across modules.
9. **`long_layer_id`** returns `("signal", 32)` for the bottom layer `0x0100FFFF`: the number of the
   bottom copper layer, not the low 16 bits.
10. **The stem `H-A-RD-PCB-*`** is a row of the reserved-families table of `docs/hypotheses.md`.
11. **`tests/corpus/test_altium_pcb_rows.py`** reads the manifest only and is not marked `needs_corpus`,
    so that it runs without the corpus.
12. **Document oracle: KiCad's conversion.** KiCad's importer rounds every converted length to 10 nm
    (S-0163), so its positions differ from `to_nm` by up to 5 nm. The oracle converts the reader's values
    the same way before the 2 nm comparison (spec delta amended); the difference left is 0 nm on all seven
    rows, which settles `H-A-UNIT`.
13. **Document oracle: references.** KiCad names a footprint after the shown designator text, so the
    references are compared with it (spec delta amended); they differ from `SOURCEDESIGNATOR` only on the
    row of note 1.
14. **Document oracle: what KiCad changes.** Pads on paste layers are not imported; component copper
    regions and net-less component copper fills become unnumbered pads; free pads become footprints of
    their own; non-plated holes lose their pad number. Each is a fact row of "What KiCad does not import"
    with its count per row on the evidence page. The oracle also compares the top-layer size of every
    component pad and the shape and corner ratio of the simple ones (`H-A-RD-PCB-PAD`).
15. **CI fetch.** The `kicad-10` job fetches the corpus by use and requires it (`FENOLITE_REQUIRE=corpus`);
    the five new rows carry no `cfb` use, so the job's fetch also passes `--uses altium-pcbdoc --uses
    altium-pcblib`, and `tests/unit/test_ci_workflow.py` checks it. No task named this; without it the
    census and the oracles would fail in that job.
16. **Field labels after the oracles.** The fields the oracles compare (prefix layer, net and component;
    track ends and width; via position, diameter and hole; pad name, position, top size, round hole,
    plating, top shape, alternate shape and corner percentage; the designator flag, wide index and shown
    text) carry `ORACLE-VERIFIED(kicad-cli)`; the region structure fields `CORPUS-VERIFIED`; every other
    field stays `INFERRED`: the census checks its framing, not its meaning.

**Added at landing (coordinator, 2026-10-05): the CI fetch, shared with c0040 and c0042.** The three reader changes each add corpus uses that the `kicad-10` job must fetch by name. They are now one list, `ALTIUM_READER_USES` in `tests/unit/test_ci_workflow.py` (`altium-pcbdoc`, `altium-pcblib`, `altium-sch`, `altium-schlib`, `altium-text`), checked one by one; the single check this change wrote for its two uses is replaced by that list.
