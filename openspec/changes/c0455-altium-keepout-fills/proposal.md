# c0455: Keep-out fills of an Altium board survive the trip through KiCad

## Why

A keep-out fill of copper (a fill record with the second flag byte 2) becomes a KiCad rule area of its
outline (change c0407). The fill tag of change c0450 marks a graphic's uuid, and a rule area is no graphic,
so the conversion back writes the area as a keep-out region. Row `-08` holds 11 keep-out fills of components
on its bottom layer (restriction byte 24 on 10, 0 on 1; S-2091); its round trip gives 11 keep-out regions
and no keep-out fill (S-2140). A rule scoped to fills no longer selects them, and the document holds
another primitive kind than the source.

## What

- The import records a keep-out fill of copper in its rule area's bag as it records a keep-out stroke
  (key `stroke`, change c0450): `fill/<x1>/<y1>/…/<x4>/<y4>/<r>`, its four corners in the area's frame and
  its restriction byte.
- A conversion to KiCad names that area `Altium.KeepOut/flag<r>/fill/<x1>/<y1>/…/<x4>/<y4>` when the area
  is still the fill's: one layer, what r forbids, the four corners as its outline.
- The Altium writer writes an area so named that is still its fill's, a rectangle, as a keep-out fill
  record of the 50-byte form on that layer: the keep-out flag and r at 46, free or of its component. Any
  other area stays a keep-out region.

## Impact

- Specs: `altium-pcb-writer` (keep-out fills of a converted board), `design-conversion` (a keep-out fill
  names its rule area).
- Code: `backends/altium/keepout_lines.py`, `backends/altium/adapter/copper.py`,
  `backends/altium/pcbrecords.py`, `backends/altium/pcbdoc.py`, `convert/altium_to_kicad.py`.
- Docs: `pcb-records.md`, `import.md`, `docs/evidence/sources.md` (S-2140), CHANGELOG.
- Footprint libraries (`PcbLib`) are not in scope: their keep-out fills still give rule areas.
