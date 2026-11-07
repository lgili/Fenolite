# Tasks: c0439

## 1. Writers

- [x] 1.1 `rec.region_record(polygon_cutout=True)` writes `KIND=1` without the keep-out flag;
  `V7_LAYERS` names Multi-Layer `MULTILAYER`.
- [x] 1.2 `pcbdoc.free_records` and `pcblib.keepout_records` write a pour-only rule area as polygon cut-outs;
  `uv run pytest tests/unit/backends/altium/test_pour_cutouts.py`.

## 2. Taken in from c0438 (cac-altium-code, commit c0acf241c)

- [x] 2.1 `convert --to altium` gives copper graphics their KiCad net (`fpitems.with_graphic_nets`);
  `uv run pytest tests/unit/convert/test_polygon_cutouts.py`.
- [x] 2.2 Level 5 kind `copper-no-net`, its explain entry, docs and refrozen schemas;
  `uv run pytest tests/unit/checks/equivalence/test_codes.py`, `uv run python tools/gen_schemas.py --check`,
  `uv run python tools/gen_cli_surface.py --check`.

## 3. Evidence and docs

- [x] 3.1 `pcb-records.md` records the census of cut-outs (rows `-01`, `-02`, `-06`, `-08`; S-1980) and the round trip of row `-01` (S-1981);
  `uv run pytest tests/unit/test_format_facts.py`.
- [x] 3.2 altium-rounds-2 opens the kit `c0439-cutouts` (round trips of rows `-01` and `-06`) in Altium Designer:
  the cut-outs show as polygon cut-outs and DRC finds no new short or keep-out clearance violation (kit request).
  Result, Altium 24.5.2.23, 2026-11-06:
  - All four documents open with no dialog, message or repair prompt.
  - Polygon cut-outs (`KIND=1`) match the source per layer: `-01` Top 1 and Bottom 1; `-06` Top 8, Bottom 2
    and Multi-Layer 3. Free netted copper of `-01` matches the source (Top 32, Bottom 13).
  - After Repour All, DRC with each document's own rules:
    - `-01`: Short-Circuit 0 and Clearance 0, against 968 and 878 before this change.
    - `-06`: Clearance goes from 25 to 0 and Board Outline Clearance from 16 to 0; no Short-Circuit.
  - Findings outside this change, left to their own changes:
    - Un-Routed and Net Antennae on vias and tracks (c0444).
    - Board cut-outs owned by a component written as keep-outs (c0443).
    - Keep-Out-layer lines written as regions (c0442).
    - Mask and silk counts (c0440).
