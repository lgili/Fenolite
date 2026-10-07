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
an oval one, centred on the pad's `position`; `drill` is its diameter (the shorter size of a slot). The
`(offset X Y)` of a pad's drill does not move the hole: as in KiCad, it moves the pad's copper, so every
entry of `copper` is built around `position` plus the offset turned with the pad. v0.1 moved the hole
instead, and `check` reported clearance errors on such pads that KiCad's DRC does not report.

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

- **Tracks.** A path holds pad ends, points, arc steps and via steps. One track joins each pair of
  consecutive points on the current layer; a via step places a via and changes the layer. Pad ends may
  stand anywhere, so one intent can chain several pads. An element with `offset` is an anchor (below),
  another with `component` is a pad end, one with `mid` an arc step, any other that is not a point a
  via step.
- **Arcs.** An arc step `(mid, end)` replaces the segment that would end at it by one arc from the point
  before it through `mid` to `end`, on the current layer, with the width and the net of the intent. Its
  three points must be distinct and must not lie on one line, which is decided exactly with integers;
  otherwise the intent is `kicad.copper.bad-intent`. The copper check and the stitch clearance treat a
  script arc as any arc: within a band of about 1 µm.
- **Via kinds.** A via step or a via intent has a `kind`: `through` (also when it has none), `blind`,
  `buried` or `micro`. A through via spans the first and the last copper layer. Any other kind holds
  its two layers in stack order, and they must fit it, else `kicad.copper.bad-layer`:

  | kind | its two layers |
  |---|---|
  | `blind` | exactly one is the first or the last copper layer |
  | `buried` | neither is |
  | `micro` | exactly one is, and the two are next to each other in the stack |

  A via step takes the layer the track is on and the layer it changes to; a single via names its
  two layers in `layers`. `resolve_copper` knows no target: the board writer refuses a `buried` via
  for KiCad 9, so that build exits 7. Stitching vias are through vias.
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

### Anchors: points in a part's frame

Wherever an intent holds a point it may hold an anchor instead: a path element, the `at` of a via step
or of a via, `mid` and `end` of an arc step, and the `along` points, the `region` points and the `origin`
of a stitch. An anchor is any object with `component`, `number`, `index` and `offset` (the protocol
`AnchorLike`; the DSL's `Anchor`, made by `part.at(…)` and `part.pad(…).at(…)`).

```python
from fenolite.backends.kicad import part_frame

frame = part_frame(design, "U1", number="9")  # or part_frame(design, "U1") for the footprint's origin
point = frame.point(Point(0, 1_000_000))  # 1 mm below pad 9, as the library draws the footprint
```

- **The map.** `offset` is measured in the footprint as its library file draws it (X to the right, Y
  down), from the footprint's origin, or from the position of the pads that `number` and `index` name.
  The board point is `at + R(θ)·S·(base + offset)`: turned with the footprint, mirrored about the
  footprint's X axis on the bottom side (`S`), rounded half to even once. Pads follow the same map, so
  `part_frame(design, c, number=n).point()` is exactly the position of that pad's record, and an
  anchor keeps its place among the pads under any rotation and on either side.
- **When it is applied.** `resolve_copper` replaces every anchor by its point first, on the design it
  is given. A build gives it the design at its effective placements, so anchored copper follows a
  part that was moved in KiCad or by `fenolite place` at the next build. Its locators and uuids are
  those of the elements the anchors stand for, so the moved items are regenerated in place
  (`kicad.copper.regenerated`). `part_frame` gives the same points to a script on a model design.
- **An anchor never joins a pad.** It is a point: it gives no net and takes none. A track's net still
  comes from its pad ends, and a via or a stitch names its net. A track from `PadEnd("R1", "2")` to an
  anchor beside that pad is on the pad's net because of the pad end, not because of the anchor.
- **A pad anchor names one position.** With `index`, the pad at that place among the pads of its
  number. Without it, every pad of the number must lie at one position, as the front and back pads
  of one padstack do.
- **What cannot be resolved** creates nothing, with the codes of the table below:
  `kicad.copper.pad-not-found` (no footprint of the component, no pad with the number, or an index
  beyond them), `kicad.copper.bad-intent` (the pads of the number lie at several positions and no
  index is given) and `kicad.copper.end-unplaced` (the part is in the staging row). Each issue names
  the intent's key, the component and the pad number.
- **An anchor in the wrong pad.** KiCad gives a via whose copper touches a pad of another net the net
  of that pad when it loads the board, and its DRC reports no `shorting_items` for it
  (`H-K-VIA-RENET`). So a via of the wrong net anchored inside a pad passes KiCad's DRC. The copper
  guard of `build` reports it as `copper.short` and refuses the build by default; with
  `--copper-check warn` that warning is the only report you get.

Shorts and clearances between script copper and other copper are not judged here: that is the copper
check (change c0029) and KiCad's DRC. A track follows its pads wherever they go, so a moved footprint can
bring a track too close to something else; `fenolite check` tells you.

## Ids and markers

Every track, arc and via gets the KiCad uuid `copper_uuid(key, locator)`: a version-8 UUID (RFC 9562)
whose first 48 bits are the bytes `fenoli`, so its text starts with `66656e6f-6c69-8`, and whose other
bits are a hash of the intent's key and the item's locator in it (`seg[i]` for the segment that leaves
path element `i`, `arc[i]` for the arc of the arc step at element `i`, `via[i]`, `via`, `via[k]`,
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
| a copper uuid that the build creates again (a track, an arc or a via) | replaced by the new copy; `kicad.copper.regenerated` (info) when a field differs, because it was edited in KiCad or its pads moved |
| a copper uuid whose intent is gone | removed; `kicad.copper.stale` (warning) |
| no copper uuid, but equal to a script item (an arc: the same ends in either order and the same mid point) | removed; `kicad.copper.duplicate` (info) |
| anything else | kept, and it then follows its net as any board copper does |

**Locks (change c0108).** An intent with `locked=True` gives each track, arc and via it creates
`locked=True`, written as `(locked yes)`; an intent without the attribute is unlocked. The lock is one of
the fields the merge compares, so script copper whose lock was changed in KiCad is regenerated with one
`kicad.copper.regenerated` info. It is not part of what makes two items the same copper: a locked copy of
a script track is still a duplicate. This is the copper lock of a track or a via, not the placement lock
of a part (`Part.place(..., locked=True)`), which is written on the footprint. `fenolite route --rip`
keeps script copper whether it is locked or not (`docs/routing.md`).

A via's protection (`Via.protection`) is one of the compared fields (change c0112): every via an intent
creates carries the `protection` of its via step, via intent or stitch intent (read by attribute, like
`kind`; an intent without it gives `ViaProtection()`, and a value that is not a `ViaProtection` gives
`kicad.copper.bad-intent`), so a protection set in KiCad on a script via is regenerated. A duplicate is
still judged without it. The board default is not copied into script vias: a field of `None` follows
`Board.via_protection`.

So a footprint moved in KiCad pulls its tracks along on the next build, removing an intent removes its
copper, and copper drawn in KiCad stays. To keep a hand-edited version of a script track, remove the
intent and redraw the track in KiCad, where it is board copper. Resolving twice changes nothing.

## Stitching rules

A stitch places through vias of one net, along a polyline, on a grid in a region, or on a grid inside
a pad of its net.

- **Along a polyline:** each segment is cut into the fewest equal parts no longer than `pitch`; every
  vertex gets one via.
- **In a region:** the candidates are `origin + (i·pitch, j·pitch)` inside the region, at least
  `diameter / 2 + margin` from every edge. The grid is global, so a region that grows keeps the vias, and
  the ids, it already had.
- **A grid in a part's frame:** when `origin` is an anchor, the grid point `(i, j)` is
  `part_frame(…).point(offset + (i·pitch, j·pitch))`: the grid turns with the anchor's part and is
  mirrored with its bottom side. The locators `via[i,j]` count in that frame, so a part that moves
  keeps the ids of its vias. At most `(2⌈R / pitch⌉ + 3)²` grid points are tried, `R` the distance from
  the grid's start to the farthest point of the region.
- **In a pad (a thermal array):** `region` is a pad reference (`component`, `number`, `index`) in
  place of a ring. It names its pads as an anchor at offset (0, 0) does: one pad with `index`, else
  every pad of the number, which must lie at one position. Each must be on the stitch's net
  (`kicad.copper.net-conflict`), and one must have copper on the outer layer of the part's side, `F.Cu`
  on the top and `B.Cu` on the bottom (`kicad.copper.layer-mismatch`). The grid starts at the pad's
  position in the part's frame, unless `origin` is an anchor, whose grid is then used. A grid point is
  a candidate when the via disc grown by `margin` lies inside one copper entry of the pad on that
  layer, decided exactly on the entry's core and width. A pad whose entries are a superset
  (`kicad.frame.shape-approximated`) is judged on that superset: give such a pad a larger margin.
- **Clearance:** a candidate is dropped when it comes closer than `clearance` to the copper or the hole
  of any pad, or to a track, arc or via of another net or of no net, or when it touches a via of its own
  net (existing vias, those of earlier intents and those already kept). Distances are decided exactly
  with integers. Tracks of its own net are no obstacle. The copper of the pads that a pad region names
  is no obstacle to that region's candidates; their holes, every other pad, also one of the same net,
  and the vias of its own net still are.
- Dropped candidates give one `kicad.copper.stitch-skipped` info with their count; a stitch that keeps
  none gives the warning `kicad.copper.stitch-empty`.
- A candidate is also dropped when its via disc meets a rule area that forbids vias on a copper layer
  (a through via crosses every copper layer), when it comes closer to the board edge than the edge
  clearance, or when it lies off the board: outside the outline or inside a cut-out. The edge
  clearance is the `min` of the governing board-wide `edge_clearance` rule, else the project's
  `min_copper_edge_clearance`. On a rebuild the rule areas and the edge of the existing board count.
  Without a closed outline the edge is not checked. These candidates join the count of
  `kicad.copper.stitch-skipped`. A pad region obeys this rule as any other stitch: a thermal array
  under a rule area that forbids vias loses the candidates the area covers.
- Zones are not avoided: a stitch is usually meant to tie zones together.

KiCad reports a through via that touches copper on one layer only as `via_dangling` (a warning): a fence
of vias along a track on one layer gets it until a zone or a second track reaches them. The same holds
for a thermal array: its vias touch their pad on one outer layer, so each is `via_dangling` until copper
of the net reaches it on another layer, a track or a plane. A plane counts once it is filled
(`fenolite fill`). With such copper KiCad's DRC reports nothing for through vias of the pad's net inside
an SMD pad (`H-K-VIA-IN-PAD`). Vias in an SMD pad draw solder away from the joint unless they are
tented, plugged or filled: stating that protection is change c0112, not part of the stitch.

## Issue codes

| code | severity | when |
|---|---|---|
| `kicad.frame.courtyard-malformed` | warning | a courtyard face does not close; its convex hull is used |
| `kicad.frame.no-courtyard` | info | a footprint has no courtyard; its pads' hull, or nothing, is used |
| `kicad.frame.shape-approximated` | info | a pad's copper entries are a conservative superset |
| `kicad.copper.bad-intent` | error | a path, region, pitch, margin, key or via kind is malformed, a key repeats, or the three points of an arc are not distinct or lie on one line |
| `kicad.copper.pad-not-found` | error | no footprint, no pad with the number, or an index beyond the matches |
| `kicad.copper.layer-mismatch` | error | no pad of a pad end has copper on the segment's layer |
| `kicad.copper.bad-layer` | error | a layer is not a copper layer of the board, a via step keeps the layer, or the layers of a via do not fit its kind |
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
| `kicad.copper.stitch-skipped` | info | stitch candidates are dropped for clearance, a rule area that forbids vias or the board edge (with the count) |

Anchors and pad regions add no code. They use five rows of the table, each with its severity:

| code | for an anchor | for a pad region |
|---|---|---|
| `kicad.copper.pad-not-found` | no footprint of the component, no pad with the number, or an index beyond the pads of the number | the same |
| `kicad.copper.bad-intent` | the pads of the number lie at more than one position and no index is given | the same; also a `region` that is an anchor |
| `kicad.copper.end-unplaced` | the part is in the staging row | the same |
| `kicad.copper.net-conflict` | (an anchor has no net) | a pad of the region is on another net than the stitch, or on none |
| `kicad.copper.layer-mismatch` | (an anchor has no layer) | no pad of the region has copper on the outer layer of the part's side |

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

Anchors and thermal arrays (change c0111) were measured on `kicad-cli` 10.0.6 on 2026-10-07 with the
benches of `tests/kicad/frame/_anchorbench.py`; the same probes on 9.0.9 wait for the `kicad-9` job, so
both rows are `INFERRED` until then:

| what | how it was checked | rows |
|---|---|---|
| where an anchored point lands | 36 vias of a marker net anchored inside pads of `Frame_Anchor` at 0° and 90° on the top and at 30° on the bottom: KiCad names each with the net of the pad its anchor names, and reports no short for one. Control: two points computed without the mirror land in each other's pad | `H-G-FRAME-ANCHOR` |
| anchored copper after `fenolite place --move` | a thermal array and its track, rebuilt after the part was moved and turned: 17 items regenerated, none dangling or unconnected. Control: the same copper given as board points stays behind, 9 `via_dangling` | `H-G-FRAME-ANCHOR` |
| a thermal array in an SMD pad | 9 through vias of the pad's net in a 3 mm × 3 mm pad: nothing in the DRC report with a track of the net through them on the other outer layer, one `via_dangling` each without it | `H-K-VIA-IN-PAD` |
