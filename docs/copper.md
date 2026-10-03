# Board-frame queries and manual copper

Where is pad 2 of `U1` on the board, and how do I draw a track to it that still fits after the part
moves? This page describes the board-frame queries of the KiCad backend and the copper API built on
them. The normative text is in `openspec/specs/board-frame/spec.md` and
`openspec/specs/manual-copper/spec.md`; the KiCad facts are in `docs/formats/kicad/frame.md`. The
script side is in `docs/dsl.md` ("Copper"), and the runnable example is `examples/blink_routed/design.py`.

The board frame is the KiCad file frame: X to the right, Y down, integer nanometres, angles in
microdegrees in [0°, 360°).

## Records and `BoardFrame`

`fenolite.backends.base` defines three plain-data records, so `checks` and `placement` can read board
geometry without importing a backend:

| record | holds |
|---|---|
| `BoardPad` | one pad: `footprint_id`, `ref`, `path` (the component path, `""` without one), `pad_id`, `number`, `kind`, board-frame `position` and `rotation`, `side`, `layers` as stored, `net_id` and `net` (its name), `copper` (entries per copper layer), `hole` and `drill` |
| `PadCopper` | the copper of a pad on one copper layer: `layer`, `core`, `width`, `filled`, `exact` |
| `PlacedExtent` | the courtyard of a placed footprint: `front` and `back` rings, `source`, `exact`, and `own` (the face of its side) |

`BoardFrame` is the protocol with `board_pads(design)` and `placed_extents(design)`; `KicadBackend`
satisfies it. The functions themselves live in `fenolite.backends.kicad.frame`:

```python
from fenolite.backends.kicad import board_pads, find_pads, placed_extent

pads = find_pads(design, "U1", 2)  # every pad numbered 2 of U1, by component path or reference
pads[0].position, pads[0].rotation, pads[0].net
extent = placed_extent(footprint)  # front and back courtyard rings in the board frame
```

- `board_pads` gives one record per pad, footprints in board order and pads in footprint order.
- `find_pads(design, component, number)` matches a component path first and a reference when no path
  matches, takes an `int` number as its decimal text, and returns every pad that shares the number (an
  exposed pad split into several pads). It raises `KeyError` naming the component and its pad numbers.
- Positions are `at + R(θ)·stored`, with no further mirror on the bottom side, and the rotation is the
  stored absolute pad angle. These are the rules KiCad was checked against at 0°, 30°, 90°, 180° and 270°
  on both sides.
- Every function is pure: it reads no file and changes none of its arguments.

## Copper entries

An entry is the set of points within `width / 2` of an integer `core`:

| pad | core | `width` | `filled` |
|---|---|---|---|
| `circle`, or an `oval` with equal sizes | the centre | the diameter | no |
| `rect` | the four corners | 0 | yes |
| `oval` | the segment of length `\|w − h\|` along the longer side | the shorter side | no |
| `roundrect` | the inner box `(w − 2r) × (h − 2r)`, or its segment or point when a side is 0 | `2r` | yes for a box |
| `custom` | the anchor (`rect`, or `circle` by `options`) as above, then one entry per primitive with its stroke width | | |

`r` is `roundrect_rratio` times the shorter side, clamped to [0, 0.5] (0.25 when absent) and rounded half
to even, so the entry's outer box is exactly the pad's box. Circles, ovals and rounded rectangles are
therefore exact: no polygon stands in for a curve. Each coordinate is computed with rationals and
rounded half to even once, so it lies within 0.5 nm of the exact value and is exact at multiples of 90°
with even sizes. Filled rings are stored in the kernel's normal form.

A pad has entries for each copper layer of its `layers`, in that order, and none when it is an
`np_thru_hole`. A padstack gives `F.Cu` the pad's own shape and every other copper layer its named
entry, else `Inner` for an inner layer, else the pad's own shape.

`hole` is the drilled hole in the board frame: one point for a round drill, the two ends of the slot for
an oval one, with the drill `offset` applied; `drill` is its diameter (the shorter size of a slot).

`copper_polygon(entry)` gives a polygon on request: the ring itself for a filled entry of width 0, and an
outer polygon (vertices within `width / 2 + tol + 2` nm) for a disc, a segment or a convex ring with a
width. Other entries raise `ValueError`.

## Supersets

Where the public facts do not settle a shape, the entry contains the pad and is flagged `exact=False`,
with one info `kicad.frame.shape-approximated` per pad:

- a `trapezoid`: its box grown by `|dx| + |dy|` of `rect_delta` on every side;
- a chamfered pad: the same pad without chamfers;
- a custom `gr_arc`, an unfilled `gr_circle` and a `gr_poly` with arcs: polylines within the default
  tolerance, their width grown by `2·tol + 2`;
- a custom `gr_curve`: the convex hull of its control points;
- a filled `gr_circle` whose radius is not a whole number of nanometres: the radius rounded up;
- a padstack layer whose shape is `roundrect`, `custom` or `trapezoid`: the box of its size.

A consumer that must not miss a short treats an inexact entry as it is: larger than the pad.

## Placed extents and their fallbacks

`placed_extent(footprint)` reads the footprint's own courtyard graphics (`F.CrtYd` and `B.CrtYd`), so it
works for read and built boards, needs no library, and follows courtyard edits made in KiCad. Both faces
are returned, because KiCad checks front against front and back against back.

| courtyard | rings | `exact` |
|---|---|---|
| rectangle, polygon | its corners or points | yes |
| lines and arcs | chained into closed contours by exact endpoint equality | no when an arc is polygonised |
| circle | an outer polygon that contains the disc, up to `tol + 2` nm outside it | no |
| a face that does not close | the convex hull of its pieces, with the warning `kicad.frame.courtyard-malformed` | no |
| no courtyard at all | the hull of the pads' copper boxes on the footprint's side (`source="pads"`), or nothing (`source="none"`), with the info `kicad.frame.no-courtyard` | no |

An instance built in memory without KiCad children uses `definition=` (`source="definition"`), mirrored
for the bottom side. `placed_extents(design)` gives one extent per footprint in board order.

## The copper API

Copper is declared as intents and resolved after placement, because a script cannot know where a pad
ends up: the build places the parts, and a footprint moved in KiCad keeps its place.

```python
from fenolite.backends.kicad import resolve_copper

design = resolve_copper(design, intents, issues=found)
```

`resolve_copper(design, intents, *, unplaced=(), issues=None)` returns the design with the copper of the
intents. A build calls it for you (`build_design(…, copper_intents=…)`; `fenolite build` passes the
script's intents). Intents are read by attribute, so the DSL's dataclasses and any object with the same
attributes work: one with `path` is a track, one with `pitch` a stitch, any other a via.

- **Tracks.** A path holds pad ends, points and via steps. One track joins each pair of consecutive
  points on the current layer; a via step places a through via and changes the layer. Pad ends may stand
  anywhere, so one intent can chain several pads.
- **Which pad.** Among pads sharing a number, the first pad end takes the one nearest to the next
  element (or the nearest pair, when the next element is a pad end too), and every later one the pad
  nearest to the element before it. `index=` picks one outright. Only pads with copper on the segment's
  layer are candidates.
- **Nets.** A track takes the net of its pads. Pads on two nets, a pad on no net, or a named net that
  differs is `kicad.copper.net-conflict`: joining an unconnected pad would create a connection the
  circuit does not have. Vias, stitches and tracks without a pad end name their net.
- **Sizes.** The width and the via sizes come from the intent, else from the class of the net; when
  neither gives one, `kicad.copper.size-missing`.
- **Staged parts.** An intent that ends at a part the build left in the staging row creates nothing
  (`kicad.copper.end-unplaced`, a warning): copper drawn there would be wrong.
- An intent with an error creates nothing, and the other intents are still resolved. A build with a
  copper error writes no file.

Shorts and clearances between script copper and other copper are not judged here: that is the copper
check (change c0029) and KiCad's DRC. A track follows its pads wherever they go, so a moved footprint can
bring a track too close to something else; `fenolite check` tells you.

## Ids and markers

Every track and via gets the KiCad uuid `copper_uuid(key, locator)`: a version-8 UUID (RFC 9562) whose
first 48 bits are the bytes `fenoli`, so its text starts with `66656e6f-6c69-8`, and whose other bits are
a hash of the intent's key and the item's locator in it (`seg[i]`, `via[i]`, `via`, `via[k]`,
`via[i,j]`). The Fenolite id derives from that uuid, as for any imported object.

- The same key and locator give the same ids in every build: the seed and `PYTHONHASHSEED` play no part,
  and changing one intent never changes the ids of another.
- The marker is how a rebuild tells script copper from copper drawn in KiCad, which gets version-4
  uuids. No registry is kept.
- `kicad-cli` 9.0.9 and 10.0.6 load these uuids, and a 10.0.6 re-save keeps them.

## The merge with an existing board

The script owns its copper. `merge_copper(existing, built)` decides what stays of the existing copper:

| existing item | outcome |
|---|---|
| a copper uuid that the build creates again | replaced by the new copy; `kicad.copper.regenerated` (info) when a field differs, because it was edited in KiCad or its pads moved |
| a copper uuid whose intent is gone | removed; `kicad.copper.stale` (warning) |
| no copper uuid, but equal to a script item | removed; `kicad.copper.duplicate` (info) |
| anything else | kept, and it then follows its net as any board copper does |

So a footprint moved in KiCad pulls its tracks along on the next build, removing an intent removes its
copper, and copper drawn in KiCad stays. To keep a hand-edited version of a script track, remove the
intent and redraw the track in KiCad, where it is board copper. Resolving twice changes nothing.

## Stitching rules

A stitch places through vias of one net, along a polyline or on a grid in a region.

- **Along a polyline:** each segment is cut into the fewest equal parts no longer than `pitch`; every
  vertex gets one via.
- **In a region:** the candidates are `origin + (i·pitch, j·pitch)` inside the region, at least
  `diameter / 2 + margin` from every edge. The grid is global, so a region that grows keeps the vias, and
  the ids, it already had.
- **Clearance:** a candidate is dropped when it comes closer than `clearance` to the copper or the hole
  of any pad, or to a track, arc or via of another net or of no net, or when it touches a via of its own
  net (existing vias, those of earlier intents and those already kept). Distances are decided exactly
  with integers. Tracks of its own net are no obstacle.
- Dropped candidates give one `kicad.copper.stitch-skipped` info with their count; a stitch that keeps
  none gives the warning `kicad.copper.stitch-empty`.
- Zones, rule areas and the board edge are not avoided in v0.1.

KiCad reports a through via that touches copper on one layer only as `via_dangling` (a warning): a fence
of vias along a track on one layer gets it until a zone or a second track reaches them.

## Issue codes

| code | severity | when |
|---|---|---|
| `kicad.frame.courtyard-malformed` | warning | a courtyard face does not close; its convex hull is used |
| `kicad.frame.no-courtyard` | info | a footprint has no courtyard; its pads' hull, or nothing, is used |
| `kicad.frame.shape-approximated` | info | a pad's copper entries are a conservative superset |
| `kicad.copper.bad-intent` | error | a path, region, pitch, margin or key is malformed, or a key repeats |
| `kicad.copper.pad-not-found` | error | no footprint, no pad with the number, or an index beyond the matches |
| `kicad.copper.layer-mismatch` | error | no pad of a pad end has copper on the segment's layer |
| `kicad.copper.bad-layer` | error | a layer is not a copper layer of the board, or a via step keeps the layer |
| `kicad.copper.net-conflict` | error | pad ends on two nets or without a net, or a named net that differs from theirs |
| `kicad.copper.unknown-net` | error | a named net is not a net of the design |
| `kicad.copper.no-net` | error | a via, a stitch or a track without a pad end names no net |
| `kicad.copper.size-missing` | error | a width, via size or clearance is neither given nor set by the net's class |
| `kicad.copper.bad-size` | error | a size is not positive, or a drill is not smaller than its diameter |
| `kicad.copper.stale` | warning | script copper of an earlier build has no intent any more and is removed |
| `kicad.copper.end-unplaced` | warning | an intent ends at a staged part and creates nothing |
| `kicad.copper.stitch-empty` | warning | a stitch keeps no candidate |
| `kicad.copper.regenerated` | info | script copper differs from its regenerated copy and is replaced |
| `kicad.copper.duplicate` | info | an item equal to script copper is removed |
| `kicad.copper.stitch-skipped` | info | stitch candidates are dropped for clearance (with the count) |

## Evidence

Measured on `kicad-cli` 9.0.9 and 10.0.6 on 2026-10-03 (`docs/evidence/kicad-frame.md`; hypotheses in
`docs/hypotheses.md`):

| what | how it was checked | rows |
|---|---|---|
| pad positions and rotations | `pcb export ipcd356` of a bench of 85 placements at 0°, 90°, 180°, 270° and 30° on both sides | `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-PAD-ANGLE-ABS` |
| copper entries of circle, rect, oval, roundrect and filled-polygon custom pads | 100 probe vias 20 µm inside the 0.2 mm clearance each give one violation; 100 probes 20 µm outside give none | `H-G-FRAME-SHAPE` |
| placed extents | pairs of courtyards overlapping by 20 µm (40 µm for circles) give one `courtyards_overlap`; pairs 20 µm apart give none | `H-G-FRAME-CRTYD`, `H-G-FRAME-CRTYD-2` |
| copper uuids | boards load on both majors; a 10.0.6 re-save keeps every uuid | `H-G-FRAME-UUID` |
| routed blink | no unconnected item and no clearance or short on script copper; one unconnected item with a segment cut; none after a footprint moved and the build ran again | `H-G-FRAME-ROUTE` |

These rows cover the bench footprints and the routed blink, not every pad token or design, so
`frame.EVIDENCE` and `copper.EVIDENCE` stay `INFERRED`, and a build with copper intents carries that
level. The routed example creates 11 tracks and 7 vias from 4 intents.
