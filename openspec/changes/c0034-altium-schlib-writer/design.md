## Context

- c0032 writes an ASCII schematic, and c0033 a binary one, with generic bodies and links (`SOURCELIBRARYNAME`, `LIBREFERENCE`) to schematic libraries that nobody writes. In Altium Designer, "Tools » Update From Libraries" then has nothing to read.
- The free Altium 365 Viewer refuses library files (maintainer report of 2026-10-02, `docs/evidence/altium-schematic.md`). Altium Designer is the only Altium check, under LEGAL.md block A.
- A `.SchLib` is an MS-CFB file. Its root holds `FileHeader`, `Storage`, optionally `SectionKeys`, and one storage per component holding a `Data` stream (S-0002, S-0131, S-0150, S-0152). c0033's `cfb.write_compound` writes root streams only.
- `SymbolDef` (`src/fenolite/model/library.py`) holds the pins (number, name, `PinType`, hot-end position, rotation, length, shape, unit, body style, hidden) and the units, but no body graphics. The writer draws pins exactly and synthesises a rectangle per part.
- `kicad-cli sym upgrade X.SchLib -o Y.kicad_sym` converts a library through KiCad's Altium importer, on 10.0 and on 9.0 (S-0153). The format researcher's scratch probe on kicad-cli 10.0.6 (2026-10-02) converted an authored library with the expected pins, units, Part Zero, reference prefix and footprint name. Six malformed variants exited 2, and a storage without `Data` crashed the tool (exit 139). The probe is scratch: this change rewrites everything from the fact page.
- A parallel change, c0035 (PcbLib and PcbDoc), builds on `cfb.Storage` and puts the KiCad footprints in `<name>.PcbLib`. It leaves Altium footprint links as c0032 writes them.
- Source restriction, from the coordinator, 2026-10-02: the comments of AltiumSharp version 2 cite a non-public decompilation folder. Facts found only in version 2 are therefore not used (LEGAL.md P1). S-0150 is version 1, pinned to commit `afe796434b6d2110c745c90abe44a6ddf64f5bca` (2023-07-21, Apache-2.0 `LICENSE` at that commit; the repository has no tags). The researcher's facts that rested on version 2 were checked against version 1 (Decision 12).

## Goals / Non-Goals

**Goals**
- One library component per distinct symbol the design uses, in libraries that the schematic's links name, listed in the project file.
- Real pins from resolved KiCad symbols, and c0032's generic body for Altium links.
- A schematic that draws the same pins at the same places as its library.
- A reusable, public storage API in `cfb.py`, for c0035.
- An `ORACLE-VERIFIED(kicad-cli)` chain for every fact that KiCad's importer reads, and an author-report protocol for the rest.

**Non-Goals**
- PcbLib and PcbDoc (c0035), IntLib, DbLib, and reading Altium files.
- Symbol graphics (the model has none), alternate display modes, pin alternates, and the side streams `PinFrac`, `PinWideText`, `PinTextData` and `PinSymbolLineWidth`.
- Changing the footprint link: c0035 owns it.

## Decisions

1. **The symbol source follows the lib id's form.**
   - `<X>.SchLib:<name>` (suffix in any letter case) is an Altium link. It gets a generic symbol, which is c0032's body over the union of the designators used by every part of that lib id.
   - Any other lib id is a KiCad lib id, resolved with c0011's `LibraryResolver.symbol`.
   - This is deterministic for a given library configuration, and the sample still reads no library.
   - Rejected:
     - Resolve every lib id and fall back to generic on failure: the bytes would change silently with the machine.
     - A `--altium-symbols` option: one more switch, with no case that needs it.
2. **Library files.**
   - All KiCad symbols go into `<name>.SchLib`, as the brief asks and as c0035 does with `<name>.PcbLib`.
   - An Altium link `X.SchLib` gets the file it names, holding generic symbols. Its links then resolve, and the sample's schematic bytes stay those the Viewer report covers.
   - `SOURCELIBRARYNAME` changes only for KiCad lib ids, from `<nickname>` (which named no file) to `<name>.SchLib`. API: `project.schlib_name(lib_id, *, design)`.
   - Rejected:
     - One `<nickname>.SchLib` per KiCad library: it mirrors KiCad, but breaks symmetry with c0035 and gives several files for one design.
     - Moving Altium links to `<name>.SchLib` too: it changes the sample's Viewer-checked schematic and drops the library the user named.
     - Leaving Altium links without a library: the sample could not test "Update From Libraries", and the brief asks for generic symbols.
   - Risk: a generated generic `X.SchLib` stands in for a real one of the same name. It is reported with `altium.schlib-generic`, and the edited-output rule refuses to overwrite a foreign `X.SchLib` already in `--out`.
3. **Storage API (public, for c0035).**
   - `cfb.Storage(name: str, entries: tuple[cfb.Entry, ...])` is a frozen dataclass, with `cfb.Entry = tuple[str, bytes] | cfb.Storage`. `write_compound(entries: Sequence[cfb.Entry])` accepts any depth.
   - Directory ids are pre-order. Each storage builds its own sibling tree with c0033's `_tree`. Large streams take sectors in directory order.
   - Storage entries have start 0, size 0, a zero CLSID and zero times.
   - Root-only calls keep c0033's bytes, which a golden test guards.
   - A helper `cfb.storage_from_paths(mapping: Mapping[str, bytes]) -> tuple[cfb.Entry, ...]` builds the tree from `A/B/Data` paths in first-seen order, for writers that think in paths (c0035).
   - Rejected:
     - A path-only API: it hides the order of siblings.
     - A third-party CFB writer: no runtime dependencies are allowed.
4. **Records.** The header record holds `HEADER`, `WEIGHT`, one font, `COMPCOUNT`, `LIBREF<i>`, `COMPDESCR<i>` and `PARTCOUNT<i>`.
   - Nothing follows the record. S-0150's writer appends a binary name list, while its reader accepts either form, and KiCad reads only the record. The choice is recorded under `H-A-SCHLIB-OPEN`.
   - `WEIGHT` = the records in all `Data` streams + 1 (S-0150's rule).
   - `Data` holds the component, binary pins, one rectangle per part, the designator `<prefix>?`, the `Comment` parameter, and 44/45/46/48 when there is a footprint. It has no `OWNERINDEX`: KiCad ignores it, and the component is the only owner.
   - The component's `UNIQUEID` is `unique_id("schlib:<library>:<lib ref>")`.
   - Rejected: S-0150's `LIBRARYPATH`, `SOURCELIBRARYNAME` and `TARGETFILENAME` keys with placeholder values. No permitted source gives their values; KiCad does not read them.
5. **Binary pins.** The layout is the one that KiCad's reader (S-0131) and S-0150's writer agree on field for field, with all five short strings. KiCad 10.0.6 refuses a pin without the fourth string.
   - `FORMALTYPE` is written 1, as in c0032's text pins and S-0130. S-0150 writes 0. The difference is recorded in `H-A-SCHLIB-PIN`.
   - The pyAltiumLib table (S-0152) is rejected: it misaligns every later field.
6. **Mapping from `SymbolDef`.**
   - Rotation 0/90/180/270 gives direction 2/3/0/1.
   - The body end is the hot end minus the length in the direction.
   - The tables for electrical type and shape are the reverse of KiCad's importer mapping. Lossy entries give warnings, not refusals, because the writer is experimental and the oracle shows the result.
   - Off-grid pins (not a multiple of 10 mil) are refused: no `PinFrac`.
   - Body style 1 and common pins are kept. Other styles and pin alternates are dropped with an info.
   - Overbars `~{AB}` become `A\B\`.
   - Rejected:
     - Writing `PinFrac`: it adds an undocumented zlib side stream for a case that KiCad's libraries do not have.
     - Display modes: no Altium check is possible yet.
7. **Body rectangle per part.** It is the bounding box of the body ends of the part's pins and the Part Zero pins, at least 200 × 200 mil. A part without pins gets a 200-mil square.
   - Rejected: reading the KiCad symbol graphics. The model and the reader drop them, and adding them is a separate change of about 2 design-days.
8. **The schematic uses the library geometry.** Each component is placed with its symbol origin at `LOCATION`, with every pin and rectangle of the symbol.
   - The generic symbol's origin is c0032's body top-left corner. A design of Altium links therefore keeps c0033's bytes, which a golden test guards.
   - Multi-part symbols give one component record per part, `CURRENTPARTID=k`, each carrying every part's children. S-0131's importer skips children of other parts, which implies they are present (`H-A-SCHLIB-MULTIPART`).
   - Part Zero pins get stubs on part 1 only. Vertical stubs take labels with `ORIENTATION=1`.
   - The coordinate check moves from a 100-mil to a 10-mil grid, because KiCad pins sit on 50 mil.
   - Rejected:
     - Generic bodies with a library elsewhere: "Update From Libraries" would move pins off the stubs (c0032's `H-A-SCH-UPDATE` risk).
     - Generic bodies for multi-part symbols only: an inconsistent half-step.
9. **Section keys.** A lib ref of more than 31 characters is stored under `/`→`_`, cut to 31, and listed in `SectionKeys`. Other invalid names and clashes are refused. KiCad shows the key as the symbol name, so the oracle compares keyed symbols by key.
10. **Implementation index.** `MODELDATAFILE*` stays 0-based, as in c0032, in both files. S-0150 version 1 reads and writes it 1-based; S-0130 documents 0; KiCad reads 0. One answer for both files keeps them consistent. The maintainer's step L3 settles it (`H-A-SCHLIB-IMPLIDX`).
11. **The oracle runs in the KiCad jobs.** The round trip is `SymbolDef` → `write_schlib` → `kicad-cli sym upgrade` → `read_symbol_library` → compare.
    - The negative controls are built from the writer's own records.
    - The crash case is not run.
    - On kicad-cli 9, a failure is marked expected-to-fail on major 9, with its message recorded on the fact page. Rejected: gating the test to 10 without trying 9.
12. **Sources after the version 2 restriction.**
    - Kept, because S-0150 (version 1) or another permitted source confirms them:
      - pin layout including `DEFAULTVALUE`;
      - `SectionKeys` (`KEYCOUNT`, `LIBREF<i>`, `SECTIONKEY<i>`);
      - storage per component named by its section key;
      - `Data`;
      - side streams written only when needed;
      - `Storage`;
      - header keys `COMPCOUNT`, `LIBREF<i>`, `COMPDESCR<i>`, `PARTCOUNT<i>`;
      - component keys;
      - 1-based data-file index in S-0150.
    - Dropped, because only version 2 gave them:
      - "real headers carry no name list";
      - "Weight is a record count";
      - the claim of a byte-exact corpus round trip;
      - "Altium writes 44 … 48 at the end";
      - the claim that the library writer writes no `OWNERINDEX` (version 1 sets an owner index).
    - c0032's S-0142 is an unpinned AltiumSharp entry. Task 1.3 checks the facts c0032 took from it against version 1 and reports any that only version 2 gives. Changing c0032's rows is outside this change.

## Files and public API

| file | change | public API |
|---|---|---|
| `src/fenolite/backends/altium/cfb.py` | extended | `Storage`, `Entry`, `write_compound(entries)`, `storage_from_paths(mapping)` |
| `src/fenolite/backends/altium/altsym.py` | new | `AltiumPin`, `AltiumSymbol` (parts, pins, rectangles, prefix, comment, description, footprint), `from_symbol_def(symbol, *, lib_ref, footprint, issues)`, `from_generic(body, *, lib_ref, prefix, comment, footprint)`, `ELECTRICAL`, `EDGE_CODES` |
| `src/fenolite/backends/altium/schlib.py` | new | `HEADER_TEXT`, `EVIDENCE`, `pin_record(pin)`, `data_stream(symbol, *, library)`, `write_schlib(symbols, *, library)` |
| `src/fenolite/backends/altium/project.py` | extended | `schlib_name(lib_id, *, design)`, `storage_name(lib_ref)`, `write_project(..., symbols=None)`, `WRITE_KINDS` + `altium_schlib` |
| `src/fenolite/backends/altium/prjpcb.py` | extended | `write_prjpcb(*, schematic, libraries=())` |
| `layout.py`, `schdoc.py`, `symbols.py`, `ascii.py` | extended | `PartSpec.body: AltiumSymbol`, four-direction stubs, 10-mil `coord_fields` |
| `src/fenolite/lens/altium.py` | extended | `symbol_source(lib_id)`, `kicad_lib_ids(design)`, `build_altium(..., resolver=None)`, new issue codes |
| `src/fenolite/cli/cmd_build.py` | extended | resolver for KiCad lib ids; kind `altium_schlib`; `result.libraries`, `result.symbols` |
| `tests/_cfb_read.py`, `tests/_altium_read.py` | extended | storage checks; `read_schlib`; vertical stubs and parts in the net readback |
| `tests/unit/backends/altium/test_cfb_storage.py`, `test_schlib.py`, `test_altsym.py` | new | |
| `tests/kicad/altium/test_schlib_oracle.py` | new | oracle round trip and negative controls |
| `tests/unit/lens/test_altium_schlib_golden.py` | new | goldens and the Part L protocol check |
| `examples/altium_kicad/` | new | `design.py`, `FenoliteDemo.kicad_sym`, `sym-lib-table` (CC0) |
| `tests/data/altium/sample/FenoliteSample.SchLib`, `tests/data/altium/kicad_example/*` | new | goldens |
| `docs/formats/altium/schematic-library.md` | new | fact page |
| `compound-file.md`, `docs/altium.md`, `docs/evidence/altium-schematic.md`, `PROVENANCE.md` | extended | |

Layering: `altsym.py` imports `fenolite.model.library` only. The resolver stays in `lens.altium`, and `backends.altium` never imports `backends.kicad`.

## Sources registered by this change

| id | URL | licence | used for |
|---|---|---|---|
| S-0150 | https://github.com/issus/AltiumSharp/tree/afe796434b6d2110c745c90abe44a6ddf64f5bca (AltiumSharp **version 1 only**, 2023-07-21: `AltiumSharp/SchLibWriter.cs`, `SchWriter.cs`, `SchLibReader.cs`, `Records/Sch/SchLibHeader.cs`, `SchComponent.cs`, `SchPrimitive.cs`, `SchImplementation.cs`) | Apache-2.0 (`LICENSE` at that commit); facts only | header keys and `WEIGHT` rule, either header form read, `SectionKeys`, storage per component, `Data`, pin field order with `DEFAULTVALUE`, optional side streams, `Storage`, component keys, 1-based data-file index. Version 2 is not used (LEGAL.md P1). |
| S-0151 | https://github.com/pluots/PyAltium/blob/main/src/pyaltium/sch/_lib.py | GPL-3.0 (facts only; nothing transcribed) | header keys `CompCount`, `LibRef<i>`, `CompDescr<i>`, `PartCount<i>` (parts + 1); `SectionKeys` overrides the storage name |
| S-0152 | https://pyaltiumlib.readthedocs.io/latest/fileformat/FileStructure.html and `BasicTypes.html`, `Primitives.html` | MIT (repository metadata) | storage names of at most 31 characters, `/` → `_`; the optional per-symbol streams; a binary-pin table, recorded as contradicted |
| S-0153 | https://gitlab.com/kicad/code/kicad/-/blob/master/eeschema/eeschema_jobs_handler.cpp, the same file on branch `9.0`, and https://gitlab.com/kicad/code/kicad/-/blob/master/eeschema/sch_io/sch_io_mgr.cpp | GPL-3.0-or-later (facts only) | `sym upgrade -o` converts any library that a plugin reads, on 10.0 and 9.0; the plugin is guessed from the path; `sym export svg` reads KiCad libraries only |
| S-0154 | https://www.altium.com/documentation/altium-designer/sch-dlg-schcomponentpinspropertiesformcomponent-pin-editor-ad?version=20 | Altium documentation, all rights reserved (facts only) | Part Zero: pins with part number 0 are common to all parts |
| S-0155 | https://www.altium.com/documentation/cstu/designator-0 | Altium documentation, all rights reserved (facts only) | default designators end in `?` (`U?`, `R?`); placed parts get suffix letters |

Cited and not re-registered:
- S-0002 (KiCad's Altium import page);
- S-0131 extended to the library functions of `sch_io_altium.cpp` and the record keys of `altium_parser_sch.cpp`;
- S-0148 extended to the short-string and binary-record readers;
- S-0130 (`FORMALTYPE=1`, 0-based data-file keys);
- S-0145 (MS-CFB storages).

Not used:
- AltiumSharp version 2 and its issue tracker;
- the adom.inc `altium-schlib` crate (no licence found);
- python-altium for libraries (it has no library section).

## Hypotheses registered by this change

| id | question | settled by | level until then |
|---|---|---|---|
| H-A-SCHLIB-OPEN | Altium opens the library: CFB with storages, header text and keys, no name list after the record, `WEIGHT` rule, `Storage`, `Data` without `OWNERINDEX` | L1 | INFERRED |
| H-A-SCHLIB-PIN | Altium shows binary pins as written (layout, `FORMALTYPE` 1, `DEFAULTVALUE`, edge codes, visibility bits) | L2 | INFERRED |
| H-A-SCHLIB-PARTS | `PARTCOUNT`, `OWNERPARTID` and Part Zero as written | L2 | INFERRED |
| H-A-SCHLIB-IMPLIDX | Altium reads the 0-based `MODELDATAFILE*` keys as the footprint's library | L3 | INFERRED |
| H-A-SCHLIB-PRJ | A `.SchLib` listed as `[DocumentN]` is a project library that "Update From Libraries" searches | L4, L5 | INFERRED |
| H-A-SCHLIB-SCHDOC | A schematic drawn from the library geometry, with vertical stubs, compiles into the model's nets | L4 | INFERRED |
| H-A-SCHLIB-MULTIPART | Part records with `CURRENTPARTID`, all children and per-part unique ids compile into one component | L4 | INFERRED |
| H-A-SCHLIB-UPDATE | "Update From Libraries" with full replacement finds every component and moves no pin | L5 | INFERRED |
| H-A-SCHLIB-SECTIONKEY | Altium finds a symbol stored under a section key | L1 with a keyed symbol | INFERRED |
| H-A-SCHLIB-KICAD | kicad-cli 10.0.6 converts the libraries with the source's pins and units | oracle test | ORACLE-VERIFIED(kicad-cli) once it passes |
| H-A-SCHLIB-KICAD9 | kicad-cli 9.0 converts them too | `kicad-9` job | UNKNOWN until run |

No collision: `docs/hypotheses.md` and the active changes have no `H-A-SCHLIB-` row. `H-A-WRITE-SCHLIB` is the roadmap row about the author's earlier writer, and is left unchanged.

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| storages, pre-order ids, trees, root-only bytes unchanged | mechanical: unit tests and the independent reader |
| header, `Data` records, binary pin bytes, section keys, refusals | mechanical, plus `INFERRED` facts |
| storages, header text, framing, component first, pin layout, units, orientation, electrical types, edge codes, Part Zero, prefix, footprint name | `ORACLE-VERIFIED(kicad-cli)`, from the 10.0.6 round trip |
| `COMPCOUNT`/`LIBREF<i>`, `WEIGHT`, `Storage`, `SectionKeys` in Altium, `UNIQUEID`, `DEFAULTVALUE`, 44/46/48, project listing, "Update From Libraries", multi-part schematic | `INFERRED` until Part L: `ALTIUM-VERIFIED(author-report; AD <x.y>; <date>; no artefact)` |
| schematic bytes of Altium-link designs unchanged | golden equality with c0033's files |
| `build --target altium` envelope | `INFERRED`, experimental |

## Size (design-days; a size, not time; about 40 per calendar day at measured agent pace)

| piece | dd |
|---|---|
| registers, sources, version-1 check, fact page | 0.5 |
| CFB storages, reader checks | 0.5 |
| `schlib.py`: header, `Storage`, `SectionKeys`, `Data` records, binary pin | 1.0 |
| `altsym.py`: generic and `SymbolDef` mapping, rectangles, refusals | 1.0 |
| lens and CLI: sources, resolver, pins and members, libraries, project, issue codes, capabilities | 0.75 |
| KiCad example, oracle round trip, negative controls, KiCad 9 | 0.75 |
| schematic from the library geometry: four directions, parts, readback | 1.0 |
| goldens, Part L, docs | 0.5 |
| closing | 0.25 |
| **total** | **6.25** |

The minimal scope is 4.0 dd. It drops the schematic from the library geometry (1.0 dd; tasks group 4) and trims the example, determinism and docs work (1.25 dd): the schematic keeps c0032's generic bodies for KiCad lib ids, with an info saying that "Update From Libraries" moves pins.

## Risks / Trade-offs

- **Altium-only keys** (no name list after the record, `WEIGHT`, no `OWNERINDEX`, `FORMALTYPE` 1) may make Altium refuse or repair the file. Mitigation: Part L1/L6 asks only for key names, and every choice is one constant to flip.
- **Multi-part schematic form** is inferred. If L4 refutes it, the fallback is the minimal scope for multi-part symbols only.
- **A generated `X.SchLib` stands in for a real one** of the same name. Mitigation: the `altium.schlib-generic` info, the documentation, and the edited-output refusal of a foreign file.
- **A kept project file** does not list new libraries: `altium.schlib-not-in-project` names them.
- **Symbol-name clashes** across KiCad libraries are refused, not renamed (open question).
- **kicad-cli 9** may differ: the oracle records the observation instead of failing CI.
- **Sources:** facts rest on GPL code (facts only), Apache-2.0 version 1 code, and Altium pages. None is transcribed.

## Migration Plan

- Archive order: **c0032 → c0033 → c0034** (then c0035).
- MODIFIED deltas copy the ADDED text of the earlier change:
  - from c0032 `altium-schematic-writer`: "Altium writer package", "ASCII schematic form", "Generic component bodies", "Designator, comment and links", "Connectivity on the sheet", "Deterministic sheet layout", "Project file";
  - from c0032 `altium-build`: "Altium build target", "Altium build outputs";
  - from c0033 `altium-build`: "Altium schematic format option".
    Its scenario "Too large refused" changes: c0033 had the ASCII build succeed with the size limit forced to 0, but this change writes libraries, which are always compound files, so that ASCII build now fails with `altium.library-too-large` (and still never gives `altium.schematic-too-large`). The rule text says so as well.
- `openspec validate --strict` accepts this now. `openspec archive` succeeds only after the earlier changes are archived.
- c0035 MODIFIES "Designator, comment and links" and "Project file" too, so its full text must start from this change's version.
- The sample's two committed project files are rebuilt; the schematics are unchanged. Part A's SHA-256 values for the project files are updated, and the 2026-10-02 Viewer report stays valid, because it covers the binary schematic, whose bytes do not change.
- No model, schema, layering, FEN-code or runtime-dependency change.

## Open Questions

1. **0- or 1-based `MODELDATAFILE*`?** Default: 0-based in both files, until L3.
2. **One `<name>.SchLib` for KiCad symbols, or one file per KiCad library?** Default: one file, matching c0035 and the brief.
3. **Generic stand-in libraries for Altium links: always, or behind an option?** Default: always, with an info. Question for the maintainer: does the real library usually sit beside the project?
4. **Symbol-name clash across KiCad libraries** (`Device:R`, `Other:R`): refuse or rename (`Other_R`)? Default: refuse.
5. **Lossy pin types:** warning (default) or refusal without `--allow-lossy`?
6. **If kicad-cli 9 cannot read the libraries:** default: expected-to-fail on major 9, with the message recorded.
7. **Multi-part unique ids:** one per part (default), or the same id on every part? L4 decides.
8. **c0032's S-0142 facts** (task 1.3): if one rests on AltiumSharp version 2 only, should the coordinator open a follow-up change? Default: report it, and change nothing here.
9. **Licence for Part L:** the maintainer may only hold a work licence. Results from an employer's licence are not recorded (P4), so Part L may stay pending. Default: the rows stay `INFERRED`, with `pending (author report)`.
