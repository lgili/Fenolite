# c0466: Altium internal planes through KiCad and back

## Why

An Altium document's internal planes do not survive a conversion to KiCad and back (S-2251):
- **The way to KiCad.** The conversion writes each internal plane (ids 39 to 54) as a `signal` row,
  `(4 "In1.Cu" signal)`. Only change c0461's `plane` loss records the plane, and nothing records its net,
  its name, its pull-back or its split polygons.
- **The way back.** `lower._stack` writes an internal plane only from an Altium import's `plane_net` layer
  pair. KiCad's `power` row maps to no plane, so public row `-01` comes back as Top Layer, Mid-Layer 1,
  Mid-Layer 2 and Bottom Layer instead of Component Side, Ground Plane, Power Plane and Solder Side. Row
  `-02` loses its planes on `GND` and `5V` the same way.
- **Rules.** The carried Width record now limits the ex-planes: the read-back holds two per-layer
  `track_width` rules, `Width/In1.Cu` and `Width/In2.Cu`, that the source does not hold.

Both public rows with planes hold Split Plane polygons (S-2250):
- Row `-01`: both planes are `(Multiple Nets)`, with 2 and 6 split polygons.
- Row `-02`: the planes are on `GND` and `5V`, with 1 and 4 split polygons.

The current writer writes one outline polygon per plane on the plane's net. It writes no split of another
net and no `(Multiple Nets)` plane.

## What

- **To KiCad.** Each internal plane of the copper chain becomes a KiCad row of type `power`. Its user name
  is the plane's Altium name, as KiCad's own import makes it (S-2201). The conversion carries each plane in
  the board property `Fenolite.Altium.Planes`: its row, its net, its pull-back, its split polygons (each a
  net and a straight ring) and the board's corner.
- **Back to Altium.** A row the carrier names that is still `power` is written as an internal plane again,
  with:
  - its carried net (a net name or `(Multiple Nets)`);
  - its pull-back;
  - the row's user name as its name;
  - its split polygons, moved with the board.

  A carried plane whose row is gone or no longer `power`, or one of whose nets the design no longer holds,
  is not restored. It is counted lost under `plane`.
- **Writer.** `PcbDocSpec` takes plane splits and plane names, and `StackSpec` takes per-plane pull-backs.
  A plane with splits is written with them instead of the outline polygon, and a `(Multiple Nets)` plane is
  allowed when it has splits.
- **Rules.** The read-back of the round trip holds the source's rules and no new per-layer rule.

## Out of scope

- The plane's copper in KiCad. KiCad's own import makes each split an unfilled zone; Fenolite gives KiCad
  no zone, so c0461's `plane` loss on the way to KiCad stands.
- A split polygon with an arc vertex. Its plane is not carried; none exists in the public rows.
- The legacy `PLANE<k>PULLBACK` keys, which the writer writes for no plane today.
- The names of signal copper layers (`Component Side`).
- A `(Multiple Nets)` plane on the direct path (import to Python, build, convert), which writes no split
  either.
