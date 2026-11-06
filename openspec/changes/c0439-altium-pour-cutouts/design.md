# Design: c0439

## Where the keep-outs came from

`adapter.copper` makes a rule area of `no_copper_pour` alone from a region of `KIND=1` on a copper layer, or
on every copper layer from the Keep-Out (56) or Multi-Layer (74) layer. KiCad keeps it as a zone rule area
that forbids pours. `pcbdoc.free_records` and `pcblib.keepout_records` wrote every rule area as keep-out
regions (`rec.region_record(keepout=value)`), so the cut-out came back as a keep-out with the value 4.

## The fix

`pcblib.is_pour_cutout(area)`: the restrictions value is the copper bit alone and `no_footprints` is false.
Such an area is written with `rec.region_record(..., polygon_cutout=True)`: `KIND=1`, flag byte 0, no
restriction keys. Layers: Multi-Layer when it lies on every copper layer of the board (or on `*.Cu` in a
footprint), else each copper layer. The reader takes both back to the same rule area.

## Evidence

Census of the public corpus on 2026-11-06 (counts only; S-0188, S-0176, S-0175), regions of `KIND=1`: row `-01` one on Top and one on
Bottom, `-02` six on Top and ten on Bottom, `-06` eight on Top, two on Bottom and three on Multi-Layer with
`V7_LAYER=MULTILAYER`; none belongs to a component. None of them has the keep-out flag.
