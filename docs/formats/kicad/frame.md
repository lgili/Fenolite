# Board-frame geometry of KiCad pads and courtyards

`fenolite.backends.kicad.frame` gives the pads and the courtyard of a placed footprint in the board
frame: X to the right, Y down, integer nanometres, angles in microdegrees. This page lists the KiCad
facts those rules rely on, in Fenolite's own words. Sources are listed in `docs/evidence/sources.md`.
The frame, rotation and placement conventions themselves are the rows "Rotation direction",
"Bottom-side placement" and the IPC-D-356 frame of `docs/formats/kicad/geometry.md`, and "Pad frame" of
`docs/formats/kicad/board.md`; this page does not repeat them. The user guide is `docs/copper.md`.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| A pad's shape is `circle`, `rect`, `oval`, `trapezoid`, `roundrect` or `custom` | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| The copper of a `circle` pad is the disc whose diameter is the X value of `size`; the page does not state it | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| The copper of an `oval` pad is the stadium of its `size`: the segment of length `\|w − h\|` along the longer side, widened by the shorter side | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| `roundrect_rratio` is a scaling factor of the pad between 0 and 1 that gives the corner radius. Fenolite scales the shorter side by it, clamps it to [0, 0.5] and takes 0.25 when it is absent; the page states none of the three | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| A `custom` pad has an anchor pad of the pad's size, `rect` or `circle` by `(options (anchor …))`, and `primitives`: graphic items with a `width` and an optional fill. Fenolite takes `rect` when the anchor is absent, and counts a `gr_poly` without `fill` as filled; the page states neither | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| `chamfer_ratio` is a scaling factor of the pad between 0 and 1 that gives the chamfer size, and `chamfer` lists the chamfered corners (`top_left`, `top_right`, `bottom_left`, `bottom_right`) | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| A `trapezoid` pad carries `rect_delta`; the page does not describe it. Fenolite uses a box that contains the pad under either reading of the delta | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| A drill is `(drill [oval] DIAMETER [WIDTH] [(offset X Y)])`: the offset is given from the pad centre, and an oval drill has two sizes | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| An oval drill is the slot along the longer of its two sizes, as wide as the shorter one, in the pad's frame; the page does not state its orientation | S-0001 | INFERRED | H-G-FRAME-SHAPE |
| The courtyard of a footprint is the set of its graphic items on `F.CrtYd` and `B.CrtYd` (shown as `F.Courtyard` and `B.Courtyard`); the manual names them as required layers and says nothing more about them | S-0038 | INFERRED | H-G-FRAME-CRTYD-2 |
| KiCad's DRC checks front courtyards against front ones and back against back, and reports an overlap under the rule-severity key `courtyards_overlap` | S-0038, S-0058 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-FRAME-CRTYD-2 |
| The graphic items of a placed footprint, courtyard included, are stored like its pads: already rotated into the board's orientation relative to the footprint position on a read board, and already mirrored on the bottom side | S-0019, S-0040 | INFERRED | H-G-FRAME-CRTYD-2 |
| An `fp_poly` may hold arcs in its `pts` | S-0018 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-PTS-ARC |
| The copper of the bench pads (one `circle`, `rect`, `oval`, `roundrect` and filled-polygon `custom` pad, at 0°, 90°, 180°, 270° and 30° on both sides) agrees with KiCad's clearance check within 20 µm | S-0020, S-0038 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-FRAME-SHAPE |
| KiCad reports two circle courtyards only once they overlap by more than about 10 µm (radius 2 mm: none at 10 µm, one at 15 µm, on 10.0.6); rectangle and line-loop courtyards are reported at 20 µm | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-FRAME-CRTYD-2 |
| A UUID of version 8 has 48 custom bits, the version `0b1000`, 12 custom bits, the variant `0b10` and 62 custom bits; only the version and variant are fixed | S-0110 | INFERRED | H-G-FRAME-UUID |
| `kicad-cli` 9.0.9 and 10.0.6 load tracks and vias whose `uuid` is a version-8 UUID, and a 10.0.6 re-save (`pcb upgrade --force`) keeps those uuids | S-0110, S-0020, S-0022 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-FRAME-UUID |
| Python 3.11 to 3.13 refuse `version=8` in `uuid.UUID`; versions 6 to 8 and `uuid8()` come with 3.14, so Fenolite sets the bits on the integer | S-0111 | INFERRED | H-G-FRAME-UUID |
| Copper that joins the pads of a net leaves no entry for that net in `unconnected_items` of the DRC report | S-0022, S-0037 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-G-FRAME-ROUTE |

## Fenolite choices

These are decisions of the code, not facts about KiCad.

- A copper entry is the set of points within `width / 2` of an integer core: a point (a disc), an open
  polyline, or a filled ring. A circle, an oval and a rounded rectangle are therefore exact, with no
  polygon approximation.
- A shape Fenolite cannot state exactly from the facts above (a trapezoid, a chamfered pad, a curved
  custom primitive, a padstack layer with an unknown corner ratio) becomes a superset, flagged
  `exact=False` with the info `kicad.frame.shape-approximated`.
- A courtyard that does not close becomes the convex hull of its pieces, with a warning. KiCad has a
  check of its own for malformed courtyards; Fenolite does not claim to match it.
- Script copper gets version-8 uuids with the marker `66656e6f-6c69` in the first 48 bits, so a rebuild
  can tell it from copper drawn in KiCad.
