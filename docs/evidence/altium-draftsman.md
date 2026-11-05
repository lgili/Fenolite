# Altium Draftsman documents: census and kit Part F

Evidence of change c0172 (native Altium Draftsman documents, `.PCBDwf`). The facts these measurements
support are rows of `docs/formats/altium/draftsman.md`; the hypotheses are the `H-A-DWF-*` rows of
`docs/hypotheses.md`. The public documents of S-0785 and S-0786 are fetched to the corpus cache by
`tools/corpus_fetch.py --uses altium-draftsman` and are never committed. Only counts, lengths, container
bytes and element names are recorded here, never a value of a document's content. No fact comes from
Altium's program code or from a third-party parser.

## Census

### Container (task 1.2, 2026-10-16)

Measured by `uv run python tools/draftsman_census.py` and pinned by
`FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py -k container`.

| row | source | bytes | first eight bytes | chunks (LZ4, stored) | last chunk decodes to | decoded bytes | XML elements | LZ4 sequences | largest offset |
|---|---|---|---|---|---|---|---|---|---|
| `altium-third-party-pcbdwf-01` | S-0785 | 4455680 | `01 80 80 40 8d 75 f2 5a` | 73 (73, 0) | 783065 | 76280537 | 2662429 | 925955 | 65535 |
| `altium-third-party-pcbdwf-02` | S-0785 | 4903885 | `01 80 80 40 f5 e0 02 f2` | 26 (24, 2) | 349325 | 26563725 | 1089079 | 361900 | 65535 |
| `altium-third-party-pcbdwf-03` | S-0786 | 458794 | `01 80 80 40 be a0 02 f2` | 6 (6, 0) | 719643 | 5962523 | 243822 | 98773 | 65531 |
| `altium-third-party-pcbdwf-04` | S-0786 | 328671 | `01 80 80 40 d6 92 05 f2` | 4 (4, 0) | 645697 | 3791425 | 172161 | 69663 | 65487 |

What the rows show:

- Every chunk but the last decodes to 1048576 bytes. An LZ4 chunk's header is 6 or 7 bytes (flag, the
  3-byte decoded length `80 80 40`, a stored length of 2 or 3 bytes); a stored chunk's is 4 bytes.
- The "four-byte field" of the first look (S-0785, S-0786) is not a field: in row 01 it is the stored length
  `8d 75` (14989) and the token `f2` with its first extra length byte `5a`; in rows 02 to 04 it is a
  three-byte stored length (45173, 36926, 84310) and the token `f2`. The token `f2` starts a literal run
  of 15 + 90 = 105 bytes, the length of `<Document xmlns="…V1"`; the first match follows.
- Literal runs are short: 1.2 %, 5.7 %, 1.6 % and 1.8 % of the decoded bytes are literals. The longest run
  is 3062, 337437 (a run of base64 text in an LZ4 block of row 02), 1850 and 1850 bytes.
- The compressed file is 5.84 %, 18.46 %, 7.69 % and 8.67 % of the decoded text.
- All four texts are well-formed XML of the Draftsman namespace (`xml.etree.ElementTree`, streamed), UTF-8,
  with no declaration.

### Candidates (task 1.2, 2026-10-16)

Each candidate of design Decision 1 was tried at the offsets 0 to 8 and at every chunk's payload start. A
decoder "decodes" when it returns at least 16 bytes of printable text; a framed format is "present" when its
leading bytes occur there.

| candidate | specification | how it was tried | result on the four rows |
|---|---|---|---|
| raw deflate | S-0806 | Python `zlib`, window −15 | decodes nothing |
| zlib | S-0805 | Python `zlib`, window 15; leading byte `78` | decodes nothing; not present |
| gzip | S-0807 | Python `zlib`, window 31; leading bytes `1F 8B` | decodes nothing; not present |
| `.xz` and legacy LZMA | S-0809 | Python `lzma`, automatic and legacy forms; leading bytes `FD 37 7A 58 5A 00` | decodes nothing; not present |
| bzip2 | Python's `bz2` (no public format specification beyond the reference program) | Python `bz2` | decodes nothing |
| LZ4 frame | S-0804 | leading bytes `04 22 4D 18` | not present |
| Zstandard frame | S-0808 | leading bytes `28 B5 2F FD` | not present |
| framed Snappy | S-0811 | leading bytes `FF 06 00 00 73 4E 61 50 70 59` | not present |
| LZ4 block | S-0803 | Fenolite's own decoder, written from the block description, one block per chunk of flag 1 | decodes every block of the four rows: 107 blocks |
| Brotli, raw Snappy, MS-XCA | design Decision 1 | not tried: the LZ4 block form decoded every chunk first | none |

No codec package was installed: the LZ4 block decoder is about forty lines of Fenolite's own code, and
the other candidates are in Python's standard library or were recognised by their leading bytes only.

### Tree (task 2.2, public half, 2026-10-16)

Measured by `uv run python tools/draftsman_census.py --tree` with Fenolite's reader and pinned by
`FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_draftsman_census.py -k tree`. Element names and
counts only.

| row | format version | root members | elements | under the `*Information` members | under `Pages` | sheets (size, items) |
|---|---|---|---|---|---|---|
| `altium-third-party-pcbdwf-01` | 22 | 37 | 2662429 | 2571867 (96.6 %) | 89037 | 2 A4, 26 and 25 items |
| `altium-third-party-pcbdwf-02` | 22 | 37 | 1089079 | 1083877 (99.5 %) | 3934 | 3 A4, 31, 26 and 29 items |
| `altium-third-party-pcbdwf-03` | 21 | 33 | 243822 | 232308 (95.3 %) | 9509 | 1 of 1056 × 816 from its template, 44 items |
| `altium-third-party-pcbdwf-04` | 21 | 33 | 172161 | 168351 (97.8 %) | 1845 | 1 of 1056 × 816 from its template, 44 items |

| row | items by kind | views (side, scale denominator and `Numenator`) | tables | notes (entries) | texts (`=` parameter texts) | document parameters |
|---|---|---|---|---|---|---|
| 01 | `BoardAssemblyViewData` 2, `Line` 16, `Picture` 2, `Text` 31 | assembly Top 2, 5; assembly Bottom 1, 2 | none | none | 31 (14) | 31 |
| 02 | `BoardFabricationViewData` 6, `DrillTableBoardView` 1, `LayerStackLegendView` 1, `Line` 24, `Picture` 5, `Text` 48, `TransmissionLineTableData` 1 | six fabrication views Top (five 1, 1; one 1, 2); one layer stack legend | drill table, transmission line table | none | 48 (21) | 31 |
| 03 | `BillOfMaterialsView` 1, `BoardAssemblyViewData` 4, `Line` 14, `LinearDimension` 3, `Picture` 2, `Rectangle` 1, `Text` 19 | assembly Top, Right, Front and Bottom, each 1, 2 | bill of materials (side `All`) | none | 19 (10) | 42 |
| 04 | `BoardFabricationViewData` 1, `Callout` 1, `DrillTableBoardView` 1, `DrillViewView` 1, `LayerStackLegendView` 1, `Line` 14, `LinearDimension` 2, `Note` 1, `Picture` 2, `Rectangle` 1, `Text` 19 | layer stack legend; drill drawing Top 1, 2; fabrication Top 1, 2 | drill table | one note of 12 entries | 19 (10) | 42 |

What the rows show:

- The board data members (`BillOfMaterialsInformation`, `BoardAssemblyInformation`,
  `BoardFabricationInformation`, `BoardLayersGeometryInformation`, `DrillTableInformation`,
  `LayerStackInformation` and the nil `BoardProjectionInformation`) hold 95.3 % to 99.5 % of a document's
  elements, and the sheets 0.4 % to 3.9 %. The copy of the board is most of a document, as design
  Decision 4 assumed when it chose shells.
- Some of these members are `i:nil` in a document: `DrillTableInformation` in 01 and 03, which have no drill
  table; `LayerStackInformation` in 01, which has no legend; `BoardAssemblyInformation` in 02, which has
  no assembly view; `BillOfMaterialsInformation` in 04, which has no BOM table. Two documents without such
  an item still fill the member (`BillOfMaterialsInformation` in 02, `LayerStackInformation` in 03).
- The documents of format version 22 have four root members more than those of version 21:
  `DocumentId`, `LayoutDrawingData`, `WiringDiagramData` and `WiringListInformationData` (the last three
  nil).
- Round F0 adds what each pending step of the approved Altium Designer 24.5.2.23 adds (task 2.2, the F0 half).

### Tree, round F0 (task 2.2, F0 half, 2026-11-04)

Measured by `uv run python tools/draftsman_census.py --json --tree <F0 files>` on the documents that an
agent saved on 2026-11-04 (S-1421), outside the repository. Names and counts only; no path or value of
the documents. All 13 are format version 24, one chunk each, 38 root members.

| step | decoded bytes | elements | under board data | under `Pages` | sheets (items) | items by kind | board data members filled |
|---|---|---|---|---|---|---|---|
| F0.1 | 53 882 | 1 844 | 8 | 18 | 1 (0) | none | none |
| F0.2 | 53 882 | 1 844 | 8 | 18 | 1 (0) | none (same bytes as F0.1) | none |
| F0.3 | 54 977 | 1 891 | 8 | 42 | 1 (1) | `Text` 1 | none |
| F0.4 | 54 978 | 1 891 | 8 | 42 | 1 (1) | `Text` 1 | none |
| F0.5 | 117 164 | 4 595 | 2 224 | 460 | 1 (1) | `BoardAssemblyViewData` 1 (Top, 1:1) | BOM, assembly, fabrication, layers geometry, embedded |
| F0.6 | 129 547 | 5 043 | 2 224 | 902 | 1 (2) | `BoardAssemblyViewData` 2 (Top, Bottom) | as F0.5 |
| F0.7 | 126 130 | 4 804 | 2 438 | 474 | 1 (2) | `DrillViewView` 1, `DrillTableBoardView` 1 | assembly, fabrication, drill table, embedded |
| F0.8 | 82 091 | 3 003 | 1 012 | 124 | 1 (1) | `LayerStackLegendView` 1 | layer stack, embedded |
| F0.9 | 121 179 | 4 732 | 2 224 | 582 | 1 (2) | `BoardAssemblyViewData` 1, `BillOfMaterialsView` 1 (side `All`) | as F0.5 |
| F0.10 | 132 027 | 5 001 | 2 438 | 653 | 1 (4) | as F0.7, `Note` 1 (2 entries), `LinearDimension` 1 | as F0.7 |
| F0.11 | 54 304 | 1 861 | 8 | 35 | 2 (0, 0) | none | none |
| F0.12 | 117 189 | 4 595 | 2 224 | 460 | 1 (1) | as F0.5 | as F0.5 |
| F0.13 (`.DwfDot`) | 127 900 | 4 867 | 2 438 | 537 | 1 (3) | as F0.10 without `LinearDimension` | as F0.7 |

Every document holds 29 document parameters and no parameter text. The F0 half of gate G1 is answered on
these files by Fenolite's reader (all decode). `test_f0_files_decode` first could not run: the kit privacy
scan refuses the folder for its VM paths (S-1314). On the maintainer's decision of 2026-11-04 it ran with
the VM's absolute work folder as the reviewed prefix (see "Observation intake") and passed on the twelve
`PCBDwf` documents and `F0-13.DwfDot`, and again on the whole folder with its PDF output once the scan
stopped reading PDF name objects as paths. Gate G1 is GO for decoding (task 1.5).
Fact rows: `docs/formats/altium/draftsman.md`, "Round F0 as saved by Altium Designer 24.5.2.23".

### Phase 1 budget

Phase 1 has a budget of 2 design-days (design Decision 1). The container of the public documents was
established on 2026-10-16 in under half a design-day. Gate G1 also needs every F0 file of the maintainer
(tasks 1.4 and 1.5) and is decided there.

## Drawing geometry (c0180)

Measured on 2026-10-25 with Fenolite's readers on the corpus cache (S-0785, S-0786, and the boards S-0187 and
S-0174); nothing of the files is committed. Comparisons of positions only. A first reading took the sheet as Y
down from its top-left corner; the title blocks and the note below show that it is Y up from its lower-left
corner, and the view counts are the same in both readings (corrected 2026-10-25).

| measurement | S-0785 with S-0187 | S-0786 with S-0174 |
|---|---|---|
| parts whose pads land on the board's pads within 0.05 unit (top: turn; bottom: mirror in Y, then turn) | `Assembly_Drawing`: 540 of 540, 239 of them bottom parts; `Fabrication_Drawing`: no part | `_Assembly`: 23 of 23; `_Fabrication`: 23 of 23; no bottom part |
| layer `Pad` primitives on a board pad centre within 0.05 unit | `Fabrication_Drawing`: 2 371 of 2 371; `Assembly_Drawing`: none in the document | `_Assembly`: 64 of 64; `_Fabrication`: none in the document |
| outline segments | 32 lines, 28 arcs (11 with the `Point` at `Angle1`, 17 at `Angle2`) | 4 lines |
| board shape tracks as stadiums (`Width` = length + width) | — | 3 of 3 checked |
| top or bottom views on their sheet (sheet Y up, `Location` the lower-left corner, custom or ratio scale) | 8 of 8 | 4 of 4; the two side views (`Right`, `Front`) not measured |
| tables with a `Size` on their sheet (`Location` the lower-left corner) | 2 of 2 | none has a `Size` |
| sheet frame: title block rows read from the top only with Y up | the `Title` row above `Number`, `Date`, `Drawn by` | the 14-unit project title above the `File` row; the one `Note` (12 elements) on its sheet only with Y up |
| part strokes (`Contour`s of `AssemblyDrawing` or `Silkscreen`) | 1 150 in `Assembly_Drawing`, open strokes | 77 in each document |
| linear dimensions | none | 5: 2 on a top view measure 225.6 and 81.6 units (the board's width and height) from their snaps; 3 on side views |

## Part F: Draftsman documents

Change c0172; pending, no Altium verification is claimed. Part F has three rounds: F0, observation files
that the maintainer saves in the approved Altium Designer 24.5.2.23 from a project Fenolite built (task 1.3); FP, probe
documents written by Fenolite that decide gates G2 and G3 (task 3.2); F1 to F8, the acceptance of a
build's document (task 6.1). Every file Altium saves stays in the maintainer's folder; only counts and
element names derived from it enter the repository, after `fenolite kit verify`'s path scan.

### Round F0: observation (task 1.3)

**Files.** Built outside the repository by `FENOLITE_ALTIUM_PART_F0=~/fenolite-altium-checks/session-6/F0-draftsman
uv run pytest tests/unit/backends/altium/test_part_f.py -k f0_kit`: `blink_routed/`, the Altium project
that `fenolite build examples/blink_routed/design.py --target altium --seed 1 --timestamp
2026-10-16T00:00:00Z` writes (the routed blink: a 50 × 30 mm two-layer board, `U1` and `R1` on the top,
`D1` on the bottom, four tracks, two layer-change vias and a row of stitching vias, an output job);
`README.md`, these steps in Brazilian Portuguese; and `SHA256SUMS`. The files settle the F0 half of
`H-A-DWF-CONTAINER` and `H-A-DWF-FIELD` and give the forms of the empty document, a Text, the views and the
tables that the writer of task 3.1 follows.

Work on a copy of the folder. Every new document is created with **File » New » Draftsman Document**:
template `[Default]`, project `blink_routed.PrjPcb`, source document `blink_routed.PcbDoc`. Every file is
saved with **File » Save As** into `blink_routed/` under the name given. Do F0.12 last, because it moves a
part on the board. For each step report `as expected` or the message Altium showed.

1. **F0.1** Open `blink_routed/blink_routed.PrjPcb`. Create a new document and add nothing. Save as
   `F0-01.PCBDwf`. Expected: one A4 sheet with no object; saved without a message.
2. **F0.2** Close `F0-01.PCBDwf`, open it again and save it unchanged as `F0-02.PCBDwf`. Expected: saved
   without a message.
3. **F0.3** Open `F0-01.PCBDwf`, place one Text (**Place » Text**) reading `FENOLITE-1` anywhere on the
   sheet. Save as `F0-03.PCBDwf`. Expected: the text shows on the sheet.
4. **F0.4** Open `F0-03.PCBDwf`, change the text to `FENOLITE-22`. Save as `F0-04.PCBDwf`. Expected: the
   new text shows.
5. **F0.5** Open `F0-01.PCBDwf`, place one **Board Assembly View** with View Side Top. Save as
   `F0-05.PCBDwf`. Expected: the view shows the outline, `U1` and `R1`.
6. **F0.6** Open `F0-05.PCBDwf`, place a second Board Assembly View with View Side Bottom. Save as
   `F0-06.PCBDwf`. Expected: the second view shows `D1`, seen from the bottom.
7. **F0.7** Open `F0-01.PCBDwf`, place one **Drill Drawing View** (layer pair Top – Bottom) and one
   **Drill Table**. Save as `F0-07.PCBDwf`. Expected: the view shows the holes with symbols and the table
   lists their sizes.
8. **F0.8** Open `F0-01.PCBDwf`, place one **Layer Stack Legend**. Save as `F0-08.PCBDwf`. Expected: the
   legend shows the board's layers, two of them copper.
9. **F0.9** Open `F0-05.PCBDwf`, place one **Bill of Materials** table. Save as `F0-09.PCBDwf`. Expected:
   the table lists `D1`, `R1` and `U1`.
10. **F0.10** Open `F0-07.PCBDwf`, place one **Note** with two entries, `FENOLITE NOTE ONE` and
    `FENOLITE NOTE TWO`, and one **Linear Dimension** between the left and the right edge of the board
    outline in the drill drawing view. Save as `F0-10.PCBDwf`. Expected: the note is numbered 1 and 2 and
    the dimension reads the board's width, 50 mm (1968.5 mil).
11. **F0.11** Open `F0-01.PCBDwf`, add a second sheet. Save as `F0-11.PCBDwf`. Expected: two empty sheets.
12. **F0.12** (last) Open `blink_routed.PcbDoc`, move `R1` 5 mm to the right and save the PCB. Open
    `F0-05.PCBDwf`, run **Tools » Import Changes From blink_routed.PcbDoc**. Save as `F0-12.PCBDwf`.
    Expected: the view shows `R1` at its new place.
13. **F0.13** Open `F0-10.PCBDwf` and save it with **File » Save As**, type Draftsman document template, as
    `F0-13.DwfDot`. Expected: saved without a message.
14. **F0.14** Open `F0-10.PCBDwf`, **File » Export to PDF** (one file, all sheets) as `F0-14.pdf`.
    Expected: a PDF of one page with the views, the table, the note and the dimension.

Send the whole folder (with the files Altium saved and the project as Altium left it), the Altium Designer
version (`AD <major>.<minor>`, from **Help » About**), the date, and one outcome per step. The files are
read only after `fenolite kit verify`'s path scan has run on the folder (task 1.4).

### Round FP: candidate probes

Prepare with `FENOLITE_ALTIUM_PART_FP=<outside folder> uv run pytest
tests/unit/backends/altium/test_part_f.py -k fp_candidates`. FP3 to FP5 can be prepared from the public
fact rows. FP1 and FP2 are absent until the real F0.3 control is supplied through `FENOLITE_DWF_F0` and
passes the kit privacy scan, including its decoded chunks. `status.json` names missing probes and keeps
the native verdict `unjudged`; `SHA256SUMS` binds the exact handover bytes. Work on a copy.

1. **FP1** Open the F0.3 control re-encoded into stored chunks. Expected: no message, the original Text.
2. **FP2** Open that control with only the Text changed to `FENOLITE-22`. Expected: no message, the changed Text.
3. **FP3** Open the document written from scratch with one sheet and one Text. Expected: no message, `FENOLITE-1`.
4. **FP4** Open the minimal document with a top assembly shell; Import Changes from `blink_routed.PcbDoc`.
   Expected: the board outline and top components fill the view. This settles `H-A-DWF-IMPORT` only when run.
5. **FP5** Use `FP5.DwfDot` in File » New » Draftsman Document. Expected: a document with the current board.

Report the date, exact version, file hashes, whether each opens without a message and what it shows.
These probes settle `H-A-DWF-MINIMAL`, `H-A-DWF-IMPORT` and `H-A-DWF-TEMPLATE`; no probe has run here.

### Round F1 to F8: candidate acceptance

Prepare with `FENOLITE_ALTIUM_PART_F=<outside folder> uv run pytest
tests/unit/backends/altium/test_part_f.py -k accept_candidate_kit`. The routed blink gains an authored
two-layer stack-up, title block and two notes per applicable page. The native gate is overridden only
inside the kit test. `expected.md` lists exact model drill counts, stack rows and parts; `SHA256SUMS`
binds the handover. This remains a candidate: generic native board Table/dimensions, exact table filters,
table sizes and source refresh await F0/FP4. Board rows are currently Texts. Work on a copy.

1. **F1** Open the project and its listed `blink_routed.PCBDwf`. Expected: no message.
2. **F2** Inspect the three sheets, paper, title-block parameters and estimated layout. Expected: correct
   titles/values and no overlapping objects. Settles `H-A-DWF-PARAMS` only after an actual report.
3. **F3** Import Changes from `blink_routed.PcbDoc`. Expected: every shell view fills from the board.
4. **F4** Inspect assembly views. Expected: designators and the bottom side viewed from below.
5. **F5** Compare the drill symbols and table with `expected.md`. Expected: exact counts per diameter.
6. **F6** Compare the legend and BOM with `expected.md`. Expected: the layer rows and parts agree.
7. **F7** Inspect the notes. Expected: the two authored notes on each applicable page, numbered in order.
8. **F8** Export all sheets to PDF, run the `PCBDrawing` output and save `saved.PCBDwf`. Expected: three
   PDF pages and the written scope retained by `FENOLITE_ALTIUM_F8=<file> uv run pytest
   tests/unit/backends/altium/test_part_f.py -k f8`. Settles `H-A-DWF-OUTJOB` only after the native output.

Send the date, exact version, original/saved hashes and one expected/observed outcome per step.
`H-A-DWF-KIT` stays unconfirmed until those actual outcomes exist. A missing save is a skipped proof.

### Observation intake

`uv run python tools/altium_observations.py F0 <folder>` runs the kit privacy scan before reading
members and reports hashes, element/item counts and changed member paths against each F0 control.
It writes nothing, prints no document values and never sets a native verdict. A scan refusal needs
local review; matched personal strings are not printed. Native files remain outside version control.

`FENOLITE_KIT_REVIEWED_PREFIX=<folder>` names exactly one absolute folder below a root that a person
reviewed, such as the work folder a native run writes into its files. A finding that is that folder or
lies under it counts as reviewed; every other finding still refuses, a relative path, a bare root or a
list refuses as the prefix, and the report holds `privacy_scan: reviewed` with the count
`privacy_reviewed`, never the prefix. Unset, nothing changes.

## Reports

No report of Part F has been received from the maintainer. The agent rounds below are not author
reports. Nothing on this page or in `docs/formats/altium/draftsman.md` is `ALTIUM-VERIFIED`.

2026-11-01 availability update: the maintainer reports that Altium Designer is unavailable now.
F0 saves, FP outcomes, F1-F8 and the native gates remain open. Public corpus read-back and authored
candidate kits are mechanical preparation only; they are not author reports or application saves.

### 2026-11-04, actual `AD 24.5.2.23`, rounds F0 and FP (sources S-1574 and S-1575)

A Claude agent ran these rounds at the maintainer's request of 2026-11-04. It operated the Altium
Designer installed in the maintainer's Parallels Windows VM. This is not the maintainer's own review.
`X2.exe` has FileVersion 24.5.2.23 (Trial licence, not signed in). Menu commands, clicks and keys were
sent through Windows UI Automation. The canvas was read from window captures, which were deleted after
viewing. Under the approved 24.5 scope these rounds complete no case, open no gate and raise no level.

**F0 inputs.** The F0 kit was built at `9de1ae80` with `FENOLITE_ALTIUM_PART_F0=<folder> uv run pytest
tests/unit/backends/altium/test_part_f.py -k f0_kit`. It has these digests:

| file | SHA-256 |
|---|---|
| `blink_routed.PrjPcb` | `99bcc6d9…` |
| `blink_routed.SchDoc` | `c1c35243…` |
| `blink_routed.PcbDoc` | `6691042b…` |
| `blink_routed.PcbLib` | `640bbcdb…` |
| `blink_routed.SchLib` | `2308a12f…` |
| `blink_routed.OutJob` | `595be494…` |
| `fenolite-base.json` | `34d8eccd…` |

The agent worked on a VM copy, `C:\FenoliteClaude\c0172\F0\blink_routed`. Every step used File » Save As
into that folder.

| step | saved file (SHA-256) | observed |
|---|---|---|
| F0.1 | `F0-01.PCBDwf` `bba5247f…` | New Document offered template `[Default]`, project `blink_routed.PrjPcb` and document `blink_routed.PcbDoc`. One sheet with no object. Saved without a message. |
| F0.2 | `F0-02.PCBDwf` `bba5247f…` | Saved without a message; the bytes equal F0-01. The Projects panel then lists `F0-02.PCBDwf` under the project, which shows as modified. The `.PrjPcb` on disk is unchanged. |
| F0.3 | `F0-03.PCBDwf` `bbd8713f…` | The Text's field holds `FENOLITE-1`. The sheet shows `FENOLITE`, clipped because Clip Text To Bounds keeps the box of the default `New Text`. Saved without a message. |
| F0.4 | `F0-04.PCBDwf` `6f3b54b0…` | The field holds `FENOLITE-22`. Saved without a message. |
| F0.5 | `F0-05.PCBDwf` `972c4046…` | A view titled `View from Top side (Scale 1:1)` shows the outline with small part graphics. The designators were not legible at the captured zoom. Saved without a message. |
| F0.6 | `F0-06.PCBDwf` `eb306061…` | The second view, with View Side Bottom, is titled `View from Bottom side` and shows `D1`. As expected. |
| F0.7 | `F0-07.PCBDwf` `b204b78c…` | The view shows the holes with symbols. The Drill Table lists 7 × 0.30 mm plated, 2 × 0.90 mm plated and 9 in total. As expected. |
| F0.8 | `F0-08.PCBDwf` `99fd0821…` | The legend lists overlays, solder masks, Top Layer and Bottom Layer (copper, 0.04 mm each), FR-4 0.32 mm and a total of 0.41 mm. Two layers are copper. As expected. |
| F0.9 | `F0-09.PCBDwf` `fa690fd3…` | **Not as expected.** The Bill of Materials table shows only its header row; there is no row for `D1`, `R1` or `U1`. When reopened for this step, `F0-05` already showed as modified (see the incident below). |
| F0.10 | `F0-10.PCBDwf` `32180e3a…` | The Note holds the two entries, numbered 1 and 2, after the default third entry was deleted. The Linear Dimension between the outline's left and right edges reads `50.00mm`. It attached only after the status bar's `Snapping: Disabled` was switched to Enabled with Shift+E. Saved without a message. |
| F0.11 | `F0-11.PCBDwf` `da95dc9e…` | Tools » Add New Sheet in `F0-01`. Saved without a message; the agent did not count the sheets. |
| F0.12 | `F0-12.PCBDwf` `e52414c9…` | `R1` was moved by a read-write DelphiScript (`MoveByXY` of +5 mm, from (32, 21) to (37, 21) mm from the board origin), not by a drag. File » Save of the PCB showed no message (`blink_routed.PcbDoc` now `3d43fa2e…`). Tools » Import Changes From blink_routed.PcbDoc showed no message, and the `R1` graphic in the top view moved right by about 5 mm, judged from captures before and after. Saved without a message. |
| F0.13 | `F0-13.DwfDot` `c4db5299…` | **A message.** Type `Altium Draftsman Document Templates (*.DwfDot)` showed a Confirmation: the dimensions, callouts, section views and detail views will be deleted, the action is irreversible, proceed? The agent chose OK, and the file was saved. |
| F0.14 | `F0-14.pdf` `3c8a4bc0…` | File » Export to PDF showed no message and no option dialog. The PDF has one A4 landscape page with the drill view, the 50.00 mm dimension, the Drill Table and the two notes. As expected. |

**Incident.** Before F0.8, keystrokes sent through SendKeys left Shift and Alt held down. Later clicks
then opened "Customizing PcbDrawing Editor", a "Draftsman" dialog and the find-text and edit-menu
windows. The agent closed them, released the keys and repeated F0.8. No saved file was overwritten.
`F0-05` showed as modified when reopened for F0.9, probably from stray keys, and F0-09 was built on it.
The cause of the disabled snapping in F0.10 is unknown. `F0-10` showed as modified as soon as it was
reopened for F0.14.

**Path scan and intake.** The saved folder was copied to the agent's kit folder outside the repository.
`uv run python tools/altium_observations.py F0 <folder>` **refused** it (exit 3) because the kit privacy
scan has findings:

- 14 raw `absolute-path` findings. Each Draftsman file holds the VM folder
  `C:\FenoliteClaude\c0172\F0\blink_routed` once, and the saved PcbDoc holds `…\blink_routed.$$$`.
- 39 decoded-chunk findings, all the VM path of `blink_routed.PcbDoc`.
- 20 findings in `F0-14.pdf`. They are PDF name objects (`/Type`, `/Filter`, …) read as POSIX roots.

No finding is a home folder or a login name. The agent checked this locally, path segment by segment.

So Altium writes the absolute path of the source PCB into every Draftsman document. A folder saved
under a user profile would therefore carry that profile's path. Because the intake refused the folder,
no member was interpreted, `test_f0_files_decode` was not run, and the F0 halves of `H-A-DWF-CONTAINER`
and `H-A-DWF-FIELD` are still unmeasured.

**FP.** The probes were built at `9de1ae80` with `FENOLITE_ALTIUM_PART_FP=<folder> uv run pytest
tests/unit/backends/altium/test_part_f.py -k fp_candidates`:

- `FP3.PCBDwf` `d29f5b1d…`; `FP4.PCBDwf` and `FP5.DwfDot` both `992b5098…`; `status.json` `a3f7e522…`.
- `status.json` lists FP1 and FP2 as missing and keeps the native verdict `unjudged`.
- With `FENOLITE_DWF_F0` set to the saved F0 folder, the build fails, because the same kit privacy scan
  refuses the F0.3 control.

The digests match the VM copy before and after the run.

| probe | observed |
|---|---|
| FP1, FP2 | not built: the F0.3 control does not pass the kit privacy scan |
| FP3 | **does not open.** File » Open shows an `Error` window, `Value cannot be null. Parameter name: source`, with a crash-report form. The agent closed it with Close, so no report was sent, and no document opened. |
| FP4 | **does not open**, with the same error; Import Changes was not reached |
| FP5 | not run as written. Offering the `.DwfDot` in File » New » Draftsman Document needs it registered under Preferences » Data Management » Templates, a lasting change to the maintainer's installation that the agent did not make. Opened directly with File » Open, it shows the same error. |

`H-A-DWF-MINIMAL`, `H-A-DWF-IMPORT` and `H-A-DWF-TEMPLATE` keep their levels. These are 24.5 agent
observations, and the rows name Altium Designer 26.5. The G2 and G3 decisions of c0172 Decision 9 are
left to the maintainer. No native file, capture or saved document enters the repository.

**Evening FP retry (source S-1581).** At the maintainer's second request of 2026-11-04 the agent rebuilt
the probes at `0207378b` with the same command. The bytes are identical to the run above: `FP3.PCBDwf`
`d29f5b1d…`, `FP4.PCBDwf` and `FP5.DwfDot` `992b5098…`, `status.json` `a3f7e522…`. So FP3 and FP4 were
not opened again. The causes asked about are these:

- FP1 and FP2 are not built because the F0.3 control fails the kit privacy scan. Altium itself writes the
  absolute path of the source PCB into every saved Draftsman document (see F0 above). The generator
  cannot choose a relative path there, because the path comes from the native control.
- The error from FP3 and FP4 is not caused by a VM path. FP3 (975 bytes) holds no path, and FP4 names
  the PCB only by its bare file name, `blink_routed.PcbDoc`, in `SourceDocumentName`. A string scan of
  both files finds no drive or home folder. The cause lies in the minimal document itself and is not
  known.
- FP5: File » New » Draftsman Document lists four built-in templates (`[Default]`, two `Assy Drawing -
  Main views` variants and `Default Fabrication Drawing`). Its "Templates ..." button opens Preferences,
  which would register the `.DwfDot` there, a lasting change to the maintainer's installation. The agent
  cancelled both dialogs. FP5 stays not run as written.

`H-A-DWF-MINIMAL`, `H-A-DWF-IMPORT` and `H-A-DWF-TEMPLATE` keep their levels.

**Night FP run with the complete probes (source S-1589).** Run by a Claude agent at the maintainer's request
of 2026-11-04/05, relayed by the coordinator, in Altium Designer 24.5.2.23 (Trial) in the maintainer's
Parallels Windows VM. It is not the maintainer's own review. The probes were built complete, with controls
that pass the kit privacy scan, at `3c6e8b35`. `status.json` lists no missing probe and keeps the native
verdict `unjudged`. The run used a VM copy. Every file has the same digest after the run.

- `FP1.PCBDwf` `2d49015e…`; `FP2.PCBDwf` `b62ab34e…`.
- `FP3.PCBDwf` `d29f5b1d…`, and `FP4.PCBDwf` and `FP5.DwfDot` `992b5098…`. These are the bytes of S-1575
  and S-1581.
- `blink_routed.PcbDoc` `6691042b…`; `status.json` `6bfbd4a7…`.

| probe | observed |
|---|---|
| FP1 | opens through File » Open with no message, and the document is not marked modified. One sheet (columns A–E, rows 1–4) holds one Text. Properties: Text `FENOLITE-1`, frame 18.289 × 6.906 mm, Clip Text on, font size 12. The frame clips the drawn text to `FENOLITE` |
| FP2 | opens with no message. The document is marked modified (`*`) right after opening. Properties: Text `FENOLITE-22`, the same frame and options. The drawn text is clipped to `FENOLITE` |
| FP3, FP4 | not opened again: the bytes are those of S-1575, where both fail with `Value cannot be null. Parameter name: source` |
| FP5 | with the agent's temporary template folder (below), File » New » Draftsman Document lists `[Default]` and `FP5`. With project `blink_routed.PrjPcb` and document `blink_routed.PcbDoc`, OK creates `blink_routed.PCBDwf` at once with no message. After a fit (Ctrl+PgDn) it shows an empty sheet, columns A–E and rows 1–4, and no board view. Nothing was written to disk. About one to two minutes later, with no further action by the agent, an `Error` window appeared with `Object reference not set to an instance of an object` and a crash-report form. Two more `Error` windows appeared while the documents were closed; their text was not read. Each was closed with Close, so no report was sent |

For comparison, the native controls `F0-03.PCBDwf` (`bbd8713f…`) and `F0-04.PCBDwf` (`6f3b54b0…`) were opened in
the same way. Both open with no message and are marked modified at once. F0-04 shows Text `FENOLITE-22` with
the same frame, Clip Text and size, and the same clipped `FENOLITE`. So the clipping comes from the control,
not from the probes.

The template folder was a temporary change, authorized by the coordinator on the maintainer's authority.
Preferences » Data Management » Templates, Local Templates folder, was the default `Altium\AD22\Templates`
folder under the Windows public documents folder. It was set to the VM probe folder for FP5 and then set back
to that value with OK. Afterwards the New Draftsman Document dialog listed only the built-in templates again.
On the first attempt, a value was typed into the hidden text box of the Templates visibility combo box.
That dialog was cancelled. The box was cleared before the final OK, and the combo box showed `Server & Local`
throughout.

`H-A-DWF-MINIMAL`, `H-A-DWF-IMPORT` and `H-A-DWF-TEMPLATE` keep their levels, because this was an agent run.
The coordinator has already treated gate G2 as failed and moved the native document to c0388. These FP1,
FP2 and FP5 observations are recorded for that change. No native file, capture or saved document enters the
repository.

## Approved pending-native scope — 2026-11-03

The maintainer explicitly authorized the pending Altium validations on the
available Altium Designer 24.5.2.23: "tenho so o24.5, mas eu autorizo as
validacoes serem no24, nao precisa ser na26". This replaces the version
prerequisite of pending runs only. Record the actual tool/build, input hashes
and each observed outcome. It does not complete a case, open a write gate,
raise evidence, prove26.5 equivalence or replace any historical26.5 report.
Do not combine different versions/input digests into one fictional kit run.
All existing acceptance criteria, facts-before-code rules and final CI remain.
The kit form keeps its existing AD major.minor dialect: use AD 24.5; keep full
build 24.5.2.23 in the separate native observation report, not a new form key.
