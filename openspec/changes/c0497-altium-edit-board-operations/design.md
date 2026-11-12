# Design: c0497

Every new operation follows the session's existing pattern (`edit/session.py`):

- a `Session` method queues one `_Queued(gate, label, run)`;
- `run` is a function of `edit/ops.py` that edits a `State`, names its item by kind, geometry and net, states
  the old values it changes, and raises `Refused` on a mismatch;
- `commit` runs the gates, `verify` (strict read-back, the unexpected-change, connectivity and integrity
  gates) and `atomic_write`.

Nothing here bypasses `verify`. A new storage that an operation writes (`Board6`, `BoardRegions`) joins
`session._records` so that the unexpected-change gate covers it.

## D1 CLI exposure: `fenolite edit PATH.PcbDoc --ops-file FILE`

**Decision.** `cmd_edit` gains a third source option, `--ops-file`, accepted only when PATH is a `.PcbDoc`.
`.py`, `.toml` and the library tables keep `--content-file` and `--edits-file`. The file is a JSON list. Each
entry is `{"op": <Session method>, "item": <item>, ...keyword arguments}`. An item is a tagged object, for
example `{"kind": "via", "at": ["12.5mm", "3mm"], "net": "GND"}` or `{"kind": "designator", "ref": "R1"}`.
Lengths are given as text with a unit (`"0.1mm"`, `"4mil"`) or as integer nm. The command:

1. builds a `Session` and queues the entries in order. An unknown op, item kind or argument gives `FEN-2001`,
   naming the entry's index;
2. runs `Session.apply` and `verify` and plans the bytes as one `PlannedWrite` of kind `pcbdoc`. The result
   holds the operation labels, the receipt's issues and the counts per storage that were removed and added;
3. writes nothing on `--dry-run`. With `--confirm --plan ID` it writes the reviewed bytes.

Session issues keep their codes, and their exit codes follow the contract: `altium.edit.assertion`,
`altium.edit.gate` and the others exit 5.

**Gates from the CLI.** `--gate NAME` (repeatable) opens one gate for this run, as `edit.open(gates=...)` does
for a script. Each opened gate gives `altium.edit.gate-opened` (warning), and the run's evidence drops to
`UNVERIFIED`. `edit.GATES` stays all off. An open gate does not raise any hypothesis.

**Alternatives.**

- One subcommand per operation (`fenolite edit cutout ...`). This needs about 20 new parsers, the items do not
  fit flags, and a script still could not chain the operations into one commit.
- A Python-only API. The field scripts used the Python API and still needed private calls. The CLI is how an
  agent reaches the operations under the write protocol.

**Decision (maintainer, 2026-11-12).** `--gate` stays: the CLI opens an unconfirmed gate for one run, with the
warning and the `UNVERIFIED` evidence, as the Python API's `gates=` does. Change c0501 uses the same option for its
Altium write.

## D2 Texts of a component (F27)

**Items.** `Designator(ref)` and `Comment(ref)`. `View.find` takes the component's index (`View.component`).
Of its `Texts6` records it takes the one whose is-designator byte (41) or is-comment byte (40) is set. There
must be exactly one, else `altium.edit.assertion`. A short text record (the 137-byte form, no flag bytes) is
refused with `altium.edit.no-template`, because the record does not say which text it is.

**Free texts.** `Text(text, layer=None, at=None)`. `layer` keeps the texts on that layer. `at` keeps the texts
whose anchor lies within `ops.REACH`, the nearest one winning by `_nearest`. The shown string is compared after
both are read through `state.wide()`, and through the short string when the record has no wide index, as
today. Now a lookup that matches nothing names the free texts on that layer, up to five, in the refusal.

**Move.** `move(Designator(ref), dx, dy)` shifts X,Y at offset 13 (`records.shift`). The anchor stays the
anchor, so a pure shift needs no mirror logic.

**Turn.** `rotate(Designator(ref), degrees, old_rotation=)`. The anchor is the bottom-left corner of the text's
box. On a mirrored record (byte 35) it is the bottom-right corner (`pcbrecords.text_record`). So the turn
works in three steps:

1. take the box centre from the anchor, the text's width and its height, mirrored when byte 35 is set;
2. turn the centre's box about itself by `degrees`;
3. write back the anchor of the turned box under the same mirror rule, and the rotation (offset 27) as
   `(old + degrees) mod 360`.

The text's width comes from the stroke font metrics the writer already uses for silk (`pcbrecords`). A TrueType
text (font type 1) has no width Fenolite can compute. It is refused with `altium.edit.assertion`, "turn a
TrueType text about its anchor with `about="anchor"`". `about="anchor"` turns it about the anchor, the simple
case that needs no width.

**Autoposition.** A component holds the position mode of its designator and its comment as keys of
`Components6`. No row of `docs/formats/altium/` names them yet. Task 1.1 takes their names and their values
from a census of the public corpus (`CORPUS-VERIFIED`, counts only). After a move or a turn, the key of that
text is set to the value that means manual. Without that, a later move of the component in Altium may put the
text back. Whether Altium keeps a manual text when the component moves is `H-A-EDIT-TEXT`, kit case
`J-text`. If the census finds no such key, the operation leaves the component record alone, and the row says
so.

**Gate.** `text`, rows `H-A-EDIT-TEXT` and `H-A-EDIT-KIT`.

## D3 Board cut-out (F28)

**Record.** `add_board_cutout(ring, *, notch=False, drawing=None)` with `ring` given in nm, without a closing
vertex. The template is:

1. the first free region of the document with `ISBOARDCUTOUT=TRUE` and `KIND=0`, with its twin
   (`ops._twins`);
2. else `pcbrecords.cutout_region(vertices)` and its shape-based form, the writer's record of change c0168. Its
   KiCad import is ORACLE-VERIFIED (`pcb-records.md`, "Board cut-outs", `H-A-CUTOUT-REGION`). How Altium reads
   it is still `H-A-SLOT-KIT` (S3 to S5).

The new region gets the ring through `records.region_outline`, on layer byte 56, with no net, no polygon and
no component. Its `V7_LAYER` is that of the template.

**Board shape.** S-0771: a Board Cutout "defines a negative area or hole within the board shape". A ring inside
the outline therefore changes no outline record. Altium subtracts it, and `Board6` keeps the outer ring. Four
saved public rows hold free cut-out regions beside their `Board6` outline (`pcb-document.md`, the census row on
layer 56). Whether any of those outlines also holds the hole is read in task 1.1. A ring that crosses
the outline is refused (`altium.edit.assertion`, "the cut-out crosses the board outline") unless `notch=True`.
Then:

- the `Board6` vertex keys (`VX<k>`, `VY<k>`, `KIND<k>`, as `ops._with_outline` writes a polygon's) take the
  outline less the ring, computed with the geometry kernel's integer boolean (`fenolite.geometry`);
- the `BoardRegions` record's vertices take the same ring (`pcb-records.md`, the row on `BoardRegions`,
  `CORPUS-VERIFIED`);
- no cut-out region is written, because the notch is part of the outline.

Arc vertices of the old outline that the boolean does not touch are kept. Others become chords at the board's
arc resolution, as c0463 D1a does for pours.

**Drawing.** `drawing="Mechanical 1"` queues `draw_board_shape` (D6) after the cut-out in the same session. The
drawing's `old_count` is read when the session is applied, and the receipt reports it. A script that wants to
assert `old_count` calls `draw_board_shape` itself.

**Gate.** `cutout`, rows `H-A-EDIT-CUTOUT`, `H-A-SLOT-KIT` and `H-A-EDIT-KIT`.

**Alternatives.**

- Always edit `Board6` for a cut-out. Rejected: interior holes are regions in every saved row, and a hole in
  `Board6` has no saved form.
- Leave the notch to the user. Rejected: the field job was a notch at the edge.

## D4 Polygon cut-out (F29)

`add_polygon_cutout(ring, *, layer)`: a free region of `KIND=1` (`pcb-records.md`, "Board cut-outs", row 2,
`ORACLE-VERIFIED(kicad-cli)`; `pcb-pour.md`, the row on polygon cut-outs: the pour reaches its edge with no
clearance). It goes on a copper layer (1 to 32), or on Multi-Layer for every layer. Its template is a free
`KIND=1` region of the document, else a free `KIND=0` region on that layer with `KIND` set to 1
(`records.set_region_keys`), else `pcbrecords.region_record(..., polygon_cutout=True)`.

A cut-out makes the pour of each polygon it meets stale. Each polygon on that layer (all copper polygons for
Multi-Layer) whose outline ring meets the cut-out's ring loses its poured primitives, as `set_outline` drops
them (`ops._poured`, all storages). The receipt names those polygons. Altium's Repour then fills them again,
which c0452 checked for `set_outline` (S-2111).

**Gate.** `cutout`.

## D5 Via tenting and mask (F30)

**Selector.** `Vias(net=None, hole=None, diameter=None)` takes every via of the net (`None`: every via) whose
hole and diameter, if given, match within `ops.TOLERANCE`. `count` is required and must equal the number of
vias taken (`altium.edit.assertion` otherwise). It works as the old value of a bulk edit, because no via can be
named by its geometry alone in a list of 1,300. A single `Via` item keeps working.

**Fields** (`pcb-copper.md`, the via rows, `H-A-PCB-CU-VIATENT`):

- first flags byte (offset 1 of the record's first subrecord): bit 5 = tented top, bit 6 = tented bottom. Other
  bits are kept. The corpus shows bits 2 and 7 varying (`68`, `88`, `E8`). This operation keeps them, where
  the field workaround copied whole bytes;
- byte 66, solder-mask cache state: 2 (manual) when either side is tented or `expansion` is given. A state of
  1 (from rules) would let the rules decide again (c0166);
- bytes 54 and 242, front and back solder-mask expansion: written only when `expansion` is given, as the
  32-bit value in document units.

A via shorter than the saved 321-byte form (a record without byte 242) is refused with
`altium.edit.no-template`. Untenting clears the bits. The cache state stays 2, so that the manual expansion
decides.

**What decides the opening.** The corpus row says it is not known whether the bits or the expansion decide
the plotted opening. Kit case `J-tent` plots the Gerber mask of four authored vias (tented both sides,
top only, untented with expansion 0.05 mm, untented from rules) after Altium opens the written document. The
row `H-A-EDIT-TENT` records the result.

**Gate.** `tenting`, rows `H-A-EDIT-TENT`, `H-A-PCB-CU-VIATENT` and `H-A-EDIT-KIT`.

## D6 Fabrication drawing and its check (F31)

**Draw.** `draw_board_shape(layer, *, width, old_count)`, where `layer` is a mechanical layer:

1. take the free tracks and arcs on `layer` (no polygon, no component); their number must equal `old_count`;
2. remove them;
3. add one track per straight edge and one arc per arc vertex of the `Board6` outline, read as
   `docboard._outline` reads it, and of each free board cut-out ring (`Regions6`, `ISBOARDCUTOUT=TRUE`,
   `KIND=0`);
4. clone each new track or arc from a free track or arc on `layer` (`ops._template`), else from one on any
   mechanical layer, moved with `ops.relayer` (layer byte and long layer id). If there is neither,
   `altium.edit.no-template`.

**Check.** A new module, `edit/drawing.py`, holds `board_shape(doc)`, giving the outline and the cut-out rings
as edges, and `compare(doc, layer)`. The comparison:

- a shape edge is drawn when a drawn track or arc lies on it, ends within 0.01 mm (`DRAWING_TOLERANCE`) of its
  ends; a chain of collinear drawn tracks that covers it counts too;
- a drawn edge is matched when it lies on a shape edge.

Each unmatched edge on either side gives one `altium.board-drawing.mismatch` (warning), placed at the edge's
middle and saying which side lacks it. The stage `altium.board-drawing` of `fenolite check` runs `compare` on
every mechanical layer whose free tracks and arcs hold a closed ring within 0.01 mm of the `Board6` outline's
box. A document with no such layer gives the single info `altium.board-drawing.none`. Picking the layer this way
needs no new option of `fenolite check`, which has no per-stage arguments (`--stages`, `--exclude`, `--matrix`
and the others are global). Its limit: a drawing that lacks part of the outer ring has no closed ring, so its
layer is not found and the stage says `altium.board-drawing.none`. The explicit form is the Python call
`drawing.compare(doc, layer)`, which `draw_board_shape` runs as its own post-condition in `verify`: after a
redraw the named layer MUST compare with no mismatch.

**Evidence.** The drawing is plain tracks and arcs on a mechanical layer, already written by the panel writer
(`pcb-document.md`, the row on flattened panels: routed gaps on Mechanical 1). `H-A-EDIT-DRAWING` records that
Altium shows the redrawn layer equal to the board shape, in kit case `J-drawing`.

**Gate.** `board_drawing`, rows `H-A-EDIT-DRAWING`, `H-A-EDIT-CREATE` and `H-A-EDIT-KIT`.

## D7 Region outline (F32)

`Session.set_outline(item: Polygon | Region, outline, *, old)`. For a `Region`:

- `old` states every vertex within `ops.REACH`, as for a polygon;
- the new ring goes into the `Regions6` record and its twin with `records.region_outline` (straight vertices;
  the twin's arc flags are cleared);
- keys, flags (keep-out byte, restrictions), layer, net, polygon and component are kept.

A region of a polygon (a poured piece) is refused: it is not free. A board cut-out's outline may be changed. Its
fabrication drawing is then stale, which `altium.board-drawing.mismatch` reports. The gate is `set_outline`,
rows `H-A-EDIT-SHAPE` and `H-A-EDIT-KIT`, because this is the same record change as a region move (J14 and
S-2111).

## Test boards

All authored for Fenolite. `tests/unit/backends/altium/edit/board_ops.py` (new) builds them from the Part J
kit board (`test_part_j.build_board`) through the writer:

- `drawn.PcbDoc`: the kit board with its outline drawn on Mechanical 1 as tracks and one arc corner, one free
  board cut-out, one keep-out region, one polygon cut-out, and planted pour pieces for `GND` and `VIN` (the kit
  board's polygons are unpoured; the pieces are planted as `faults.py` plants its faults);
- `vias.PcbDoc`: twelve vias on two nets in the four tenting states, in the saved 321-byte form;
- `texts.PcbDoc`: `D1` on the top and `R1` flipped to the bottom, with designator and comment texts in the
  saved long form, and two free texts with one string on two layers.

Files that go under `tests/data` get a `tests/data/MANIFEST.toml` entry. The kit cases use the same builders,
and their saved native files stay outside the repository.

## Format evidence needed

| fact | where | label now | to reach |
|---|---|---|---|
| names and values of the component keys of a text's position mode | census of the public corpus (task 1.1) | none | CORPUS-VERIFIED |
| a turned or moved designator keeps its place in Altium | J-text | none | ALTIUM-VERIFIED(kit) |
| a written board cut-out without the keep-out flag is a hole in Altium | J-cutout (with S3 to S5) | INFERRED | ALTIUM-VERIFIED(kit) |
| a notched `Board6` and `BoardRegions` open without a collision | J-cutout | INFERRED | ALTIUM-VERIFIED(kit) |
| which of bits and expansion decides the plotted via opening | J-tent | INFERRED | ALTIUM-VERIFIED(kit) |
| a redrawn mechanical layer shows equal to the board shape | J-drawing | INFERRED | ALTIUM-VERIFIED(kit) |
| a changed keep-out ring is kept by Altium and its DRC | J-region | INFERRED (H-A-EDIT-SHAPE) | ALTIUM-VERIFIED(kit) |

## Risks

- **Kit case ids.** c0499 takes J34. The new cases are named `J-text`, `J-cutout`, `J-tent`, `J-drawing` and
  `J-region`, and get their numbers when they are written (task 4.1).
- **The CLI's `--gate`.** It makes it easy to write unconfirmed records. The warning, the `UNVERIFIED` evidence
  and the receipt's operation labels keep that visible. The maintainer accepted this trade (D1).
- **Text width.** Turning about the box centre depends on the stroke font metrics. Kit case J-text checks one
  0° to 90° turn on each side.

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-EDIT-TEXT` | a component's Designator and Comment text moved by the edit session (position, rotation, layer) opens in Altium Designer at the written place, without a repair message |
| `H-A-EDIT-CUTOUT` | a board cut-out region and a polygon cutout added by the edit session show in Altium Designer's board shape or pour as written, and a repour leaves them empty |
| `H-A-EDIT-TENT` | a via whose tenting the edit session sets carries the solder-mask flags Altium Designer reads as tented on the chosen sides |
| `H-A-EDIT-DRAWING` | board-outline tracks the edit session draws from the board shape on a mechanical layer follow every board-shape and cut-out vertex, so the layer plots the same outline |
