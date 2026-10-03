## Context

- **c0032 and c0033** (on main) write `<name>.PrjPcb` and `<name>.SchDoc` (binary by default) from a DSL design. Names this change builds on: `backends.altium.project` (`write_project`, `unique_id`, `split_link`, `component_path`, `WRITE_KINDS`, `EVIDENCE`), `prjpcb.write_prjpcb`, `binary.frame_record`, `ascii.text_problem`, `cfb.write_compound`, `CompoundTooLarge`, `lens.altium` (`build_altium`, `ALTIUM_ISSUE_CODES`, `ALTIUM_BUILD_EVIDENCE`, `EXPERIMENTAL`), `cmd_build --target altium`, `tests/_cfb_read.py`, `tests/_altium_read.py`.
- **c0034** (proposed in commit `e473fc6`, archived before this change) resolves KiCad lib ids with c0011's `LibraryResolver` when `lens.altium.kicad_lib_ids(model)` is not empty, writes every KiCad symbol into one `<name>.SchLib` (`project.schlib_name`), adds `cfb.Storage`, `cfb.Entry` and `cfb.storage_from_paths`, `project.storage_name`, the `libraries` argument of `write_prjpcb` and the info `altium.schlib-not-in-project`, and registers AltiumSharp version 1 as S-0150. It leaves footprint links to this change. Its "Library and storage names" already says that c0035 puts all KiCad footprints in `<design>.PcbLib`, and its footprint link keeps c0032's `MODELDATAFILE0=<library>`. Its versions of "Altium build target", "Altium build outputs", "Altium symbol sources", "Designator, comment and links" and "Project file" are the base of this change's MODIFIED texts ("Spec deltas and archive order").
- **Format facts** (format research of 2026-10-02, public sources only; recorded in `docs/formats/altium/pcb-*.md` by task 1.2):
  - A PcbLib is a compound file: `FileHeader`; `Library/{Header, Data, Models/{Header, Data}}`; `SectionKeys` only for footprints whose storage name differs from their name; per footprint a storage with `Header`, `Parameters` (`PATTERN`, `HEIGHT`, `DESCRIPTION`), `WideStrings`, `Data` and `UniqueIdPrimitiveInformation/{Header, Data}` (S-0150, S-0162). KiCad finds a footprint only through `Parameters/PATTERN` and needs `Library/Data` (S-0162; local negative controls).
  - A footprint's `Data` is its name as a string block, then mixed primitive records. A PcbDoc has one storage per kind (`Pads6`, `Tracks6`, …) whose primitives carry absolute coordinates and a component index (S-0160, S-0161).
  - Lengths are int32 in 1/10 000 mil (2.54 nm); angles IEEE doubles in degrees, counter-clockwise; Y up (S-0002, S-0160, S-0163). Lengths in property text are decimal mils with the suffix `mil` (S-0163).
  - Records: a track is one subrecord of 36 bytes, an arc 47; a pad has six subrecords, the fifth at least 110 bytes (two writers agree on 114), the sixth empty or at least 596 bytes; a text 40 bytes or the long form (S-0150, S-0160, S-0143). A roundrect pad is shape round plus alternate shape 9 and a corner percentage in the sixth subrecord; KiCad reads the percentage as twice its corner ratio (S-0160, S-0161, S-0150).
  - Layer ids: 1 top, 32 bottom, 33/34 overlays, 35/36 paste, 37/38 solder, 57–72 Mechanical 1–16, 74 Multi-Layer; a through-hole pad must be on Multi-Layer (S-0002, S-0160, S-0161).
  - `Board6` holds one property record: origin, `LAYER<i>NAME`/`PREV`/`NEXT` (KiCad follows `NEXT` from layer 1 and needs ids up to 32 listed), outline vertices `VX<k>`/`VY<k>`/`KIND<k>` (S-0160, S-0161). `Nets6` and `Components6` are property records indexed by position; `Components6` holds `PATTERN`, `SOURCEDESIGNATOR`, `SOURCEUNIQUEID`, `SOURCEFOOTPRINTLIBRARY` (S-0160, S-0161, S-0143).
  - Altium links schematic and PCB components by the schematic component's unique id, stored on the PCB side as `\<id>`; designators are the fallback (S-0164, S-0139).
- **Oracles (local, kicad-cli 10.0.6, authored probes).** `kicad-cli fp upgrade X.PcbLib -o out.pretty` converts a PcbLib; exit 0 can still write no file (a footprint without `Parameters`), so tests count files. `kicad-cli pcb import --format altium` reads a PcbDoc; missing storages are reported only on stdout, not in the JSON report; empty `Data` streams silence them. KiCad 9.0's `fp upgrade` takes the same converter path; 9.0 has no `pcb import` (S-0166, read on the 9.0 branch on 2026-10-02).
- **Compound files.** c0033's `write_compound` refuses an empty stream. A PcbDoc needs empty `Data` streams, and KiCad reads them (probe). This change allows them (MODIFIED "Compound file container").
- **Model limits.** `Pad` has no corner ratio, slot or drill offset: the KiCad reader keeps `roundrect_rratio`, oval and offset drills as opaque children in `ext["kicad"]` (`backends/kicad/_fpmap.py`). Only `lens` may read them (layering).
- **Sample.** `examples/blink_2layer` uses the authored CC0 mini library: roundrect SMD pads, a rect and a round through-hole pad, lines, rectangles, arcs, a circle and a filled pin-1 polygon on silkscreen, fabrication and courtyard; a bottom-side part; a 50 × 30 mm board; all parts placed. c0032's sample links only to Altium libraries and gets no PCB file. c0034's example names footprints of a library it does not have.

## Goals / Non-Goals

**Goals:**
- `<name>.PcbLib` with every resolved footprint the design uses, round-tripped through `kicad-cli fp upgrade` with the same geometry.
- An experimental `<name>.PcbDoc` linked to the schematic by unique ids, read by `kicad-cli pcb import` with the same components, nets and pads.
- Refusal over approximation, with one closed issue table.
- The PcbLib and its round trip first; the PcbDoc after the PcbLib sample is handed over.

**Non-Goals:**
- Everything under Non-goals in the proposal.
- Any byte change for a design whose footprint links all name `.PcbLib` files.

## Decisions

1. **Footprint source by link form.** `lens.altium.footprint_source(link)` is `altium` when the link's library part ends with `.PcbLib` in any case (the user's library: no footprint, link unchanged), and `kicad` otherwise. The link is c0032's `footprint` or c0034's symbol `Footprint` property. A `kicad` link is resolved with `LibraryResolver.footprint`; a failure gives `altium.footprint-unresolved` (warning), and the footprint is not written.
   - Rejected: an error, as c0034 does for symbols. A footprint only feeds the PCB; the schematic and its libraries stay useful, and c0034's example keeps building.
2. **One `<name>.PcbLib`** (`project.pcblib_name(link, design=…)`, "PCB library name"), matching c0034's `<name>.SchLib` and the sentence of c0034's "Library and storage names" that promises it. Footprints keep `FootprintDef.name`. Two `kicad` links with one name from two libraries, or two names with one storage name, give `altium.footprint-name-collision` (warning): neither is written, so no part gets the wrong footprint.
   - Rejected: one `<nickname>.PcbLib` per KiCad footprint library, named by a shared `project.library_file_name`. An intermediate c0034 draft had that function; the committed c0034 (`e473fc6`) has `schlib_name` with one `<design>.SchLib` instead. Per-library files would break that symmetry, contradict c0034's text and need a fourth MODIFIED writer requirement. Open question 1 keeps it for the coordinator.
   - Rejected: renaming a colliding footprint (the `PATTERN` would differ from KiCad's name).
3. **The schematic links by form, not by outcome.** `MODELDATAFILE0` is `project.pcblib_name(link, design=…)`: unchanged for `altium` links, `<name>.PcbLib` for `kicad` links whether or not the footprint was written, as c0034's `schlib_name` does. Schematic bytes then never depend on a library's content. MODIFIED "Designator, comment and links".
4. **Storage names** come from c0034's `project.storage_name`; `SectionKeys` lists the keyed footprints (S-0145, S-0150).
5. **KiCad-only pad facts are read in `lens`.** `lens.altium.pad_extras(defn)` reads `roundrect_rratio` and the other opaque children of each pad and returns `pcblib.PadExtras(corner_ratio, refusal, dropped)`. The backend never imports `backends.kicad`.
6. **Refuse or drop.** `pcblib.check_footprint` refuses a footprint (`altium.footprint-unsupported`, warning; not written) for a pad it cannot write exactly or a copper graphic, and drops with `altium.primitive-dropped` (warning) polygons, filled shapes, graphics on unmapped layers and pad settings it has no field for. Texts, properties and 3D models give `altium.footprint-extras-dropped` (info); Altium adds designator and comment on placement.
   - Rejected: writing a trapezoid as a rect, or a slot as a round hole (wrong geometry).
7. **Layer map, one table.** `F.Cu` 1, `B.Cu` 32, `F.SilkS` 33, `B.SilkS` 34, `F.Fab` Mechanical 13, `B.Fab` Mechanical 14, `F.CrtYd` Mechanical 15, `B.CrtYd` Mechanical 16; through-hole pads 74. Altium has no fixed fabrication or courtyard layer, and KiCad imports Mechanical n as `User.n`, so no oracle checks this choice. Open question for the maintainer.
8. **Records.** Track 36 bytes; arc 47 (AltiumSharp version 1's 45-byte arc fails in KiCad); pad fifth subrecord 114 bytes with version 1's defaults; sixth empty unless roundrect (596 bytes, alternate shape 9, percentage `round(200·ratio)`). Rectangles become four tracks, circles a 0–360° arc. Arcs come from KiCad's start, mid and end: the centre exact, the direction from `orient2d` in the Y-up frame.
9. **Platform-independent doubles.** Angles are computed with `decimal` and converted once (`float(Decimal)` rounds correctly), never with `math.atan2`, so bytes do not depend on the C library.
   - Rejected: `math.atan2` (last-bit differences would break golden files between Linux CI and macOS).
10. **Rounding.** nm → unit is `round(nm · 50 / 127)`, half away from zero: at most 1.27 nm per value, documented as lossy by rounding; no `--allow-lossy` needed.
11. **PcbDoc frame.** Placement as KiCad places: absolute = `at + R(θ)·M·local` (`geometry.transform.Transform.placement`; `H-G-BOTTOM-PLACE`, `H-G-BOTTOM-STORE`). Then Y negated and shifted so the outline's lower-left corner is at (1000 mil, 1000 mil), with `ORIGINX`/`ORIGINY` there. Bottom layers swap through the pair table.
    - Rejected: negative coordinates (KiCad reads them; unknown for Altium).
12. **PcbDoc content.** `FileHeader` and `FileHeaderSix` (S-0143), `Board6` (stack of ids 1–74 linked `1 → 32 → 0`, outline), `Nets6` (sorted names), `Components6` (`SOURCEUNIQUEID=\<unique_id>`, `SOURCEDESIGNATOR`, `PATTERN`, `SOURCEFOOTPRINTLIBRARY=<name>.PcbLib`), `Pads6`, `Tracks6`, `Arcs6`, `Texts6` (designator, and comment hidden by `COMMENTON=FALSE`), `WideStrings6`; every other storage KiCad looks for, empty.
13. **When the PcbDoc is written.** When the design has an outline without cutouts and every component with a footprint link has its footprint in the PcbLib. Otherwise `altium.pcbdoc-not-written` (info) names the reason. Parts without any footprint link are left off the board, as Altium's change order would.
14. **Placements.** DSL placements; an unplaced part is staged right of the outline as the KiCad build does (`lens.build.STAGING_OFFSET`, `STAGING_GAP`), with `altium.pcb-staged` (info). With a PcbDoc, the board and placements are no longer `altium.not-lowered`. `build_altium` gains `placements=` beside c0032's `placed=`.
15. **Project file.** `write_prjpcb(*, schematic, pcb=None, libraries=())`: the PcbDoc is `[Document2]` when written; the PcbLib joins c0034's libraries. A kept project gives `altium.pcb-not-in-project` (info). MODIFIED "Project file".
16. **Experimental entry of its own.** `capabilities` lists `altium-pcb-writer` beside `altium-schematic-writer`, with write kinds `altium_pcbdoc` and `altium_pcblib` (`lens.altium.PCB_WRITE_KINDS`) and `lens.altium.PCB_BUILD_EVIDENCE`. `ALTIUM_BUILD_EVIDENCE` also names the `H-A-PCB-*` rows, as c0034 did for its rows, so the build envelope covers the PCB files. `project.WRITE_KINDS` and c0033's and c0034's entry stay as they are. MODIFIED `cli-contract` "Experimental features in capabilities" (c0032), which allowed one entry.
    - Rejected: adding the kinds to `altium-schematic-writer` (two more MODIFIED texts, and the PCB writer could not be cut on its own).
17. **AltiumSharp version 1 only.** PCB facts come from S-0150 (commit `afe796434b6d2110c745c90abe44a6ddf64f5bca`, 2023-07-21, Apache-2.0). Version 2 (2026) cites a non-public `docs/decompile/` folder in its comments, so a fact found only there is dropped or re-sourced from KiCad or altiumts (`LEGAL.md` P1). Dropped: `FileVersionInfo`, `LayerKindMapping`, `PadViaLibrary`, `ComponentParamsTOC`, `Textures` and `ModelsNoEmbed` in a PcbLib, and version 2's longer PcbLib header. The PcbDoc `FileHeader` form appears in version 2 but is taken from altiumts (S-0143), an independent MIT writer.
18. **Cut order** (sizes in design-days, total 9.5):
    1. **The PcbDoc goes first** (group 4 and step P of task 6.1, −3.6). The PcbLib alone serves the change-order route that c0032 documents. Cutting it removes the requirements "PCB document file", "PCB document placement", "PCB document links and nets", "PCB document oracle" and "PCB document output", the codes `altium.pcbdoc-not-written` and `altium.pcb-staged`, the write kind `altium_pcbdoc` and `pcb=` of `write_prjpcb`; the rest stands. Cost: without a licence the maintainer may use, nothing Altium-made checks the PCB records, because the Viewer lists `.PcbDoc` and not `.PcbLib` (S-0149).
    2. If the PcbDoc stays: staging (−0.25 of task 4.4), refusing a board with unplaced parts through `altium.pcbdoc-not-written` instead.
    3. The `kicad-9` PcbLib run (−0; only its record in task 3.5).
    - Not optional: the PcbLib, its pad shapes, the layer map and the `fp upgrade` round trip (minimum 5.9).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/cfb.py` (extended) | empty streams |
| `src/fenolite/backends/altium/pcbrecords.py` (new) | `to_units(nm) -> int`; `mil_text(units) -> str`; `string_block(text) -> bytes`; `property_block(fields) -> bytes`; layer constants, `LAYER_MAP`, `FLIP_PAIRS`; `NO_INDEX = 0xFFFF`; `ArcGeometry`, `arc_from_points(start, mid, end)`; `track_record`, `arc_record`, `pad_record`, `text_record`; `EVIDENCE` |
| `src/fenolite/backends/altium/pcblib.py` (new) | `LIBRARY_HEADER_TEXT`; `PadExtras`; `LibFootprint(defn, extras)`; `FootprintCheck`; `check_footprint(defn, extras) -> FootprintCheck`; `write_pcblib(footprints) -> bytes`; `EVIDENCE` |
| `src/fenolite/backends/altium/pcbdoc.py` (new) | `FILE_HEADER_TEXT`, `FILE_HEADER_SIX_TEXT`, `EMPTY_STORAGES`, `BOARD_OFFSET_MIL = 1000`; `PlacedComponent`; `PcbDocSpec`; `write_pcbdoc(spec) -> bytes`; `EVIDENCE` |
| `src/fenolite/backends/altium/project.py`, `prjpcb.py` (extended) | `pcblib_name(link, *, design)`; `write_project(..., footprints=…, pcb=…)`; `write_prjpcb(*, schematic, pcb=None, libraries=())` |
| `src/fenolite/lens/altium.py` (extended) | `footprint_source`, `kicad_footprint_ids`, `pad_extras`; `build_altium(..., placements=None)`; nine codes; `PCB_WRITE_KINDS`; `PCB_BUILD_EVIDENCE`; summary `footprints`, `pcb_document` |
| `src/fenolite/cli/cmd_build.py`, `cmd_capabilities.py` (extended) | placements passed; resolver for footprint links; write kinds; result keys; second entry |
| `tests/_altium_pcb_read.py` (new, test code) | `read_pcblib`, `read_pcbdoc`, `decode_primitives`; written from the fact pages, never imports the writer |
| `tests/unit/backends/altium/test_altium_pcb_read.py` (new) | the decoder's negative controls |
| `tests/unit/backends/altium/test_pcbrecords.py`, `test_pcblib.py`, `test_pcbdoc.py`, `test_cfb.py`; `tests/unit/lens/test_altium_pcb.py`, `test_altium_pcb_golden.py`; `tests/unit/cli/test_capabilities_experimental.py` | records, refusals, names, links, determinism, golden files, entries |
| `tests/kicad/altium/test_pcblib_oracle.py`, `test_pcbdoc_oracle.py` (new) | the two oracles |
| `tests/data/altium/blink/` (new, authored) | the five files of the blink build, in `MANIFEST.toml`; c0034's `tests/data/altium/kicad_example/` schematic rebuilt |
| `docs/formats/altium/pcb-library.md`, `pcb-records.md`, `pcb-document.md`, `docs/evidence/altium-pcb.md` (new) | fact tables; protocol |
| `docs/altium.md`, `docs/cli-contract.md`, `docs/formats/altium/compound-file.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`, `PROVENANCE.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md` (extended) | |

Layering: the new modules import `core`, `model`, `geometry` and their siblings; `ALLOWED` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0160 | https://gitlab.com/kicad/code/kicad/-/blob/master/pcbnew/pcb_io/altium/altium_parser_pcb.cpp and `altium_parser_pcb.h` | GPL-2.0-or-later (facts only) | record lengths, offsets, enums and minimums |
| S-0161 | https://gitlab.com/kicad/code/kicad/-/blob/master/pcbnew/pcb_io/altium/altium_pcb.cpp | GPL-3.0-or-later (facts only) | stream requirements, pad semantics, indexes, stack walk, component path |
| S-0162 | https://gitlab.com/kicad/code/kicad/-/blob/master/pcbnew/pcb_io/altium/pcb_io_altium_designer.cpp and `altium_pcb_compound_file.cpp` | GPL (facts only) | PcbLib enumeration through `Parameters/PATTERN`, `Library/Data`, signature check |
| S-0163 | https://gitlab.com/kicad/code/kicad/-/blob/master/common/io/altium/altium_props_utils.cpp | GPL-2.0-or-later (facts only) | `mil` text units, 2.54 nm |
| S-0164 | https://altium.com/kr/documentation/altium-designer/workspacemanager-dlg-comfirmcompmatchesformedit-component-links-ad?version=24 and https://resources.altium.com/p/automating-your-eco-with-component-links | Altium, all rights reserved (read for facts) | component links by unique id, path form, designator fallback |
| S-0165 | https://www.altium.com/documentation/altium-designer/pcb-dlg-confirmfileformatformfile-format-pcb-ad | Altium, all rights reserved (read for facts) | "PCB Binary Version 6.0" is the recommended PCB format |
| S-0166 | https://gitlab.com/kicad/code/kicad/-/blob/master/pcbnew/pcbnew_jobs_handler.cpp, the same file and `pcbnew/pcb_io/pcb_io_mgr.cpp` on branch `9.0`, and `kicad/cli/command_pcb_import.cpp` | GPL (facts only) | `fp upgrade -o` converts non-KiCad libraries on 9.0 and 10.0; `pcb import` exists from 10.0 |

Cited and widened, no new id:
- **S-0150** (c0034, AltiumSharp version 1 at the pinned commit): `AltiumSharp/PcbLibWriter.cs`, `CompoundFileWriter.cs`, `Records/Pcb/*.cs`.
- **S-0142**: marked "unpinned; Fenolite uses AltiumSharp only through S-0150 (version 1); version 2 is not a source (`LEGAL.md` P1)".
- **S-0143**: altiumts at commit `1fad5fa2b7b9f4e83b06072d5b965f153aae1c48` (PcbDoc writer, `FileHeaderSix`, empty storages) and circuit-json-to-altium's Viewer report.
- **S-0002** (PCB section), **S-0145** (storages, empty streams), **S-0149** (the Viewer lists `.PcbDoc`, not `.PcbLib`), **S-0020** (local runs).

S-0167 … S-0169 stay unused. KiCad sources are read for facts only and recorded in Fenolite's words (`LEGAL.md` A2, P2).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-PCB-KICAD-LIB | KiCad converts the PcbLib with the source geometry (S-0160, S-0162, S-0166) | `test_pcblib_oracle.py` on 10.0.6 and 9.0.9 | one file per footprint; pads and graphics within 10 nm |
| H-A-PCB-KICAD-DOC | KiCad imports the PcbDoc with its components, nets and pads (S-0160, S-0161) | `test_pcbdoc_oracle.py` on 10.0.6 | exit 0; no error in report or stdout; equal references, pad nets and relative positions |
| H-A-PCB-LIB-OPEN | Altium Designer opens a PcbLib holding only the streams AltiumSharp version 1 writes | kit request (D1) | footprints listed, no repair prompt |
| H-A-PCB-LIB-NAME | Altium shows a footprint stored under a section key with its full name | kit request (D1) | the long name is shown |
| H-A-PCB-PAD | Pads with version 1's defaults, roundrect by alternate shape and holes on Multi-Layer show as written | kit request (D1, P1) | shapes, sizes and holes as in the protocol table |
| H-A-PCB-GRAPHICS | 36-byte tracks and 47-byte arcs on overlay and mechanical layers render | kit request (D1, P1) | outlines visible on the mapped layers |
| H-A-PCB-ECO | With the PcbLib in the project, the change order into a blank PcbDoc places every footprint | kit request (D2) | no footprint not found |
| H-A-PCB-PRJ | Altium shows the PcbLib and the PcbDoc that the project file lists | kit request (D1) | both listed in the project |
| H-A-PCB-DOC-VIEWER | The Altium 365 Viewer renders the sample PcbDoc | kit request (P1, P2) | outline, three components, pads, designators |
| H-A-PCB-DOC-OPEN | Altium Designer opens the PcbDoc: headers, empty storages and streams, two-layer stack, offset frame | kit request (D3) | no repair prompt |
| H-A-PCB-DOC-LINK | "Update PCB Document" adds and removes no component (`SOURCEUNIQUEID=\<id>`) | kit request (D3) | no add or remove |
| H-A-PCB-DOC-NETS | The same change order changes no net | kit request (D3) | no net change |
| H-A-PCB-DOC-BOTTOM | A bottom component's `ROTATION` and mirrored pads match the design | `test_pcbdoc_oracle.py`; kit request (P1, D3) | `D1` matches its KiCad build |

Every row starts `INFERRED`; the two `KICAD` rows reach `ORACLE-VERIFIED(kicad-cli)` when their test passes on 10.0.6. No other active change uses the stem `H-A-PCB-` (`H-A-WRITE-PCBLIB` is c0014's roadmap row for the author's earlier writer).

## Evidence level per behaviour (before merge)

| behaviour | level | proof |
|---|---|---|
| Units, records, layer map, storage names, refusals, empty streams | mechanical; facts `INFERRED` | `test_pcbrecords.py`, `test_pcblib.py`, `test_cfb.py` |
| PcbLib read by KiCad with the same geometry | `ORACLE-VERIFIED(kicad-cli)` on 10.0.6; 9.0.9 recorded | `test_pcblib_oracle.py` |
| PcbDoc read by KiCad | `ORACLE-VERIFIED(kicad-cli)` on 10.0.6 | `test_pcbdoc_oracle.py` |
| Links, issues, determinism, golden files, CLI, capabilities | mechanical | `test_altium_pcb*.py`, `test_altium_build.py`, `test_capabilities_experimental.py` |
| Altium opens, renders and links | `INFERRED`; author reports per row | `docs/evidence/altium-pcb.md` |
| Build envelope | `INFERRED`, experimental | `ALTIUM_BUILD_EVIDENCE` |

## Size (design-days)

| group | tasks | dd |
|---|---|---|
| 1. restriction, sources, hypotheses, fact pages | 1.1 0.25, 1.2 0.25 | 0.5 |
| 2. empty streams, PCB records, test decoder | 2.1 0.25, 2.2 0.5, 2.3 0.25 | 1.0 |
| 3. PcbLib and its round trip | 3.1 pads 0.5, 3.2 checks and graphics 0.5, 3.3 library file 0.75, 3.4 lens, links and project 0.75, 3.5 oracle 0.5, 3.6 sample and Part D hand-off 0.25 | 3.25 |
| 4. PcbDoc (cut first) | 4.1 headers, `Board6`, nets 0.5, 4.2 components, texts, links 0.75, 4.3 placement 1.0, 4.4 build rules and staging 0.5, 4.5 oracle 0.5, 4.6 sample and Part P hand-off 0.25 | 3.5 |
| 5. capabilities, determinism, documentation | 5.1 0.25, 5.2 0.25 | 0.5 |
| 6. author reports | 6.1 Viewer 0.1, 6.2 Altium Designer 0.15 | 0.25 |
| 7. closing | 7.1 0.25, 7.2 0.15, 7.3 0.1 | 0.5 |
| **total** | | **9.5** |

The research estimated 9.5 (shared 1.5, PcbLib 3.5, PcbDoc 4.5). c0034's `cfb.Storage` saves 0.5 of the shared work and the PcbDoc has no routing (−1.0), but the author reports, the closing group and the c0034 example rebuild come back (+1.0). A size, not calendar time. Minimum after the cut order of Decision 18: 5.9.

## Risks / Trade-offs

- [Altium needs a stream version 1 does not write] → each such stream is a hypothesis row, and the fix adds bytes. No version 2-only fact is used.
- [The PcbLib cannot be checked in Altium without a licence the maintainer may use] → the PcbDoc carries the same records into the free Viewer (Part P). It is still first in the cut order: the PcbLib is the part the change-order route needs. Results from an employer's licence are never recorded (`LEGAL.md` P4).
- [KiCad accepts what Altium rejects (the 35- or 36-byte track)] → KiCad levels never promote an Altium row.
- [The user edits the PcbDoc in Altium] → the next build refuses it (`FEN-7001`); `--discard-layout` replaces it and keeps a backup.
- [Unresolved or colliding footprints] → warnings, and no PcbDoc.
- [c0034's example now gets `altium.footprint-unresolved` and a new `MODELDATAFILE0`] → task 3.4 rebuilds its golden schematic; its library and project file keep their bytes. c0034's statement that its footprint library is never opened stays true: `FenoliteDemo` names no footprint table entry.
- [c0034's checks read `result.experimental[0]` as the schematic entry] → with two entries sorted by name, index 0 is `altium-pcb-writer`; task 5.1 makes the tests select entries by name.
- [c0034's symbol checks refuse a Mini symbol] → the Mini pins lie on the 10-mil grid (checked 2026-10-02: 111 values, none off); if another c0034 refusal appears, task 3.6 reports it before the sample is committed.

## Spec deltas and archive order

**Archive order: c0032 → c0033 → c0034 → c0035.** None of the Altium capabilities is in `openspec/specs/` yet. Each MODIFIED text below is copied in full from the latest change in that chain that holds it, then edited; `openspec validate --strict` accepts this now, and `openspec archive` succeeds only in this order. If c0034 changes before it archives, task 1.1 copies its final texts again.

| capability | requirement | delta | base text |
|---|---|---|---|
| `altium-pcb-writer` (new) | PCB units and record framing; PCB layer map; Footprint pad records; Footprint line and arc records; Footprint content checks; PCB library name; PCB library file; PCB document file; PCB document placement; PCB document links and nets; PCB files read back; PCB library oracle; PCB document oracle | ADDED (13) | — |
| `altium-build` | Altium footprint sources; PCB library outputs; PCB document output; PCB issue codes; PCB evidence and capabilities; PCB samples; PCB author reports; PCB writers are documented | ADDED (8) | — |
| `altium-build` | Altium build target | MODIFIED | c0034's MODIFIED text (`placements=`, footprint resolver, result keys, write kinds) |
| `altium-build` | Altium build outputs | MODIFIED | c0034's MODIFIED text (PCB files planned; "MUST NOT write a PCB library, a PCB document" lifted) |
| `altium-build` | Altium symbol sources | MODIFIED | c0034's ADDED text ("Footprint libraries are never opened" narrowed) |
| `altium-schematic-writer` | Designator, comment and links | MODIFIED | c0034's MODIFIED text (`MODELDATAFILE0=project.pcblib_name(...)`) |
| `altium-schematic-writer` | Project file | MODIFIED | c0034's MODIFIED text (`pcb=`, `.PcbLib` among the libraries) |
| `altium-schematic-writer` | Compound file container | MODIFIED | c0033's ADDED text (empty streams allowed); c0034 does not modify it |
| `cli-contract` | Experimental features in capabilities | MODIFIED | c0032's ADDED text (two entries); c0033 and c0034 extend it without modifying it |

## Migration Plan

- Designs whose footprint links all name `.PcbLib` files keep every byte (c0032's sample). Designs with KiCad footprint links get `<name>.PcbLib`, maybe `<name>.PcbDoc`, and a new `MODELDATAFILE0`; the build is experimental.
- The archive order and the base of every MODIFIED text are in "Spec deltas and archive order".
- c0034's example schematic golden is rebuilt once; c0032's and c0033's sample files are unchanged.
- No model, schema, layering, FEN-code or runtime-dependency change.
- Rollback: remove the modules and the lens step.

## Open Questions

1. **One `<design>.PcbLib`, or one `<nickname>.PcbLib` per KiCad footprint library?** Default: one file, as committed c0034 says and does for symbols (Decision 2). Question for the coordinator: a per-library layout must change c0034 and c0035 together.
2. Mechanical layers for fabrication and courtyard. Default: 13/14 and 15/16. Question for the maintainer.
3. Mechanical layer pairs in `Board6`. Default: none (no public key).
4. A comment text per component. Default: written, hidden.
5. `SOURCEUNIQUEID` with or without the backslash. Default: with (S-0161, S-0164).
6. An empty stream's starting sector. Default: ENDOFCHAIN; task 1.2 records the MS-CFB section, or the row stays `INFERRED` under `H-A-PCB-DOC-OPEN`.
7. **Licence for Part D.** The maintainer may only hold a work licence. Results from an employer's licence are not recorded (P4). Default: Part D stays `pending (author report)`, and Part P (the free Viewer) is the only Altium check.
8. If `kicad-cli` 9.0.9 cannot convert the PcbLib. Default: expected-to-fail on major 9, with the message recorded on `H-A-PCB-KICAD-LIB`.

## Revision of 2026-10-03: the library in the form Altium saves

The maintainer opened the first `blink.PcbLib` in an Altium Designer trial: a "catastrophic" error, also for a library without footprints. `kicad-cli fp upgrade` read the same file. The requirement "PCB library file" and the scenarios of "PCB files read back" were edited in place (this change is not archived).

- **Cause.** The stream set of AltiumSharp version 1 is not what Altium needs. Four Altium-saved libraries under MIT and GPL-2.0 (S-0170, S-0171, read in a scratch folder, never committed) and the reports of a GPL writer whose libraries are opened in Altium (S-0173) show: a 53-byte `FileHeader` (text, the double 5.01, an eight-letter id); a `Library/Data` block that is a whole board record of about 2 000 keys with `KIND=Protel_Advanced_PCB_Library` and `VERSION=3.00`, never `HEADER`/`WEIGHT`; and the `Library` side streams `EmbeddedFonts`, `ModelsNoEmbed`, `Textures`, `ComponentParamsTOC` and `PadViaLibrary`. S-0173 reports the same "catastrophic failure whilst loading section Library" for a short block, and that a stack of about 90 keys is still refused.
- **Decision: generate the whole board record by rule (`libboard.py`), copy nothing.** The minimal key set Altium needs is unknown and each probe costs the maintainer a session, so the writer emits every key of the libraries' record, each from a rule stated on `pcb-library.md` (layer lists, long layer ids, the numbered layers in groups of five, the CR between the record's lines, layer sets, the 2D view keys). The alternative, a template block captured from a real library (what S-0173 does), would put a third-party file's bytes into the package (`LEGAL.md` B, ADR-0003); rejected. The generator's output was compared with the libraries in the scratch folder: the keys, their order and the line breaks are equal, and the values differ only where Fenolite chooses (file name, date, ids, enabled mechanical layers, grid, window).
- **Not changed.** Pad, track and arc records keep their short forms (114, 36 and 47 bytes; the Altium-saved libraries hold 170 to 185, 45 to 49 bytes): the lengths are explicit, older files hold short records, and the failure is at library level. `FileVersionInfo` (compatibility messages in Altium's words) and `LayerKindMapping` (only in the 2022 libraries) are not written. These stay under `H-A-PCB-LIB-OPEN` and `H-A-PCB-PAD` until the next report.
- **PCB document.** `FileHeaderSix` gets the GUID block of an Altium-saved document (S-0172), the same rule as the library's `FileHeader`. `Board6` keeps its short record of version 5.00: the saved document's record (about 2 300 keys, other stack keys than a library's) is recorded as a fact row, and whether the short one opens stays `H-A-PCB-DOC-OPEN`.
