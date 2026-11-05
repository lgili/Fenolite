# c0411: rule areas in footprint definitions

## Why

A keep-out of a footprint belongs to the footprint: every board that places the part should get it.

- An Altium library (PcbLib) holds such keep-outs:
  - tracks, arcs, fills and regions with the keep-out flag on copper;
  - polygon cut-outs (`KIND=1` regions);
  - drawings on the Keep-Out layer.
- KiCad 10.0.6's `fp upgrade` makes each one a rule area (`zone` with `keepout`) inside the footprint.
  c0410 measured this and pins it in `test_library_keepouts_as_kicad_upgrades_them`.
- Fenolite's `FootprintDef` holds no rule area, and the KiCad footprint reader keeps a footprint's zones
  opaque. So c0410 drops the copper ones as a reported loss (`footprint-keepouts`, hint naming c0411).
  Keep-Out layer drawings of a footprint stay graphics of `Altium.KeepOut`, which no KiCad footprint can
  hold.

## What

- **Model.** `FootprintDef.keepouts` and `FootprintInstance.keepouts`: `Keepout` entities in the
  footprint's frame, in record order. The change is additive:
  - the canonical writer omits an empty tuple, so existing footprints keep their bytes;
  - the schemas, `frozen-v0.json` (additive keys) and the model review inventory are regenerated.
- **Altium import.**
  - The library adapter makes rule areas of library keep-outs, with the shapes and restrictions of the
    board import (c0407, c0410): bands of tracks and arcs, outlines of fills and regions, pour-only polygon
    cut-outs.
  - The board adapter keeps a component's keep-outs in its `FootprintInstance` instead of moving them to
    the board.
  - The `footprint-keepouts` loss of c0410 goes away.
- **Placement.** Placing a definition carries its rule areas into the instance (frame, side, layers swapped
  for a bottom placement). Board checks see an instance's rule areas as board rule areas in the board frame.
- **KiCad.**
  - The `.kicad_mod` and board writers write an instance's or definition's rule areas as footprint `zone`s
    with `keepout`.
  - The footprint reader projects such zones into `keepouts` and keeps every other zone opaque.
  - Rule areas of the Keep-Out layer drawings of a footprint come from `convert`, as for a board.
- **Altium writers.** The PcbLib writer and the PcbDoc writer (a component's primitives) write a footprint's
  rule areas as keep-out regions of the footprint, on the Keep-Out layer when they cover every copper layer.
- **Oracle proof.**
  - The authored library of c0410 through `fp upgrade` 10.0.6 and through Fenolite's import and KiCad
    writer gives the same rule areas: layers, restrictions, boxes within 10 µm, areas within 1 %.
  - A KiCad footprint with a rule area reads and writes back unchanged.
  - A board placing it passes `kicad-cli pcb drc` load.

## Sources

S-1720 … S-1729 are reserved for this change. Task 1.1 reads and records:

- the KiCad footprint file format pages (the `zone` of a footprint);
- KiCad's footprint rule area documentation;
- Altium's footprint keep-out documentation.

## Impact

- **Code:**
  - `model/library.py` and `model/board.py` (new fields), canonical JSON, the schemas and the model review
    inventory;
  - `backends/altium/adapter/copper.py`, `library.py` and `board.py`;
  - placement (`model` and `lens` placement of definitions);
  - `backends/kicad/mod.py`, `_fpmap.py` and `pcb.py`;
  - `backends/altium/pcblib.py`, `pcbdoc.py` and `lower.py`;
  - the checks that read rule areas.
- **Public surface:** a public model field, so the model version and `docs/design-model.md` need a line.
  `fenolite.dsl` footprint authoring does not change here.
- **Ordering:** it waits for c0409 to land, which changes the Altium footprint primitive import (its B8).

## Not here

| item | owner |
|---|---|
| A `fenolite.dsl` call to author rule areas in a footprint | a later change (Fenolite) |
| The restrictions a Keep-Out layer region holds (`KEEPOUTRESTRICTIONS`) | a later change (Fenolite) |
