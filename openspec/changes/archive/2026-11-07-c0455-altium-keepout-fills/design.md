# Design: c0455

## Marker

A keep-out stroke of copper already travels through KiCad in its rule area's name (change c0450,
`keepout_lines`). A keep-out fill uses the same prefix and flag:

    Altium.KeepOut/flag<r>/fill/<x1>/<y1>/<x2>/<y2>/<x3>/<y3>/<x4>/<y4>

The numbers are the four corners in nanometres, in the frame of the rule area (a footprint's pad frame for
its own areas), in the order of the area's outline. Putting the corners in the name tells an edited
outline apart from the fill's own, as the band does for a stroke, and keeps two fills of one footprint
distinct. `parse` returns `("fill", corners, 0, False)` for such a name, so `flag`, `flags`, `intact` and
`strokes` handle a fill as one more kind: its band is its corners, and `strokes` gives a filled polygon of
the area's layer.

An area is still its fill's (`intact`) when it has one layer, forbids what r forbids and no more (as for a
stroke), its outline is the four corners within `TOLERANCE` (10 nm), and those corners make a rectangle
within that tolerance (opposite corners share a centre, adjacent edges are square). An area edited since
stays an area.

## Import

The adapter may not import `keepout_lines`, so it records the fill raw in the area's bag under the key
`stroke` of change c0450: `fill/<corners>/<r>`. The key names the primitive the area was read from; a
stroke value carries a width before r, a fill value none. `convert.altium_to_kicad.stroke_names` builds the
marker from it and keeps it when `intact`. Fills of library footprints (`PcbLib`) are not marked.

## Writer

`pcbrecords.fill_record` takes `keepout`, the restriction byte: the second flag byte becomes 2 and byte 46
holds r, the form of the 11 keep-out fills of row `-08` (S-2091). A fill of a component goes through
`lower._keepout_strokes` as a `ComponentGraphic` with `keepout`, a free one through `PcbDocSpec.keepout_strokes`
as a stroke does. When `fill_geometry` finds no rectangle (not expected after `intact`), the writer writes a
keep-out region with r, as before this change.

## Counts

A written keep-out fill counts under `keep-out` as a written area, as a stroke does (`_count_strokes`).
