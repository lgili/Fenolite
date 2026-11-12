## ADDED Requirements

### Requirement: Designator and comment texts moved and turned
A session SHALL move and turn the designator or the comment text of a component, named by `Designator(ref)` or
`Comment(ref)`, with `Session.move` and `Session.rotate`. The item MUST be the one long text record of the component
whose is-designator or is-comment byte is set; none or two MUST refuse with `altium.edit.assertion`, and a
short record without those bytes with `altium.edit.no-template`. A move MUST shift the record's anchor alone. A turn
MUST turn the text's box about its centre and write the anchor of the turned box: its bottom-left corner, or its
bottom-right corner when the record's mirror byte is set. The component's position-mode key of that text MUST
then read manual when the corpus census names the key (change c0497).

#### Scenario: A bottom designator turned in place
- **GIVEN** the authored `texts.PcbDoc`, with `R1` on the bottom and its designator mirrored, at rotation 0
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_texts_c0497.py -k bottom_turn` turns
  `Designator("R1")` by 90° stating the old rotation 0 and commits
- **THEN** the written designator reads rotation 90 and the mirror byte set, and the centre of its box is where it
  was within 1 µm, and no other text record changes

#### Scenario: A comment moved
- **GIVEN** the authored `texts.PcbDoc`
- **WHEN** a session moves `Comment("D1")` by 1 mm in Y and commits
- **THEN** only that text's anchor moves by 1 mm, and `D1`'s designator and component record keep their place

### Requirement: Free texts narrowed by layer and place
`Text(text, layer=None, at=None)` SHALL keep only the free texts on `layer` and, with `at`, the nearest one whose
anchor lies within 0.002 mm. A lookup that matches no text MUST name up to five free texts of that layer in its
refusal (change c0497).

#### Scenario: Two free texts with one string
- **GIVEN** the authored `texts.PcbDoc`, with the free text `REV A` on Top Overlay and on Bottom Overlay
- **WHEN** a session moves `Text("REV A")`, and another moves `Text("REV A", layer="Bottom Overlay")`
- **THEN** the first is refused with `altium.edit.assertion` naming two records, and the second moves only the
  bottom one

### Requirement: Board cut-out added
`Session.add_board_cutout(ring, *, notch=False, drawing=None)` SHALL write a free region with `KIND=0` and
`ISBOARDCUTOUT=TRUE` on the Keep-Out layer, without net, polygon or component, in `Regions6` and in
`ShapeBasedRegions6`, cloned from a board cut-out of the document, else in the writer's form
(`pcbrecords.cutout_region`). A ring that crosses the board outline MUST be refused with `altium.edit.assertion`
unless `notch=True`. With `notch=True`, the `Board6` outline and the vertices of `BoardRegions` MUST become the
outline less the ring, and no cut-out region is written. `drawing=LAYER` MUST redraw that layer in the same commit,
as `draw_board_shape` does (change c0497).

#### Scenario: An inner cut-out
- **GIVEN** the authored `drawn.PcbDoc`, and a session that adds a 4 mm × 2 mm cut-out inside the board with
  `drawing="Mechanical 1"`
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_cutouts_c0497.py -k inner` commits it
- **THEN** both region storages hold one more cut-out of that ring, `Board6` is unchanged, Mechanical 1 holds
  four more tracks along the ring, and `fenolite check out.PcbDoc --stages altium.board-drawing` reports no
  mismatch

#### Scenario: A cut-out across the edge
- **GIVEN** the authored `drawn.PcbDoc`, and a ring that crosses its right edge
- **WHEN** a session adds it without `notch`, and another adds it with `notch=True`
- **THEN** the first is refused naming the board outline, and the second writes a `Board6` outline with the notch,
  the same ring in `BoardRegions`, and no new region

### Requirement: Polygon cut-out added
`Session.add_polygon_cutout(ring, *, layer)` SHALL write a free region with `KIND=1` on a copper layer or on
Multi-Layer, with its twin. Each polygon on that layer whose outline meets the ring MUST lose its poured primitives
in every storage, and the receipt MUST name it. Other polygons MUST keep their pour (change c0497).

#### Scenario: A cut-out in a ground pour
- **GIVEN** the authored `drawn.PcbDoc`, whose polygons `GND` and `VIN` hold planted pour pieces, and a ring
  inside `GND`
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_cutouts_c0497.py -k polygon_cutout` adds the cut-out
  on `GND`'s layer and commits
- **THEN** one free region of `KIND=1` is written on that layer, `GND` holds no poured primitive, `VIN` keeps
  its pour, and the receipt names `GND`

### Requirement: Via tenting and mask set
`Session.set_via_mask(selector, *, tented_top, tented_bottom, expansion=None, count)` SHALL set bits 5 and 6 of
the first flags byte of each via the selector takes, keeping its other bits, and the solder-mask cache state 2 at
byte 66. With `expansion` it MUST write it at bytes 54 and 242. The selector is a `Via` or
`Vias(net=None, hole=None, diameter=None)`. The number of vias it takes MUST equal `count`, else
`altium.edit.assertion`. A via record without byte 242 MUST refuse with `altium.edit.no-template` (change c0497).

#### Scenario: Every via of a net tented
- **GIVEN** the authored `vias.PcbDoc`, with six vias on `GND` in mixed tenting states
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_vias_c0497.py -k net` tents both sides of
  `Vias(net="GND")` stating `count=6` and commits
- **THEN** the six read `tented_top` and `tented_bottom`, keep bits 2 and 7 of their flags byte and their
  expansions, and the other six vias are unchanged; with `count=5` the commit is refused

### Requirement: Board shape drawn on a mechanical layer
`Session.draw_board_shape(layer, *, width, old_count)` SHALL remove the free tracks and arcs of the mechanical
layer `layer`, whose number MUST equal `old_count`, and draw each edge of the `Board6` outline and of each free board
cut-out ring as a track or an arc of `width`, cloned from a track or arc of a mechanical layer. The commit MUST
refuse a result that `drawing.compare` finds different from the board shape (change c0497).

#### Scenario: The drawing redrawn after a notch
- **GIVEN** the authored `drawn.PcbDoc`, its outline drawn on Mechanical 1 by 5 tracks and 1 arc
- **WHEN** a session notches the board and calls `draw_board_shape("Mechanical 1", width=0.1 mm, old_count=6)`
- **THEN** Mechanical 1 holds the new outline's edges, and `drawing.compare` gives no mismatch

### Requirement: Board drawing check
The stage `altium.board-drawing` of `fenolite check` SHALL compare, on each mechanical layer whose free tracks and arcs
close a ring within 0.01 mm of the box of the `Board6` outline, the drawn edges with the edges of the board shape.
Each edge of either side that has no edge of the other within 0.01 mm MUST give `altium.board-drawing.mismatch`
(warning) at its middle. A document with no such layer MUST give `altium.board-drawing.none` (info) (change c0497).

#### Scenario: A cut-out not drawn
- **GIVEN** a copy of `drawn.PcbDoc` with a second board cut-out that Mechanical 1 does not draw
- **WHEN** `fenolite check copy.PcbDoc --stages altium.board-drawing --json` runs
- **THEN** the issues hold one `altium.board-drawing.mismatch` per edge of that ring, and the original document
  gives none

### Requirement: Region outlines
`Session.set_outline` SHALL also take a free `Region`: `old` states each vertex within 0.002 mm, and the new ring
MUST be written into the `Regions6` record and its `ShapeBasedRegions6` twin, keeping its keys, flags, layer and
net. A region of a polygon MUST be refused (change c0497).

#### Scenario: A keep-out region enlarged
- **GIVEN** the authored `drawn.PcbDoc` and its rectangular keep-out region
- **WHEN** `uv run pytest tests/unit/backends/altium/edit/test_shapes.py -k region_outline` gives it a ring 1 mm
  larger on each side, stating the old ring, and commits
- **THEN** both records read back with the new ring and the keep-out flag and restrictions of the source; a wrong
  old ring is refused with `altium.edit.assertion`

### Requirement: Gates of the board edits
The operations of change c0497 SHALL be gated: the texts of a component by `text` (`H-A-EDIT-TEXT`), both cut-outs
by `cutout` (`H-A-EDIT-CUTOUT`, `H-A-SLOT-KIT`), the via mask by `tenting` (`H-A-EDIT-TENT`,
`H-A-PCB-CU-VIATENT`), the drawing by `board_drawing` (`H-A-EDIT-DRAWING`) and a region's outline by `set_outline`
(`H-A-EDIT-SHAPE`), each with `H-A-EDIT-KIT`. Every gate MUST be off as released, and each new hypothesis MUST be
named by a Part J case.

#### Scenario: A cut-out behind its gate
- **GIVEN** the gate of `cutout` off, as released
- **WHEN** a session adds a board cut-out and commits
- **THEN** the commit is refused naming the gate of `cutout` and `H-A-EDIT-CUTOUT`, and nothing is written
