# board-frame Specification

## Purpose
Give the board-frame geometry of a KiCad design: every pad where it lies on the board, with exact integer copper entries per copper layer and its hole, and the courtyard of every placed footprint with rotation and side applied, so that checks, placement and manual copper need no hand-made pad table.
## Requirements
### Requirement: Board-frame module
The module `fenolite.backends.kicad.frame` SHALL compute the records of `backend-protocol` "Board-frame protocol" for designs read or built by the KiCad backend, and MUST import only the standard library, `core`, `model`, `geometry`, `backends.base` and modules of `backends.kicad` (`package-layering`).
- Public names: `board_pads`, `find_pads`, `placed_extent`, `placed_extents`, `copper_polygon`, `COURTYARD_LAYERS` (`("F.CrtYd", "B.CrtYd")`), `FRAME_ISSUE_CODES` and `EVIDENCE`. `fenolite.backends.kicad` MUST re-export `board_pads`, `find_pads`, `placed_extent` and `placed_extents`.
- `KicadBackend.board_pads` and `KicadBackend.placed_extents` MUST return what `board_pads` and `placed_extents` of this module return for the same arguments.
- Every function MUST be pure: it reads no file and no environment variable, runs no subprocess, and returns new values without changing its arguments.
- The board frame is the KiCad file frame: X to the right, Y down, integer nanometres, angles in microdegrees in [0°, 360°).

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change

#### Scenario: The backend delegates and nothing changes
- **GIVEN** the design read from `tests/data/kicad/board/two_layer.kicad_pcb` and the canonical texts of `canonical.dump_texts` for it
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_frame_pads.py -k delegates` compares `KicadBackend().board_pads(design)` with `frame.board_pads(design)` and dumps the design again
- **THEN** the two tuples are equal and the texts are unchanged

### Requirement: Board-frame pads
`board_pads(design, *, issues=None)` SHALL return one `BoardPad` per pad of every footprint of `design.board`, footprints in board order and pads in footprint order, and `find_pads(design, component, number)` SHALL return the records of the pads numbered `number` of the footprints of `component`.
- `ref` MUST be the reference of the footprint's component, `path` its `properties["fenolite.path"]` or `""`, and `net` the name of the net that `net_id` names, or `None`.
- `position` MUST be `Transform.placement(footprint.position, footprint.rotation).apply(pad.position)`, with no mirror on either side, because a bottom footprint keeps its stored, mirrored children (`H-G-BOTTOM-PLACE`). `rotation` MUST be `pcb.pad_angle_to_board(pad.rotation, footprint.rotation)`, the stored absolute angle (`H-G-PAD-ANGLE-ABS`). `side` MUST be the footprint's and `layers` MUST be `pad.layers` as stored.
- `find_pads` MUST match `component` against component paths first and against references when no path matches, MUST accept an `int` number as its decimal text, and MUST return every match of every matching footprint, in board order and pad order, so all pads sharing a number (an exposed pad split into several pads) are returned.
- `find_pads` MUST raise `KeyError` when no footprint matches `component`, or when no pad of the matched footprints has the number; the message MUST name the component and list the pad numbers of the matched footprints.

#### Scenario: The 270° case
- **GIVEN** `Mini_R_0603` placed with `place_footprint` for the component `R1` at (10 mm, 20 mm) with rotation 270° on the top
- **WHEN** `find_pads(design, "R1", 1)` and `find_pads(design, "R1", "2")` are called
- **THEN** pad `1` is one record at (10 mm, 19.2 mm) with rotation 270°, and pad `2` is at (10 mm, 20.8 mm)

#### Scenario: Bottom footprint
- **GIVEN** `Mini_QFP-32_7x7mm_P0.8mm` placed for `U1` at (50 mm, 50 mm) at 0° on the bottom, and the same definition placed on the top in another design
- **WHEN** `find_pads(design, "U1", "1")` is called on both
- **THEN** the bottom record is at (45.85 mm, 52.8 mm) with side `bottom` and layers `B.Cu`, `B.Mask`, `B.Paste`, and the top record is at (45.85 mm, 47.2 mm)

#### Scenario: Pads sharing a number
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top for a component `J1` whose `fenolite.path` is `io/J1`
- **WHEN** `find_pads(design, "io/J1", "1")` and `find_pads(design, "J1", 1)` are called
- **THEN** both return the two pads numbered `1`, at (−2 mm, 0) and (2 mm, 0), in that order

#### Scenario: Unknown pad number
- **GIVEN** the design of "The 270° case"
- **WHEN** `find_pads(design, "R1", "3")` is called
- **THEN** a `KeyError` is raised whose message names `R1` and lists `1` and `2`

### Requirement: Pad copper entries
`BoardPad.copper` SHALL hold, for each copper layer of `pad.layers` in that order, one or more `PadCopper` entries whose union is the pad's copper on that layer in the board frame, and SHALL be empty for a pad of kind `np_thru_hole`.
- Each entry MUST be built in the pad's own frame and moved by `Transform.placement(position, rotation)`; every coordinate MUST be computed exactly and rounded half to even once, so it lies within 0.5 nm of the exact value and is exact at multiples of 90° when the pad's sizes are even. Rings MUST be stored in the normal form.
- With `w` and `h` the pad size, the entries of the pad tokens of S-0001 MUST be:
  - `circle`: the centre with width `w`;
  - `rect`: the four corners of the `w × h` box, filled, width 0;
  - `oval`: as `circle` when `w == h`, otherwise the segment of length `|w − h|` along the longer side, with width `min(w, h)`;
  - `roundrect`: with `q` the opaque `roundrect_rratio` clamped to [0, 0.5] (0.25 when absent) and `r` equal to `q·min(w, h)` rounded half to even, the `(w − 2r) × (h − 2r)` box, filled, with width `2r`; when a side of the box is 0, the core is its segment (two points) or its point instead, with `filled` false;
  - `custom`: the anchor of `options` (`circle` or `rect`, `rect` when absent) at the pad size as above, then one entry per primitive with its stroke width: a filled `gr_poly` or `gr_rect` as a filled ring, an unfilled one as a closed polyline, a `gr_line` as its segment, and a filled `gr_circle` as its centre with width `2·⌈r⌉ + stroke`, exact only when the radius `r` is an integer. A `gr_poly` without `fill` counts as filled.
- These entries MUST be conservative supersets with `exact == False`, each pad giving one `kicad.frame.shape-approximated` info:
  - a `trapezoid` pad: its box grown by `|dx| + |dy|` on every side, `(dx, dy)` being its `rect_delta`;
  - a pad with chamfered corners (`chamfer_ratio` and a non-empty `chamfer` list): the same pad without chamfers;
  - a custom `gr_arc`: the polyline of `Arc.polygonize(DEFAULT_TOL)`; an unfilled `gr_circle`: the closed polyline of `Circle.polygonize(DEFAULT_TOL)`; a `gr_poly` whose `pts` hold arcs: its ring with the arcs polygonised, filled when the primitive is; each with its width grown by `2·DEFAULT_TOL + 2`;
  - a custom `gr_curve`: the convex hull of its control points, filled, with its stroke width;
  - a padstack layer whose shape is `roundrect`, `custom` or `trapezoid`: the box of its size.
- A padstack MUST give `F.Cu` the pad's own shape and size, and `B.Cu` and each inner copper layer the padstack entry named after that layer, else the entry `Inner` for an inner layer, else the pad's own shape and size.

#### Scenario: Roundrect pad
- **GIVEN** `Mini_R_0603` placed for `R1` at (10 mm, 20 mm), 0°, on the top
- **WHEN** `find_pads(design, "R1", 1)[0].copper` is read
- **THEN** it is one entry on `F.Cu` whose core is (8.975, 19.75), (9.425, 19.75), (9.425, 20.25), (8.975, 20.25) in mm, filled, with width 0.45 mm and `exact` true, so its outer box is the pad's 0.9 mm × 0.95 mm

#### Scenario: Oval, circle anchor and custom polygon
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top
- **WHEN** `board_pads(design)` is read
- **THEN** pad `2` has the segment (0, −2.9 mm)–(0, −2.1 mm) with width 1.6 mm on each copper layer, pad `3` has the disc at (4 mm, 0) with width 0.5 mm and the filled triangle (3.5, −0.5), (4.5, −0.5), (4, 0.5) in mm with width 0, and the unnumbered `np_thru_hole` pad has no entry

#### Scenario: Padstack layers
- **GIVEN** `Mini_Edge_Cases` placed with the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`
- **WHEN** the entries of pad `4` are read
- **THEN** the `F.Cu` entry is a disc of width 1.7 mm, the `In1.Cu` and `In2.Cu` entries are discs of width 1.2 mm, and the `B.Cu` entry is a filled 1.5 mm × 1.5 mm box

#### Scenario: Trapezoid flagged as a superset
- **GIVEN** the authored test footprint `Frame_Trapezoid`, whose `trapezoid` pad `1` of size 1 mm × 1 mm has `(rect_delta 0 0.2)`, placed at (0, 0), 0°
- **WHEN** `board_pads(design, issues=found)` runs
- **THEN** the pad's entry is the filled box (−0.7, −0.7)–(0.7, 0.7) in mm with `exact` false, and `found` holds one `kicad.frame.shape-approximated` naming the footprint and pad `1`

### Requirement: Pad holes
`BoardPad.hole` and `BoardPad.drill` SHALL give the drilled hole of a pad in the board frame: for `(drill D)`, the one point `position + R(rotation)·offset` with `drill == D`; for `(drill oval W H)`, the segment of length `|W − H|` along the longer of the two sizes, moved the same way, with `drill == min(W, H)`. `offset` MUST be the `(offset X Y)` of the drill node, else (0, 0), read from the pad's slots as `docs/formats/kicad/libraries.md` ("Drill forms") describes. A pad without a drill MUST have `hole == ()` and `drill is None`.

#### Scenario: Round and oval holes
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top
- **WHEN** `board_pads(design)` is read
- **THEN** pad `2` has the hole (0, −2.9 mm)–(0, −2.1 mm) with `drill` 0.8 mm, pad `4` the hole (−4 mm, 0) with `drill` 1 mm, the `np_thru_hole` pad the hole (0, 2 mm) with `drill` 1.2 mm, and pad `1` no hole

### Requirement: Placed extents
`placed_extent(footprint, *, definition=None, tol=DEFAULT_TOL, issues=None) -> PlacedExtent` SHALL return the courtyard of a placed footprint in the board frame, and `placed_extents(design, *, definitions=None, tol=DEFAULT_TOL, issues=None)` SHALL return one extent per footprint of `design.board`, in board order, `definitions` mapping a `lib_ref` to its definition.
- **Pieces.** The pieces of `front` and `back` MUST be the graphics on `F.CrtYd` and `B.CrtYd` among the footprint's own children, read in the stored frame, the frame in which c0018's `mod.board_footprints` reads a placed footprint, `fp_poly` children whose `pts` hold arcs included (`H-G-PTS-ARC`), and moved by `Transform.placement(footprint.position, footprint.rotation)` with no mirror; `source` is then `courtyard`. A footprint without KiCad slots MUST use, when a definition is given, its graphics on those layers moved by `Transform.placement(position, rotation, mirror=side == "bottom")`, front and back swapped on the bottom side, with `source` `definition`.
- **Rings.** A `rect` MUST give its four corners and a `polygon` its points; a `circle` MUST give `Circle.polygonize(tol, outer=True)` of its moved centre and its squared radius; `line` and `arc` pieces MUST be chained exactly with `assemble_rings` and each closed contour polygonised with `tol`. Rings MUST be in the normal form and each face sorted as `normalize_polygons` sorts. `exact` MUST be false when a curve was polygonised.
- **Malformed.** When the pieces of a face do not close (`geometry.open-contour` or `geometry.branching-contour`), that face MUST be the convex hull of the points of its pieces, curves polygonised, with `exact` false and one `kicad.frame.courtyard-malformed` warning naming the footprint and the layer.
- **Fallback.** When neither face has a piece, `source` MUST be `pads` and the face of the footprint's side MUST hold the convex hull of the corners of the boxes of all copper entries of its pads (a core's box grown by `⌈width / 2⌉`), with `exact` false; without copper entries `source` MUST be `none` and both faces empty. Both MUST give one `kicad.frame.no-courtyard` info.

#### Scenario: Rotated courtyard
- **GIVEN** `Mini_R_0603` placed at (10 mm, 20 mm) with rotation 90° on the top, and again at 270°
- **WHEN** `placed_extent(footprint)` is called for each
- **THEN** both give `front` equal to the one ring (9.25, 18.5), (10.75, 18.5), (10.75, 21.5), (9.25, 21.5) in mm, `back` empty, `source` `courtyard` and `exact` true

#### Scenario: Bottom courtyard is mirrored
- **GIVEN** the authored test footprint `Frame_Shapes`, whose courtyard is the rectangle (−3 mm, −2 mm)–(3 mm, 4 mm), placed at (50 mm, 50 mm), 0°, on the bottom
- **WHEN** `placed_extent(footprint)` is called
- **THEN** `back` is the ring (47, 46), (53, 46), (53, 52), (47, 52) in mm, `front` is empty and `own` is `back`

#### Scenario: Definition for an instance without slots
- **GIVEN** a `FootprintInstance` built in the test with the position, rotation and side of "Bottom courtyard is mirrored" and no `ext`
- **WHEN** `placed_extent(footprint, definition=<Frame_Shapes>)` is called
- **THEN** `back` equals the ring of that scenario and `source` is `definition`

#### Scenario: Circle courtyard
- **GIVEN** the authored test footprint `Frame_Round`, whose courtyard is a circle of radius 2 mm about its origin, placed at (20 mm, 20 mm)
- **WHEN** `placed_extent(footprint)` is called
- **THEN** `front` holds one ring, every vertex lies between 2 mm + 5 000 nm and 2 mm + 5 002 nm from (20 mm, 20 mm), every generated integer point within 2 mm of it is located `INSIDE` or `BOUNDARY` of the ring, and `exact` is false

#### Scenario: No courtyard
- **GIVEN** the authored test footprint `Frame_NoCourtyard`, with two `smd` rect pads of 1 mm × 1 mm at (±2 mm, 0) and no courtyard, placed at (0, 0), 0°, on the top
- **WHEN** `placed_extent(footprint, issues=found)` is called
- **THEN** `source` is `pads`, `front` is the ring (−2.5, −0.5), (2.5, −0.5), (2.5, 0.5), (−2.5, 0.5) in mm, `exact` is false, and `found` holds `kicad.frame.no-courtyard`

#### Scenario: Open courtyard
- **GIVEN** the authored test footprint `Frame_OpenCourtyard`, whose `F.CrtYd` holds three sides of a square
- **WHEN** `placed_extent(footprint, issues=found)` is called
- **THEN** `front` is the convex hull of the six end points, `exact` is false, and `found` holds one `kicad.frame.courtyard-malformed` naming the footprint and `F.CrtYd`

### Requirement: Copper polygons
`copper_polygon(entry, *, tol=DEFAULT_TOL) -> Polygon` SHALL return a polygon that contains the copper of a `PadCopper` entry, and SHALL be exact for a filled ring of width 0.
- A filled ring of width 0 MUST give `Polygon(entry.core)`.
- A disc, a two-point segment, or a filled convex ring with a width above 0 MUST give a polygon that contains every point within `width / 2` of the core, and whose vertices all lie within `width / 2 + tol + 2` nm of the core.
- Any other entry (a polyline of more than two points, a non-convex ring with a width above 0, a point or segment of width 0) MUST raise `ValueError` naming the case.

#### Scenario: Rounded and square entries
- **GIVEN** the roundrect entry of "Roundrect pad" and the `rect` entry of pad `1` of `Mini_LED_THT_3mm`
- **WHEN** `copper_polygon` is called on each
- **THEN** every generated integer point within 0.225 mm of the first core box is located `INSIDE` or `BOUNDARY` of the first polygon, every vertex of it lies within 0.225 mm + 5 002 nm of that box, and the second polygon equals `Polygon(entry.core)`

### Requirement: Board-frame issue codes
`frame` SHALL report its findings only with the codes of the closed table `FRAME_ISSUE_CODES`. They are `kicad.*` codes, so they pass through the closed sets of `lens.build.BUILD_ISSUE_CODES` (c0011) and `lens.preserve.PRESERVE_ISSUE_CODES` (c0019) unchanged, as `design-dsl` "Build issue codes" and `layout-lens` "Layout issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.frame.courtyard-malformed` | warning | a courtyard face does not close; its convex hull is used |
| `kicad.frame.no-courtyard` | info | a footprint has no courtyard; its pads' hull, or nothing, is used |
| `kicad.frame.shape-approximated` | info | a pad's copper entries are a conservative superset |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_frame_issues.py -k closed_set` collects every issue code produced by the frame tests
- **THEN** each is a key of `FRAME_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

### Requirement: Board-frame evidence
`frame.EVIDENCE` SHALL be `Evidence(Level.INFERRED, hypotheses=("H-G-ROT-DIR", "H-G-BOTTOM-PLACE", "H-G-PAD-ANGLE-ABS", "H-G-FRAME-SHAPE", "H-G-FRAME-CRTYD-2"))`; `H-G-FRAME-CRTYD-2` succeeds `H-G-FRAME-CRTYD`, refuted for circle courtyards at 20 µm.
- The level MUST stay `INFERRED` when `H-G-FRAME-SHAPE` and `H-G-FRAME-CRTYD-2` become `KICAD-VERIFIED`: those rows cover the bench footprints, not every pad token or courtyard. Positions and rotations rest on the three reused rows, which are `KICAD-VERIFIED (9.0.x, 10.0.x)`.

#### Scenario: Evidence constant
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_frame_issues.py -k evidence` reads `frame.EVIDENCE`
- **THEN** its level is `INFERRED` and its hypotheses are the five ids, in that order

### Requirement: Board-frame facts are documented
The board-frame rules and the KiCad facts they rely on SHALL be documented in Fenolite's own words, with sources and evidence labels.
- `docs/formats/kicad/frame.md` (new) MUST hold, as fact rows with source, label and hypothesis, the pad tokens and their entries (S-0001), the drill forms, the courtyard layers and pieces, the DRC key `courtyards_overlap` (S-0038, S-0058), and the load and re-save of version-8 uuids (S-0110, S-0020, S-0022), and MUST point to the existing frame rows of `docs/formats/kicad/board.md` and `geometry.md`.
- `docs/copper.md` (new) MUST describe the records and `BoardFrame`, the entry conventions, the supersets, the placed extents and their fallbacks, the copper API of `manual-copper`, the issue codes and the evidence.
- `docs/hypotheses.md` MUST register `H-G-FRAME-UUID`, `H-G-FRAME-SHAPE`, `H-G-FRAME-CRTYD`, its successor `H-G-FRAME-CRTYD-2` and `H-G-FRAME-ROUTE`, and `docs/evidence/sources.md` MUST register S-0110 and S-0111.

#### Scenario: Registers hold the new rows
- **WHEN** `grep -c '^| H-G-FRAME-' docs/hypotheses.md` runs
- **THEN** it prints `5`

#### Scenario: Fact tables are labelled
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py` runs
- **THEN** it passes, and every row of `docs/formats/kicad/frame.md` has a source id, a valid label and, below `KICAD-VERIFIED`, a hypothesis

