# c0496: adding a remote zone leaves the other written pours unchanged

Found on: reviewing a private maintainer board on 2026-11-11 (codes only; nothing from the board is in
this change).

## Why

Adding zones far away from a net's pour changed the pour that Fenolite writes into the PcbDoc for unrelated
nets. The vias were grouped differently per segment, zero-length segments appeared, and Altium's
dead-copper analysis found a dead island in a pour that had none before. KiCad's fill of the same nets was
identical. So the writer, not the design, changed those pours.

`backends/altium/pcbdoc.py` explains most of it. `write_pcbdoc_result` keeps the source's poured regions
(c0482) only through `_carried_pour_records`. That function returns `None` unless every polygon of the
document has a carried pour with its vertices, net and layer. One new zone has none, so every polygon
falls back to the computed pour (`pour_reading`, c0215/c0463). A computed pour is not the source's region
set. So one remote zone rewrites the copper of every net.

The rest is the computed pour itself. Zero-length segments and a different grouping mean its output
depends on more than the polygon's own inputs. Possible sources are record order, polygon indices, or
objects far from the polygon.

## What Changes

- **Per-polygon carry.** A polygon whose carried pour matches (vertices, net, layer) keeps its carried
  regions, re-indexed, when no new or changed polygon could change it. That means no new or changed
  polygon on its layer whose outline, grown by the larger of the two clearances, meets its outline. The
  other polygons are computed. The copper check (`check_pour`) judges the whole written document, as
  today. A polygon it fails falls back as today, and only that polygon.
- **Computed pours depend on their own inputs.** The computed region records of a polygon depend only on
  its own record, the rules that apply to it, the objects within its outline grown by its largest
  clearance, and the polygons before it on its layer. They must be byte-identical when anything else
  changes, apart from the polygon index in the record prefix. Task 1.1 finds what breaks this (record order,
  the index, a global input) and fixes it.
- **No zero-length segments.** A written pour region holds no zero-length edge, and the pour writes no
  zero-length track or arc.
- **Explained otherwise.** A polygon whose written pour changes although none of its inputs changed is
  reported with `altium.pour-changed` (warning), naming the input that changed it. A silent change is a
  defect.

## Impact

- `src/fenolite/backends/altium/pcbdoc.py` (`write_pcbdoc_result`, `_carried_pour_records`).
- `src/fenolite/backends/altium/pour.py` (`pour_reading`), `pourrecord.py`.
- `src/fenolite/convert/zonepours.py` (no format change).
