# c0482: the source's pour is kept

## Why

A conversion to Altium pours every polygon itself (`pour="computed"`, c0215). The written copper is
Fenolite's, not the source's. On the maintainer's board (private; codes and counts only), F2 and F5
both fail equivalence:
- 2 `equiv.route-vias` errors: 2 stitching vias of two nets lose their connection under the computed pour;
- 2 `equiv.route-stub` warnings.

The conversion to KiCad (F4) keeps the source's pour as zone fills, and it passes. The way back drops
those fills and pours again.

## What Changes

- A conversion to KiCad carries, in the board property `Fenolite.Altium.Pours`, each polygon's region
  records as read (`Regions6` with their `ShapeBasedRegions6` twins). With them it carries:
  - the polygon's vertices as read, its net and its layer;
  - whether the source's own pour fails Fenolite's copper check.
- The Altium writer writes those records, with the new polygon index, under two conditions:
  - every polygon of the document has a carried pour with the written polygon's vertices, net and layer;
  - Fenolite's copper check finds no fault that the source's own pour does not have.
  Otherwise it computes the pour as before.
- The pour is found by vertices, net and layer, not by zone uuid. A script's build gives its zones other
  uuids, so `import --to python` and `build --target altium` (c0480) keep the pour too.
- The report counts no `zone-fill` change for a kept pour. `altium.zones-poured` says that the regions are
  the source's.

## Impact

- `src/fenolite/convert/zonepours.py` (new), `convert/to_kicad.py`, `convert/to_altium.py`,
  `convert/altium_to_kicad.py`, `backends/altium/pcbdoc.py`, `backends/altium/lower.py`.
- `docs/formats/altium/pcb-pour.md`.
- No change to a build of a script that carries no pour, or to a document whose polygons do not all
  match.
