## Context

Fenolite writes Altium schematics (ASCII and binary, c0032, c0033, c0036, c0037) and schematic
libraries (c0034). Altium Designer 26.5 opens and compiles them. Nothing in the product reads an
Altium file. v0.3 reads the second backend; this change is the schematic half of the readers.

What exists:

- **Fact pages.** `docs/formats/altium/schematic-ascii.md`, `schematic-binary.md` and
  `schematic-library.md` hold the record syntax, the framing, the binary pin table and the library
  container, each row with a source and a label. c0037 adds the hierarchy and harness rows.
- **Test readers.** `tests/_altium_read.py` and `tests/_cfb_read.py` check Fenolite's own output.
  They are strict by design: 7-bit text, upper-case keys, exact `WEIGHT`, no `Additional`, exactly
  five pin strings, no side stream.
- **What Altium-saved files show** (research note of c0037, files of S-0187 and S-0188 read in a
  scratch folder):
  - recent files use mixed-case keys (`Location.X`, `OwnerIndex`), older ones upper-case;
  - values hold bytes above 0x7F;
  - every sheet has an `Additional` stream, with its own header and its own index space;
  - an owner index of 0 is left out;
  - the header record carries a unique id, and saved records carry keys Fenolite never writes
    (`INDEXINSHEET`, …).
- **No specification.** Altium publishes none. Facts come from the documentation of an open-source
  converter (S-0130, S-0147), from KiCad's importer read for facts (S-0131, S-0148, S-0153), from
  AltiumSharp version 1 at `afe7964` only (S-0150), from two documentation sites of open-source
  readers (S-0151, S-0152) and from Altium's user documentation.
- **Oracle.** `kicad-cli sym upgrade` converts a `.SchLib` (S-0153), so libraries have a second
  reading. `kicad-cli` reads no `.SchDoc` (S-0132), so schematics have none.

The container reader is change c0039, which owns the container API and the corpus row ids
(settled at integration, 2026-10-03). This change uses `read.cfb.open_compound`, `CompoundFile` and
the corpus rule "Second-backend corpus rows" as c0039 specifies them: `open_compound` takes no
`issues` argument, so `_container.open_container` copies `CompoundFile.notes` into `issues`.
`.Harness` definition files are listed by c0042 and read by no v0.3 change.

## Goals / Non-Goals

**Goals**

- Read every `.SchDoc`, `.SchDot` and `.SchLib` that Altium saved, without losing a byte.
- Give c0043, c0044 and c0046 typed, named records and an owner tree.
- Be exact about lengths: no float, and an explicit flag when nanometres round.
- Be lenient where saved files need it, and say what was tolerated.
- Reach `CORPUS-VERIFIED` for the structure and `ORACLE-VERIFIED(kicad-cli)` for library pins.

**Non-Goals**

- Container parsing (c0039). Nets, the neutral model, a registered backend (c0043).
- CLI commands (c0044). The drawing-sheet model (c0046). PCB and project files (c0041, c0042).
- Writing Altium files from read records. `encode_stream` proves identity; it is not a writer.
- Rendering, image decoding, and resolving any path a record names.

## Decisions

1. **The container comes from `read.cfb` (c0039) through one private function.** This change
   calls `cfb.is_compound(data)` and `cfb.open_compound(data, file=file)`, and uses
   `CompoundFile.streams()`, `.storages()`, `.children(path)`, `.read(path)` and `.notes`. A
   `CompoundError` (a `FormatError`) is passed on unchanged, and the notes are added to `issues`.
   `read/sch/_container.py` is the only module that touches `read.cfb`, so a renamed member in
   c0039 changes one file.
   - Rejected: reuse `tests/_cfb_read.py`. It is a test helper, refuses DIFAT sectors, and the product
     must not import tests.
   - Rejected: a second container reader here. Two readers would drift.
2. **Layout: a package `read/sch/` and a module `read/schlib.py`.** The naming contract fixes
   `read.sch` and `read.schlib`. The schematic side needs several modules (property lists, framing,
   units, records, pins, document), so `sch` is a package whose `__init__` exports the surface.
   `schlib` imports `sch`; `sch` never imports `schlib`.
   - Rejected: helpers named `read/props.py` and `read/framing.py`. c0041 is written in parallel and
     may pick the same names. Open Question 1 offers a later move.
3. **Bytes in, frozen records out, no file access.** The functions take `bytes` and a `file` label
   for messages. c0043's backend opens paths and follows sheet file names. This keeps the reader
   pure, easy to fuzz, and unable to touch the file system.
   - Rejected: `read_schematic(path)`. It mixes I/O with parsing and tempts a reader to resolve
     `MODELDATAFILE` and sheet names.
4. **Lossless by construction: every record keeps its payload, every list its fields.** A `Prop` is
   `(key as written, raw value bytes)`. Typed attributes are views computed from the property list.
   Nothing is stored twice, so a typed value can never disagree with the kept bytes, and
   `to_bytes()` is the identity for any input.
   - Rejected: typed dataclass fields plus an `ext` bag of unknown keys, as the KiCad slots do. It
     loses key order, letter case, spaces and number formats unless every field also stores its
     text, which is the same data twice.
   - Rejected: keep only the raw stream and re-parse on demand. Consumers want records.
5. **`encode_stream` rebuilds; it does not echo.** Identity proved by returning a stored copy proves
   nothing. The rebuild goes through `PropertyList.to_bytes`, `encode_pin` and `enframe`, so a
   parsing step that drops or merges anything fails the corpus test. c0044's "copy identity per
   stream" level calls it.
6. **Keys compare without letter case; the spelling is kept.** Saved files hold both styles
   (S-0187, S-0188), and two readers already fold case (S-0131, S-0150 version 1). Lookup folds to
   upper case. A repeated key keeps both fields; lookup takes the first and `duplicates` names it.
   - Rejected: a dict per record. It drops order and repeats.
7. **Text is decoded late, by three rules.** The `%UTF8%` twin first, then UTF-8 for an ASCII file
   that is valid UTF-8, then the code page. Default `cp1252`: the one code page a source names
   (S-0130, S-0150 version 1). The caller may pass another single-byte code page. A byte the
   decoding does not define becomes U+FFFD with a warning; the raw bytes stay.
   - Rejected: guess the code page from the bytes. A wrong guess is silent. A parameter is honest.
   - Rejected: Latin-1 for everything. It never fails and is wrong for 0x80 to 0x9F.
   - Rejected: raise on an undecodable byte. One bad label would make a whole design unreadable.
8. **A length is an integer count of 1/100 000 unit.** One unit is 10 mil, 254 000 nm. A `_FRAC`
   key adds 1/100 000 unit, which is 2.54 nm, so a fraction is not always a whole nanometre.
   `SchLength.value` is exact; `nm()` rounds half to even and `exact` says whether it rounded. The
   importer (c0043) decides what to do with an inexact length; the reader never hides it.
   - Rejected: nanometres only. It rounds at read time and breaks the identity for odd fractions.
   - Rejected: `Fraction` as the stored value. An integer of the smallest file unit is simpler and
     compares fast; `mils()` returns a `Fraction` for callers that want one.
   - The sign rule (`units × 100 000 + frac`, each with its own sign) is `H-A-RD-SCH-FRAC`.
9. **The reader keeps the file's frame.** Y upwards, origin at the sheet's lower left, children of a
   placed component in absolute sheet coordinates, library coordinates relative to the symbol.
   Flipping and scaling are the importer's work, so a record always shows what the file says.
10. **One typed class per documented record id, 43 in all; the table is closed.** The ids and names
    are those S-0130 lists, plus 46 to 48 and 215 to 218, which the fact pages already hold. Another
    id is an `UnknownRecord` with its full property list, and an info names it.
    - Rejected: type only what c0043 needs. c0044's `inspect` and `diff` then show half the file as
      unknown.
    - Rejected: classes generated from a data table. Explicit classes give pyright-checked names;
      the table test keeps them and the format page equal.
11. **Each class declares `MODELED`; the rest is `unknown_keys`.** This is the "lossless slot" of
    the scope table: a key Fenolite does not model is never dropped and is always visible. The
    census counts unknown keys per record id over the corpus, which tells later changes what to
    model next.
12. **Owner rules per index space.** `FileHeader`: `OWNERINDEX` names an earlier record; absent
    means sheet level. `Additional`: `OWNERINDEXADDITIONALLIST=T` means "index into `Additional`",
    and an omitted index is 0 (S-0187, S-0188). Library `Data`: every record belongs to the
    component unless it names an earlier record.
    - A bad index leaves the record at the root with a warning. KiCad's reader drops such a child
      (S-0131); a lossless reader cannot.
    - Rejected: treat a missing `OWNERINDEX` in `FileHeader` as index 0, the sheet. It would make
      every wire a child of the sheet and the sheet the single root. The two readings are equal for
      consumers, and "no owner" matches the fact row.
    - Rejected: infer owners from position in a schematic document. The files give indexes.
13. **Owners are refs, not object links.** `RecordRef(stream, index)` with `stream` in `main`,
    `additional`, `data`. Records are frozen and hashable, and a document is a flat tuple, so there
    is no cycle, no deep recursion, and `walk` uses an explicit stack.
14. **Parts and display modes are exposed, never resolved.** `children_of(component, part=, mode=)`
    filters; `shown_children` applies the component's own `CURRENTPARTID` and `DISPLAYMODE`. Whether
    a multi-part component becomes one model component is c0043's decision.
    - `part_count = PARTCOUNT − 1` is recorded for Fenolite's own files and for KiCad's importer
      (`H-A-SCHLIB-KICAD`); for Altium-saved files it is `H-A-RD-SCH-PARTS`.
15. **Binary pins: optional strings from the end, and a kept tail.** Fenolite writes five short
    strings; KiCad reads four and ignores the rest (S-0131); what Altium writes is measured on the
    corpus (`H-A-RD-SCH-PIN`). The reader accepts two to five strings and keeps any bytes after the
    last known field in `tail`.
    - Rejected: require five, as the test reader does. That is a check of Fenolite's writer, not a
      reader of other files.
16. **Side streams are kept always and decoded only from a documented layout.** The fact page knows
    their names and purpose, not their bytes. Task 1.3 reads S-0131, S-0148 and S-0152 for the
    layout and records it. A stream without a recorded layout, or that does not match it to the last
    byte, stays opaque with an info, and changes no pin. `SIDE_STREAMS_DECODED` may be empty at
    merge; Open Question 3.
    - Rejected: decode from the format researcher's memory or from AltiumSharp version 2. Neither is
      a permitted source.
17. **Embedded files are never decompressed while reading.** A `Storage` record is kept as bytes.
    `EmbeddedFile.data(limit)` decompresses on request with a cap of 64 MiB, so a small file cannot
    expand without bound.
18. **Fatal errors are few.** Not a schematic, no `FileHeader`, a wrong header text, a cut frame, a
    broken container. Everything else is an issue from a closed table, and the reading continues.
    A reader that refuses a file over a wrong `WEIGHT` would be useless on real files.
    - Rejected: a `strict=True` mode. c0044's `check` is the place that turns findings into exit 5.
19. **The ASCII form has no public Altium-saved file; it stays `INFERRED`.** A search found none
    under a usable licence. The ASCII reader is tested on Fenolite's own output (CR LF and LF
    variants), on authored files with a byte-order mark, a continuation and a second header, and on
    corpus binary records rewritten one per line under `tmp_path`, which is the documented relation
    between the forms (S-0130). Open Question 2 asks for an author-saved file.
    - Rejected: label the ASCII form `CORPUS-VERIFIED` from rewritten records. Fenolite wrote those
      lines; they show nothing about what Altium writes.
20. **Corpus rows follow c0039's rule and add two tags.** Ids are
    `altium-third-party-schdoc-NN` and `altium-third-party-schlib-NN`, with the uses `altium` and
    `origin:third-party`. This change adds `altium-sch` and `altium-schlib`, so its tests fetch
    only what they read. c0039's four schematic rows are reused and gain the tag. An evidence rule
    counts repositories and needs three, as c0039 states.
    - Rejected: a separate id family. Two families for one file would list it twice.
    - If another change takes an id named here first, this change takes the next free number.
21. **The census prints key names and counts only.** Key names and record ids are the format's
    vocabulary. Net names, part names, texts and coordinates are a third party's design and never
    leave the cache. A test compares the census output with the files' texts.
22. **The product reader and the test reader stay separate.** The test reader is evidence for the
    writers. The new agreement test reads Fenolite's samples with both and compares; neither
    imports the other. A misreading shared by the fact pages is caught by the corpus and the oracle.
23. **No CLI, no registry entry, no `capabilities` change.** c0043 registers `AltiumBackend`; c0044
    adds `inspect`. Proofs of this change are `pytest` runs and `python -c` lines.

## Files and public API

| File | Change | Public API |
|---|---|---|
| `src/fenolite/backends/altium/read/sch/__init__.py` | new | the names of "Reader interfaces for later changes"; `EVIDENCE` |
| `src/fenolite/backends/altium/read/sch/_container.py` | new | private: `open_container(data, *, file, issues) -> cfb.CompoundFile` |
| `src/fenolite/backends/altium/read/sch/framing.py` | new | `Frame`, `deframe(stream, *, where, file="")`, `enframe(frames)`, `split_lines(data)`, `join_lines(lines)` |
| `src/fenolite/backends/altium/read/sch/props.py` | new | `Prop`, `PropertyList`, `parse(payload, *, codepage, utf8=False)`, `DEFAULT_CODEPAGE` |
| `src/fenolite/backends/altium/read/sch/units.py` | new | `SchLength`, `Color`, `UNIT_NM`, `FRAC_PER_UNIT`, `parse_udeg(text)` |
| `src/fenolite/backends/altium/read/sch/records.py` | new | `RecordRef`, `SchRecord`, `PropertyRecord`, `UnknownRecord`, the 43 classes, `RECORD_TYPES`, `Font` |
| `src/fenolite/backends/altium/read/sch/pins.py` | new | `decode_pin(payload, …) -> Pin \| None`, `encode_pin(pin) -> bytes` |
| `src/fenolite/backends/altium/read/sch/document.py` | new | `SchDocument`, `Harness`, `EmbeddedFile`, `read_schematic`, `detect`, `encode_stream`, `check_identity`, `MAX_EMBEDDED` |
| `src/fenolite/backends/altium/read/sch/issues.py` | new | `ISSUE_CODES` |
| `src/fenolite/backends/altium/read/schlib.py` | new | `SchLibrary`, `SchLibComponent`, `read_schlib`, `encode_stream`, `SIDE_STREAMS_DECODED` |
| `tools/altium_census.py` | new | `--uses TAG [--json]` |
| `tests/_altium_sch_build.py` | new | test-only builder of authored streams and files (frames, lines, pins, a compound file through `backends.altium.cfb.write_compound`) |
| `tests/unit/backends/altium/read/test_sch_framing.py`, `test_sch_props.py`, `test_sch_text.py`, `test_sch_units.py`, `test_sch_records.py`, `test_sch_records_table.py`, `test_sch_document.py`, `test_sch_ascii.py`, `test_sch_owner.py`, `test_sch_additional.py`, `test_sch_storage.py`, `test_sch_parts.py`, `test_sch_pins.py`, `test_schlib.py`, `test_schlib_side.py`, `test_sch_identity.py`, `test_sch_issues.py`, `test_sch_fuzz.py`, `test_sch_bounds.py`, `test_sch_own_output.py`, `test_sch_imports.py`, `test_sch_surface.py` | new | tests |
| `tests/corpus/test_altium_sch_read.py` | new | corpus checks, census vocabulary, ASCII from corpus records |
| `tests/kicad/altium/test_schlib_read_oracle.py` | new | library oracle |
| `tests/corpus/manifest.toml`, `tests/corpus/test_manifest.py` | rows, rules | — |
| `tests/unit/test_altium_rows.py` | extended | the fifteen `H-A-RD-SCH-*` ids (c0039 already admits the `H-A-RD-` family in `test_format_facts.py`) |
| `docs/formats/altium/schematic-records.md` | new | record tables |
| `docs/formats/altium/schematic-ascii.md`, `schematic-binary.md`, `schematic-library.md` | rows | — |
| `docs/evidence/altium-read-schematic.md` | new | census and oracle results |
| `docs/evidence/sources.md`, `docs/hypotheses.md`, `src/fenolite/backends/altium/PROVENANCE.md`, `LEGAL-ANNEX.md`, `docs/altium.md` | rows, sections | — |

`backends.altium.read` is inside `backends.altium`, so its imports follow the row `backends.<x>` of
`package-layering`: `model`, `geometry`, `backends.base` and `core`. This change imports only `core`.
No entry of `tests/unit/test_import_graph.py` changes.

Main signatures:

```python
def read_schematic(data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE,
                   issues: list[Issue] | None = None) -> SchDocument: ...
def read_schlib(data: bytes, *, file: str = "", codepage: str = DEFAULT_CODEPAGE,
                issues: list[Issue] | None = None) -> SchLibrary: ...
def detect(data: bytes) -> str | None: ...          # "ascii", "binary", "library"
def check_identity(result: SchDocument | SchLibrary) -> tuple[str, ...]: ...
```

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0277 | https://github.com/LanguidSmartass/altium-libs at commit `5e7cf90145aa20ec79ac2e0d510ccd8ff1f19a19`: six `.SchLib` files under `libs/00_Connectors/` (the repository of S-0170, which registered two `.PcbLib` files) | MIT (`LICENSE`); files saved by Altium Designer, fetched by the corpus tool, never committed | schematic libraries as Altium saves them: header, storages, binary pins, pin strings, side streams, parts |
| S-0278 | https://github.com/luxonis/oak-hardware at commit `7d569e3ccdff30014a498dc6c64a2e0dcad6964c`: the two schematic libraries under `BG0249_DepthAI_RGB_Camera/PCB/` and `BG0250TG_DepthAI_Mono_Camera/PCB/` (the repository and commit of S-0187) | MIT (`LICENSE`); fetched, never committed | a second origin of saved libraries |
| S-0279 | https://github.com/HangX-Ma/miniFOC at commit `324ac59357440746b89ee1882f213ea987bb4438`: `Hardware/miniFOC_driver/foc.SchDoc` and `foc_schlib.SchLib`, Git LFS objects (the repository and commit of S-0176) | Apache-2.0 (`LICENSE`); fetched, never committed | a third origin: a saved schematic and its library from one design, so placed parts can be compared with library parts |
| S-0280 | https://docs.python.org/3/library/codecs.html#standard-encodings | PSF License Version 2 | the code pages the standard library names; `cp1252` leaves five bytes undefined |
| S-0281 | https://docs.python.org/3/library/zlib.html | PSF License Version 2 | `zlib.decompressobj` and its `max_length` argument, for the bounded decompression of embedded files |
| S-0282 | https://www.altium.com/documentation/altium-designer/components-libraries/creating-schematic-symbol | Altium documentation, all rights reserved (read for facts) | multi-part components; display modes: Normal and Alternate 1 to 255 |

S-0283 and S-0284 stay unused. The range of this change was moved from S-0213–S-0220 to
S-0277–S-0284 at integration (2026-10-03): S-0215 to S-0218 are registered by the active change
c0016, and S-0213 and S-0214 lie in the range of c0022.

Cited, already registered:

- S-0130, S-0147: record ids and names 1 to 226, keys, `_FRAC`, `%UTF8%`, the `Additional` and
  `Storage` streams, display modes.
- S-0131, S-0148, S-0153: what a second reader needs; binary pins; side-stream names; the library
  oracle. GPL, read for facts only; nothing transcribed or followed.
- S-0150: AltiumSharp version 1 at `afe796434b6d2110c745c90abe44a6ddf64f5bca` only.
- S-0151, S-0152: library header, section keys, side streams.
- S-0145: the container, through c0039.
- S-0187, S-0188: saved schematics with hierarchy and harnesses (registered by c0037). c0039 lists
  two sheets of each as corpus rows; this change lists the other eight.
- S-0176: the repository of S-0279; c0039 lists its PCB document.
- S-0142 is not used.

Task 1.1 widens the "used for" cells. The listings of the three repositories were read on
2026-10-03 through the public tree pages. No file was downloaded for this proposal.

## Hypotheses registered by this change

All rows: backend `altium`, level `INFERRED`, result `pending`.

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-RD-SCH-FRAME` | Every `FileHeader`, `Additional`, `Storage` and `Data` stream of a saved file is a plain sequence of frames, and each property list ends with one NUL | corpus test | 0 cut frames, 0 `malformed-record` over three repositories |
| `H-A-RD-SCH-IDENT` | Rebuilding each stream from the parsed records gives the bytes read | corpus test | `check_identity` is `()` for every row |
| `H-A-RD-SCH-HEADER` | Saved files carry one of the three known header texts, and `WEIGHT` is the number of records after the header (in a library, as `schematic-library.md` states) | census | counts of each text; `weight-mismatch` count recorded, 0 or explained |
| `H-A-RD-SCH-CASE` | Keys are the same after upper-casing in every saved file, and no record holds two keys equal after folding | census | 0 duplicates; every folded key of a typed record is in `MODELED` or counted as unknown |
| `H-A-RD-SCH-TEXT` | A non-ASCII value decodes in `cp1252`, and its `%UTF8%` twin, when present, gives the same text | census | counts of values with a twin, equal and different; 0 `text-undecodable`, or each explained |
| `H-A-RD-SCH-OWNER` | In `FileHeader` every `OWNERINDEX` names an earlier record, and a record without one is at the sheet level | corpus test | 0 `orphan-record`; every record reached once from the roots |
| `H-A-RD-SCH-ADDOWNER` | In `Additional`, records with `OWNERINDEXADDITIONALLIST=T` name a record of `Additional`, an omitted index is 0, and their owner is a harness connector | corpus test | every entry and type has a connector as owner |
| `H-A-RD-SCH-LIBOWNER` | In a library's `Data`, an `OWNERINDEX` that is present names an earlier record of the same stream, and the other records belong to the component | census | distribution of `OWNERINDEX` per record id; 0 indexes out of range |
| `H-A-RD-SCH-FRAC` | A length is `K × 100 000 + K_FRAC` in 1/100 000 unit, each integer with its own sign, and `K_FRAC` is between -99 999 and 99 999 | census | 0 fractions out of range; counts by sign pair recorded |
| `H-A-RD-SCH-PARTS` | `PARTCOUNT − 1` is the number of parts, every child's `OWNERPARTID` is -1, 0 or a part, and its display mode is below `DISPLAYMODECOUNT` | corpus test and oracle | 0 `part-out-of-range`; unit counts equal KiCad's |
| `H-A-RD-SCH-PIN` | Binary pins of saved libraries follow the field table; the number of trailing strings and any tail are as the census records | corpus test and oracle | 0 malformed pins; pins equal KiCad's for the compared fields |
| `H-A-RD-SCH-PINSIDE` | The side streams have the layout task 1.3 records from a permitted source | corpus test | every side stream of the corpus matches to its last byte, or the stream stays opaque |
| `H-A-RD-SCH-STORAGE` | `Storage` is a header record followed by one binary record per embedded file, with the layout task 1.3 records | census | counts of known and opaque records |
| `H-A-RD-SCH-ASCII` | Altium's ASCII form holds the binary payloads one per line, with a second header line before the `Additional` records | authored tests; an author-saved file if Open Question 2 is granted | stays `INFERRED` without a saved file |
| `H-A-RD-SCH-KICAD` | `kicad-cli sym upgrade` converts the corpus libraries, and its pins and unit counts equal Fenolite's reading | oracle test | every row outside `KNOWN` agrees |

Checked against `docs/hypotheses.md` on 2026-10-03: no id starts with `H-A-RD-`.

## Evidence level per behaviour (before merge)

| Behaviour | Level | Basis |
|---|---|---|
| Framing, property lists, identity | `CORPUS-VERIFIED` | corpus test, three repositories of schematics and three of libraries |
| Header texts, `WEIGHT`, key case | `CORPUS-VERIFIED` for what the census finds; a mismatch is recorded as a fact row | census |
| Owner tree, `FileHeader` and `Additional` | `CORPUS-VERIFIED` (structure) | corpus test |
| Owner rule in library `Data` | `CORPUS-VERIFIED` if the census agrees, else `INFERRED` | census |
| Typed keys of each record | the label of each fact row: `INFERRED`, or `ORACLE-VERIFIED(kicad-cli)` for library keys the oracle reads | fact pages |
| Lengths and fractions | `CORPUS-VERIFIED` for the range; `ORACLE-VERIFIED(kicad-cli)` for library pin positions | census, oracle |
| Binary pins, parts, display modes | `ORACLE-VERIFIED(kicad-cli)` for the compared fields; `INFERRED` for the others | oracle test |
| Side streams | opaque: Fenolite's own rule; decoded: `CORPUS-VERIFIED` layout, `INFERRED` meaning | corpus test |
| Text decoding | `CORPUS-VERIFIED` that values decode and twins agree; the default code page is a choice | census |
| ASCII form | `INFERRED` | authored tests; no saved file |
| Embedded files | `INFERRED` | authored tests, census |
| Own output read back | Fenolite's own check | agreement test with the test reader |
| `read.sch.EVIDENCE` | the lowest of the registered rows, so `INFERRED` while `H-A-RD-SCH-ASCII` is pending | — |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, provenance, fact rows, corpus rows | 1.0 |
| 2. framing, property lists, text, units | 1.0 |
| 3. typed records and the record page | 1.5 |
| 4. document: streams, ASCII form, owner tree, `Additional`, `Storage` | 1.5 |
| 5. library: container, binary pins, side streams, parts and modes | 1.5 |
| 6. identity, issues, bounds, fuzz | 0.75 |
| 7. own output, corpus test, census tool, oracle | 1.25 |
| 8. closing | 0.5 |
| **total** | **9.0** |

A size, not calendar time.

## Overlaps with other active changes

- **c0039 (compound reader).** This change imports `read.cfb` and nothing else of it. If c0039 names
  its function or its result differently, only `read/sch/_container.py` changes. c0039 archives
  first.
- **c0037 (hierarchy and harnesses, being implemented).** It registers S-0185 to S-0188 and adds the
  fact rows of records 15, 16, 18, 32, 33 and 215 to 218 and of the `Additional` stream. This change
  cites those rows and adds only the reading rules. If c0037 is not merged when task 1.2 runs, the
  task adds the rows it needs and c0037 rebases.
- **c0041, c0042 (written in parallel).** No shared file except the registers, `PROVENANCE.md`, the
  corpus manifest and `tests/corpus/test_manifest.py`, where each change adds its own rows.
- **c0043, c0044, c0046.** They consume "Reader interfaces for later changes". c0046 may add
  requirements to this capability for template keys; the `Template`, `Sheet` and `Image` classes and
  `template_children()` are here for it.
- **`corpus-policy`.** One ADDED requirement, "Altium schematic corpus rows", which refers to
  c0039's "Second-backend corpus rows" and adds a tag to four of its rows. No MODIFIED delta, so
  the only archive-order constraint is c0039 first.

## Risks / Trade-offs

- **Saved files may break a rule that every source states.** The census reports it, the fact row is
  corrected first, and the reader follows the files. The fatal set is small so this rarely stops a
  read.
- **The corpus is small.** Three repositories and a few versions of the tool. Mitigation: unknown items are kept, so an unseen key or record costs nothing; the census
  tool runs on any later row.
- **One reading of a library may agree with KiCad and still differ from Altium.** The oracle shows
  agreement between two clean-room readers, not truth. Rows keep `ORACLE-VERIFIED(kicad-cli)`, never
  an Altium label.
- **`cp1252` may be wrong for a file saved under another system code page.** The text is then wrong
  but the bytes are kept, and the caller can pass the code page.
- **Views computed from property lists cost time on each access.** Files hold thousands of records,
  not millions. `functools.cached_property` is not used on frozen slotted records; c0043 reads each
  attribute once.
- **LFS rows.** Two rows of S-0279 are LFS objects. The fetch tool takes any URL; the row uses the
  URL that serves the bytes. If that URL stops working, the rows are dropped; a third repository must then be found before a
  row is labelled `CORPUS-VERIFIED`.
- **A licence may change.** Rows pin a commit, and the licence is read at that commit.

## Migration Plan

- No migration: new modules, no change to a writer, a model type, a CLI command or `capabilities`.
- The test readers stay as they are.
- Rollback: remove `read/sch/`, `read/schlib.py`, the tool, the tests and the corpus rows.

## Open Questions

1. Should `framing.py` and `props.py` move up to `read/` so the PCB reader (c0041) shares them?
   Default: no; they stay under `read/sch/` until c0041's design asks for them, then a small
   refactor moves them with re-exports.
2. May the maintainer save Fenolite's sample from Altium Designer as "Advanced Schematic ascii" and
   commit that file as an authored fixture with an author report? Default: no, because the trial
   licence's terms on such reports are the maintainer's call; the ASCII form stays `INFERRED`.
3. If no permitted source gives the layout of a pin side stream, is an opaque stream acceptable for
   v0.3? Default: yes. Pins then keep their 10-mil positions and short texts, the info says so, and
   c0044's round trip still copies the stream.
4. Should the default code page follow the caller's locale? Default: no; a fixed `cp1252` keeps
   results equal on every machine.
5. Should records 215 to 218 found in `FileHeader` give a warning? Default: no; the reader accepts
   them anywhere.
6. Should `LGPL-3.0` rows (S-0188) be fetched in CI or only locally? Default: fetched like any other
   row. They are read for measurement and never copied, which the corpus policy allows.
7. Should a later change model the unknown keys the census finds most often? Default: c0043 names
   the keys it needs; this change models the keys of the fact pages only.

## Implementation notes

Recorded during the implementation (2026-10-05). Where the spec delta changed, it was amended in this folder.

1. **Zero-valued point keys are left out (corpus).** Saved libraries hold polylines and polygons with fewer
   `X<n>`/`Y<n>` keys than `LOCATIONCOUNT`: a coordinate of 0 has no key, so a point at (0, 0) has none. Reading
   only the keys that exist lost those points (11 `bad-value` warnings on three library rows). The reader now
   takes points 1 to `LOCATIONCOUNT` when the count is at most the record's length in bytes (a missing key
   reads 0) and warns only for a larger count or for items past the count. The "Huge count" scenario holds.
   Spec amended: "Lengths and fractions" and "Bounded reading of untrusted files".
2. **Section keys may hold `/` (corpus).** Two library rows list a `SECTIONKEY<i>` with `/` whose storage holds
   `_` in its place. The lookup tries both. Spec amended: "Schematic library container"; fact row added to
   `schematic-library.md`.
3. **`H-A-RD-SCH-TEXT` refuted.** Twins differ from the `cp1252` reading of their plain value in 514 of 734
   (schematics) and 188 of 193 (libraries) cases: the byte 0x8E for U+00A6 (S-0130 describes it) and plain
   values in another system code page (S-0279). The reader already takes the twin first; nothing in the code
   changed. Successor `H-A-RD-SCH-TEXT-2` registered; "Text decoding" amended with the sentence that the twin
   wins. A value without a twin in such a file is mis-decoded as `cp1252` (bytes kept); `check_codepage`
   accepts single-byte code pages only, as the spec states.
4. **`PropertyList.get(key)`** returns the text view (`str`, or `None` when the key is missing); `raw(key)`
   returns the bytes and `prop(key)` the field. The scenario "`get("OWNERPARTID")` is `-1`" is read as the
   text `"-1"`, with `int("OWNERPARTID") == -1`.
5. **Census without values.** The census gives the header text as its kind (`schematic-binary`,
   `schematic-ascii`, `library`) and replaces a library's storage names, which are component names, by
   `<component>`; its fixed labels are `census.LABELS`. `tests/corpus/test_altium_sch_read.py` checks that no
   census string is a value of a file unless it is also a key name or a class name.
6. **Records are filled in place while a stream is read.** Owners, children, `bad_keys` and `PinFrac`
   fractions are set on records that no caller has seen yet (`_build.settle`), because a copy per record made
   a stream of 100 000 records slow. Records are frozen for their users.
7. **`PinFrac` is decoded while reading.** Decision 17 forbids decompressing embedded files; a `PinFrac` entry is
   a side-stream record of 12 bytes, decompressed with a cap of 13 bytes (S-0281), and decoded only when every
   record matches the layout to its last byte.
8. **Locators count frames.** A binary record's locator is `<stream>/record <frame index>`, the header being
   record 0; so the third record of the "Property list without its NUL" scenario is `FileHeader/record 2`. An
   orphan's message names the record's index in its index space.
9. **Small API additions** that the spec does not forbid: `SchDocument.blank_lines`, `extra_sections`,
   `all_records()`, `stream_mismatches()`; `SchLibComponent.data`, `get(ref)`, `of_type(cls)`;
   `SchRecord.owner_index`, `trusted_count(key)`, `MODELED` as a class attribute; `read.sch.HYPOTHESES`;
   `read.schlib.check_library` and `decode_pin_frac`; a private `_build` module shared by both readers; a
   `census` module (`read.sch` never imports `read.schlib`: the library census takes a protocol).
10. **Unknown streams of a component** (`PinPackageLength`, found in 99 storages) get an
    `altium.sch.unknown-stream` info, as root streams do; the spec did not say.
11. **Oracle `KNOWN` lists behaviours, not rows.** kicad-cli 10.0.6 writes a space of a pin name as `_` (1 pin)
    and holds positions in steps of 100 nm (5 `PinFrac` pins). The comparison applies both to Fenolite's side
    and counts the pins they touch; no row is skipped. Both are oracle-observation rows of
    `schematic-library.md`.
12. **`H-A-RD-SCH-PARTS` stays `INFERRED`.** No corpus library holds a multi-part or multi-mode component, so
    the oracle compares unit counts of 1 only.
13. **Capabilities.** `fenolite capabilities --json` at the c0039 commit and after this change are equal except
    the `elapsed_ms` timing field.
14. **Order of tasks.** Task 1.4 (corpus rows) was done before 1.2 and 1.3, which it does not depend on; task
    8.1's proof ran after the edits of 8.2 and 8.3, so that it checks the final tree.
15. **Trailing pin bytes in a document.** A binary pin of a schematic document carries no owner index, so
    `altium.sch.pin-trailing-bytes` is given once per document there (once per component in a library).
16. **Task 8.1.** The one full `make check` of this change (2026-10-05, on a machine under heavy load from
    parallel suites) passed ruff, the format check, pyright and the residue scan, and ran 6 649 tests green with
    one failure outside this change: `tests/unit/geometry/test_polygon.py::test_clip_result_inside_both`, a
    hypothesis deadline (257 ms against 200 ms). That file passes alone (26 passed). The full suite was not run
    again, by the coordinator's load rule; item 15 was added afterwards and checked with the reader's tests,
    the corpus test and the oracle. Task 8.1 stays unticked until the coordinator's run at landing.

**Added at landing (coordinator, 2026-10-05).**

- **The CI fetch.** Eighteen of the twenty-two corpus rows carry `altium-sch` or `altium-schlib` and neither `rt0` nor `cfb`, so the `kicad-10` job, which runs `tests/corpus` with `FENOLITE_REQUIRE=kicad,corpus`, did not fetch them. The job's fetch step now also passes `--uses altium-sch --uses altium-schlib`, and `tests/unit/test_ci_workflow.py` checks both (`ALTIUM_READER_USES`). No task named this.
- **Task 8.1.** The implementing run of the full suite failed on one test outside this change, a hypothesis deadline in `tests/unit/geometry/test_polygon.py` under a load average near 95. The task is ticked on the full run made at landing, after the rebase onto c0042.
