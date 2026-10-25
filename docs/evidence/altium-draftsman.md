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
- Round F0 adds what each step of Altium Designer 26.5 adds (task 2.2, the F0 half).

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
that the maintainer saves in Altium Designer 26.5 from a project Fenolite built (task 1.3); FP, probe
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

## Reports

No report of Part F has been received. Nothing on this page or in `docs/formats/altium/draftsman.md` is
`ALTIUM-VERIFIED`.
