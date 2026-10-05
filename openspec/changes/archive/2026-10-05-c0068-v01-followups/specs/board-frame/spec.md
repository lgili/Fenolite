## MODIFIED Requirements

### Requirement: Pad holes
`BoardPad.hole` and `BoardPad.drill` SHALL give the drilled hole of a pad in the board frame: for `(drill D)`, the one point `position` with `drill == D`; for `(drill oval W H)`, the segment of length `|W − H|` along the longer of the two sizes, centred on `position`, with `drill == min(W, H)`. The `(offset X Y)` of the drill node MUST NOT move the hole: KiCad keeps the hole at the pad's position and moves the pad's copper by the offset ("Pad copper entries"; `H-G-FRAME-OFFSET`, measured on 9.0.9 and 10.0.6). A pad without a drill MUST have `hole == ()` and `drill is None`.

#### Scenario: Round and oval holes
- **GIVEN** `Mini_Edge_Cases` placed at (0, 0), 0°, on the top
- **WHEN** `board_pads(design)` is read
- **THEN** pad `2` has the hole (0, −2.9 mm)–(0, −2.1 mm) with `drill` 0.8 mm, pad `4` the hole (−4 mm, 0) with `drill` 1 mm, the `np_thru_hole` pad the hole (0, 2 mm) with `drill` 1.2 mm, and pad `1` no hole

#### Scenario: Hole of a pad with an offset drill
- **GIVEN** the authored test footprint `Frame_Offset`, whose through-hole `rect` pad `1` of size 2 mm × 2 mm at (0, 0) has `(drill 0.8 (offset 0 -0.4))`, placed at (10 mm, 10 mm), 0°, on the top
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_frame_pads.py -k offset` reads `board_pads(design)`
- **THEN** the pad has `position` (10 mm, 10 mm), the hole (10 mm, 10 mm) and `drill` 0.8 mm

### Requirement: Pad copper entries
`BoardPad.copper` SHALL hold, for each copper layer of `pad.layers` in that order, one or more `PadCopper` entries whose union is the pad's copper on that layer in the board frame, and SHALL be empty for a pad of kind `np_thru_hole`.
- Each entry MUST be built in the pad's own frame, moved there by the `(offset X Y)` of the pad's drill node when it has one, read from the pad's slots as `docs/formats/kicad/libraries.md` ("Drill forms") describes, and then moved by `Transform.placement(position, rotation)`, so the offset turns with the pad as its shape does. KiCad keeps the hole at the pad's position and moves the copper by the offset (`H-G-FRAME-OFFSET`). `BoardPad.position` stays the pad's position, which is where its hole is; every coordinate MUST be computed exactly and rounded half to even once, so it lies within 0.5 nm of the exact value and is exact at multiples of 90° when the pad's sizes are even. Rings MUST be stored in the normal form.
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

#### Scenario: Copper of a pad with an offset drill
- **GIVEN** the footprint `Frame_Offset` of "Pad holes", placed at (10 mm, 10 mm), 0°, on the top
- **WHEN** `board_pads(design)` is read
- **THEN** each copper entry of pad `1` is the filled box (9, 8.6)–(11, 10.6) in mm, that is the pad's box moved by (0, −0.4 mm), and the hole lies inside it

#### Scenario: The offset turns with the footprint
- **GIVEN** the same footprint placed at 90°
- **WHEN** `board_pads(design)` is read
- **THEN** the centre of the copper box is 0.4 mm from the hole, at the point that `Transform.placement(position, rotation)` gives for (0, −0.4 mm)
