# Design: c0452

## Decision 1: twins before the change

`ops.move` of a region takes `_twins(state, raw)` before `state.replace`. `_twins` looked the region up by its
bytes in `Regions6`; after the replace no record held those bytes and the unpacking of one match raised.

## Decision 2: the nearest record within reach

`View.find` keeps every record whose stated coordinates lie within `REACH`, 0.002 mm (787 units), and takes
the nearest. The distance of a record is the largest difference of a stated coordinate (a track's two ends
in either order, an arc's centre and radius, a fill's two corners, a region's corner). A second record
whose distance is within `TOLERANCE` (2 units) of the nearest one's is a second match and refuses, as
before. So:

- a point rounded to the micrometre, as `fenolite inspect` and the kit's `expected.md` show it, names the
  record it was read from: the rounding is at most 0.0005 mm;
- of two tracks less than 0.002 mm apart, the stated ends name the nearer one;
- two coincident tracks are told apart by `width` (matched within `TOLERANCE`), or refused.

`_twins` takes, for each region, the nearest record of `ShapeBasedRegions6` of the same layer, polygon,
component and property text whose box lies within `REACH`, in place of an equal rounded box.

## Decision 3: arcs and fills

`Arc(centre, radius, net, layer=None, width=None)` and `Fill(corner, opposite, layer, net=None)` (corners in
either order) are found like a track. `move` shifts them with `records.transform` (already written for
both kinds, for a component's primitives); `delete` removes the record. `check_expect` takes `width` of an
arc and `rotation` of a fill.

## Decision 4: polygons

A polygon's outline is its keys `KIND<n>`, `VX<n>`, `VY<n>`, `CX<n>`, `CY<n>`, `SA<n>`, `EA<n>` and `R<n>`
in `Polygons6`, the first vertex repeated last (`docboard._outline`).

- `move(Polygon(name), dx, dy)` shifts every `VX`, `VY`, `CX` and `CY` value and moves each primitive whose
  prefix names the polygon (poured regions in both forms, tracks and arcs of a hatch).
- `set_outline(Polygon(name), outline, old=...)` states the old outline (its vertices, without the repeated
  one, each within `REACH`), writes the new one as line vertices in the place of the old keys, and removes
  the poured primitives: their copper no longer follows the outline.
- `add_polygon(name, outline, layer=, net=)` clones the first record of `Polygons6` (its keys are the same
  on every layer, which the `LAYER` key names) with a new `NAME`, `LAYER`, `NET`, `POURINDEX` one above the
  highest, a new `UNIQUEID` where the template holds one, and the outline; it pours nothing.

## Decision 5: new records

`create` clones a record of the same kind and layer that the document holds, as `clone` does
(`H-A-EDIT-CLONE`), and refuses with `altium.edit.no-template` when there is none:

- `add_arc(centre, radius, start, end, width=, layer=, net=None)`: centre, radius, the two angles and the
  width at the reader's offsets; no polygon, component or sub-polygon.
- `add_fill(corner, opposite, layer=, net=None, rotation=0)`: the two corners, lower-left first, and the
  rotation. The bytes after 37 are the template's: no row records what they hold.
- `add_region(outline, layer=, net=None)`: the template's head (prefix and property text) with no hole,
  the new outline, and the template's tail; in `Regions6` as doubles and, when the template has a twin, in
  `ShapeBasedRegions6` as 37-byte vertices with the closing vertex, as `pcbrecords.region_record` writes them.
  `SUBPOLYINDEX` and `UNIONINDEX` are the template's (a free region's).

## Decision 6: gates and rows

`OPERATIONS` gains `create` (rows `H-A-EDIT-CREATE`, `H-A-EDIT-IDS`, `H-A-EDIT-KIT`) and `set_outline`
(`H-A-EDIT-SHAPE`, `H-A-EDIT-KIT`); `move` and `delete` add `H-A-EDIT-SHAPE`. Both new gates are off. Case
J23 of Part J names both rows, and phase B writes `shapes`, `create` and `set_outline` from
`J01-resave.PcbDoc`; the fill, which the kit board does not hold, is proven on a document that Altium
Designer saved with one (S-2111 onward, through the agent session of the maintainer's VM).
