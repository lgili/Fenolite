# Altium PCB document (`.PcbDoc`)

This page states, in Fenolite's own words, what the experimental writer `fenolite.backends.altium.pcbdoc`
(change c0035) relies on to write an Altium PCB document in the binary form, and what the test decoder
`tests/_altium_pcb_read.py` checks. Records are in `pcb-records.md`, the container in `compound-file.md`.

- Sources: KiCad's developer page (S-0002), KiCad's importer read for facts only (S-0160, S-0161), an MIT
  binary PcbDoc writer and a project that reports its output checked in the Altium 365 Viewer (S-0143),
  Altium's documentation (S-0164, S-0165, S-0149) and `kicad-cli` (S-0020, S-0166).
- Every row stays `INFERRED` until the maintainer's report (`docs/evidence/altium-pcb.md`, Parts P and D);
  `kicad-cli pcb import` settles only `H-A-PCB-KICAD-DOC`.
- `tests/unit/test_format_facts.py` checks the tables.

## Storages

| fact | source | label | hypothesis |
|---|---|---|---|
| "PCB Binary Version 6.0" is Altium's recommended PCB save format; an ASCII form with the same extension exists | S-0165 | INFERRED | H-A-PCB-DOC-OPEN |
| A binary PCB document is a compound file: root streams for the header, then one storage per object kind, each holding `Header` (a 32-bit record count) and `Data` (the records). Unlike a library footprint, every kind has its own `Data`, and each record keeps its type byte | S-0002, S-0160, S-0161 | INFERRED | H-A-PCB-KICAD-DOC |
| Property-text kinds: `Board6`, `Nets6`, `Components6`, `Classes6`, `Rules6`, `Polygons6`, `Dimensions6`. Binary kinds: `Arcs6`, `Pads6`, `Vias6`, `Tracks6`, `Texts6`, `Fills6`, `Regions6`, `ShapeBasedRegions6`, `ComponentBodies6`, `ShapeBasedComponentBodies6` | S-0002, S-0161 | INFERRED | H-A-PCB-KICAD-DOC |
| KiCad needs `Board6/Data`; a missing storage of the other kinds it looks for is reported on its standard output as "File not found" but not in its JSON report. A storage with `Header` 0 and an empty `Data` silences it (local probe of the format research) | S-0161, S-0020 | INFERRED | H-A-PCB-KICAD-DOC |
| The MIT writer writes empty storages for the kinds it does not use, among them `Arcs6`, `Regions6`, `ComponentBodies6`, `Classes6`, `DifferentialPairs6` and `Connections6`, and a third party reports such a file opening in the Viewer | S-0143 | INFERRED | H-A-PCB-DOC-VIEWER |
| `FileHeader`: KiCad reads a 32-bit length and a short string and checks nothing. The MIT writer writes the 32-bit value 19, then the first ten characters of `PCB 5.0 Binary File` in UTF-16LE (20 bytes), and a second root stream `FileHeaderSix`: the 32-bit value 19, one length byte, `PCB 6.0 Binary File` and the double 5.01 | S-0143, S-0161 | INFERRED | H-A-PCB-DOC-OPEN |
| `WideStrings6/Data` is a table: per entry a 32-bit index, a 32-bit byte length that counts a 2-byte NUL, and the UTF-16LE text with that NUL | S-0002, S-0160 | INFERRED | H-A-PCB-DOC-VIEWER |
| Primitives of a placed component are stored at absolute board coordinates with the component's index; the document holds no footprint definitions. A component index past the component count stops KiCad's import | S-0161, S-0143 | INFERRED | H-A-PCB-KICAD-DOC |

## Board, nets and components

| fact | source | label | hypothesis |
|---|---|---|---|
| `Board6/Data` is exactly one property record; KiCad refuses an empty one | S-0160, S-0161 | INFERRED | H-A-PCB-KICAD-DOC |
| `Board6` holds `ORIGINX` and `ORIGINY` (mil text) and the layer stack `LAYER<i>NAME`, `LAYER<i>PREV`, `LAYER<i>NEXT` (layer ids, 0 the end), and per mechanical layer `LAYER<i>MECHENABLED` | S-0002, S-0160 | INFERRED | H-A-PCB-DOC-OPEN |
| KiCad builds the copper stack by following `NEXT` from layer 1 until 0. It reads the `LAYER<i>` keys from i = 1 until the first missing `NAME` and follows a link only to an id below the number of names read, so ids up to at least 33 must be listed for a two-layer board to reach 32 | S-0160, S-0161 | INFERRED | H-A-PCB-KICAD-DOC |
| The outline is the vertex list `VX<k>`, `VY<k>`, `KIND<k>` (0 a line; another value an arc with `CX<k>`, `CY<k>`, `R<k>`, `SA<k>`, `EA<k>`); KiCad turns it into `Edge.Cuts` segments. The MIT project closes the polygon by repeating the first vertex and writes `KIND=Protel_Advanced_PCB` and `VERSION=5.00` | S-0002, S-0160, S-0143 | INFERRED | H-A-PCB-KICAD-DOC |
| `Nets6/Data` holds one property record per net with `NAME`; a net's index is its position | S-0160, S-0143 | INFERRED | H-A-PCB-DOC-NETS |
| `Components6/Data` holds one property record per component: `LAYER` (`TOP` or `BOTTOM`), `X`, `Y` (mil text), `ROTATION` (degrees), `LOCKED`, `NAMEON`, `COMMENTON`, `PATTERN` (the footprint name), `SOURCEDESIGNATOR`, `SOURCEUNIQUEID`, `SOURCEHIERARCHICALPATH`, `SOURCEFOOTPRINTLIBRARY`, `SOURCECOMPONENTLIBRARY` and `SOURCELIBREFERENCE` | S-0160, S-0143 | INFERRED | H-A-PCB-DOC-OPEN |
| KiCad takes the reference from `SOURCEDESIGNATOR`, the footprint id from `SOURCEFOOTPRINTLIBRARY` without path and extension plus `PATTERN`, and the footprint path from `SOURCEHIERARCHICALPATH` and `SOURCEUNIQUEID` with one leading backslash removed | S-0161 | INFERRED | H-A-PCB-KICAD-DOC |
| Altium links a schematic component and its PCB component by the schematic component's unique id, stored on the PCB side as the path `\<id>` (one sheet level); when ids do not match it offers to link by designator, comment and footprint | S-0164, S-0139 | INFERRED | H-A-PCB-DOC-LINK |
| Net names equal to the schematic's keep the connectivity in the change order | S-0164, S-0141 | INFERRED | H-A-PCB-DOC-NETS |
| The Altium 365 Viewer lists `*.PcbDoc` among its inputs and not `*.PcbLib` | S-0149 | INFERRED | H-A-PCB-DOC-VIEWER |
| `kicad-cli pcb import --format altium` reads a PCB document from 10.0; 9.0 has no `pcb import` | S-0166 | INFERRED | H-A-PCB-KICAD-DOC |
| `kicad-cli` 10.0.6 imports the PCB document Fenolite writes for the blink sample: exit 0, no error in the report or on stdout, three footprints with their references, pad nets and relative positions, the outline as four `Edge.Cuts` segments, the copper layers "Top Layer" and "Bottom Layer", `D1` on the bottom (`tests/kicad/altium/test_pcbdoc_oracle.py`, 2026-10-03) | S-0020, S-0166 | ORACLE-VERIFIED(kicad-cli) (10.0.6; 2026-10-03) | H-A-PCB-KICAD-DOC |
| The only warnings of that import, on stdout and not in the report, are "Layer 'Internal Plane n' could not be mapped and will be skipped" for n from 1 to 16; the mechanical layers 69 to 72 and the other names give none | S-0020 | INFERRED | H-A-PCB-KICAD-DOC |
| KiCad moves an imported board to the middle of its sheet, so an import keeps relative positions only; it warns about each `Board6` layer it cannot map (local probe of the format research) | S-0020 | INFERRED | H-A-PCB-KICAD-DOC |

## Fenolite's choices

- The root holds `FileHeader` and `FileHeaderSix` in the MIT writer's form, then the storages `Board6`,
  `Nets6`, `Components6`, `Pads6`, `Tracks6`, `Arcs6`, `Texts6`, `WideStrings6` and the empty storages
  `Vias6`, `Fills6`, `Regions6`, `ShapeBasedRegions6`, `Polygons6`, `Dimensions6`, `Classes6`, `Rules6`,
  `ComponentBodies6`, `ShapeBasedComponentBodies6`, `DifferentialPairs6` and `Connections6` (`Header` 0, empty
  `Data`).
- `Board6` holds `KIND=Protel_Advanced_PCB`, `VERSION=5.00`, `ORIGINX`, `ORIGINY`; for i from 1 to 74
  `LAYER<i>NAME` (the names of `pcb-records.md`, "Layers"), `LAYER<i>PREV` and `LAYER<i>NEXT` with
  `LAYER1NEXT=32`, `LAYER32PREV=1` and every other link 0; `LAYER<i>MECHENABLED=TRUE` for 69 to 72; then
  the outline as `KIND<k>=0`, `VX<k>`, `VY<k>` from k = 0, the first vertex repeated last.
- Frame: a point is placed as KiCad places it (`Transform.placement(at, θ, mirror=bottom)`), then Y is
  negated and the result shifted so that the outline's lowest X and highest Y (in KiCad's Y-down frame)
  land on (1000 mil, 1000 mil), which is also `ORIGINX`/`ORIGINY`. On the bottom side every layer takes
  its flip partner.
- Nets are written in name order; components in component-path order. `SOURCEUNIQUEID` is `\` followed
  by the schematic `UNIQUEID`, `SOURCEHIERARCHICALPATH` is empty, `NAMEON=TRUE`, `COMMENTON=FALSE`;
  `ROTATION` has at most six decimals.
- A pad whose number is a pin of its component on a net carries that net's index; other pads `0xFFFF`.
- Each component gets a designator text 0.5 mm above the middle of the top edge of the box of its pads and
  graphics, 1 mm high with a 0.15 mm stroke on the overlay of its side, and a comment text 1.5 mm below
  the middle of the bottom edge, hidden by `COMMENTON=FALSE`; both texts are also in `WideStrings6`, the
  wide-string index being the text's position in `Texts6`.
- No routing, vias, zones, rules, classes or polygons.
