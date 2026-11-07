# c0442: Altium keep-out lines come back as lines

## Why

Older Altium boards draw a keep-out as plain tracks and arcs on the Keep-Out layer, without the keep-out
flag (`pcb-records.md`, "Regions and keep-outs"). A conversion to KiCad gives each stroke the rule area of
the band its width covers (c0407, c0410). Written back to Altium, that area became a flagged region of the
Keep-Out layer: another primitive kind. A design rule whose scope selects regions then checks every
written region, where the source had only tracks and arcs. On the public row `-01` (BMS), the round trip
wrote 20 such regions in place of 12 tracks and 8 arcs (S-2010). On the maintainer's board the same change
of form gave a flood of clearance violations against the keep-outs.

## What

- **Import.** `convert`'s `keepouts` names each rule area of a plain stroke (a track, arc or circle of the
  Keep-Out layer that has no keep-out record) with the stroke itself: `Altium.KeepOut/<kind>/<numbers>`
  (`backends/altium/keepout_lines.py`). The name is in the alphabet of a DSL rule-area name, and a KiCad
  zone keeps it. So the stroke survives a KiCad file (flow B) and `import --to python` (flow A).
- **Writer.** `lower` gives each marked rule area of a board or a footprint back as its stroke: a track or
  an arc on the Keep-Out layer without the keep-out flag, free or owned by its component, with the
  stroke's width. A circle's two rings give one full arc. The area is counted written under `keep-out`,
  and not as a graphic.
- **Guard.** A marked area whose outline is no longer its stroke's band (beyond 10 nm), or that no longer
  forbids tracks, vias, pads and poured copper, or that forbids footprints, was edited after the
  conversion. It is written as a keep-out region, as any rule area is.
- **Equivalence.** Two drawings of a keep-out layer that pair as rule areas also compare their `form`:
  `stroke` or `area`. A line written back as a region is a `keepout-field` difference on `form`.

## Not in this change

- A keep-out track or arc with the flag (second flag byte 2) on the Keep-Out layer still comes back as a
  flagged region.
- Board cut-outs owned by a component (c0443).
- Un-routed and antennae findings (c0444).
- The derived PcbLib does not hold a footprint's keep-out strokes; the component in the PcbDoc does.

## Impact

- Code:
  - `src/fenolite/backends/altium/keepout_lines.py` (new)
  - `backends/altium/lower.py`
  - `convert/altium_to_kicad.py`
  - `checks/equivalence/shapes.py`
- Docs:
  - `docs/formats/altium/pcb-records.md`
  - `docs/equivalence.md`
  - `docs/evidence/sources.md` (S-2010)
  - `CHANGELOG.md`
